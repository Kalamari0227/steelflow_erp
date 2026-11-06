"""Add one-time physical consumption and retain immutable batch history."""
from alembic import op

revision = 'ops_factory_batch_guards'
down_revision = 'ops_factory_fleet_release'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE UNIQUE INDEX factory_v3_one_version_consumption
ON factory_v3_batch_io(run_id,material_version_id)
WHERE role IN ('INPUT','STOCK_ADDITION') AND material_version_id IS NOT NULL""")
    collision_keys = {
        'material_versions': 'id=NEW.id OR (material_id=NEW.material_id AND ordinal=NEW.ordinal)',
        'version_edges': 'id=NEW.id OR (batch_id=NEW.batch_id AND input_version_id=NEW.input_version_id AND output_version_id=NEW.output_version_id)',
        'batch_io': """id=NEW.id
OR (NEW.source_id IS NOT NULL AND source_id=NEW.source_id)
OR (NEW.material_version_id IS NOT NULL AND material_version_id=NEW.material_version_id
 AND ((batch_id=NEW.batch_id AND role=NEW.role)
 OR (role IN ('INPUT','STOCK_ADDITION') AND NEW.role IN ('INPUT','STOCK_ADDITION'))))""",
    }
    for table, collision in collision_keys.items():
        for action in ('UPDATE', 'DELETE'):
            op.execute(f"""CREATE TRIGGER factory_v3_{table}_immutable_{action.lower()}
BEFORE {action} ON factory_v3_{table}
BEGIN SELECT RAISE(ABORT,'factory batch history is immutable'); END""")
        op.execute(f"""CREATE TRIGGER factory_v3_{table}_no_replace
BEFORE INSERT ON factory_v3_{table}
WHEN EXISTS(SELECT 1 FROM factory_v3_{table} WHERE run_id=NEW.run_id AND ({collision}))
BEGIN SELECT RAISE(ABORT,'factory batch history identity is immutable'); END""")
    for action in ('UPDATE', 'DELETE'):
        op.execute(f"""CREATE TRIGGER factory_v3_completed_batch_{action.lower()}
BEFORE {action} ON factory_v3_process_batches WHEN OLD.status='COMPLETED'
BEGIN SELECT RAISE(ABORT,'factory completed batch is immutable'); END""")
    op.execute("""CREATE TRIGGER factory_v3_completed_batch_no_replace
BEFORE INSERT ON factory_v3_process_batches
WHEN EXISTS(SELECT 1 FROM factory_v3_process_batches WHERE run_id=NEW.run_id AND id=NEW.id AND status='COMPLETED')
BEGIN SELECT RAISE(ABORT,'factory completed batch identity is immutable'); END""")


class BatchHistoryDowngradeError(RuntimeError):
    """Removing guards would permit rewriting retained physical provenance."""


def downgrade() -> None:
    raise BatchHistoryDowngradeError('Factory history is permanent; batch guards require restoring the preserved database instead.')
