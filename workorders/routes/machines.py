from flask.views import MethodView
from flask_smorest import Blueprint
from sqlalchemy import select

from ..extensions import db
from ..models import Machine
from ..schemas import MachinePageSchema, MachineSchema, MachineUpdateSchema, PageQuerySchema
from ..services import delete_machine, get_or_404, paginate

blp = Blueprint("machines", __name__, url_prefix="/machines", description="Machines on the shop floor")


@blp.route("")
class Machines(MethodView):
    @blp.arguments(PageQuerySchema, location="query")
    @blp.response(200, MachinePageSchema)
    def get(self, args):
        """List machines (paginated)."""
        return paginate(select(Machine).order_by(Machine.id), args["page"], args["per_page"])

    @blp.arguments(MachineSchema)
    @blp.response(201, MachineSchema)
    def post(self, data):
        """Register a machine. Names are unique (409 on a duplicate)."""
        machine = Machine(**data)
        db.session.add(machine)
        db.session.commit()
        return machine


@blp.route("/<int:machine_id>")
class MachineById(MethodView):
    @blp.response(200, MachineSchema)
    def get(self, machine_id):
        return get_or_404(Machine, machine_id, "Machine")

    @blp.arguments(MachineUpdateSchema)
    @blp.response(200, MachineSchema)
    def patch(self, data, machine_id):
        machine = get_or_404(Machine, machine_id, "Machine")
        for field, value in data.items():
            setattr(machine, field, value)
        db.session.commit()
        return machine

    @blp.response(204)
    def delete(self, machine_id):
        """Delete a machine. Refused with 409 while it has unfinished work orders."""
        delete_machine(get_or_404(Machine, machine_id, "Machine"))
