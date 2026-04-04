use anchor_lang::prelude::*;

declare_id!("AC6xZSbeD6fMRafNVGbnuN4vt94py7heNKyepp7KqBUv");

const DEFAULT_DRAWDOWN_THRESHOLD_BPS: u64 = 2000; // 20%
const DEFAULT_MAX_SLASH_BPS: u64 = 5000; // 50%

#[program]
pub mod slashing_module {
    use super::*;

    pub fn initialize(
        ctx: Context<Initialize>,
        vault: Pubkey,
        registry: Pubkey,
    ) -> Result<()> {
        let config = &mut ctx.accounts.config;
        config.admin = ctx.accounts.admin.key();
        config.vault = vault;
        config.registry = registry;
        config.drawdown_threshold_bps = DEFAULT_DRAWDOWN_THRESHOLD_BPS;
        config.max_slash_bps = DEFAULT_MAX_SLASH_BPS;
        config.bump = ctx.bumps.config;
        Ok(())
    }

    pub fn init_agent_state(ctx: Context<InitAgentState>, agent: Pubkey) -> Result<()> {
        let state = &mut ctx.accounts.agent_state;
        state.agent = agent;
        state.peak_value = 0;
        state.current_value = 0;
        state.bump = ctx.bumps.agent_state;
        Ok(())
    }

    pub fn init_slash_history(ctx: Context<InitSlashHistory>, agent: Pubkey) -> Result<()> {
        let history = &mut ctx.accounts.slash_history;
        history.agent = agent;
        history.records = Vec::new();
        history.bump = ctx.bumps.slash_history;
        Ok(())
    }

    pub fn report_performance(
        ctx: Context<ReportPerformance>,
        current_value: u64,
    ) -> Result<()> {
        let config = &ctx.accounts.config;
        let agent_state = &mut ctx.accounts.agent_state;
        let slash_history = &mut ctx.accounts.slash_history;

        if agent_state.peak_value == 0 || current_value > agent_state.peak_value {
            agent_state.peak_value = current_value;
        }

        agent_state.current_value = current_value;

        let peak = agent_state.peak_value;

        if peak > current_value {
            let drawdown_bps = ((peak - current_value) as u128)
                .checked_mul(10_000)
                .ok_or(SlashingError::MathOverflow)?
                .checked_div(peak as u128)
                .ok_or(SlashingError::MathOverflow)? as u64;

            emit!(DrawdownReportedEvent {
                agent: agent_state.agent,
                drawdown_bps,
            });

            if drawdown_bps > config.drawdown_threshold_bps {
                let excess_bps = drawdown_bps
                    .checked_sub(config.drawdown_threshold_bps)
                    .ok_or(SlashingError::MathOverflow)?;

                let slash_bps = if excess_bps > config.max_slash_bps {
                    config.max_slash_bps
                } else {
                    excess_bps
                };

                let clock = Clock::get()?;

                slash_history.records.push(SlashRecord {
                    timestamp: clock.unix_timestamp,
                    drawdown_bps,
                    slashed_bps: slash_bps,
                });

                emit!(SlashExecutedEvent {
                    agent: agent_state.agent,
                    slash_bps,
                });

                // CPI hooks for registry/vault can be wired later
                // registry.slash_agent(...)
                // vault.enforce_drawdown_limit(...)
            }
        }

        Ok(())
    }

    pub fn set_threshold(ctx: Context<SetThreshold>, threshold_bps: u64) -> Result<()> {
        require!(
            threshold_bps >= 500 && threshold_bps <= 5000,
            SlashingError::ThresholdOutOfRange
        );

        let config = &mut ctx.accounts.config;
        config.drawdown_threshold_bps = threshold_bps;

        emit!(ThresholdUpdatedEvent {
            new_threshold: threshold_bps,
        });

        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,

    #[account(
        init,
        payer = admin,
        seeds = [b"config"],
        bump,
        space = 8 + SlashingConfig::INIT_SPACE
    )]
    pub config: Account<'info, SlashingConfig>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(agent: Pubkey)]
pub struct InitAgentState<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,

    #[account(
        seeds = [b"config"],
        bump = config.bump,
        has_one = admin @ SlashingError::Unauthorized
    )]
    pub config: Account<'info, SlashingConfig>,

    #[account(
        init,
        payer = admin,
        seeds = [b"agent_state", agent.as_ref()],
        bump,
        space = 8 + AgentState::INIT_SPACE
    )]
    pub agent_state: Account<'info, AgentState>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(agent: Pubkey)]
pub struct InitSlashHistory<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,

    #[account(
        seeds = [b"config"],
        bump = config.bump,
        has_one = admin @ SlashingError::Unauthorized
    )]
    pub config: Account<'info, SlashingConfig>,

    #[account(
        init,
        payer = admin,
        seeds = [b"slash_history", agent.as_ref()],
        bump,
        space = 8 + SlashHistory::INIT_SPACE
    )]
    pub slash_history: Account<'info, SlashHistory>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct ReportPerformance<'info> {
    pub admin: Signer<'info>,

    #[account(
        seeds = [b"config"],
        bump = config.bump,
        has_one = admin @ SlashingError::Unauthorized
    )]
    pub config: Account<'info, SlashingConfig>,

    #[account(
        mut,
        seeds = [b"agent_state", agent_state.agent.as_ref()],
        bump = agent_state.bump
    )]
    pub agent_state: Account<'info, AgentState>,

    #[account(
        mut,
        seeds = [b"slash_history", agent_state.agent.as_ref()],
        bump = slash_history.bump
    )]
    pub slash_history: Account<'info, SlashHistory>,
}

#[derive(Accounts)]
pub struct SetThreshold<'info> {
    pub admin: Signer<'info>,

    #[account(
        mut,
        seeds = [b"config"],
        bump = config.bump,
        has_one = admin @ SlashingError::Unauthorized
    )]
    pub config: Account<'info, SlashingConfig>,
}

#[account]
#[derive(InitSpace)]
pub struct SlashingConfig {
    pub admin: Pubkey,
    pub vault: Pubkey,
    pub registry: Pubkey,
    pub drawdown_threshold_bps: u64,
    pub max_slash_bps: u64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct AgentState {
    pub agent: Pubkey,
    pub peak_value: u64,
    pub current_value: u64,
    pub bump: u8,
}

#[derive(AnchorSerialize, AnchorDeserialize, Clone, InitSpace)]
pub struct SlashRecord {
    pub timestamp: i64,
    pub drawdown_bps: u64,
    pub slashed_bps: u64,
}

#[account]
#[derive(InitSpace)]
pub struct SlashHistory {
    pub agent: Pubkey,
    #[max_len(200)]
    pub records: Vec<SlashRecord>,
    pub bump: u8,
}

#[event]
pub struct DrawdownReportedEvent {
    pub agent: Pubkey,
    pub drawdown_bps: u64,
}

#[event]
pub struct SlashExecutedEvent {
    pub agent: Pubkey,
    pub slash_bps: u64,
}

#[event]
pub struct ThresholdUpdatedEvent {
    pub new_threshold: u64,
}

#[error_code]
pub enum SlashingError {
    #[msg("Unauthorized")]
    Unauthorized,
    #[msg("Threshold out of range")]
    ThresholdOutOfRange,
    #[msg("Math overflow")]
    MathOverflow,
}