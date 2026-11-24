import shutil
import subprocess
import sys
from pathlib import Path

from conftest import READING, predict_ok


def test_summary_report(client, machine, mocked):
    predict_ok(mocked, 0.9)
    client.post("/work-orders", json={"machine_id": machine["id"], "title": "A", "reading": READING})
    b = client.post("/work-orders", json={"machine_id": machine["id"], "title": "B"}).get_json()
    client.patch(f"/work-orders/{b['id']}", json={"status": "done"})
    rep = client.get("/reports/summary").get_json()
    rows = {(r["status"], r["priority"]): r["orders"] for r in rep["by_status_and_priority"]}
    assert rows == {("open", "critical"): 1, ("done", "unscored"): 1}
    assert rep["by_machine"][0] == {"machine_id": machine["id"], "machine_name": "Mill-01", "open_orders": 1,
                                    "highest_failure_probability": 0.9}


def test_health_reports_database(client):
    body = client.get("/health").get_json()
    assert body["status"] == "ok" and body["database"] in {"sqlite", "postgresql", "mysql"}


def test_unknown_route_and_method_are_json(client):
    r = client.get("/does-not-exist")
    assert r.status_code == 404 and r.get_json()["error"]["code"] == "not_found"
    r = client.delete("/health")
    assert r.status_code == 405 and r.get_json()["error"]["code"] == "method_not_allowed"


def test_malformed_json_is_a_json_error(client):
    r = client.post("/machines", data="{not json", content_type="application/json")
    assert r.status_code in (400, 422) and "error" in r.get_json()


def test_unexpected_error_hides_internals(app, client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr("workorders.routes.machines.paginate", boom)
    r = client.get("/machines")
    assert r.status_code == 500
    assert r.get_json() == {"error": {"code": "internal_error", "message": "Something went wrong on our side."}}
    assert "secret" not in r.get_data(as_text=True)


def test_openapi_docs(client):
    spec = client.get("/openapi.json").get_json()
    assert spec["info"]["title"] == "Work Order API"
    assert "/work-orders" in spec["paths"] and "/machines/{machine_id}" in spec["paths"]
    assert client.get("/docs").status_code == 200


def test_app_starts_without_public_folder(tmp_path):
    """Vercel serves public/ from its CDN and leaves it out of the function bundle."""
    root = Path(__file__).resolve().parent.parent
    shutil.copytree(root / "workorders", tmp_path / "workorders")
    shutil.copy(root / "app.py", tmp_path / "app.py")
    code = ("import app; c = app.app.test_client(); r = c.get('/health'); "
            "assert r.status_code == 200, r.data; assert c.get('/').status_code == 404")
    r = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", "AUTO_CREATE_TABLES": "1",
                            "DATABASE_URL": f"sqlite:///{tmp_path}/t.db"})
    assert r.returncode == 0, r.stderr


def test_seed_is_idempotent_and_skips_missing_tables(app, mocked):
    from workorders.extensions import db
    from workorders.models import Machine, WorkOrder
    from workorders.seed import seed_demo_data

    seed_demo_data()  # predictor not mocked: every reading falls back to "unscored"
    seed_demo_data()
    assert db.session.query(Machine).count() == 3 and db.session.query(WorkOrder).count() == 3
    db.session.remove()  # end the open transaction before dropping tables (PostgreSQL would wait on it)
    db.drop_all()
    seed_demo_data()  # no tables: must not raise
