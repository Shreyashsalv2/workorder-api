from flask_smorest import Blueprint
from sqlalchemy import text

from ..extensions import db

blp = Blueprint("reports", __name__, url_prefix="/reports", description="Aggregated reports (plain SQL)")

# Plain SQL on purpose: portable GROUP BY that runs unchanged on SQLite, PostgreSQL and MySQL.
SUMMARY_SQL = text("""
    SELECT status, priority, COUNT(*) AS orders
    FROM work_orders
    GROUP BY status, priority
    ORDER BY status, priority
""")
BY_MACHINE_SQL = text("""
    SELECT m.id AS machine_id, m.name AS machine_name,
           SUM(CASE WHEN w.status <> 'done' THEN 1 ELSE 0 END) AS open_orders,
           MAX(w.failure_probability) AS highest_failure_probability
    FROM machines m
    LEFT JOIN work_orders w ON w.machine_id = m.id
    GROUP BY m.id, m.name
    ORDER BY open_orders DESC, m.id
""")


@blp.route("/summary")
@blp.response(200)
def summary():
    """Work-order counts by status and priority, plus open orders per machine."""
    rows = db.session.execute(SUMMARY_SQL).mappings().all()
    machines = db.session.execute(BY_MACHINE_SQL).mappings().all()
    return {
        "by_status_and_priority": [dict(r) for r in rows],
        "by_machine": [{**dict(r), "open_orders": int(r["open_orders"] or 0),
                        "highest_failure_probability": (float(r["highest_failure_probability"])
                                                        if r["highest_failure_probability"] is not None else None)}
                       for r in machines],
    }
