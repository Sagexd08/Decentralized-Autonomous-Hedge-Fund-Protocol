// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

<<<<<<< HEAD
import "./src/AgentRegistry.sol";
=======
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title AgentRegistry
 * @notice Manages agent registration, staking, and anti-sybil enforcement.
 *         Agents must stake collateral before receiving any capital allocation.
 *
 * @dev Anti-sybil: minimum stake = MIN_STAKE tokens.
 *      Agents in probation must pass simulation arena before live allocation.
 */
contract AgentRegistry is Ownable, ReentrancyGuard {
    IERC20 public immutable stakeToken;

    uint256 public constant MIN_STAKE = 10_000e18; // 10,000 tokens
    uint256 public constant SIMULATION_PERIOD = 7 days;

    enum AgentStatus { Unregistered, Probation, Active, Slashed, Deregistered }

    struct Agent {
        address owner;
        bytes32 strategyHash;   // keccak256 of strategy description
        uint256 stakedAmount;
        uint256 registeredAt;
        uint256 simulationEnds;
        AgentStatus status;
        uint8 riskPool;         // 0=Conservative, 1=Balanced, 2=Aggressive
    }

    mapping(address => Agent) public agents;
    address[] public agentList;

    event AgentRegistered(address indexed agent, uint8 riskPool, uint256 stake);
    event AgentActivated(address indexed agent);
    event AgentSlashed(address indexed agent, uint256 slashedAmount);
    event AgentDeregistered(address indexed agent);
    event StakeIncreased(address indexed agent, uint256 amount);

    constructor(address _stakeToken) Ownable(msg.sender) {
        stakeToken = IERC20(_stakeToken);
    }

    /**
     * @notice Register a new strategy agent with mandatory stake.
     * @param agentAddress The agent's execution address
     * @param strategyHash keccak256 hash of strategy description
     * @param riskPool Target risk pool (0/1/2)
     * @param stakeAmount Amount to stake (must be >= MIN_STAKE)
     */
    function registerAgent(
        address agentAddress,
        bytes32 strategyHash,
        uint8 riskPool,
        uint256 stakeAmount
    ) external nonReentrant {
        require(agents[agentAddress].status == AgentStatus.Unregistered, "Already registered");
        require(stakeAmount >= MIN_STAKE, "Insufficient stake");
        require(riskPool <= 2, "Invalid pool");

        stakeToken.transferFrom(msg.sender, address(this), stakeAmount);

        agents[agentAddress] = Agent({
            owner: msg.sender,
            strategyHash: strategyHash,
            stakedAmount: stakeAmount,
            registeredAt: block.timestamp,
            simulationEnds: block.timestamp + SIMULATION_PERIOD,
            status: AgentStatus.Probation,
            riskPool: riskPool
        });

        agentList.push(agentAddress);
        emit AgentRegistered(agentAddress, riskPool, stakeAmount);
    }

    /**
     * @notice Activate agent after passing simulation period.
     */
    function activateAgent(address agentAddress) external onlyOwner {
        Agent storage agent = agents[agentAddress];
        require(agent.status == AgentStatus.Probation, "Not in probation");
        require(block.timestamp >= agent.simulationEnds, "Simulation not complete");
        agent.status = AgentStatus.Active;
        emit AgentActivated(agentAddress);
    }

    /**
     * @notice Slash agent stake on drawdown breach. Called by SlashingModule.
     * @param agentAddress Agent to slash
     * @param slashBps Percentage of stake to slash (basis points)
     */
    function slashAgent(address agentAddress, uint256 slashBps) external onlyOwner {
        Agent storage agent = agents[agentAddress];
        require(agent.status == AgentStatus.Active, "Agent not active");
        uint256 slashAmount = (agent.stakedAmount * slashBps) / 10000;
        agent.stakedAmount -= slashAmount;
        agent.status = AgentStatus.Slashed;
        // Slashed tokens go to protocol treasury
        stakeToken.transfer(owner(), slashAmount);
        emit AgentSlashed(agentAddress, slashAmount);
    }

    function getActiveAgents() external view returns (address[] memory) {
        uint count;
        for (uint i = 0; i < agentList.length; i++) {
            if (agents[agentList[i]].status == AgentStatus.Active) count++;
        }
        address[] memory active = new address[](count);
        uint j;
        for (uint i = 0; i < agentList.length; i++) {
            if (agents[agentList[i]].status == AgentStatus.Active) {
                active[j++] = agentList[i];
            }
        }
        return active;
    }
}
>>>>>>> D!
