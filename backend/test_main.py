from fastapi.testclient import TestClient
import sys
import os

# Ensure the backend directory is on the path
sys.path.insert(0, os.path.dirname(__file__))

from main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "2.1.0"}


def test_get_pool_not_found():
    response = client.get("/api/pools/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Pool not found"


def test_deposit_pool_not_found():
    response = client.post("/api/pools/deposit", json={"pool_id": "nonexistent", "amount": 100, "investor_address": "0x123"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Pool not found"


def test_global_exception_handler():
    # Trigger a route that raises an unhandled exception
    @app.get("/test-error")
    def raise_error():
        raise RuntimeError("test error")

    response = client.get("/test-error")
    assert response.status_code == 500
    assert response.json() == {"detail": "test error"}


def test_vote_proposal_not_found():
    response = client.post("/api/governance/vote", json={"proposal_id": 9999, "support": True, "voter": "0xabc"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Proposal not found"
