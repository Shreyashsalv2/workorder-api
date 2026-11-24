"""Settings, read from environment variables so the same code runs locally, in Docker, in CI and on Vercel."""
from __future__ import annotations

import os


def _bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        # Heroku/Render style URLs use postgres://; SQLAlchemy needs a driver name.
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        elif url.startswith("mysql://"):
            url = "mysql+pymysql://" + url[len("mysql://"):]
        return url
    # Serverless hosts (Vercel) only allow writes under /tmp.
    if os.environ.get("VERCEL"):
        return "sqlite:////tmp/workorders.db"
    return "sqlite:///workorders.db"


class Config:
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Without a real database (local SQLite, Vercel demo) create tables directly and seed sample data.
    AUTO_CREATE_TABLES = _bool("AUTO_CREATE_TABLES", SQLALCHEMY_DATABASE_URI.startswith("sqlite"))
    SEED_DEMO_DATA = _bool("SEED_DEMO_DATA", bool(os.environ.get("VERCEL")))

    PREDICTOR_URL = os.environ.get("PREDICTOR_URL", "https://machine-failure-predictor.vercel.app")
    PREDICTOR_TIMEOUT = float(os.environ.get("PREDICTOR_TIMEOUT", "4"))
    PREDICTOR_RETRIES = int(os.environ.get("PREDICTOR_RETRIES", "2"))

    MAX_PER_PAGE = 100
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

    API_TITLE = "Work Order API"
    API_VERSION = "1.0.0"
    OPENAPI_VERSION = "3.0.3"
    OPENAPI_URL_PREFIX = "/"
    OPENAPI_JSON_PATH = "openapi.json"
    OPENAPI_SWAGGER_UI_PATH = "/docs"
    OPENAPI_SWAGGER_UI_URL = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/"
    JSON_SORT_KEYS = False
