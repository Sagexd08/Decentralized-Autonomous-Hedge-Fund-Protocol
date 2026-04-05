"""
Simple trade diagnostic - ASCII only, no Unicode issues.
Investigates why only AGT-001 trades while others remain idle.
Uses real ML model and price engine.
"""
import asyncio
import json
import time
import httpx
import websockets
from collections import deque

TARGET_AGENTS = ["AGT-001", "AGT-002", "AGT-003"]
WS_URL = "ws://localhost:8000/ws/trading"
API_URL = "http://localhost:8000"

print("=" * 60)
print("TRADE DIAGNOSTIC - Real ML Model + Price Engine")
print("=" * 60)

async def diagnose():
    """Run diagnostic test."""
    trade_log = []
    
    # Connect to WebSocket first
    print("\n[1] Connecting to WebSocket...")
    try:
        async with websockets.connect(WS_URL, ping_interval=20) as ws:
            print("  OK: Connected to", WS_URL)
            
            async with httpx.AsyncClient() as client:
                # Fire force-trades for all agents rapidly
                print("\n[2] Firing force-trades...")
                for agent in TARGET_AGENTS:
                    try:
                        r = await client.post(
                            f"{API_URL}/api/agents/{agent}/force-trade",
                            timeout=10
                        )
                        status = "OK" if r.status_code == 200 else f"FAIL:{r.status_code}"
                        print(f"  {agent}: {status}")
                    except Exception as exc:
                        print(f"  {agent}: ERROR - {exc}")
                    await asyncio.sleep(0.5)
                
                # Listen for 30 seconds
                print("\n[3] Listening for trade events (30s)...")
                start = time.time()
                
                while time.time() - start < 30:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        msg = json.loads(raw)
                        
                        if msg.get("type") == "swap":
                            agent = msg.get("agent", "")
                            if agent in TARGET_AGENTS:
                                trade_log.append(msg)
                                elapsed = time.time() - start
                                decision = msg.get("decision", "?")
                                token = msg.get("token", "?")
                                bps = msg.get("returnBps", 0)
                                count = sum(1 for t in trade_log if t.get("agent") == agent)
                                
                                print(f"  [{elapsed:5.1f}s] {agent} {decision} {token} bps={bps:+d} #{count}")
                    except asyncio.TimeoutError:
                        pass
    except Exception as exc:
        print(f"  WebSocket error: {exc}")
    
    # Summary
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    for agent in TARGET_AGENTS:
        count = sum(1 for t in trade_log if t.get("agent") == agent)
        buys = sum(1 for t in trade_log if t.get("agent") == agent and t.get("decision") == "BUY")
        sells = sum(1 for t in trade_log if t.get("agent") == agent and t.get("decision") == "SELL")
        status = "TRADING" if count > 0 else "IDLE"
        print(f"  {agent}: {count} trades ({buys} BUY / {sells} SELL) - {status}")
    
    total = len(trade_log)
    print(f"\n  Total: {total} trades")
    
    if total == 0:
        print("\n  WARNING: No trades detected!")
        print("  Possible causes:")
        print("    - ML model producing only HOLD decisions")
        print("    - Price engine in strongly bearish regime")
        print("    - WebSocket broadcast not working")
    elif sum(1 for t in trade_log if t.get("agent") == "AGT-001") > 0 and \
         sum(1 for t in trade_log if t.get("agent") == "AGT-002") == 0 and \
         sum(1 for t in trade_log if t.get("agent") == "AGT-003") == 0:
        print("\n  ALERT: Only AGT-001 is trading!")
        print("  This suggests a race condition or state issue in the trading engine.")
    else:
        print("\n  OK: All agents are trading")
    
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(diagnose())
