"""Exception handling: every error leaves the API in one JSON shape.

    {"error": {"code": "not_found", "message": "...", "details": {...}}}

Domain code raises the small exception classes below; the handlers registered in
`register_error_handlers` turn them (and Flask, validation and database errors) into that shape.
"""
from __future__ import annotations

import logging

from flask import jsonify
from flask_smorest import Api
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

log = logging.getLogger(__name__)


class APIError(Exception):
    """Base class for errors the API reports on purpose."""

    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(APIError):
    status_code = 404
    code = "not_found"


class ConflictError(APIError):
    status_code = 409
    code = "conflict"


class InvalidTransitionError(ConflictError):
    code = "invalid_status_transition"


class UpstreamError(APIError):
    """The prediction service failed (timeout, 5xx, bad JSON). Callers usually recover from it."""

    status_code = 502
    code = "upstream_error"


def error_body(status: int, code: str, message: str, details: dict | None = None):
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    resp = jsonify(body)
    resp.status_code = status
    return resp


_HTTP_CODES = {400: "bad_request", 404: "not_found", 405: "method_not_allowed", 409: "conflict",
               413: "payload_too_large", 415: "unsupported_media_type", 422: "validation_error"}


class JSONErrorApi(Api):
    """flask-smorest Api whose HTTP errors (including 422 validation errors) use the same JSON shape."""

    def handle_http_exception(self, error: HTTPException):
        status = error.code or 500
        details = None
        data = getattr(error, "data", None) or {}
        if "messages" in data:  # webargs/marshmallow validation errors
            details = data["messages"]
            # Report per-field errors whatever the request location (json, query).
            if isinstance(details, dict) and len(details) == 1:
                details = next(iter(details.values()))
        message = "Request validation failed." if status == 422 else (error.description or error.name)
        return error_body(status, _HTTP_CODES.get(status, "http_error"), message, details)


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(err: APIError):
        return error_body(err.status_code, err.code, err.message, err.details)

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(err: IntegrityError):
        from .extensions import db

        db.session.rollback()
        log.info("integrity error: %s", err.orig)
        return error_body(409, "conflict", "The request conflicts with existing data (for example a duplicate name).")

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):
        if isinstance(err, HTTPException):  # routed here only outside flask-smorest blueprints
            return error_body(err.code or 500, _HTTP_CODES.get(err.code, "http_error"), err.description or err.name)
        from .extensions import db

        db.session.rollback()
        log.exception("unhandled error")
        # Never leak a traceback or internal message to the client.
        return error_body(500, "internal_error", "Something went wrong on our side.")
