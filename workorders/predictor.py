"""Client for the external failure-prediction API (a third-party integration).

Network calls fail in ordinary ways: timeouts, 5xx errors, bad JSON. This client retries what is
worth retrying (connection errors, timeouts, 5xx) with a short backoff, does not retry client errors
(4xx), and turns every failure into one `UpstreamError` that callers can handle.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import requests

from .errors import UpstreamError

log = logging.getLogger(__name__)

# Failure probability -> work-order priority. Bands are a product decision, kept in one place.
PRIORITY_BANDS = [(0.80, "critical"), (0.50, "high"), (0.20, "medium"), (0.0, "low")]


def priority_for(probability: float) -> str:
    if not 0.0 <= probability <= 1.0:
        raise ValueError(f"probability must be between 0 and 1, got {probability}")
    for floor, label in PRIORITY_BANDS:
        if probability >= floor:
            return label
    return "low"  # pragma: no cover


@dataclass
class Score:
    probability: float
    priority: str
    model: str
    warnings: list[str]


class PredictorClient:
    def __init__(self, base_url: str, timeout: float = 4.0, retries: int = 2, backoff: float = 0.3,
                 session: requests.Session | None = None):
        self.url = base_url.rstrip("/") + "/predict"
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.session = session or requests.Session()

    def score(self, product_type: str, reading: dict) -> Score:
        payload = {"type": product_type, **reading}
        last_error = "unknown error"
        for attempt in range(self.retries + 1):
            try:
                resp = self.session.post(self.url, json=payload, timeout=self.timeout)
            except requests.Timeout:
                last_error = f"timed out after {self.timeout}s"
            except requests.ConnectionError as exc:
                last_error = f"connection failed ({exc.__class__.__name__})"
            else:
                if resp.status_code >= 500:
                    last_error = f"prediction service returned {resp.status_code}"
                elif resp.status_code >= 400:
                    # Our request was rejected: retrying will not help.
                    raise UpstreamError("The prediction service rejected the reading.",
                                        {"status": resp.status_code})
                else:
                    return self._parse(resp)
            if attempt < self.retries:
                time.sleep(self.backoff * (2 ** attempt))
        log.warning("prediction service unavailable: %s", last_error)
        raise UpstreamError("The prediction service is unavailable.", {"reason": last_error})

    @staticmethod
    def _parse(resp: requests.Response) -> Score:
        try:
            data = resp.json()
            probability = float(data["failure_probability"])
            return Score(probability=probability, priority=priority_for(probability),
                         model=str(data.get("model", "unknown")), warnings=list(data.get("warnings", [])))
        except (ValueError, KeyError, TypeError) as exc:
            raise UpstreamError("The prediction service sent an unexpected response.",
                                {"reason": exc.__class__.__name__}) from exc
