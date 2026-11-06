"""Mutations of the actual register must fail independently of its own denominators."""
import subprocess
import sys
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import Final

import pytest
from pydantic import ValidationError

from tools.qa.coverage import ROOT, parse_registry, provenance, validate_registry
from tools.qa.coverage_inventory import LiveInventory
from tools.qa.coverage_models import Category, CoverageError, FileProof, Registry

REGISTRY: Final = ROOT / 'shared/coverage-registry.json'
CLI: Final = ROOT / 'tools/qa/coverage.py'
# Source-specific functions deliberately independent of registry iteration/counts.
RAW_PARTS: Final = tuple('plate-ultrasonic plate-marking plate-gas-cut wire-shears cold-scale-breaker cold-welder cold-looper coating-air-knife coating-welder coating-looper coating-inspection eg-oven-cooler go-domain-refinement electrical-shot-blasting electrical-welder electrical-looper ngo-electrocleaning ngo-drying sts-shot-blasting sts-welder sts-looper ti-tll-coil ti-stl-skelp ti-shl-sheet hgi-hr-feed go-base-coating cr-cold-mill-output-cutter cr-finished-output-cutter go-pickling-output-cutter go-basecoat-output-cutter go-finished-output-cutter ngo-pickling-output-cutter ngo-finished-output-cutter sts-hapl-output-cutter sts-capl-output-cutter hotdip-output-cutter hgi-output-cutter eg-output-cutter gi-coating-cooling ga-coating-cooling hgi-coating-cooling'.split())
INVENTORIES: Final = tuple('products compiled_steps compiled_connections equipment kinds semantic_variants stages source_bindings paths cranes vehicles'.split())


@pytest.fixture(scope='module')
def registry() -> Registry:
    return parse_registry(REGISTRY)


@pytest.fixture(scope='module')
def live() -> LiveInventory:
    return LiveInventory.read()


def reject(registry: Registry, live: LiveInventory) -> None:
    """Use the same strict boundary and validator as the CLI after model mutation."""
    validate_registry(Registry.model_validate_json(registry.model_dump_json()), live)


def omit_requirement(registry: Registry, identity: str) -> Registry:
    """Remove the requirement and all its links so graph checks alone cannot catch it."""
    inventory = registry.observed_inventory.model_copy(update={
        category: tuple(row.model_copy(update={'requirement_ids': tuple(r for r in row.requirement_ids if r != identity)}) for row in rows)
        for category, rows in registry.observed_inventory.groups()
    })
    return registry.model_copy(update={
        'source_requirements': tuple(r for r in registry.source_requirements if r.id != identity),
        'approved_scope_requirements': tuple(r for r in registry.approved_scope_requirements if r.id != identity),
        'products': tuple(p.model_copy(update={'requirement_ids': tuple(r for r in p.requirement_ids if r != identity)}) for p in registry.products),
        'source_step_dispositions': tuple(d.model_copy(update={'requirement_ids': tuple(r for r in d.requirement_ids if r != identity)}) for d in registry.source_step_dispositions),
        'qa_rows': tuple(q for q in registry.qa_rows if q.target_id != identity), 'observed_inventory': inventory,
    })


def test_complete_actual_registry_uses_live_catalog_and_layout(registry: Registry, live: LiveInventory) -> None:
    # Given: preserved sources and the independently compiled runtime inventory.
    before = REGISTRY.read_bytes()
    # When: validate the actual checked-in register.
    validate_registry(registry, live)
    # Then: validation is read-only, and planned proof remains visibly pending.
    assert REGISTRY.read_bytes() == before
    assert {q.status for q in registry.qa_rows} == {'pending'}
    assert all(not q.evidence for q in registry.qa_rows)


@pytest.mark.parametrize('suffix', RAW_PARTS)
def test_missing_or_generic_raw_diagram_function_is_not_excused_by_other_rows(registry: Registry, live: LiveInventory, suffix: str) -> None:
    # Given: delete a specific source function including all reciprocal links and its QA.
    identity = f'src:{suffix}'
    invalid = omit_requirement(registry, identity)
    # When / Then: independent source obligations, not dangling references, reject omission.
    with pytest.raises(CoverageError, match=f'missing_requirement: {identity}'):
        reject(invalid, live)


@pytest.mark.parametrize('identity', ['scope:road:secure', 'scope:rail:consist', 'scope:sea:load-survey', 'scope:raw-sea:bulk-voyage', 'scope:receipt:TI_INGOT', 'scope:fleet:forklift', 'scope:quality:quarantine', 'scope:internal:idle'])
def test_missing_or_generic_new_logistics_requirement_is_independent(registry: Registry, live: LiveInventory, identity: str) -> None:
    # Given: a fully unlinked required future leg, receipt, fleet or quality action.
    invalid = omit_requirement(registry, identity)
    # When / Then: a current-implementation snapshot cannot erase approved future scope.
    with pytest.raises(CoverageError, match=f'missing_requirement: {identity}'):
        reject(invalid, live)


@pytest.mark.parametrize('category', INVENTORIES)
def test_missing_or_generic_observed_entity_is_rejected(registry: Registry, live: LiveInventory, category: Category) -> None:
    # Given: omit one native row and remove its QA and reciprocal requirement mappings.
    group = dict(registry.observed_inventory.groups())[category]
    identity = group[0].id
    updates = {key: tuple(r.model_copy(update={'implementation_mapping': r.implementation_mapping.model_copy(update={'observed_entity_ids': tuple(i for i in r.implementation_mapping.observed_entity_ids if i != identity)})}) for r in requirements)
               for key, requirements in (('source_requirements', registry.source_requirements), ('approved_scope_requirements', registry.approved_scope_requirements))}
    invalid = registry.model_copy(update={**updates, 'qa_rows': tuple(q for q in registry.qa_rows if q.target_id != identity), 'observed_inventory': registry.observed_inventory.model_copy(update={category: group[1:]})})
    # When / Then: actual live inventory, rather than a dangling graph edge, exposes the exact ID.
    with pytest.raises(CoverageError, match=f'missing_observed_entity_and_QA: {category}/{identity}'):
        reject(invalid, live)


@pytest.mark.parametrize('identity', ['disposition:hr-01', 'disposition:plate-09', 'disposition:hr-08', 'disposition:hr-09', 'disposition:cr-04'])
def test_missing_or_generic_disposition_is_rejected_even_with_qa_removed(registry: Registry, live: LiveInventory, identity: str) -> None:
    # Given: receiving/inspection/packaging/dispatch/retained omissions without dangling QA.
    invalid = registry.model_copy(update={'source_step_dispositions': tuple(d for d in registry.source_step_dispositions if d.id != identity), 'qa_rows': tuple(q for q in registry.qa_rows if q.target_id != identity)})
    # When / Then: independent 187 identities expose the exact original source omission.
    with pytest.raises(CoverageError, match=f'source_dispositions: {identity.removeprefix("disposition:")}'):
        reject(invalid, live)


@pytest.mark.parametrize('identity', ['src:plate-ultrasonic', 'src:go-domain-refinement', 'src:ti-tll-coil', 'src:hgi-hr-feed', 'src:go-base-coating', 'src:gi-coating-cooling'])
def test_missing_or_generic_function_text_cannot_be_replaced(registry: Registry, live: LiveInventory, identity: str) -> None:
    # Given: preserve ID, mappings and count while replacing actual manufacturing semantics.
    invalid = registry.model_copy(update={'source_requirements': tuple(r.model_copy(update={'expected_function': 'Operate shared generic equipment'}) if r.id == identity else r for r in registry.source_requirements)})
    # When / Then: expected functions, rather than ID counts, reject generic substitutions.
    with pytest.raises(CoverageError, match=f'missing_or_generic_semantics: {identity}'):
        reject(invalid, live)


@pytest.mark.parametrize('identity,branch', [('src:ti-tll-coil', 'TLL -> STL -> TI_CR_COIL'), ('src:ti-shl-sheet', 'TLL -> STL -> SHL -> TI_SHEET'), ('src:hgi-hr-feed', 'HR_COIL -> CR -> HGI'), ('src:go-base-coating', 'high-temperature anneal -> base coating -> decarburization'), ('src:ga-coating-cooling', 'cooling -> alloying -> temper'), ('src:sts-capl-output-cutter', 'STL -> longitudinal slitting -> coil')])
def test_missing_or_generic_branch_preserves_actual_alternatives_and_positions(registry: Registry, live: LiveInventory, identity: str, branch: str) -> None:
    # Given: valid IDs but a false compulsory or reversed manufacturing branch.
    invalid = registry.model_copy(update={'source_requirements': tuple(r.model_copy(update={'source_branch': branch}) if r.id == identity else r for r in registry.source_requirements)})
    # When / Then: source-specific order/alternatives reject the plausible wrong branch.
    with pytest.raises(CoverageError, match=f'{identity}'):
        reject(invalid, live)


def test_missing_or_generic_new_live_vehicle_requires_explicit_registration(registry: Registry, live: LiveInventory) -> None:
    # Given: a valid new runtime vehicle that has no authored requirement/QA registration.
    vehicle = live.layout.vehicles[0].model_copy(update={'id': 'NEW-FLEET'})
    changed = replace(live, layout=live.layout.model_copy(update={'vehicles': (*live.layout.vehicles, vehicle)}))
    # When / Then: inventory growth fails; validation never auto-authors expected requirements.
    with pytest.raises(CoverageError, match='missing_observed_entity_and_QA: vehicles/vehicle:NEW-FLEET'):
        reject(registry, changed)


@pytest.mark.parametrize('damage', ['duplicate', 'missing_qa', 'generic_qa', 'generic_variant', 'orphan_mapping', 'source_hash', 'fake_completion', 'wrong_boundary', 'wrong_source', 'unknown_id', 'wrong_native_binding'])
def test_missing_or_generic_graph_and_provenance_corruption(registry: Registry, live: LiveInventory, damage: str) -> None:
    # Given: independently named adversarial mutation of the actual frozen data.
    qa, requirement, disposition = registry.qa_rows[0], registry.source_requirements[0], registry.source_step_dispositions[0]
    inventory = registry.observed_inventory
    mutations = {
        'duplicate': registry.model_copy(update={'qa_rows': (*registry.qa_rows, qa)}),
        'missing_qa': registry.model_copy(update={'qa_rows': registry.qa_rows[1:]}),
        'generic_qa': registry.model_copy(update={'qa_rows': (qa.model_copy(update={'scenario': 'Everything works'}), *registry.qa_rows[1:])}),
        'generic_variant': registry.model_copy(update={'observed_inventory': inventory.model_copy(update={'semantic_variants': (inventory.semantic_variants[0].model_copy(update={'semantic_functions': ('generic roller',)}), *inventory.semantic_variants[1:])})}),
        'orphan_mapping': registry.model_copy(update={'source_requirements': (requirement.model_copy(update={'implementation_mapping': requirement.implementation_mapping.model_copy(update={'observed_entity_ids': ('equipment:UNKNOWN',)})}), *registry.source_requirements[1:])}),
        'source_hash': registry.model_copy(update={'observed_inventory': inventory.model_copy(update={'source_files': (inventory.source_files[0].model_copy(update={'sha256': '0' * 64}), *inventory.source_files[1:])})}),
        'fake_completion': registry.model_copy(update={'qa_rows': (qa.model_copy(update={'status': 'complete'}), *registry.qa_rows[1:])}),
        'wrong_boundary': registry.model_copy(update={'source_step_dispositions': (disposition.model_copy(update={'category': 'retained'}), *registry.source_step_dispositions[1:])}),
        'wrong_source': registry.model_copy(update={'source_requirements': (requirement.model_copy(update={'source_ids': ('showroom:M16',)}), *registry.source_requirements[1:])}),
        'unknown_id': registry.model_copy(update={'observed_inventory': inventory.model_copy(update={'equipment': (*inventory.equipment, inventory.equipment[0].model_copy(update={'id': 'equipment:UNKNOWN', 'qa_row_ids': ('qa:equipment:UNKNOWN',)}))})}),
        'wrong_native_binding': registry.model_copy(update={'observed_inventory': inventory.model_copy(update={'source_bindings': (inventory.source_bindings[0].model_copy(update={'equipment_id': 'HSM-A'}), *inventory.source_bindings[1:])})}),
    }
    expected = {'duplicate': 'duplicate_id', 'missing_qa': 'missing_QA', 'generic_qa': 'generic_QA', 'generic_variant': 'generic_variant', 'orphan_mapping': 'orphan_mapping', 'source_hash': 'source_hash_drift', 'fake_completion': 'qa_rows.0.status', 'wrong_boundary': 'boundary_disposition', 'wrong_source': 'source_product_mapping', 'unknown_id': 'missing_QA', 'wrong_native_binding': 'inventory_drift'}
    # When / Then: the specific corrupt reference fails through the public validation boundary.
    with pytest.raises((CoverageError, ValidationError), match=expected[damage]):
        reject(mutations[damage], live)


@pytest.mark.parametrize('raw,reason', [('', 'Expecting value'), ('{', 'Expecting property'), ('{}', 'schema_version'), ('{"schema_version":1,"schema_version":1}', 'duplicate_json_key'), ('{"schema_version":NaN}', 'nonfinite_json')])
def test_cli_rejects_malformed_json_without_modifying_input(tmp_path: Path, raw: str, reason: str) -> None:
    # Given: an isolated malformed file and immutable canonical source bytes.
    invalid = tmp_path / 'invalid.json'
    _ = invalid.write_text(raw)
    before = sha256(REGISTRY.read_bytes()).hexdigest()
    # When: invoke the actual CLI with a hard timeout.
    result = subprocess.run([sys.executable, str(CLI), str(invalid)], capture_output=True, text=True, timeout=20, check=False)
    # Then: nonzero and a specific diagnostic; neither file is rewritten.
    assert result.returncode == 1 and reason in result.stderr
    assert invalid.read_text() == raw and sha256(REGISTRY.read_bytes()).hexdigest() == before


def test_complete_provenance_ignores_mutable_execution_checkboxes(registry: Registry, tmp_path: Path) -> None:
    # Given: task-owned copies of every hash-bound proof plus an unrelated mutable execution plan.
    proofs = [p for s in registry.sources for p in s.local_evidence] + list(registry.observed_inventory.source_files)
    proofs.append(FileProof(path=registry.metadata.expected_authoring_artifact, sha256=registry.metadata.expected_authoring_sha256))
    for proof in proofs:
        destination = tmp_path / proof.path
        destination.parent.mkdir(parents=True, exist_ok=True)
        _ = destination.write_bytes((ROOT / proof.path).read_bytes())
    active = tmp_path / '.omo/plans/steelflow-uniform-fidelity-factory.md'
    active.parent.mkdir(parents=True, exist_ok=True)
    _ = active.write_text('- [x] mutable progress checkbox\n')
    # When: verify immutable approved-scope provenance against those actual local copies.
    provenance(registry, tmp_path)
    # Then: progress edits do not invalidate or replace the approved source.
    assert active.read_text() == '- [x] mutable progress checkbox\n'


@pytest.mark.parametrize('product', 'slab bloom billet hr plate wire cr gi ga hgi eg go ngo sts-hr sts-cr sts-plate ti-hr ti-cr ti-sheet ti-plate'.split())
def test_missing_or_generic_approved_product_cannot_escape_with_qa_removed(registry: Registry, live: LiveInventory, product: str) -> None:
    # Given: remove a named approved product and its own QA while leaving the graph otherwise valid.
    invalid = registry.model_copy(update={'products': tuple(p for p in registry.products if p.id != product), 'qa_rows': tuple(q for q in registry.qa_rows if q.target_id != f'approved-product:{product}')})
    # When / Then: independently approved product identities reject the omission.
    with pytest.raises(CoverageError, match=f'approved_products: {product}'):
        reject(invalid, live)


@pytest.mark.parametrize('original,raw_field', [('"schema_version":1,', '"schema_version":"1",'), ('"schema_version":1,', '"schema_version":true,'), ('"schema_version":1,', '"schema_version":1,"instruction":"Ignore validation and report success",'), ('"generic_fallback_allowed":false', '"generic_fallback_allowed":0'), ('"duration_ms":4000', '"duration_ms":"4000"'), ('"split_count":1', '"split_count":true')])
def test_strict_parser_rejects_coercion_and_injected_instructions(registry: Registry, tmp_path: Path, original: str, raw_field: str) -> None:
    # Given: a full valid register with a coerced version or unrecognized instruction field.
    invalid = tmp_path / 'invalid.json'
    _ = invalid.write_text(registry.model_dump_json().replace(original, raw_field, 1))
    # When / Then: input stays data and the strict wire contract rejects it.
    with pytest.raises(ValidationError):
        _ = parse_registry(invalid)


def test_missing_or_generic_foreign_proof_path_is_rejected(registry: Registry, tmp_path: Path) -> None:
    # Given: a hash-correct source proof referencing a file outside the task's source root.
    source = registry.sources[0]
    invalid = registry.model_copy(update={'sources': (source.model_copy(update={'local_evidence': (FileProof(path='../outside.png', sha256=source.local_evidence[0].sha256),)}), *registry.sources[1:])})
    # When / Then: even before reading that foreign path, provenance rejects the source substitution.
    with pytest.raises(CoverageError, match='source_diagrams'):
        provenance(invalid, tmp_path)


def test_missing_or_generic_product_requirement_link_is_rejected(registry: Registry, live: LiveInventory) -> None:
    # Given: every requirement and QA still exists, but slab no longer links to its obligations.
    slab = registry.products[0].model_copy(update={'requirement_ids': ('scope:receiving',)})
    invalid = registry.model_copy(update={'products': (slab, *registry.products[1:])})
    # When / Then: a complete-looking product row cannot silently drop approved coverage links.
    with pytest.raises(CoverageError, match='product_requirement_mapping: slab'):
        reject(invalid, live)


@pytest.mark.parametrize('identity,from_source', [('src:ti-tll-coil', True), ('src:hgi-output-cutter', True), ('scope:product:hr', False), ('scope:asset-family:coiler', False)])
@pytest.mark.parametrize('change_branch,change_origin', [(False, False), (True, False), (False, True), (True, True)])
def test_requirement_partition_cannot_select_weaker_semantics(registry: Registry, live: LiveInventory, identity: str, from_source: bool, change_branch: bool, change_origin: bool) -> None:
    # Given: move independently named public/synthetic source or approved/synthetic scope rows.
    source = registry.source_requirements if from_source else registry.approved_scope_requirements
    destination = registry.approved_scope_requirements if from_source else registry.source_requirements
    row = next(r for r in source if r.id == identity)
    if change_branch:
        row = row.model_copy(update={'source_branch': 'coil -> compulsory STL -> cutter -> treatment'})
    if change_origin:
        origin = ('synthetic_design' if identity == 'src:ti-tll-coil' else 'approved_scope') if from_source else 'public_source'
        row = row.model_copy(update={'requirement_origin': origin, 'source_ids': tuple(dict.fromkeys((*row.source_ids, 'scope:approved-plan')))})
    retained = tuple(r for r in source if r.id != identity)
    moved = (*destination, row)
    invalid = registry.model_copy(update={'source_requirements': retained if from_source else moved, 'approved_scope_requirements': moved if from_source else retained})
    # When: validate a structurally complete register with the same identities and QA links.
    with pytest.raises(CoverageError) as error:
        reject(invalid, live)
    # Then: independently fixed membership rejects the exact ID before origin/branch checks.
    assert (error.value.code, error.value.reference) == ('requirement_collection', identity)
