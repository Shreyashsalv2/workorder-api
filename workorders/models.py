"""SQLAlchemy models. Portable across SQLite, PostgreSQL and MySQL (string enums, explicit lengths)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .errors import InvalidTransitionError
from .extensions import db

PRODUCT_TYPES = ("L", "M", "H")
STATUSES = ("open", "in_progress", "done")
PRIORITIES = ("unscored", "low", "medium", "high", "critical")

# Allowed status changes. Anything else is a 409 Conflict.
TRANSITIONS = {
    "open": {"in_progress", "done"},
    "in_progress": {"open", "done"},
    "done": set(),
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Machine(db.Model):
    __tablename__ = "machines"
    __table_args__ = (CheckConstraint("product_type IN ('L','M','H')", name="ck_machine_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    product_type: Mapped[str] = mapped_column(String(1), nullable=False)
    location: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)

    work_orders: Mapped[list["WorkOrder"]] = relationship(back_populates="machine")


class WorkOrder(db.Model):
    __tablename__ = "work_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(20), default="unscored", nullable=False, index=True)

    # Optional sensor reading sent with the order; used to score failure risk.
    air_temperature_k: Mapped[float | None]
    process_temperature_k: Mapped[float | None]
    rotational_speed_rpm: Mapped[float | None]
    torque_nm: Mapped[float | None]
    tool_wear_min: Mapped[float | None]
    failure_probability: Mapped[float | None]
    scoring_note: Mapped[str | None] = mapped_column(String(300))

    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow, nullable=False)

    machine: Mapped[Machine] = relationship(back_populates="work_orders")

    READING_FIELDS = ("air_temperature_k", "process_temperature_k", "rotational_speed_rpm", "torque_nm",
                      "tool_wear_min")

    @property
    def reading(self) -> dict | None:
        values = {f: getattr(self, f) for f in self.READING_FIELDS}
        return values if all(v is not None for v in values.values()) else None

    def transition_to(self, new_status: str) -> None:
        if new_status == self.status:
            return
        if new_status not in TRANSITIONS[self.status]:
            raise InvalidTransitionError(
                f"Cannot move a work order from '{self.status}' to '{new_status}'.",
                {"from": self.status, "to": new_status, "allowed": sorted(TRANSITIONS[self.status])},
            )
        self.status = new_status
