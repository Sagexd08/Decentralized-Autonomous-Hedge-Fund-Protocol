from fastapi.testclient import TestClient
import sys
import os
from pathlib import Path

# Ensure the backend directory is on the path
sys.path.insert(0, os.path.dirname(__file__))

import main
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


def test_sync_ml_model_from_supabase_success(monkeypatch):
    calls = {}

    def fake_download(bucket, object_path, destination):
        calls["args"] = (bucket, object_path, destination)
        return Path(destination)

    monkeypatch.setattr("core.supabase.download_storage_file", fake_download)

    assert main._sync_ml_model_from_supabase() is True
    assert calls["args"][0] == "models"
    assert calls["args"][1] == "model.pkl"
    assert calls["args"][2] == main._LOCAL_MODEL_PATH


def test_load_ml_artifacts_success(monkeypatch):
    sentinel_model = object()
    sentinel_scaler = object()

    def fake_load_model(path):
        assert path == main._LOCAL_MODEL_PATH
        return sentinel_model, sentinel_scaler

    monkeypatch.setattr("ml.train_hybrid.load_model", fake_load_model)

    model, scaler = main._load_ml_artifacts()
    assert model is sentinel_model
    assert scaler is sentinel_scaler
