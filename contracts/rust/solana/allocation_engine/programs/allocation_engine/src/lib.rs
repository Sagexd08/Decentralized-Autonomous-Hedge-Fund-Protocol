use anchor_lang::prelude::*;

declare_id!("2MKzNfzPkEvsj6BKSrEEc9d4hdXmZnkyYQgTEtFZqbvR");

const DEFAULT_ETA: u64 = 10_000; // 0.01 scaled by 1e6
const ALPHA: u64 = 300; // 0.3 * 1000

#[program]
pub mod allocation_engine {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>, vault: Pubkey) -> Result<()> {
        let config = &mut ctx.accounts.config;
        config.admin = ctx.accounts.admin.key();
        config.vault = vault;
        config.eta = DEFAULT_ETA;
        config.update_count = 0;
        config.bump = ctx.bumps.config;
        Ok(())
    }

    pub fn submit_update(
        ctx: Context<SubmitUpdate>,
        scores: Vec<i64>,
        weights: Vec<u64>,
    ) -> Result<()> {
        let config = &mut ctx.accounts.config;

        require!(
            ctx.remaining_accounts.len() == scores.len() && scores.len() == weights.len(),
            AllocationError::LengthMismatch
        );

        let mut i = 0usize;
        while i < scores.len() {
            let agent_state_info = &ctx.remaining_accounts[i];

            let mut data: &[u8] = &agent_state_info.try_borrow_data()?;
            let mut agent_state = AgentState::try_deserialize(&mut data)?;

            let score = scores[i];
            agent_state.agent_score = score;

            let recent: u64 = if score > 0 { score as u64 } else { 0 };
            let historical = agent_state.reputation_score;

            agent_state.reputation_score =
                (ALPHA * recent + (1000 - ALPHA) * historical) / 1000;

            let mut dst = agent_state_info.try_borrow_mut_data()?;
            let mut dst_slice: &mut [u8] = &mut dst;
            agent_state.try_serialize(&mut dst_slice)?;

            emit!(ReputationUpdatedEvent {
                agent: agent_state.agent,
                score: agent_state.reputation_score,
            });

            i += 1;
        }

        config.update_count = config
            .update_count
            .checked_add(1)
            .ok_or(AllocationError::MathOverflow)?;

        emit!(ScoresSubmittedEvent {
            agents: ctx
                .remaining_accounts
                .iter()
                .map(|a| a.key())
                .collect(),
            scores,
        });

        // Optional future CPI to vault goes here

        Ok(())
    }

    pub fn set_eta(ctx: Context<SetEta>, eta: u64) -> Result<()> {
        require!(eta > 0 && eta <= 50_000, AllocationError::EtaOutOfRange);

        let config = &mut ctx.accounts.config;
        config.eta = eta;

        emit!(EtaUpdatedEvent { new_eta: eta });

        Ok(())
    }

    pub fn init_agent_state(ctx: Context<InitAgentState>, agent: Pubkey) -> Result<()> {
        let agent_state = &mut ctx.accounts.agent_state;
        agent_state.agent = agent;
        agent_state.agent_score = 0;
        agent_state.reputation_score = 0;
        agent_state.bump = ctx.bumps.agent_state;
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
        space = 8 + AllocationConfig::INIT_SPACE
    )]
    pub config: Account<'info, AllocationConfig>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct SubmitUpdate<'info> {
    pub admin: Signer<'info>,

    #[account(
        mut,
        seeds = [b"config"],
        bump = config.bump,
        has_one = admin @ AllocationError::Unauthorized
    )]
    pub config: Account<'info, AllocationConfig>,
}

#[derive(Accounts)]
pub struct SetEta<'info> {
    pub admin: Signer<'info>,

    #[account(
        mut,
        seeds = [b"config"],
        bump = config.bump,
        has_one = admin @ AllocationError::Unauthorized
    )]
    pub config: Account<'info, AllocationConfig>,
}

#[derive(Accounts)]
#[instruction(agent: Pubkey)]
pub struct InitAgentState<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,

    #[account(
        seeds = [b"config"],
        bump = config.bump,
        has_one = admin @ AllocationError::Unauthorized
    )]
    pub config: Account<'info, AllocationConfig>,

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

#[account]
#[derive(InitSpace)]
pub struct AllocationConfig {
    pub admin: Pubkey,
    pub vault: Pubkey,
    pub eta: u64,
    pub update_count: u64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct AgentState {
    pub agent: Pubkey,
    pub agent_score: i64,
    pub reputation_score: u64,
    pub bump: u8,
}

#[event]
pub struct EtaUpdatedEvent {
    pub new_eta: u64,
}

#[event]
pub struct ScoresSubmittedEvent {
    pub agents: Vec<Pubkey>,
    pub scores: Vec<i64>,
}

#[event]
pub struct ReputationUpdatedEvent {
    pub agent: Pubkey,
    pub score: u64,
}

#[error_code]
pub enum AllocationError {
    #[msg("Unauthorized")]
    Unauthorized,
    #[msg("Length mismatch")]
    LengthMismatch,
    #[msg("Eta out of range")]
    EtaOutOfRange,
    #[msg("Math overflow")]
    MathOverflow,
}