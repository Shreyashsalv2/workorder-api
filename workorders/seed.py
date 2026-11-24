"""Sample data for the live demo (only when SEED_DEMO_DATA is on and the database is empty)."""
import logging

from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

from .extensions import db
from .models import Machine, WorkOrder
from .services import score_work_order

MACHINES = [("Mill-01", "L", "Bay A"), ("Mill-02", "M", "Bay A"), ("Lathe-07", "H", "Bay C")]
ORDERS = [
    ("Mill-01", "Spindle vibration after tool change",
     dict(air_temperature_k=300.0, process_temperature_k=310.0, rotational_speed_rpm=1350, torque_nm=62.0,
          tool_wear_min=210)),
    ("Mill-02", "Routine weekly inspection",
     dict(air_temperature_k=299.0, process_temperature_k=309.5, rotational_speed_rpm=1500, torque_nm=40.0,
          tool_wear_min=90)),
    ("Lathe-07", "Coolant level check", None),
]


log = logging.getLogger(__name__)


def seed_demo_data() -> None:
    """Idempotent and safe to run from several workers at once."""
    if not inspect(db.engine).has_table("machines"):
        return  # tables not created yet (e.g. while `flask db upgrade` itself is running)
    if db.session.scalar(select(func.count()).select_from(Machine)):
        return
    machines = {name: Machine(name=name, product_type=t, location=loc) for name, t, loc in MACHINES}
    db.session.add_all(machines.values())
    for name, title, reading in ORDERS:
        order = WorkOrder(machine=machines[name], title=title)
        for field, value in (reading or {}).items():
            setattr(order, field, value)
        score_work_order(order)
        db.session.add(order)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()  # another worker seeded first
        log.info("demo data already seeded by another worker")
