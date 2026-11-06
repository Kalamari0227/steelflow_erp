"""Reviewed material-family compatibility and typed asset mechanics descriptors."""

from typing import Annotated, Final, Literal, Self
from collections.abc import Mapping
from types import MappingProxyType

from pydantic import Field, model_validator

from .contracts_v3_core import Contract, Digest, Finite, Id, Text
from .motion_types import Quaternion, Vector, SchemaVersion, require

SocketFamily = Literal[
    "ORE",
    "SCRAP",
    "LIQUID_IRON",
    "LIQUID_STEEL",
    "SLAB",
    "BLOOM",
    "BILLET",
    "INGOT",
    "STRIP",
    "PLATE",
    "COIL",
    "WIRE_COIL",
    "PACKAGED",
]
FORM_FAMILIES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "ORE": ("ORE",),
        "HOT_METAL": ("LIQUID_IRON",),
        "LIQUID_STEEL": ("LIQUID_STEEL",),
        "SCRAP": ("SCRAP",),
        "SLAB": ("SLAB",),
        "BLOOM": ("BLOOM",),
        "BILLET": ("BILLET",),
        "HOT_SLAB": ("SLAB",),
        "HOT_BLOOM": ("BLOOM",),
        "HOT_BILLET": ("BILLET",),
        "HOT_STRIP": ("STRIP",),
        "HOT_PLATE": ("PLATE",),
        "STRIP": ("STRIP",),
        "THIN_STRIP": ("STRIP",),
        "COATED_STRIP": ("STRIP",),
        "HR_COIL": ("COIL",),
        "CR_COIL": ("COIL",),
        "GI_COIL": ("COIL",),
        "GA_COIL": ("COIL",),
        "HGI_COIL": ("COIL",),
        "EG_COIL": ("COIL",),
        "GO_COIL": ("COIL",),
        "NGO_COIL": ("COIL",),
        "WIRE": ("WIRE_COIL",),
        "WIRE_COIL": ("WIRE_COIL",),
        "PLATE": ("PLATE",),
        "STS_HR_COIL": ("COIL",),
        "STS_CR_COIL": ("COIL",),
        "STS_PLATE": ("PLATE",),
        "TI_INGOT": ("INGOT",),
        "TI_SLAB": ("SLAB",),
        "TI_HR_COIL": ("COIL",),
        "TI_CR_COIL": ("COIL",),
        "TI_SHEET": ("PLATE",),
        "TI_PLATE": ("PLATE",),
        "COKE": ("ORE",),
        "COAL": ("ORE",),
        "LIMESTONE": ("ORE",),
        "ALLOY": ("ORE",),
        "SLAG": ("ORE",),
        "BYPRODUCT": ("ORE",),
    }
)


class BindingSocket(Contract):
    socket_id: Id
    family: SocketFamily
    position_m: Vector
    orientation_xyzw: Quaternion
    motion_function_ids: tuple[Text, ...]


class BindingFunction(Contract):
    function_id: Text
    node_id: Text
    kind: Literal["rotation", "translation", "state"]
    axis: Vector
    pivot_m: Vector
    min_value: Finite
    max_value: Finite

    @model_validator(mode="after")
    def mechanics(self) -> Self:
        require(self.min_value < self.max_value, "binding", self.function_id)
        require(
            abs(sum(x * x for x in self.axis) - 1) <= 1e-6, "axis", self.function_id
        )
        require(self.function_id == self.node_id, "binding", self.function_id)
        return self


class AssetBinding(Contract):
    owner_id: Id
    policy_id: Text
    sockets: tuple[BindingSocket, ...]
    functions: tuple[BindingFunction, ...]

    @model_validator(mode="after")
    def unique(self) -> Self:
        require(
            len({s.socket_id for s in self.sockets}) == len(self.sockets),
            "duplicate",
            self.owner_id,
        )
        require(
            len({f.function_id for f in self.functions}) == len(self.functions),
            "duplicate",
            self.owner_id,
        )
        moving = {f.function_id for f in self.functions if f.kind != "state"}
        require(
            all(
                len(set(s.motion_function_ids)) == len(s.motion_function_ids)
                and set(s.motion_function_ids) <= moving
                for s in self.sockets
            ),
            "binding",
            self.owner_id,
        )
        from .motion_finishing_continuity import validate_registered_sockets
        validate_registered_sockets(self)
        return self


PositiveFinite = Annotated[Finite, Field(gt=0)]


class InternalFeedRoller(Contract):
    part_id: Id
    surface_node_id: Id
    radius_m: PositiveFinite
    width_m: PositiveFinite
    center_m: Vector
    ratio: PositiveFinite


class InternalFeedBinding(Contract):
    schema_version: SchemaVersion
    id: Id
    kind: Literal['linear_roller_feed']
    custody_socket_id: Id
    driver_function_id: Id
    start_m: Vector
    end_m: Vector
    rollers: Annotated[tuple[InternalFeedRoller, ...], Field(min_length=2, max_length=64)]


class LiftedInternalFeedBinding(InternalFeedBinding):
    support_lift_function_id: Id


class InternalFeedAssetBinding(AssetBinding):
    internal_feeds: Annotated[tuple[LiftedInternalFeedBinding | InternalFeedBinding, ...], Field(min_length=1, max_length=1)]


class BathPathBinding(Contract):
    schema_version: SchemaVersion
    id: Id
    kind: Literal['finite_galvanizing_bath']
    custody_socket_id: Id
    driver_function_id: Id
    source_asset_id: Id
    source_manifest_sha256: Digest
    source_recipe_sha256: Digest
    glb_sha256_by_lod: tuple[Digest, Digest, Digest]
    stock_length_m: Finite
    width_m: Finite
    thickness_m: Finite
    required_state_functions: tuple[Id, ...]
    outlet_roller_ids: tuple[Id, ...]


class BathPathAssetBinding(AssetBinding):
    bath_paths: tuple[BathPathBinding]


AssetBindingValue = BathPathAssetBinding | InternalFeedAssetBinding | AssetBinding
