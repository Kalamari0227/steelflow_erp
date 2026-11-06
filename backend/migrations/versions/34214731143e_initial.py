from alembic import op
import sqlalchemy as sa


revision = '34214731143e'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table('customers',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('country', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('locations',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('x', sa.Double(), nullable=False),
    sa.Column('y', sa.Double(), nullable=False),
    sa.Column('z', sa.Double(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('operation_events',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('scenario_id', sa.String(), nullable=False),
    sa.Column('run_id', sa.String(), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('entity_type', sa.String(), nullable=False),
    sa.Column('entity_id', sa.String(), nullable=False),
    sa.Column('event_type', sa.String(), nullable=False),
    sa.Column('occurred_at', sa.String(), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.CheckConstraint('sequence > 0'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('run_id', 'sequence')
    )
    op.create_table('simulation',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('scenario_id', sa.String(), nullable=False),
    sa.Column('run_id', sa.String(), nullable=False),
    sa.Column('tick', sa.Integer(), nullable=False),
    sa.Column('playing', sa.Boolean(), nullable=False),
    sa.Column('speed', sa.Integer(), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.CheckConstraint('id = 1'),
    sa.CheckConstraint('speed IN (1,2,4)'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('orders',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('customer_id', sa.String(), nullable=False),
    sa.Column('grade', sa.String(), nullable=False),
    sa.Column('quantity_kg', sa.Integer(), nullable=False),
    sa.Column('due_at', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.CheckConstraint('quantity_kg > 0'),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('production_lots',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('order_id', sa.String(), nullable=False),
    sa.Column('line_id', sa.String(), nullable=False),
    sa.Column('planned_kg', sa.Integer(), nullable=False),
    sa.Column('actual_kg', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.CheckConstraint('actual_kg >= 0 AND actual_kg <= planned_kg'),
    sa.ForeignKeyConstraint(['line_id'], ['locations.id'], ),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('shipments',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('order_id', sa.String(), nullable=False),
    sa.Column('mode', sa.String(), nullable=False),
    sa.Column('etd', sa.String(), nullable=False),
    sa.Column('eta', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('coils',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('lot_id', sa.String(), nullable=False),
    sa.Column('grade', sa.String(), nullable=False),
    sa.Column('width_mm', sa.Integer(), nullable=False),
    sa.Column('thickness_mm', sa.Double(), nullable=False),
    sa.Column('weight_kg', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.CheckConstraint('weight_kg > 0'),
    sa.ForeignKeyConstraint(['lot_id'], ['production_lots.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('inventory',
    sa.Column('coil_id', sa.String(), nullable=False),
    sa.Column('location_id', sa.String(), nullable=False),
    sa.Column('availability_status', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['coil_id'], ['coils.id'], ),
    sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ),
    sa.PrimaryKeyConstraint('coil_id')
    )
    op.create_table('shipment_coils',
    sa.Column('shipment_id', sa.String(), nullable=False),
    sa.Column('coil_id', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['coil_id'], ['coils.id'], ),
    sa.ForeignKeyConstraint(['shipment_id'], ['shipments.id'], ),
    sa.PrimaryKeyConstraint('shipment_id', 'coil_id'),
    sa.UniqueConstraint('coil_id')
    )
    op.execute("""CREATE TRIGGER events_no_update BEFORE UPDATE ON operation_events
        BEGIN SELECT RAISE(ABORT, 'operation events are append-only'); END""")
    op.execute("""CREATE TRIGGER events_no_delete BEFORE DELETE ON operation_events
        BEGIN SELECT RAISE(ABORT, 'operation events are append-only'); END""")
    op.execute("""CREATE TRIGGER events_order BEFORE INSERT ON operation_events
        WHEN NEW.sequence != COALESCE((SELECT MAX(sequence) FROM operation_events WHERE run_id=NEW.run_id), 0) + 1
        BEGIN SELECT RAISE(ABORT, 'event sequence must be contiguous'); END""")
    for operation in ('INSERT', 'UPDATE'):
        op.execute(f"""CREATE TRIGGER shipment_order_{operation.lower()} BEFORE {operation} ON shipment_coils
            WHEN (SELECT order_id FROM shipments WHERE id=NEW.shipment_id) !=
                 (SELECT production_lots.order_id FROM coils JOIN production_lots ON coils.lot_id=production_lots.id WHERE coils.id=NEW.coil_id)
            BEGIN SELECT RAISE(ABORT, 'shipment and coil must belong to the same order'); END""")
    op.execute("""CREATE TRIGGER shipment_order_immutable BEFORE UPDATE OF order_id ON shipments
        WHEN NEW.order_id != OLD.order_id AND EXISTS(SELECT 1 FROM shipment_coils WHERE shipment_id=OLD.id)
        BEGIN SELECT RAISE(ABORT, 'assigned shipment order is immutable'); END""")
    op.execute("""CREATE TRIGGER coil_lot_immutable BEFORE UPDATE OF lot_id ON coils
        WHEN NEW.lot_id != OLD.lot_id AND EXISTS(SELECT 1 FROM shipment_coils WHERE coil_id=OLD.id)
        BEGIN SELECT RAISE(ABORT, 'assigned coil lot is immutable'); END""")
    op.execute("""CREATE TRIGGER lot_order_immutable BEFORE UPDATE OF order_id ON production_lots
        WHEN NEW.order_id != OLD.order_id AND EXISTS(SELECT 1 FROM coils JOIN shipment_coils ON coils.id=shipment_coils.coil_id WHERE coils.lot_id=OLD.id)
        BEGIN SELECT RAISE(ABORT, 'assigned lot order is immutable'); END""")

def downgrade() -> None:
    op.drop_table('shipment_coils')
    op.drop_table('inventory')
    op.drop_table('coils')
    op.drop_table('shipments')
    op.drop_table('production_lots')
    op.drop_table('orders')
    op.drop_table('simulation')
    op.drop_table('operation_events')
    op.drop_table('locations')
    op.drop_table('customers')
