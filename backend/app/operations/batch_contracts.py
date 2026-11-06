"""Closed terminal observation and deterministic integer batch accounting."""
from __future__ import annotations

from collections.abc import Iterable

from .contracts_v3_core import (
    MAX_SAFE_INTEGER, Contract, Id, MaterialDimensions, MaterialForm, Ms,
    NonNegative, PositiveKg, RunKey, Text,
)
from .stock_contracts import require


class PhysicalInput(Contract):
    material_version_id: Id
    quantity_kg: PositiveKg


class AccountingInput(Contract):
    source_id: Id
    quantity_kg: PositiveKg


class BatchOutput(Contract):
    material_id: Id
    grade: Text
    form: MaterialForm
    dimensions: MaterialDimensions
    quantity_kg: PositiveKg
    destination_id: Id
    work_order_id: Id | None


class BatchCompletion(Contract):
    run_id: RunKey
    expected_revision: NonNegative
    command_id: Id
    recipe_id: Id
    process_id: Id | None
    start_ms: Ms
    end_ms: Ms
    inputs: tuple[PhysicalInput, ...]
    stock_additions: tuple[PhysicalInput, ...]
    external_additions: tuple[AccountingInput, ...]
    outputs: tuple[BatchOutput, ...]
    byproducts: tuple[AccountingInput, ...]
    losses: tuple[AccountingInput, ...]


def safe_total(quantities: Iterable[int]) -> int:
    """Keep aggregate kg representable in both Python and JavaScript contracts."""
    total = sum(quantities)
    require(0 <= total <= MAX_SAFE_INTEGER, 'aggregate kg exceeds safe integer range')
    return total


def distribute_kg(total_kg: int, output_ids: tuple[str, ...]) -> dict[str, int]:  # noqa: DICT_OK
    """Equal whole-kg split; stable IDs own the deterministic remainder."""
    require(type(total_kg) is int and 0 < total_kg <= MAX_SAFE_INTEGER, 'safe positive integer kg required')
    require(bool(output_ids) and all(type(key) is str and bool(key) for key in output_ids), 'output IDs required')
    require(len(set(output_ids)) == len(output_ids), 'duplicate output ID')
    require(total_kg >= len(output_ids), 'each output needs positive kg')
    quotient, remainder = divmod(total_kg, len(output_ids))
    return {key: quotient + (index < remainder) for index, key in enumerate(sorted(output_ids))}


def edge_quantities(request: BatchCompletion) -> tuple[tuple[str, str, int], ...]:
    """Integer transport table; only positive physical-to-output cells are edges.

    Physical sources precede external sources. Sinks are output, byproduct,
    loss, each sorted by its explicit ID. Products use unbounded Python ints.
    """
    physical = sorted((*request.inputs, *request.stock_additions), key=lambda row: row.material_version_id)
    sources = [(row.material_version_id, row.quantity_kg, True) for row in physical]
    sources.extend((row.source_id, row.quantity_kg, False) for row in sorted(request.external_additions, key=lambda row: row.source_id))
    sinks = [(row.material_id, row.quantity_kg, True) for row in sorted(request.outputs, key=lambda row: row.material_id)]
    sinks.extend((row.source_id, row.quantity_kg, False) for row in sorted(request.byproducts, key=lambda row: row.source_id))
    sinks.extend((row.source_id, row.quantity_kg, False) for row in sorted(request.losses, key=lambda row: row.source_id))
    remaining = [row[1] for row in sources]
    incoming = safe_total(remaining)
    require(incoming == safe_total(row[1] for row in sinks), 'batch mass imbalance')
    edges: list[tuple[str, str, int]] = []
    for sink_id, quantity, output in sinks:
        total = sum(remaining)
        require(0 < quantity <= total, 'invalid batch sink mass')
        shares = [quantity * available // total for available in remaining]
        remainder = quantity - sum(shares)
        for index, available in enumerate(remaining):
            if remainder and shares[index] < available:
                shares[index] += 1
                remainder -= 1
        require(remainder == 0, 'integer transport remainder was not allocated')
        for index, (source_id, _, physical_source) in enumerate(sources):
            remaining[index] -= shares[index]
            if physical_source and output and shares[index] > 0:
                edges.append((source_id, sink_id, shares[index]))
    require(not any(remaining), 'unconsumed transport mass')
    return tuple(edges)
