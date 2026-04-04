// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IMockPriceFeed {
    function getPrice(address token) external view returns (uint256);
}

interface IMockERC20 {
    function mint(address to, uint256 amount) external;
}

/// @notice Mock Uniswap router: swaps ETH for ERC20 tokens using MockPriceFeed prices.
///         Applies 0.3% fee and ±2% pseudo-random slippage.
contract MockUniswapRouter {
    IMockPriceFeed public priceFeed;
    uint256 public constant FEE_BPS = 30;       // 0.3%
    uint256 public constant SLIPPAGE_BPS = 200; // ±2%

    event Swap(address indexed token, address indexed to, uint256 ethIn, uint256 tokenOut);

    constructor(address _priceFeed) {
        priceFeed = IMockPriceFeed(_priceFeed);
    }

    /// @notice Swap ETH for tokens
    /// @param minAmountOut Minimum acceptable token output (slippage guard)
    /// @param token        ERC20 token to receive
    /// @param to           Recipient address
    function swapExactETHForTokens(
        uint256 minAmountOut,
        address token,
        address to
    ) external payable returns (uint256 amountOut) {
        require(msg.value > 0, "No ETH sent");

        uint256 price = priceFeed.getPrice(token);
        require(price > 0, "No price available");

        // base = msg.value * price / 1e8
        uint256 base = msg.value * price / 1e8;

        // afterFee = base * (10000 - 30) / 10000
        uint256 afterFee = base * (10000 - FEE_BPS) / 10000;

        // Derive pseudo-random slippage in [-200, +200] bps
        uint256 rand = uint256(
            keccak256(abi.encodePacked(block.timestamp, block.prevrandao, token, to, msg.value))
        );
        // Map to [-200, +200]: rand % 401 - 200
        int256 slippagePct = int256(rand % 401) - 200;

        // amountOut = afterFee + afterFee * slippagePct / 10000
        int256 slippageDelta = int256(afterFee) * slippagePct / 10000;
        int256 computed = int256(afterFee) + slippageDelta;
        if (computed < 0) computed = 0;
        amountOut = uint256(computed);

        require(amountOut >= minAmountOut, "Slippage exceeded");

        IMockERC20(token).mint(to, amountOut);
        emit Swap(token, to, msg.value, amountOut);
    }
}
