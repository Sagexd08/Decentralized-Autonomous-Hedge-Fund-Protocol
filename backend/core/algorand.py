"""
Algorand client — wraps py-algorand-sdk (algod REST API).

The algod daemon is the same backend that `goal` CLI talks to.
Start a node with:
    goal node start -d $ALGORAND_DATA
Then point ALGORAND_ALGOD_URL / ALGORAND_API_TOKEN at the local daemon.

For testnet without a local node, use a third-party algod endpoint and
supply its token via ALGORAND_API_TOKEN.
"""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import algosdk
    from algosdk.v2client import algod, indexer
    from algosdk import transaction, mnemonic, account as algo_account
    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False
    algosdk = None  # type: ignore


class AlgorandClient:
    """
    Thin wrapper around algosdk.v2client.algod.AlgodClient.

    Usage
    -----
    client = AlgorandClient.from_settings()
    if client.is_connected():
        txid = client.send_payment(sender_sk, receiver_address, amount_microalgos)
    """

    def __init__(self, algod_url: str, api_token: str, indexer_url: str = ""):
        self._algod_url = algod_url
        self._api_token = api_token
        self._indexer_url = indexer_url
        self._algod: Optional[object] = None
        self._indexer: Optional[object] = None

        if not _SDK_AVAILABLE:
            logger.warning(
                "py-algorand-sdk not installed. Run: pip install py-algorand-sdk"
            )
            return

        headers = {"X-Algo-API-Token": api_token} if api_token else {}
        try:
            self._algod = algod.AlgodClient(api_token, algod_url, headers)
            if indexer_url:
                self._indexer = indexer.IndexerClient(api_token, indexer_url, headers)
        except Exception as exc:
            logger.warning("AlgorandClient init failed: %s", exc)

    @classmethod
    def from_settings(cls) -> "AlgorandClient":
        from core.settings import settings

        data_dir = settings.algorand_data_dir
        cli_algod_url = ""
        cli_api_token = ""
        if data_dir:
            cli_algod_url, cli_api_token = _read_goal_algod_config(data_dir)

        return cls(
            algod_url=settings.algorand_algod_url or cli_algod_url,
            api_token=settings.algorand_api_token or cli_api_token,
            indexer_url=settings.algorand_indexer_url,
        )

    def is_connected(self) -> bool:
        if self._algod is None:
            return False
        try:
            self._algod.status()
            return True
        except Exception:
            return False

    def is_indexer_connected(self) -> bool:
        if self._indexer is None:
            return False
        try:
            self._indexer.health()
            return True
        except Exception:
            return False

    def connectivity_status(self) -> dict:
        """Return a lightweight connectivity snapshot for algod/indexer."""
        status = {
            "sdk_available": _SDK_AVAILABLE,
            "algod": {
                "configured": bool(self._algod_url),
                "reachable": False,
                "error": None,
            },
            "indexer": {
                "configured": bool(self._indexer_url),
                "reachable": False,
                "error": None,
            },
        }

        if not _SDK_AVAILABLE:
            status["algod"]["error"] = "py-algorand-sdk not installed"
            if status["indexer"]["configured"]:
                status["indexer"]["error"] = "py-algorand-sdk not installed"
            status["healthy"] = False
            return status

        if self._algod is None:
            status["algod"]["error"] = "algod client not initialised"
        else:
            try:
                self._algod.status()
                status["algod"]["reachable"] = True
            except Exception as exc:
                status["algod"]["error"] = str(exc)

        if not status["indexer"]["configured"]:
            status["indexer"]["error"] = "indexer URL not configured"
        elif self._indexer is None:
            status["indexer"]["error"] = "indexer client not initialised"
        else:
            try:
                self._indexer.health()
                status["indexer"]["reachable"] = True
            except Exception as exc:
                status["indexer"]["error"] = str(exc)

        status["healthy"] = status["algod"]["reachable"] and (
            not status["indexer"]["configured"] or status["indexer"]["reachable"]
        )
        return status

    def suggested_params(self):
        """Fetch network-suggested transaction parameters from algod."""
        return self._algod.suggested_params()

    def send_payment(
        self,
        sender_private_key: str,
        receiver: str,
        amount_microalgos: int,
        note: bytes = b"",
    ) -> str:
        """
        Sign and submit a payment transaction.
        Returns the transaction ID (txid).

        Parameters
        ----------
        sender_private_key : base64-encoded 64-byte private key (algosdk format)
        receiver          : Algorand address of the recipient
        amount_microalgos : amount in microALGOs (1 ALGO = 1_000_000 microALGOs)
        note              : optional bytes note field (max 1 KB)
        """
        if self._algod is None:
            raise RuntimeError("algod client not initialised")

        sender_address = algo_account.address_from_private_key(sender_private_key)
        params = self.suggested_params()

        txn = transaction.PaymentTxn(
            sender=sender_address,
            sp=params,
            receiver=receiver,
            amt=amount_microalgos,
            note=note,
        )
        signed = txn.sign(sender_private_key)
        txid = self._algod.send_transaction(signed)
        logger.info("Algorand payment sent: txid=%s  %s → %s  %d µALGO",
                    txid, sender_address, receiver, amount_microalgos)
        return txid

    def call_app(
        self,
        sender_private_key: str,
        app_id: int,
        app_args: list,
    ) -> str:
        """
        Submit a NoOp application call (equivalent to `goal app call`).
        Returns the transaction ID.

        Parameters
        ----------
        sender_private_key : base64-encoded private key
        app_id             : Algorand application ID (integer)
        app_args           : list of bytes arguments passed to the ABI method
        """
        if self._algod is None:
            raise RuntimeError("algod client not initialised")

        sender_address = algo_account.address_from_private_key(sender_private_key)
        params = self.suggested_params()

        txn = transaction.ApplicationNoOpTxn(
            sender=sender_address,
            sp=params,
            index=app_id,
            app_args=app_args,
        )
        signed = txn.sign(sender_private_key)
        txid = self._algod.send_transaction(signed)
        logger.info("Algorand app call: txid=%s  app=%d  sender=%s",
                    txid, app_id, sender_address)
        return txid

    def wait_for_confirmation(self, txid: str, rounds: int = 4) -> dict:
        """Block until txid is confirmed (or raises on timeout)."""
        return transaction.wait_for_confirmation(self._algod, txid, rounds)

    def account_info(self, address: str) -> dict:
        """Return account info dict from algod (balance, assets, etc.)."""
        return self._algod.account_info(address)

    def app_info(self, app_id: int) -> dict:
        """Return application info from algod."""
        return self._algod.application_info(app_id)

    @staticmethod
    def private_key_from_mnemonic(mnemonic_phrase: str) -> str:
        """Convert a 25-word mnemonic to a private key (algosdk format)."""
        return mnemonic.to_private_key(mnemonic_phrase)

    @staticmethod
    def generate_account() -> tuple[str, str]:
        """Generate a new Algorand keypair. Returns (private_key, address)."""
        private_key, address = algo_account.generate_account()
        return private_key, address


# Module-level singleton — created lazily on first import
_client: Optional[AlgorandClient] = None


def get_algorand_client() -> AlgorandClient:
    global _client
    if _client is None:
        _client = AlgorandClient.from_settings()
    return _client


def _read_goal_algod_config(data_dir: str) -> tuple[str, str]:
    """
    Read algod.net and algod.token generated by `goal`.
    Returns (algod_url, api_token) where values may be empty strings if unavailable.
    """
    base = Path(data_dir).expanduser()
    net_file = base / "algod.net"
    token_file = base / "algod.token"

    host_port = _safe_read_file(net_file)
    token = _safe_read_file(token_file)

    url = ""
    if host_port:
        url = host_port if host_port.startswith(("http://", "https://")) else f"http://{host_port}"
    return url, token


def _safe_read_file(path: Path) -> str:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""
