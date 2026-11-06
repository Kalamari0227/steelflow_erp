"""Typed collection storage codec shared by lifecycle and archive readers."""
import json
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import contracts_v3 as c, models_v3 as rows
from .bundle_registry import ServiceError
from .contracts_v3_validation import collections

TABLES: Final = (
    ("orders", rows.FactoryOrder.__table__), ("work_orders", rows.WorkOrder.__table__),
    ("production_lots", rows.ProductionLot.__table__), ("stock_lots", rows.StockLot.__table__),
    ("receipts", rows.StockReceipt.__table__), ("materials", rows.Material.__table__),
    ("material_versions", rows.MaterialVersion.__table__), ("version_edges", rows.VersionEdge.__table__),
    ("allocations", rows.MaterialAllocation.__table__), ("process_batches", rows.ProcessBatch.__table__),
    ("batch_io", rows.BatchIO.__table__), ("processes", rows.ProcessExecution.__table__),
    ("fleet", rows.FleetAsset.__table__), ("vehicle_states", rows.VehicleState.__table__),
    ("transport_jobs", rows.TransportJob.__table__), ("movement_segments", rows.MovementSegment.__table__),
    ("reservations", rows.ResourceReservation.__table__), ("consists", rows.Consist.__table__),
    ("consist_members", rows.ConsistMember.__table__), ("attachments", rows.Attachment.__table__),
    ("shipments", rows.Shipment.__table__), ("shipment_legs", rows.ShipmentLeg.__table__),
    ("shipment_materials", rows.ShipmentMaterial.__table__), ("quality", rows.QualityRecord.__table__),
    ("events", rows.FactoryEvent.__table__), ("mass_ledger", rows.MassLedgerEntry.__table__),
)


def insert_collections(session: Session, state: c.FactoryCollections) -> None:
    groups = collections(state)
    for name, table in TABLES:
        records = groups[name]
        if name == "events":
            records = tuple(sorted(state.events, key=lambda row: row.sequence))
        for record in records:
            session.execute(table.insert().values(**record.model_dump(mode="json")))


def load_rows(session: Session, run_id: str) -> c.FactorySnapshot:
    """Validate actual persisted values, including JSON, UTC and cross-run links."""
    run_table = rows.FactoryRun.__table__
    run = session.execute(select(run_table).where(run_table.c.id == run_id)).mappings().one_or_none()
    if run is None:
        raise ServiceError("not_found", run_id, 404)
    payload = {name: [dict(record) for record in session.execute(select(table).where(table.c.run_id == run_id).order_by(table.c.sequence if name == "events" else table.c.id)).mappings()] for name, table in TABLES}
    return c.FactorySnapshot.model_validate_json(json.dumps({**payload, "schema_version": 3, "run": dict(run)}))
