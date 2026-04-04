// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Mock price feed storing prices for WBTC/WETH/USDC/LINK/UNI (scaled 1e8).
///         Prices update via a ±1% pseudo-random walk bounded at [50%, 200%] of initial.
contract MockPriceFeed {
    // token address => current price (scaled 1e8)
    mapping(address => uint256) public prices;
    // token address => initial price (for bounds enforcement)
    mapping(address => uint256) public initialPrices;
    address[] public tokens;

    event PricesUpdated(address[] tokens, uint256[] newPrices);

    constructor(address[] memory _tokens, uint256[] memory _initialPrices) {
        require(_tokens.length == _initialPrices.length, "Length mismatch");
        for (uint256 i = 0; i < _tokens.length; i++) {
            tokens.push(_tokens[i]);
            prices[_tokens[i]] = _initialPrices[i];
            initialPrices[_tokens[i]] = _initialPrices[i];
        }
    }

    /// @notice Update all prices by ±1% pseudo-random walk, bounded [50%, 200%] of initial
    function updatePrices() external {
        uint256[] memory newPrices = new uint256[](tokens.length);
        for (uint256 i = 0; i < tokens.length; i++) {
            address token = tokens[i];
            // Derive pseudo-random delta in [-1_000_000, +1_000_000]
            uint256 rand = uint256(
                keccak256(abi.encodePacked(block.timestamp, block.prevrandao, token, i))
            );
            // Map to [-1_000_000, +1_000_000]: rand % 2_000_001 - 1_000_000
            int256 delta = int256(rand % 2_000_001) - 1_000_000;

            uint256 current = prices[token];
            uint256 initial = initialPrices[token];

            // Apply: price = price * (1e8 + delta) / 1e8
            int256 newPrice = int256(current) + (int256(current) * delta) / 1e8;
            if (newPrice < 0) newPrice = 0;

            uint256 updated = uint256(newPrice);

            // Clamp to [50%, 200%] of initial
            uint256 minPrice = initial * 50 / 100;
            uint256 maxPrice = initial * 200 / 100;
            if (updated < minPrice) updated = minPrice;
            if (updated > maxPrice) updated = maxPrice;

            prices[token] = updated;
            newPrices[i] = updated;
        }
        emit PricesUpdated(tokens, newPrices);
    }

    /// @notice Read current price for a token
    function getPrice(address token) external view returns (uint256) {
        return prices[token];
    }

    /// @notice Get number of tracked tokens
    function tokenCount() external view returns (uint256) {
        return tokens.length;
    }
}
