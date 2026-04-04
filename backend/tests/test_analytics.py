def test_monte_carlo_returns_200(client):
    response = client.get("/api/analytics/monte-carlo")
    assert response.status_code == 200


def test_monte_carlo_response_keys(client):
    response = client.get("/api/analytics/monte-carlo")
    data = response.json()
    assert "stats" in data
    assert "paths" in data


def test_rolling_volatility_returns_200(client):
    response = client.get("/api/analytics/rolling-volatility")
    assert response.status_code == 200


def test_regime_returns_200(client):
    response = client.get("/api/analytics/regime")
    assert response.status_code == 200


def test_regime_equal_length(client):
    response = client.get("/api/analytics/regime")
    data = response.json()
    assert "regimes" in data
    assert "confidences" in data
    assert len(data["regimes"]) == len(data["confidences"])


def test_allocation_weights_returns_200(client):
    response = client.get("/api/analytics/allocation-weights")
    assert response.status_code == 200
