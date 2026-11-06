"""Additive factory schema; restore a preserved database to roll back."""
# noqa: SIZE_OK -- frozen migration DDL must not import evolving application models.
from alembic import op

revision = "ops_factory_v3"
down_revision = "ops_20261024_unified"
branch_labels = None
depends_on = None

TABLES = (
    """CREATE TABLE factory_v3_active_writer (
	id INTEGER NOT NULL, 
	run_id VARCHAR NOT NULL, 
	bootstrap_mode VARCHAR NOT NULL, 
	activation_generation INTEGER NOT NULL, 
	legacy_write_locked BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (id=1), 
	CHECK (bootstrap_mode IN ('canonical','legacy_fixture','v3_contract_test')), 
	CHECK (activation_generation IS NULL OR (typeof(activation_generation)='integer' AND activation_generation BETWEEN 1 AND 9007199254740991)), 
	CHECK (legacy_write_locked IN (0,1)), 
	CHECK ((legacy_write_locked=0 AND bootstrap_mode='legacy_fixture') OR (legacy_write_locked=1 AND bootstrap_mode!='legacy_fixture')), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_run_registry (run_id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_allocations (
	material_id VARCHAR NOT NULL, 
	order_id VARCHAR NOT NULL, 
	work_order_id VARCHAR NOT NULL, 
	quantity_kg INTEGER NOT NULL, 
	active BOOLEAN NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, material_id) REFERENCES factory_v3_materials (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, order_id) REFERENCES factory_v3_orders (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, work_order_id, order_id) REFERENCES factory_v3_work_orders (run_id, id, order_id) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (quantity_kg IS NULL OR (typeof(quantity_kg)='integer' AND quantity_kg BETWEEN 1 AND 9007199254740991)), 
	CHECK (active IN (0,1)), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_attachments (
	material_id VARCHAR NOT NULL, 
	kind VARCHAR NOT NULL, 
	owner_id VARCHAR NOT NULL, 
	socket_id VARCHAR NOT NULL, 
	acquired_at_ms INTEGER NOT NULL, 
	released_at_ms INTEGER, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, material_id) REFERENCES factory_v3_materials (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (kind IN ('slot','equipment','hook','vehicle','railcar','ship','customer')), 
	CHECK (acquired_at_ms IS NULL OR (typeof(acquired_at_ms)='integer' AND acquired_at_ms BETWEEN 0 AND 4193483039999)), 
	CHECK (released_at_ms IS NULL OR (typeof(released_at_ms)='integer' AND released_at_ms BETWEEN 0 AND 4193483039999)), 
	CHECK (released_at_ms IS NULL OR released_at_ms>=acquired_at_ms), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_batch_io (
	batch_id VARCHAR NOT NULL, 
	role VARCHAR NOT NULL, 
	material_version_id VARCHAR, 
	quantity_kg INTEGER NOT NULL, 
	source_id VARCHAR, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, batch_id) REFERENCES factory_v3_process_batches (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, material_version_id) REFERENCES factory_v3_material_versions (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (quantity_kg IS NULL OR (typeof(quantity_kg)='integer' AND quantity_kg BETWEEN 1 AND 9007199254740991)), 
	CHECK (role IN ('INPUT','STOCK_ADDITION','EXTERNAL_ADDITION','OUTPUT','BYPRODUCT','LOSS')), 
	CHECK (material_version_id IS NOT NULL OR (role IN ('EXTERNAL_ADDITION','BYPRODUCT','LOSS') AND source_id IS NOT NULL)), 
	UNIQUE (run_id, batch_id, role, material_version_id), 
	UNIQUE (run_id, source_id), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_bundle_artifacts (
	bundle_id VARCHAR NOT NULL, 
	path VARCHAR NOT NULL, 
	role VARCHAR NOT NULL, 
	format_version VARCHAR NOT NULL, 
	sha256 VARCHAR NOT NULL, 
	content BLOB NOT NULL, 
	PRIMARY KEY (bundle_id, path), 
	CHECK (length(sha256)=64 AND sha256 NOT GLOB '*[^0-9a-f]*'), 
	FOREIGN KEY(bundle_id) REFERENCES factory_v3_bundles (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_bundles (
	id VARCHAR NOT NULL, 
	bundle_hash VARCHAR NOT NULL, 
	profile VARCHAR NOT NULL, 
	manifest_bytes BLOB NOT NULL, 
	reader_version VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (length(bundle_hash)=64 AND bundle_hash NOT GLOB '*[^0-9a-f]*'), 
	UNIQUE (id, bundle_hash, profile), 
	CHECK (profile IN ('v3_contract_test','demo','scale')), 
	UNIQUE (bundle_hash)
)""",
    """CREATE TABLE factory_v3_command_receipts (
	run_id VARCHAR NOT NULL, 
	command_id VARCHAR NOT NULL, 
	payload_digest VARCHAR NOT NULL, 
	result_run_id VARCHAR NOT NULL, 
	result_revision INTEGER NOT NULL, 
	reply_json JSON, 
	PRIMARY KEY (run_id, command_id), 
	CHECK (length(payload_digest)=64 AND payload_digest NOT GLOB '*[^0-9a-f]*'), 
	CHECK (result_revision IS NULL OR (typeof(result_revision)='integer' AND result_revision BETWEEN 0 AND 9007199254740991)), 
	CHECK (json_valid(reply_json)), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_run_registry (run_id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(result_run_id) REFERENCES factory_v3_run_registry (run_id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_consist_members (
	consist_id VARCHAR NOT NULL, 
	fleet_id VARCHAR NOT NULL, 
	ordinal INTEGER NOT NULL, 
	coupler_distance_m DOUBLE NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, consist_id) REFERENCES factory_v3_consists (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, fleet_id) REFERENCES factory_v3_fleet (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	UNIQUE (run_id, fleet_id), 
	UNIQUE (run_id, consist_id, ordinal), 
	CHECK (ordinal IS NULL OR (typeof(ordinal)='integer' AND ordinal BETWEEN 0 AND 9007199254740991)), 
	CHECK (coupler_distance_m>=0 AND coupler_distance_m<1e308), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_consists (
	locomotive_id VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, locomotive_id) REFERENCES factory_v3_fleet (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	UNIQUE (run_id, locomotive_id), 
	CHECK (status IN ('IDLE','MOVING','BLOCKED')), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_events (
	sequence INTEGER NOT NULL, 
	event_type VARCHAR NOT NULL, 
	entity_type VARCHAR NOT NULL, 
	entity_id VARCHAR NOT NULL, 
	at_ms INTEGER NOT NULL, 
	occurred_at VARCHAR NOT NULL, 
	source_id VARCHAR NOT NULL, 
	payload JSON, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	UNIQUE (run_id, sequence), 
	UNIQUE (run_id, source_id), 
	CHECK (sequence IS NULL OR (typeof(sequence)='integer' AND sequence BETWEEN 1 AND 9007199254740991)), 
	CHECK (at_ms IS NULL OR (typeof(at_ms)='integer' AND at_ms BETWEEN 0 AND 4193483039999)), 
	CHECK (event_type IN ('RUN_CREATED','CLOCK_ADVANCED','PLAYING_CHANGED','SPEED_CHANGED','STOCK_RECEIVED','MATERIAL_ALLOCATED','BATCH_STARTED','BATCH_COMPLETED','ATTACHMENT_ACQUIRED','ATTACHMENT_RELEASED','JOB_ASSIGNED','JOB_EMPTY_APPROACH','JOB_QUEUED','JOB_LOADING','JOB_DISPATCHED','JOB_UNLOADING','JOB_RETURNING','JOB_IDLE','JOB_BLOCKED','JOB_COMPLETED','RESERVATION_ACQUIRED','RESERVATION_RELEASED','MOTION_PHASE_STARTED','MOTION_PHASE_COMPLETED','QUALITY_RECORDED','PLAN_RELEASED','WORK_ORDER_RELEASED','PROCESS_STARTED','PROCESS_BLOCKED','PROCESS_COMPLETED','MATERIAL_TRANSFORMED','MATERIAL_SPLIT','MATERIAL_MERGED','TRANSFER_STARTED','TRANSFER_LOADING','TRANSFER_DEPARTED','TRANSFER_UNLOADING','TRANSFER_ARRIVED','INSPECTION_STARTED','INSPECTION_PASSED','INSPECTION_HELD','INSPECTION_FAILED','PACKAGING_STARTED','PACKAGING_COMPLETED','MATERIAL_AVAILABLE','SHIPMENT_ALLOCATED','SHIPMENT_LOADING','MATERIAL_LOADED','SHIPMENT_LOADED','SHIPMENT_DISPATCHED','SHIPMENT_AT_PORT','SHIPMENT_SAILING','SHIPMENT_DELIVERED','ORDER_DELIVERED','RESOURCE_DOWN','RESOURCE_RESTORED','RECOVERY_ROUTED')), 
	CHECK (json_valid(payload) AND json_type(payload)='object'), 
	CHECK (entity_type IN ('run','order','work_order','production_lot','stock_lot','receipt','material','material_version','batch','process','fleet','job','attachment','shipment','shipment_leg','quality')), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_fleet (
	kind VARCHAR NOT NULL, 
	variant VARCHAR NOT NULL, 
	capacity_kg INTEGER NOT NULL, 
	length_m DOUBLE NOT NULL, 
	load_envelope_m JSON NOT NULL, 
	turn_radius_m DOUBLE NOT NULL, 
	mode VARCHAR NOT NULL, 
	load_socket_id VARCHAR NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	CHECK (kind IN ('truck','carrier','forklift','torpedo','ladle','locomotive','railcar','ship')), 
	CHECK (capacity_kg IS NULL OR (typeof(capacity_kg)='integer' AND capacity_kg BETWEEN 1 AND 9007199254740991)), 
	CHECK (mode IN ('road','rail','hot_metal_rail','water')), 
	CHECK (length_m>0 AND length_m<=1.7976931348623157e308), 
	CHECK (turn_radius_m>=0 AND turn_radius_m<=1.7976931348623157e308), 
	CHECK (json_valid(load_envelope_m) AND json_type(load_envelope_m)='array' AND json_array_length(load_envelope_m)=3), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_locations (
	kind VARCHAR NOT NULL, 
	x DOUBLE NOT NULL, 
	y DOUBLE NOT NULL, 
	z DOUBLE NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	CHECK (substr(id,1,3)='v2:'), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_mass_ledger (
	source_id VARCHAR NOT NULL, 
	kind VARCHAR NOT NULL, 
	quantity_kg INTEGER NOT NULL, 
	at_ms INTEGER NOT NULL, 
	material_id VARCHAR, 
	batch_id VARCHAR, 
	event_id VARCHAR, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, material_id) REFERENCES factory_v3_materials (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, batch_id) REFERENCES factory_v3_process_batches (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, event_id) REFERENCES factory_v3_events (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	UNIQUE (run_id, source_id), 
	CHECK (kind IN ('OPENING_STOCK','EXTERNAL_RECEIPT','EXTERNAL_ADDITION','BYPRODUCT','IRRECOVERABLE_LOSS')), 
	CHECK (quantity_kg IS NULL OR (typeof(quantity_kg)='integer' AND quantity_kg BETWEEN 1 AND 9007199254740991)), 
	CHECK (at_ms IS NULL OR (typeof(at_ms)='integer' AND at_ms BETWEEN 0 AND 4193483039999)), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_material_versions (
	material_id VARCHAR NOT NULL, 
	ordinal INTEGER NOT NULL, 
	grade VARCHAR NOT NULL, 
	form VARCHAR NOT NULL, 
	dimensions JSON NOT NULL, 
	weight_kg INTEGER NOT NULL, 
	cause_event_id VARCHAR, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, material_id) REFERENCES factory_v3_materials (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, cause_event_id) REFERENCES factory_v3_events (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	UNIQUE (run_id, material_id, ordinal), 
	UNIQUE (run_id, id, material_id), 
	UNIQUE (run_id, id, material_id, grade, form, weight_kg, dimensions), 
	CHECK (ordinal IS NULL OR (typeof(ordinal)='integer' AND ordinal BETWEEN 1 AND 9007199254740991)), 
	CHECK (weight_kg IS NULL OR (typeof(weight_kg)='integer' AND weight_kg BETWEEN 1 AND 9007199254740991)), 
	CHECK (form IN ('ORE','HOT_METAL','LIQUID_STEEL','SCRAP','SLAB','BLOOM','BILLET','HOT_SLAB','HOT_BLOOM','HOT_BILLET','HOT_STRIP','HOT_PLATE','STRIP','THIN_STRIP','COATED_STRIP','HR_COIL','CR_COIL','GI_COIL','GA_COIL','HGI_COIL','EG_COIL','GO_COIL','NGO_COIL','WIRE','WIRE_COIL','PLATE','STS_HR_COIL','STS_CR_COIL','STS_PLATE','TI_INGOT','TI_SLAB','TI_HR_COIL','TI_CR_COIL','TI_SHEET','TI_PLATE','COKE','COAL','LIMESTONE','ALLOY','SLAG','BYPRODUCT')), 
	CHECK (json_valid(dimensions) AND json_type(dimensions)='object'), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_materials (
	grade VARCHAR NOT NULL, 
	form VARCHAR NOT NULL, 
	dimensions JSON NOT NULL, 
	weight_kg INTEGER NOT NULL, 
	current_version_id VARCHAR NOT NULL, 
	origin_stock_lot_id VARCHAR, 
	production_lot_id VARCHAR, 
	quality_status VARCHAR NOT NULL, 
	availability_status VARCHAR NOT NULL, 
	active BOOLEAN NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, origin_stock_lot_id) REFERENCES factory_v3_stock_lots (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, production_lot_id) REFERENCES factory_v3_production_lots (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, current_version_id, id, grade, form, weight_kg, dimensions) REFERENCES factory_v3_material_versions (run_id, id, material_id, grade, form, weight_kg, dimensions) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (form IN ('ORE','HOT_METAL','LIQUID_STEEL','SCRAP','SLAB','BLOOM','BILLET','HOT_SLAB','HOT_BLOOM','HOT_BILLET','HOT_STRIP','HOT_PLATE','STRIP','THIN_STRIP','COATED_STRIP','HR_COIL','CR_COIL','GI_COIL','GA_COIL','HGI_COIL','EG_COIL','GO_COIL','NGO_COIL','WIRE','WIRE_COIL','PLATE','STS_HR_COIL','STS_CR_COIL','STS_PLATE','TI_INGOT','TI_SLAB','TI_HR_COIL','TI_CR_COIL','TI_SHEET','TI_PLATE','COKE','COAL','LIMESTONE','ALLOY','SLAG','BYPRODUCT')), 
	CHECK (weight_kg IS NULL OR (typeof(weight_kg)='integer' AND weight_kg BETWEEN 1 AND 9007199254740991)), 
	CHECK (json_valid(dimensions) AND json_type(dimensions)='object'), 
	CHECK (quality_status IN ('PENDING','PASSED','HOLD','FAILED')), 
	CHECK (availability_status IN ('WIP','QUARANTINED','AVAILABLE','RESERVED','SHIPPED','CONSUMED')), 
	CHECK (active IN (0,1) AND ((active=0 AND availability_status='CONSUMED') OR (active=1 AND availability_status!='CONSUMED'))), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_movement_segments (
	job_id VARCHAR NOT NULL, 
	ordinal INTEGER NOT NULL, 
	segment_id VARCHAR NOT NULL, 
	start_ms INTEGER NOT NULL, 
	end_ms INTEGER NOT NULL, 
	from_position_m JSON NOT NULL, 
	to_position_m JSON NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, job_id) REFERENCES factory_v3_transport_jobs (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	UNIQUE (run_id, job_id, ordinal), 
	CHECK (ordinal IS NULL OR (typeof(ordinal)='integer' AND ordinal BETWEEN 0 AND 9007199254740991)), 
	CHECK (start_ms IS NULL OR (typeof(start_ms)='integer' AND start_ms BETWEEN 0 AND 4193483039999)), 
	CHECK (end_ms IS NULL OR (typeof(end_ms)='integer' AND end_ms BETWEEN 0 AND 4193483039999)), 
	CHECK (end_ms IS NULL OR (start_ms IS NOT NULL AND end_ms > start_ms)), 
	CHECK (json_valid(from_position_m) AND json_array_length(from_position_m)=3), 
	CHECK (json_valid(to_position_m) AND json_array_length(to_position_m)=3), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_orders (
	customer_id VARCHAR NOT NULL, 
	product_id VARCHAR NOT NULL, 
	grade VARCHAR NOT NULL, 
	quantity_kg INTEGER NOT NULL, 
	due_at VARCHAR NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	CHECK (quantity_kg IS NULL OR (typeof(quantity_kg)='integer' AND quantity_kg BETWEEN 1 AND 9007199254740991)), 
	CHECK (product_id IN ('slab','bloom','billet','hr','plate','wire','cr','gi','ga','hgi','eg','go','ngo','sts-hr','sts-cr','sts-plate','ti-hr','ti-cr','ti-sheet','ti-plate')), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_process_batches (
	process_id VARCHAR, 
	recipe_id VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	start_ms INTEGER, 
	end_ms INTEGER, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, process_id) REFERENCES factory_v3_processes (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (status IN ('QUEUED','RUNNING','BLOCKED','COMPLETED')), 
	CHECK (start_ms IS NULL OR (typeof(start_ms)='integer' AND start_ms BETWEEN 0 AND 4193483039999)), 
	CHECK (end_ms IS NULL OR (typeof(end_ms)='integer' AND end_ms BETWEEN 0 AND 4193483039999)), 
	CHECK (end_ms IS NULL OR (start_ms IS NOT NULL AND end_ms > start_ms)), 
	CHECK (status NOT IN ('RUNNING','COMPLETED') OR (start_ms IS NOT NULL AND end_ms IS NOT NULL)), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_processes (
	work_order_id VARCHAR, 
	route_step_id VARCHAR NOT NULL, 
	equipment_id VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	ready_at_ms INTEGER NOT NULL, 
	start_ms INTEGER, 
	end_ms INTEGER, 
	planned_duration_ms INTEGER NOT NULL, 
	blocked_reason VARCHAR, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, work_order_id) REFERENCES factory_v3_work_orders (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (status IN ('QUEUED','RUNNING','BLOCKED','COMPLETED')), 
	CHECK (ready_at_ms IS NULL OR (typeof(ready_at_ms)='integer' AND ready_at_ms BETWEEN 0 AND 4193483039999)), 
	CHECK (start_ms IS NULL OR (typeof(start_ms)='integer' AND start_ms BETWEEN 0 AND 4193483039999)), 
	CHECK (end_ms IS NULL OR (typeof(end_ms)='integer' AND end_ms BETWEEN 0 AND 4193483039999)), 
	CHECK (planned_duration_ms IS NULL OR (typeof(planned_duration_ms)='integer' AND planned_duration_ms BETWEEN 1 AND 4193483039999)), 
	CHECK (end_ms IS NULL OR (start_ms IS NOT NULL AND end_ms > start_ms)), 
	CHECK (start_ms IS NULL OR start_ms>=ready_at_ms), 
	CHECK (status NOT IN ('RUNNING','COMPLETED') OR (start_ms IS NOT NULL AND end_ms IS NOT NULL)), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_production_lots (
	work_order_id VARCHAR NOT NULL, 
	planned_kg INTEGER NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, work_order_id) REFERENCES factory_v3_work_orders (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (planned_kg IS NULL OR (typeof(planned_kg)='integer' AND planned_kg BETWEEN 1 AND 9007199254740991)), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_quality (
	material_id VARCHAR NOT NULL, 
	material_version_id VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	at_ms INTEGER NOT NULL, 
	event_id VARCHAR, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, material_id) REFERENCES factory_v3_materials (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, event_id) REFERENCES factory_v3_events (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, material_version_id, material_id) REFERENCES factory_v3_material_versions (run_id, id, material_id) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (at_ms IS NULL OR (typeof(at_ms)='integer' AND at_ms BETWEEN 0 AND 4193483039999)), 
	CHECK (status IN ('PENDING','PASSED','HOLD','FAILED')), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_receipts (
	stock_lot_id VARCHAR NOT NULL, 
	source_id VARCHAR NOT NULL, 
	quantity_kg INTEGER NOT NULL, 
	received_at_ms INTEGER NOT NULL, 
	event_id VARCHAR, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, stock_lot_id) REFERENCES factory_v3_stock_lots (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, event_id) REFERENCES factory_v3_events (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	UNIQUE (run_id, source_id), 
	CHECK (quantity_kg IS NULL OR (typeof(quantity_kg)='integer' AND quantity_kg BETWEEN 1 AND 9007199254740991)), 
	CHECK (received_at_ms IS NULL OR (typeof(received_at_ms)='integer' AND received_at_ms BETWEEN 0 AND 4193483039999)), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_reservations (
	resource_id VARCHAR NOT NULL, 
	job_id VARCHAR NOT NULL, 
	start_ms INTEGER NOT NULL, 
	end_ms INTEGER NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, job_id) REFERENCES factory_v3_transport_jobs (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (start_ms IS NULL OR (typeof(start_ms)='integer' AND start_ms BETWEEN 0 AND 4193483039999)), 
	CHECK (end_ms IS NULL OR (typeof(end_ms)='integer' AND end_ms BETWEEN 0 AND 4193483039999)), 
	CHECK (end_ms IS NULL OR (start_ms IS NOT NULL AND end_ms > start_ms)), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_run_registry (
	run_id VARCHAR NOT NULL, 
	schema_version INTEGER NOT NULL, 
	fixture_version VARCHAR NOT NULL, 
	bundle_id VARCHAR, 
	PRIMARY KEY (run_id), 
	CHECK (schema_version IN ('1','2','3')), 
	CHECK ((schema_version=3 AND fixture_version='factory-v2' AND bundle_id IS NOT NULL) OR (schema_version IN (1,2) AND fixture_version!='factory-v2')), 
	UNIQUE (run_id, bundle_id, fixture_version), 
	FOREIGN KEY(bundle_id) REFERENCES factory_v3_bundles (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_runs (
	id VARCHAR NOT NULL, 
	fixture_version VARCHAR NOT NULL, 
	bundle_id VARCHAR NOT NULL, 
	bundle_hash VARCHAR NOT NULL, 
	profile VARCHAR NOT NULL, 
	scenario_id VARCHAR NOT NULL, 
	seed INTEGER NOT NULL, 
	elapsed_ms INTEGER NOT NULL, 
	duration_ms INTEGER NOT NULL, 
	revision INTEGER NOT NULL, 
	event_sequence INTEGER NOT NULL, 
	playing BOOLEAN NOT NULL, 
	speed INTEGER NOT NULL, 
	epoch_at VARCHAR NOT NULL, 
	started_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(id, bundle_id, fixture_version) REFERENCES factory_v3_run_registry (run_id, bundle_id, fixture_version) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(bundle_id, bundle_hash, profile) REFERENCES factory_v3_bundles (id, bundle_hash, profile) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (fixture_version='factory-v2'), 
	CHECK (scenario_id IN ('NORMAL','DELAY','RECOVERY')), 
	CHECK (seed IS NULL OR (typeof(seed)='integer' AND seed BETWEEN 0 AND 9007199254740991)), 
	CHECK (elapsed_ms IS NULL OR (typeof(elapsed_ms)='integer' AND elapsed_ms BETWEEN 0 AND 4193483039999)), 
	CHECK (duration_ms IS NULL OR (typeof(duration_ms)='integer' AND duration_ms BETWEEN 1 AND 4193483039999)), 
	CHECK (revision IS NULL OR (typeof(revision)='integer' AND revision BETWEEN 0 AND 9007199254740991)), 
	CHECK (event_sequence IS NULL OR (typeof(event_sequence)='integer' AND event_sequence BETWEEN 0 AND 9007199254740991)), 
	CHECK (elapsed_ms<=duration_ms), 
	CHECK (playing IN (0,1)), 
	CHECK (speed IN ('1','2','4')), 
	CHECK (epoch_at IN ('2026-10-30T00:00:00Z','2026-10-30T00:00:00.000Z','2026-10-30T00:00:00+00:00')), 
	FOREIGN KEY(id) REFERENCES factory_v3_run_registry (run_id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_shipment_legs (
	shipment_id VARCHAR NOT NULL, 
	ordinal INTEGER NOT NULL, 
	mode VARCHAR NOT NULL, 
	from_node_id VARCHAR NOT NULL, 
	to_node_id VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	eta_ms INTEGER, 
	start_ms INTEGER, 
	end_ms INTEGER, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, shipment_id) REFERENCES factory_v3_shipments (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	UNIQUE (run_id, shipment_id, ordinal), 
	CHECK (ordinal IS NULL OR (typeof(ordinal)='integer' AND ordinal BETWEEN 0 AND 9007199254740991)), 
	CHECK (mode IN ('ROAD','RAIL','SEA')), 
	CHECK (status IN ('PLANNED','LOADING','IN_TRANSIT','UNLOADING','DELIVERED')), 
	CHECK (eta_ms IS NULL OR (typeof(eta_ms)='integer' AND eta_ms BETWEEN 0 AND 4193483039999)), 
	CHECK (start_ms IS NULL OR (typeof(start_ms)='integer' AND start_ms BETWEEN 0 AND 4193483039999)), 
	CHECK (end_ms IS NULL OR (typeof(end_ms)='integer' AND end_ms BETWEEN 0 AND 4193483039999)), 
	CHECK (end_ms IS NULL OR (start_ms IS NOT NULL AND end_ms > start_ms)), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_shipment_materials (
	shipment_id VARCHAR NOT NULL, 
	material_id VARCHAR NOT NULL, 
	active BOOLEAN NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, shipment_id) REFERENCES factory_v3_shipments (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, material_id) REFERENCES factory_v3_materials (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (active IN (0,1)), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_shipments (
	order_id VARCHAR NOT NULL, 
	mode VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	capacity_kg INTEGER NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, order_id) REFERENCES factory_v3_orders (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (mode IN ('ROAD','RAIL','SEA')), 
	CHECK (status IN ('PLANNED','ALLOCATED','LOADING','DISPATCHED','IN_TRANSIT','DELIVERED')), 
	CHECK (capacity_kg IS NULL OR (typeof(capacity_kg)='integer' AND capacity_kg BETWEEN 1 AND 9007199254740991)), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_stock_lots (
	source_kind VARCHAR NOT NULL, 
	grade VARCHAR NOT NULL, 
	form VARCHAR NOT NULL, 
	quantity_kg INTEGER NOT NULL, 
	received_at_ms INTEGER NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	CHECK (source_kind IN ('OPENING','PURCHASED','RETURNED')), 
	CHECK (form IN ('ORE','HOT_METAL','LIQUID_STEEL','SCRAP','SLAB','BLOOM','BILLET','HOT_SLAB','HOT_BLOOM','HOT_BILLET','HOT_STRIP','HOT_PLATE','STRIP','THIN_STRIP','COATED_STRIP','HR_COIL','CR_COIL','GI_COIL','GA_COIL','HGI_COIL','EG_COIL','GO_COIL','NGO_COIL','WIRE','WIRE_COIL','PLATE','STS_HR_COIL','STS_CR_COIL','STS_PLATE','TI_INGOT','TI_SLAB','TI_HR_COIL','TI_CR_COIL','TI_SHEET','TI_PLATE','COKE','COAL','LIMESTONE','ALLOY','SLAG','BYPRODUCT')), 
	CHECK (quantity_kg IS NULL OR (typeof(quantity_kg)='integer' AND quantity_kg BETWEEN 1 AND 9007199254740991)), 
	CHECK (received_at_ms IS NULL OR (typeof(received_at_ms)='integer' AND received_at_ms BETWEEN 0 AND 4193483039999)), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_transport_jobs (
	fleet_id VARCHAR, 
	material_id VARCHAR, 
	shipment_leg_id VARCHAR, 
	from_node_id VARCHAR NOT NULL, 
	to_node_id VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	ready_at_ms INTEGER NOT NULL, 
	start_ms INTEGER, 
	end_ms INTEGER, 
	blocked_resource_id VARCHAR, 
	equipment_id VARCHAR, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, fleet_id) REFERENCES factory_v3_fleet (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, material_id) REFERENCES factory_v3_materials (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, shipment_leg_id) REFERENCES factory_v3_shipment_legs (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (status IN ('IDLE','ASSIGNED','EMPTY_APPROACH','QUEUED','LOADING','MOVING','UNLOADING','RETURNING','BLOCKED','COMPLETED','STRUCTURAL_BLOCKED')), 
	CHECK (ready_at_ms IS NULL OR (typeof(ready_at_ms)='integer' AND ready_at_ms BETWEEN 0 AND 4193483039999)), 
	CHECK (start_ms IS NULL OR (typeof(start_ms)='integer' AND start_ms BETWEEN 0 AND 4193483039999)), 
	CHECK (end_ms IS NULL OR (typeof(end_ms)='integer' AND end_ms BETWEEN 0 AND 4193483039999)), 
	CHECK (end_ms IS NULL OR (start_ms IS NOT NULL AND end_ms > start_ms)), 
	CHECK (fleet_id IS NULL OR equipment_id IS NULL), 
	CHECK (start_ms IS NULL OR start_ms>=ready_at_ms), 
	CHECK (status!='STRUCTURAL_BLOCKED' OR blocked_resource_id IS NOT NULL), 
	UNIQUE (run_id, id, fleet_id), 
	CHECK (status NOT IN ('ASSIGNED','BLOCKED','EMPTY_APPROACH','LOADING','MOVING','QUEUED','RETURNING','UNLOADING') OR fleet_id IS NOT NULL OR equipment_id IS NOT NULL), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_vehicle_states (
	fleet_id VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	node_id VARCHAR NOT NULL, 
	position_m JSON NOT NULL, 
	yaw_rad DOUBLE NOT NULL, 
	current_job_id VARCHAR, 
	available_at_ms INTEGER NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, fleet_id) REFERENCES factory_v3_fleet (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, current_job_id, fleet_id) REFERENCES factory_v3_transport_jobs (run_id, id, fleet_id) DEFERRABLE INITIALLY DEFERRED, 
	UNIQUE (run_id, fleet_id), 
	CHECK (available_at_ms IS NULL OR (typeof(available_at_ms)='integer' AND available_at_ms BETWEEN 0 AND 4193483039999)), 
	CHECK (status IN ('IDLE','ASSIGNED','EMPTY_APPROACH','QUEUED','LOADING','MOVING','UNLOADING','RETURNING','BLOCKED')), 
	CHECK (json_valid(position_m) AND json_type(position_m)='array' AND json_array_length(position_m)=3), 
	CHECK (abs(yaw_rad)<=1.7976931348623157e308), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_version_edges (
	batch_id VARCHAR NOT NULL, 
	input_version_id VARCHAR NOT NULL, 
	output_version_id VARCHAR NOT NULL, 
	transferred_kg INTEGER NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, batch_id) REFERENCES factory_v3_process_batches (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, input_version_id) REFERENCES factory_v3_material_versions (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	FOREIGN KEY(run_id, output_version_id) REFERENCES factory_v3_material_versions (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (transferred_kg IS NULL OR (typeof(transferred_kg)='integer' AND transferred_kg BETWEEN 1 AND 9007199254740991)), 
	CHECK (input_version_id!=output_version_id), 
	UNIQUE (run_id, batch_id, input_version_id, output_version_id), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
    """CREATE TABLE factory_v3_work_orders (
	order_id VARCHAR NOT NULL, 
	route_id VARCHAR NOT NULL, 
	route_version INTEGER NOT NULL, 
	planned_kg INTEGER NOT NULL, 
	status VARCHAR NOT NULL, 
	run_id VARCHAR NOT NULL, 
	id VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, id), 
	FOREIGN KEY(run_id, order_id) REFERENCES factory_v3_orders (run_id, id) DEFERRABLE INITIALLY DEFERRED, 
	CHECK (route_version IS NULL OR (typeof(route_version)='integer' AND route_version BETWEEN 1 AND 9007199254740991)), 
	CHECK (planned_kg IS NULL OR (typeof(planned_kg)='integer' AND planned_kg BETWEEN 1 AND 9007199254740991)), 
	CHECK (status IN ('PLANNED','RELEASED','COMPLETED')), 
	UNIQUE (run_id, id, order_id), 
	FOREIGN KEY(run_id) REFERENCES factory_v3_runs (id) DEFERRABLE INITIALLY DEFERRED
)""",
)

INDEXES = (
    """CREATE UNIQUE INDEX factory_v3_one_active_allocation ON factory_v3_allocations (run_id, material_id) WHERE active=1""",
    """CREATE UNIQUE INDEX factory_v3_one_current_attachment ON factory_v3_attachments (run_id, material_id) WHERE released_at_ms IS NULL""",
    """CREATE INDEX ix_factory_v3_bundle_artifacts_role ON factory_v3_bundle_artifacts (role)""",
    """CREATE UNIQUE INDEX factory_v3_one_active_shipment ON factory_v3_shipment_materials (run_id, material_id) WHERE active=1""",
    """CREATE UNIQUE INDEX factory_v3_one_equipment_job ON factory_v3_transport_jobs (run_id, equipment_id) WHERE status IN ('ASSIGNED','BLOCKED','EMPTY_APPROACH','LOADING','MOVING','QUEUED','RETURNING','UNLOADING') AND equipment_id IS NOT NULL""",
    """CREATE UNIQUE INDEX factory_v3_one_fleet_job ON factory_v3_transport_jobs (run_id, fleet_id) WHERE status IN ('ASSIGNED','BLOCKED','EMPTY_APPROACH','LOADING','MOVING','QUEUED','RETURNING','UNLOADING') AND fleet_id IS NOT NULL""",
    """CREATE UNIQUE INDEX factory_v3_one_material_job ON factory_v3_transport_jobs (run_id, material_id) WHERE status IN ('ASSIGNED','BLOCKED','EMPTY_APPROACH','LOADING','MOVING','QUEUED','RETURNING','UNLOADING') AND material_id IS NOT NULL""",
)

TRIGGERS = (
    """CREATE TRIGGER factory_v3_event_sequence BEFORE INSERT ON factory_v3_events
WHEN NEW.sequence != COALESCE((SELECT MAX(sequence)+1 FROM factory_v3_events WHERE run_id=NEW.run_id),1)
BEGIN SELECT RAISE(ABORT,'factory event sequence must be contiguous'); END""",
    """CREATE TRIGGER factory_v3_writer_permanent BEFORE UPDATE ON factory_v3_active_writer
WHEN NEW.legacy_write_locked < OLD.legacy_write_locked
 OR NEW.activation_generation < OLD.activation_generation
 OR (NEW.run_id != OLD.run_id AND NEW.activation_generation != OLD.activation_generation+1)
 OR (NEW.run_id = OLD.run_id AND NEW.activation_generation != OLD.activation_generation)
BEGIN SELECT RAISE(ABORT,'factory writer transition is permanent and generation ordered'); END""",
    """CREATE TRIGGER factory_v3_writer_no_delete BEFORE DELETE ON factory_v3_active_writer
BEGIN SELECT RAISE(ABORT,'factory writer guard is permanent'); END""",
    """CREATE TRIGGER factory_v3_run_binding BEFORE UPDATE OF id,fixture_version,bundle_id,bundle_hash,profile,epoch_at ON factory_v3_runs
WHEN NEW.id!=OLD.id OR NEW.fixture_version!=OLD.fixture_version OR NEW.bundle_id!=OLD.bundle_id
 OR NEW.bundle_hash!=OLD.bundle_hash OR NEW.profile!=OLD.profile OR NEW.epoch_at!=OLD.epoch_at
BEGIN SELECT RAISE(ABORT,'factory run bundle binding is immutable'); END""",
)


def upgrade() -> None:
    for statement in TABLES + INDEXES + TRIGGERS:
        op.execute(statement)
    duplicate_keys = (
        ("active_writer", "id=NEW.id"),
        ("runs", "id=NEW.id"),
        ("events", "run_id=NEW.run_id AND (id=NEW.id OR source_id=NEW.source_id OR sequence=NEW.sequence)"),
        ("mass_ledger", "run_id=NEW.run_id AND (id=NEW.id OR source_id=NEW.source_id)"),
        ("command_receipts", "run_id=NEW.run_id AND command_id=NEW.command_id"),
        ("bundles", "id=NEW.id OR bundle_hash=NEW.bundle_hash"),
        ("bundle_artifacts", "bundle_id=NEW.bundle_id AND path=NEW.path"),
        ("run_registry", "run_id=NEW.run_id"),
    )
    for table, predicate in duplicate_keys:
        op.execute(f"""CREATE TRIGGER factory_v3_{table}_no_replace BEFORE INSERT ON factory_v3_{table}
WHEN EXISTS (SELECT 1 FROM factory_v3_{table} WHERE {predicate})
BEGIN SELECT RAISE(ABORT,'factory immutable identity already exists'); END""")
    op.execute("""CREATE TRIGGER factory_v3_registry_writer BEFORE INSERT ON factory_v3_run_registry
WHEN EXISTS (SELECT 1 FROM factory_v3_active_writer WHERE run_id=NEW.run_id
 AND ((NEW.schema_version=3 AND bootstrap_mode='legacy_fixture') OR (NEW.schema_version!=3 AND bootstrap_mode!='legacy_fixture')))
BEGIN SELECT RAISE(ABORT,'factory writer mode must match registered schema'); END""")
    for table in ("events", "mass_ledger", "command_receipts", "bundles", "bundle_artifacts", "run_registry"):
        for action in ("UPDATE", "DELETE"):
            op.execute(f"""CREATE TRIGGER factory_v3_{table}_{action.lower()} BEFORE {action} ON factory_v3_{table}
BEGIN SELECT RAISE(ABORT,'factory audit and bundle rows are append-only'); END""")
    for action in ("INSERT", "UPDATE"):
        op.execute(f"""CREATE TRIGGER factory_v3_writer_registry_{action.lower()} BEFORE {action} ON factory_v3_active_writer
WHEN EXISTS (SELECT 1 FROM factory_v3_run_registry WHERE run_id=NEW.run_id
 AND ((schema_version=3 AND NEW.bootstrap_mode='legacy_fixture') OR (schema_version!=3 AND NEW.bootstrap_mode!='legacy_fixture')))
BEGIN SELECT RAISE(ABORT,'factory writer mode must match registered schema'); END""")
        op.execute(f"""CREATE TRIGGER factory_v3_location_collision_{action.lower()} BEFORE {action} ON factory_v3_locations
WHEN EXISTS (SELECT 1 FROM locations WHERE id=NEW.id)
BEGIN SELECT RAISE(ABORT,'factory v2 location namespace collision'); END""")
        exclusion = "AND NOT (reservation.run_id=OLD.run_id AND reservation.id=OLD.id)" if action == "UPDATE" else ""
        op.execute(f"""CREATE TRIGGER factory_v3_reservation_overlap_{action.lower()} BEFORE {action} ON factory_v3_reservations
WHEN EXISTS (SELECT 1 FROM factory_v3_reservations AS reservation
 WHERE reservation.run_id=NEW.run_id AND reservation.resource_id=NEW.resource_id
 AND reservation.start_ms<NEW.end_ms AND NEW.start_ms<reservation.end_ms {exclusion})
BEGIN SELECT RAISE(ABORT,'factory reservation intervals overlap'); END""")
        exclusion = "AND NOT (edge.run_id=OLD.run_id AND edge.id=OLD.id)" if action == "UPDATE" else ""
        op.execute(f"""CREATE TRIGGER factory_v3_version_cycle_{action.lower()} BEFORE {action} ON factory_v3_version_edges
WHEN EXISTS (WITH RECURSIVE descendants(id) AS (
 SELECT NEW.output_version_id UNION SELECT edge.output_version_id FROM factory_v3_version_edges AS edge
 JOIN descendants ON edge.input_version_id=descendants.id WHERE edge.run_id=NEW.run_id {exclusion})
 SELECT 1 FROM descendants WHERE id=NEW.input_version_id)
BEGIN SELECT RAISE(ABORT,'factory version lineage must be acyclic'); END""")
        for table in ("materials", "material_versions"):
            op.execute(f"""CREATE TRIGGER factory_v3_{table}_dimensions_{action.lower()} BEFORE {action} ON factory_v3_{table}
WHEN EXISTS (SELECT 1 FROM json_each(NEW.dimensions) WHERE key NOT IN
 ('length_mm','width_mm','thickness_mm','diameter_mm','inner_diameter_mm')
 OR (type!='null' AND (type NOT IN ('integer','real') OR value<=0 OR value>1.7976931348623157e308)))
BEGIN SELECT RAISE(ABORT,'factory dimensions must be finite positive millimeters'); END""")
        for table, columns in (("vehicle_states", ("position_m",)), ("movement_segments", ("from_position_m", "to_position_m"))):
            for column in columns:
                op.execute(f"""CREATE TRIGGER factory_v3_{table}_{column}_{action.lower()} BEFORE {action} ON factory_v3_{table}
WHEN EXISTS (SELECT 1 FROM json_each(NEW.{column}) WHERE type NOT IN ('integer','real') OR abs(value)>1.7976931348623157e308)
BEGIN SELECT RAISE(ABORT,'factory position must contain finite meters'); END""")
        op.execute(f"""CREATE TRIGGER factory_v3_fleet_envelope_{action.lower()} BEFORE {action} ON factory_v3_fleet
WHEN EXISTS (SELECT 1 FROM json_each(NEW.load_envelope_m) WHERE type NOT IN ('integer','real') OR value<=0 OR value>1.7976931348623157e308)
BEGIN SELECT RAISE(ABORT,'factory load envelope must contain finite positive meters'); END""")


class FactoryHistoryDowngradeError(RuntimeError):
    """A destructive downgrade cannot preserve immutable factory history."""

    def __str__(self) -> str:
        return "Factory history is permanent; restore the preserved database and pinned bundle instead."


def downgrade() -> None:
    raise FactoryHistoryDowngradeError
