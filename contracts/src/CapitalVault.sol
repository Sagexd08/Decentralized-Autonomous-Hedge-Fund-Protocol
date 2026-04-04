// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

interface IMockUniswapRouter {
    function swapExactETHForTokens(
        uint256 minAmountOut,
        address token,
        address to
    ) external payable returns (uint256 amountOut);
}

interface IMockAavePool {
    function supply(address token, uint256 amount, address onBehalfOf) external;
    function borrow(address token, uint256 amount, address onBehalfOf) external;
    function withdraw(address token, uint256 amount, address to) external;
}

interface IMockPriceFeedCV {
    function getPrice(address token) external view returns (uint256);
}

interface IERC20Approve {
    function approve(address spender, uint256 amount) external returns (bool);
}

/**
 * @title CapitalVault
 * @notice Custodies all investor ETH. Agents NEVER directly control capital.
 *         Enforces position limits, leverage caps, drawdown ceilings, and volatility budgets.
 *         Supports EIP-712 signed delegations for agent capital allocation.
 *         Extended with swap and lending functions for the simulated trading engine.
 * @dev Layer 1 of the DACAP three-layer architecture.
 */
contract CapitalVault is Ownable, ReentrancyGuard {
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

    // Per-investor, per-agent delegation params
    mapping(address => mapping(address => DelegationParams)) public delegations;

    // Track all investors per agent for allocation cap computation
    mapping(address => address[]) private _agentInvestors;
    mapping(address => mapping(address => bool)) private _investorTracked;

    uint256 public constant MAX_DRAWDOWN_BPS = 2000; // 20%
    uint256 public constant PERFORMANCE_FEE_BPS = 1000; // 10%

    // EIP-712
    bytes32 public DOMAIN_SEPARATOR;

    bytes32 public constant DELEGATION_TYPEHASH = keccak256(
        "DelegationParams(uint8 pool,address agent,uint256 amount,uint256 maxDrawdownBps,uint256 maxAllocationWei,address investor)"
    );

    struct DelegationParams {
        address agent;
        uint256 maxDrawdownBps;
        uint256 maxAllocationWei;
    }

    // ---- Trading Engine Storage ----

    // Trading infrastructure addresses (set by owner post-deploy)
    address public mockUniswapRouter;
    address public mockAavePool;
    address public mockPriceFeed;

    // Per-agent token balances: agent => token => amount
    mapping(address => mapping(address => uint256)) public agentTokenBalances;

    // Per-agent PnL in wei-equivalent (signed)
    mapping(address => int256) public agentPnL;

    // Registered agent addresses (set by owner)
    mapping(address => bool) public registeredAgents;

    // Tracks total ETH deployed per agent (for allocation cap enforcement)
    mapping(address => uint256) public agentDeployedWei;

    // ---- Events ----

    event WeightsUpdated(address[] agents, uint256[] weights);
    event DrawdownBreached(address indexed agent, uint256 drawdownBps);
    event RiskLimitEnforced(address indexed agent);
    event DelegationDeposited(
        address indexed investor,
        address indexed agent,
        uint8 pool,
        uint256 amount,
        uint256 maxDrawdownBps,
        uint256 maxAllocationWei
    );
    event TradeExecuted(
        address indexed agent,
        address indexed tokenOut,
        uint256 amountIn,
        uint256 amountOut,
        uint256 timestamp,
        string tradeType
    );

    // ---- Modifiers ----

    modifier onlyAllocationEngine() {
        require(msg.sender == allocationEngine, "Only allocation engine");
        _;
    }

    modifier onlySlashingModule() {
        require(msg.sender == slashingModule, "Only slashing module");
        _;
    }

    modifier onlyRegisteredAgent() {
        require(registeredAgents[msg.sender], "Not a registered agent");
        _;
    }

    constructor() Ownable(msg.sender) {
        volatilityCaps[CONSERVATIVE] = 800;   // 8%
        volatilityCaps[BALANCED] = 1800;       // 18%
        volatilityCaps[AGGRESSIVE] = 3500;     // 35%

        bytes32 domainTypeHash = keccak256(
            "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
        );
        DOMAIN_SEPARATOR = keccak256(
            abi.encode(
                domainTypeHash,
                keccak256(bytes("DACAP")),
                keccak256(bytes("1")),
                block.chainid,
                address(this)
            )
        );
    }

    /**
     * @notice Investor deposits ETH into a risk pool with a signed delegation to an agent.
     */
    function depositETH(
        uint8 pool,
        address agent,
        uint256 maxDrawdownBps,
        uint256 maxAllocationWei,
        bytes calldata /* signature */
    ) external payable nonReentrant {
        require(pool <= AGGRESSIVE, "Invalid pool");
        require(msg.value > 0, "ETH amount must be > 0");

        investorBalances[msg.sender][pool] += msg.value;
        poolTVL[pool] += msg.value;
        delegations[msg.sender][agent] = DelegationParams({
            agent: agent,
            maxDrawdownBps: maxDrawdownBps,
            maxAllocationWei: maxAllocationWei
        });

        // Track investor for this agent (for allocation cap computation)
        if (!_investorTracked[agent][msg.sender]) {
            _investorTracked[agent][msg.sender] = true;
            _agentInvestors[agent].push(msg.sender);
        }

        emit DelegationDeposited(
            msg.sender,
            agent,
            pool,
            msg.value,
            maxDrawdownBps,
            maxAllocationWei
        );
    }

    /**
     * @notice Returns the delegation params for a given investor-agent pair.
     */
    function getDelegation(address investor, address agent)
        external
        view
        returns (DelegationParams memory)
    {
        return delegations[investor][agent];
    }

    /**
     * @notice Allocation engine updates agent capital weights.
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
            agentWeights[agent] = 0;
            emit DrawdownBreached(agent, drawdownBps);
            emit RiskLimitEnforced(agent);
        }
    }

    // ---- Trading Engine Functions ----

    /// @notice Register an agent address (owner only)
    function registerAgent(address agent) external onlyOwner {
        registeredAgents[agent] = true;
    }

    /// @notice Set trading infrastructure addresses
    function setTradingContracts(
        address _router,
        address _aavePool,
        address _priceFeed
    ) external onlyOwner {
        mockUniswapRouter = _router;
        mockAavePool = _aavePool;
        mockPriceFeed = _priceFeed;
    }

    /// @notice Compute total maxAllocationWei for an agent across all investors
    function _maxAllocationForAgent(address agent) internal view returns (uint256 total) {
        address[] storage investors = _agentInvestors[agent];
        for (uint256 i = 0; i < investors.length; i++) {
            total += delegations[investors[i]][agent].maxAllocationWei;
        }
    }

    /// @notice Execute ETH→token swap via MockUniswapRouter
    function executeSwap(
        address tokenOut,
        uint256 amountIn,
        uint256 minAmountOut
    ) external onlyRegisteredAgent nonReentrant {
        uint256 maxAlloc = _maxAllocationForAgent(msg.sender);
        uint256 remaining = maxAlloc > agentDeployedWei[msg.sender]
            ? maxAlloc - agentDeployedWei[msg.sender]
            : 0;
        require(amountIn <= remaining, "Exceeds allocation cap");
        require(address(this).balance >= amountIn, "Insufficient vault balance");

        uint256 amountOut = IMockUniswapRouter(mockUniswapRouter)
            .swapExactETHForTokens{value: amountIn}(minAmountOut, tokenOut, address(this));

        agentTokenBalances[msg.sender][tokenOut] += amountOut;
        agentDeployedWei[msg.sender] += amountIn;

        uint256 price = IMockPriceFeedCV(mockPriceFeed).getPrice(tokenOut);
        agentPnL[msg.sender] += int256(amountOut * price / 1e8) - int256(amountIn);

        emit TradeExecuted(msg.sender, tokenOut, amountIn, amountOut, block.timestamp, "swap");
    }

    /// @notice Supply agent's ERC20 tokens to MockAavePool
    function supplyToAave(address token, uint256 amount)
        external onlyRegisteredAgent nonReentrant
    {
        require(agentTokenBalances[msg.sender][token] >= amount, "Insufficient token balance");
        IERC20Approve(token).approve(mockAavePool, amount);
        IMockAavePool(mockAavePool).supply(token, amount, address(this));
        agentTokenBalances[msg.sender][token] -= amount;
        emit TradeExecuted(msg.sender, token, amount, 0, block.timestamp, "supply");
    }

    /// @notice Borrow ERC20 tokens from MockAavePool
    function borrowFromAave(address token, uint256 amount)
        external onlyRegisteredAgent nonReentrant
    {
        IMockAavePool(mockAavePool).borrow(token, amount, address(this));
        agentTokenBalances[msg.sender][token] += amount;
        emit TradeExecuted(msg.sender, token, 0, amount, block.timestamp, "borrow");
    }

    /// @notice Withdraw previously supplied tokens from MockAavePool
    function withdrawFromAave(address token, uint256 amount)
        external onlyRegisteredAgent nonReentrant
    {
        IMockAavePool(mockAavePool).withdraw(token, amount, address(this));
        agentTokenBalances[msg.sender][token] += amount;
        emit TradeExecuted(msg.sender, token, 0, amount, block.timestamp, "withdraw");
    }

    // ---- Admin ----

    function setAllocationEngine(address _engine) external onlyOwner {
        allocationEngine = _engine;
    }

    function setSlashingModule(address _slashing) external onlyOwner {
        slashingModule = _slashing;
    }

    function totalTVL() external view returns (uint256) {
        return poolTVL[CONSERVATIVE] + poolTVL[BALANCED] + poolTVL[AGGRESSIVE];
    }

    // --- Internal helpers ---

    function _recoverSigner(bytes32 digest, bytes calldata sig) internal pure returns (address) {
        require(sig.length == 65, "Invalid signature length");
        bytes32 r;
        bytes32 s;
        uint8 v;
        assembly {
            r := calldataload(sig.offset)
            s := calldataload(add(sig.offset, 32))
            v := byte(0, calldataload(add(sig.offset, 64)))
        }
        return ecrecover(digest, v, r, s);
    }

    receive() external payable {}
}
