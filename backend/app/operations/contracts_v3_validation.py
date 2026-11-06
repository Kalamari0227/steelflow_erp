"""Cross-row schema3 integrity, separate from state-transition algorithms."""
from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from .contracts_v3_core import ACTIVE_JOB_STATUSES, ContractViolation, RunEntity
from .time_adapter_v3 import sim_ms_to_utc

if TYPE_CHECKING:
    from .contracts_v3 import FactoryCollections, FactorySnapshot


def collections(state: FactoryCollections) -> dict[str, tuple[RunEntity, ...]]:
    """Typed collection registry used for scope and identity checks."""
    return {
        "orders": state.orders, "work_orders": state.work_orders, "production_lots": state.production_lots,
        "stock_lots": state.stock_lots, "receipts": state.receipts, "materials": state.materials,
        "material_versions": state.material_versions, "version_edges": state.version_edges,
        "allocations": state.allocations, "process_batches": state.process_batches, "batch_io": state.batch_io,
        "processes": state.processes, "fleet": state.fleet, "vehicle_states": state.vehicle_states,
        "transport_jobs": state.transport_jobs, "movement_segments": state.movement_segments,
        "reservations": state.reservations, "consists": state.consists, "consist_members": state.consist_members,
        "attachments": state.attachments, "shipments": state.shipments, "shipment_legs": state.shipment_legs,
        "shipment_materials": state.shipment_materials, "quality": state.quality, "events": state.events,
        "mass_ledger": state.mass_ledger,
    }


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise ContractViolation("invalid_contract", detail)


def unique(values: Iterable[str | int | tuple[str, int] | tuple[str, str]], detail: str) -> None:
    items = tuple(values)
    require(len(items) == len(set(items)), detail)


def validate_snapshot(state: FactorySnapshot) -> None:
    groups = collections(state)
    indexes = {name: {row.id for row in rows} for name, rows in groups.items()}
    for name, rows in groups.items():
        require(len(rows) == len(indexes[name]), f"duplicate id in {name}")
        require(all(row.run_id == state.run.id for row in rows), f"cross-run row in {name}")
    references: list[tuple[str | None, str]] = []
    references.extend((r.order_id, "orders") for r in state.work_orders)
    references.extend((r.work_order_id, "work_orders") for r in state.production_lots)
    references.extend((r.stock_lot_id, "stock_lots") for r in state.receipts)
    references.extend((r.event_id, "events") for r in state.receipts)
    for r in state.materials:
        references.extend(((r.origin_stock_lot_id, "stock_lots"), (r.production_lot_id, "production_lots"), (r.current_version_id, "material_versions")))
    for r in state.material_versions:
        references.extend(((r.material_id, "materials"), (r.cause_event_id, "events")))
    for r in state.version_edges:
        references.extend(((r.batch_id, "process_batches"), (r.input_version_id, "material_versions"), (r.output_version_id, "material_versions")))
    for r in state.allocations:
        references.extend(((r.material_id, "materials"), (r.order_id, "orders"), (r.work_order_id, "work_orders")))
    references.extend((r.process_id, "processes") for r in state.process_batches)
    for r in state.batch_io:
        references.extend(((r.batch_id, "process_batches"), (r.material_version_id, "material_versions")))
    references.extend((r.work_order_id, "work_orders") for r in state.processes)
    references.extend((r.fleet_id, "fleet") for r in state.vehicle_states)
    references.extend((r.current_job_id, "transport_jobs") for r in state.vehicle_states)
    for r in state.transport_jobs:
        references.extend(((r.fleet_id, "fleet"), (r.material_id, "materials"), (r.shipment_leg_id, "shipment_legs")))
    references.extend((r.job_id, "transport_jobs") for r in state.movement_segments)
    references.extend((r.job_id, "transport_jobs") for r in state.reservations)
    references.extend((r.locomotive_id, "fleet") for r in state.consists)
    for r in state.consist_members:
        references.extend(((r.consist_id, "consists"), (r.fleet_id, "fleet")))
    references.extend((r.material_id, "materials") for r in state.attachments)
    references.extend((r.owner_id, "fleet") for r in state.attachments if r.kind in {"vehicle", "railcar", "ship"})
    references.extend((r.order_id, "orders") for r in state.shipments)
    references.extend((r.shipment_id, "shipments") for r in state.shipment_legs)
    for r in state.shipment_materials:
        references.extend(((r.shipment_id, "shipments"), (r.material_id, "materials")))
    for r in state.quality:
        references.extend(((r.material_id, "materials"), (r.material_version_id, "material_versions"), (r.event_id, "events")))
    for r in state.mass_ledger:
        references.extend(((r.material_id, "materials"), (r.batch_id, "process_batches"), (r.event_id, "events")))
    event_collections = {"order": "orders", "work_order": "work_orders", "production_lot": "production_lots", "stock_lot": "stock_lots", "receipt": "receipts", "material": "materials", "material_version": "material_versions", "batch": "process_batches", "process": "processes", "fleet": "fleet", "job": "transport_jobs", "attachment": "attachments", "shipment": "shipments", "shipment_leg": "shipment_legs", "quality": "quality"}
    for event in state.events:
        if event.entity_type == "run":
            require(event.entity_id == state.run.id, "event run entity mismatch")
        else:
            references.append((event.entity_id, event_collections[event.entity_type]))
        context = event.payload
        references.extend((key, "materials") for key in context.material_ids)
        references.extend(((context.order_id, "orders"), (context.work_order_id, "work_orders"), (context.process_id, "processes"), (context.batch_id, "process_batches"), (context.job_id, "transport_jobs"), (context.shipment_leg_id, "shipment_legs"), (context.from_attachment_id, "attachments"), (context.to_attachment_id, "attachments")))
    for key, collection in references:
        require(key is None or key in indexes[collection], f"missing reference {collection}/{key}")
    validate_materials(state)
    validate_batches(state)
    validate_logistics(state)
    validate_reservations(state)
    unique((r.sequence for r in state.events), "duplicate event sequence")
    unique((r.source_id for r in state.events), "duplicate event source")
    unique((r.source_id for r in state.receipts), "duplicate receipt source")
    unique((r.source_id for r in state.mass_ledger), "duplicate mass source")
    incoming = sum(r.quantity_kg for r in state.mass_ledger if r.kind in {"OPENING_STOCK", "EXTERNAL_RECEIPT", "EXTERNAL_ADDITION"})
    outgoing = sum(r.quantity_kg for r in state.mass_ledger if r.kind in {"BYPRODUCT", "IRRECOVERABLE_LOSS"})
    require(incoming == sum(r.weight_kg for r in state.materials if r.active) + outgoing, "global mass imbalance")
    require(len(state.events) == state.run.event_sequence and all(event.sequence == index for index, event in enumerate(sorted(state.events, key=lambda row: row.sequence), 1)), "event sequence gap or run mismatch")
    for event in state.events:
        require(event.at_ms <= state.run.elapsed_ms, "future event")
        require(event.occurred_at == sim_ms_to_utc(event.at_ms), "event UTC differs from simulation clock")


def validate_materials(state: FactorySnapshot) -> None:
    versions = {r.id: r for r in state.material_versions}
    works = {r.id: r for r in state.work_orders}
    materials = {r.id: r for r in state.materials}
    unique(((r.material_id, r.ordinal) for r in state.material_versions), "duplicate version ordinal")
    unique((r.material_id for r in state.allocations if r.active), "multiple active allocations")
    unique((r.material_id for r in state.attachments if r.released_at_ms is None), "multiple current attachments")
    for material in state.materials:
        version = versions[material.current_version_id]
        require((version.material_id, version.grade, version.form, version.dimensions, version.weight_kg) ==
                (material.id, material.grade, material.form, material.dimensions, material.weight_kg), "current version mismatch")
    for allocation in state.allocations:
        require(works[allocation.work_order_id].order_id == allocation.order_id, "allocation work/order mismatch")
        require(allocation.quantity_kg <= materials[allocation.material_id].weight_kg, "allocation exceeds physical mass")
        require(not allocation.active or materials[allocation.material_id].active, "inactive material allocated")
    for quality in state.quality:
        require(versions[quality.material_version_id].material_id == quality.material_id, "quality version mismatch")
    for attachment in state.attachments:
        require(attachment.released_at_ms is not None or materials[attachment.material_id].active, "consumed material has custody")


def validate_batches(state: FactorySnapshot) -> None:
    versions = {r.id: r for r in state.material_versions}
    incoming_roles = {"INPUT", "STOCK_ADDITION", "EXTERNAL_ADDITION"}
    outgoing_roles = {"OUTPUT", "BYPRODUCT", "LOSS"}
    unique(((r.batch_id, f"{r.role}:{r.material_version_id}:{r.source_id}") for r in state.batch_io), "duplicate batch IO source")
    unique((r.material_version_id for r in state.batch_io if r.material_version_id is not None and r.role in {"INPUT", "STOCK_ADDITION"}), "version consumed twice")
    unique(((r.batch_id, f"{r.input_version_id}:{r.output_version_id}") for r in state.version_edges), "duplicate version edge")
    for batch in state.process_batches:
        rows = tuple(r for r in state.batch_io if r.batch_id == batch.id)
        if batch.status == "COMPLETED":
            require(bool(rows), "completed batch has no mass IO")
            require(sum(r.quantity_kg for r in rows if r.role in incoming_roles) == sum(r.quantity_kg for r in rows if r.role in outgoing_roles), "batch mass imbalance")
        for row in rows:
            if row.material_version_id is not None:
                require(row.quantity_kg <= versions[row.material_version_id].weight_kg, "batch IO exceeds version mass")
    graph: dict[str, set[str]] = {}
    for edge in state.version_edges:
        inputs = [r for r in state.batch_io if r.batch_id == edge.batch_id and r.material_version_id == edge.input_version_id and r.role in incoming_roles]
        outputs = [r for r in state.batch_io if r.batch_id == edge.batch_id and r.material_version_id == edge.output_version_id and r.role in {"OUTPUT", "BYPRODUCT"}]
        require(bool(inputs) and bool(outputs), "version edge absent from batch IO")
        require(edge.transferred_kg <= min(sum(r.quantity_kg for r in inputs), sum(r.quantity_kg for r in outputs)), "edge exceeds IO mass")
        graph.setdefault(edge.input_version_id, set()).add(edge.output_version_id)
    for batch in state.process_batches:
        edges = tuple(r for r in state.version_edges if r.batch_id == batch.id)
        for row in state.batch_io:
            if row.batch_id == batch.id and row.material_version_id is not None:
                outgoing = sum(e.transferred_kg for e in edges if e.input_version_id == row.material_version_id)
                incoming = sum(e.transferred_kg for e in edges if e.output_version_id == row.material_version_id)
                require(max(outgoing, incoming) <= row.quantity_kg, "edge totals exceed IO mass")
    # Iterative topological check avoids recursion limits on long production histories.
    indegree = {key: 0 for key in versions}
    for targets in graph.values():
        for key in targets:
            indegree[key] += 1
    ready = [key for key, count in indegree.items() if count == 0]
    visited = 0
    while ready:
        key = ready.pop()
        visited += 1
        for target in graph.get(key, set()):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    require(visited == len(versions), "version lineage cycle")


def validate_logistics(state: FactorySnapshot) -> None:
    unique((r.fleet_id for r in state.vehicle_states), "duplicate vehicle state")
    unique((r.fleet_id for r in state.transport_jobs if r.fleet_id is not None and r.status in ACTIVE_JOB_STATUSES), "multiple active fleet jobs")
    unique((r.equipment_id for r in state.transport_jobs if r.equipment_id is not None and r.status in ACTIVE_JOB_STATUSES), "multiple active equipment jobs")
    unique((r.material_id for r in state.transport_jobs if r.material_id is not None and r.status in ACTIVE_JOB_STATUSES), "multiple active material jobs")
    unique(((r.job_id, r.ordinal) for r in state.movement_segments), "duplicate movement ordinal")
    unique(((r.consist_id, r.ordinal) for r in state.consist_members), "duplicate consist ordinal")
    unique((r.fleet_id for r in state.consist_members), "fleet belongs to multiple consists")
    unique(((r.shipment_id, r.ordinal) for r in state.shipment_legs), "duplicate shipment leg ordinal")
    jobs = {r.id: r for r in state.transport_jobs}
    for vehicle in state.vehicle_states:
        if vehicle.current_job_id is not None:
            require(jobs[vehicle.current_job_id].fleet_id == vehicle.fleet_id, "vehicle current job owner mismatch")
    fleet = {r.id: r for r in state.fleet}
    for consist in state.consists:
        require(fleet[consist.locomotive_id].kind == "locomotive", "consist requires locomotive")
    for member in state.consist_members:
        require(fleet[member.fleet_id].kind == "railcar", "consist member requires railcar")


def validate_reservations(state: FactorySnapshot) -> None:
    """Retain original windows and compare only effective nonempty occupancy."""
    indexed = {row.id: row for row in state.reservations}
    occupied: dict[str, list[tuple[int, int]]] = {}
    for row in state.reservations:
        require(row.released_at_ms is None or row.released_at_ms <= state.run.elapsed_ms, "future reservation release")
        end = row.end_ms if row.released_at_ms is None else min(row.end_ms, row.released_at_ms)
        if row.start_ms < end:
            occupied.setdefault(row.resource_id, []).append((row.start_ms, end))
    for intervals in occupied.values():
        previous_end = -1
        for start, end in sorted(intervals):
            require(start >= previous_end, "reservation intervals overlap")
            previous_end = end
    for event in state.events:
        context = event.payload
        if context.reservation_id is None:
            continue
        row = indexed.get(context.reservation_id)
        require(row is not None, "missing reservation event reference")
        if row is None:
            continue
        require(context.job_id == row.job_id and context.resource_id == row.resource_id, "reservation event owner mismatch")
        if event.event_type == "RESERVATION_RELEASED":
            require(row.released_at_ms == event.at_ms, "reservation release event time mismatch")
