def test_create_and_get(client):
    r = client.post("/machines", json={"name": "Mill-01", "product_type": "L", "location": "Bay A"})
    assert r.status_code == 201
    body = r.get_json()
    assert body["name"] == "Mill-01" and body["id"] > 0
    assert client.get(f"/machines/{body['id']}").get_json()["product_type"] == "L"


def test_list_is_paginated(client):
    for i in range(5):
        client.post("/machines", json={"name": f"M{i}", "product_type": "M"})
    page = client.get("/machines?page=2&per_page=2").get_json()
    assert page["total"] == 5 and page["page"] == 2 and [m["name"] for m in page["items"]] == ["M2", "M3"]


def test_duplicate_name_is_409(client, machine):
    r = client.post("/machines", json={"name": "Mill-01", "product_type": "H"})
    assert r.status_code == 409 and r.get_json()["error"]["code"] == "conflict"


def test_invalid_type_and_unknown_field_are_422(client):
    r = client.post("/machines", json={"name": "X", "product_type": "Z", "colour": "red"})
    assert r.status_code == 422
    details = r.get_json()["error"]["details"]
    assert "product_type" in details and "colour" in details


def test_missing_machine_is_404(client):
    r = client.get("/machines/999")
    assert r.status_code == 404
    assert r.get_json()["error"] == {"code": "not_found", "message": "Machine 999 does not exist.",
                                     "details": {"id": 999}}


def test_update(client, machine):
    r = client.patch(f"/machines/{machine['id']}", json={"location": "Bay B"})
    assert r.status_code == 200 and r.get_json()["location"] == "Bay B"


def test_delete_blocked_while_orders_are_open(client, machine):
    client.post("/work-orders", json={"machine_id": machine["id"], "title": "Check belt"})
    r = client.delete(f"/machines/{machine['id']}")
    assert r.status_code == 409
    assert r.get_json()["error"]["details"]["unfinished_orders"] == 1


def test_delete_after_orders_are_done(client, machine):
    order = client.post("/work-orders", json={"machine_id": machine["id"], "title": "Check belt"}).get_json()
    client.patch(f"/work-orders/{order['id']}", json={"status": "done"})
    assert client.delete(f"/machines/{machine['id']}").status_code == 204
    assert client.get(f"/machines/{machine['id']}").status_code == 404
    assert client.get(f"/work-orders/{order['id']}").status_code == 404
