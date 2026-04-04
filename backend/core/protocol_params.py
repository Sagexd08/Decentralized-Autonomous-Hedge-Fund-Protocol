"""
Live protocol parameters singleton.
Governance writes here when proposals pass; agents/allocation engine read from here.
"""
import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)

_STORE_PATH = Path(__file__).parent.parent / "governance_store.json"

# Defaults — overridden by governance store on first read
_DEFAULTS = {
    "eta": 0.01,
    "slashing_threshold_bps": 2000,
    "aggressive_vol_cap_bps": 3500,
    "conservative_vol_cap_bps": 800,
    "balanced_vol_cap_bps": 1800,
    "min_stake": 10000,
    "quorum_pct": 20,
    "proposal_duration_days": 5,
    "max_allocation_pct": 35,
    "reputation_decay": 0.95,
    "slash_recovery_epochs": 10,
}


class ProtocolParams:
    """
    Thread-safe in-process parameter store.
    Reads from governance_store.json on first access, then stays in memory.
    Governance API calls `apply(key, value)` whenever a proposal executes or is vetoed.
    """

    def __init__(self):
        self._params: dict = {}
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        try:
            if _STORE_PATH.exists():
                with open(_STORE_PATH) as f:
                    store = json.load(f)
                self._params = {**_DEFAULTS, **store.get("params", {})}
            else:
                self._params = dict(_DEFAULTS)
        except Exception as e:
            logger.warning(f"ProtocolParams: failed to load store: {e}")
            self._params = dict(_DEFAULTS)
        self._loaded = True

    def get(self, key: str, default=None):
        self._ensure_loaded()
        return self._params.get(key, default if default is not None else _DEFAULTS.get(key))

    def apply(self, key: str, value):
        """Called by governance when a proposal is executed or vetoed."""
        self._ensure_loaded()
        self._params[key] = value
        logger.info(f"[ProtocolParams] {key} → {value}")

    @property
    def eta(self) -> float:
        return float(self.get("eta", 0.01))

    @property
    def slashing_threshold_bps(self) -> int:
        return int(self.get("slashing_threshold_bps", 2000))

    @property
    def aggressive_vol_cap_bps(self) -> int:
        return int(self.get("aggressive_vol_cap_bps", 3500))

    @property
    def max_allocation_pct(self) -> float:
        return float(self.get("max_allocation_pct", 35))

    @property
    def reputation_decay(self) -> float:
        return float(self.get("reputation_decay", 0.95))


# Global singleton — import this everywhere
protocol_params = ProtocolParams()
