"""
Governance API — persistent DAO with proposals, voting, quorum, and parameter execution.
State is stored in a JSON file so votes/proposals survive restarts.
"""
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

_STORE_PATH = Path(__file__).parent.parent / "governance_store.json"

_DEFAULT_PARAMS = {
    "eta":                    {"value": 0.01,  "label": "Learning Rate η",          "min": 0.001, "max": 0.05,  "step": 0.001, "unit": "",   "category": "allocation"},
    "slashing_threshold_bps": {"value": 2000,  "label": "Slashing Threshold (bps)", "min": 500,   "max": 5000,  "step": 100,   "unit": "bps","category": "risk"},
    "aggressive_vol_cap_bps": {"value": 3500,  "label": "Aggressive Vol Cap (bps)", "min": 1000,  "max": 6000,  "step": 100,   "unit": "bps","category": "risk"},
    "min_stake":              {"value": 10000, "label": "Min Agent Stake",           "min": 1000,  "max": 100000,"step": 1000,  "unit": "DAC","category": "agents"},
    "quorum_pct":             {"value": 20,    "label": "Quorum Threshold (%)",      "min": 5,     "max": 60,    "step": 1,     "unit": "%",  "category": "governance"},
    "proposal_duration_days": {"value": 5,     "label": "Proposal Duration (days)",  "min": 1,     "max": 14,    "step": 1,     "unit": "d",  "category": "governance"},
    "max_allocation_pct":     {"value": 35,    "label": "Max Single Agent Alloc (%)", "min": 5,    "max": 60,    "step": 1,     "unit": "%",  "category": "allocation"},
    "conservative_vol_cap_bps":{"value": 800,  "label": "Conservative Vol Cap (bps)","min": 200,   "max": 2000,  "step": 50,    "unit": "bps","category": "risk"},
    "balanced_vol_cap_bps":   {"value": 1800,  "label": "Balanced Vol Cap (bps)",    "min": 500,   "max": 3500,  "step": 100,   "unit": "bps","category": "risk"},
    "reputation_decay":       {"value": 0.95,  "label": "Reputation Decay Factor",   "min": 0.8,   "max": 1.0,   "step": 0.01,  "unit": "",   "category": "agents"},
    "slash_recovery_epochs":  {"value": 10,    "label": "Slash Recovery Epochs",     "min": 1,     "max": 50,    "step": 1,     "unit": "ep", "category": "agents"},
}

_DEFAULT_STORE = {
    "params": {k: v["value"] for k, v in _DEFAULT_PARAMS.items()},
    "proposals": [],
    "votes": [],
    "executed": [],
}

_SEED_PROPOSALS = [
    {
        "id": "prop-001",
        "title": "Increase learning rate η from 0.01 to 0.015",
        "description": "Higher η allows the allocation engine to adapt faster to regime changes. Backtests show +3.2% annualised return improvement in trending markets.",
        "category": "allocation",
        "param_name": "eta",
        "current_value": 0.01,
        "proposed_value": 0.015,
        "proposer": "0x1111111111111111111111111111111111111111",
        "votes_for": 1200,
        "votes_against": 800,
        "status": "active",
        "quorum_reached": False,
        "created_at": time.time() - 86400,
        "ends_at": time.time() + 172800,
    },
    {
        "id": "prop-002",
        "title": "Reduce slashing threshold from 20% to 15% drawdown",
        "description": "Tighter slashing protects the protocol from rogue agents. Agents with >15% drawdown will have 10% of stake slashed.",
        "category": "risk",
        "param_name": "slashing_threshold_bps",
        "current_value": 2000,
        "proposed_value": 1500,
        "proposer": "0x2222222222222222222222222222222222222222",
        "votes_for": 8100,
        "votes_against": 1900,
        "status": "passed",
        "quorum_reached": True,
        "created_at": time.time() - 7 * 86400,
        "ends_at": time.time() - 86400,
    },
    {
        "id": "prop-003",
        "title": "Raise aggressive pool vol cap from 35% to 40%",
        "description": "Allows aggressive agents more room to operate in high-volatility regimes. Risk: increased drawdown exposure.",
        "category": "risk",
        "param_name": "aggressive_vol_cap_bps",
        "current_value": 3500,
        "proposed_value": 4000,
        "proposer": "0x3333333333333333333333333333333333333333",
        "votes_for": 4500,
        "votes_against": 5500,
        "status": "rejected",
        "quorum_reached": True,
        "created_at": time.time() - 10 * 86400,
        "ends_at": time.time() - 5 * 86400,
    },
    {
        "id": "prop-004",
        "title": "Increase minimum agent stake to 15,000 DAC",
        "description": "Raising the stake floor improves agent skin-in-the-game and reduces low-quality registrations.",
        "category": "agents",
        "param_name": "min_stake",
        "current_value": 10000,
        "proposed_value": 15000,
        "proposer": "0x4444444444444444444444444444444444444444",
        "votes_for": 500,
        "votes_against": 300,
        "status": "active",
        "quorum_reached": False,
        "created_at": time.time() - 2 * 86400,
        "ends_at": time.time() + 3 * 86400,
    },
]

def _load_store() -> dict:
    if _STORE_PATH.exists():
        try:
            with open(_STORE_PATH) as f:
                store = json.load(f)

            for k, v in _DEFAULT_STORE.items():
                store.setdefault(k, v)
            return store
        except Exception:
            pass
    store = dict(_DEFAULT_STORE)
    store["proposals"] = list(_SEED_PROPOSALS)
    _save_store(store)
    return store

def _save_store(store: dict):
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_STORE_PATH, "w") as f:
        json.dump(store, f, indent=2)

def _resolve_proposals(store: dict):
    """Auto-close expired active proposals and execute passed ones.
    Also immediately executes if quorum + supermajority (>66%) is reached before deadline."""
    now = time.time()
    changed = False
    quorum_total = 10000

    for p in store["proposals"]:
        if p["status"] != "active":
            continue
        total_votes = p["votes_for"] + p["votes_against"]
        quorum_pct = store["params"].get("quorum_pct", 20)
        p["quorum_reached"] = (total_votes / quorum_total * 100) >= quorum_pct

        if p["quorum_reached"] and total_votes > 0:
            for_pct = p["votes_for"] / total_votes * 100
            if for_pct > 66:
                p["status"] = "passed"
                if p.get("param_name") and p.get("proposed_value") is not None:
                    store["params"][p["param_name"]] = p["proposed_value"]
                    if p["id"] not in store["executed"]:
                        store["executed"].append(p["id"])
                    _apply_live(p["param_name"], p["proposed_value"])
                changed = True
                continue
            elif (100 - for_pct) > 66:
                p["status"] = "rejected"
                changed = True
                continue

        if p["ends_at"] <= now:
            if p["quorum_reached"] and p["votes_for"] > p["votes_against"]:
                p["status"] = "passed"
                if p.get("param_name") and p.get("proposed_value") is not None:
                    store["params"][p["param_name"]] = p["proposed_value"]
                    if p["id"] not in store["executed"]:
                        store["executed"].append(p["id"])
                    _apply_live(p["param_name"], p["proposed_value"])
            else:
                p["status"] = "rejected" if p["quorum_reached"] else "expired"
            changed = True

    if changed:
        _save_store(store)

def _apply_live(key: str, value):
    """Push param change into the in-process singleton so agents pick it up immediately."""
    try:
        from core.protocol_params import protocol_params
        protocol_params.apply(key, value)
    except Exception as e:
        logger.warning(f"Failed to apply live param {key}={value}: {e}")

ADMIN_ADDRESS = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"

class ProposalCreate(BaseModel):
    title: str
    description: str
    category: str
    param_name: Optional[str] = None
    proposed_value: Optional[float] = None
    proposer: str = "0x0000000000000000000000000000000000000000"
    duration_days: Optional[int] = None

class VoteRequest(BaseModel):
    proposal_id: str
    voter: str
    support: bool
    weight: float = 100.0

class VetoRequest(BaseModel):
    admin_address: str
    reason: str = ""

@router.get("/proposals")
def list_proposals():
    store = _load_store()
    _resolve_proposals(store)
    proposals = store["proposals"]

    quorum_total = 10000
    quorum_pct = store["params"].get("quorum_pct", 20)
    result = []
    for p in reversed(proposals):
        total = p["votes_for"] + p["votes_against"]
        pct_for = round(p["votes_for"] / total * 100, 1) if total > 0 else 0
        pct_against = round(p["votes_against"] / total * 100, 1) if total > 0 else 0
        result.append({
            **p,
            "votes_for_pct": pct_for,
            "votes_against_pct": pct_against,
            "total_votes": total,
            "quorum_pct_needed": quorum_pct,
            "quorum_progress": round(total / quorum_total * 100, 1),
            "end_date": _fmt_ts(p["ends_at"]),
            "created_date": _fmt_ts(p["created_at"]),
            "param_meta": _DEFAULT_PARAMS.get(p.get("param_name", ""), {}),
        })
    return result

@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: str):
    store = _load_store()
    p = next((x for x in store["proposals"] if x["id"] == proposal_id), None)
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
    votes = [v for v in store["votes"] if v["proposal_id"] == proposal_id]
    return {**p, "vote_history": votes}

@router.post("/propose")
def create_proposal(data: ProposalCreate):
    store = _load_store()
    duration = data.duration_days or int(store["params"].get("proposal_duration_days", 5))
    current_val = None
    if data.param_name:
        current_val = store["params"].get(data.param_name)

    proposal = {
        "id": f"prop-{uuid.uuid4().hex[:8]}",
        "title": data.title,
        "description": data.description,
        "category": data.category,
        "param_name": data.param_name,
        "current_value": current_val,
        "proposed_value": data.proposed_value,
        "proposer": data.proposer,
        "votes_for": 0,
        "votes_against": 0,
        "status": "active",
        "quorum_reached": False,
        "created_at": time.time(),
        "ends_at": time.time() + duration * 86400,
    }
    store["proposals"].append(proposal)
    _save_store(store)
    return proposal

@router.post("/vote")
def cast_vote(data: VoteRequest):
    store = _load_store()
    proposal = next((p for p in store["proposals"] if p["id"] == data.proposal_id), None)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal["status"] != "active":
        raise HTTPException(status_code=400, detail="Proposal is not active")
    if time.time() > proposal["ends_at"]:
        raise HTTPException(status_code=400, detail="Voting period has ended")

    existing = next((v for v in store["votes"]
                     if v["proposal_id"] == data.proposal_id and v["voter"].lower() == data.voter.lower()), None)
    if existing:
        raise HTTPException(status_code=409, detail="Address has already voted on this proposal")

    vote_record = {
        "id": str(uuid.uuid4()),
        "proposal_id": data.proposal_id,
        "voter": data.voter,
        "support": data.support,
        "weight": data.weight,
        "ts": time.time(),
    }
    store["votes"].append(vote_record)

    if data.support:
        proposal["votes_for"] += data.weight
    else:
        proposal["votes_against"] += data.weight

    _resolve_proposals(store)
    _save_store(store)
    return {"message": "Vote recorded", "proposal": proposal}

@router.post("/proposals/{proposal_id}/veto")
def veto_proposal(proposal_id: str, data: VetoRequest):
    """Admin-only: veto any proposal regardless of vote outcome. Reverts param if already executed."""
    if data.admin_address.lower() != ADMIN_ADDRESS.lower():
        raise HTTPException(status_code=403, detail="Not authorized — admin only")

    store = _load_store()
    proposal = next((p for p in store["proposals"] if p["id"] == proposal_id), None)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal["status"] == "vetoed":
        raise HTTPException(status_code=400, detail="Already vetoed")

    prev_status = proposal["status"]
    proposal["status"] = "vetoed"
    proposal["veto_reason"] = data.reason
    proposal["vetoed_by"] = data.admin_address
    proposal["vetoed_at"] = time.time()

    if prev_status == "passed" and proposal.get("param_name") and proposal.get("current_value") is not None:
        store["params"][proposal["param_name"]] = proposal["current_value"]
        _apply_live(proposal["param_name"], proposal["current_value"])
        if proposal["id"] in store["executed"]:
            store["executed"].remove(proposal["id"])
        proposal["veto_reverted"] = True
        logger.info(f"[Veto] Reverted {proposal['param_name']} → {proposal['current_value']}")

    _save_store(store)
    return {"message": "Proposal vetoed", "proposal": proposal}

@router.get("/params")
def get_params():
    store = _load_store()
    result = {}
    for key, meta in _DEFAULT_PARAMS.items():
        result[key] = {
            **meta,
            "value": store["params"].get(key, meta["value"]),
        }
    return result

@router.get("/stats")
def get_stats():
    store = _load_store()
    proposals = store["proposals"]
    return {
        "total_proposals": len(proposals),
        "active": sum(1 for p in proposals if p["status"] == "active"),
        "passed": sum(1 for p in proposals if p["status"] == "passed"),
        "rejected": sum(1 for p in proposals if p["status"] == "rejected"),
        "expired": sum(1 for p in proposals if p["status"] == "expired"),
        "total_votes_cast": len(store["votes"]),
        "params_executed": len(store["executed"]),
    }

@router.get("/votes/{voter_address}")
def get_voter_history(voter_address: str):
    store = _load_store()
    votes = [v for v in store["votes"] if v["voter"].lower() == voter_address.lower()]
    return votes

def _fmt_ts(ts: float) -> str:
    import datetime
    return datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M UTC")
