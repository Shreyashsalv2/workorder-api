import pytest
import requests
import responses

from conftest import PREDICTOR, READING, predict_ok


def test_create_without_reading_is_unscored(client, machine, mocked):
    r = client.post("/work-orders", json={"machine_id": machine["id"], "title": "Coolant check"})
    assert r.status_code == 201
    body = r.get_json()
    assert body["priority"] == "unscored" and body["status"] == "open" and body["reading"] is None
    assert len(mocked.calls) == 0  # no reading, no network call


def test_create_with_reading_is_scored(client, machine, mocked):
    predict_ok(mocked, 0.9843)
    r = client.post("/work-orders", json={"machine_id": machine["id"], "title": "Vibration", "reading": READING})
    body = r.get_json()
    assert r.status_code == 201
    assert body["priority"] == "critical" and body["failure_probability"] == 0.9843
    assert body["reading"] == READING
    sent = mocked.calls[0].request
    assert b'"type": "L"' in sent.body or b'"type":"L"' in sent.body


def test_prediction_service_down_still_saves_the_order(client, machine, mocked):
    for _ in range(3):
        mocked.add(responses.POST, PREDICTOR + "/predict", status=503)
    r = client.post("/work-orders", json={"machine_id": machine["id"], "title": "Vibration", "reading": READING})
    body = r.get_json()
    assert r.status_code == 201
    assert body["priority"] == "unscored" and "503" in body["scoring_note"]
    assert len(mocked.calls) == 3  # first try + 2 retries


def test_timeout_still_saves_the_order(client, machine, mocked):
    for _ in range(3):
        mocked.add(responses.POST, PREDICTOR + "/predict", body=requests.Timeout())
    body = client.post("/work-orders", json={"machine_id": machine["id"], "title": "T", "reading": READING}).get_json()
    assert body["priority"] == "unscored" and "timed out" in body["scoring_note"]


def test_rescore_after_service_recovers(client, machine, mocked):
    for _ in range(3):
        mocked.add(responses.POST, PREDICTOR + "/predict", status=500)
    order = client.post("/work-orders", json={"machine_id": machine["id"], "title": "T", "reading": READING}).get_json()
    mocked.reset()
    predict_ok(mocked, 0.31)
    r = client.post(f"/work-orders/{order['id']}/score")
    assert r.status_code == 200 and r.get_json()["priority"] == "medium"


def test_unknown_machine_is_404(client):
    r = client.post("/work-orders", json={"machine_id": 42, "title": "T"})
    assert r.status_code == 404 and r.get_json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("bad", [
    {"title": ""},
    {"reading": {**READING, "torque_nm": -5}},
    {"reading": {"air_temperature_k": 300}},
    {"priority": "critical"},
])
def test_invalid_input_is_422(client, machine, bad):
    payload = {"machine_id": machine["id"], "title": "T", **bad}
    r = client.post("/work-orders", json=payload)
    assert r.status_code == 422 and r.get_json()["error"]["code"] == "validation_error"


def test_status_flow_and_invalid_transition(client, machine):
    order = client.post("/work-orders", json={"machine_id": machine["id"], "title": "T"}).get_json()
    url = f"/work-orders/{order['id']}"
    assert client.patch(url, json={"status": "in_progress"}).get_json()["status"] == "in_progress"
    assert client.patch(url, json={"status": "done"}).get_json()["status"] == "done"
    r = client.patch(url, json={"status": "open"})
    assert r.status_code == 409
    err = r.get_json()["error"]
    assert err["code"] == "invalid_status_transition" and err["details"]["from"] == "done"


def test_filters_and_pagination(client, machine, mocked):
    predict_ok(mocked, 0.95)
    predict_ok(mocked, 0.05)
    client.post("/work-orders", json={"machine_id": machine["id"], "title": "A", "reading": READING})
    client.post("/work-orders", json={"machine_id": machine["id"], "title": "B", "reading": READING})
    client.post("/work-orders", json={"machine_id": machine["id"], "title": "C"})
    crit = client.get("/work-orders?priority=critical").get_json()
    assert crit["total"] == 1 and crit["items"][0]["title"] == "A"
    page = client.get("/work-orders?per_page=2").get_json()
    assert page["total"] == 3 and [o["title"] for o in page["items"]] == ["C", "B"]  # newest first
    assert client.get("/work-orders?status=bogus").status_code == 422


def test_delete_order(client, machine):
    order = client.post("/work-orders", json={"machine_id": machine["id"], "title": "T"}).get_json()
    assert client.delete(f"/work-orders/{order['id']}").status_code == 204
    assert client.get(f"/work-orders/{order['id']}").status_code == 404
