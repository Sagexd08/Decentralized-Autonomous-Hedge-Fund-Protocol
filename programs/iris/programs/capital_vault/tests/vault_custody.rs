//! **The highest-priority security test in the repository** (v2 section 5).
//!
//! IRIS invariant 1: *agents never custody investor capital. Allocation
//! authority is not wallet control.* An agent can be handed 35% of the vault's
//! weight and still must not be able to move a single token out of it.
//!
//! These tests attack that invariant from every angle we can construct:
//!
//!   1. an agent PDA — the account the registry derives for an agent — cannot
//!      sign a withdrawal at all;
//!   2. an agent keypair that *can* sign still cannot drain a depositor's
//!      balance, because the balance PDA is seeded by the depositor;
//!   3. an agent cannot forge a balance account of its own;
//!   4. an agent cannot pose as the allocation engine and rewrite weights;
//!   5. the depositor themselves can withdraw, so the guards above are
//!      genuinely about authority and not just a broken instruction.
//!
//! Test 5 matters as much as the rest: a withdrawal path that rejects
//! *everyone* would pass tests 1–4 while proving nothing.
//!
//! These run on solana-program-test with `processor!()`, so they need neither
//! a validator nor the SBF toolchain — but they do need OpenSSL, which is why
//! `make anchor-test` runs them in Linux. See docker/anchor.Dockerfile.

use anchor_lang::solana_program::{account_info::AccountInfo, entrypoint::ProgramResult};
use anchor_lang::{InstructionData, ToAccountMetas};
use solana_program_test::{processor, BanksClientError, ProgramTest, ProgramTestContext};
use solana_sdk::{
    instruction::Instruction,
    program_pack::Pack,
    pubkey::Pubkey,
    signature::{Keypair, Signer},
    system_instruction,
    transaction::Transaction,
};

/// Anchor's generated `entry` wants `&'info [AccountInfo<'info>]` — the slice
/// and the infos sharing one lifetime — while `processor!` hands over a slice
/// whose lifetime is shorter than the infos it holds. The two are compatible in
/// practice (the harness keeps the accounts alive for the whole invocation) but
/// not to the borrow checker, so the standard Anchor test shim re-ties the
/// lifetimes. Confined to test code; the program itself contains no `unsafe`.
fn capital_vault_entry<'info>(
    program_id: &Pubkey,
    accounts: &[AccountInfo<'info>],
    data: &[u8],
) -> ProgramResult {
    let accounts: &'info [AccountInfo<'info>] = unsafe { std::mem::transmute(accounts) };
    capital_vault::entry(program_id, accounts, data)
}

const BALANCED: u8 = 1;
const DECIMALS: u8 = 6;
const DEPOSIT: u64 = 1_000_000_000; // 1,000 tokens

/// The registry's agent PDA seed. Kept in sync with agent_registry deliberately
/// by hand: if that seed ever changes, this test must be revisited rather than
/// silently continuing to attack an address no agent uses.
const AGENT_SEED: &[u8] = b"agent";

// ─── harness ────────────────────────────────────────────────────────────────

struct Harness {
    ctx: ProgramTestContext,
    mint: Keypair,
    investor: Keypair,
    investor_ata: Pubkey,
    config: Pubkey,
    vault_authority: Pubkey,
    vault_ata: Pubkey,
    pool_state: Pubkey,
    investor_balance: Pubkey,
}

fn pda(seeds: &[&[u8]]) -> Pubkey {
    Pubkey::find_program_address(seeds, &capital_vault::ID).0
}

fn ata(owner: &Pubkey, mint: &Pubkey) -> Pubkey {
    anchor_spl::associated_token::get_associated_token_address(owner, mint)
}

async fn setup() -> Harness {
    let mut pt = ProgramTest::new(
        "capital_vault",
        capital_vault::ID,
        processor!(capital_vault_entry),
    );
    pt.prefer_bpf(false);
    let mut ctx = pt.start_with_context().await;

    let payer = ctx.payer.insecure_clone();
    let mint = Keypair::new();
    let investor = Keypair::new();

    let config = pda(&[b"config"]);
    let vault_authority = pda(&[b"vault_authority"]);
    let vault_ata = ata(&vault_authority, &mint.pubkey());
    let pool_state = pda(&[b"pool_state", &[BALANCED]]);
    let investor_balance = pda(&[
        b"investor_pool",
        investor.pubkey().as_ref(),
        &[BALANCED],
    ]);
    let investor_ata = ata(&investor.pubkey(), &mint.pubkey());

    // fund the investor so it can pay rent for its own accounts
    send(
        &mut ctx,
        &[system_instruction::transfer(
            &payer.pubkey(),
            &investor.pubkey(),
            5_000_000_000,
        )],
        &[&payer],
    )
    .await
    .expect("fund investor");

    // create the stake mint
    let mint_rent = ctx
        .banks_client
        .get_rent()
        .await
        .unwrap()
        .minimum_balance(spl_token::state::Mint::LEN);
    send(
        &mut ctx,
        &[
            system_instruction::create_account(
                &payer.pubkey(),
                &mint.pubkey(),
                mint_rent,
                spl_token::state::Mint::LEN as u64,
                &spl_token::ID,
            ),
            spl_token::instruction::initialize_mint(
                &spl_token::ID,
                &mint.pubkey(),
                &payer.pubkey(),
                None,
                DECIMALS,
            )
            .unwrap(),
        ],
        &[&payer, &mint],
    )
    .await
    .expect("create mint");

    // investor ATA, funded
    send(
        &mut ctx,
        &[
            spl_associated_token_account::instruction::create_associated_token_account(
                &payer.pubkey(),
                &investor.pubkey(),
                &mint.pubkey(),
                &spl_token::ID,
            ),
            spl_token::instruction::mint_to(
                &spl_token::ID,
                &mint.pubkey(),
                &investor_ata,
                &payer.pubkey(),
                &[],
                DEPOSIT * 10,
            )
            .unwrap(),
        ],
        &[&payer],
    )
    .await
    .expect("fund investor ATA");

    // initialize the vault, then the balanced pool
    let init = Instruction {
        program_id: capital_vault::ID,
        accounts: capital_vault::accounts::Initialize {
            admin: payer.pubkey(),
            token_mint: mint.pubkey(),
            config,
            vault_authority,
            vault_token_account: vault_ata,
            token_program: spl_token::ID,
            associated_token_program: spl_associated_token_account::ID,
            system_program: solana_sdk::system_program::ID,
        }
        .to_account_metas(None),
        data: capital_vault::instruction::Initialize {}.data(),
    };
    let init_pool = Instruction {
        program_id: capital_vault::ID,
        accounts: capital_vault::accounts::InitPoolState {
            admin: payer.pubkey(),
            config,
            pool_state,
            system_program: solana_sdk::system_program::ID,
        }
        .to_account_metas(None),
        data: capital_vault::instruction::InitPoolState { pool: BALANCED }.data(),
    };
    send(&mut ctx, &[init, init_pool], &[&payer])
        .await
        .expect("initialize vault");

    Harness {
        ctx,
        mint,
        investor,
        investor_ata,
        config,
        vault_authority,
        vault_ata,
        pool_state,
        investor_balance,
    }
}

async fn send(
    ctx: &mut ProgramTestContext,
    ixs: &[Instruction],
    signers: &[&Keypair],
) -> Result<(), BanksClientError> {
    let blockhash = ctx.banks_client.get_latest_blockhash().await.unwrap();
    let tx = Transaction::new_signed_with_payer(
        ixs,
        Some(&ctx.payer.pubkey()),
        &[&[&ctx.payer.insecure_clone()], signers].concat(),
        blockhash,
    );
    ctx.banks_client.process_transaction(tx).await
}

/// Submit a transaction that is deliberately missing a required signature.
///
/// `Transaction::new_signed_with_payer` *panics* on a missing signer, which
/// would prove the point in the client and never reach the runtime. This signs
/// with whoever it can and submits anyway, so the rejection we assert on is the
/// validator's, not the SDK's.
async fn send_partially_signed(
    ctx: &mut ProgramTestContext,
    ixs: &[Instruction],
    signers: &[&Keypair],
) -> Result<(), BanksClientError> {
    let blockhash = ctx.banks_client.get_latest_blockhash().await.unwrap();
    let payer = ctx.payer.insecure_clone();
    let mut tx = Transaction::new_with_payer(ixs, Some(&payer.pubkey()));
    let mut all: Vec<&Keypair> = vec![&payer];
    all.extend_from_slice(signers);
    tx.partial_sign(&all, blockhash);
    ctx.banks_client.process_transaction(tx).await
}

impl Harness {
    fn deposit_ix(&self) -> Instruction {
        Instruction {
            program_id: capital_vault::ID,
            accounts: capital_vault::accounts::Deposit {
                investor: self.investor.pubkey(),
                config: self.config,
                token_mint: self.mint.pubkey(),
                investor_token_account: self.investor_ata,
                vault_authority: self.vault_authority,
                vault_token_account: self.vault_ata,
                investor_pool_balance: self.investor_balance,
                pool_state: self.pool_state,
                token_program: spl_token::ID,
                associated_token_program: spl_associated_token_account::ID,
                system_program: solana_sdk::system_program::ID,
            }
            .to_account_metas(None),
            data: capital_vault::instruction::Deposit {
                pool: BALANCED,
                amount: DEPOSIT,
            }
            .data(),
        }
    }

    /// A withdrawal built to look exactly like the investor's, but with
    /// `withdrawer` in the signer slot and `balance` as the balance account.
    fn withdraw_ix(
        &self,
        withdrawer: &Pubkey,
        withdrawer_ata: &Pubkey,
        balance: &Pubkey,
    ) -> Instruction {
        Instruction {
            program_id: capital_vault::ID,
            accounts: capital_vault::accounts::Withdraw {
                investor: *withdrawer,
                config: self.config,
                token_mint: self.mint.pubkey(),
                investor_token_account: *withdrawer_ata,
                vault_authority: self.vault_authority,
                vault_token_account: self.vault_ata,
                investor_pool_balance: *balance,
                pool_state: self.pool_state,
                token_program: spl_token::ID,
            }
            .to_account_metas(None),
            data: capital_vault::instruction::Withdraw {
                pool: BALANCED,
                amount: DEPOSIT,
            }
            .data(),
        }
    }

    async fn vault_balance(&mut self) -> u64 {
        let acct = self
            .ctx
            .banks_client
            .get_account(self.vault_ata)
            .await
            .unwrap()
            .expect("vault ATA exists");
        spl_token::state::Account::unpack(&acct.data).unwrap().amount
    }
}

/// The address the registry would derive for this agent.
fn agent_pda(agent_authority: &Pubkey) -> Pubkey {
    Pubkey::find_program_address(
        &[AGENT_SEED, agent_authority.as_ref()],
        &agent_registry_id(),
    )
    .0
}

fn agent_registry_id() -> Pubkey {
    "F4s8zTom7KLNLXAhRpbgwJ2dYSNg2hi4M1Rn4m9t71NN"
        .parse()
        .unwrap()
}

// ─── the invariant ──────────────────────────────────────────────────────────

/// **THE test.** An agent PDA is off-curve: no private key exists for it, and
/// only its owning program can sign for it via CPI. capital_vault::withdraw is
/// never reachable by CPI from agent_registry, so there is no path by which an
/// agent PDA can authorise a withdrawal. Proven here by trying.
#[tokio::test]
async fn agent_pda_cannot_sign_a_vault_withdrawal() {
    let mut h = setup().await;
    let investor = h.investor.insecure_clone();
    let deposit = h.deposit_ix();
    send(&mut h.ctx, &[deposit], &[&investor])
        .await
        .expect("investor deposit");

    let before = h.vault_balance().await;
    assert_eq!(before, DEPOSIT, "deposit should have landed in the vault");

    let agent_authority = Keypair::new();
    let agent = agent_pda(&agent_authority.pubkey());

    // First, the structural fact the whole invariant rests on: a program
    // derived address is off the ed25519 curve, so no private key for it
    // exists and no wallet can ever be made to sign as it.
    assert!(
        !agent.is_on_curve(),
        "an agent PDA must be off-curve; if this ever fails, a keypair for it          could exist and the custody boundary is gone"
    );

    // Now prove the runtime agrees. Submit the withdrawal with the agent in the
    // signer slot and no signature for it.
    let ix = h.withdraw_ix(&agent, &h.investor_ata, &h.investor_balance);
    let err = send_partially_signed(&mut h.ctx, &[ix], &[])
        .await
        .expect_err("an agent PDA must not be able to withdraw from the vault");

    let msg = format!("{err:?}");
    assert!(
        msg.contains("Signature") || msg.contains("signature"),
        "expected a signature-verification rejection, got: {msg}"
    );

    assert_eq!(
        h.vault_balance().await,
        before,
        "vault balance must be untouched after the attack"
    );
}

/// An agent whose execution address *is* a real keypair can sign — and still
/// cannot touch someone else's balance, because `investor_pool_balance` is
/// seeded by the signer's own key.
#[tokio::test]
async fn a_signing_agent_cannot_drain_a_depositors_balance() {
    let mut h = setup().await;
    let investor = h.investor.insecure_clone();
    let payer = h.ctx.payer.insecure_clone();
    let mint = h.mint.pubkey();
    let deposit = h.deposit_ix();
    send(&mut h.ctx, &[deposit], &[&investor])
        .await
        .expect("investor deposit");
    let before = h.vault_balance().await;

    let agent = Keypair::new();
    let fund = system_instruction::transfer(&payer.pubkey(), &agent.pubkey(), 2_000_000_000);
    let mk_ata = spl_associated_token_account::instruction::create_associated_token_account(
        &payer.pubkey(),
        &agent.pubkey(),
        &mint,
        &spl_token::ID,
    );
    send(&mut h.ctx, &[fund, mk_ata], &[&payer]).await.unwrap();
    let agent_ata = ata(&agent.pubkey(), &mint);

    // Signed by the agent, but pointing at the investor's balance PDA.
    let ix = h.withdraw_ix(&agent.pubkey(), &agent_ata, &h.investor_balance);
    let err = send(&mut h.ctx, &[ix], &[&agent])
        .await
        .expect_err("an agent must not withdraw against a depositor's balance");

    let msg = format!("{err:?}");
    assert!(
        msg.contains("ConstraintSeeds") || msg.contains("2006") || msg.contains("seeds"),
        "expected a seeds-constraint rejection, got: {msg}"
    );
    assert_eq!(h.vault_balance().await, before, "vault must be untouched");
}

/// Nor can the agent point at a balance PDA of its own: it never deposited, so
/// that account does not exist and `withdraw` will not create one.
#[tokio::test]
async fn an_agent_cannot_conjure_its_own_balance_account() {
    let mut h = setup().await;
    let investor = h.investor.insecure_clone();
    let payer = h.ctx.payer.insecure_clone();
    let mint = h.mint.pubkey();
    let deposit = h.deposit_ix();
    send(&mut h.ctx, &[deposit], &[&investor])
        .await
        .expect("investor deposit");
    let before = h.vault_balance().await;

    let agent = Keypair::new();
    let fund = system_instruction::transfer(&payer.pubkey(), &agent.pubkey(), 2_000_000_000);
    let mk_ata = spl_associated_token_account::instruction::create_associated_token_account(
        &payer.pubkey(),
        &agent.pubkey(),
        &mint,
        &spl_token::ID,
    );
    send(&mut h.ctx, &[fund, mk_ata], &[&payer]).await.unwrap();

    let agent_balance = pda(&[b"investor_pool", agent.pubkey().as_ref(), &[BALANCED]]);
    let agent_ata = ata(&agent.pubkey(), &mint);

    let ix = h.withdraw_ix(&agent.pubkey(), &agent_ata, &agent_balance);
    send(&mut h.ctx, &[ix], &[&agent])
        .await
        .expect_err("withdraw must not initialise a balance account");

    assert_eq!(h.vault_balance().await, before, "vault must be untouched");
}

/// Allocation authority is held by the allocation engine, and the vault checks
/// that by key. An agent cannot rewrite its own weight.
#[tokio::test]
async fn an_agent_cannot_impersonate_the_allocation_engine() {
    let mut h = setup().await;
    let payer = h.ctx.payer.insecure_clone();
    let agent = Keypair::new();
    let fund = system_instruction::transfer(&payer.pubkey(), &agent.pubkey(), 1_000_000_000);
    send(&mut h.ctx, &[fund], &[&payer]).await.unwrap();

    let ix = Instruction {
        program_id: capital_vault::ID,
        accounts: capital_vault::accounts::UpdateWeights {
            allocation_engine_signer: agent.pubkey(),
            config: h.config,
        }
        .to_account_metas(None),
        data: capital_vault::instruction::UpdateWeights {
            agents: vec![agent.pubkey()],
            weights: vec![1_000_000_000_000_000_000u64],
        }
        .data(),
    };

    let err = send(&mut h.ctx, &[ix], &[&agent])
        .await
        .expect_err("only the allocation engine may set weights");
    let msg = format!("{err:?}");
    assert!(
        msg.contains("OnlyAllocationEngine") || msg.contains("6") || msg.contains("Constraint"),
        "expected an authority rejection, got: {msg}"
    );
}

/// Control: the guards above must be about *authority*, not a withdrawal path
/// that rejects everyone. The depositor can take their own money out.
#[tokio::test]
async fn the_depositor_can_still_withdraw() {
    let mut h = setup().await;
    let investor = h.investor.insecure_clone();
    let deposit = h.deposit_ix();
    send(&mut h.ctx, &[deposit], &[&investor])
        .await
        .expect("investor deposit");
    assert_eq!(h.vault_balance().await, DEPOSIT);

    let ix = h.withdraw_ix(&investor.pubkey(), &h.investor_ata, &h.investor_balance);
    send(&mut h.ctx, &[ix], &[&investor])
        .await
        .expect("the depositor must be able to withdraw their own balance");

    assert_eq!(
        h.vault_balance().await,
        0,
        "the depositor's withdrawal should have emptied the vault"
    );
}
