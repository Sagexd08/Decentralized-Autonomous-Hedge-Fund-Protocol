"""
Live trade test — watches /ws/trading for 60 seconds and prints every
trade event from AGT-001, AGT-002, AGT-003.
Also polls /api/prices/current every 10s to show live prices.
"""
import asyncio
import json
import time
import httpx
import websockets

TARGET_AGENTS = {"AGT-001", "AGT-002", "AGT-003"}
WS_URL  = "ws://localhost:8000/ws/trading"
API_URL = "http://localhost:8000"
DURATION = 90  # seconds to watch

trade_counts = {a: 0 for a in TARGET_AGENTS}
slash_events = []
mwu_updates  = []

RESET  = "\033[0m"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"


def color_decision(d: str) -> str:
    if d == "BUY":  return f"{GREEN}{BOLD}BUY {RESET}"
    if d == "SELL": return f"{RED}{BOLD}SELL{RESET}"
    return f"{YELLOW}HOLD{RESET}"


async def print_prices():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/api/prices/current", timeout=5)
        prices = r.json()
    print(f"\n{CYAN}{'─'*60}{RESET}")
    print(f"{CYAN}  LIVE PRICES{RESET}")
    for sym, info in prices.items():
        chg = info['change_pct']
        arrow = "▲" if chg >= 0 else "▼"
        col = GREEN if chg >= 0 else RED
        print(f"  {sym:<6}  ${info['price']:>12,.4f}  {col}{arrow} {chg:+.3f}%{RESET}")
    print(f"{CYAN}{'─'*60}{RESET}\n")


async def watch_trades():
    start = time.time()
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  DACAP LIVE TRADE TEST — watching {', '.join(sorted(TARGET_AGENTS))}{RESET}")
    print(f"{BOLD}  Duration: {DURATION}s   WebSocket: {WS_URL}{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")

    await print_prices()
    last_price_print = time.time()

    async with websockets.connect(WS_URL, ping_interval=20) as ws:
        print(f"{GREEN}✓ WebSocket connected{RESET}\n")
        while time.time() - start < DURATION:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=12.0)
                msg = json.loads(raw)
                mtype = msg.get("type", "swap")
                agent = msg.get("agent", "")

                # ── trade event ──────────────────────────────────────────
                if mtype == "swap" and agent in TARGET_AGENTS:
                    trade_counts[agent] += 1
                    elapsed = time.time() - start
                    decision = msg.get("decision", "?")
                    token    = msg.get("token", "?")
                    bps      = msg.get("returnBps", 0)
                    chains   = msg.get("chains", {})
                    stellar  = chains.get("stellar") or "—"
                    solana   = chains.get("solana")  or "—"
                    print(
                        f"[{elapsed:5.1f}s] {BOLD}{agent}{RESET}  "
                        f"{color_decision(decision)}  "
                        f"{token:<5}  bps={bps:+5d}  "
                        f"stellar={stellar}  solana={solana}  "
                        f"(trade #{trade_counts[agent]})"
                    )

                # ── slash event ───────────────────────────────────────────
                elif mtype == "slash_event":
                    slash_events.append(msg)
                    elapsed = time.time() - start
                    print(
                        f"\n{RED}{BOLD}[{elapsed:5.1f}s] ⚡ SLASH EVENT{RESET}  "
                        f"agent={msg.get('agent_id')}  "
                        f"drawdown={msg.get('drawdown_bps')}bps  "
                        f"slash={msg.get('slash_bps')}bps\n"
                    )

                # ── MWU weight update ─────────────────────────────────────
                elif mtype == "mwu_update":
                    mwu_updates.append(msg)
                    elapsed = time.time() - start
                    weights = msg.get("weights", {})
                    relevant = {k: round(v, 4) for k, v in weights.items() if k in TARGET_AGENTS}
                    if relevant:
                        print(
                            f"\n{CYAN}[{elapsed:5.1f}s] ⚖  MWU UPDATE{RESET}  "
                            f"weights={relevant}\n"
                        )

                # ── TVL change ────────────────────────────────────────────
                elif mtype == "tvl_change":
                    elapsed = time.time() - start
                    print(
                        f"[{elapsed:5.1f}s] {YELLOW}TVL change{RESET}  "
                        f"stellar={msg.get('stellar_tvl',0):,}  "
                        f"solana={msg.get('solana_tvl',0):,}"
                    )

                # refresh prices every 20s
                if time.time() - last_price_print > 20:
                    await print_prices()
                    last_price_print = time.time()

            except asyncio.TimeoutError:
                elapsed = time.time() - start
                print(f"[{elapsed:5.1f}s] … waiting for trades")
            except websockets.exceptions.ConnectionClosed:
                print(f"{RED}WebSocket closed{RESET}")
                break

    # ── summary ───────────────────────────────────────────────────────────
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  TEST SUMMARY{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    total = sum(trade_counts.values())
    for agent, count in sorted(trade_counts.items()):
        bar = "█" * count
        print(f"  {agent}  {count:3d} trades  {GREEN}{bar}{RESET}")
    print(f"\n  Total trades : {total}")
    print(f"  Slash events : {len(slash_events)}")
    print(f"  MWU updates  : {len(mwu_updates)}")

    # final portfolio snapshot
    print(f"\n{BOLD}  FINAL PORTFOLIO SNAPSHOT{RESET}")
    async with httpx.AsyncClient() as client:
        for agent in sorted(TARGET_AGENTS):
            r = await client.get(f"{API_URL}/api/agents/{agent}/portfolio", timeout=8)
            d = r.json()
            print(
                f"  {agent}  active={d['trading_active']}  "
                f"weight={d['allocation_weight']:.4f}  "
                f"solana_score={d['solana_score']}"
            )
    print(f"{BOLD}{'='*60}{RESET}\n")


if __name__ == "__main__":
    asyncio.run(watch_trades())
