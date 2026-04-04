def test_list_pools_returns_200_and_three_pools(client):
    response = client.get("/api/pools/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3


def test_get_conservative_pool_returns_200(client):
    response = client.get("/api/pools/conservative")
    assert response.status_code == 200
    assert response.json()["id"] == "conservative"

 
def test_get_nonexistent_pool_returns_404(client):
    response = client.get("/api/pools/nonexistent")
    assert response.status_code == 404


def test_deposit_with_valid_data_returns_200(client):
    payload = {
        "pool_id": "balanced",
        "amount": 1000.0,
        "investor_address": "0xABC123"
    }
    response = client.post("/api/pools/deposit", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["pool"] == "balanced"
    assert data["amount"] == 1000.0
    assert data["status"] == "pending"
