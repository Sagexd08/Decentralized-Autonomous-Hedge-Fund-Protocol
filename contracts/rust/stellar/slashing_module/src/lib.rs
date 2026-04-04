#![no_std]

use soroban_sdk::{
    contract, contractclient, contracterror, contractimpl, contracttype, panic_with_error, Address,
    Env, Vec,
};

#[contract]
pub struct SlashingModule;

#[contractclient(name = "RegistryClient")]
pub trait AgentRegistryContract {
    fn slash_agent(env: Env, agent_address: Address, slash_bps: u32);
}

#[contractclient(name = "VaultClient")]
pub trait CapitalVaultContract {
    fn enforce_drawdown_limit(env: Env, agent: Address);
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SlashRecord {
    pub timestamp: u64,
    pub drawdown_bps: u32,
    pub slashed_bps: u32,
}

#[contracttype]
#[derive(Clone)]
pub enum DataKey {
    Admin,
    Vault,
    Registry,
    DrawdownThresholdBps,
    MaxSlashBps,
    PeakValue(Address),
    CurrentValue(Address),
    SlashHistory(Address),
}

#[contracterror]
#[repr(u32)]
#[derive(Copy, Clone, Debug, Eq, PartialEq, PartialOrd, Ord)]
pub enum SlashingError {
    AlreadyInitialized = 1,
    NotInitialized = 2,
    ThresholdOutOfRange = 3,
}

const DEFAULT_DRAWDOWN_THRESHOLD_BPS: u32 = 2000; // 20%
const DEFAULT_MAX_SLASH_BPS: u32 = 5000; // 50%

fn has_admin(env: &Env) -> bool {
    env.storage().instance().has(&DataKey::Admin)
}

fn get_admin(env: &Env) -> Address {
    env.storage()
        .instance()
        .get(&DataKey::Admin)
        .unwrap_or_else(|| panic_with_error!(env, SlashingError::NotInitialized))
}

fn require_admin(env: &Env) {
    let admin = get_admin(env);
    admin.require_auth();
}

fn get_vault(env: &Env) -> Address {
    env.storage()
        .instance()
        .get(&DataKey::Vault)
        .unwrap_or_else(|| panic_with_error!(env, SlashingError::NotInitialized))
}

fn get_registry(env: &Env) -> Address {
    env.storage()
        .instance()
        .get(&DataKey::Registry)
        .unwrap_or_else(|| panic_with_error!(env, SlashingError::NotInitialized))
}

fn get_drawdown_threshold_bps(env: &Env) -> u32 {
    env.storage()
        .instance()
        .get(&DataKey::DrawdownThresholdBps)
        .unwrap_or(DEFAULT_DRAWDOWN_THRESHOLD_BPS)
}

fn get_max_slash_bps(env: &Env) -> u32 {
    env.storage()
        .instance()
        .get(&DataKey::MaxSlashBps)
        .unwrap_or(DEFAULT_MAX_SLASH_BPS)
}

fn get_peak_value(env: &Env, agent: &Address) -> i128 {
    env.storage()
        .persistent()
        .get(&DataKey::PeakValue(agent.clone()))
        .unwrap_or(0)
}

fn set_peak_value(env: &Env, agent: &Address, value: i128) {
    env.storage()
        .persistent()
        .set(&DataKey::PeakValue(agent.clone()), &value);
}

fn get_current_value(env: &Env, agent: &Address) -> i128 {
    env.storage()
        .persistent()
        .get(&DataKey::CurrentValue(agent.clone()))
        .unwrap_or(0)
}

fn set_current_value(env: &Env, agent: &Address, value: i128) {
    env.storage()
        .persistent()
        .set(&DataKey::CurrentValue(agent.clone()), &value);
}

fn get_slash_history(env: &Env, agent: &Address) -> Vec<SlashRecord> {
    env.storage()
        .persistent()
        .get(&DataKey::SlashHistory(agent.clone()))
        .unwrap_or_else(|| Vec::new(env))
}

fn set_slash_history(env: &Env, agent: &Address, history: &Vec<SlashRecord>) {
    env.storage()
        .persistent()
        .set(&DataKey::SlashHistory(agent.clone()), history);
}

fn execute_slash(env: &Env, agent: &Address, drawdown_bps: u32) {
    let threshold = get_drawdown_threshold_bps(env);
    let max_slash = get_max_slash_bps(env);

    let excess_bps = drawdown_bps - threshold;
    let slash_bps = if excess_bps > max_slash {
        max_slash
    } else {
        excess_bps
    };

    let mut history = get_slash_history(env, agent);
    history.push_back(SlashRecord {
        timestamp: env.ledger().timestamp(),
        drawdown_bps,
        slashed_bps: slash_bps,
    });
    set_slash_history(env, agent, &history);

    let registry = get_registry(env);
    let vault = get_vault(env);

    let registry_client = RegistryClient::new(env, &registry);
    registry_client.slash_agent(agent, &slash_bps);

    let vault_client = VaultClient::new(env, &vault);
    vault_client.enforce_drawdown_limit(agent);

    env.events()
        .publish(("SlashExecuted", agent.clone()), slash_bps);
}

#[contractimpl]
impl SlashingModule {
    pub fn init(env: Env, admin: Address, vault: Address, registry: Address) {
        if has_admin(&env) {
            panic_with_error!(&env, SlashingError::AlreadyInitialized);
        }

        admin.require_auth();

        env.storage().instance().set(&DataKey::Admin, &admin);
        env.storage().instance().set(&DataKey::Vault, &vault);
        env.storage().instance().set(&DataKey::Registry, &registry);
        env.storage()
            .instance()
            .set(&DataKey::DrawdownThresholdBps, &DEFAULT_DRAWDOWN_THRESHOLD_BPS);
        env.storage()
            .instance()
            .set(&DataKey::MaxSlashBps, &DEFAULT_MAX_SLASH_BPS);
    }

    pub fn report_performance(env: Env, agent: Address, current_value: i128) {
        require_admin(&env);

        let peak = get_peak_value(&env, &agent);

        if peak == 0 || current_value > peak {
            set_peak_value(&env, &agent, current_value);
        }

        set_current_value(&env, &agent, current_value);

        let updated_peak = get_peak_value(&env, &agent);

        if updated_peak > current_value && updated_peak > 0 {
            let drawdown_bps =
                (((updated_peak - current_value) * 10_000i128) / updated_peak) as u32;

            env.events()
                .publish(("DrawdownReported", agent.clone()), drawdown_bps);

            if drawdown_bps > get_drawdown_threshold_bps(&env) {
                execute_slash(&env, &agent, drawdown_bps);
            }
        }
    }

    pub fn set_threshold(env: Env, threshold_bps: u32) {
        require_admin(&env);

        if threshold_bps < 500 || threshold_bps > 5000 {
            panic_with_error!(&env, SlashingError::ThresholdOutOfRange);
        }

        env.storage()
            .instance()
            .set(&DataKey::DrawdownThresholdBps, &threshold_bps);

        env.events().publish(("ThresholdUpdated",), threshold_bps);
    }

    pub fn get_slash_history(env: Env, agent: Address) -> Vec<SlashRecord> {
        get_slash_history(&env, &agent)
    }

    pub fn get_peak_value(env: Env, agent: Address) -> i128 {
        get_peak_value(&env, &agent)
    }

    pub fn get_current_value(env: Env, agent: Address) -> i128 {
        get_current_value(&env, &agent)
    }

    pub fn get_config(env: Env) -> (Address, Address, Address, u32, u32) {
        (
            get_admin(&env),
            get_vault(&env),
            get_registry(&env),
            get_drawdown_threshold_bps(&env),
            get_max_slash_bps(&env),
        )
    }
}