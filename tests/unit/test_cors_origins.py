"""
CORS origin policy.

These assert through a real `CORSMiddleware`, not against a reimplementation of
its matching rules — a test that re-derives the rule it is checking passes
whenever the two derivations agree, including when both are wrong. What is
asserted is the only thing a browser looks at: the `Access-Control-Allow-Origin`
header on the response.

The bug being pinned: the origin list was the six localhost addresses served by
`docker compose up`, so the deployed dashboard's every client-side fetch was
rejected and the UI rendered "Failed to fetch" over a completely healthy API.
It survived because the failure is invisible from the server — CORS is enforced
in the browser after the response is sent, so nothing appears in the access log,
and server-rendered requests are not subject to it at all.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

from core import origins  # noqa: E402


def build(env: dict[str, str]) -> FastAPI:
    """A minimal app carrying the same origin policy `main` installs."""
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins.allowed_origins(env),
        allow_origin_regex=origins.allowed_origin_regex(env),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["*"],
    )

    @app.get("/api/probe")
    def probe() -> dict:
        return {"ok": True}

    return app


def call(app: FastAPI, method: str, headers: dict[str, str]) -> tuple[int, dict[str, str]]:
    """Drive the ASGI app directly and return (status, response headers).

    Deliberately not `fastapi.testclient.TestClient`: that routes through
    httpx, which dropped the `app=` constructor argument in 0.28 while the
    pinned Starlette still passes it, so the client raises a TypeError before
    any request is made. Speaking ASGI here keeps this test measuring CORS
    rather than the compatibility of two unrelated pins.
    """
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "https",
        "path": "/api/probe",
        "raw_path": b"/api/probe",
        "query_string": b"",
        "root_path": "",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": ("test", 1),
        "server": ("testserver", 443),
    }
    sent: list[dict] = []

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict) -> None:
        sent.append(message)

    asyncio.run(app(scope, receive, send))

    start = next(m for m in sent if m["type"] == "http.response.start")
    return start["status"], {
        key.decode().lower(): value.decode() for key, value in start["headers"]
    }


def allows(env: dict[str, str], origin: str) -> bool:
    """Would a browser hand this response to a page served from `origin`?"""
    status, headers = call(build(env), "GET", {"Origin": origin})
    assert status == 200, "the route itself must answer either way"
    return headers.get("access-control-allow-origin") == origin


def allows_preflight(env: dict[str, str], origin: str) -> bool:
    """The same question for the OPTIONS a browser sends ahead of a POST."""
    _, headers = call(
        build(env),
        "OPTIONS",
        {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    return headers.get("access-control-allow-origin") == origin


PROD = {"IRIS_ALLOWED_ORIGINS": "https://iris-protocol.vercel.app"}


class TestTheDeployedApp:
    """The case that was broken in production."""

    def test_configured_production_origin_is_allowed(self):
        assert allows(PROD, "https://iris-protocol.vercel.app")

    def test_the_preflight_is_allowed_too(self):
        # Every POST from the dashboard — registering an agent, staking,
        # voting — is preceded by an OPTIONS the browser sends on its own. A
        # policy that admits the GET but not the preflight breaks writes only,
        # which is the harder half of this bug to notice.
        assert allows_preflight(PROD, "https://iris-protocol.vercel.app")

    def test_production_origin_is_refused_when_not_configured(self):
        # Not a defect — it is why the variable has to be set on the service.
        # Stated as a test so the requirement is visible rather than folded
        # into a comment in a YAML file.
        assert not allows({}, "https://custom-domain.example.com")

    def test_trailing_slash_in_the_dashboard_field_still_works(self):
        # An origin has no path, so "https://x/" never equals a browser's
        # Origin header. Easy to type into a web form and hard to debug.
        env = {"IRIS_ALLOWED_ORIGINS": "https://iris-protocol.vercel.app/"}
        assert allows(env, "https://iris-protocol.vercel.app")

    def test_several_origins_may_be_listed(self):
        env = {"IRIS_ALLOWED_ORIGINS": "https://a.example.com, https://b.example.com"}
        assert allows(env, "https://a.example.com")
        assert allows(env, "https://b.example.com")


class TestPreviewDeployments:
    """Per-branch hostnames, which cannot be enumerated in advance."""

    @pytest.mark.parametrize(
        "origin",
        [
            "https://iris-protocol.vercel.app",
            "https://decentralized-autonomous-hedge-fund-protocol-n7zem8z1t.vercel.app",
            "https://decentralized-a-git-d75d11-sohomchatterjee07-gmailcoms-projects.vercel.app",
            "https://decentralized-autonomous-h-sohomchatterjee07-gmailcoms-projects.vercel.app",
        ],
    )
    def test_this_projects_deployments_match(self, origin: str):
        assert allows({}, origin)

    @pytest.mark.parametrize(
        "origin",
        [
            # Anyone can deploy to vercel.app. The pattern is scoped to this
            # project's hostname prefixes for that reason, and these routes are
            # unauthenticated, so the origin list is the only thing in the way.
            "https://someone-elses-app.vercel.app",
            "https://evil.com",
            # Anchoring: a prefix match would admit both of these.
            "https://iris-protocol.vercel.app.evil.com",
            "https://evil.com/iris-protocol.vercel.app",
        ],
    )
    def test_unrelated_origins_are_refused(self, origin: str):
        assert not allows({}, origin)

    def test_http_previews_are_refused(self):
        # The pattern requires https. Vercel does not serve plaintext, so an
        # http origin claiming to be one is not a deployment of this project.
        assert not allows({}, "http://iris-protocol.vercel.app")

    def test_empty_regex_disables_pattern_matching(self):
        # Starlette reads "" as a pattern that matches everything, which is the
        # opposite of what clearing a variable looks like it should do.
        env = {"IRIS_ALLOWED_ORIGIN_REGEX": ""}
        assert not allows(env, "https://iris-protocol.vercel.app")
        assert not allows(env, "https://anything-at-all.example.com")


class TestLocalDevelopment:
    """Unchanged behaviour: the compose stack must keep working."""

    @pytest.mark.parametrize("origin", list(origins.LOCAL_ORIGINS))
    def test_localhost_is_always_allowed(self, origin: str):
        assert allows({}, origin)
        assert allows(PROD, origin)


def test_no_wildcard_is_ever_emitted():
    """A credentialed response carrying `*` is rejected by every browser.

    So a wildcard here would not loosen the policy, it would break every
    origin including the ones that work today.
    """
    for env in ({}, PROD, {"IRIS_ALLOWED_ORIGINS": "*"}):
        assert "*" not in origins.allowed_origins(env)
