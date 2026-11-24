"""Work Order API: a Flask REST API for machine-maintenance work orders."""
from __future__ import annotations

import logging

from flask import Flask

from .config import Config
from .errors import register_error_handlers
from .extensions import api, db, migrate

__version__ = "1.0.0"


def create_app(config: type[Config] | Config | None = None, **overrides) -> Flask:
    """Application factory: one function builds the app for tests, Docker and Vercel."""
    app = Flask(__name__)
    app.config.from_object(config or Config)
    app.config.update(overrides)
    app.json.sort_keys = False  # keep fields in schema order
    logging.basicConfig(level=app.config.get("LOG_LEVEL", "INFO"))

    db.init_app(app)
    migrate.init_app(app, db)
    api.init_app(app)
    register_error_handlers(app)

    from .routes import health, machines, reports, work_orders

    api.register_blueprint(health.blp)
    api.register_blueprint(machines.blp)
    api.register_blueprint(work_orders.blp)
    api.register_blueprint(reports.blp)

    with app.app_context():
        if app.config.get("AUTO_CREATE_TABLES"):
            db.create_all()
        if app.config.get("SEED_DEMO_DATA"):
            from .seed import seed_demo_data

            seed_demo_data()
    return app
