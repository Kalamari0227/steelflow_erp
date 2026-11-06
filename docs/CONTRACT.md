# API contract v1

All responses are JSON. IDs are stable synthetic strings. Weights are integer kilograms, dimensions are mm, positions are local scene units, and timestamps are ISO 8601 UTC. Collection GET routes return arrays directly. Errors use FastAPI `{ "detail": ... }` with 404 for unknown IDs and 422 for invalid controls.

The additional product-journey catalog is an object envelope `{products: [...]}`; see its independent contract below.

`GET /health`: service health. `GET /api/v1/world`: atomic World snapshot defined in `src/contracts.ts` and backend Pydantic models. `GET /api/v1/kpis`, `/orders`, `/orders/{id}`, `/coils/{id}`, `/shipments`, `/events`, `/scenarios` expose the corresponding resources. Order detail joins customer/lots/coils/shipments; coil detail joins lot/order/customer/current location/nullable shipment.

All control POSTs return World: `/simulation/reset`, `/simulation/pause`, `/simulation/step` (optional `{ "steps": 1 }`, bounded 1–48), `/simulation/play` (optional `{ "speed": 1 }`, only 1/2/4), `/scenarios/{NORMAL|DELAY|RECOVERY}/activate`.

Additional control: `/simulation/speed` accepts `{ "speed": 1|2|4 }` and preserves the current play/pause state. Changing speed never starts a paused simulation.

Simulation metadata also includes `tick_seconds`, the configured positive finite real-time cadence before dividing by speed. The default is 1 second. This is presentation timing metadata, not a second business clock.

World includes simulation metadata, KPIs, customers, orders, lots, coils, locations, inventory, shipments, shipment_coils, current-run events, risks, AI availability, and the required `production` snapshot. Event queries support run history; events have monotonically ordered sequences per run. Reset/activation retain older history and begin a new run. The initial run event is reproducible except its run/audit ID. No DELETE or operational mutation endpoints exist.

Authoritative schemas: FastAPI `/openapi.json`; browser runtime validators: `src/contracts.ts`. Contract parity is exercised by frontend-to-live-backend end-to-end tests. Business state is never advanced by a browser animation or polling request.

## Production workspace

`GET /api/v1/production` returns the same production snapshot embedded in World. `GET /api/v1/production/stages/{stage_id}` returns a stage and its participating batches; unknown IDs return 404. All existing simulation controls also advance/reset production. No separate browser clock is used.

Schemas: `backend/app/production_schemas.py` and `src/production/contracts.ts`.

| Object | Fields and semantics |
| --- | --- |
| Production snapshot | `tick`, `scenario_id`, `data_scope="synthetic_production_only"`, `total_mass_kg`, `completed_mass_kg`, `batches`, `stages`, `transports` |
| Batch | Stable `id`, `source_fixture_id`, target `product`, fixed `mass_kg`, current `material_id`, `parent_material_id`, `material_form`, `material_role`, `current_stage`, `current_location_id`, nullable `active_transport_id`, `current_step`, `equipment_id`, `status` (`queued`, `running`, `in_transit`, `completed`), ordered `route`, `route_progress` in 0..1, `steps`, `material_history` |
| Step | Stable `id`, `stage_id`, `name`, `equipment_id`, `start_tick`, `end_tick`, `status` (`queued`, `running`, `completed`). A tick represents 30 simulated minutes; start ticks may precede zero to demonstrate work already in progress. |
| Material version | Stable `id`, nullable `parent_id`, `form`, contextual `role` (`feedstock`, `sale_product`), producing `stage_id`, `created_tick`. Only reached versions appear. Latest version matches the current batch material ID, form and role. |
| Stage | `id`, `name`, `equipment_ids`, `substeps`, current occupant `batch_ids`, counts and masses for queued/running/completed occupants. These are current occupancy totals, not cumulative throughput or every batch routed through the stage. |
| Transport leg | Stable `id`, `batch_id`, `vehicle_id`, `vehicle_kind` (`flatbed_truck`, `hot_metal_car`, `ladle_car`), cargo `material_id`, `material_form`, `mass_kg`, `from_stage`, `to_stage`, `start_tick`, `end_tick`, `status` (`queued`, `in_transit`, `completed`). Future legs describe scheduled cargo, not current inventory. |

Stage IDs are `ironmaking`, `steelmaking`, `casting`, `hot_rolling`, `cold_rolling`, `coating`, `finishing`, `stock`. Target products are `SLAB`, `BLOOM`, `BILLET`, `HR`, `CR`, `GI`, `GA`, `EG`, `HGI`. Pre-product forms also include `ORE`, `HOT_METAL`, `LIQUID_STEEL`.

The nine batches conserve 198,000 kg independently of the legacy 318,000 kg logistics fixtures. Material history is lineage metadata, not duplicate inventory. A target-form material has `sale_product` role even while inspection/packing is pending; role is not a quality release. There are no production order/coil/shipment assignment links in this slice.

Production is a pure projection of immutable plans onto the persisted simulation tick and scenario. Advancing the backend clock appends production transition events to the existing run history; reads do not append events. Scenario replay returns identical production snapshots and transition payloads, with new run/audit IDs. DELAY adds 3 ticks to GI/GA HSM-A work; RECOVERY uses HSM-B with a 1-tick extension. Other production batches are unaffected.

Each of the 50 inter-stage legs lasts one tick; same-stage equipment steps have no transport gap. During transit, `current_location_id` and `equipment_id` identify the carrier, `active_transport_id` identifies its leg, and `current_stage` retains the origin for route context only. Stage occupancy excludes the batch. The destination's operations remain queued until the leg completes. Current material ID/form/role are unchanged by transport. Arrival puts the batch at the destination stage and clears the active leg.

Advancing across a leg boundary appends `TRANSPORT_DEPARTED` or `TRANSPORT_ARRIVED` with `entity_type="production_transport"`, `entity_id=leg.id` and the leg fields plus tick in its payload. Initial fixtures may already be in transit or beyond earlier legs at tick0; historical pre-baseline movements are fixture context, not newly executed events.

## Product manufacturing journey

This independent synthetic workspace does not mutate World, its scenarios or production batch mass. Authoritative schemas: `backend/app/journey_schemas.py` and `src/journey/contracts.ts`.

| Route | Request / response |
| --- | --- |
| `GET /api/v1/journey/products` | `{products: ProductDefinition[]}`; 17 validated routes, 8 families |
| `GET /api/v1/journey` | Current `JourneySnapshot` |
| `POST /api/v1/journey/select` | `{product_id: string}` → new paused run; unknown product 404 |
| `POST /api/v1/journey/reset` | No body; new paused run of current product, speed 1 |
| `POST /api/v1/journey/play`, `/pause` | No body; change playback |
| `POST /api/v1/journey/step` | No body; pause and advance to next operation boundary |
| `POST /api/v1/journey/speed` | `{speed: 1|2|4}`; preserves play/pause |
| `GET /api/v1/journey/events` | Ordered event array; optional `run_id` filter |

Every POST returns `JourneySnapshot`: `data_scope="synthetic_product_journey"`, `run_id`, globally increasing `revision`, `product_id`, `playing`, `speed`, `elapsed_ms`, `duration_ms`, `active_step_id`, `step_elapsed_ms`, `step_duration_ms`, `completed`, `material` and `history`.

Material contains `lineage_id`, `version_id`, nullable `parent_version_id`, `form`, `role`, `location_id`, integer `mass_kg`. History contains only reached versions with `version_id`, `parent_version_id`, `form`, producing `step_id` and `at_ms`. One version is current; history is not duplicate inventory. Each completed operation creates a new version, even if form is unchanged. Role is `feedstock` until route completion, then `sale_product`. Location is the active operation ID, then `{product_id}:dispatch`; active step remains the last operation when complete.

`ProductDefinition` contains stable `id`, `family`, `name`, `description`, `source_url`, `source_title`, `input_form`, `output_form`, fixed `mass_kg`, ordered `steps`. Each step has `id`, `name`, `equipment_kind`, positive `duration_ms` divisible by 100, `input_form`, `output_form`, `description`. Route validation rejects duplicate IDs and discontinuous forms.

Each journey event contains `id`, `run_id`, `product_id`, contiguous `sequence`, `event_type`, `step_id`, `elapsed_ms` and real audit UTC `occurred_at`. Reset/select retain old history. The DB rejects event mutation/deletion and skipped sequences. The server owns a 100ms integer clock; reads do not advance it. Final time is capped, completed playback stops, and restart restores the saved position paused. Synthetic elapsed times/forms/lineage reproduce; audit UUIDs/timestamps and revision do not.
