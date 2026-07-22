from fastapi.testclient import TestClient

from app.main import app
from app.proactive.store import proactive_store


def test_proactive_api_snapshot() -> None:
    proactive_store.reset()
    proactive_store.set_dismissal("I guess not.")
    with TestClient(app) as client:
        response = client.get("/api/proactive")
    assert response.status_code == 200
    payload = response.json()
    assert payload["dismissal"] == "I guess not."
    proactive_store.reset()
