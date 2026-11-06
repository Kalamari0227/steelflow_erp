"""Add retained, one-way reservation release without rewriting historical rows."""
from alembic import op

revision = 'ops_factory_fleet_release'
down_revision = 'ops_factory_v3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""ALTER TABLE factory_v3_reservations ADD COLUMN released_at_ms INTEGER DEFAULT NULL
CHECK(released_at_ms IS NULL OR (typeof(released_at_ms)='integer' AND released_at_ms BETWEEN 0 AND 4193483039999))""")
    for action in ('INSERT', 'UPDATE'):
        op.execute(f'DROP TRIGGER factory_v3_reservation_overlap_{action.lower()}')
        exclusion = 'AND NOT (reservation.run_id=OLD.run_id AND reservation.id=OLD.id)' if action == 'UPDATE' else ''
        op.execute(f"""CREATE TRIGGER factory_v3_reservation_overlap_{action.lower()} BEFORE {action} ON factory_v3_reservations
WHEN NEW.start_ms < MIN(NEW.end_ms,COALESCE(NEW.released_at_ms,NEW.end_ms))
AND EXISTS (SELECT 1 FROM factory_v3_reservations AS reservation
WHERE reservation.run_id=NEW.run_id AND reservation.resource_id=NEW.resource_id
AND reservation.start_ms < MIN(reservation.end_ms,COALESCE(reservation.released_at_ms,reservation.end_ms))
AND reservation.start_ms < MIN(NEW.end_ms,COALESCE(NEW.released_at_ms,NEW.end_ms))
AND NEW.start_ms < MIN(reservation.end_ms,COALESCE(reservation.released_at_ms,reservation.end_ms)) {exclusion})
BEGIN SELECT RAISE(ABORT,'factory reservation intervals overlap'); END""")
    op.execute("""CREATE TRIGGER factory_v3_reservation_immutable BEFORE UPDATE ON factory_v3_reservations
WHEN NEW.run_id IS NOT OLD.run_id OR NEW.id IS NOT OLD.id OR NEW.job_id IS NOT OLD.job_id
OR NEW.resource_id IS NOT OLD.resource_id OR NEW.start_ms IS NOT OLD.start_ms OR NEW.end_ms IS NOT OLD.end_ms
BEGIN SELECT RAISE(ABORT,'factory reservation identity and original window are immutable'); END""")
    op.execute("""CREATE TRIGGER factory_v3_reservation_release_one_way BEFORE UPDATE ON factory_v3_reservations
WHEN OLD.released_at_ms IS NOT NULL AND NEW.released_at_ms IS NOT OLD.released_at_ms
BEGIN SELECT RAISE(ABORT,'factory reservation release is one-way'); END""")
    op.execute("""CREATE TRIGGER factory_v3_reservation_no_delete BEFORE DELETE ON factory_v3_reservations
BEGIN SELECT RAISE(ABORT,'factory reservation history is retained'); END""")
    op.execute("""CREATE TRIGGER factory_v3_reservation_no_replace BEFORE INSERT ON factory_v3_reservations
WHEN EXISTS(SELECT 1 FROM factory_v3_reservations WHERE run_id=NEW.run_id AND id=NEW.id)
BEGIN SELECT RAISE(ABORT,'factory reservation identity is immutable'); END""")


class FleetReleaseDowngradeError(RuntimeError):
    """Dropping the release column would change retained occupancy history."""


def downgrade() -> None:
    raise FleetReleaseDowngradeError('Factory history is permanent; reservation release history requires restoring the preserved database instead.')
