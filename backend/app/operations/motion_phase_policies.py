"""Explicit known-policy alternatives for each reviewed logistics semantic phase.

These are capability alternatives, never placement or asset-completion claims.
All required selected-policy channels are supplied; inactive joints use held values.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final
from .motion_types import MotionRecipe, require

_ROWS: Final = """
raw-sea:load-port fleet:ship fleet:unloader fleet:crane fleet:conveyor campus:berth equipment:port fleet:overhead-crane fleet:port-crane
raw-sea:bulk-voyage fleet:ship equipment:ship
raw-sea:berth fleet:ship equipment:ship campus:berth equipment:port
raw-sea:unload fleet:ship fleet:unloader fleet:crane fleet:conveyor fleet:overhead-crane fleet:port-crane
raw-sea:yard-store campus:raw-yard fleet:stacker fleet:reclaimer equipment:stock
raw-sea:process-feed fleet:reclaimer fleet:conveyor fleet:truck equipment:charge fleet:dump-truck
receiving:arrival fleet:truck fleet:slab-carrier fleet:coil-carrier fleet:railcar fleet:ship campus:gate fleet:dump-truck
receiving:inspection campus:receiving-inspection equipment:inspection
receiving:weigh campus:weighbridge
receiving:unload fleet:forklift fleet:crane fleet:slab-carrier fleet:coil-carrier fleet:truck fleet:railcar fleet:ship fleet:ladle-car fleet:torpedo fleet:unloader fleet:dump-truck fleet:overhead-crane fleet:port-crane
receiving:store campus:warehouse campus:raw-yard equipment:stock
receiving:downstream-feed fleet:conveyor fleet:slab-carrier fleet:coil-carrier fleet:forklift fleet:crane fleet:torpedo fleet:ladle-car equipment:charge fleet:overhead-crane fleet:port-crane
road:dispatch fleet:truck campus:gate fleet:dump-truck
road:wait fleet:truck campus:warehouse fleet:dump-truck
road:load fleet:truck fleet:crane fleet:forklift fleet:slab-carrier fleet:coil-carrier fleet:dump-truck fleet:overhead-crane fleet:port-crane
road:secure fleet:truck equipment:packaging fleet:dump-truck
road:weigh fleet:truck campus:weighbridge fleet:dump-truck
road:gate-out fleet:truck campus:gate fleet:dump-truck
road:travel fleet:truck fleet:dump-truck
road:customer-unload fleet:truck fleet:forklift fleet:crane campus:customer-dock fleet:dump-truck fleet:overhead-crane fleet:port-crane
road:customer-accept campus:customer-dock equipment:delivery
road:empty-return fleet:truck fleet:dump-truck
rail:consist fleet:locomotive fleet:railcar
rail:shunt fleet:locomotive fleet:railcar
rail:wagon-load fleet:railcar fleet:crane fleet:forklift fleet:overhead-crane fleet:port-crane
rail:block-move fleet:locomotive fleet:railcar fleet:torpedo fleet:ladle-car
rail:destination-unload fleet:railcar fleet:crane fleet:forklift fleet:overhead-crane fleet:port-crane
rail:destination-store campus:warehouse equipment:stock
rail:last-mile fleet:truck fleet:forklift fleet:slab-carrier fleet:coil-carrier fleet:dump-truck
rail:customer-delivery campus:customer-dock equipment:delivery
rail:empty-return fleet:locomotive fleet:railcar
sea:quay-transfer fleet:crane fleet:slab-carrier fleet:coil-carrier fleet:truck equipment:port campus:berth fleet:dump-truck fleet:overhead-crane fleet:port-crane
sea:berth-wait fleet:ship equipment:ship campus:berth equipment:port
sea:load-survey fleet:ship equipment:ship fleet:crane equipment:inspection equipment:port campus:berth fleet:overhead-crane fleet:port-crane
sea:voyage fleet:ship equipment:ship
sea:unload-survey fleet:ship equipment:ship fleet:unloader fleet:crane equipment:inspection fleet:overhead-crane fleet:port-crane
sea:hub-store campus:warehouse campus:raw-yard equipment:stock
sea:last-mile fleet:truck fleet:railcar fleet:dump-truck
sea:customer-delivery campus:customer-dock equipment:delivery
sea:empty-return fleet:ship equipment:ship
internal:approach fleet:truck fleet:slab-carrier fleet:coil-carrier fleet:forklift fleet:torpedo fleet:ladle-car fleet:locomotive fleet:railcar fleet:ship fleet:crane fleet:unloader fleet:dump-truck fleet:overhead-crane fleet:port-crane
internal:load fleet:crane fleet:slab-carrier fleet:coil-carrier fleet:forklift fleet:torpedo fleet:ladle-car fleet:truck fleet:railcar fleet:ship fleet:unloader fleet:dump-truck fleet:overhead-crane fleet:port-crane campus:receiving-cradle:coil-v1
internal:move fleet:truck fleet:slab-carrier fleet:coil-carrier fleet:forklift fleet:torpedo fleet:ladle-car fleet:locomotive fleet:railcar fleet:ship fleet:crane fleet:unloader fleet:stacker fleet:reclaimer fleet:conveyor fleet:dump-truck fleet:overhead-crane fleet:port-crane
internal:unload fleet:crane fleet:slab-carrier fleet:coil-carrier fleet:forklift fleet:torpedo fleet:ladle-car fleet:truck fleet:railcar fleet:ship fleet:unloader fleet:dump-truck fleet:overhead-crane fleet:port-crane campus:receiving-cradle:coil-v1
internal:empty-return fleet:truck fleet:slab-carrier fleet:coil-carrier fleet:forklift fleet:torpedo fleet:ladle-car fleet:locomotive fleet:railcar fleet:ship fleet:crane fleet:unloader fleet:dump-truck fleet:overhead-crane fleet:port-crane
internal:idle fleet:truck fleet:slab-carrier fleet:coil-carrier fleet:forklift fleet:torpedo fleet:ladle-car fleet:locomotive fleet:railcar fleet:ship fleet:crane fleet:unloader fleet:stacker fleet:reclaimer fleet:conveyor campus:warehouse equipment:stock fleet:dump-truck fleet:overhead-crane fleet:port-crane
quality:inspect equipment:inspection campus:receiving-inspection
quality:quarantine campus:warehouse equipment:stock
quality:reinspect equipment:inspection campus:receiving-inspection
quality:package equipment:packaging
quality:store campus:warehouse equipment:stock
quality:custody campus:hall campus:warehouse campus:raw-yard campus:customer-dock equipment:stock equipment:delivery
"""
PHASE_POLICIES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "scope:" + parts[0]: tuple("policy:" + p for p in parts[1:])
        for line in _ROWS.strip().splitlines()
        if (parts := line.split())
    }
)


def validate_recipe_windows(recipe: MotionRecipe) -> tuple[bool, tuple[str, ...]]:
    """Validate the complete ordered phase partition without temporal gaps."""
    travel = {
        "bulk-voyage",
        "travel",
        "empty-return",
        "shunt",
        "block-move",
        "last-mile",
        "voyage",
        "quay-transfer",
        "approach",
        "move",
        "gate-out",
        "downstream-feed",
        "process-feed",
        "customer-delivery",
    }
    loads = {
        "load-port",
        "unload",
        "load",
        "wagon-load",
        "destination-unload",
        "load-survey",
        "unload-survey",
        "customer-unload",
    }
    phase = recipe.semantic_id.split(":")[-1]
    production = recipe.semantic_id.startswith(("source:", "src:"))
    windows = (
        ("entry", "work", "exit")
        if production
        else (
            ("travel",)
            if phase in travel
            else (("load",) if phase in loads else ("hold",))
        )
    )
    kind = (
        "process" if production else ("transport" if phase in travel else "logistics")
    )
    require(
        tuple(w.id for w in recipe.windows) == windows
        and recipe.windows[0].start == 0
        and recipe.windows[-1].end == 1
        and all(a.end == b.start for a, b in zip(recipe.windows, recipe.windows[1:]))
        and recipe.execution_kind == kind,
        "registry_coverage",
        recipe.id,
    )
    return production, windows
