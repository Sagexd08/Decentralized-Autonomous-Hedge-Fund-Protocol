"""
The market data layer — IRIS_BUILD_PROMPT v2.0 sections 0c and 13, Phase 13.

Real observations of real venues, written into `market_events` under the
`LIVE` label with the venue that said so recorded alongside. Everything in
here is public, unauthenticated market data: there are no API keys in this
package and none are required, which is deliberate — section 0 forbids
credentials in source, and a market data layer that needs a secret to run is a
market data layer that will be run with the secret checked in.
"""

from agents.market.providers import (  # noqa: F401
    ASSETS,
    Candle,
    MarketDataError,
    Provider,
    Quote,
    binance,
    coinbase,
    default_provider,
    kraken,
    provider_by_name,
    providers_for,
)
