// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title SlashingModule
 * @notice Monitors agent drawdown and executes slashing when thresholds are breached.
 *         Redistributes slashed collateral to protocol treasury.
 *
 * @dev Slashing formula:
 *      slashBps = min(drawdownBps - threshold, maxSlashBps)
 *      Ensures proportional punishment, not binary elimination.
 */
contract SlashingModule is Ownable {
    address public vault;
    address public registry;

    uint256 public drawdownThresholdBps = 2000;  // 20%
    uint256 public maxSlashBps = 5000;            // 50% of stake

    struct SlashRecord {
        uint256 timestamp;
        uint256 drawdownBps;
        uint256 slashedBps;
    }

    mapping(address => SlashRecord[]) public slashHistory;
    mapping(address => uint256) public peakValues;
    mapping(address => uint256) public currentValues;

    event DrawdownReported(address indexed agent, uint256 drawdownBps);
    event SlashExecuted(address indexed agent, uint256 slashBps);
    event ThresholdUpdated(uint256 newThreshold);

    constructor(address _vault, address _registry) Ownable(msg.sender) {
        vault = _vault;
        registry = _registry;
    }

    /**
     * @notice Report agent performance. Called by oracle after each evaluation.
     * @param agent Agent address
     * @param currentValue Current portfolio value (scaled by 1e6)
     */
    function reportPerformance(address agent, uint256 currentValue) external onlyOwner {
        if (peakValues[agent] == 0 || currentValue > peakValues[agent]) {
            peakValues[agent] = currentValue;
        }
        currentValues[agent] = currentValue;

        uint256 peak = peakValues[agent];
        if (peak > currentValue) {
            uint256 drawdownBps = ((peak - currentValue) * 10000) / peak;
            emit DrawdownReported(agent, drawdownBps);

            if (drawdownBps > drawdownThresholdBps) {
                _executeSlash(agent, drawdownBps);
            }
        }
    }

    function _executeSlash(address agent, uint256 drawdownBps) internal {
        uint256 excessBps = drawdownBps - drawdownThresholdBps;
        uint256 slashBps = excessBps > maxSlashBps ? maxSlashBps : excessBps;

        slashHistory[agent].push(SlashRecord({
            timestamp: block.timestamp,
            drawdownBps: drawdownBps,
            slashedBps: slashBps
        }));

        IAgentRegistry(registry).slashAgent(agent, slashBps);
        ICapitalVault(vault).enforceDrawdownLimit(agent);
        emit SlashExecuted(agent, slashBps);
    }

    function setThreshold(uint256 _thresholdBps) external onlyOwner {
        require(_thresholdBps >= 500 && _thresholdBps <= 5000, "Out of range");
        drawdownThresholdBps = _thresholdBps;
        emit ThresholdUpdated(_thresholdBps);
    }

    function getSlashHistory(address agent) external view returns (SlashRecord[] memory) {
        return slashHistory[agent];
    }
}

interface IAgentRegistry {
    function slashAgent(address agent, uint256 slashBps) external;
}

interface ICapitalVault {
    function enforceDrawdownLimit(address agent) external;
}
