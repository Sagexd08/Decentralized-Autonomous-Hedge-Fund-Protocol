#![no_std]

use soroban_sdk::{
    contract, contracterror, contractimpl, contracttype, panic_with_error, token, Address, BytesN,
    Env, Vec,
};

#[contract]
pub struct AgentRegistry;

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum AgentStatus {
    Unregistered,
    Probation,
    Active,
    Slashed,
    Deregistered,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Agent {
    pub owner: Address,
    pub strategy_hash: BytesN<32>,
    pub staked_amount: i128,
    pub registered_at: u64,
    pub simulation_ends: u64,
    pub status: AgentStatus,
    pub risk_pool: u32,
}

#[contracttype]
#[derive(Clone)]
pub enum DataKey {
    Admin,
    StakeToken,
    Treasury,
    MinStake,
    SimulationPeriodSecs,
    Agent(Address),
    AgentList,
}

#[contracterror]
#[repr(u32)]
#[derive(Copy, Clone, Debug, Eq, PartialEq, PartialOrd, Ord)]
pub enum RegistryError {
    AlreadyInitialized = 1,
    NotInitialized = 2,
    AlreadyRegistered = 3,
    InsufficientStake = 4,
    InvalidRiskPool = 5,
    AgentNotFound = 6,
    NotInProbation = 7,
    SimulationNotComplete = 8,
    AgentNotActive = 9,
    InvalidSlashBps = 10,
}

fn has_admin(env: &Env) -> bool {
    env.storage().instance().has(&DataKey::Admin)
}

fn get_admin(env: &Env) -> Address {
    env.storage()
        .instance()
        .get(&DataKey::Admin)
        .unwrap_or_else(|| panic_with_error!(env, RegistryError::NotInitialized))
}

fn require_admin(env: &Env) {
    let admin = get_admin(env);
    admin.require_auth();
}

fn get_stake_token(env: &Env) -> Address {
    env.storage()
        .instance()
        .get(&DataKey::StakeToken)
        .unwrap_or_else(|| panic_with_error!(env, RegistryError::NotInitialized))
}

fn get_treasury(env: &Env) -> Address {
    env.storage()
        .instance()
        .get(&DataKey::Treasury)
        .unwrap_or_else(|| panic_with_error!(env, RegistryError::NotInitialized))
}

fn get_min_stake(env: &Env) -> i128 {
    env.storage()
        .instance()
        .get(&DataKey::MinStake)
        .unwrap_or_else(|| panic_with_error!(env, RegistryError::NotInitialized))
}

fn get_simulation_period_secs(env: &Env) -> u64 {
    env.storage()
        .instance()
        .get(&DataKey::SimulationPeriodSecs)
        .unwrap_or_else(|| panic_with_error!(env, RegistryError::NotInitialized))
}

fn get_agent_list(env: &Env) -> Vec<Address> {
    env.storage()
        .persistent()
        .get(&DataKey::AgentList)
        .unwrap_or_else(|| Vec::new(env))
}

fn set_agent_list(env: &Env, list: &Vec<Address>) {
    env.storage().persistent().set(&DataKey::AgentList, list);
}

fn get_agent_opt(env: &Env, agent_address: &Address) -> Option<Agent> {
    env.storage()
        .persistent()
        .get(&DataKey::Agent(agent_address.clone()))
}

fn get_agent_or_panic(env: &Env, agent_address: &Address) -> Agent {
    get_agent_opt(env, agent_address)
        .unwrap_or_else(|| panic_with_error!(env, RegistryError::AgentNotFound))
}

fn set_agent(env: &Env, agent_address: &Address, agent: &Agent) {
    env.storage()
        .persistent()
        .set(&DataKey::Agent(agent_address.clone()), agent);
}

#[contractimpl]
impl AgentRegistry {
    pub fn init(
        env: Env,
        admin: Address,
        stake_token: Address,
        treasury: Address,
        min_stake: i128,
        simulation_period_secs: u64,
    ) {
        if has_admin(&env) {
            panic_with_error!(&env, RegistryError::AlreadyInitialized);
        }

        admin.require_auth();

        env.storage().instance().set(&DataKey::Admin, &admin);
        env.storage().instance().set(&DataKey::StakeToken, &stake_token);
        env.storage().instance().set(&DataKey::Treasury, &treasury);
        env.storage().instance().set(&DataKey::MinStake, &min_stake);
        env.storage()
            .instance()
            .set(&DataKey::SimulationPeriodSecs, &simulation_period_secs);

        let empty_list = Vec::<Address>::new(&env);
        set_agent_list(&env, &empty_list);
    }

    pub fn register_agent(
        env: Env,
        owner: Address,
        agent_address: Address,
        strategy_hash: BytesN<32>,
        risk_pool: u32,
        stake_amount: i128,
    ) {
        if !has_admin(&env) {
            panic_with_error!(&env, RegistryError::NotInitialized);
        }

        owner.require_auth();

        if get_agent_opt(&env, &agent_address).is_some() {
            panic_with_error!(&env, RegistryError::AlreadyRegistered);
        }

        if stake_amount < get_min_stake(&env) {
            panic_with_error!(&env, RegistryError::InsufficientStake);
        }

        if risk_pool > 2 {
            panic_with_error!(&env, RegistryError::InvalidRiskPool);
        }

        let token_address = get_stake_token(&env);
        let token_client = token::Client::new(&env, &token_address);

        token_client.transfer(&owner, &env.current_contract_address(), &stake_amount);

        let now = env.ledger().timestamp();
        let simulation_ends = now + get_simulation_period_secs(&env);

        let agent = Agent {
            owner: owner.clone(),
            strategy_hash,
            staked_amount: stake_amount,
            registered_at: now,
            simulation_ends,
            status: AgentStatus::Probation,
            risk_pool,
        };

        set_agent(&env, &agent_address, &agent);

        let mut list = get_agent_list(&env);
        list.push_back(agent_address.clone());
        set_agent_list(&env, &list);

        env.events().publish(
            ("AgentRegistered", agent_address),
            (risk_pool, stake_amount),
        );
    }

    pub fn activate_agent(env: Env, agent_address: Address) {
        require_admin(&env);

        let mut agent = get_agent_or_panic(&env, &agent_address);

        if agent.status != AgentStatus::Probation {
            panic_with_error!(&env, RegistryError::NotInProbation);
        }

        if env.ledger().timestamp() < agent.simulation_ends {
            panic_with_error!(&env, RegistryError::SimulationNotComplete);
        }

        agent.status = AgentStatus::Active;
        set_agent(&env, &agent_address, &agent);

        env.events().publish(("AgentActivated", agent_address), ());
    }

    pub fn slash_agent(env: Env, agent_address: Address, slash_bps: u32) {
        require_admin(&env);

        if slash_bps > 10_000 {
            panic_with_error!(&env, RegistryError::InvalidSlashBps);
        }

        let mut agent = get_agent_or_panic(&env, &agent_address);

        if agent.status != AgentStatus::Active {
            panic_with_error!(&env, RegistryError::AgentNotActive);
        }

        let slash_amount = (agent.staked_amount * slash_bps as i128) / 10_000;
        agent.staked_amount -= slash_amount;
        agent.status = AgentStatus::Slashed;

        set_agent(&env, &agent_address, &agent);

        let token_address = get_stake_token(&env);
        let treasury = get_treasury(&env);
        let token_client = token::Client::new(&env, &token_address);

        token_client.transfer(&env.current_contract_address(), &treasury, &slash_amount);

        env.events().publish(("AgentSlashed", agent_address), slash_amount);
    }

    pub fn get_agent(env: Env, agent_address: Address) -> Agent {
        get_agent_or_panic(&env, &agent_address)
    }

    pub fn get_active_agents(env: Env) -> Vec<Address> {
        let list = get_agent_list(&env);
        let mut active = Vec::<Address>::new(&env);

        let mut i = 0;
        while i < list.len() {
            let addr = list.get(i).unwrap();
            let agent = get_agent_or_panic(&env, &addr);
            if agent.status == AgentStatus::Active {
                active.push_back(addr);
            }
            i += 1;
        }

        active
    }

    pub fn get_config(env: Env) -> (Address, Address, Address, i128, u64) {
        (
            get_admin(&env),
            get_stake_token(&env),
            get_treasury(&env),
            get_min_stake(&env),
            get_simulation_period_secs(&env),
        )
    }
}