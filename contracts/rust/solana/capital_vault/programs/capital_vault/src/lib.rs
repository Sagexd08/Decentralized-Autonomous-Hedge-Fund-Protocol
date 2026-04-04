use anchor_lang::prelude::*;
use anchor_spl::{
    associated_token::AssociatedToken,
    token_interface::{self, Mint, TokenAccount, TokenInterface, TransferChecked},
};

declare_id!("4AdNiFej3xrBh5t5NziiMMTMs1YK7qMUxgTNBwo4tcf2");

const CONSERVATIVE: u8 = 0;
const BALANCED: u8 = 1;
const AGGRESSIVE: u8 = 2;

const MAX_DRAWDOWN_BPS: u64 = 2000;
const PERFORMANCE_FEE_BPS: u64 = 1000;

#[program]
pub mod capital_vault {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let config = &mut ctx.accounts.config;

        config.admin = ctx.accounts.admin.key();
        config.token_mint = ctx.accounts.token_mint.key();
        config.allocation_engine = Pubkey::default();
        config.slashing_module = Pubkey::default();
        config.bump = ctx.bumps.config;
        config.vault_authority_bump = ctx.bumps.vault_authority;

        config.volatility_caps[CONSERVATIVE as usize] = 800;
        config.volatility_caps[BALANCED as usize] = 1800;
        config.volatility_caps[AGGRESSIVE as usize] = 3500;

        Ok(())
    }

    pub fn deposit(ctx: Context<Deposit>, pool: u8, amount: u64) -> Result<()> {
        require!(pool <= AGGRESSIVE, VaultError::InvalidPool);
        require!(amount > 0, VaultError::InvalidAmount);

        let decimals = ctx.accounts.token_mint.decimals;

        let cpi_accounts = TransferChecked {
            from: ctx.accounts.investor_token_account.to_account_info(),
            mint: ctx.accounts.token_mint.to_account_info(),
            to: ctx.accounts.vault_token_account.to_account_info(),
            authority: ctx.accounts.investor.to_account_info(),
        };

        let cpi_ctx = CpiContext::new(ctx.accounts.token_program.to_account_info(), cpi_accounts);
        token_interface::transfer_checked(cpi_ctx, amount, decimals)?;

        let investor_pool = &mut ctx.accounts.investor_pool_balance;
        investor_pool.investor = ctx.accounts.investor.key();
        investor_pool.pool = pool;
        investor_pool.balance = investor_pool
            .balance
            .checked_add(amount)
            .ok_or(VaultError::MathOverflow)?;
        investor_pool.bump = ctx.bumps.investor_pool_balance;

        let pool_state = &mut ctx.accounts.pool_state;
        pool_state.pool = pool;
        pool_state.tvl = pool_state
            .tvl
            .checked_add(amount)
            .ok_or(VaultError::MathOverflow)?;


        emit!(DepositedEvent {
            investor: ctx.accounts.investor.key(),
            pool,
            amount,
        });

        Ok(())
    }

    pub fn withdraw(ctx: Context<Withdraw>, pool: u8, amount: u64) -> Result<()> {
        require!(pool <= AGGRESSIVE, VaultError::InvalidPool);
        require!(amount > 0, VaultError::InvalidAmount);

        let investor_pool = &mut ctx.accounts.investor_pool_balance;
        require!(investor_pool.balance >= amount, VaultError::InsufficientBalance);

        investor_pool.balance = investor_pool
            .balance
            .checked_sub(amount)
            .ok_or(VaultError::MathOverflow)?;

        let pool_state = &mut ctx.accounts.pool_state;
        pool_state.tvl = pool_state
            .tvl
            .checked_sub(amount)
            .ok_or(VaultError::MathOverflow)?;

        let decimals = ctx.accounts.token_mint.decimals;

        let signer_seeds: &[&[&[u8]]] = &[&[
            b"vault_authority",
            &[ctx.accounts.config.vault_authority_bump],
        ]];

        let cpi_accounts = TransferChecked {
            from: ctx.accounts.vault_token_account.to_account_info(),
            mint: ctx.accounts.token_mint.to_account_info(),
            to: ctx.accounts.investor_token_account.to_account_info(),
            authority: ctx.accounts.vault_authority.to_account_info(),
        };

        let cpi_ctx = CpiContext::new_with_signer(
            ctx.accounts.token_program.to_account_info(),
            cpi_accounts,
            signer_seeds,
        );

        token_interface::transfer_checked(cpi_ctx, amount, decimals)?;

        emit!(WithdrawnEvent {
            investor: ctx.accounts.investor.key(),
            pool,
            amount,
        });

        Ok(())
    }

    pub fn update_weights(
        ctx: Context<UpdateWeights>,
        agents: Vec<Pubkey>,
        weights: Vec<u64>,
    ) -> Result<()> {
        require!(agents.len() == weights.len(), VaultError::LengthMismatch);

        let mut total: u128 = 0;
        for weight in weights.iter() {
            total = total
                .checked_add(*weight as u128)
                .ok_or(VaultError::MathOverflow)?;
        }

        require!(total == 1_000_000_000_000_000_000u128, VaultError::WeightsMustSumTo1e18);

        require!(
            ctx.remaining_accounts.len() == agents.len(),
            VaultError::MissingWeightAccounts
        );

        for (i, agent_key) in agents.iter().enumerate() {
            let acct = &ctx.remaining_accounts[i];
            require!(acct.key() == *agent_key, VaultError::AgentMismatch);

            let mut data: &[u8] = &acct.try_borrow_data()?;
            let mut agent_weight = AgentWeight::try_deserialize(&mut data)?;

            agent_weight.agent = *agent_key;
            agent_weight.weight = weights[i];

            let mut dst = acct.try_borrow_mut_data()?;
            let mut dst_slice: &mut [u8] = &mut dst;
            agent_weight.try_serialize(&mut dst_slice)?;
        }

        emit!(WeightsUpdatedEvent { agents, weights });

        Ok(())
    }

    pub fn enforce_drawdown_limit(ctx: Context<EnforceDrawdownLimit>) -> Result<()> {
        let agent_metric = &mut ctx.accounts.agent_metric;
        let agent_weight = &mut ctx.accounts.agent_weight;

        let peak = agent_metric.peak_value;
        let current = agent_metric.current_value;

        if peak == 0 {
            return Ok(());
        }

        let drawdown_bps = ((peak - current) as u128)
            .checked_mul(10_000)
            .ok_or(VaultError::MathOverflow)?
            .checked_div(peak as u128)
            .ok_or(VaultError::MathOverflow)? as u64;

        if drawdown_bps > MAX_DRAWDOWN_BPS {
            agent_weight.weight = 0;

            emit!(DrawdownBreachedEvent {
                agent: agent_metric.agent,
                drawdown_bps,
            });

            emit!(RiskLimitEnforcedEvent {
                agent: agent_metric.agent,
            });
        }

        Ok(())
    }

    pub fn set_allocation_engine(ctx: Context<SetAllocationEngine>, engine: Pubkey) -> Result<()> {
        ctx.accounts.config.allocation_engine = engine;
        Ok(())
    }

    pub fn set_slashing_module(ctx: Context<SetSlashingModule>, slashing: Pubkey) -> Result<()> {
        ctx.accounts.config.slashing_module = slashing;
        Ok(())
    }

    pub fn init_pool_state(ctx: Context<InitPoolState>, pool: u8) -> Result<()> {
        require!(pool <= AGGRESSIVE, VaultError::InvalidPool);

        let pool_state = &mut ctx.accounts.pool_state;
        pool_state.pool = pool;
        pool_state.tvl = 0;
        pool_state.bump = ctx.bumps.pool_state;

        Ok(())
    }

    pub fn init_agent_weight(ctx: Context<InitAgentWeight>, agent: Pubkey) -> Result<()> {
        let agent_weight = &mut ctx.accounts.agent_weight;
        agent_weight.agent = agent;
        agent_weight.weight = 0;
        agent_weight.bump = ctx.bumps.agent_weight;
        Ok(())
    }

    pub fn init_agent_metric(ctx: Context<InitAgentMetric>, agent: Pubkey) -> Result<()> {
        let metric = &mut ctx.accounts.agent_metric;
        metric.agent = agent;
        metric.peak_value = 0;
        metric.current_value = 0;
        metric.bump = ctx.bumps.agent_metric;
        Ok(())
    }

    pub fn set_agent_metric(
        ctx: Context<SetAgentMetric>,
        peak_value: u64,
        current_value: u64,
    ) -> Result<()> {
        let metric = &mut ctx.accounts.agent_metric;
        metric.peak_value = peak_value;
        metric.current_value = current_value;
        Ok(())
    }

    pub fn total_tvl(ctx: Context<TotalTvl>) -> Result<u64> {
        let mut total = 0u64;

        for acct in ctx.remaining_accounts.iter() {
            let mut data: &[u8] = &acct.try_borrow_data()?;
            let pool_state = PoolState::try_deserialize(&mut data)?;
            total = total.checked_add(pool_state.tvl).ok_or(VaultError::MathOverflow)?;
        }

        Ok(total)
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,

    pub token_mint: InterfaceAccount<'info, Mint>,

    #[account(
        init,
        payer = admin,
        seeds = [b"config"],
        bump,
        space = 8 + VaultConfig::INIT_SPACE
    )]
    pub config: Account<'info, VaultConfig>,

    /// CHECK: PDA authority for vault token ATA
    #[account(
        seeds = [b"vault_authority"],
        bump
    )]
    pub vault_authority: UncheckedAccount<'info>,

    #[account(
        init,
        payer = admin,
        associated_token::mint = token_mint,
        associated_token::authority = vault_authority,
        associated_token::token_program = token_program
    )]
    pub vault_token_account: InterfaceAccount<'info, TokenAccount>,

    pub token_program: Interface<'info, TokenInterface>,
    pub associated_token_program: Program<'info, AssociatedToken>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(pool: u8)]
pub struct Deposit<'info> {
    #[account(mut)]
    pub investor: Signer<'info>,

    #[account(
        seeds = [b"config"],
        bump = config.bump
    )]
    pub config: Account<'info, VaultConfig>,

    pub token_mint: InterfaceAccount<'info, Mint>,

    #[account(
        mut,
        constraint = investor_token_account.owner == investor.key(),
        constraint = investor_token_account.mint == token_mint.key()
    )]
    pub investor_token_account: InterfaceAccount<'info, TokenAccount>,

    /// CHECK: PDA authority for vault ATA
    #[account(
        seeds = [b"vault_authority"],
        bump = config.vault_authority_bump
    )]
    pub vault_authority: UncheckedAccount<'info>,

    #[account(
        mut,
        associated_token::mint = token_mint,
        associated_token::authority = vault_authority,
        associated_token::token_program = token_program
    )]
    pub vault_token_account: InterfaceAccount<'info, TokenAccount>,

    #[account(
        init_if_needed,
        payer = investor,
        seeds = [b"investor_pool".as_ref(), investor.key().as_ref(), &[pool]],
        bump,
        space = 8 + InvestorPoolBalance::INIT_SPACE
    )]
    pub investor_pool_balance: Account<'info, InvestorPoolBalance>,

    #[account(
        mut,
        seeds = [b"pool_state".as_ref(), &[pool]],
        bump = pool_state.bump
    )]
    pub pool_state: Account<'info, PoolState>,

    pub token_program: Interface<'info, TokenInterface>,
    pub associated_token_program: Program<'info, AssociatedToken>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(pool: u8)]
pub struct Withdraw<'info> {
    #[account(mut)]
    pub investor: Signer<'info>,

    #[account(
        seeds = [b"config"],
        bump = config.bump
    )]
    pub config: Account<'info, VaultConfig>,

    pub token_mint: InterfaceAccount<'info, Mint>,

    #[account(
        mut,
        constraint = investor_token_account.owner == investor.key(),
        constraint = investor_token_account.mint == token_mint.key()
    )]
    pub investor_token_account: InterfaceAccount<'info, TokenAccount>,

    /// CHECK: PDA authority for vault ATA
    #[account(
        seeds = [b"vault_authority"],
        bump = config.vault_authority_bump
    )]
    pub vault_authority: UncheckedAccount<'info>,

    #[account(
        mut,
        associated_token::mint = token_mint,
        associated_token::authority = vault_authority,
        associated_token::token_program = token_program
    )]
    pub vault_token_account: InterfaceAccount<'info, TokenAccount>,

    #[account(
        mut,
        seeds = [b"investor_pool".as_ref(), investor.key().as_ref(), &[pool]],
        bump = investor_pool_balance.bump,
        constraint = investor_pool_balance.pool == pool
    )]
    pub investor_pool_balance: Account<'info, InvestorPoolBalance>,

    #[account(
        mut,
        seeds = [b"pool_state".as_ref(), &[pool]],
        bump = pool_state.bump
    )]
    pub pool_state: Account<'info, PoolState>,

    pub token_program: Interface<'info, TokenInterface>,
}

#[derive(Accounts)]
pub struct UpdateWeights<'info> {
    pub allocation_engine_signer: Signer<'info>,

    #[account(
        seeds = [b"config"],
        bump = config.bump,
        constraint = config.allocation_engine == allocation_engine_signer.key() @ VaultError::OnlyAllocationEngine
    )]
    pub config: Account<'info, VaultConfig>,
}

#[derive(Accounts)]
pub struct EnforceDrawdownLimit<'info> {
    pub slashing_module_signer: Signer<'info>,

    #[account(
        seeds = [b"config"],
        bump = config.bump,
        constraint = config.slashing_module == slashing_module_signer.key() @ VaultError::OnlySlashingModule
    )]
    pub config: Account<'info, VaultConfig>,

    #[account(
        mut,
        seeds = [b"agent_metric", agent_metric.agent.as_ref()],
        bump = agent_metric.bump
    )]
    pub agent_metric: Account<'info, AgentMetric>,

    #[account(
        mut,
        seeds = [b"agent_weight", agent_metric.agent.as_ref()],
        bump = agent_weight.bump
    )]
    pub agent_weight: Account<'info, AgentWeight>,
}

#[derive(Accounts)]
pub struct SetAllocationEngine<'info> {
    pub admin: Signer<'info>,

    #[account(
        mut,
        seeds = [b"config"],
        bump = config.bump,
        has_one = admin @ VaultError::Unauthorized
    )]
    pub config: Account<'info, VaultConfig>,
}

#[derive(Accounts)]
pub struct SetSlashingModule<'info> {
    pub admin: Signer<'info>,

    #[account(
        mut,
        seeds = [b"config"],
        bump = config.bump,
        has_one = admin @ VaultError::Unauthorized
    )]
    pub config: Account<'info, VaultConfig>,
}

#[derive(Accounts)]
#[instruction(pool: u8)]
pub struct InitPoolState<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,

    #[account(
        seeds = [b"config"],
        bump = config.bump,
        has_one = admin @ VaultError::Unauthorized
    )]
    pub config: Account<'info, VaultConfig>,

    #[account(
        init,
        payer = admin,
        seeds = [b"pool_state".as_ref(), &[pool]],
        bump,
        space = 8 + PoolState::INIT_SPACE
    )]
    pub pool_state: Account<'info, PoolState>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(agent: Pubkey)]
pub struct InitAgentWeight<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,

    #[account(
        seeds = [b"config"],
        bump = config.bump,
        has_one = admin @ VaultError::Unauthorized
    )]
    pub config: Account<'info, VaultConfig>,

    #[account(
        init,
        payer = admin,
        seeds = [b"agent_weight", agent.as_ref()],
        bump,
        space = 8 + AgentWeight::INIT_SPACE
    )]
    pub agent_weight: Account<'info, AgentWeight>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(agent: Pubkey)]
pub struct InitAgentMetric<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,

    #[account(
        seeds = [b"config"],
        bump = config.bump,
        has_one = admin @ VaultError::Unauthorized
    )]
    pub config: Account<'info, VaultConfig>,

    #[account(
        init,
        payer = admin,
        seeds = [b"agent_metric", agent.as_ref()],
        bump,
        space = 8 + AgentMetric::INIT_SPACE
    )]
    pub agent_metric: Account<'info, AgentMetric>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct SetAgentMetric<'info> {
    pub admin: Signer<'info>,

    #[account(
        seeds = [b"config"],
        bump = config.bump,
        has_one = admin @ VaultError::Unauthorized
    )]
    pub config: Account<'info, VaultConfig>,

    #[account(
        mut,
        seeds = [b"agent_metric", agent_metric.agent.as_ref()],
        bump = agent_metric.bump
    )]
    pub agent_metric: Account<'info, AgentMetric>,
}

#[derive(Accounts)]
pub struct TotalTvl<'info> {
    pub system_program: Program<'info, System>,
}

#[account]
#[derive(InitSpace)]
pub struct VaultConfig {
    pub admin: Pubkey,
    pub token_mint: Pubkey,
    pub allocation_engine: Pubkey,
    pub slashing_module: Pubkey,
    pub volatility_caps: [u64; 3],
    pub vault_authority_bump: u8,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct InvestorPoolBalance {
    pub investor: Pubkey,
    pub pool: u8,
    pub balance: u64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct PoolState {
    pub pool: u8,
    pub tvl: u64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct AgentWeight {
    pub agent: Pubkey,
    pub weight: u64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct AgentMetric {
    pub agent: Pubkey,
    pub peak_value: u64,
    pub current_value: u64,
    pub bump: u8,
}

#[event]
pub struct DepositedEvent {
    pub investor: Pubkey,
    pub pool: u8,
    pub amount: u64,
}

#[event]
pub struct WithdrawnEvent {
    pub investor: Pubkey,
    pub pool: u8,
    pub amount: u64,
}

#[event]
pub struct WeightsUpdatedEvent {
    pub agents: Vec<Pubkey>,
    pub weights: Vec<u64>,
}

#[event]
pub struct DrawdownBreachedEvent {
    pub agent: Pubkey,
    pub drawdown_bps: u64,
}

#[event]
pub struct RiskLimitEnforcedEvent {
    pub agent: Pubkey,
}

#[error_code]
pub enum VaultError {
    #[msg("Unauthorized")]
    Unauthorized,
    #[msg("Invalid pool")]
    InvalidPool,
    #[msg("Invalid amount")]
    InvalidAmount,
    #[msg("Insufficient balance")]
    InsufficientBalance,
    #[msg("Length mismatch")]
    LengthMismatch,
    #[msg("Weights must sum to 1e18")]
    WeightsMustSumTo1e18,
    #[msg("Only allocation engine")]
    OnlyAllocationEngine,
    #[msg("Only slashing module")]
    OnlySlashingModule,
    #[msg("Math overflow")]
    MathOverflow,
    #[msg("Missing weight accounts")]
    MissingWeightAccounts,
    #[msg("Agent mismatch")]
    AgentMismatch,
}