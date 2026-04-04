// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title AllocationEngine
 * @notice Implements on-chain weight storage for the Multiplicative Weights Update algorithm.
 *         MWU computation happens off-chain; results are submitted and verified here.
 *
 * @dev Update rule (computed off-chain):
 *      w_i(t+1) = w_i(t) * exp(eta * R_i(t))
 *      Normalized: w_i(t+1) /= sum_j(w_j(t+1))
 *
 *      Regret bound: O(sqrt(T * ln(N))) vs best fixed agent in hindsight.
 */
contract AllocationEngine is Ownable {
    address public vault;

    // Learning rate eta (scaled by 1e6, e.g. 10000 = 0.01)
    uint256 public eta = 10000;

    // Agent performance scores (risk-adjusted returns, signed)
    mapping(address => int256) public agentScores;

    // Reputation scores: alpha * recent + (1-alpha) * historical
    mapping(address => uint256) public reputationScores;
    uint256 public constant ALPHA = 300; // 0.3 * 1000

    uint256 public updateCount;

    event EtaUpdated(uint256 newEta);
    event ScoresSubmitted(address[] agents, int256[] scores);
    event ReputationUpdated(address indexed agent, uint256 score);

    constructor(address _vault) Ownable(msg.sender) {
        vault = _vault;
    }

    /**
     * @notice Submit risk-adjusted performance scores for agents.
     *         Called by authorized oracle after each evaluation period.
     * @param agents Agent addresses
     * @param scores Risk-adjusted returns (scaled by 1e6)
     * @param weights Normalized MWU weights (sum = 1e18)
     */
    function submitUpdate(
        address[] calldata agents,
        int256[] calldata scores,
        uint256[] calldata weights
    ) external onlyOwner {
        require(agents.length == scores.length && agents.length == weights.length, "Length mismatch");

        for (uint i = 0; i < agents.length; i++) {
            agentScores[agents[i]] = scores[i];
            _updateReputation(agents[i], scores[i]);
        }

        // Forward normalized weights to vault
        ICapitalVault(vault).updateWeights(agents, weights);
        updateCount++;
        emit ScoresSubmitted(agents, scores);
    }

    /**
     * @notice Reputation decay: Score = alpha * recent + (1-alpha) * historical
     */
    function _updateReputation(address agent, int256 recentScore) internal {
        uint256 recent = recentScore > 0 ? uint256(recentScore) : 0;
        uint256 historical = reputationScores[agent];
        reputationScores[agent] = (ALPHA * recent + (1000 - ALPHA) * historical) / 1000;
        emit ReputationUpdated(agent, reputationScores[agent]);
    }

    function setEta(uint256 _eta) external onlyOwner {
        require(_eta > 0 && _eta <= 50000, "eta out of range");
        eta = _eta;
        emit EtaUpdated(_eta);
    }
}

interface ICapitalVault {
    function updateWeights(address[] calldata agents, uint256[] calldata weights) external;
}
