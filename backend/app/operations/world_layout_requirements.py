"""Independent factory admission inputs, sourced from T2/T4 rather than world counts."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final
from pydantic import BaseModel, ConfigDict
from tools.qa.coverage import parse_registry
from tools.qa.coverage_models import Registry
from tools.qa.coverage_expectations import PARTS

FLEET_REQUIRED: Final = (('truck',32),('slab-carrier',12),('coil-carrier',12),('forklift',16),
    ('torpedo',4),('ladle-car',4),('locomotive',4),('railcar',12),('ship',4))
RECEIPT_FORMS: Final = ('ORE','SCRAP','TI_INGOT','SLAB','BLOOM','BILLET','HR_COIL','CR_COIL',
    'STS_HR_COIL','TI_HR_COIL','COAL','LIMESTONE','NICKEL_ORE')


class HallIdentity(BaseModel):
    model_config=ConfigDict(frozen=True,extra='ignore')
    id: str
    stage_id: str


class CampusIdentities(BaseModel):
    model_config=ConfigDict(frozen=True,extra='ignore')
    halls: tuple[HallIdentity,...]


class AssetPolicyIdentity(BaseModel):
    model_config=ConfigDict(frozen=True,extra='ignore')
    id: str
    kind: str
    category: str
    required_functions: tuple[str,...]
    fixed_functions: tuple[str,...]


class AssetIdentities(BaseModel):
    model_config=ConfigDict(frozen=True,extra='ignore')
    policies: tuple[AssetPolicyIdentity,...]


@dataclass(frozen=True,slots=True)
class LayoutRequirements:
    registry: Registry
    campus: CampusIdentities
    assets: AssetIdentities
    sha256: str
    source_hashes: tuple[tuple[str,str],...]

    @classmethod
    def read(cls, root: Path) -> 'LayoutRequirements':
        paths=('shared/coverage-registry.json','shared/factory-campus.json','shared/asset-requirements.json',
               'tools/qa/coverage_expectations.py','backend/app/operations/world_layout_policy.py')
        hashes=tuple((p,sha256((root/p).read_bytes()).hexdigest()) for p in paths)
        digest=sha256('\n'.join(p+' '+h for p,h in hashes).encode()).hexdigest()
        return cls(parse_registry(root/paths[0]),CampusIdentities.model_validate_json((root/paths[1]).read_bytes()),
            AssetIdentities.model_validate_json((root/paths[2]).read_bytes()),digest,hashes)

    @property
    def source_functions(self) -> frozenset[str]:
        return frozenset('src:'+key for key in PARTS)
