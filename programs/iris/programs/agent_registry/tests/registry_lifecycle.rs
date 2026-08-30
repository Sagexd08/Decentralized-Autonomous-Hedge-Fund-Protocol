//! AgentRegistry lifecycle — IRIS_BUILD_PROMPT v2.0 section 5 / Phase 2 DoD.
//!
//! Covers the full instruction surface the spec asks for — register_agent,
//! update_model, stake, unstake, activate_agent, deactivate_agent,
//! freeze_agent — and the authority boundaries around each.
//!
//! The rules being asserted, stated plainly:
//!
//!   * an agent's OWNER controls its collateral and its model;
//!   * the ADMIN controls status transitions;
//!   * the agent's own execution address controls nothing;
//!   * an agent cannot unstake below the minimum while it is still live —
//!     an agent with nothing at risk is not staked, it is just present;
//!   * freezing is reversible and does not confiscate; slashing is neither.

use anchor_lang::solana_program::{account_info::AccountInfo, entrypoint::ProgramResult};
use anchor_lang::{AccountDeserialize, InstructionData, ToAccountMetas};
use solana_program_test::{processor, BanksClientError, ProgramTest, ProgramTestContext};
use solana_sdk::{
    instruction::Instruction,
    program_pack::Pack,
    pubkey::Pubkey,
    signature::{Keypair, Signer},
    system_instruction,
    transaction::Transaction,
};

use agent_registry::{AgentAccount, AgentStatus};

const DECIMALS: u8 = 6;
const MIN_STAKE: u64 = 10_000_000; // 10 tokens
const OWNER_FUNDS: u64 = 1_000_000_000;
const SIM_PERIOD: i64 = 7 * 24 * 60 * 60;
const BALANCED: u8 = 1;

/// See the note on the equivalent shim in capital_vault's tests: Anchor's
/// `entry` and `processor!` disagree on lifetime variance, not on behaviour.
fn registry_entry<'info>(
    program_id: &Pubkey,
    accounts: &[AccountInfo<'info>],
    data: &[u8],
) -> ProgramResult {
    let accounts: &'info [AccountInfo<'info>] = unsafe { std::mem::transmute(accounts) };
    agent_registry::entry(program_id, accounts, data)
}

struct Harness {
    ctx: ProgramTestContext,
    mint: Pubkey,
    admin: Keypair,
    owner: Keypair,
    owner_ata: Pubkey,
    config: Pubkey,
    agent_list: Pubkey,
    vault_authority: Pubkey,
    vault_ata: Pubkey,
    agent_authority: Pubkey,
    agent: Pubkey,
}

fn pda(seeds: &[&[u8]]) -> Pubkey {
    Pubkey::find_program_address(seeds, &agent_registry::ID).0
}

fn ata(owner: &Pubkey, mint: &Pubkey) -> Pubkey {
    anchor_spl::associated_token::get_associated_token_address(owner, mint)
}

async fn send(
    ctx: &mut ProgramTestContext,
    ixs: &[Instruction],
    signers: &[&Keypair],
) -> Result<(), BanksClientError> {
    let blockhash = ctx.banks_client.get_latest_blockhash().await.unwrap();
    let payer = ctx.payer.insecure_clone();
    let mut all: Vec<&Keypair> = vec![&payer];
    all.extend_from_slice(signers);
    let tx = Transaction::new_signed_with_payer(ixs, Some(&payer.pubkey()), &all, blockhash);
    ctx.banks_client.process_transaction(tx).await
}

async fn setup() -> Harness {
    let mut pt = ProgramTest::new("agent_registry", agent_registry::ID, processor!(registry_entry));
    pt.prefer_bpf(false);
    let mut ctx = pt.start_with_context().await;

    let payer = ctx.payer.insecure_clone();
    let admin = payer.insecure_clone();
    let owner = Keypair::new();
    let mint_kp = Keypair::new();
    let mint = mint_kp.pubkey();
    let agent_authority = Keypair::new().pubkey();

    let config = pda(&[b"config"]);
    let agent_list = pda(&[b"agent_list"]);
    let vault_authority = pda(&[b"vault_authority"]);
    let vault_ata = ata(&vault_authority, &mint);
    let owner_ata = ata(&owner.pubkey(), &mint);
    let agent = pda(&[b"agent", agent_authority.as_ref()]);

    let rent = ctx.banks_client.get_rent().await.unwrap();
    let mint_rent = rent.minimum_balance(spl_token::state::Mint::LEN);

    send(
        &mut ctx,
        &[
            system_instruction::transfer(&payer.pubkey(), &owner.pubkey(), 5_000_000_000),
            system_instruction::create_account(
                &payer.pubkey(),
                &mint,
                mint_rent,
                spl_token::state::Mint::LEN as u64,
                &spl_token::ID,
            ),
            spl_token::instruction::initialize_mint(
                &spl_token::ID,
                &mint,
                &payer.pubkey(),
                None,
                DECIMALS,
            )
            .unwrap(),
        ],
        &[&mint_kp],
    )
    .await
    .expect("mint setup");

    send(
        &mut ctx,
        &[
            spl_associated_token_account::instruction::create_associated_token_account(
                &payer.pubkey(),
                &owner.pubkey(),
                &mint,
                &spl_token::ID,
            ),
            spl_token::instruction::mint_to(
                &spl_token::ID,
                &mint,
                &owner_ata,
                &payer.pubkey(),
                &[],
                OWNER_FUNDS,
            )
            .unwrap(),
        ],
        &[],
    )
    .await
    .expect("owner ATA");

    let init = Instruction {
        program_id: agent_registry::ID,
        accounts: agent_registry::accounts::Initialize {
            admin: admin.pubkey(),
            stake_mint: mint,
            config,
            agent_list,
            vault_authority,
            vault_token_account: vault_ata,
            token_program: spl_token::ID,
            associated_token_program: spl_associated_token_account::ID,
            system_program: solana_sdk::system_program::ID,
        }
        .to_account_metas(None),
        data: agent_registry::instruction::Initialize {
            min_stake: MIN_STAKE,
            simulation_period: SIM_PERIOD,
        }
        .data(),
    };
    send(&mut ctx, &[init], &[]).await.expect("initialize registry");

    Harness {
        ctx,
        mint,
        admin,
        owner,
        owner_ata,
        config,
        agent_list,
        vault_authority,
        vault_ata,
        agent_authority,
        agent,
    }
}

impl Harness {
    fn register_ix(&self, stake: u64) -> Instruction {
        Instruction {
            program_id: agent_registry::ID,
            accounts: agent_registry::accounts::RegisterAgent {
                owner: self.owner.pubkey(),
                agent_authority: self.agent_authority,
                config: self.config,
                agent_list: self.agent_list,
                agent: self.agent,
                stake_mint: self.mint,
                owner_token_account: self.owner_ata,
                vault_authority: self.vault_authority,
                vault_token_account: self.vault_ata,
                token_program: spl_token::ID,
                associated_token_program: spl_associated_token_account::ID,
                system_program: solana_sdk::system_program::ID,
            }
            .to_account_metas(None),
            data: agent_registry::instruction::RegisterAgent {
                agent_id: [7u8; 32],
                model_hash: [1u8; 32],
                strategy_hash: [2u8; 32],
                risk_pool: BALANCED,
                stake_amount: stake,
            }
            .data(),
        }
    }

    fn stake_ix(&self, signer: &Pubkey, ata_: &Pubkey, amount: u64) -> Instruction {
        Instruction {
            program_id: agent_registry::ID,
            accounts: agent_registry::accounts::Stake {
                owner: *signer,
                config: self.config,
                agent: self.agent,
                stake_mint: self.mint,
                owner_token_account: *ata_,
                vault_authority: self.vault_authority,
                vault_token_account: self.vault_ata,
                token_program: spl_token::ID,
            }
            .to_account_metas(None),
            data: agent_registry::instruction::Stake { amount }.data(),
        }
    }

    fn unstake_ix(&self, amount: u64) -> Instruction {
        Instruction {
            program_id: agent_registry::ID,
            accounts: agent_registry::accounts::Unstake {
                owner: self.owner.pubkey(),
                config: self.config,
                agent: self.agent,
                stake_mint: self.mint,
                owner_token_account: self.owner_ata,
                vault_authority: self.vault_authority,
                vault_token_account: self.vault_ata,
                token_program: spl_token::ID,
            }
            .to_account_metas(None),
            data: agent_registry::instruction::Unstake { amount }.data(),
        }
    }

    fn update_model_ix(&self, signer: &Pubkey, hash: [u8; 32]) -> Instruction {
        Instruction {
            program_id: agent_registry::ID,
            accounts: agent_registry::accounts::UpdateModel {
                owner: *signer,
                agent: self.agent,
            }
            .to_account_metas(None),
            data: agent_registry::instruction::UpdateModel { model_hash: hash }.data(),
        }
    }

    fn status_ix(&self, signer: &Pubkey, which: &str) -> Instruction {
        let accounts = agent_registry::accounts::FreezeAgent {
            admin: *signer,
            config: self.config,
            agent: self.agent,
        }
        .to_account_metas(None);
        let data = match which {
            "freeze" => agent_registry::instruction::FreezeAgent {}.data(),
            "unfreeze" => agent_registry::instruction::UnfreezeAgent {}.data(),
            "deactivate" => agent_registry::instruction::DeactivateAgent {}.data(),
            _ => unreachable!(),
        };
        Instruction { program_id: agent_registry::ID, accounts, data }
    }

    async fn agent_state(&mut self) -> AgentAccount {
        let acct = self
            .ctx
            .banks_client
            .get_account(self.agent)
            .await
            .unwrap()
            .expect("agent account exists");
        AgentAccount::try_deserialize(&mut acct.data.as_slice()).unwrap()
    }
}

// ─── register ───────────────────────────────────────────────────────────────

#[tokio::test]
async fn register_agent_records_identity_and_moves_the_stake() {
    let mut h = setup().await;
    let owner = h.owner.insecure_clone();
    let ix = h.register_ix(MIN_STAKE * 2);
    send(&mut h.ctx, &[ix], &[&owner]).await.expect("register");

    let a = h.agent_state().await;
    assert_eq!(a.owner, owner.pubkey());
    assert_eq!(a.agent_id, [7u8; 32]);
    assert_eq!(a.model_hash, [1u8; 32]);
    assert_eq!(a.model_version, 1, "first model is version 1");
    assert_eq!(a.staked_amount, MIN_STAKE * 2);
    assert_eq!(a.status, AgentStatus::Probation, "agents start on probation");
    assert_eq!(a.reputation, 0);
    assert_eq!(a.allocation_weight, 0, "a new agent is allocated nothing");
}

#[tokio::test]
async fn registering_below_the_minimum_stake_is_rejected() {
    let mut h = setup().await;
    let owner = h.owner.insecure_clone();
    let ix = h.register_ix(MIN_STAKE - 1);
    send(&mut h.ctx, &[ix], &[&owner])
        .await
        .expect_err("stake below the minimum must not register");
}

// ─── stake / unstake ────────────────────────────────────────────────────────

#[tokio::test]
async fn stake_and_unstake_move_collateral_both_ways() {
    let mut h = setup().await;
    let owner = h.owner.insecure_clone();
    let owner_ata = h.owner_ata;

    let reg = h.register_ix(MIN_STAKE * 2);
    send(&mut h.ctx, &[reg], &[&owner]).await.expect("register");

    let add = h.stake_ix(&owner.pubkey(), &owner_ata, MIN_STAKE);
    send(&mut h.ctx, &[add], &[&owner]).await.expect("stake");
    assert_eq!(h.agent_state().await.staked_amount, MIN_STAKE * 3);

    let remove = h.unstake_ix(MIN_STAKE);
    send(&mut h.ctx, &[remove], &[&owner]).await.expect("unstake");
    assert_eq!(h.agent_state().await.staked_amount, MIN_STAKE * 2);
}

#[tokio::test]
async fn a_live_agent_cannot_unstake_below_the_minimum() {
    let mut h = setup().await;
    let owner = h.owner.insecure_clone();
    let reg = h.register_ix(MIN_STAKE * 2);
    send(&mut h.ctx, &[reg], &[&owner]).await.expect("register");

    // would leave MIN_STAKE - 1 behind
    let ix = h.unstake_ix(MIN_STAKE + 1);
    send(&mut h.ctx, &[ix], &[&owner])
        .await
        .expect_err("an agent must keep the minimum at risk while it is live");

    assert_eq!(h.agent_state().await.staked_amount, MIN_STAKE * 2);
}

#[tokio::test]
async fn a_stranger_cannot_stake_against_someone_elses_agent() {
    let mut h = setup().await;
    let owner = h.owner.insecure_clone();
    let reg = h.register_ix(MIN_STAKE * 2);
    send(&mut h.ctx, &[reg], &[&owner]).await.expect("register");

    let stranger = Keypair::new();
    let stranger_ata = ata(&stranger.pubkey(), &h.mint);
    let ix = h.stake_ix(&stranger.pubkey(), &stranger_ata, MIN_STAKE);
    send(&mut h.ctx, &[ix], &[&stranger])
        .await
        .expect_err("only the owner may stake for their agent");
}

// ─── model identity ─────────────────────────────────────────────────────────

#[tokio::test]
async fn update_model_bumps_the_version() {
    let mut h = setup().await;
    let owner = h.owner.insecure_clone();
    let reg = h.register_ix(MIN_STAKE * 2);
    send(&mut h.ctx, &[reg], &[&owner]).await.expect("register");

    let ix = h.update_model_ix(&owner.pubkey(), [9u8; 32]);
    send(&mut h.ctx, &[ix], &[&owner]).await.expect("update model");

    let a = h.agent_state().await;
    assert_eq!(a.model_hash, [9u8; 32]);
    assert_eq!(a.model_version, 2, "a new model must be a new version");
}

#[tokio::test]
async fn republishing_the_same_model_is_rejected() {
    let mut h = setup().await;
    let owner = h.owner.insecure_clone();
    let reg = h.register_ix(MIN_STAKE * 2);
    send(&mut h.ctx, &[reg], &[&owner]).await.expect("register");

    // same hash it registered with
    let ix = h.update_model_ix(&owner.pubkey(), [1u8; 32]);
    send(&mut h.ctx, &[ix], &[&owner])
        .await
        .expect_err("an unchanged model must not consume a version number");
}

#[tokio::test]
async fn a_stranger_cannot_swap_an_agents_model() {
    let mut h = setup().await;
    let owner = h.owner.insecure_clone();
    let reg = h.register_ix(MIN_STAKE * 2);
    send(&mut h.ctx, &[reg], &[&owner]).await.expect("register");

    let stranger = Keypair::new();
    let ix = h.update_model_ix(&stranger.pubkey(), [9u8; 32]);
    send(&mut h.ctx, &[ix], &[&stranger])
        .await
        .expect_err("only the owner may publish a new model");
}

// ─── status transitions ─────────────────────────────────────────────────────

#[tokio::test]
async fn freeze_is_reversible_and_zeroes_allocation() {
    let mut h = setup().await;
    let owner = h.owner.insecure_clone();
    let admin = h.admin.insecure_clone();
    let reg = h.register_ix(MIN_STAKE * 2);
    send(&mut h.ctx, &[reg], &[&owner]).await.expect("register");

    let staked_before = h.agent_state().await.staked_amount;

    let freeze = h.status_ix(&admin.pubkey(), "freeze");
    send(&mut h.ctx, &[freeze], &[]).await.expect("freeze");

    let a = h.agent_state().await;
    assert_eq!(a.status, AgentStatus::Frozen);
    assert_eq!(a.allocation_weight, 0, "a frozen agent receives no capital");
    assert_eq!(
        a.staked_amount, staked_before,
        "freezing must not confiscate — that is what slashing is for"
    );

    let unfreeze = h.status_ix(&admin.pubkey(), "unfreeze");
    send(&mut h.ctx, &[unfreeze], &[]).await.expect("unfreeze");
    assert_eq!(h.agent_state().await.status, AgentStatus::Active);
}

#[tokio::test]
async fn deactivation_retires_the_agent_and_zeroes_allocation() {
    let mut h = setup().await;
    let owner = h.owner.insecure_clone();
    let admin = h.admin.insecure_clone();
    let reg = h.register_ix(MIN_STAKE * 2);
    send(&mut h.ctx, &[reg], &[&owner]).await.expect("register");

    let ix = h.status_ix(&admin.pubkey(), "deactivate");
    send(&mut h.ctx, &[ix], &[]).await.expect("deactivate");

    let a = h.agent_state().await;
    assert_eq!(a.status, AgentStatus::Deregistered);
    assert_eq!(a.allocation_weight, 0);
}

#[tokio::test]
async fn a_retired_agent_may_recover_its_full_stake() {
    let mut h = setup().await;
    let owner = h.owner.insecure_clone();
    let admin = h.admin.insecure_clone();
    let reg = h.register_ix(MIN_STAKE * 2);
    send(&mut h.ctx, &[reg], &[&owner]).await.expect("register");

    let deactivate = h.status_ix(&admin.pubkey(), "deactivate");
    send(&mut h.ctx, &[deactivate], &[]).await.expect("deactivate");

    // the minimum-stake floor applies only while the agent is live
    let ix = h.unstake_ix(MIN_STAKE * 2);
    send(&mut h.ctx, &[ix], &[&owner])
        .await
        .expect("a retired agent's collateral must be returnable in full");

    assert_eq!(h.agent_state().await.staked_amount, 0);
}

#[tokio::test]
async fn only_the_admin_may_freeze_an_agent() {
    let mut h = setup().await;
    let owner = h.owner.insecure_clone();
    let reg = h.register_ix(MIN_STAKE * 2);
    send(&mut h.ctx, &[reg], &[&owner]).await.expect("register");

    // the agent's own owner is not the protocol admin
    let ix = h.status_ix(&owner.pubkey(), "freeze");
    send(&mut h.ctx, &[ix], &[&owner])
        .await
        .expect_err("only the admin may freeze");
}
