# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic>=2.10,<3"]
# ///
# Run: backend/.venv/bin/python tools/qa/coverage.py [registry.json]
"""Fail closed on incomplete coverage; pending implementation is never a completion claim."""
import json
import sys
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from typing import Final

from pydantic import JsonValue, ValidationError

ROOT: Final = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'backend')]

from tools.qa.coverage_expectations import (  # noqa: E402
    COUNTS,
    DIAGRAMS,
    OFFICIAL,
    PRODUCTS,
    SHOWROOM,
    boundary,
    matches,
    require,
    validate_expected,
)
from tools.qa.coverage_inventory import SOURCE_FILES, LiveInventory  # noqa: E402
from tools.qa.coverage_models import (  # noqa: E402
    CoverageError,
    FileProof,
    Linked,
    Observed,
    Registry,
    Requirement,
)


def unique_pairs(pairs: list[tuple[str, JsonValue]]) -> Mapping[str, JsonValue]:
    """Reject duplicate JSON keys before the typed parser can overwrite them."""
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        require(key not in result, 'duplicate_json_key', key)
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise CoverageError('nonfinite_json', value)


def parse_registry(path: Path) -> Registry:
    return parse_registry_bytes(path.read_bytes())


def parse_registry_bytes(raw: bytes) -> Registry:
    """Use one immutable read for both structural and duplicate-key admission."""
    json.loads(raw, object_pairs_hook=unique_pairs, parse_constant=reject_constant)
    return Registry.model_validate_json(raw)


def file_proof(proof: FileProof, root: Path) -> None:
    resolved = (root / proof.path).resolve()
    require(not Path(proof.path).is_absolute() and resolved.is_relative_to(root.resolve()), 'unsafe_evidence_path', proof.path)
    require(resolved.is_file(), 'missing_source_file', proof.path)
    require(sha256(resolved.read_bytes()).hexdigest() == proof.sha256, 'source_hash_drift', proof.path)


def provenance(registry: Registry, root: Path) -> None:
    sources = {row.id: row for row in registry.sources}
    expected = {f'showroom:{key}' for key in DIAGRAMS} | {f'official:{key}' for key in OFFICIAL} | {'scope:approved-plan'}
    require(sources.keys() == expected, 'source_inventory', ','.join(sorted(sources.keys() ^ expected)))
    for key, diagrams in DIAGRAMS.items():
        row = sources[f'showroom:{key}']
        require(row.url == f'https://my.posco.com/s/exshowrmproductmain?lv1=a0uTJ000004p{key}YAE', 'source_url', row.id)
        require(row.observed_at == '2026-10-24' and row.access_status == 'live_text_inaccessible', 'source_observation_status', row.id)
        require({p.path for p in row.local_evidence} == {f'docs/evidence/posco-reference/{name}.png' for name in diagrams.split()}, 'source_diagrams', row.id)
    for key, url in OFFICIAL.items():
        row = sources[f'official:{key}']
        require(row.url == url and row.observed_at == '2026-10-25' and row.access_status == 'research_report_accessed', 'official_source', row.id)
    plan = sources['scope:approved-plan']
    require(plan.url is None and plan.access_status == 'local_approved_scope', 'scope_source', plan.id)
    require(tuple((p.path, p.sha256) for p in plan.local_evidence) == (('.omo/ulw-execute/steelflow-uniform-fidelity-factory/approved-plan.md', 'db6d8fb0f0de1dd6dc998d62afcea41d9ed70858f37032ebab8e2b2575373bbc'),), 'scope_evidence', plan.id)
    for row in registry.sources:
        for proof in row.local_evidence:
            file_proof(proof, root)
    metadata = registry.metadata
    file_proof(FileProof(path=metadata.expected_authoring_artifact, sha256=metadata.expected_authoring_sha256), root)
    files = registry.observed_inventory.source_files
    require(len(files) == len(SOURCE_FILES) and frozenset(p.path for p in files) == SOURCE_FILES, 'inventory_source_files', 'observed_inventory.source_files')
    for proof in files:
        file_proof(proof, root)
    required_unknowns = {'live_showroom_structure_not_reverified', 'HGI_specific_3D_diagram_unavailable',
                        'Ti_cold_branch_adaptation_requires_mapping', 'machine_geometry_axes_speeds_clearances_unverified',
                        'historical_catalog_not_current_plant_configuration', '187_demo_steps_not_complete_source_requirements'}
    require(required_unknowns <= set(metadata.known_unknowns), 'missing_uncertainty', 'metadata.known_unknowns')


def check_links(registry: Registry) -> None:
    requirements = {r.id: r for r in registry.requirements()}
    qa = {r.id: r for r in registry.qa_rows}
    observed = {r.id: r for _, group in registry.observed_inventory.groups() for r in group}
    targets: list[tuple[str, Linked | Requirement]] = [
        *(('requirement', r) for r in registry.requirements()),
        *(('approved_product', r) for r in registry.products),
        *(('source_step_disposition', r) for r in registry.source_step_dispositions),
        *((kind, r) for kind, group in registry.observed_inventory.groups() for r in group),
    ]
    all_ids = [r.id for _, r in targets] + [r.id for r in registry.sources] + [r.id for r in registry.qa_rows]
    seen: set[str] = set()
    for identity in all_ids:
        require(identity not in seen, 'duplicate_id', identity)
        seen.add(identity)
    referenced: set[str] = set()
    for kind, target in targets:
        target_id = f'approved-product:{target.id}' if kind == 'approved_product' else target.id
        require(len(set(target.qa_row_ids)) == len(target.qa_row_ids), 'duplicate_QA_link', target.id)
        for qid in target.qa_row_ids:
            require(qid in qa, 'missing_QA', f'{target.id}/{qid}')
            row = qa[qid]
            require(row.target_id == target_id and row.target_type == kind, 'orphan_QA', qid)
            require(target_id in row.scenario, 'generic_QA', qid)
            for pattern in ('semantics|ordered section', 'motion', 'support', 'custody', 'selection', 'normal', 'wait', 'fault', 'pause', 'resume'):
                matches(pattern, row.scenario, qid)
            for pattern in ('API', 'transform', 'custody', 'continuous video', 'independent.*review'):
                matches(pattern, ' '.join(row.proof_requirements), qid)
            referenced.add(qid)
    for entity in (*registry.products, *registry.source_step_dispositions, *observed.values()):
        require(len(set(entity.requirement_ids)) == len(entity.requirement_ids), 'duplicate_requirement_link', entity.id)
        for rid in entity.requirement_ids:
            require(rid in requirements, 'orphan_requirement', f'{entity.id}/{rid}')
    require(referenced == qa.keys(), 'orphan_QA', ','.join(sorted(qa.keys() - referenced)))
    sources = {s.id for s in registry.sources}
    for row in registry.requirements():
        require(set(row.source_ids) <= sources, 'unknown_source', row.id)
        require(len(set(row.source_ids)) == len(row.source_ids), 'duplicate_source_link', row.id)
        mapping = row.implementation_mapping
        require(mapping.planned_entity_ids == (f'planned:{row.id}',), 'planned_mapping', row.id)
        require(len(set(mapping.observed_entity_ids)) == len(mapping.observed_entity_ids), 'duplicate_mapping', row.id)
        require(set(mapping.observed_entity_ids) <= observed.keys(), 'orphan_mapping', row.id)
        reverse = {key for key, entity in observed.items() if row.id in entity.requirement_ids}
        require(set(mapping.observed_entity_ids) == reverse, 'mapping_not_reciprocal', row.id)
        for qid in row.qa_row_ids:
            require(set(qa[qid].delivery_tasks) == set(row.delivery_tasks), 'QA_delivery_tasks', qid)
        for value in (row.expected_function, row.source_branch, row.adaptation, row.uncertainty, row.proof_requirement):
            require(value.strip().lower() not in {'generic', 'placeholder', 'fallback', 'tbd', 'todo', 'n/a', 'unknown'}, 'generic_requirement', row.id)
    for variant in registry.observed_inventory.semantic_variants:
        require(variant.semantic_functions == tuple(requirements[rid].expected_function for rid in variant.requirement_ids), 'generic_variant', variant.id)
        matches('parts.*motion.*source.*placement QA', variant.reuse_policy, variant.id)
    for product in registry.products:
        require(set(product.requirement_ids) == {r.id for r in requirements.values() if product.id in r.products}, 'product_requirement_mapping', product.id)


def check_native_mapping(registry: Registry) -> None:
    inventory = registry.observed_inventory
    equipment = {e.native_id: e for e in inventory.equipment}

    def source_requirement(source: str) -> str:
        return {'final-inspection': 'scope:inspection', 'final-packaging': 'scope:packaging'}.get(source, 'scope:carbon-upstream' if source.startswith('cs-') else f'src:{source}')

    def linked(row: Observed, required: set[str]) -> None:
        require(required <= set(row.requirement_ids), 'native_requirement_mapping', row.id)

    for row in inventory.compiled_steps:
        linked(row, {source_requirement(row.source_step_id)})
    for row in inventory.source_bindings:
        linked(row, {source_requirement(row.source_step_id)})
    for item in inventory.equipment:
        linked(item, {f'scope:asset-family:{item.kind}', *(source_requirement(s) for s in item.source_step_ids)})
    for variant in inventory.semantic_variants:
        require(set(variant.requirement_ids) == set(equipment[variant.equipment_ids[0]].requirement_ids), 'variant_requirement_mapping', variant.id)
    for row in inventory.kinds:
        linked(row, {f'scope:asset-family:{row.native_id}'})
    for row in inventory.products:
        linked(row, {f'scope:product:{row.native_id}'})
    for row in inventory.compiled_connections:
        linked(row, {f'scope:product:{row.product_id}', 'scope:internal:move'})
    for row in inventory.paths:
        linked(row, {'scope:internal:move'})


def validate_registry(registry: Registry, live: LiveInventory | None = None) -> None:
    check_links(registry)
    validate_expected(registry)
    require(frozenset(p.id for p in registry.products) == PRODUCTS, 'approved_products', ','.join(sorted(PRODUCTS ^ {p.id for p in registry.products})))
    provenance(registry, ROOT)
    current = live or LiveInventory.read()
    current.compare(registry)
    check_native_mapping(registry)
    originals = current.dispositions()
    expected_steps = {f'{p}-{n:02}' for p, count in COUNTS.items() for n in range(1, count + 1)}
    registered = {d.source_step_id for d in registry.source_step_dispositions}
    require(registered == expected_steps == set(originals), 'source_dispositions', ','.join(sorted(registered ^ expected_steps)))
    for row in registry.source_step_dispositions:
        original = originals[row.source_step_id]
        category = boundary(row.source_step_id)
        rid = f'src:{row.source_step_id}' if category == 'retained' else f'scope:{category}'
        required = (rid, 'src:plate-ultrasonic') if row.source_step_id == 'plate-09' else (rid,)
        require(row.id == f'disposition:{row.source_step_id}' and row.original_step.model_dump() == original.source_step.model_dump(), 'original_step_drift', row.id)
        require(row.product_id == original.product_id and row.source_id == f'showroom:{SHOWROOM[row.product_id]}', 'disposition_source', row.id)
        require(row.category == category and row.requirement_ids == required and row.replaced_by == (rid,), 'boundary_disposition', row.id)


def main(arguments: list[str]) -> int:
    if arguments in (['--help'], ['-h']):
        print('Usage: backend/.venv/bin/python tools/qa/coverage.py [registry.json]\n       coverage.py --refresh-finishing INPUT.json --output NEW_OWNED.json\nRead-only default validation; refresh changes only sealed forms and source hashes. All implementation/evidence remains pending.')
        return 0
    if len(arguments) == 4 and arguments[0] == '--refresh-finishing' and arguments[2] == '--output':
        try:
            output = Path(arguments[3]).absolute()
            require('..' not in output.parts and output == output.resolve() and output.is_relative_to(ROOT / '.omo/evidence') and output.suffix == '.json', 'unsafe_output', str(output))
            require(not output.exists() and not any(p.is_symlink() for p in (output, *output.parents)), 'output_exists_or_symlink', str(output))
            input_raw = Path(arguments[1]).read_bytes()
            registry = LiveInventory.read().refresh_finishing_forms(parse_registry_bytes(input_raw), ROOT)
            validate_registry(registry)
            # Keep original authoring order and scalar representations. The typed
            # projection above proves all other native/authored fields unchanged.
            document = json.loads(input_raw)
            steps = {row.id: row for row in registry.observed_inventory.compiled_steps}
            for row in document['observed_inventory']['compiled_steps']:
                row['input_form'] = steps[row['id']].input_form
                row['output_form'] = steps[row['id']].output_form
            hashes = {row.path: row.sha256 for row in registry.observed_inventory.source_files}
            for row in document['observed_inventory']['source_files']:
                row['sha256'] = hashes[row['path']]
            raw = json.dumps(document, ensure_ascii=False, indent=2) + '\n'
            with output.open('x', encoding='utf-8') as stream:
                stream.write(raw)
        except (CoverageError, ValidationError, OSError, UnicodeError, json.JSONDecodeError) as error:
            print(f'coverage: FAIL {error}', file=sys.stderr)
            return 1
        print(json.dumps({'status': 'sealed_finishing_forms_refreshed_implementation_pending', 'output': str(output), 'sha256': sha256(raw.encode()).hexdigest()}))
        return 0
    if len(arguments) > 1 or any(arg.startswith('-') for arg in arguments):
        print('coverage: invalid arguments; use --help', file=sys.stderr)
        return 2
    path = Path(arguments[0]) if arguments else ROOT / 'shared/coverage-registry.json'
    try:
        registry = parse_registry(path)
        validate_registry(registry)
    except (CoverageError, ValidationError, OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f'coverage: FAIL {error}', file=sys.stderr)
        return 1
    print(json.dumps({'status': 'registration_complete_implementation_pending', 'products': len(registry.products),
                      'source_dispositions': len(registry.source_step_dispositions), 'requirements': len(registry.requirements()),
                      'pending_QA': len(registry.qa_rows), 'observed': {k: len(v) for k, v in registry.observed_inventory.groups()},
                      'unmapped': [], 'placeholder': [], 'waived': []}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
