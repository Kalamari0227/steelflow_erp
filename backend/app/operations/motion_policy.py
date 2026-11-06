"""Immutable, closed policy and placement projections from the reviewed catalog."""

from pathlib import Path
from typing import ClassVar, Final, Self
from pydantic import BaseModel, ConfigDict, model_validator

from .motion_types import require

ROOT: Final = Path(__file__).resolve().parents[3]


class PolicyRecord(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")


class FixedRelation(PolicyRecord):
    fixed_part_id: str
    parent_part_id: str


class Policy(PolicyRecord):

    id: str
    category: str
    kind: str
    families: tuple[str, ...]
    required_functions: tuple[str, ...]
    fixed_functions: tuple[str, ...]
    state_bound_fixed_functions: tuple[str, ...]
    required_socket_roles: tuple[str, ...]
    roof_required: bool
    requirement_ids: tuple[str, ...]
    relative_fixed_parts: tuple[FixedRelation, ...] = ()


class AdditionalFunctions(PolicyRecord):
    moving: tuple[str, ...]
    state: tuple[str, ...]


class ExistingBinding(PolicyRecord):
    category: str
    kind: str
    variant: str
    policy_group_id: str
    placement_ids: tuple[str, ...]
    allowed_families: tuple[str, ...]
    stage_ids: tuple[str, ...]
    requirement_ids: tuple[str, ...]
    qa_row_ids: tuple[str, ...]
    additional_functions: AdditionalFunctions | None = None
    extension_policy_id: str | None = None

    @model_validator(mode="after")
    def paired_extension(self) -> Self:
        present = self.model_fields_set & {"additional_functions", "extension_policy_id"}
        require(not present or (len(present) == 2 and self.additional_functions is not None and self.extension_policy_id is not None), "invalid_contract", self.variant)
        return self


class Policies(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")
    policies: tuple[Policy, ...]
    existing_bindings: tuple[ExistingBinding, ...]

    @model_validator(mode="after")
    def flat_extensions(self) -> Self:
        require(len({p.id for p in self.policies}) == len(self.policies), "duplicate", "policies")
        policy_by_id = {p.id: p for p in self.policies}
        bases = [p for p in self.policies if not p.id.startswith("policy:equipment:finishing:")]
        require(len({(p.category, p.kind) for p in bases}) == len(bases), "duplicate", "base_policies")
        extension_ids: set[str] = set()
        for binding in self.existing_bindings:
            base = policy_by_id.get(binding.policy_group_id)
            require(base is not None and not binding.policy_group_id.startswith("policy:equipment:finishing:") and base.category == binding.category and base.kind == binding.kind, "binding", binding.variant)
            if base is None:
                continue
            extra = binding.additional_functions
            if extra is None:
                continue
            extension_id = binding.extension_policy_id
            if extension_id is None:
                continue
            require(len(binding.placement_ids) == 1, "binding", binding.variant)
            owner = binding.placement_ids[0].removeprefix("equipment:")
            require(extension_id == f"policy:equipment:finishing:{owner}:v1" and extension_id not in extension_ids, "binding", binding.variant)
            extension_ids.add(extension_id)
            extension = policy_by_id.get(extension_id)
            require(extension is not None, "binding", extension_id)
            if extension is None:
                continue
            added = (*extra.moving, *extra.state)
            require(len(set(added)) == len(added) and not (set(added) & (set(base.required_functions) | set(base.fixed_functions))), "duplicate", binding.variant)
            expected = base.model_copy(update={"id": extension.id, "required_functions": (*base.required_functions, *extra.moving), "fixed_functions": (*base.fixed_functions, *extra.state), "state_bound_fixed_functions": (*base.state_bound_fixed_functions, *extra.state)})
            require(extension == expected, "binding", extension.id)
        require({p.id for p in self.policies if p.id.startswith("policy:equipment:finishing:")} == extension_ids, "binding", "extension_policies")
        return self


def load_policies() -> Policies:
    return Policies.model_validate_json(
        (ROOT / "shared/asset-requirements.json").read_bytes()
    )
