"""Read-only projection of the preserved catalog and physical layout."""
import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final

from app.operations.catalog import (
    FORM_OVERRIDES,
    OperationsCatalog,
    RouteStep,
    SourceDisposition,
    canonical_form,
    load_catalog,
)
from app.operations.layout import FactoryLayout, load_factory_layout
from pydantic import JsonValue

from tools.qa.coverage_expectations import require
from tools.qa.coverage_models import Category, FileProof, Registry

SOURCE_FILES: Final = frozenset({
    'backend/app/data/journey_products.json', 'backend/app/data/operations_routes.json',
    'backend/app/operations/catalog.py', 'backend/app/operations/layout.py', 'shared/factory-layout.json',
})


@dataclass(frozen=True, slots=True)
class LiveInventory:
    catalog: OperationsCatalog
    layout: FactoryLayout

    @classmethod
    def read(cls) -> 'LiveInventory':
        return cls(load_catalog(), load_factory_layout())

    def dispositions(self) -> Mapping[str, SourceDisposition]:
        return {row.source_step.id: row for row in self.catalog.manifest}

    def refresh_finishing_forms(self, registry: Registry, root: Path) -> Registry:
        """Project only nine sealed source form changes; compare rejects all other drift."""
        source = self.dispositions()
        compiled = {step.key: step for route in self.catalog.routes for step in route.steps}
        rows = []
        for row in registry.observed_inventory.compiled_steps:
            target = compiled.get(row.key)
            require(target is not None, 'unknown_observed_entity', row.id)
            if target is None:
                continue
            forms: dict[str, str] = {}
            if row.source_step_id in FORM_OVERRIDES:
                original = source[row.source_step_id].source_step
                for field in ('input_form', 'output_form'):
                    old = canonical_form(getattr(original, field))
                    new = getattr(target, field)
                    require(getattr(row, field) in (old, new), 'inventory_drift', row.id + ':' + field)
                    forms[field] = new
            rows.append(row.model_copy(update=forms))
        proofs = registry.observed_inventory.source_files
        require(len(proofs) == len(SOURCE_FILES) and {p.path for p in proofs} == SOURCE_FILES, 'inventory_source_files', 'observed_inventory.source_files')
        refreshed = []
        for proof in proofs:
            digest = sha256((root / proof.path).read_bytes()).hexdigest()
            require(proof.path in {'backend/app/operations/catalog.py', 'backend/app/data/operations_routes.json'} or digest == proof.sha256, 'source_hash_drift', proof.path)
            refreshed.append(FileProof(path=proof.path, sha256=digest))
        observed = registry.observed_inventory.model_copy(update={'compiled_steps': tuple(rows), 'source_files': tuple(refreshed)})
        result = registry.model_copy(update={'observed_inventory': observed})
        self.compare(result)
        return result

    def compare(self, registry: Registry) -> None:
        """Compare every observed identity and native semantic field to current parsed files."""
        rows: dict[str, str] = {}

        def add(category: Category, identity: str, **fields: JsonValue) -> None:
            key = f'{category}/{identity}'
            require(key not in rows, 'duplicate_live_entity', key)
            rows[key] = json.dumps(fields, sort_keys=True)

        for route in self.catalog.routes:
            add('products', f'product:{route.product_id}', native_id=route.product_id,
                input_form=route.input_form, output_form=route.output_form, blocks=list(route.blocks))
            for step in route.steps:
                fields: dict[str, JsonValue] = {
                    'native_id': step.key, 'product_id': route.product_id, 'key': step.key,
                    'ordinal': step.ordinal, 'source_step_id': step.source_step_id,
                    'source_product_id': step.source_product_id, 'source_url': step.source_url,
                    'source_title': step.source_title, 'name': step.name, 'description': step.description,
                    'equipment_id': step.equipment_id, 'equipment_kind': step.equipment_kind,
                    'duration_ms': step.duration_ms, 'input_form': step.input_form, 'output_form': step.output_form,
                    'role': step.role, 'additions_kg': step.additions_kg, 'loss_kg': step.loss_kg, 'split_count': step.split_count,
                }
                require(set(fields) == {'native_id', 'product_id', *RouteStep.model_fields}, 'unhandled_step_field', step.key)
                add('compiled_steps', f'step:{step.key}', **fields)
        for route in self.layout.routes:
            for ordinal, path in enumerate(route.path_ids):
                add('compiled_connections', f'connection:{route.product_id}:{ordinal + 1:03}',
                    native_id=f'{route.product_id}:{path}', product_id=route.product_id, path_id=path,
                    from_equipment_id=route.equipment_ids[ordinal], to_equipment_id=route.equipment_ids[ordinal + 1], ordinal=ordinal)
        for equipment in self.layout.equipment:
            add('equipment', f'equipment:{equipment.id}', native_id=equipment.id, stage_id=equipment.stage_id,
                kind=equipment.kind, semantic_variant_id=f'variant:{equipment.kind}:{equipment.id}',
                source_step_ids=[b.source_step_id for b in self.layout.source_bindings if b.equipment_id == equipment.id])
            add('semantic_variants', f'variant:{equipment.kind}:{equipment.id}',
                native_id=f'{equipment.kind}:{equipment.id}', kind=equipment.kind, equipment_ids=[equipment.id])
        for kind in {e.kind for e in self.layout.equipment}:
            add('kinds', f'kind:{kind}', native_id=kind, equipment_ids=[e.id for e in self.layout.equipment if e.kind == kind])
        for stage in self.layout.stages:
            add('stages', f'stage:{stage.id}', native_id=stage.id, equipment_ids=[e.id for e in self.layout.equipment if e.stage_id == stage.id])
        for binding in self.layout.source_bindings:
            add('source_bindings', f'binding:{binding.source_step_id}', native_id=binding.source_step_id,
                source_step_id=binding.source_step_id, equipment_id=binding.equipment_id)
        for path in self.layout.paths:
            add('paths', f'path:{path.id}', native_id=path.id, from_location_id=path.from_location_id,
                to_location_id=path.to_location_id, mode=path.mode, network=path.network)
        for crane in self.layout.cranes:
            add('cranes', f'crane:{crane.id}', native_id=crane.id, location_id=crane.location_id,
                pick_location_id=crane.pick_location_id, drop_location_id=crane.drop_location_id)
        for vehicle in self.layout.vehicles:
            add('vehicles', f'vehicle:{vehicle.id}', native_id=vehicle.id, mode=vehicle.mode, network=vehicle.network)
        registered = {f'{category}/{row.id}': row for category, group in registry.observed_inventory.groups() for row in group}
        for key in sorted(rows.keys() - registered.keys()):
            require(False, 'missing_observed_entity_and_QA', key)
        for key in sorted(registered.keys() - rows.keys()):
            require(False, 'unknown_observed_entity', key)
        for key, row in registered.items():
            # Projection excludes authored links; they are independently checked by the validator.
            actual = row.model_dump_json(exclude={'id', 'requirement_ids', 'qa_row_ids', 'semantic_functions', 'reuse_policy'})
            require(json.dumps(json.loads(actual), sort_keys=True) == rows[key], 'inventory_drift', key)
