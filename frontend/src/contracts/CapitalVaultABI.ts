export const CAPITAL_VAULT_ABI = [
  "function depositETH(uint8 pool, address agent, uint256 maxDrawdownBps, uint256 maxAllocationWei, bytes calldata signature) payable",
  "function getDelegation(address investor, address agent) view returns (tuple(address agent, uint256 maxDrawdownBps, uint256 maxAllocationWei))",
  "event DelegationDeposited(address indexed investor, address indexed agent, uint8 pool, uint256 amount, uint256 maxDrawdownBps, uint256 maxAllocationWei)",
] as const
