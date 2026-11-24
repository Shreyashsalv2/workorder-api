"""marshmallow schemas: request validation (unknown fields are rejected) and JSON output."""
from __future__ import annotations

from marshmallow import Schema, fields, validate

from .models import PRIORITIES, PRODUCT_TYPES, STATUSES


class MachineSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    product_type = fields.Str(required=True, validate=validate.OneOf(PRODUCT_TYPES),
                              metadata={"description": "Product quality variant: L, M or H"})
    location = fields.Str(load_default=None, allow_none=True, validate=validate.Length(max=100))
    created_at = fields.DateTime(dump_only=True)


class MachineUpdateSchema(Schema):
    name = fields.Str(validate=validate.Length(min=1, max=100))
    product_type = fields.Str(validate=validate.OneOf(PRODUCT_TYPES))
    location = fields.Str(allow_none=True, validate=validate.Length(max=100))


class SensorReadingSchema(Schema):
    """Physical sanity limits. The scoring service warns separately about values outside its training range."""

    air_temperature_k = fields.Float(required=True, validate=validate.Range(250, 350))
    process_temperature_k = fields.Float(required=True, validate=validate.Range(250, 380))
    rotational_speed_rpm = fields.Float(required=True, validate=validate.Range(0, 5000))
    torque_nm = fields.Float(required=True, validate=validate.Range(0, 150))
    tool_wear_min = fields.Float(required=True, validate=validate.Range(0, 400))


class WorkOrderCreateSchema(Schema):
    machine_id = fields.Int(required=True, validate=validate.Range(min=1))
    title = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    description = fields.Str(load_default=None, allow_none=True, validate=validate.Length(max=2000))
    reading = fields.Nested(SensorReadingSchema, load_default=None, allow_none=True)


class WorkOrderUpdateSchema(Schema):
    title = fields.Str(validate=validate.Length(min=1, max=200))
    description = fields.Str(allow_none=True, validate=validate.Length(max=2000))
    status = fields.Str(validate=validate.OneOf(STATUSES))


class WorkOrderSchema(Schema):
    id = fields.Int()
    machine_id = fields.Int()
    machine_name = fields.Function(lambda wo: wo.machine.name)
    title = fields.Str()
    description = fields.Str(allow_none=True)
    status = fields.Str()
    priority = fields.Str()
    reading = fields.Dict(allow_none=True)
    failure_probability = fields.Float(allow_none=True)
    scoring_note = fields.Str(allow_none=True)
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


class WorkOrderQuerySchema(Schema):
    status = fields.Str(validate=validate.OneOf(STATUSES))
    priority = fields.Str(validate=validate.OneOf(PRIORITIES))
    machine_id = fields.Int(validate=validate.Range(min=1))
    page = fields.Int(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Int(load_default=20, validate=validate.Range(min=1, max=100))


class PageSchema(Schema):
    page = fields.Int()
    per_page = fields.Int()
    total = fields.Int()


class WorkOrderPageSchema(PageSchema):
    items = fields.List(fields.Nested(WorkOrderSchema))


class MachinePageSchema(PageSchema):
    items = fields.List(fields.Nested(MachineSchema))


class PageQuerySchema(Schema):
    page = fields.Int(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Int(load_default=20, validate=validate.Range(min=1, max=100))
