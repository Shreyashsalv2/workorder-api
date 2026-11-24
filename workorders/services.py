"""Business logic, kept out of the route functions so it can be tested on its own."""
from __future__ import annotations

from flask import current_app
from sqlalchemy import func, select

from .errors import ConflictError, NotFoundError, UpstreamError
from .extensions import db
from .models import Machine, WorkOrder
from .predictor import PredictorClient


def get_or_404(model, obj_id: int, label: str):
    obj = db.session.get(model, obj_id)
    if obj is None:
        raise NotFoundError(f"{label} {obj_id} does not exist.", {"id": obj_id})
    return obj


def predictor() -> PredictorClient:
    cfg = current_app.config
    return PredictorClient(cfg["PREDICTOR_URL"], timeout=cfg["PREDICTOR_TIMEOUT"], retries=cfg["PREDICTOR_RETRIES"])


def score_work_order(order: WorkOrder) -> None:
    """Set priority from the prediction service. If it is down, keep the order and say why."""
    reading = order.reading
    if reading is None:
        order.priority, order.failure_probability = "unscored", None
        order.scoring_note = "No sensor reading, so the order was not scored."
        return
    try:
        score = predictor().score(order.machine.product_type, reading)
    except UpstreamError as err:
        order.priority, order.failure_probability = "unscored", None
        reason = err.details.get("reason") or f"request rejected with HTTP {err.details.get('status')}"
        order.scoring_note = f"Not scored, the prediction service failed ({reason}). Retry with POST /work-orders/<id>/score."
        return
    order.failure_probability = round(score.probability, 4)
    order.priority = score.priority
    note = f"Scored by {score.model}."
    if score.warnings:
        note += " " + " ".join(score.warnings)
    order.scoring_note = note[:300]


def create_work_order(data: dict) -> WorkOrder:
    machine = get_or_404(Machine, data["machine_id"], "Machine")
    order = WorkOrder(machine=machine, title=data["title"], description=data.get("description"))
    if data.get("reading"):
        for field, value in data["reading"].items():
            setattr(order, field, value)
    score_work_order(order)
    db.session.add(order)
    db.session.commit()
    return order


def update_work_order(order: WorkOrder, data: dict) -> WorkOrder:
    if "status" in data:
        order.transition_to(data["status"])
    for field in ("title", "description"):
        if field in data:
            setattr(order, field, data[field])
    db.session.commit()
    return order


def delete_machine(machine: Machine) -> None:
    open_orders = db.session.scalar(
        select(func.count()).select_from(WorkOrder).where(WorkOrder.machine_id == machine.id,
                                                          WorkOrder.status != "done"))
    if open_orders:
        raise ConflictError("This machine still has work orders that are not done.",
                            {"machine_id": machine.id, "unfinished_orders": open_orders})
    for order in list(machine.work_orders):
        db.session.delete(order)
    db.session.delete(machine)
    db.session.commit()


def paginate(stmt, page: int, per_page: int) -> dict:
    total = db.session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    items = db.session.scalars(stmt.limit(per_page).offset((page - 1) * per_page)).all()
    return {"items": items, "page": page, "per_page": per_page, "total": total}
