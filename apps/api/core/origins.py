"""
Which browsers may call the protocol API.

Lives here rather than inline in `main.py` so it can be tested without
importing the app — `main` pulls in torch, the Solana client and the market
feed, none of which have anything to say about CORS.

The bug this exists to prevent is specific and was live in production: the
origin list was the six localhost addresses that `docker compose up` serves
from, so every browser request from the deployed web app was rejected. Two
properties make that failure unusually hard to read from the outside:

  * it happens in the *browser*, after the API has already answered, so the
    access log shows ordinary 200s and there is nothing to find server-side;
  * server-rendered fetches are unaffected, because CORS is a browser rule and
    binds nothing else — so the §0c provenance banner, rendered on the server,
    filled in correctly on the very page whose client panels were all showing
    "Failed to fetch".

Wildcards are not an option even setting security aside: the API sends
credentials, and `Access-Control-Allow-Origin: *` is invalid in a credentialed
response — browsers reject the pair outright.
"""

from __future__ import annotations

import os
from typing import Mapping

# What `docker compose up` and the Vite dev server serve from. Always allowed:
# these name the developer's own machine, so admitting them grants nothing that
# anyone reaching them does not already have.
LOCAL_ORIGINS: tuple[str, ...] = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
)

# Vercel gives every branch and every deployment its own hostname, so preview
# origins cannot be enumerated ahead of time and a fixed list would admit
# production while breaking every preview.
#
# Anchored at both ends and scoped to this project's own hostname prefixes,
# deliberately: `\.vercel\.app$` alone would hand these unauthenticated routes
# to anyone who can deploy to Vercel, which is everyone.
DEFAULT_ORIGIN_REGEX = r"^https://(iris-protocol|decentralized-a[a-z0-9-]*)\.vercel\.app$"


def allowed_origins(env: Mapping[str, str] | None = None) -> list[str]:
    """The localhost defaults plus whatever `IRIS_ALLOWED_ORIGINS` names.

    Comma-separated. Trailing slashes are stripped because an origin has no
    path component — `https://example.com/` never matches a browser's `Origin`
    header, and writing it that way in a dashboard field is the obvious
    mistake to make.

    A literal `*` is dropped rather than honoured. It does not do what someone
    typing it into a dashboard expects: this API sends credentials, and a
    wildcard in a credentialed response is invalid, so browsers reject it. The
    result would not be a permissive API but a broken one — including for the
    origins that work today. Dropping it leaves the explicit list intact.
    """
    env = os.environ if env is None else env
    configured = [
        origin.strip().rstrip("/")
        for origin in env.get("IRIS_ALLOWED_ORIGINS", "").split(",")
        if origin.strip() and origin.strip() != "*"
    ]
    return list(LOCAL_ORIGINS) + configured


def allowed_origin_regex(env: Mapping[str, str] | None = None) -> str | None:
    """The preview-deployment pattern, or None to match nothing.

    `IRIS_ALLOWED_ORIGIN_REGEX=""` is meaningful: it disables regex matching
    entirely, leaving only the explicit list. Starlette treats the empty string
    as a pattern matching every origin, which is the opposite of what setting a
    variable to nothing reads like, so it is mapped to None here.
    """
    env = os.environ if env is None else env
    pattern = env.get("IRIS_ALLOWED_ORIGIN_REGEX", DEFAULT_ORIGIN_REGEX).strip()
    return pattern or None
