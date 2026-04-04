import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str
    graph_api_key: str
    news_api_key: str
    apify_api_token: str
    apify_cryptopanic_actor_id: str
    gdelt_api_url: str
    alchemy_api_key: str
    alchemy_app_id: str
    alchemy_eth_mainnet_url: str
    alchemy_eth_sepolia_url: str
    alchemy_eth_hoodi_url: str
    alchemy_eth_mainnet_beacon_url: str
    alchemy_eth_sepolia_beacon_url: str
    alchemy_eth_hoodi_beacon_url: str
    alchemy_zksync_mainnet_url: str
    alchemy_zksync_sepolia_url: str
    alchemy_solana_mainnet_url: str
    alchemy_solana_devnet_url: str
    supabase_url: str
    supabase_publishable_key: str
    supabase_secret_key: str
    alpha_vantage_api_key: str
    ws_market_source: str
    ws_normalized_stream_enabled: bool
    groq_api_key: str
    groq_model: str
    groq_requests_per_minute: int
    groq_requests_per_day: int
    groq_tokens_per_minute: int
    groq_tokens_per_day: int

def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()

def _bool_env(name: str, default: str = "false") -> bool:
    return _env(name, default).lower() in {"1", "true", "yes", "on"}

def get_settings() -> Settings:
    alchemy_api_key = _env("ALCHEMY_API_KEY")
    return Settings(
        database_url=_env("DATABASE_URL", "sqlite:///./dacap.db"),
        redis_url=_env("REDIS_URL", "redis://localhost:6379"),
        graph_api_key=_env("GRAPH_API_KEY"),
        news_api_key=_env("NEWS_API_KEY"),
        apify_api_token=_env("APIFY_API_TOKEN"),
        apify_cryptopanic_actor_id=_env("APIFY_CRYPTOPANIC_ACTOR_ID", "zZGeHO6iOODDq5MMd"),
        gdelt_api_url=_env("GDELT_API_URL", "https://api.gdeltproject.org/api/v2/doc/doc?query=bitcoin&mode=ArtList&maxrecords=10&format=json"),
        alchemy_api_key=alchemy_api_key,
        alchemy_app_id=_env("ALCHEMY_APP_ID"),
        alchemy_eth_mainnet_url=_env("ALCHEMY_ETH_MAINNET_URL", f"https://eth-mainnet.g.alchemy.com/v2/{alchemy_api_key}" if alchemy_api_key else ""),
        alchemy_eth_sepolia_url=_env("ALCHEMY_ETH_SEPOLIA_URL", f"https://eth-sepolia.g.alchemy.com/v2/{alchemy_api_key}" if alchemy_api_key else ""),
        alchemy_eth_hoodi_url=_env("ALCHEMY_ETH_HOODI_URL", f"https://eth-hoodi.g.alchemy.com/v2/{alchemy_api_key}" if alchemy_api_key else ""),
        alchemy_eth_mainnet_beacon_url=_env("ALCHEMY_ETH_MAINNET_BEACON_URL", f"https://eth-mainnetbeacon.g.alchemy.com/v2/{alchemy_api_key}" if alchemy_api_key else ""),
        alchemy_eth_sepolia_beacon_url=_env("ALCHEMY_ETH_SEPOLIA_BEACON_URL", f"https://eth-sepoliabeacon.g.alchemy.com/v2/{alchemy_api_key}" if alchemy_api_key else ""),
        alchemy_eth_hoodi_beacon_url=_env("ALCHEMY_ETH_HOODI_BEACON_URL", f"https://eth-hoodibeacon.g.alchemy.com/v2/{alchemy_api_key}" if alchemy_api_key else ""),
        alchemy_zksync_mainnet_url=_env("ALCHEMY_ZKSYNC_MAINNET_URL", f"https://zksync-mainnet.g.alchemy.com/v2/{alchemy_api_key}" if alchemy_api_key else ""),
        alchemy_zksync_sepolia_url=_env("ALCHEMY_ZKSYNC_SEPOLIA_URL", f"https://zksync-sepolia.g.alchemy.com/v2/{alchemy_api_key}" if alchemy_api_key else ""),
        alchemy_solana_mainnet_url=_env("ALCHEMY_SOLANA_MAINNET_URL", f"https://solana-mainnet.g.alchemy.com/v2/{alchemy_api_key}" if alchemy_api_key else ""),
        alchemy_solana_devnet_url=_env("ALCHEMY_SOLANA_DEVNET_URL", f"https://solana-devnet.g.alchemy.com/v2/{alchemy_api_key}" if alchemy_api_key else ""),
        supabase_url=_env("SUPABASE_URL"),
        supabase_publishable_key=_env("SUPABASE_PUBLISHABLE_KEY"),
        supabase_secret_key=_env("SUPABASE_SECRET_KEY"),
        alpha_vantage_api_key=_env("ALPHA_VANTAGE_API_KEY"),
        ws_market_source=_env("WS_MARKET_SOURCE", "simulated"),
        ws_normalized_stream_enabled=_bool_env("WS_NORMALIZED_STREAM_ENABLED", "true"),
        groq_api_key=_env("GROQ_API_KEY"),
        groq_model=_env("GROQ_MODEL", "llama-3.1-8b-instant"),
        groq_requests_per_minute=int(_env("GROQ_REQUESTS_PER_MINUTE", "30") or "30"),
        groq_requests_per_day=int(_env("GROQ_REQUESTS_PER_DAY", "14400") or "14400"),
        groq_tokens_per_minute=int(_env("GROQ_TOKENS_PER_MINUTE", "6000") or "6000"),
        groq_tokens_per_day=int(_env("GROQ_TOKENS_PER_DAY", "100000") or "100000"),
    )

settings = get_settings()
