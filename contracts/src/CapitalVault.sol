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

contract CapitalVault is Ownable, ReentrancyGuard {
    address public allocationEngine;
    address public slashingModule;

    uint8 public constant CONSERVATIVE = 0;
    uint8 public constant BALANCED = 1;
    uint8 public constant AGGRESSIVE = 2;

    mapping(uint8 => uint256) public volatilityCaps;

    mapping(address => mapping(uint8 => uint256)) public investorBalances;

    mapping(address => uint256) public agentWeights;

    mapping(address => uint256) public agentPeakValue;
    mapping(address => uint256) public agentCurrentValue;

    mapping(uint8 => uint256) public poolTVL;

    mapping(address => mapping(address => DelegationParams)) public delegations;

    mapping(address => address[]) private _agentInvestors;
    mapping(address => mapping(address => bool)) private _investorTracked;

    uint256 public constant MAX_DRAWDOWN_BPS = 2000;
    uint256 public constant PERFORMANCE_FEE_BPS = 1000;

    bytes32 public DOMAIN_SEPARATOR;

    bytes32 public constant DELEGATION_TYPEHASH = keccak256(
        "DelegationParams(uint8 pool,address agent,uint256 amount,uint256 maxDrawdownBps,uint256 maxAllocationWei,address investor)"
    );

    struct DelegationParams {
        address agent;
        uint256 maxDrawdownBps;
        uint256 maxAllocationWei;
    }

    address public mockUniswapRouter;
    address public mockAavePool;
    address public mockPriceFeed;

    mapping(address => mapping(address => uint256)) public agentTokenBalances;

    mapping(address => int256) public agentPnL;

    mapping(address => bool) public registeredAgents;

    mapping(address => uint256) public agentDeployedWei;

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
        volatilityCaps[CONSERVATIVE] = 800;
        volatilityCaps[BALANCED] = 1800;
        volatilityCaps[AGGRESSIVE] = 3500;

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

    function depositETH(
        uint8 pool,
        address agent,
        uint256 maxDrawdownBps,
        uint256 maxAllocationWei,
        bytes calldata
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

    function getDelegation(address investor, address agent)
        external
        view
        returns (DelegationParams memory)
    {
        return delegations[investor][agent];
    }

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

    function registerAgent(address agent) external onlyOwner {
        registeredAgents[agent] = true;
    }

    function setTradingContracts(
        address _router,
        address _aavePool,
        address _priceFeed
    ) external onlyOwner {
        mockUniswapRouter = _router;
        mockAavePool = _aavePool;
        mockPriceFeed = _priceFeed;
    }

    function _maxAllocationForAgent(address agent) internal view returns (uint256 total) {
        address[] storage investors = _agentInvestors[agent];
        for (uint256 i = 0; i < investors.length; i++) {
            total += delegations[investors[i]][agent].maxAllocationWei;
        }
    }

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

    function supplyToAave(address token, uint256 amount)
        external onlyRegisteredAgent nonReentrant
    {
        require(agentTokenBalances[msg.sender][token] >= amount, "Insufficient token balance");
        IERC20Approve(token).approve(mockAavePool, amount);
        IMockAavePool(mockAavePool).supply(token, amount, address(this));
        agentTokenBalances[msg.sender][token] -= amount;
        emit TradeExecuted(msg.sender, token, amount, 0, block.timestamp, "supply");
    }

    function borrowFromAave(address token, uint256 amount)
        external onlyRegisteredAgent nonReentrant
    {
        IMockAavePool(mockAavePool).borrow(token, amount, address(this));
        agentTokenBalances[msg.sender][token] += amount;
        emit TradeExecuted(msg.sender, token, 0, amount, block.timestamp, "borrow");
    }

    function withdrawFromAave(address token, uint256 amount)
        external onlyRegisteredAgent nonReentrant
    {
        IMockAavePool(mockAavePool).withdraw(token, amount, address(this));
        agentTokenBalances[msg.sender][token] += amount;
        emit TradeExecuted(msg.sender, token, 0, amount, block.timestamp, "withdraw");
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
