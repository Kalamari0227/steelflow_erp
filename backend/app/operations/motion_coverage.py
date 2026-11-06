"""Exact applicability relations derived from independent reviewed coverage inputs."""

from typing import Final

from .motion_coverage_sources import CoverageDocument

from .motion_types import MotionRegistry, require
from .motion_phase_policies import PHASE_POLICIES

FLEET_PHASE_FAMILY: Final = {
    "truck": "road",
    "slab-carrier": "internal",
    "coil-carrier": "internal",
    "forklift": "internal",
    "torpedo": "internal",
    "ladle-car": "internal",
    "locomotive": "rail",
    "railcar": "rail",
    "ship": "sea",
    "crane": "internal",
    "unloader": "raw-sea",
    "stacker": "raw-sea",
    "reclaimer": "raw-sea",
    "conveyor": "internal",
    'dump-truck': 'road',
    'ship-bulk': 'sea',
    'overhead-crane': 'internal',
    'port-crane': 'internal',
    'railcar-coil': 'rail',
    'railcar-bulk': 'rail',
}
ASSET_LOGISTICS: Final = {
    "stock": ("quality:store", "receiving:store"),
    "port": ("sea:quay-transfer", "sea:berth-wait", "sea:load-survey"),
    "ship": (
        "sea:voyage",
        "sea:unload-survey",
        "sea:load-survey",
        "raw-sea:bulk-voyage",
    ),
    "delivery": (
        "road:customer-unload",
        "road:customer-accept",
        "rail:customer-delivery",
        "sea:customer-delivery",
    ),
}
SCOPE_PREFIXES: Final = {
    "scope:receiving": ("receiving:",),
    "scope:dispatch": ("road:", "rail:", "sea:"),
    "scope:ti-purchased-ingot": ("receiving:",),
    "scope:intermediate-sale": (
        "receiving:downstream-feed",
        "quality:inspect",
        "quality:package",
        "road:dispatch",
        "rail:consist",
        "sea:quay-transfer",
    ),
    'scope:handling:receiving-cradle': ('internal:load', 'internal:unload'),
}
BOUNDARY_TARGETS: Final = {
    "scope:inspection": "scope:quality:inspect",
    "scope:packaging": "scope:quality:package",
    "scope:dispatch": "scope:road:dispatch",
    "scope:receiving": "scope:receiving:arrival",
}


def validate_applicability(
    registry: MotionRegistry, coverage: CoverageDocument
) -> None:
    """Reject valid-ID rewiring as well as omissions; no default applicability."""
    expected: dict[tuple[str, str], set[str]] = {}
    steps = coverage.observed_inventory.compiled_steps
    scope_families = {
        "raw-sea",
        "receiving",
        "road",
        "rail",
        "sea",
        "internal",
        "quality",
    }
    logistics = {
        r.id
        for r in coverage.requirements()
        if len(r.id.split(":")) == 3 and r.id.split(":")[1] in scope_families
    }
    source_ids = {s.source_step_id for s in steps}
    all_ids = (
        {"motion:source:" + s for s in source_ids}
        | {
            "motion:" + r.id
            for r in coverage.source_requirements
            if r.id[4:] not in source_ids
        }
        | {"motion:" + s for s in logistics}
    )
    for req in coverage.requirements():
        entities = set(req.implementation_mapping.observed_entity_ids)
        ids = {
            "motion:source:" + s.source_step_id
            for s in steps
            if req.id in s.requirement_ids or s.id in entities
        }
        if (
            req.id in logistics
            or req.id.startswith("src:")
            and req.id[4:] not in source_ids
        ):
            ids.add("motion:" + req.id)
        if req.id.startswith("scope:product:"):
            ids.update(
                "motion:source:" + s.source_step_id
                for s in steps
                if s.product_id == req.id.split(":")[-1]
            )
        if req.id.startswith("scope:asset-family:"):
            kind = req.id.split(":")[-1]
            ids.update(
                "motion:source:" + s.source_step_id
                for s in steps
                if s.equipment_kind == kind
            )
            ids.update("motion:scope:" + s for s in ASSET_LOGISTICS.get(kind, ()))
            ids.update(
                "motion:" + phase
                for phase, policies in PHASE_POLICIES.items()
                if "policy:equipment:" + kind in policies
            )
        ids.update(
            "motion:" + s
            for s in logistics
            if any(
                s.startswith("scope:" + prefix)
                for prefix in SCOPE_PREFIXES.get(req.id, ())
            )
        )
        if req.id in {"scope:uniform-fidelity", "scope:material-ledger"}:
            ids = set(all_ids)
        if req.id.startswith(("scope:receipt:", "scope:fleet:")):
            family = (
                "receiving"
                if req.id.startswith("scope:receipt:")
                else FLEET_PHASE_FAMILY[req.id.split(":")[-1]]
            )
            dimension = {
                "motion:" + s
                for s in logistics
                if s.startswith("scope:" + family + ":")
            }
            ids.update(dimension)
            expected[
                ("receipt" if req.id.startswith("scope:receipt:") else "fleet", req.id)
            ] = dimension
        expected[("requirement", req.id)] = ids
    for connection in coverage.observed_inventory.compiled_connections:
        expected[("connection", connection.id)] = {"motion:scope:internal:move"}
    for disposition in coverage.source_step_dispositions:
        sid = disposition.source_step_id
        expected[("disposition", disposition.id)] = (
            {"motion:source:" + sid}
            if sid in source_ids
            else {"motion:" + BOUNDARY_TARGETS[r] for r in disposition.replaced_by}
        )
    actual = {
        (a.kind, a.reference_id): set(a.recipe_ids) for a in registry.applicability
    }
    require(actual == expected, "registry_coverage", "applicability relations")
