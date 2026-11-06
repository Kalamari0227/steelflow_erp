from sqlalchemy import JSON, CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pydantic import JsonValue


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    country: Mapped[str]


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (CheckConstraint("quantity_kg > 0"),)
    id: Mapped[str] = mapped_column(primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    grade: Mapped[str]
    quantity_kg: Mapped[int]
    due_at: Mapped[str]
    status: Mapped[str]


class Location(Base):
    __tablename__ = "locations"
    id: Mapped[str] = mapped_column(primary_key=True)
    type: Mapped[str]
    name: Mapped[str]
    x: Mapped[float]
    y: Mapped[float]
    z: Mapped[float]


class ProductionLot(Base):
    __tablename__ = "production_lots"
    __table_args__ = (CheckConstraint("actual_kg >= 0 AND actual_kg <= planned_kg"),)
    id: Mapped[str] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    line_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    planned_kg: Mapped[int]
    actual_kg: Mapped[int]
    status: Mapped[str]


class Coil(Base):
    __tablename__ = "coils"
    __table_args__ = (CheckConstraint("weight_kg > 0"),)
    id: Mapped[str] = mapped_column(primary_key=True)
    lot_id: Mapped[str] = mapped_column(ForeignKey("production_lots.id"))
    grade: Mapped[str]
    width_mm: Mapped[int]
    thickness_mm: Mapped[float]
    weight_kg: Mapped[int]
    status: Mapped[str]


class Inventory(Base):
    __tablename__ = "inventory"
    coil_id: Mapped[str] = mapped_column(ForeignKey("coils.id"), primary_key=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    availability_status: Mapped[str]


class Shipment(Base):
    __tablename__ = "shipments"
    id: Mapped[str] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    mode: Mapped[str]
    etd: Mapped[str]
    eta: Mapped[str]
    status: Mapped[str]


class ShipmentCoil(Base):
    __tablename__ = "shipment_coils"
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"), primary_key=True)
    coil_id: Mapped[str] = mapped_column(ForeignKey("coils.id"), unique=True, primary_key=True)


class Simulation(Base):
    __tablename__ = "simulation"
    __table_args__ = (CheckConstraint("id = 1"), CheckConstraint("speed IN (1,2,4)"))
    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[str]
    run_id: Mapped[str]
    tick: Mapped[int]
    playing: Mapped[bool]
    speed: Mapped[int]
    sequence: Mapped[int]


class OperationEvent(Base):
    __tablename__ = "operation_events"
    __table_args__ = (UniqueConstraint("run_id", "sequence"), CheckConstraint("sequence > 0"))
    id: Mapped[str] = mapped_column(primary_key=True)
    scenario_id: Mapped[str]
    run_id: Mapped[str]
    sequence: Mapped[int]
    entity_type: Mapped[str]
    entity_id: Mapped[str]
    event_type: Mapped[str]
    occurred_at: Mapped[str]
    payload: Mapped[dict[str, JsonValue]] = mapped_column(JSON)
    recorded_at: Mapped[str | None]


class JourneyState(Base):
    __tablename__ = "journey_state"
    __table_args__ = (CheckConstraint("id = 1"), CheckConstraint("speed IN (1,2,4)"),
                      CheckConstraint("elapsed_ms >= 0 AND elapsed_ms <= duration_ms"),
                      CheckConstraint("duration_ms > 0"), CheckConstraint("revision >= 0"))
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str]
    product_id: Mapped[str]
    revision: Mapped[int]
    elapsed_ms: Mapped[int]
    duration_ms: Mapped[int]
    playing: Mapped[bool]
    speed: Mapped[int]
    sequence: Mapped[int]


class JourneyEvent(Base):
    __tablename__ = "journey_events"
    __table_args__ = (UniqueConstraint("run_id", "sequence"), CheckConstraint("sequence > 0"),
                      CheckConstraint("elapsed_ms >= 0"))
    id: Mapped[str] = mapped_column(primary_key=True)
    run_id: Mapped[str]
    product_id: Mapped[str]
    sequence: Mapped[int]
    event_type: Mapped[str]
    step_id: Mapped[str]
    elapsed_ms: Mapped[int]
    occurred_at: Mapped[str]
