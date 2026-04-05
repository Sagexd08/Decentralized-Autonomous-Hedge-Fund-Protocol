"""
Live trade test — watches /ws/trading for 90 seconds and prints every
trade event from AGT-001, AGT-002, AGT-003.
Fires force-trade cycles at t=5s, t=15s, t=25s to guarantee visible output.
"""
import asyncio
import json
import time
import httpx
import websockets

TARGET_AGENTS = ["AGT-001", "AGT-002", "AGT-003"]
WS_URL  = "ws://localhost:8000/ws/trading"
API_URL = "http://localhost:8000"
DURATION = 90

trade_log    = []
slash_events = []
mwu_updates  = []

RESET  = "\033[0m"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"


def color_decision(d: str) -> str:
    if d == "BUY":  return f"{GREEN}{BOLD} BUY {RESET}"
    if d == "SELL": return f"{RED}{BOLD}SELL {RESET}"
    return f"{YELLOW} HOLD{RESET}"


async def get_prices(client: httpx.AsyncClient) -> dict:
    r = await client.get(f"{API_URL}/api/prices/current", timeout=5)
    return r.json()


async def print_prices(client: httpx.AsyncClient):
    prices = await get_prices(client)
    print(f"\n{CYAN}{'─'*62}{RESET}")
    print(f"{CYAN}  LIVE PRICES{RESET}")
    for sym, info in prices.items():
        chg = info['change_pct']
        arrow = "▲" if chg >= 0 else "▼"
        col = GREEN if chg >= 0 else RED
        print(f"  {sym:<6}  ${info['price']:>12,.4f}  {col}{arrow} {chg:+.4f}%{RESET}")
    print(f"{CYAN}{'─'*62}{RESET}\n")


async def fire_force_trades(client: httpx.AsyncClient, label: str):
    """Trigger one forced trade cycle per agent."""
    print(f"{DIM}  [{label}] Firing force-trade cycles...{RESET}")
    for agent in TARGET_AGENTS:
        try:
            r = await client.post(
                f"{API_URL}/api/agents/{agent}/force-trade", timeout=10
            )
            print(f"{DIM}  force-trade {agent} → {r.json().get('status')}{RESET}")
        except Exception as exc:
            print(f"{DIM}  force-trade {agent} failed: {exc}{RESET}")
    print()


async def watch_trades():
    start = time.time()
    print(f"\n{BOLD}{'='*62}{RESET}")
    print(f"{BOLD}  DACAP LIVE TRADE TEST{RESET}")
    print(f"{BOLD}  Agents: {', '.join(TARGET_AGENTS)}{RESET}")
    print(f"{BOLD}  Duration: {DURATION}s  |  WS: {WS_URL}{RESET}")
    print(f"{BOLD}{'='*62}{RESET}\n")

    async with httpx.AsyncClient() as client:
        await print_prices(client)
        last_price_print = time.time()

        # Schedule force-trade injections
        force_trade_times = {5, 15, 25, 45, 65}
        fired_at = set()

        async with websockets.connect(WS_URL, ping_interval=20) as ws:
            print(f"{GREEN}✓ WebSocket connected to {WS_URL}{RESET}\n")

            while time.time() - start < DURATION:
                elapsed = time.time() - start

                # Fire force-trades at scheduled times
                for t in force_trade_times:
                    if elapsed >= t and t not in fired_at:
                        fired_at.add(t)
                        await fire_force_trades(client, f"t={t:.0f}s")

                # Refresh prices every 25s
                if time.time() - last_price_print > 25:
                    await print_prices(client)
                    last_price_print = time.time()

                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
                    msg = json.loads(raw)
                    mtype = msg.get("type", "swap")
                    agent = msg.get("agent", "")

                    # ── trade event ───────────────────────────────────────
                    if mtype == "swap" and agent in TARGET_AGENTS:
                        trade_log.append(msg)
                        decision = msg.get("decision", "?")
                        token    = msg.get("token", "?")
                        bps      = msg.get("returnBps", 0)
                        chains   = msg.get("chains", {})
                        stellar  = (chains.get("stellar") or "—")[:12]
                        solana   = (chains.get("solana")  or "—")[:12]
                        count    = sum(1 for t in trade_log if t.get("agent") == agent)
                        print(
                            f"[{elapsed:5.1f}s] {BOLD}{agent}{RESET}  "
                            f"{color_decision(decision)}  "
                            f"{token:<5}  bps={bps:+6d}  "
                            f"stellar={stellar}  solana={solana}  "
                            f"#{count}"
                        )

                    # ── slash event ───────────────────────────────────────
                    elif mtype == "slash_event":
                        slash_events.append(msg)
                        print(
                            f"\n{RED}{BOLD}[{elapsed:5.1f}s] ⚡ SLASH  "
                            f"agent={msg.get('agent_id')}  "
                            f"drawdown={msg.get('drawdown_bps')}bps  "
                            f"slash={msg.get('slash_bps')}bps{RESET}\n"
                        )

                    # ── MWU update ────────────────────────────────────────
                    elif mtype == "mwu_update":
                        mwu_updates.append(msg)
                        weights = msg.get("weights", {})
                        relevant = {k: round(v, 4) for k, v in weights.items()
                                    if k in TARGET_AGENTS}
                        if relevant:
                            print(
                                f"[{elapsed:5.1f}s] {CYAN}⚖  MWU  "
                                f"weights={relevant}{RESET}"
                            )

                    # ── TVL change ────────────────────────────────────────
                    elif mtype == "tvl_change":
                        print(
                            f"[{elapsed:5.1f}s] {YELLOW}TVL  "
                            f"stellar={msg.get('stellar_tvl',0):,}  "
                            f"solana={msg.get('solana_tvl',0):,}{RESET}"
                        )

                except asyncio.TimeoutError:
                    pass
                except websockets.exceptions.ConnectionClosed:
                    print(f"{RED}WebSocket closed — reconnecting...{RESET}")
                    break

    # ── summary ───────────────────────────────────────────────────────────
    print(f"\n{BOLD}{'='*62}{RESET}")
    print(f"{BOLD}  TEST SUMMARY{RESET}")
    print(f"{BOLD}{'='*62}{RESET}")

    for agent in TARGET_AGENTS:
        count = sum(1 for t in trade_log if t.get("agent") == agent)
        buys  = sum(1 for t in trade_log if t.get("agent") == agent and t.get("decision") == "BUY")
        sells = sum(1 for t in trade_log if t.get("agent") == agent and t.get("decision") == "SELL")
        bar   = f"{GREEN}{'B'*buys}{RESET}{RED}{'S'*sells}{RESET}"
        print(f"  {agent}  {count:3d} trades  ({buys} BUY / {sells} SELL)  {bar}")

    total = len(trade_log)
    print(f"\n  Total trades : {BOLD}{total}{RESET}")
    print(f"  Slash events : {len(slash_events)}")
    print(f"  MWU updates  : {len(mwu_updates)}")

    # Final portfolio snapshot
    print(f"\n{BOLD}  FINAL PORTFOLIO SNAPSHOT{RESET}")
    async with httpx.AsyncClient() as client:
        for agent in TARGET_AGENTS:
            r = await client.get(f"{API_URL}/api/agents/{agent}/portfolio", timeout=8)
            d = r.json()
            print(
                f"  {agent}  active={d['trading_active']}  "
                f"weight={d['allocation_weight']:.4f}  "
                f"solana_score={d['solana_score']}  "
                f"solana_slot=live"
            )

    # Show last 5 trades
    if trade_log:
        print(f"\n{BOLD}  LAST {min(5,len(trade_log))} TRADES{RESET}")
        for t in trade_log[-5:]:
            print(
                f"  {t.get('agent')}  {t.get('decision')}  "
                f"{t.get('token')}  bps={t.get('returnBps',0):+d}  "
                f"ts={t.get('timestamp')}"
            )

    print(f"{BOLD}{'='*62}{RESET}\n")


if __name__ == "__main__":
    asyncio.run(watch_trades())
