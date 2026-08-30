use anchor_lang::prelude::*;
use anchor_spl::{
    associated_token::AssociatedToken,
    token_interface::{
        self, Mint, TokenAccount, TokenInterface, TransferChecked,
    },
};

declare_id!("F4s8zTom7KLNLXAhRpbgwJ2dYSNg2hi4M1Rn4m9t71NN");

const DEFAULT_MIN_STAKE: u64 = 10_000_000_000; // placeholder, adjust to your mint decimals
const DEFAULT_SIMULATION_PERIOD: i64 = 7 * 24 * 60 * 60; // 7 days

#[program]
pub mod agent_registry {
    use super::*;

    pub fn initialize(
        ctx: Context<Initialize>,
        min_stake: u64,
        simulation_period: i64,
    ) -> Result<()> {
        let config = &mut ctx.accounts.config;
        let agent_list = &mut ctx.accounts.agent_list;

        config.admin = ctx.accounts.admin.key();
        config.stake_mint = ctx.accounts.stake_mint.key();
        config.min_stake = min_stake;
        config.simulation_period = simulation_period;
        config.vault_authority_bump = ctx.bumps.vault_authority;
        config.bump = ctx.bumps.config;

        agent_list.agents = Vec::new();
        agent_list.bump = ctx.bumps.agent_list;

        Ok(())
    }

    pub fn register_agent(
        ctx: Context<RegisterAgent>,
        agent_id: [u8; 32],
        model_hash: [u8; 32],
        strategy_hash: [u8; 32],
        risk_pool: u8,
        stake_amount: u64,
    ) -> Result<()> {
        require!(risk_pool <= 2, RegistryError::InvalidPool);
        require!(
            stake_amount >= ctx.accounts.config.min_stake,
            RegistryError::InsufficientStake
        );

        let agent = &mut ctx.accounts.agent;
        require!(
            agent.status == AgentStatus::Unregistered,
            RegistryError::AlreadyRegistered
        );

        let clock = Clock::get()?;
        let decimals = ctx.accounts.stake_mint.decimals;

        let cpi_accounts = TransferChecked {
            from: ctx.accounts.owner_token_account.to_account_info(),
            mint: ctx.accounts.stake_mint.to_account_info(),
            to: ctx.accounts.vault_token_account.to_account_info(),
            authority: ctx.accounts.owner.to_account_info(),
        };

        let cpi_program = ctx.accounts.token_program.to_account_info();
        let cpi_ctx = CpiContext::new(cpi_program, cpi_accounts);

        token_interface::transfer_checked(cpi_ctx, stake_amount, decimals)?;

        agent.owner = ctx.accounts.owner.key();
        agent.agent_id = agent_id;
        agent.agent_address = ctx.accounts.agent_authority.key();
        agent.model_hash = model_hash;
        agent.model_version = 1;
        agent.strategy_hash = strategy_hash;
        agent.staked_amount = stake_amount;
        agent.reputation = 0;
        agent.allocation_weight = 0;
        agent.registered_at = clock.unix_timestamp;
        agent.simulation_ends = clock.unix_timestamp + ctx.accounts.config.simulation_period;
        agent.status = AgentStatus::Probation;
        agent.risk_pool = risk_pool;
        agent.bump = ctx.bumps.agent;

        let list = &mut ctx.accounts.agent_list;
        list.agents.push(ctx.accounts.agent_authority.key());

        emit!(AgentRegisteredEvent {
            agent: ctx.accounts.agent_authority.key(),
            risk_pool,
            stake: stake_amount,
        });

        Ok(())
    }

    pub fn activate_agent(ctx: Context<ActivateAgent>) -> Result<()> {
        let clock = Clock::get()?;
        let agent = &mut ctx.accounts.agent;

        require!(
            agent.status == AgentStatus::Probation,
            RegistryError::NotInProbation
        );
        require!(
            clock.unix_timestamp >= agent.simulation_ends,
            RegistryError::SimulationNotComplete
        );

        agent.status = AgentStatus::Active;

        emit!(AgentActivatedEvent {
            agent: agent.agent_address
        });

        Ok(())
    }

    pub fn slash_agent(ctx: Context<SlashAgent>, slash_bps: u16) -> Result<()> {
        require!(slash_bps <= 10_000, RegistryError::InvalidSlashBps);

        let agent = &mut ctx.accounts.agent;
        require!(agent.status == AgentStatus::Active, RegistryError::AgentNotActive);

        let slash_amount = ((agent.staked_amount as u128) * (slash_bps as u128) / 10_000u128) as u64;
        let remaining = agent
            .staked_amount
            .checked_sub(slash_amount)
            .ok_or(RegistryError::MathOverflow)?;

        let decimals = ctx.accounts.stake_mint.decimals;

        let signer_seeds: &[&[&[u8]]] = &[&[
            b"vault_authority",
            &[ctx.accounts.config.vault_authority_bump],
        ]];

        let cpi_accounts = TransferChecked {
            from: ctx.accounts.vault_token_account.to_account_info(),
            mint: ctx.accounts.stake_mint.to_account_info(),
            to: ctx.accounts.treasury_token_account.to_account_info(),
            authority: ctx.accounts.vault_authority.to_account_info(),
        };

        let cpi_program = ctx.accounts.token_program.to_account_info();
        let cpi_ctx = CpiContext::new_with_signer(cpi_program, cpi_accounts, signer_seeds);

        token_interface::transfer_checked(cpi_ctx, slash_amount, decimals)?;

        agent.staked_amount = remaining;
        agent.status = AgentStatus::Slashed;

        emit!(AgentSlashedEvent {
            agent: agent.agent_address,
            slashed_amount: slash_amount,
        });

        Ok(())
    }

    /// Publish a new model version. Model identity is persistent and versioned
    /// (v2 invariant 3), so the hash must actually change — silently
    /// "upgrading" to the same weights would make version history meaningless.
    pub fn update_model(ctx: Context<UpdateModel>, model_hash: [u8; 32]) -> Result<()> {
        let agent = &mut ctx.accounts.agent;
        require!(
            agent.status != AgentStatus::Unregistered
                && agent.status != AgentStatus::Deregistered,
            RegistryError::AgentNotRegistered
        );
        require!(model_hash != agent.model_hash, RegistryError::ModelUnchanged);

        agent.model_hash = model_hash;
        agent.model_version = agent
            .model_version
            .checked_add(1)
            .ok_or(RegistryError::MathOverflow)?;

        emit!(ModelUpdatedEvent {
            agent: agent.agent_address,
            model_hash,
            model_version: agent.model_version,
        });

        Ok(())
    }

    /// Add collateral. Slashed and deregistered agents cannot top up their way
    /// back in; that is what the status transitions are for.
    pub fn stake(ctx: Context<Stake>, amount: u64) -> Result<()> {
        require!(amount > 0, RegistryError::ZeroAmount);
        require!(
            matches!(
                ctx.accounts.agent.status,
                AgentStatus::Probation | AgentStatus::Active | AgentStatus::Frozen
            ),
            RegistryError::AgentNotRegistered
        );

        let decimals = ctx.accounts.stake_mint.decimals;
        let cpi_ctx = CpiContext::new(
            ctx.accounts.token_program.to_account_info(),
            TransferChecked {
                from: ctx.accounts.owner_token_account.to_account_info(),
                mint: ctx.accounts.stake_mint.to_account_info(),
                to: ctx.accounts.vault_token_account.to_account_info(),
                authority: ctx.accounts.owner.to_account_info(),
            },
        );
        token_interface::transfer_checked(cpi_ctx, amount, decimals)?;

        let agent = &mut ctx.accounts.agent;
        agent.staked_amount = agent
            .staked_amount
            .checked_add(amount)
            .ok_or(RegistryError::MathOverflow)?;

        emit!(StakeChangedEvent {
            agent: agent.agent_address,
            staked_amount: agent.staked_amount,
            delta: amount as i128,
        });

        Ok(())
    }

    /// Withdraw collateral, down to but never below the configured minimum
    /// while the agent is still live. An agent that could unstake to zero and
    /// keep trading would have nothing at risk.
    pub fn unstake(ctx: Context<Unstake>, amount: u64) -> Result<()> {
        require!(amount > 0, RegistryError::ZeroAmount);

        let config = &ctx.accounts.config;
        let agent = &ctx.accounts.agent;

        require!(
            agent.status != AgentStatus::Slashed,
            RegistryError::AgentSlashed
        );

        let remaining = agent
            .staked_amount
            .checked_sub(amount)
            .ok_or(RegistryError::InsufficientStake)?;

        // Only a fully deregistered agent may take its collateral to zero.
        if agent.status != AgentStatus::Deregistered {
            require!(remaining >= config.min_stake, RegistryError::InsufficientStake);
        }

        let decimals = ctx.accounts.stake_mint.decimals;
        let signer_seeds: &[&[&[u8]]] =
            &[&[b"vault_authority", &[config.vault_authority_bump]]];

        let cpi_ctx = CpiContext::new_with_signer(
            ctx.accounts.token_program.to_account_info(),
            TransferChecked {
                from: ctx.accounts.vault_token_account.to_account_info(),
                mint: ctx.accounts.stake_mint.to_account_info(),
                to: ctx.accounts.owner_token_account.to_account_info(),
                authority: ctx.accounts.vault_authority.to_account_info(),
            },
            signer_seeds,
        );
        token_interface::transfer_checked(cpi_ctx, amount, decimals)?;

        let agent = &mut ctx.accounts.agent;
        agent.staked_amount = remaining;

        emit!(StakeChangedEvent {
            agent: agent.agent_address,
            staked_amount: remaining,
            delta: -(amount as i128),
        });

        Ok(())
    }

    /// Retire an agent. Its allocation weight drops to zero immediately —
    /// a deactivated agent must not keep receiving capital.
    pub fn deactivate_agent(ctx: Context<DeactivateAgent>) -> Result<()> {
        let agent = &mut ctx.accounts.agent;
        require!(
            agent.status != AgentStatus::Unregistered
                && agent.status != AgentStatus::Deregistered,
            RegistryError::AgentNotRegistered
        );

        agent.status = AgentStatus::Deregistered;
        agent.allocation_weight = 0;

        emit!(AgentStatusChangedEvent {
            agent: agent.agent_address,
            status: AgentStatus::Deregistered,
        });

        Ok(())
    }

    /// Halt an agent without confiscating its stake — the risk engine's
    /// intermediate response, between "fine" and "slashed" (v2 section 5).
    /// Reversible via `unfreeze_agent`.
    pub fn freeze_agent(ctx: Context<FreezeAgent>) -> Result<()> {
        let agent = &mut ctx.accounts.agent;
        require!(
            matches!(agent.status, AgentStatus::Probation | AgentStatus::Active),
            RegistryError::AgentNotActive
        );

        agent.status = AgentStatus::Frozen;
        agent.allocation_weight = 0;

        emit!(AgentStatusChangedEvent {
            agent: agent.agent_address,
            status: AgentStatus::Frozen,
        });

        Ok(())
    }

    pub fn unfreeze_agent(ctx: Context<FreezeAgent>) -> Result<()> {
        let agent = &mut ctx.accounts.agent;
        require!(agent.status == AgentStatus::Frozen, RegistryError::AgentNotFrozen);

        agent.status = AgentStatus::Active;

        emit!(AgentStatusChangedEvent {
            agent: agent.agent_address,
            status: AgentStatus::Active,
        });

        Ok(())
    }

    pub fn get_active_agents(ctx: Context<GetActiveAgents>) -> Result<Vec<Pubkey>> {
        let mut active = Vec::new();

        for agent_key in ctx.accounts.agent_list.agents.iter() {
            let data = ctx
                .remaining_accounts
                .iter()
                .find(|a| a.key() == *agent_key)
                .ok_or(RegistryError::MissingAgentAccount)?;

            let mut data_slice: &[u8] = &data.try_borrow_data()?;
            let agent_account = AgentAccount::try_deserialize(&mut data_slice)?;

            if agent_account.status == AgentStatus::Active {
                active.push(agent_account.agent_address);
            }
        }

        Ok(active)
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,

    pub stake_mint: InterfaceAccount<'info, Mint>,

    #[account(
        init,
        payer = admin,
        seeds = [b"config"],
        bump,
        space = 8 + RegistryConfig::INIT_SPACE
    )]
    pub config: Account<'info, RegistryConfig>,

    #[account(
        init,
        payer = admin,
        seeds = [b"agent_list"],
        bump,
        space = 8 + AgentList::INIT_SPACE
    )]
    pub agent_list: Account<'info, AgentList>,

    /// CHECK: PDA authority for vault ATA
    #[account(
        seeds = [b"vault_authority"],
        bump
    )]
    pub vault_authority: UncheckedAccount<'info>,

    #[account(
        init,
        payer = admin,
        associated_token::mint = stake_mint,
        associated_token::authority = vault_authority,
        associated_token::token_program = token_program
    )]
    pub vault_token_account: InterfaceAccount<'info, TokenAccount>,

    pub token_program: Interface<'info, TokenInterface>,
    pub associated_token_program: Program<'info, AssociatedToken>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct RegisterAgent<'info> {
    #[account(mut)]
    pub owner: Signer<'info>,

    /// CHECK: execution address / identity of the agent
    pub agent_authority: UncheckedAccount<'info>,

    #[account(
        mut,
        seeds = [b"config"],
        bump = config.bump
    )]
    pub config: Account<'info, RegistryConfig>,

    #[account(
        mut,
        seeds = [b"agent_list"],
        bump = agent_list.bump
    )]
    pub agent_list: Account<'info, AgentList>,

    #[account(
        init,
        payer = owner,
        seeds = [b"agent", agent_authority.key().as_ref()],
        bump,
        space = 8 + AgentAccount::INIT_SPACE
    )]
    pub agent: Account<'info, AgentAccount>,

    pub stake_mint: InterfaceAccount<'info, Mint>,

    #[account(
        mut,
        constraint = owner_token_account.owner == owner.key(),
        constraint = owner_token_account.mint == stake_mint.key()
    )]
    pub owner_token_account: InterfaceAccount<'info, TokenAccount>,

    /// CHECK: PDA authority for vault ATA
    #[account(
        seeds = [b"vault_authority"],
        bump = config.vault_authority_bump
    )]
    pub vault_authority: UncheckedAccount<'info>,

    #[account(
        mut,
        associated_token::mint = stake_mint,
        associated_token::authority = vault_authority,
        associated_token::token_program = token_program
    )]
    pub vault_token_account: InterfaceAccount<'info, TokenAccount>,

    pub token_program: Interface<'info, TokenInterface>,
    pub associated_token_program: Program<'info, AssociatedToken>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct ActivateAgent<'info> {
    pub admin: Signer<'info>,

    #[account(
        seeds = [b"config"],
        bump = config.bump,
        has_one = admin @ RegistryError::Unauthorized
    )]
    pub config: Account<'info, RegistryConfig>,

    #[account(
        mut,
        seeds = [b"agent", agent.agent_address.as_ref()],
        bump = agent.bump
    )]
    pub agent: Account<'info, AgentAccount>,
}

#[derive(Accounts)]
pub struct SlashAgent<'info> {
    pub admin: Signer<'info>,

    #[account(
        seeds = [b"config"],
        bump = config.bump,
        has_one = admin @ RegistryError::Unauthorized
    )]
    pub config: Account<'info, RegistryConfig>,

    pub stake_mint: InterfaceAccount<'info, Mint>,

    #[account(
        mut,
        seeds = [b"agent", agent.agent_address.as_ref()],
        bump = agent.bump
    )]
    pub agent: Account<'info, AgentAccount>,

    /// CHECK: PDA authority for vault ATA
    #[account(
        seeds = [b"vault_authority"],
        bump = config.vault_authority_bump
    )]
    pub vault_authority: UncheckedAccount<'info>,

    #[account(
        mut,
        associated_token::mint = stake_mint,
        associated_token::authority = vault_authority,
        associated_token::token_program = token_program
    )]
    pub vault_token_account: InterfaceAccount<'info, TokenAccount>,

    #[account(
        mut,
        constraint = treasury_token_account.mint == stake_mint.key()
    )]
    pub treasury_token_account: InterfaceAccount<'info, TokenAccount>,

    pub token_program: Interface<'info, TokenInterface>,
}

// ── Accounts for the section 5 instruction surface ──────────────────────────
//
// Authority model, stated once because it is the whole point:
//   * the agent's OWNER signs stake / unstake / update_model — it is their
//     collateral and their model;
//   * the ADMIN signs activate / deactivate / freeze / slash;
//   * the agent's own execution address signs nothing here. Being an agent
//     confers no authority over funds (v2 invariant 1).

#[derive(Accounts)]
pub struct UpdateModel<'info> {
    pub owner: Signer<'info>,

    #[account(
        mut,
        seeds = [b"agent", agent.agent_address.as_ref()],
        bump = agent.bump,
        has_one = owner @ RegistryError::Unauthorized
    )]
    pub agent: Account<'info, AgentAccount>,
}

#[derive(Accounts)]
pub struct Stake<'info> {
    #[account(mut)]
    pub owner: Signer<'info>,

    #[account(seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, RegistryConfig>,

    #[account(
        mut,
        seeds = [b"agent", agent.agent_address.as_ref()],
        bump = agent.bump,
        has_one = owner @ RegistryError::Unauthorized
    )]
    pub agent: Account<'info, AgentAccount>,

    #[account(constraint = stake_mint.key() == config.stake_mint @ RegistryError::WrongMint)]
    pub stake_mint: InterfaceAccount<'info, Mint>,

    #[account(
        mut,
        constraint = owner_token_account.owner == owner.key(),
        constraint = owner_token_account.mint == stake_mint.key()
    )]
    pub owner_token_account: InterfaceAccount<'info, TokenAccount>,

    /// CHECK: PDA authority for the vault ATA
    #[account(seeds = [b"vault_authority"], bump = config.vault_authority_bump)]
    pub vault_authority: UncheckedAccount<'info>,

    #[account(
        mut,
        associated_token::mint = stake_mint,
        associated_token::authority = vault_authority,
        associated_token::token_program = token_program
    )]
    pub vault_token_account: InterfaceAccount<'info, TokenAccount>,

    pub token_program: Interface<'info, TokenInterface>,
}

#[derive(Accounts)]
pub struct Unstake<'info> {
    #[account(mut)]
    pub owner: Signer<'info>,

    #[account(seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, RegistryConfig>,

    #[account(
        mut,
        seeds = [b"agent", agent.agent_address.as_ref()],
        bump = agent.bump,
        has_one = owner @ RegistryError::Unauthorized
    )]
    pub agent: Account<'info, AgentAccount>,

    #[account(constraint = stake_mint.key() == config.stake_mint @ RegistryError::WrongMint)]
    pub stake_mint: InterfaceAccount<'info, Mint>,

    #[account(
        mut,
        constraint = owner_token_account.owner == owner.key(),
        constraint = owner_token_account.mint == stake_mint.key()
    )]
    pub owner_token_account: InterfaceAccount<'info, TokenAccount>,

    /// CHECK: PDA authority for the vault ATA
    #[account(seeds = [b"vault_authority"], bump = config.vault_authority_bump)]
    pub vault_authority: UncheckedAccount<'info>,

    #[account(
        mut,
        associated_token::mint = stake_mint,
        associated_token::authority = vault_authority,
        associated_token::token_program = token_program
    )]
    pub vault_token_account: InterfaceAccount<'info, TokenAccount>,

    pub token_program: Interface<'info, TokenInterface>,
}

#[derive(Accounts)]
pub struct DeactivateAgent<'info> {
    pub admin: Signer<'info>,

    #[account(
        seeds = [b"config"],
        bump = config.bump,
        has_one = admin @ RegistryError::Unauthorized
    )]
    pub config: Account<'info, RegistryConfig>,

    #[account(
        mut,
        seeds = [b"agent", agent.agent_address.as_ref()],
        bump = agent.bump
    )]
    pub agent: Account<'info, AgentAccount>,
}

#[derive(Accounts)]
pub struct FreezeAgent<'info> {
    pub admin: Signer<'info>,

    #[account(
        seeds = [b"config"],
        bump = config.bump,
        has_one = admin @ RegistryError::Unauthorized
    )]
    pub config: Account<'info, RegistryConfig>,

    #[account(
        mut,
        seeds = [b"agent", agent.agent_address.as_ref()],
        bump = agent.bump
    )]
    pub agent: Account<'info, AgentAccount>,
}

#[derive(Accounts)]
pub struct GetActiveAgents<'info> {
    #[account(
        seeds = [b"agent_list"],
        bump = agent_list.bump
    )]
    pub agent_list: Account<'info, AgentList>,
}

#[account]
#[derive(InitSpace)]
pub struct RegistryConfig {
    pub admin: Pubkey,
    pub stake_mint: Pubkey,
    pub min_stake: u64,
    pub simulation_period: i64,
    pub vault_authority_bump: u8,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct AgentAccount {
    pub owner: Pubkey,
    /// Stable protocol-level identity, independent of the execution address.
    pub agent_id: [u8; 32],
    pub agent_address: Pubkey,
    /// Model identity is persistent and versioned (v2 invariant 3): a new model
    /// must be distinguishable from the last.
    pub model_hash: [u8; 32],
    pub model_version: u32,
    pub strategy_hash: [u8; 32],
    pub staked_amount: u64,
    /// IRIS Score, scaled by 1000. Written by the reputation engine.
    pub reputation: u64,
    /// Share of the vault, in basis points. Written by the allocation engine.
    /// This is authority to be allocated to, never authority to move funds.
    pub allocation_weight: u64,
    pub registered_at: i64,
    pub simulation_ends: i64,
    pub status: AgentStatus,
    pub risk_pool: u8,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct AgentList {
    // The Solana runtime caps a program-created account at 10,240 bytes
    // (MAX_PERMITTED_DATA_INCREASE). This account is 8 (discriminator)
    // + 4 (vec prefix) + 32*N + 1 (bump), so N must stay at or below 319.
    // The previous value of 5000 asked for ~160KB and made `initialize` fail
    // with InvalidRealloc — on devnet as surely as in the test harness.
    //
    // 300 leaves headroom. Growing past it needs a different shape (a paged
    // list, or dropping the on-chain roster and indexing agent PDAs
    // off-chain), not a bigger number here.
    #[max_len(300)]
    pub agents: Vec<Pubkey>,
    pub bump: u8,
}

#[derive(AnchorSerialize, AnchorDeserialize, InitSpace, Clone, Debug, PartialEq, Eq)]
pub enum AgentStatus {
    Unregistered,
    Probation,
    Active,
    /// Risk engine halted this agent. Reversible, unlike Slashed.
    Frozen,
    Slashed,
    Deregistered,
}

#[event]
pub struct AgentRegisteredEvent {
    pub agent: Pubkey,
    pub risk_pool: u8,
    pub stake: u64,
}

#[event]
pub struct AgentActivatedEvent {
    pub agent: Pubkey,
}

#[event]
pub struct AgentSlashedEvent {
    pub agent: Pubkey,
    pub slashed_amount: u64,
}

#[event]
pub struct ModelUpdatedEvent {
    pub agent: Pubkey,
    pub model_hash: [u8; 32],
    pub model_version: u32,
}

#[event]
pub struct StakeChangedEvent {
    pub agent: Pubkey,
    pub staked_amount: u64,
    pub delta: i128,
}

#[event]
pub struct AgentStatusChangedEvent {
    pub agent: Pubkey,
    pub status: AgentStatus,
}

#[error_code]
pub enum RegistryError {
    #[msg("Already registered")]
    AlreadyRegistered,
    #[msg("Insufficient stake")]
    InsufficientStake,
    #[msg("Invalid pool")]
    InvalidPool,
    #[msg("Unauthorized")]
    Unauthorized,
    #[msg("Not in probation")]
    NotInProbation,
    #[msg("Simulation not complete")]
    SimulationNotComplete,
    #[msg("Agent not active")]
    AgentNotActive,
    #[msg("Invalid slash bps")]
    InvalidSlashBps,
    #[msg("Math overflow")]
    MathOverflow,
    #[msg("Missing agent account in remaining accounts")]
    MissingAgentAccount,
    #[msg("Agent is not registered")]
    AgentNotRegistered,
    #[msg("Model hash is unchanged; a new version must be a different model")]
    ModelUnchanged,
    #[msg("Amount must be greater than zero")]
    ZeroAmount,
    #[msg("Agent has been slashed")]
    AgentSlashed,
    #[msg("Agent is not frozen")]
    AgentNotFrozen,
    #[msg("Wrong stake mint")]
    WrongMint,
}