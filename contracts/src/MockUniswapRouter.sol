pragma solidity ^0.8.20;

interface IMockPriceFeed {
    function getPrice(address token) external view returns (uint256);
}

interface IMockERC20 {
    function mint(address to, uint256 amount) external;
}

contract MockUniswapRouter {
    IMockPriceFeed public priceFeed;
    uint256 public constant FEE_BPS = 30;
    uint256 public constant SLIPPAGE_BPS = 200;

    event Swap(address indexed token, address indexed to, uint256 ethIn, uint256 tokenOut);

    constructor(address _priceFeed) {
        priceFeed = IMockPriceFeed(_priceFeed);
    }

    function swapExactETHForTokens(
        uint256 minAmountOut,
        address token,
        address to
    ) external payable returns (uint256 amountOut) {
        require(msg.value > 0, "No ETH sent");

        uint256 price = priceFeed.getPrice(token);
        require(price > 0, "No price available");

        uint256 base = msg.value * price / 1e8;

        uint256 afterFee = base * (10000 - FEE_BPS) / 10000;

        uint256 rand = uint256(
            keccak256(abi.encodePacked(block.timestamp, block.prevrandao, token, to, msg.value))
        );

        int256 slippagePct = int256(rand % 401) - 200;

        int256 slippageDelta = int256(afterFee) * slippagePct / 10000;
        int256 computed = int256(afterFee) + slippageDelta;
        if (computed < 0) computed = 0;
        amountOut = uint256(computed);

        require(amountOut >= minAmountOut, "Slippage exceeded");

        IMockERC20(token).mint(to, amountOut);
        emit Swap(token, to, msg.value, amountOut);
    }
}
