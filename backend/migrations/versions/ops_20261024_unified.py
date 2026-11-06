# noqa: SIZE_OK -- one frozen additive revision must retain its complete schema and trigger definitions.
from alembic import op
import sqlalchemy as sa

revision = "ops_20261024_unified"
down_revision = "9db710a4c201"
branch_labels = None
depends_on = None

TABLES = (
    """CREATE TABLE operations_runs (
	id VARCHAR NOT NULL, 
	fixture_version VARCHAR NOT NULL, 
	seed INTEGER NOT NULL, 
	scenario_id VARCHAR NOT NULL, 
	elapsed_ms INTEGER NOT NULL, 
	duration_ms INTEGER NOT NULL, 
	revision INTEGER NOT NULL, 
	event_sequence INTEGER NOT NULL, 
	playing BOOLEAN NOT NULL, 
	speed INTEGER NOT NULL, 
	epoch_at VARCHAR NOT NULL, 
	started_at VARCHAR NOT NULL, 
	plan_revision INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (scenario_id IN ('NORMAL','DELAY','RECOVERY')), 
	CHECK (fixture_version = 'erp-v1'), 
	CHECK (typeof(seed) = 'integer' AND seed BETWEEN 0 AND 9007199254740991), 
	CHECK (typeof(elapsed_ms) = 'integer' AND elapsed_ms BETWEEN 0 AND 9007199254740991), 
	CHECK (typeof(duration_ms) = 'integer' AND duration_ms BETWEEN 1 AND 9007199254740991), 
	CHECK (typeof(revision) = 'integer' AND revision BETWEEN 0 AND 9007199254740991), 
	CHECK (typeof(event_sequence) = 'integer' AND event_sequence BETWEEN 0 AND 9007199254740991), 
	CHECK (typeof(plan_revision) = 'integer' AND plan_revision BETWEEN 0 AND 9007199254740991), 
	CHECK (playing IN (0,1)), 
	CHECK (speed IN (1,2,4)), 
	CHECK (elapsed_ms <= duration_ms), 
	CHECK (epoch_at IN ('2026-10-30T00:00:00Z','2026-10-30T00:00:00+00:00'))
)""",
    """CREATE TABLE operations_current_run (
	id INTEGER NOT NULL, 
	run_id VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (id = 1), 
	FOREIGN KEY(run_id) REFERENCES operations_runs (id)
)""",
    """CREATE TABLE operations_orders (
	customer_id VARCHAR NOT NULL, 
	product_id VARCHAR NOT NULL, 
	grade VARCHAR NOT NULL, 
	width_mm DOUBLE, 
	thickness_mm DOUBLE, 
	quantity_kg INTEGER NOT NULL, 
	due_at VARCHAR NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	CHECK (product_id IN ('slab','bloom','billet','hr','plate','wire','cr','gi','ga','hgi','eg','go','ngo','sts-hr','sts-cr','sts-plate','ti-hr','ti-cr','ti-sheet','ti-plate')), 
	CHECK (typeof(quantity_kg) = 'integer' AND quantity_kg BETWEEN 1 AND 9007199254740991), 
	CHECK (width_mm IS NULL OR (width_mm > 0 AND width_mm < 1e308)), 
	CHECK (thickness_mm IS NULL OR (thickness_mm > 0 AND thickness_mm < 1e308)), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(run_id) REFERENCES operations_runs (id)
)""",
    """CREATE TABLE work_orders (
	order_id VARCHAR NOT NULL, 
	route_id VARCHAR NOT NULL, 
	route_version INTEGER NOT NULL, 
	planned_kg INTEGER NOT NULL, 
	status VARCHAR NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, order_id) REFERENCES operations_orders (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (typeof(route_version) = 'integer' AND route_version BETWEEN 1 AND 9007199254740991), 
	CHECK (typeof(planned_kg) = 'integer' AND planned_kg BETWEEN 1 AND 9007199254740991), 
	CHECK (status IN ('PLANNED','RELEASED','COMPLETED')), 
	UNIQUE (run_id, id, order_id), 
	FOREIGN KEY(run_id) REFERENCES operations_runs (id)
)""",
    """CREATE TABLE operations_lots (
	work_order_id VARCHAR NOT NULL, 
	planned_kg INTEGER NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, work_order_id) REFERENCES work_orders (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (typeof(planned_kg) = 'integer' AND planned_kg BETWEEN 1 AND 9007199254740991), 
	FOREIGN KEY(run_id) REFERENCES operations_runs (id)
)""",
    """CREATE TABLE materials (
	lot_id VARCHAR NOT NULL, 
	lineage_id VARCHAR NOT NULL, 
	current_version_id VARCHAR NOT NULL, 
	form VARCHAR NOT NULL, 
	weight_kg INTEGER NOT NULL, 
	location_id VARCHAR NOT NULL, 
	quality_status VARCHAR NOT NULL, 
	availability_status VARCHAR NOT NULL, 
	active BOOLEAN NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, lot_id) REFERENCES operations_lots (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (typeof(weight_kg) = 'integer' AND weight_kg BETWEEN 1 AND 9007199254740991), 
	CHECK (form IN ('ORE','HOT_METAL','LIQUID_STEEL','SCRAP','SLAB','BLOOM','BILLET','HOT_SLAB','HOT_BLOOM','HOT_BILLET','HOT_STRIP','HOT_PLATE','STRIP','THIN_STRIP','COATED_STRIP','HR_COIL','CR_COIL','GI_COIL','GA_COIL','HGI_COIL','EG_COIL','GO_COIL','NGO_COIL','WIRE','WIRE_COIL','PLATE','STS_HR_COIL','STS_CR_COIL','STS_PLATE','TI_INGOT','TI_SLAB','TI_HR_COIL','TI_CR_COIL','TI_SHEET','TI_PLATE')), 
	CHECK (quality_status IN ('PENDING','PASSED','HOLD','FAILED')), 
	CHECK (availability_status IN ('WIP','QUARANTINED','AVAILABLE','RESERVED','SHIPPED','CONSUMED')), 
	CHECK (active IN (0,1) AND active = (availability_status != 'CONSUMED')), 
	CONSTRAINT fk_material_current_version FOREIGN KEY(run_id, current_version_id, id, form, weight_kg) REFERENCES material_versions (run_id, id, material_id, form, weight_kg) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(location_id) REFERENCES locations (id), 
	FOREIGN KEY(run_id) REFERENCES operations_runs (id)
)""",
    """CREATE TABLE material_versions (
	material_id VARCHAR NOT NULL, 
	ordinal INTEGER NOT NULL, 
	parent_version_id VARCHAR, 
	form VARCHAR NOT NULL, 
	weight_kg INTEGER NOT NULL, 
	cause_event_id VARCHAR, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, material_id) REFERENCES materials (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, cause_event_id) REFERENCES operation_events (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, parent_version_id) REFERENCES material_versions (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	UNIQUE (run_id, material_id, ordinal), 
	UNIQUE (run_id, id, material_id), 
	UNIQUE (run_id, id, material_id, form, weight_kg), 
	CHECK (typeof(ordinal) = 'integer' AND ordinal BETWEEN 1 AND 9007199254740991), 
	CHECK (typeof(weight_kg) = 'integer' AND weight_kg BETWEEN 1 AND 9007199254740991), 
	CHECK (form IN ('ORE','HOT_METAL','LIQUID_STEEL','SCRAP','SLAB','BLOOM','BILLET','HOT_SLAB','HOT_BLOOM','HOT_BILLET','HOT_STRIP','HOT_PLATE','STRIP','THIN_STRIP','COATED_STRIP','HR_COIL','CR_COIL','GI_COIL','GA_COIL','HGI_COIL','EG_COIL','GO_COIL','NGO_COIL','WIRE','WIRE_COIL','PLATE','STS_HR_COIL','STS_CR_COIL','STS_PLATE','TI_INGOT','TI_SLAB','TI_HR_COIL','TI_CR_COIL','TI_SHEET','TI_PLATE')), 
	CHECK (parent_version_id IS NULL OR parent_version_id != id), 
	FOREIGN KEY(run_id) REFERENCES operations_runs (id)
)""",
    """CREATE TABLE process_executions (
	material_id VARCHAR NOT NULL, 
	route_step_id VARCHAR NOT NULL, 
	source_step_id VARCHAR NOT NULL, 
	step_ordinal INTEGER NOT NULL, 
	equipment_id VARCHAR NOT NULL, 
	predecessor_id VARCHAR, 
	status VARCHAR NOT NULL, 
	planned_duration_ms INTEGER NOT NULL, 
	ready_at_ms INTEGER NOT NULL, 
	start_ms INTEGER, 
	end_ms INTEGER, 
	input_form VARCHAR NOT NULL, 
	output_form VARCHAR NOT NULL, 
	additions_kg INTEGER NOT NULL, 
	loss_kg INTEGER NOT NULL, 
	split_count INTEGER NOT NULL, 
	blocked_reason VARCHAR, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, material_id) REFERENCES materials (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, predecessor_id) REFERENCES process_executions (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (status IN ('QUEUED','RUNNING','BLOCKED','COMPLETED')), 
	CHECK (input_form IN ('ORE','HOT_METAL','LIQUID_STEEL','SCRAP','SLAB','BLOOM','BILLET','HOT_SLAB','HOT_BLOOM','HOT_BILLET','HOT_STRIP','HOT_PLATE','STRIP','THIN_STRIP','COATED_STRIP','HR_COIL','CR_COIL','GI_COIL','GA_COIL','HGI_COIL','EG_COIL','GO_COIL','NGO_COIL','WIRE','WIRE_COIL','PLATE','STS_HR_COIL','STS_CR_COIL','STS_PLATE','TI_INGOT','TI_SLAB','TI_HR_COIL','TI_CR_COIL','TI_SHEET','TI_PLATE')), 
	CHECK (output_form IN ('ORE','HOT_METAL','LIQUID_STEEL','SCRAP','SLAB','BLOOM','BILLET','HOT_SLAB','HOT_BLOOM','HOT_BILLET','HOT_STRIP','HOT_PLATE','STRIP','THIN_STRIP','COATED_STRIP','HR_COIL','CR_COIL','GI_COIL','GA_COIL','HGI_COIL','EG_COIL','GO_COIL','NGO_COIL','WIRE','WIRE_COIL','PLATE','STS_HR_COIL','STS_CR_COIL','STS_PLATE','TI_INGOT','TI_SLAB','TI_HR_COIL','TI_CR_COIL','TI_SHEET','TI_PLATE')), 
	CHECK (typeof(step_ordinal) = 'integer' AND step_ordinal BETWEEN 0 AND 9007199254740991), 
	CHECK (typeof(planned_duration_ms) = 'integer' AND planned_duration_ms BETWEEN 1 AND 9007199254740991), 
	CHECK (typeof(ready_at_ms) = 'integer' AND ready_at_ms BETWEEN 0 AND 9007199254740991), 
	CHECK (start_ms IS NULL OR (typeof(start_ms)='integer' AND start_ms >= 0)), 
	CHECK (end_ms IS NULL OR (typeof(end_ms)='integer' AND end_ms >= 0)), 
	CHECK (end_ms IS NULL OR start_ms IS NULL OR end_ms > start_ms), 
	CHECK (status NOT IN ('RUNNING','COMPLETED') OR (start_ms IS NOT NULL AND end_ms IS NOT NULL)), 
	CHECK (typeof(additions_kg) = 'integer' AND additions_kg BETWEEN 0 AND 9007199254740991), 
	CHECK (typeof(loss_kg) = 'integer' AND loss_kg BETWEEN 0 AND 9007199254740991), 
	CHECK (split_count IN (1,2)), 
	CHECK (predecessor_id IS NULL OR predecessor_id != id), 
	FOREIGN KEY(run_id) REFERENCES operations_runs (id)
)""",
    """CREATE TABLE material_lineage_edges (
	parent_material_id VARCHAR NOT NULL, 
	child_material_id VARCHAR NOT NULL, 
	process_id VARCHAR NOT NULL, 
	transferred_kg INTEGER NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, parent_material_id) REFERENCES materials (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, child_material_id) REFERENCES materials (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, process_id) REFERENCES process_executions (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	UNIQUE (run_id, parent_material_id, child_material_id), 
	CHECK (parent_material_id != child_material_id), 
	CHECK (typeof(transferred_kg) = 'integer' AND transferred_kg BETWEEN 1 AND 9007199254740991), 
	FOREIGN KEY(run_id) REFERENCES operations_runs (id)
)""",
    """CREATE TABLE material_allocations (
	order_id VARCHAR NOT NULL, 
	work_order_id VARCHAR NOT NULL, 
	material_id VARCHAR NOT NULL, 
	final_planned_kg INTEGER NOT NULL, 
	active BOOLEAN NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, order_id) REFERENCES operations_orders (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, material_id) REFERENCES materials (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, work_order_id, order_id) REFERENCES work_orders (run_id, id, order_id) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (typeof(final_planned_kg) = 'integer' AND final_planned_kg BETWEEN 1 AND 9007199254740991), 
	CHECK (active IN (0,1)), 
	FOREIGN KEY(run_id) REFERENCES operations_runs (id)
)""",
    """CREATE TABLE transfers (
	material_id VARCHAR NOT NULL, 
	from_location_id VARCHAR NOT NULL, 
	to_location_id VARCHAR NOT NULL, 
	mode VARCHAR NOT NULL, 
	vehicle_id VARCHAR, 
	crane_id VARCHAR, 
	status VARCHAR NOT NULL, 
	phase_start_ms INTEGER, 
	phase_end_ms INTEGER, 
	capacity_kg INTEGER NOT NULL, 
	process_id VARCHAR, 
	travel_duration_ms INTEGER NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, material_id) REFERENCES materials (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, process_id) REFERENCES process_executions (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (mode IN ('roller','flatbed','hot_metal_car','ladle_car')), 
	CHECK (status IN ('WAITING','LOADING','IN_TRANSIT','UNLOADING','ARRIVED')), 
	CHECK (mode = 'roller' OR vehicle_id IS NOT NULL), 
	CHECK (typeof(capacity_kg) = 'integer' AND capacity_kg BETWEEN 1 AND 9007199254740991), 
	CHECK (typeof(travel_duration_ms) = 'integer' AND travel_duration_ms BETWEEN 1 AND 9007199254740991), 
	CHECK (phase_start_ms IS NULL OR (typeof(phase_start_ms)='integer' AND phase_start_ms >= 0)), 
	CHECK (phase_end_ms IS NULL OR (typeof(phase_end_ms)='integer' AND phase_end_ms >= 0)), 
	CHECK (phase_start_ms IS NULL OR phase_end_ms IS NULL OR phase_end_ms > phase_start_ms), 
	FOREIGN KEY(from_location_id) REFERENCES locations (id), 
	FOREIGN KEY(to_location_id) REFERENCES locations (id), 
	FOREIGN KEY(run_id) REFERENCES operations_runs (id)
)""",
    """CREATE TABLE inspections (
	material_id VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	inspected_version_id VARCHAR NOT NULL, 
	reason VARCHAR, 
	release_event_id VARCHAR, 
	start_ms INTEGER, 
	end_ms INTEGER, 
	packaging_end_ms INTEGER, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, material_id) REFERENCES materials (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, release_event_id) REFERENCES operation_events (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, inspected_version_id, material_id) REFERENCES material_versions (run_id, id, material_id) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (status IN ('PENDING','PASSED','HOLD','FAILED')), 
	FOREIGN KEY(run_id) REFERENCES operations_runs (id)
)""",
    """CREATE TABLE operations_shipments (
	order_id VARCHAR NOT NULL, 
	mode VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	location_id VARCHAR NOT NULL, 
	capacity_kg INTEGER NOT NULL, 
	etd_at VARCHAR, 
	eta_at VARCHAR, 
	phase_start_ms INTEGER, 
	phase_end_ms INTEGER, 
	delivered_at VARCHAR, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, order_id) REFERENCES operations_orders (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (mode IN ('SEA','ROAD')), 
	CHECK (status IN ('PLANNED','ALLOCATED','LOADING','LOADED','DISPATCHED','AT_PORT','IN_TRANSIT','DELIVERED')), 
	CHECK (typeof(capacity_kg) = 'integer' AND capacity_kg BETWEEN 1 AND 9007199254740991), 
	FOREIGN KEY(location_id) REFERENCES locations (id), 
	FOREIGN KEY(run_id) REFERENCES operations_runs (id)
)""",
    """CREATE TABLE shipment_materials (
	shipment_id VARCHAR NOT NULL, 
	material_id VARCHAR NOT NULL, 
	active BOOLEAN NOT NULL, 
	loaded BOOLEAN NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, shipment_id) REFERENCES operations_shipments (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, material_id) REFERENCES materials (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (active IN (0,1)), 
	CHECK (loaded IN (0,1)), 
	FOREIGN KEY(run_id) REFERENCES operations_runs (id)
)""",
    """CREATE TABLE mass_movements (
	cause_event_id VARCHAR NOT NULL, 
	process_id VARCHAR NOT NULL, 
	input_material_ids JSON NOT NULL, 
	output_material_ids JSON NOT NULL, 
	input_kg INTEGER NOT NULL, 
	output_kg INTEGER NOT NULL, 
	additions_kg INTEGER NOT NULL, 
	loss_kg INTEGER NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, cause_event_id) REFERENCES operation_events (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, process_id) REFERENCES process_executions (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	UNIQUE (run_id, process_id), 
	CHECK (typeof(input_kg) = 'integer' AND input_kg BETWEEN 0 AND 9007199254740991), 
	CHECK (typeof(output_kg) = 'integer' AND output_kg BETWEEN 0 AND 9007199254740991), 
	CHECK (typeof(additions_kg) = 'integer' AND additions_kg BETWEEN 0 AND 9007199254740991), 
	CHECK (typeof(loss_kg) = 'integer' AND loss_kg BETWEEN 0 AND 9007199254740991), 
	CHECK (input_kg + additions_kg = output_kg + loss_kg), 
	CHECK (json_valid(input_material_ids) AND json_type(input_material_ids) = 'array'), 
	CHECK (json_valid(output_material_ids) AND json_type(output_material_ids) = 'array'), 
	FOREIGN KEY(run_id) REFERENCES operations_runs (id)
)""",
    """CREATE TABLE command_receipts (
	run_id VARCHAR NOT NULL, 
	command_id VARCHAR NOT NULL, 
	action VARCHAR NOT NULL, 
	payload_digest VARCHAR NOT NULL, 
	applied_revision INTEGER NOT NULL, 
	PRIMARY KEY (run_id, command_id), 
	CHECK (action IN ('play','pause','reset','step','speed','scenario')), 
	CHECK (typeof(applied_revision) = 'integer' AND applied_revision BETWEEN 0 AND 9007199254740991), 
	CHECK (length(payload_digest) = 64 AND payload_digest NOT GLOB '*[^0-9a-f]*'), 
	FOREIGN KEY(run_id) REFERENCES operations_runs (id)
)""",
)
INDEXES = (
    "CREATE UNIQUE INDEX uq_material_active_allocation ON material_allocations (run_id, material_id) WHERE active = 1",
    "CREATE UNIQUE INDEX uq_material_active_transfer ON transfers (run_id, material_id) WHERE status != 'ARRIVED'",
    "CREATE UNIQUE INDEX uq_material_active_shipment ON shipment_materials (run_id, material_id) WHERE active = 1",
    "CREATE UNIQUE INDEX uq_operation_event_run_id ON operation_events (run_id, id)",
)
TRIGGERS = (
    """CREATE TRIGGER ops_lineage_no_cycle_insert BEFORE INSERT ON material_lineage_edges
WHEN EXISTS (
    WITH RECURSIVE descendants(id) AS (
        SELECT NEW.child_material_id
        UNION
        SELECT edge.child_material_id FROM material_lineage_edges AS edge
        JOIN descendants ON edge.parent_material_id = descendants.id
        WHERE edge.run_id = NEW.run_id 
    )
    SELECT 1 FROM descendants WHERE id = NEW.parent_material_id
)
BEGIN SELECT RAISE(ABORT, 'material lineage must be acyclic'); END""",
    """CREATE TRIGGER ops_allocation_order_insert BEFORE INSERT ON material_allocations
WHEN NOT EXISTS (
    SELECT 1 FROM materials AS material
    JOIN operations_lots AS lot ON lot.run_id = material.run_id AND lot.id = material.lot_id
    WHERE material.run_id = NEW.run_id AND material.id = NEW.material_id AND lot.work_order_id = NEW.work_order_id
)
BEGIN SELECT RAISE(ABORT, 'allocation must match material work order'); END""",
    """CREATE TRIGGER ops_shipment_order_insert BEFORE INSERT ON shipment_materials
WHEN NEW.active = 1 AND NOT EXISTS (
    SELECT 1 FROM material_allocations AS allocation
    JOIN operations_shipments AS shipment ON shipment.run_id = allocation.run_id AND shipment.order_id = allocation.order_id
    WHERE allocation.run_id = NEW.run_id AND allocation.material_id = NEW.material_id
      AND allocation.active = 1 AND shipment.id = NEW.shipment_id
)
BEGIN SELECT RAISE(ABORT, 'shipment must match active material order allocation'); END""",
    """CREATE TRIGGER ops_mass_materials_insert BEFORE INSERT ON mass_movements
WHEN EXISTS (
    SELECT 1 FROM json_each(NEW.input_material_ids) AS item
    WHERE item.type != 'text' OR NOT EXISTS (SELECT 1 FROM materials WHERE run_id = NEW.run_id AND id = item.value)
) OR EXISTS (
    SELECT 1 FROM json_each(NEW.output_material_ids) AS item
    WHERE item.type != 'text' OR NOT EXISTS (SELECT 1 FROM materials WHERE run_id = NEW.run_id AND id = item.value)
) OR (SELECT count(*) FROM json_each(NEW.input_material_ids)) != (SELECT count(DISTINCT value) FROM json_each(NEW.input_material_ids))
  OR (SELECT count(*) FROM json_each(NEW.output_material_ids)) != (SELECT count(DISTINCT value) FROM json_each(NEW.output_material_ids))
  OR json_array_length(NEW.input_material_ids) = 0 OR json_array_length(NEW.output_material_ids) = 0
BEGIN SELECT RAISE(ABORT, 'mass movement requires distinct same-run materials'); END""",
    """CREATE TRIGGER ops_lineage_no_cycle_update BEFORE UPDATE ON material_lineage_edges
WHEN EXISTS (
    WITH RECURSIVE descendants(id) AS (
        SELECT NEW.child_material_id
        UNION
        SELECT edge.child_material_id FROM material_lineage_edges AS edge
        JOIN descendants ON edge.parent_material_id = descendants.id
        WHERE edge.run_id = NEW.run_id AND NOT (edge.run_id = OLD.run_id AND edge.id = OLD.id)
    )
    SELECT 1 FROM descendants WHERE id = NEW.parent_material_id
)
BEGIN SELECT RAISE(ABORT, 'material lineage must be acyclic'); END""",
    """CREATE TRIGGER ops_allocation_order_update BEFORE UPDATE ON material_allocations
WHEN NOT EXISTS (
    SELECT 1 FROM materials AS material
    JOIN operations_lots AS lot ON lot.run_id = material.run_id AND lot.id = material.lot_id
    WHERE material.run_id = NEW.run_id AND material.id = NEW.material_id AND lot.work_order_id = NEW.work_order_id
)
BEGIN SELECT RAISE(ABORT, 'allocation must match material work order'); END""",
    """CREATE TRIGGER ops_shipment_order_update BEFORE UPDATE ON shipment_materials
WHEN NEW.active = 1 AND NOT EXISTS (
    SELECT 1 FROM material_allocations AS allocation
    JOIN operations_shipments AS shipment ON shipment.run_id = allocation.run_id AND shipment.order_id = allocation.order_id
    WHERE allocation.run_id = NEW.run_id AND allocation.material_id = NEW.material_id
      AND allocation.active = 1 AND shipment.id = NEW.shipment_id
)
BEGIN SELECT RAISE(ABORT, 'shipment must match active material order allocation'); END""",
    """CREATE TRIGGER ops_mass_materials_update BEFORE UPDATE ON mass_movements
WHEN EXISTS (
    SELECT 1 FROM json_each(NEW.input_material_ids) AS item
    WHERE item.type != 'text' OR NOT EXISTS (SELECT 1 FROM materials WHERE run_id = NEW.run_id AND id = item.value)
) OR EXISTS (
    SELECT 1 FROM json_each(NEW.output_material_ids) AS item
    WHERE item.type != 'text' OR NOT EXISTS (SELECT 1 FROM materials WHERE run_id = NEW.run_id AND id = item.value)
) OR (SELECT count(*) FROM json_each(NEW.input_material_ids)) != (SELECT count(DISTINCT value) FROM json_each(NEW.input_material_ids))
  OR (SELECT count(*) FROM json_each(NEW.output_material_ids)) != (SELECT count(DISTINCT value) FROM json_each(NEW.output_material_ids))
  OR json_array_length(NEW.input_material_ids) = 0 OR json_array_length(NEW.output_material_ids) = 0
BEGIN SELECT RAISE(ABORT, 'mass movement requires distinct same-run materials'); END""",
    """CREATE TRIGGER ops_assigned_shipment_order BEFORE UPDATE OF order_id, run_id ON operations_shipments
WHEN (NEW.order_id != OLD.order_id OR NEW.run_id != OLD.run_id) AND EXISTS (
    SELECT 1 FROM shipment_materials WHERE run_id = OLD.run_id AND shipment_id = OLD.id AND active = 1
)
BEGIN SELECT RAISE(ABORT, 'assigned shipment order is immutable'); END""",
    """CREATE TRIGGER ops_shipped_allocation_update BEFORE UPDATE ON material_allocations
WHEN OLD.active = 1 AND (NEW.active != 1 OR NEW.order_id != OLD.order_id OR NEW.material_id != OLD.material_id OR NEW.run_id != OLD.run_id)
AND EXISTS (SELECT 1 FROM shipment_materials WHERE run_id = OLD.run_id AND material_id = OLD.material_id AND active = 1)
BEGIN SELECT RAISE(ABORT, 'shipped material allocation is immutable'); END""",
    """CREATE TRIGGER ops_shipped_allocation_delete BEFORE DELETE ON material_allocations
WHEN OLD.active = 1 AND EXISTS (
    SELECT 1 FROM shipment_materials WHERE run_id = OLD.run_id AND material_id = OLD.material_id AND active = 1
)
BEGIN SELECT RAISE(ABORT, 'shipped material allocation is immutable'); END""",
    """CREATE TRIGGER ops_allocated_material_lot BEFORE UPDATE OF lot_id, run_id ON materials
WHEN (NEW.lot_id != OLD.lot_id OR NEW.run_id != OLD.run_id) AND EXISTS (
    SELECT 1 FROM material_allocations WHERE run_id = OLD.run_id AND material_id = OLD.id
)
BEGIN SELECT RAISE(ABORT, 'allocated material lot is immutable'); END""",
    """CREATE TRIGGER ops_allocated_lot_work_order BEFORE UPDATE OF work_order_id, run_id ON operations_lots
WHEN (NEW.work_order_id != OLD.work_order_id OR NEW.run_id != OLD.run_id) AND EXISTS (
    SELECT 1 FROM materials AS material JOIN material_allocations AS allocation
      ON material.run_id = allocation.run_id AND material.id = allocation.material_id
    WHERE material.run_id = OLD.run_id AND material.lot_id = OLD.id
)
BEGIN SELECT RAISE(ABORT, 'allocated lot work order is immutable'); END""",
)


def upgrade() -> None:
    op.add_column("operation_events", sa.Column("recorded_at", sa.String(), nullable=True))
    for statement in TABLES + INDEXES + TRIGGERS:
        op.execute(statement)


def downgrade() -> None:
    for table in ['command_receipts','mass_movements','shipment_materials','operations_shipments','inspections','transfers','material_allocations','material_lineage_edges','process_executions','material_versions','materials','operations_lots','work_orders','operations_orders','operations_current_run','operations_runs']:
        op.drop_table(table)
    op.drop_index("uq_operation_event_run_id", table_name="operation_events")
    op.drop_column("operation_events", "recorded_at")

