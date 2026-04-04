pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";

contract AllocationEngine is Ownable {
    address public vault;

    uint256 public eta = 10000;

    mapping(address => int256) public agentScores;

    mapping(address => uint256) public reputationScores;
    uint256 public constant ALPHA = 300;

    uint256 public updateCount;

    event EtaUpdated(uint256 newEta);
    event ScoresSubmitted(address[] agents, int256[] scores);
    event ReputationUpdated(address indexed agent, uint256 score);

    constructor(address _vault) Ownable(msg.sender) {
        vault = _vault;
    }

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

        ICapitalVault(vault).updateWeights(agents, weights);
        updateCount++;
        emit ScoresSubmitted(agents, scores);
    }

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
