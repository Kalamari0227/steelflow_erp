"""Independent motion coverage and reviewed asset-policy admission."""

from pathlib import Path
from typing import Final

from pydantic import ValidationError

from .catalog import load_catalog
from .motion_policy import load_policies
from .motion_effective_policy import policy_alternatives
from .motion_phase_policies import PHASE_POLICIES, validate_recipe_windows
from .motion_types import MotionError, MotionRegistry, require
from .world_contract import read_json
from .world_types import WorldContractError

ROOT: Final = Path(__file__).resolve().parents[3]


def parse_motion_registry(raw: str | bytes) -> MotionRegistry:
    try:
        registry = MotionRegistry.model_validate(read_json(raw))
    except WorldContractError as error:
        raise MotionError(error.code, error.reference) from error
    except ValidationError as error:
        raise MotionError("invalid_contract", "registry") from error
    validate_registry(registry)
    return registry


def validate_registry(registry: MotionRegistry) -> None:
    """Validate denominator against separately reviewed T2 requirements and catalog."""
    from .motion_coverage_sources import CoverageDocument

    coverage = CoverageDocument.model_validate_json(
        (ROOT / "shared/coverage-registry.json").read_bytes()
    )
    require(
        len(coverage.source_requirements) == 179
        and len(coverage.approved_scope_requirements) == 155,
        "registry_coverage",
        "requirements",
    )
    from .motion_coverage import validate_applicability

    validate_applicability(registry, coverage)
    catalog = load_catalog()
    source_ids = {s.source_step_id for r in catalog.routes for s in r.steps}
    families = {"raw-sea", "receiving", "road", "rail", "sea", "internal", "quality"}
    logistics = {
        r.id
        for r in coverage.approved_scope_requirements
        if len(r.id.split(":")) == 3 and r.id.split(":")[1] in families
    }
    expected = (
        {"source:" + sid for sid in source_ids}
        | {
            r.id
            for r in coverage.source_requirements
            if r.id.removeprefix("src:") not in source_ids
        }
        | logistics
    )
    require(
        len(registry.recipes) == len(expected) == 243,
        "registry_coverage",
        "semantic_count",
    )
    require(
        {r.semantic_id for r in registry.recipes} == expected,
        "registry_coverage",
        "semantics",
    )
    require(
        len({r.id for r in registry.recipes}) == len(registry.recipes),
        "duplicate",
        "recipes",
    )
    policy_catalog = load_policies()
    policies = {p.id: p for p in policy_catalog.policies}
    compiled = {s.id for s in coverage.observed_inventory.compiled_steps}
    mapped = [sid for r in registry.recipes for sid in r.compiled_step_ids]
    require(
        len(mapped) == len(set(mapped)) == 348 and set(mapped) == compiled,
        "registry_coverage",
        "compiled_steps",
    )
    valid_requirements = {r.id for r in coverage.requirements()}
    for recipe in registry.recipes:
        production, windows = validate_recipe_windows(recipe)
        if recipe.semantic_id.startswith("source:"):
            source = recipe.semantic_id.removeprefix("source:")
            rows = [
                s
                for s in coverage.observed_inventory.compiled_steps
                if s.source_step_id == source
            ]
            require(
                bool(rows)
                and recipe.source_step_ids == (source,)
                and set(recipe.compiled_step_ids) == {s.id for s in rows},
                "registry_coverage",
                recipe.id,
            )
            require(
                recipe.execution_kind == "process"
                and recipe.meaning == rows[0].name + " — " + rows[0].description
                and set(recipe.requirement_ids)
                == {rid for row in rows for rid in row.requirement_ids},
                "registry_coverage",
                recipe.id,
            )
            alternatives = policy_alternatives(policy_catalog, "equipment", rows[0].equipment_kind, rows[0].equipment_id)
            require(all(policy_alternatives(policy_catalog, "equipment", row.equipment_kind, row.equipment_id) == alternatives for row in rows), "registry_coverage", recipe.id)
            require(recipe.policy_ids in ((alternatives[0].id,), tuple(p.id for p in alternatives)), "registry_coverage", recipe.id)
            require(
                {(f.function_id, f.kind, f.policy_id) for f in recipe.functions}
                == {(f, kind, policy.id) for policy in alternatives if policy.id in recipe.policy_ids for kind, functions in (("moving", policy.required_functions), ("state", policy.state_bound_fixed_functions)) for f in functions},
                "registry_coverage",
                recipe.id,
            )
        elif recipe.semantic_id.startswith("src:"):
            require(
                not recipe.policy_ids
                and len(recipe.functions) == 1
                and recipe.functions[0].kind == "unresolved"
                and not recipe.source_step_ids
                and not recipe.compiled_step_ids,
                "registry_coverage",
                recipe.id,
            )
        else:
            require(
                recipe.policy_ids == PHASE_POLICIES[recipe.semantic_id]
                and not recipe.source_step_ids
                and not recipe.compiled_step_ids,
                "registry_coverage",
                recipe.id,
            )
            expected_functions = {
                (function, kind, pid)
                for pid in recipe.policy_ids
                for kind, functions in [
                    ("moving", policies[pid].required_functions),
                    ("state", policies[pid].state_bound_fixed_functions),
                ]
                for function in functions
            }
            require(
                {(f.function_id, f.kind, f.policy_id) for f in recipe.functions}
                == expected_functions,
                "registry_coverage",
                recipe.id,
            )
        require(
            all(
                f.window_id == ("work" if production else windows[0])
                for f in recipe.functions
            ),
            "registry_coverage",
            recipe.id,
        )
        if not recipe.semantic_id.startswith("source:"):
            requirement = next(
                r for r in coverage.requirements() if r.id == recipe.semantic_id
            )
            require(
                recipe.requirement_ids == (requirement.id,)
                and recipe.meaning == requirement.expected_function
                and all(
                    f.semantic_need == requirement.expected_function
                    if f.kind == "unresolved"
                    else f.semantic_need
                    == requirement.expected_function + ": " + f.function_id
                    for f in recipe.functions
                ),
                "registry_coverage",
                recipe.id,
            )
        require(
            recipe.id == "motion:" + recipe.semantic_id, "registry_coverage", recipe.id
        )
        require(
            set(recipe.requirement_ids) <= valid_requirements,
            "registry_coverage",
            recipe.id,
        )
        for function in recipe.functions:
            if function.policy_id is None:
                require(
                    function.kind == "unresolved"
                    and function.function_id == "need:" + recipe.semantic_id,
                    "unknown_function",
                    function.function_id,
                )
                continue
            policy = policies.get(function.policy_id)
            require(policy is not None, "binding", function.policy_id)
            if policy is None:
                raise MotionError("binding", function.policy_id)
            admitted = {
                "moving": policy.required_functions,
                "state": policy.state_bound_fixed_functions,
                "unresolved": (),
            }
            require(
                function.function_id in admitted[function.kind],
                "unknown_function",
                function.function_id,
            )
    expected_apps: dict[str, set[str]] = {
        "requirement": valid_requirements,
        "connection": {c.id for c in coverage.observed_inventory.compiled_connections},
        "disposition": {d.id for d in coverage.source_step_dispositions},
        "receipt": {
            r.id for r in coverage.requirements() if r.id.startswith("scope:receipt:")
        },
        "fleet": {
            r.id for r in coverage.requirements() if r.id.startswith("scope:fleet:")
        },
    }
    require(
        len({(a.kind, a.reference_id) for a in registry.applicability})
        == len(registry.applicability),
        "duplicate",
        "applicability",
    )
    recipe_ids = {r.id for r in registry.recipes}
    for kind, ids in expected_apps.items():
        require(
            {a.reference_id for a in registry.applicability if a.kind == kind} == ids,
            "registry_coverage",
            kind,
        )
    for app in registry.applicability:
        require(
            bool(app.recipe_ids)
            and len(set(app.recipe_ids)) == len(app.recipe_ids)
            and set(app.recipe_ids) <= recipe_ids,
            "registry_coverage",
            app.reference_id,
        )
