"""Real factory exits may pass a public road dock without using its process."""
from collections import deque
from pathlib import Path
from typing import Literal, assert_never

import pytest

from app.operations.world_contract import FactoryWorld
from app.operations.world_layout_coverage import validate_coverage
from app.operations.world_layout_paths import port_graph, reachable
from app.operations.world_layout_policy import OPTIONAL_EXIT_BRANCHES
from app.operations.world_layout_requirements import LayoutRequirements
from tools.factory_world.assembly import assemble

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope='module')
def factory() -> FactoryWorld:
    return assemble(ROOT)


def path_between(graph: dict[str, set[str]], endpoints: tuple[str, str]) -> tuple[str, ...]:
    """Find an actual directed witness, retaining deterministic predecessor order."""
    start, end = endpoints
    pending = deque([(start,)])
    seen = {start}
    while pending:
        path = pending.popleft()
        if path[-1] == end:
            return path
        for target in sorted(graph.get(path[-1], set()) - seen):
            seen.add(target)
            pending.append((*path, target))
    raise AssertionError(f'actual witness absent: {start} -> {end}')


def test_public_road_optional_exits_accept_original_full_world(factory: FactoryWorld) -> None:
    # SHL's actual own-work -> own-crane -> own-dock exit passes STL road docks.
    validate_coverage(factory, LayoutRequirements.read(ROOT))


@pytest.mark.parametrize('branch', OPTIONAL_EXIT_BRANCHES)
def test_actual_processing_route_cannot_substitute_for_optional_exit(
    factory: FactoryWorld, branch: tuple[str, str, tuple[str, ...]],
) -> None:
    from app.operations.world_layout_paths import optional_exit_graph
    source, product, forbidden = branch
    assert factory.spatial is not None
    ports = {port.id: port for port in factory.ports}
    binding = next(row for row in factory.spatial.coverage
                   if row.source_id == source and row.product_ids == (product,))
    start = next(ports[identity].node_id for identity in binding.port_ids
                 if ports[identity].socket_id == 'work')
    warehouse = next(port.node_id for port in factory.ports
                     if port.owner_id == 'WAREHOUSE' and port.socket_id == 'work')
    processing_owner = {'src:ti-tll-coil': 'TI-CR-08', 'src:ti-shl-sheet': 'TI-SHEET-08'}[source]
    processing = next(port.node_id for port in factory.ports
                      if port.owner_id == processing_owner and port.socket_id == 'work')
    docks = {port.node_id for port in factory.ports
             if port.owner_id in forbidden and port.socket_id == 'dock'}
    original = port_graph(factory)
    inbound_graph = {node: targets - docks for node, targets in original.items() if node not in docks}
    inbound = path_between(inbound_graph, (start, processing))
    visited = set(inbound[:-1])
    outbound_graph = {node: targets - visited for node, targets in original.items() if node not in visited}
    outbound = path_between(outbound_graph, (processing, warehouse))
    edges = set(zip(inbound, inbound[1:])) | set(zip(outbound, outbound[1:]))
    forced = {node: {target for a, target in edges if a == node} for node, _ in edges}
    assert warehouse in reachable(forced, start)
    assert processing in path_between(forced, (start, warehouse))
    permitted = optional_exit_graph(factory, forbidden)
    guarded = {node: targets & permitted.get(node, set()) for node, targets in forced.items()}
    assert warehouse not in reachable(guarded, start)


def test_shl_public_road_pass_does_not_authorize_internal_contacts(factory: FactoryWorld) -> None:
    from app.operations.world_layout_paths import optional_exit_graph
    source, product, forbidden = OPTIONAL_EXIT_BRANCHES[1]
    assert factory.spatial is not None
    binding = next(row for row in factory.spatial.coverage
                   if row.source_id == source and row.product_ids == (product,))
    ports = {port.id: port for port in factory.ports}
    start = next(ports[identity].node_id for identity in binding.port_ids
                 if ports[identity].socket_id == 'work')
    available = reachable(optional_exit_graph(factory, forbidden), start)
    assert {'v2:n:TI-CR-08:dock', 'v2:n:func-ti-stl-skelp-ti-cr:dock'} <= available
    assert not {port.node_id for port in factory.ports
                if port.owner_id in forbidden and port.socket_id != 'dock'} & available


def test_public_dock_cannot_borrow_a_crane_as_its_optional_exit(factory: FactoryWorld) -> None:
    from app.operations.world_layout_paths import optional_exit_graph
    assert factory.spatial is not None
    _, _, forbidden = OPTIONAL_EXIT_BRANCHES[1]
    dock = next(port for port in factory.ports if port.owner_id == 'TI-CR-08' and port.socket_id == 'dock')
    warehouse = next(port for port in factory.ports if port.owner_id == 'WAREHOUSE' and port.socket_id == 'work')
    original = next(crane for crane in factory.spatial.crane_reaches if dock.id in crane.pick_port_ids)
    borrowed = original.model_copy(update={'pick_port_ids': (dock.id,), 'drop_port_ids': (warehouse.id,)})
    spatial = factory.spatial.model_copy(update={'crane_reaches': (borrowed,)})
    damaged = factory.model_copy(update={'spatial': spatial})
    assert warehouse.node_id in port_graph(damaged)[dock.node_id]
    assert warehouse.node_id not in optional_exit_graph(damaged, forbidden)[dock.node_id]


@pytest.mark.parametrize('damage', ['work-alias', 'port-roller', 'port-mixed', 'node-mixed'])
def test_dock_name_cannot_promote_an_internal_or_mixed_role(
    factory: FactoryWorld, damage: Literal['work-alias', 'port-roller', 'port-mixed', 'node-mixed'],
) -> None:
    from app.operations.world_layout_paths import optional_exit_graph
    _, _, forbidden = OPTIONAL_EXIT_BRANCHES[1]
    dock = next(port for port in factory.ports if port.owner_id == 'TI-CR-08' and port.socket_id == 'dock')
    ports, nodes = factory.ports, factory.nodes
    match damage:
        case 'work-alias':
            ports = tuple(port.model_copy(update={'node_id': dock.node_id})
                          if port.owner_id == dock.owner_id and port.socket_id == 'work' else port for port in ports)
        case 'port-roller':
            ports = tuple(port.model_copy(update={'modes': ('roller',)}) if port.id == dock.id else port for port in ports)
        case 'port-mixed':
            ports = tuple(port.model_copy(update={'modes': ('road', 'roller')}) if port.id == dock.id else port for port in ports)
        case 'node-mixed':
            nodes = tuple(node.model_copy(update={'modes': ('road', 'roller')}) if node.id == dock.node_id else node for node in nodes)
        case unreachable:
            assert_never(unreachable)
    damaged = factory.model_copy(update={'ports': ports, 'nodes': nodes})
    guarded = optional_exit_graph(damaged, forbidden)
    assert dock.node_id not in guarded
    assert all(dock.node_id not in targets for targets in guarded.values())
