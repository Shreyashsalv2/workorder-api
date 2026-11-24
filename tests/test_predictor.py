import pytest
import requests
import responses

from workorders.errors import UpstreamError
from workorders.predictor import PredictorClient, priority_for

URL = "http://predictor.test"


@pytest.mark.parametrize("p,label", [(0.0, "low"), (0.19, "low"), (0.2, "medium"), (0.49, "medium"),
                                     (0.5, "high"), (0.79, "high"), (0.8, "critical"), (1.0, "critical")])
def test_priority_bands(p, label):
    assert priority_for(p) == label


def test_priority_rejects_out_of_range():
    with pytest.raises(ValueError):
        priority_for(1.5)


@responses.activate
def test_retries_on_5xx_then_succeeds():
    responses.add(responses.POST, URL + "/predict", status=502)
    responses.add(responses.POST, URL + "/predict", json={"failure_probability": 0.6, "model": "rf", "warnings": []})
    score = PredictorClient(URL, retries=2, backoff=0).score("M", {"torque_nm": 50})
    assert score.priority == "high" and len(responses.calls) == 2


@responses.activate
def test_does_not_retry_client_errors():
    responses.add(responses.POST, URL + "/predict", status=422, json={"detail": "bad"})
    with pytest.raises(UpstreamError) as exc:
        PredictorClient(URL, retries=2, backoff=0).score("M", {})
    assert exc.value.details == {"status": 422} and len(responses.calls) == 1


@responses.activate
def test_gives_up_after_retries():
    responses.add(responses.POST, URL + "/predict", body=requests.ConnectionError())
    with pytest.raises(UpstreamError) as exc:
        PredictorClient(URL, retries=1, backoff=0).score("L", {})
    assert "connection failed" in exc.value.details["reason"] and len(responses.calls) == 2


@responses.activate
@pytest.mark.parametrize("body", [{"unexpected": 1}, {"failure_probability": "high"}, {"failure_probability": 7}])
def test_bad_response_is_an_upstream_error(body):
    responses.add(responses.POST, URL + "/predict", json=body)
    with pytest.raises(UpstreamError):
        PredictorClient(URL, retries=0).score("L", {})
