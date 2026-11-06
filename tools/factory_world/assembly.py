"""Build the complete candidate without publishing or changing source fixtures."""
from pathlib import Path
from app.operations.world_contract import FactoryWorld
from tools.factory_world.builder import Builder
from tools.factory_world.production import lines, make_hall
from tools.factory_world.logistics import make_logistics, make_sea_ports
from tools.factory_world.networks import make_parking, make_roads, make_other_networks, access_routes
from tools.factory_world.coverage import add_coverage
from tools.factory_world.scope_paths import scope_coverage
from tools.factory_world.raw_materials import make_raw_conveyor
from tools.factory_world.crossings import register_crossings


def assemble(root: Path) -> FactoryWorld:
    b=Builder()
    for line in lines(): make_hall(b,line)
    make_logistics(b)
    make_sea_ports(b)
    make_raw_conveyor(b)
    make_parking(b)
    make_other_networks(b)
    make_roads(b)
    access_routes(b)
    add_coverage(b,root)
    scope_coverage(b,root)
    register_crossings(b)
    return b.finish()
