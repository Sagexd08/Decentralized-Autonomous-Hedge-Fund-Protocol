# programs/iris

Anchor workspace for the IRIS Solana programs (v2 section 4):
agent_registry, capital_vault, performance_engine, risk_engine, governance.

The four programs that exist today still live as standalone Anchor workspaces
under contracts/rust/solana/. Consolidating them into this single workspace,
and adding performance_engine, risk_engine and governance, is **Phase 2** work
and deliberately out of Phase 1 scope.

Phase 2's gate is the agent-cannot-withdraw-vault test — the highest-priority
security test in the repo (v2 section 5).
