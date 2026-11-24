from flask_smorest import Blueprint
from sqlalchemy import text

from .. import __version__
from ..extensions import db

blp = Blueprint("health", __name__, description="Service health")


@blp.route("/health")
@blp.response(200)
def health():
    """Liveness check that also runs a trivial query against the database."""
    db.session.execute(text("SELECT 1"))
    return {"status": "ok", "version": __version__, "database": db.engine.dialect.name}
