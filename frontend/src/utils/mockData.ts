export const generateTimeSeries = (points: number, base: number, volatility: number) => {
  const data = []
  let val = base
  const now = Date.now()
  for (let i = points; i >= 0; i--) {
    val += (Math.random() - 0.48) * volatility
    data.push({
      time: new Date(now - i * 3600000).toISOString().slice(0, 16).replace('T', ' '),
      value: Math.max(0, parseFloat(val.toFixed(2)))
    })
  }
  return data
}

export const agents = [
  { id: 'AGT-001', address: '0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266', name: 'AlphaWave', strategy: 'Momentum + ML', risk: 'Aggressive', sharpe: 2.41, drawdown: -8.2, allocation: 28, pnl: 34.7, volatility: 18.4, stake: 50000, status: 'active', score: 91 },
  { id: 'AGT-002', address: '0x70997970C51812dc3A010C7d01b50e0d17dc79C8', name: 'NeuralArb', strategy: 'Cross-DEX Arbitrage', risk: 'Balanced', sharpe: 1.87, drawdown: -4.1, allocation: 22, pnl: 21.3, volatility: 11.2, stake: 40000, status: 'active', score: 84 },
  { id: 'AGT-003', address: '0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC', name: 'QuantSigma', strategy: 'Mean Reversion', risk: 'Conservative', sharpe: 1.52, drawdown: -2.8, allocation: 18, pnl: 14.6, volatility: 7.8, stake: 35000, status: 'active', score: 78 },
  { id: 'AGT-004', address: '0x90F79bf6EB2c4f870365E785982E1f101E93b906', name: 'VoltexAI', strategy: 'Volatility Breakout', risk: 'Aggressive', sharpe: 3.12, drawdown: -14.5, allocation: 15, pnl: 52.1, volatility: 28.9, stake: 60000, status: 'active', score: 88 },
  { id: 'AGT-005', address: '0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65', name: 'DeltaHedge', strategy: 'Options Delta Neutral', risk: 'Balanced', sharpe: 1.23, drawdown: -5.9, allocation: 10, pnl: 9.8, volatility: 9.1, stake: 30000, status: 'probation', score: 62 },
  { id: 'AGT-006', address: '0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc', name: 'OmegaFlow', strategy: 'Liquidation Hunter', risk: 'Aggressive', sharpe: 2.78, drawdown: -11.2, allocation: 7, pnl: 41.3, volatility: 22.6, stake: 45000, status: 'active', score: 85 },
  { id: 'AGT-007', address: '0xBcd4042DE499D14e55001CcbB24a551F3b954096', name: 'StableYield', strategy: 'Stablecoin Yield Optimization', risk: 'Conservative', sharpe: 1.18, drawdown: -1.4, allocation: 12, pnl: 8.9, volatility: 4.2, stake: 28000, status: 'active', score: 72 },
  { id: 'AGT-008', address: '0x71bE63f3384f5fb98995898A86B02Fb2426c5788', name: 'FluxArb', strategy: 'Statistical Pairs Trading', risk: 'Balanced', sharpe: 2.05, drawdown: -6.3, allocation: 14, pnl: 27.4, volatility: 13.7, stake: 42000, status: 'active', score: 80 },
  { id: 'AGT-009', address: '0xdD2FD4581271e230360230F9337D5c0430Bf44C0', name: 'NovaSurge', strategy: 'High-Frequency Momentum Scalping', risk: 'Aggressive', sharpe: 3.44, drawdown: -17.8, allocation: 9, pnl: 61.2, volatility: 33.1, stake: 70000, status: 'active', score: 87 },
]

export const pools = [
  { id: 'conservative', name: 'Conservative', tvl: 4200000, apy: 12.4, agents: 3, volatilityCap: 8, color: '#10b981' },
  { id: 'balanced', name: 'Balanced', tvl: 8700000, apy: 24.7, agents: 5, volatilityCap: 18, color: '#3b82f6' },
  { id: 'aggressive', name: 'Aggressive', tvl: 12400000, apy: 47.2, agents: 6, volatilityCap: 35, color: '#a855f7' },
]

export const portfolioHistory = generateTimeSeries(90, 100000, 2000)
export const pnlHistory = generateTimeSeries(30, 0, 500)

export const allocationData = agents.map(a => ({ name: a.name, value: a.allocation }))

export const marketRegimes = [
  { time: '2026-01', regime: 'Bull', confidence: 87 },
  { time: '2026-02', regime: 'Sideways', confidence: 72 },
  { time: '2026-03', regime: 'Bear', confidence: 65 },
  { time: '2026-04', regime: 'Bull', confidence: 91 },
]

export const monteCarloData = Array.from({ length: 50 }, (_, i) => ({
  path: i,
  data: generateTimeSeries(30, 100000, 3000 + Math.random() * 2000)
}))

export const rollingVolatility = generateTimeSeries(60, 15, 2)
export const trendWave = generateTimeSeries(60, 50, 8)

export const proposals = [
  { id: 1, title: 'Increase η (learning rate) from 0.01 to 0.015', votes: { for: 68, against: 32 }, status: 'active', ends: '2026-04-05' },
  { id: 2, title: 'Reduce max drawdown threshold from 20% to 15%', votes: { for: 81, against: 19 }, status: 'passed', ends: '2026-03-28' },
  { id: 3, title: 'Add new Aggressive pool with 50% volatility cap', votes: { for: 44, against: 56 }, status: 'rejected', ends: '2026-03-20' },
]

export const smartContracts = [
  { id: 'SC-001', name: 'Capital Vault v2.1', address: '0x1a2b...3c4d', status: 'deployed', tvl: 25300000, audited: true },
  { id: 'SC-002', name: 'Allocation Engine v1.4', address: '0x5e6f...7a8b', status: 'deployed', tvl: 0, audited: true },
  { id: 'SC-003', name: 'Agent Registry v1.0', address: '0x9c0d...1e2f', status: 'deployed', tvl: 0, audited: false },
  { id: 'SC-004', name: 'Slashing Module v1.2', address: '0x3a4b...5c6d', status: 'deployed', tvl: 0, audited: true },
]
