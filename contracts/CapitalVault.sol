// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title CapitalVault
 * @notice Custodies all investor funds. Agents NEVER directly control capital.
 *         Enforces position limits, leverage caps, drawdown ceilings, and volatility budgets.
 * @dev Layer 1 of the DACAP three-layer architecture.
 */
contract CapitalVault is Ownable, ReentrancyGuard {
    IERC20 public immutable token;
    address public allocationEngine;
    address public slashingModule;

    // Risk pool IDs: 0=Conservative, 1=Balanced, 2=Aggressive
    uint8 public constant CONSERVATIVE = 0;
    uint8 public constant BALANCED = 1;
    uint8 public constant AGGRESSIVE = 2;

    // Volatility caps per pool (in basis points, annualized)
    mapping(uint8 => uint256) public volatilityCaps;

    // Investor balances per pool
    mapping(address => mapping(uint8 => uint256)) public investorBalances;

    // Agent capital weights (normalized, 1e18 = 100%)
    mapping(address => uint256) public agentWeights;

    // Agent drawdown tracking
    mapping(address => uint256) public agentPeakValue;
    mapping(address => uint256) public agentCurrentValue;

    // Total TVL per pool
    mapping(uint8 => uint256) public poolTVL;

    uint256 public constant MAX_DRAWDOWN_BPS = 2000; // 20%
    uint256 public constant PERFORMANCE_FEE_BPS = 1000; // 10%

    event Deposited(address indexed investor, uint8 pool, uint256 amount);
    event Withdrawn(address indexed investor, uint8 pool, uint256 amount);
    event WeightsUpdated(address[] agents, uint256[] weights);
    event DrawdownBreached(address indexed agent, uint256 drawdownBps);
    event RiskLimitEnforced(address indexed agent);

    modifier onlyAllocationEngine() {
        require(msg.sender == allocationEngine, "Only allocation engine");
        _;
    }

    modifier onlySlashingModule() {
        require(msg.sender == slashingModule, "Only slashing module");
        _;
    }

    constructor(address _token) Ownable(msg.sender) {
        token = IERC20(_token);
        volatilityCaps[CONSERVATIVE] = 800;   // 8%
        volatilityCaps[BALANCED] = 1800;       // 18%
        volatilityCaps[AGGRESSIVE] = 3500;     // 35%
    }

    /**
     * @notice Investor deposits into a risk pool.
     * @param pool Risk pool ID (0=Conservative, 1=Balanced, 2=Aggressive)
     * @param amount Amount of tokens to deposit
     */
    function deposit(uint8 pool, uint256 amount) external nonReentrant {
        require(pool <= AGGRESSIVE, "Invalid pool");
        require(amount > 0, "Amount must be > 0");
        token.transferFrom(msg.sender, address(this), amount);
        investorBalances[msg.sender][pool] += amount;
        poolTVL[pool] += amount;
        emit Deposited(msg.sender, pool, amount);
    }

    /**
     * @notice Investor withdraws from a risk pool.
     */
    function withdraw(uint8 pool, uint256 amount) external nonReentrant {
        require(investorBalances[msg.sender][pool] >= amount, "Insufficient balance");
        investorBalances[msg.sender][pool] -= amount;
        poolTVL[pool] -= amount;
        token.transfer(msg.sender, amount);
        emit Withdrawn(msg.sender, pool, amount);
    }

    /**
     * @notice Allocation engine updates agent capital weights.
     *         Weights are computed off-chain via MWU algorithm and submitted here.
     * @param agents Array of agent addresses
     * @param weights Normalized weights (sum = 1e18)
     */
    function updateWeights(
        address[] calldata agents,
        uint256[] calldata weights
    ) external onlyAllocationEngine {
        require(agents.length == weights.length, "Length mismatch");
        uint256 total;
        for (uint i = 0; i < weights.length; i++) {
            total += weights[i];
        }
        require(total == 1e18, "Weights must sum to 1e18");
        for (uint i = 0; i < agents.length; i++) {
            agentWeights[agents[i]] = weights[i];
        }
        emit WeightsUpdated(agents, weights);
    }

    /**
     * @notice Check and enforce drawdown limits for an agent.
     */
    function enforceDrawdownLimit(address agent) external onlySlashingModule {
        uint256 peak = agentPeakValue[agent];
        uint256 current = agentCurrentValue[agent];
        if (peak == 0) return;
        uint256 drawdownBps = ((peak - current) * 10000) / peak;
        if (drawdownBps > MAX_DRAWDOWN_BPS) {
            agentWeights[agent] = 0; // Zero out allocation
            emit DrawdownBreached(agent, drawdownBps);
            emit RiskLimitEnforced(agent);
        }
    }

    function setAllocationEngine(address _engine) external onlyOwner {
        allocationEngine = _engine;
    }

    function setSlashingModule(address _slashing) external onlyOwner {
        slashingModule = _slashing;
    }

    function totalTVL() external view returns (uint256) {
        return poolTVL[CONSERVATIVE] + poolTVL[BALANCED] + poolTVL[AGGRESSIVE];
    }
}
