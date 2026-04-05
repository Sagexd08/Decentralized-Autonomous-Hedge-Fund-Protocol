#![no_std]

use soroban_sdk::{
    contract, contracterror, contractimpl, contracttype, panic_with_error, token, Address, Env,
    Vec,
};

#[contract]
pub struct CapitalVault;

#[contracttype]
#[derive(Clone)]
pub enum DataKey {
    Admin,
    Token,
    AllocationEngine,
    SlashingModule,
    VolatilityCap(u32),
    InvestorBalance(Address, u32),
    AgentWeight(Address),
    AgentPeakValue(Address),
    AgentCurrentValue(Address),
    PoolTvl(u32),
}

#[contracterror]
#[repr(u32)]
#[derive(Copy, Clone, Debug, Eq, PartialEq, PartialOrd, Ord)]
pub enum VaultError {
    AlreadyInitialized = 1,
    NotInitialized = 2,
    InvalidPool = 3,
    InvalidAmount = 4,
    InsufficientBalance = 5,
    LengthMismatch = 6,
    WeightsMustSumTo1e18 = 7,
    OnlyAllocationEngine = 8,
    OnlySlashingModule = 9,
}

const CONSERVATIVE: u32 = 0;
const BALANCED: u32 = 1;
const AGGRESSIVE: u32 = 2;

const MAX_DRAWDOWN_BPS: u32 = 2000; // 20%
const PERFORMANCE_FEE_BPS: u32 = 1000; // 10% (stored as public getter equivalent)

fn has_admin(env: &Env) -> bool {
    env.storage().instance().has(&DataKey::Admin)
}

fn get_admin(env: &Env) -> Address {
    env.storage()
        .instance()
        .get(&DataKey::Admin)
        .unwrap_or_else(|| panic_with_error!(env, VaultError::NotInitialized))
}

fn require_admin(env: &Env) {
    let admin = get_admin(env);
    admin.require_auth();
}

fn get_token(env: &Env) -> Address {
    env.storage()
        .instance()
        .get(&DataKey::Token)
        .unwrap_or_else(|| panic_with_error!(env, VaultError::NotInitialized))
}

fn get_allocation_engine_opt(env: &Env) -> Option<Address> {
    env.storage().instance().get(&DataKey::AllocationEngine)
}

fn get_slashing_module_opt(env: &Env) -> Option<Address> {
    env.storage().instance().get(&DataKey::SlashingModule)
}

fn require_allocation_engine(env: &Env) {
    let caller = env.current_contract_address();
    let engine = get_allocation_engine_opt(env)
        .unwrap_or_else(|| panic_with_error!(env, VaultError::NotInitialized));
    engine.require_auth();
    let _ = caller;
}

fn require_slashing_module(env: &Env) {
    let caller = env.current_contract_address();
    let slashing = get_slashing_module_opt(env)
        .unwrap_or_else(|| panic_with_error!(env, VaultError::NotInitialized));
    slashing.require_auth();
    let _ = caller;
}

fn ensure_valid_pool(env: &Env, pool: u32) {
    if pool > AGGRESSIVE {
        panic_with_error!(env, VaultError::InvalidPool);
    }
}

fn get_volatility_cap_internal(env: &Env, pool: u32) -> i128 {
    env.storage()
        .persistent()
        .get(&DataKey::VolatilityCap(pool))
        .unwrap_or(0)
}

fn set_volatility_cap_internal(env: &Env, pool: u32, value: i128) {
    env.storage()
        .persistent()
        .set(&DataKey::VolatilityCap(pool), &value);
}

fn get_investor_balance_internal(env: &Env, investor: &Address, pool: u32) -> i128 {
    env.storage()
        .persistent()
        .get(&DataKey::InvestorBalance(investor.clone(), pool))
        .unwrap_or(0)
}

fn set_investor_balance_internal(env: &Env, investor: &Address, pool: u32, value: i128) {
    env.storage()
        .persistent()
        .set(&DataKey::InvestorBalance(investor.clone(), pool), &value);
}

fn get_agent_weight_internal(env: &Env, agent: &Address) -> i128 {
    env.storage()
        .persistent()
        .get(&DataKey::AgentWeight(agent.clone()))
        .unwrap_or(0)
}

fn set_agent_weight_internal(env: &Env, agent: &Address, value: i128) {
    env.storage()
        .persistent()
        .set(&DataKey::AgentWeight(agent.clone()), &value);
}

fn get_agent_peak_internal(env: &Env, agent: &Address) -> i128 {
    env.storage()
        .persistent()
        .get(&DataKey::AgentPeakValue(agent.clone()))
        .unwrap_or(0)
}

fn set_agent_peak_internal(env: &Env, agent: &Address, value: i128) {
    env.storage()
        .persistent()
        .set(&DataKey::AgentPeakValue(agent.clone()), &value);
}

fn get_agent_current_internal(env: &Env, agent: &Address) -> i128 {
    env.storage()
        .persistent()
        .get(&DataKey::AgentCurrentValue(agent.clone()))
        .unwrap_or(0)
}

fn set_agent_current_internal(env: &Env, agent: &Address, value: i128) {
    env.storage()
        .persistent()
        .set(&DataKey::AgentCurrentValue(agent.clone()), &value);
}

fn get_pool_tvl_internal(env: &Env, pool: u32) -> i128 {
    env.storage()
        .persistent()
        .get(&DataKey::PoolTvl(pool))
        .unwrap_or(0)
}

fn set_pool_tvl_internal(env: &Env, pool: u32, value: i128) {
    env.storage().persistent().set(&DataKey::PoolTvl(pool), &value);
}

#[contractimpl]
impl CapitalVault {
    pub fn init(env: Env, admin: Address, token: Address) {
        if has_admin(&env) {
            panic_with_error!(&env, VaultError::AlreadyInitialized);
        }

        admin.require_auth();

        env.storage().instance().set(&DataKey::Admin, &admin);
        env.storage().instance().set(&DataKey::Token, &token);

        // Default volatility caps in basis points
        set_volatility_cap_internal(&env, CONSERVATIVE, 800);
        set_volatility_cap_internal(&env, BALANCED, 1800);
        set_volatility_cap_internal(&env, AGGRESSIVE, 3500);

        set_pool_tvl_internal(&env, CONSERVATIVE, 0);
        set_pool_tvl_internal(&env, BALANCED, 0);
        set_pool_tvl_internal(&env, AGGRESSIVE, 0);
    }

    pub fn deposit(env: Env, investor: Address, pool: u32, amount: i128) {
        investor.require_auth();
        ensure_valid_pool(&env, pool);

        if amount <= 0 {
            panic_with_error!(&env, VaultError::InvalidAmount);
        }

        let token_addr = get_token(&env);
        let token_client = token::Client::new(&env, &token_addr);

        token_client.transfer(&investor, &env.current_contract_address(), &amount);

        let current_balance = get_investor_balance_internal(&env, &investor, pool);
        let current_tvl = get_pool_tvl_internal(&env, pool);

        set_investor_balance_internal(&env, &investor, pool, current_balance + amount);
        set_pool_tvl_internal(&env, pool, current_tvl + amount);

        env.events()
            .publish(("Deposited", investor.clone(), pool), amount);
    }

    pub fn withdraw(env: Env, investor: Address, pool: u32, amount: i128) {
        investor.require_auth();
        ensure_valid_pool(&env, pool);

        if amount <= 0 {
            panic_with_error!(&env, VaultError::InvalidAmount);
        }

        let balance = get_investor_balance_internal(&env, &investor, pool);
        if balance < amount {
            panic_with_error!(&env, VaultError::InsufficientBalance);
        }

        let tvl = get_pool_tvl_internal(&env, pool);

        set_investor_balance_internal(&env, &investor, pool, balance - amount);
        set_pool_tvl_internal(&env, pool, tvl - amount);

        let token_addr = get_token(&env);
        let token_client = token::Client::new(&env, &token_addr);
        token_client.transfer(&env.current_contract_address(), &investor, &amount);

        env.events()
            .publish(("Withdrawn", investor.clone(), pool), amount);
    }

    pub fn update_weights(env: Env, agents: Vec<Address>, weights: Vec<i128>) {
        require_allocation_engine(&env);

        if agents.len() != weights.len() {
            panic_with_error!(&env, VaultError::LengthMismatch);
        }

        let mut total: i128 = 0;
        let mut i = 0;
        while i < weights.len() {
            total += weights.get(i).unwrap();
            i += 1;
        }

        if total != 1_000_000_000_000_000_000i128 {
            panic_with_error!(&env, VaultError::WeightsMustSumTo1e18);
        }

        let mut j = 0;
        while j < agents.len() {
            let agent = agents.get(j).unwrap();
            let weight = weights.get(j).unwrap();
            set_agent_weight_internal(&env, &agent, weight);
            j += 1;
        }

        env.events().publish(("WeightsUpdated",), (agents, weights));
    }

    pub fn enforce_drawdown_limit(env: Env, agent: Address) {
        require_slashing_module(&env);

        let peak = get_agent_peak_internal(&env, &agent);
        let current = get_agent_current_internal(&env, &agent);

        if peak == 0 {
            return;
        }

        let drawdown_bps = ((peak - current) * 10_000i128) / peak;

        if drawdown_bps > MAX_DRAWDOWN_BPS as i128 {
            set_agent_weight_internal(&env, &agent, 0);
            env.events()
                .publish(("DrawdownBreached", agent.clone()), drawdown_bps);
            env.events().publish(("RiskLimitEnforced", agent), ());
        }
    }

    pub fn set_allocation_engine(env: Env, engine: Address) {
        require_admin(&env);
        env.storage()
            .instance()
            .set(&DataKey::AllocationEngine, &engine);
    }

    pub fn set_slashing_module(env: Env, slashing: Address) {
        require_admin(&env);
        env.storage()
            .instance()
            .set(&DataKey::SlashingModule, &slashing);
    }

    // Optional helper for testing / oracle updates
    pub fn set_agent_values(env: Env, agent: Address, peak: i128, current: i128) {
        require_admin(&env);
        set_agent_peak_internal(&env, &agent, peak);
        set_agent_current_internal(&env, &agent, current);
    }

    pub fn total_tvl(env: Env) -> i128 {
        get_pool_tvl_internal(&env, CONSERVATIVE)
            + get_pool_tvl_internal(&env, BALANCED)
            + get_pool_tvl_internal(&env, AGGRESSIVE)
    }

    pub fn get_config(env: Env) -> (Address, Address, Option<Address>, Option<Address>) {
        (
            get_admin(&env),
            get_token(&env),
            get_allocation_engine_opt(&env),
            get_slashing_module_opt(&env),
        )
    }

    pub fn get_investor_balance(env: Env, investor: Address, pool: u32) -> i128 {
        ensure_valid_pool(&env, pool);
        get_investor_balance_internal(&env, &investor, pool)
    }

    pub fn get_agent_weight(env: Env, agent: Address) -> i128 {
        get_agent_weight_internal(&env, &agent)
    }

    pub fn get_agent_peak_value(env: Env, agent: Address) -> i128 {
        get_agent_peak_internal(&env, &agent)
    }

    pub fn get_agent_current_value(env: Env, agent: Address) -> i128 {
        get_agent_current_internal(&env, &agent)
    }

    pub fn get_pool_tvl(env: Env, pool: u32) -> i128 {
        ensure_valid_pool(&env, pool);
        get_pool_tvl_internal(&env, pool)
    }

    pub fn get_volatility_cap(env: Env, pool: u32) -> i128 {
        ensure_valid_pool(&env, pool);
        get_volatility_cap_internal(&env, pool)
    }

    pub fn max_drawdown_bps(_env: Env) -> u32 {
        MAX_DRAWDOWN_BPS
    }

    pub fn performance_fee_bps(_env: Env) -> u32 {
        PERFORMANCE_FEE_BPS
    }

    pub fn conservative(_env: Env) -> u32 {
        CONSERVATIVE
    }

    pub fn balanced(_env: Env) -> u32 {
        BALANCED
    }

    pub fn aggressive(_env: Env) -> u32 {
        AGGRESSIVE
    }
}