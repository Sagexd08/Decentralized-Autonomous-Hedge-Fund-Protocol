def test_list_agents(client):
    response = client.get("/api/agents/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_agent_by_id(client):
    response = client.get("/api/agents/AGT-001")
    assert response.status_code == 200
    assert response.json()["name"] == "AlphaWave"
 

def test_get_agent_invalid_id(client):
    response = client.get("/api/agents/INVALID")
    assert response.status_code == 404


def test_register_agent(client):
    payload = {
        "name": "TestBot",
        "strategy": "Test Strategy",
        "risk": "Balanced",
        "stake": 10000,
        "address": "0xdeadbeef"
    }
    response = client.post("/api/agents/register", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["id"].startswith("AGT-")
