"""Full-factory admission; the general v2 parser alone never proves physical layout."""
from dataclasses import dataclass
from hashlib import sha256
from app.operations.world_contract import FactoryWorld,parse_world
from app.operations.world_layout_requirements import LayoutRequirements
from app.operations.world_layout_coverage import validate_coverage
from app.operations.world_layout_paths import validate_access
from app.operations.world_layout_physics import validate_sweeps,validate_cranes_and_parking,validate_blocks_and_crossings
from app.operations.world_trajectory import fillet_trajectory,Trajectory
from app.operations.world_types import require


@dataclass(frozen=True,slots=True)
class ValidatedFactoryLayout:
    world: FactoryWorld
    raw_sha256: str
    requirements_sha256: str
    coverage: tuple[tuple[str,int],...]
    swept_checks: int
    registered_crossings: int

    def verify_bytes(self, raw: bytes) -> None:
        require(sha256(raw).hexdigest()==self.raw_sha256,'world_byte_hash','validation proof')


def validate_factory_layout(world: bytes, requirements: LayoutRequirements) -> ValidatedFactoryLayout:
    """Consume exact bytes so proof cannot silently bind a reserialized tree."""
    parsed=parse_world(world)
    require(parsed.spatial is not None,'spatial_required','full factory admission')
    coverage=validate_coverage(parsed,requirements)
    validate_access(parsed)
    validate_cranes_and_parking(parsed)
    crossings=validate_blocks_and_crossings(parsed)
    sweeps=validate_sweeps(parsed)
    return ValidatedFactoryLayout(parsed,sha256(world).hexdigest(),requirements.sha256,coverage,sweeps,crossings)
