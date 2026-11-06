from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy.orm import Session

from . import models as m
from .schemas import Scenario

BASE_TIME: Final = datetime(2026, 10, 30, 8, tzinfo=UTC)
MAX_TICK: Final = 24
SCENARIOS: Final = [
    Scenario(id="NORMAL", name="Normal flow", description="Planned production and dispatch windows."),
    Scenario(id="DELAY", name="Line A delay", description="A three-hour line outage puts two orders past their promised arrival."),
    Scenario(id="RECOVERY", name="Recovery plan", description="Reserve Line B and priority dispatch recover two hours; one hour contingency remains."),
]


def timestamp(tick: int) -> str:
    return (BASE_TIME + timedelta(minutes=tick * 30)).isoformat().replace("+00:00", "Z")


def seed(session: Session) -> None:
    locations = [
        ("LINE-A", "production", "Hot rolling · Line A", -12, -7),
        ("LINE-B", "production", "Finishing · Line B", -12, 0),
        ("YARD", "yard", "Coil yard", 0, -5),
        ("DISPATCH", "dispatch", "Truck dispatch", 9, -4),
        ("PORT", "port", "Harbor terminal", 10, 7),
        ("SEA", "sea", "Coastal shipping lane", 17, 10),
        ("CUSTOMER", "customer", "Customer delivery", 17, -4),
    ]
    for identity, kind, name, x, z in locations:
        session.add(m.Location(id=identity, type=kind, name=name, x=x, y=0, z=z))
    customers = ["Han River Fabrication", "Northstar Motors", "Harbor Construction", "Atlas Appliances", "Pacific Railworks", "Summit Engineering"]
    for index, name in enumerate(customers):
        session.add(m.Customer(id=f"CU-{index+1:03}", name=name, country=["KR", "JP", "AU"][index % 3]))
    session.flush()
    for index in range(6):
        identity = 1001 + index
        grade = ["SPHC", "SS400", "SPCC"][index % 3]
        weight = 12000 + index * 500
        session.add(m.Order(id=f"O-{identity}", customer_id=f"CU-{index+1:03}", grade=grade, quantity_kg=weight * 4, due_at=timestamp(16 - index * 2), status="PLANNED"))
        session.flush()
        session.add(m.ProductionLot(id=f"LOT-{identity}", order_id=f"O-{identity}", line_id="LINE-A" if index < 2 or index % 2 == 0 else "LINE-B", planned_kg=weight * 4, actual_kg=0, status="PLANNED"))
        session.add(m.Shipment(id=f"SH-{identity}", order_id=f"O-{identity}", mode="COASTAL", etd=timestamp(8 - index * 2), eta=timestamp(14 - index * 2), status="PLANNED"))
        session.flush()
        for coil_index in range(4):
            coil_id = f"C-{1001 + index * 4 + coil_index}"
            session.add(m.Coil(id=coil_id, lot_id=f"LOT-{identity}", grade=grade, width_mm=1250 + 50 * (index % 3), thickness_mm=2.5 + index * 0.5, weight_kg=weight, status="PLANNED"))
            session.flush()
            session.add(m.Inventory(coil_id=coil_id, location_id="LINE-A", availability_status="PLANNED"))
            session.add(m.ShipmentCoil(shipment_id=f"SH-{identity}", coil_id=coil_id))
    session.flush()
