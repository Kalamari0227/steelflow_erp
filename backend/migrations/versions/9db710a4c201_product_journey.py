from alembic import op
import sqlalchemy as sa

revision = "9db710a4c201"
down_revision = "34214731143e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("journey_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("elapsed_ms", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("playing", sa.Boolean(), nullable=False),
        sa.Column("speed", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.CheckConstraint("id = 1"), sa.CheckConstraint("speed IN (1,2,4)"),
        sa.CheckConstraint("elapsed_ms >= 0 AND elapsed_ms <= duration_ms"),
        sa.CheckConstraint("duration_ms > 0"), sa.CheckConstraint("revision >= 0"))
    op.create_table("journey_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("step_id", sa.String(), nullable=False),
        sa.Column("elapsed_ms", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.String(), nullable=False),
        sa.UniqueConstraint("run_id", "sequence"), sa.CheckConstraint("sequence > 0"),
        sa.CheckConstraint("elapsed_ms >= 0"))
    for action in ("UPDATE", "DELETE"):
        op.execute(f"CREATE TRIGGER journey_no_{action.lower()} BEFORE {action} ON journey_events BEGIN SELECT RAISE(ABORT, 'journey events are append-only'); END")
    op.execute("""CREATE TRIGGER journey_event_order BEFORE INSERT ON journey_events
        WHEN NEW.sequence != COALESCE((SELECT MAX(sequence) FROM journey_events WHERE run_id=NEW.run_id), 0) + 1
        BEGIN SELECT RAISE(ABORT, 'journey event sequence must be contiguous'); END""")


def downgrade() -> None:
    op.drop_table("journey_events")
    op.drop_table("journey_state")
