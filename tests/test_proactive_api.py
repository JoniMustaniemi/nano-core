from app.proactive.store import proactive_store


def test_proactive_api_snapshot(api_client) -> None:
    proactive_store.reset()
    proactive_store.set_dismissal("I guess not.")
    response = api_client.get("/api/proactive")
    assert response.status_code == 200
    payload = response.json()
    assert payload["dismissal"] == "I guess not."
    proactive_store.reset()


def test_proactive_api_dismiss_clears_state(api_client) -> None:
    proactive_store.reset()
    proactive_store.set_dismissal("I guess not.")
    response = api_client.post("/api/proactive/dismiss")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert proactive_store.snapshot()["dismissal"] is None
    proactive_store.reset()
