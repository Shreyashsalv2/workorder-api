"""Fixtures. Set TEST_DATABASE_URL to run the whole suite on PostgreSQL or MySQL (CI does all three)."""
import os

import pytest
import responses

from workorders import create_app
from workorders.extensions import db

PREDICTOR = "http://predictor.test"
DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite://")


@pytest.fixture()
def app():
    app = create_app(SQLALCHEMY_DATABASE_URI=DB_URL, TESTING=True, AUTO_CREATE_TABLES=False,
                     SEED_DEMO_DATA=False, PREDICTOR_URL=PREDICTOR, PREDICTOR_RETRIES=2,
                     PREDICTOR_TIMEOUT=0.5)
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def mocked():
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        yield rsps


@pytest.fixture(autouse=True)
def fast_backoff(monkeypatch):
    monkeypatch.setattr("workorders.predictor.time.sleep", lambda s: None)


@pytest.fixture()
def machine(client):
    return client.post("/machines", json={"name": "Mill-01", "product_type": "L", "location": "Bay A"}).get_json()


READING = {"air_temperature_k": 300.0, "process_temperature_k": 310.0, "rotational_speed_rpm": 1350,
           "torque_nm": 62.0, "tool_wear_min": 210}


def predict_ok(rsps, probability, warnings=None):
    rsps.add(responses.POST, PREDICTOR + "/predict",
             json={"failure_probability": probability, "predicted_failure": probability > 0.42,
                   "threshold": 0.42, "model": "random_forest", "derived": {}, "warnings": warnings or []})
