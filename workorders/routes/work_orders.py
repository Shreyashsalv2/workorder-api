from flask.views import MethodView
from flask_smorest import Blueprint
from sqlalchemy import select

from ..extensions import db
from ..models import WorkOrder
from ..schemas import (WorkOrderCreateSchema, WorkOrderPageSchema, WorkOrderQuerySchema, WorkOrderSchema,
                       WorkOrderUpdateSchema)
from ..services import create_work_order, get_or_404, paginate, score_work_order, update_work_order

blp = Blueprint("work_orders", __name__, url_prefix="/work-orders", description="Maintenance work orders")


@blp.route("")
class WorkOrders(MethodView):
    @blp.arguments(WorkOrderQuerySchema, location="query")
    @blp.response(200, WorkOrderPageSchema)
    def get(self, args):
        """List work orders, newest first. Filter by status, priority or machine."""
        stmt = select(WorkOrder).order_by(WorkOrder.id.desc())
        for field in ("status", "priority", "machine_id"):
            if field in args:
                stmt = stmt.where(getattr(WorkOrder, field) == args[field])
        return paginate(stmt, args["page"], args["per_page"])

    @blp.arguments(WorkOrderCreateSchema)
    @blp.response(201, WorkOrderSchema)
    def post(self, data):
        """Create a work order. With a sensor reading, its priority comes from the failure-prediction API."""
        return create_work_order(data)


@blp.route("/<int:order_id>")
class WorkOrderById(MethodView):
    @blp.response(200, WorkOrderSchema)
    def get(self, order_id):
        return get_or_404(WorkOrder, order_id, "Work order")

    @blp.arguments(WorkOrderUpdateSchema)
    @blp.response(200, WorkOrderSchema)
    def patch(self, data, order_id):
        """Update title/description or move status (open -> in_progress -> done). Invalid moves are 409."""
        return update_work_order(get_or_404(WorkOrder, order_id, "Work order"), data)

    @blp.response(204)
    def delete(self, order_id):
        db.session.delete(get_or_404(WorkOrder, order_id, "Work order"))
        db.session.commit()


@blp.route("/<int:order_id>/score", methods=["POST"])
@blp.response(200, WorkOrderSchema)
def rescore(order_id):
    """Ask the prediction service again, for example after it was unavailable."""
    order = get_or_404(WorkOrder, order_id, "Work order")
    score_work_order(order)
    db.session.commit()
    return order
