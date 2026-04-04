#![no_std]

use soroban_sdk::{
    contract, contractclient, contracterror, contractimpl, contracttype, panic_with_error, Address,
    Env, Vec,
};

#[contract]
pub struct AllocationEngine;

#[contractclient(name = "VaultClient")]
pub trait VaultContract {
    fn update_weights(env: Env, agents: Vec<Address>, weights: Vec<i128>);
}

#[contracttype]
#[derive(Clone)]
pub enum DataKey {
    Admin,
    Vault,
    Eta,
    UpdateCount,
    AgentScore(Address),
    ReputationScore(Address),
}

#[contracterror]
#[repr(u32)]
#[derive(Copy, Clone, Debug, Eq, PartialEq, PartialOrd, Ord)]
pub enum AllocationError {
    AlreadyInitialized = 1,
    NotInitialized = 2,
    LengthMismatch = 3,
    EtaOutOfRange = 4,
}

const DEFAULT_ETA: u32 = 10_000; // 0.01 scaled by 1e6
const ALPHA: u32 = 300; // 0.3 * 1000

fn has_admin(env: &Env) -> bool {
    env.storage().instance().has(&DataKey::Admin)
}

fn get_admin(env: &Env) -> Address {
    env.storage()
        .instance()
        .get(&DataKey::Admin)
        .unwrap_or_else(|| panic_with_error!(env, AllocationError::NotInitialized))
}

fn require_admin(env: &Env) {
    let admin = get_admin(env);
    admin.require_auth();
}

fn get_vault(env: &Env) -> Address {
    env.storage()
        .instance()
        .get(&DataKey::Vault)
        .unwrap_or_else(|| panic_with_error!(env, AllocationError::NotInitialized))
}

fn get_eta_internal(env: &Env) -> u32 {
    env.storage()
        .instance()
        .get(&DataKey::Eta)
        .unwrap_or(DEFAULT_ETA)
}

fn get_update_count_internal(env: &Env) -> u32 {
    env.storage()
        .instance()
        .get(&DataKey::UpdateCount)
        .unwrap_or(0)
}

fn get_reputation_internal(env: &Env, agent: &Address) -> i128 {
    env.storage()
        .persistent()
        .get(&DataKey::ReputationScore(agent.clone()))
        .unwrap_or(0)
}

fn set_reputation_internal(env: &Env, agent: &Address, value: i128) {
    env.storage()
        .persistent()
        .set(&DataKey::ReputationScore(agent.clone()), &value);
}

fn set_score_internal(env: &Env, agent: &Address, value: i128) {
    env.storage()
        .persistent()
        .set(&DataKey::AgentScore(agent.clone()), &value);
}

fn get_score_internal(env: &Env, agent: &Address) -> i128 {
    env.storage()
        .persistent()
        .get(&DataKey::AgentScore(agent.clone()))
        .unwrap_or(0)
}

fn update_reputation(env: &Env, agent: &Address, recent_score: i128) -> i128 {
    let recent = if recent_score > 0 { recent_score } else { 0 };
    let historical = get_reputation_internal(env, agent);

    let updated = ((ALPHA as i128) * recent + ((1000 - ALPHA) as i128) * historical) / 1000;

    set_reputation_internal(env, agent, updated);

    env.events()
        .publish(("ReputationUpdated", agent.clone()), updated);

    updated
}

#[contractimpl]
impl AllocationEngine {
    pub fn init(env: Env, admin: Address, vault: Address) {
        if has_admin(&env) {
            panic_with_error!(&env, AllocationError::AlreadyInitialized);
        }

        admin.require_auth();

        env.storage().instance().set(&DataKey::Admin, &admin);
        env.storage().instance().set(&DataKey::Vault, &vault);
        env.storage().instance().set(&DataKey::Eta, &DEFAULT_ETA);
        env.storage().instance().set(&DataKey::UpdateCount, &0u32);
    }

    pub fn submit_update(
        env: Env,
        agents: Vec<Address>,
        scores: Vec<i128>,
        weights: Vec<i128>,
    ) {
        require_admin(&env);

        if agents.len() != scores.len() || agents.len() != weights.len() {
            panic_with_error!(&env, AllocationError::LengthMismatch);
        }

        let mut i = 0;
        while i < agents.len() {
            let agent = agents.get(i).unwrap();
            let score = scores.get(i).unwrap();

            set_score_internal(&env, &agent, score);
            update_reputation(&env, &agent, score);

            i += 1;
        }

        let vault = get_vault(&env);
        let vault_client = VaultClient::new(&env, &vault);
        vault_client.update_weights(&agents, &weights);

        let new_count = get_update_count_internal(&env) + 1;
        env.storage().instance().set(&DataKey::UpdateCount, &new_count);

        env.events().publish(("ScoresSubmitted",), (agents, scores));
    }

    pub fn set_eta(env: Env, eta: u32) {
        require_admin(&env);

        if eta == 0 || eta > 50_000 {
            panic_with_error!(&env, AllocationError::EtaOutOfRange);
        }

        env.storage().instance().set(&DataKey::Eta, &eta);
        env.events().publish(("EtaUpdated",), eta);
    }

    pub fn get_config(env: Env) -> (Address, Address, u32, u32) {
        (
            get_admin(&env),
            get_vault(&env),
            get_eta_internal(&env),
            get_update_count_internal(&env),
        )
    }

    pub fn get_agent_score(env: Env, agent: Address) -> i128 {
        get_score_internal(&env, &agent)
    }

    pub fn get_reputation_score(env: Env, agent: Address) -> i128 {
        get_reputation_internal(&env, &agent)
    }

    pub fn alpha(_env: Env) -> u32 {
        ALPHA
    }
}