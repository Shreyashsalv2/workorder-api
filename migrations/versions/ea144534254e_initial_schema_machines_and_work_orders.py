"""initial schema: machines and work orders

Revision ID: ea144534254e
Revises: 
Create Date: 2026-11-25 03:12:51.321002

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ea144534254e'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('machines',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('product_type', sa.String(length=1), nullable=False),
    sa.Column('location', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.CheckConstraint("product_type IN ('L','M','H')", name='ck_machine_type'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('work_orders',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('machine_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.String(length=2000), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('priority', sa.String(length=20), nullable=False),
    sa.Column('air_temperature_k', sa.Double(), nullable=True),
    sa.Column('process_temperature_k', sa.Double(), nullable=True),
    sa.Column('rotational_speed_rpm', sa.Double(), nullable=True),
    sa.Column('torque_nm', sa.Double(), nullable=True),
    sa.Column('tool_wear_min', sa.Double(), nullable=True),
    sa.Column('failure_probability', sa.Double(), nullable=True),
    sa.Column('scoring_note', sa.String(length=300), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['machine_id'], ['machines.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('work_orders', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_work_orders_machine_id'), ['machine_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_work_orders_priority'), ['priority'], unique=False)
        batch_op.create_index(batch_op.f('ix_work_orders_status'), ['status'], unique=False)


def downgrade():
    # Dropping the table drops its indexes too. Dropping the machine_id index first fails on MySQL,
    # which keeps that index for the foreign key.
    op.drop_table('work_orders')
    op.drop_table('machines')
