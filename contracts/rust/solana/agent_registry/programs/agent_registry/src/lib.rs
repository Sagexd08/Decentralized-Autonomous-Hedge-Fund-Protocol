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
        agent.agent_address = ctx.accounts.agent_authority.key();
        agent.strategy_hash = strategy_hash;
        agent.staked_amount = stake_amount;
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
    pub agent_address: Pubkey,
    pub strategy_hash: [u8; 32],
    pub staked_amount: u64,
    pub registered_at: i64,
    pub simulation_ends: i64,
    pub status: AgentStatus,
    pub risk_pool: u8,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct AgentList {
    #[max_len(5000)]
    pub agents: Vec<Pubkey>,
    pub bump: u8,
}

#[derive(AnchorSerialize, AnchorDeserialize, InitSpace, Clone, PartialEq, Eq)]
pub enum AgentStatus {
    Unregistered,
    Probation,
    Active,
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
}