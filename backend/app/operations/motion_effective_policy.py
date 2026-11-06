"""Select one reviewed owner alternative; omission always selects its base."""

from .motion_policy import Policies, Policy
from .motion_types import MotionError, require


def policy_alternatives(catalog: Policies, category: str, kind: str, owner_id: str) -> tuple[Policy, ...]:
    """Resolve the base plus the exact placement's optional flat extension."""
    base = next((p for p in catalog.policies if p.category == category and p.kind == kind and not p.id.startswith("policy:equipment:finishing:")), None)
    if base is None:
        raise MotionError("binding", owner_id)
    rows = [b for b in catalog.existing_bindings if "equipment:" + owner_id in b.placement_ids]
    require(len(rows) <= 1 and all(b.category == category and b.kind == kind and b.policy_group_id == base.id for b in rows), "binding", owner_id)
    if not rows or rows[0].extension_policy_id is None:
        return (base,)
    extension = next(p for p in catalog.policies if p.id == rows[0].extension_policy_id)
    return (base, extension)


def effective_policy(catalog: Policies, category: str, kind: str, owner_id: str, selected_policy_id: str | None = None) -> Policy:
    """Manifest omission is None; raw explicit null is rejected upstream."""
    alternatives = policy_alternatives(catalog, category, kind, owner_id)
    selected = alternatives[0].id if selected_policy_id is None else selected_policy_id
    result = next((p for p in alternatives if p.id == selected), None)
    if result is None:
        raise MotionError("binding", selected)
    return result
