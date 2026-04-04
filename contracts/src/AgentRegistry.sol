pragma solidity ^0.8.20;

<<<<<<< HEAD
interface IERC20 {
    function transferFrom(address from, address to, uint256 value) external returns (bool);
    function transfer(address to, uint256 value) external returns (bool);
}

abstract contract Ownable {
    address private _owner;

    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    constructor(address initialOwner) {
        require(initialOwner != address(0), "Invalid owner");
        _owner = initialOwner;
        emit OwnershipTransferred(address(0), initialOwner);
    }

    modifier onlyOwner() {
        require(msg.sender == _owner, "Ownable: caller is not the owner");
        _;
    }

    function owner() public view returns (address) {
        return _owner;
    }
}

abstract contract ReentrancyGuard {
    uint256 private constant _NOT_ENTERED = 1;
    uint256 private constant _ENTERED = 2;
    uint256 private _status = _NOT_ENTERED;

    modifier nonReentrant() {
        require(_status != _ENTERED, "ReentrancyGuard: reentrant call");
        _status = _ENTERED;
        _;
        _status = _NOT_ENTERED;
    }
}
=======
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
>>>>>>> D!

contract AgentRegistry is Ownable, ReentrancyGuard {
    IERC20 public immutable stakeToken;

    uint256 public constant MIN_STAKE = 10_000e18;
    uint256 public constant SIMULATION_PERIOD = 7 days;

    enum AgentStatus { Unregistered, Probation, Active, Slashed, Deregistered }

    struct Agent {
        address owner;
        bytes32 strategyHash;
        uint256 stakedAmount;
        uint256 registeredAt;
        uint256 simulationEnds;
        AgentStatus status;
        uint8 riskPool;
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

    function activateAgent(address agentAddress) external onlyOwner {
        Agent storage agent = agents[agentAddress];
        require(agent.status == AgentStatus.Probation, "Not in probation");
        require(block.timestamp >= agent.simulationEnds, "Simulation not complete");
        agent.status = AgentStatus.Active;
        emit AgentActivated(agentAddress);
    }

    function slashAgent(address agentAddress, uint256 slashBps) external onlyOwner {
        Agent storage agent = agents[agentAddress];
        require(agent.status == AgentStatus.Active, "Agent not active");
        uint256 slashAmount = (agent.stakedAmount * slashBps) / 10000;
        agent.stakedAmount -= slashAmount;
        agent.status = AgentStatus.Slashed;

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
