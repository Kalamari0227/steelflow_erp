// @vitest-environment node
import { readFileSync } from 'node:fs';
import corpus from '../../../../shared/fixtures/asset-manifest-cases.json';
import policy from '../../../../shared/asset-requirements.json';
import { describe, expect, it } from 'vitest';
import { AssetManifestError, parseAssetManifest, parseAssetManifestValue, parseProductionAssetManifest } from './manifest';

import { changed, corruptions, equipmentExample, fixture, frozen, policyExample, rawFixture, required } from './manifestTestFixtures';
import type { ExampleAsset } from './manifestTestFixtures';

describe('asset metadata admission', () => {
  it('valid preserves the independently authored shear identity', () => {
    // Given
    const raw = rawFixture();
    // When
    const parsed = parseAssetManifest(raw);
    // Then
    expect(parsed.assets[0]).toMatchObject({ kind: 'shear', variant: 'variant:shear:CUT-SLAB', placement_ids: ['equipment:CUT-SLAB'] });
  });

  it('license_or_binding_missing rejects a manifest without operational bindings', () => {
    // Given
    const parsed = parseAssetManifest(rawFixture());
    const input = { ...parsed, assets: parsed.assets.map(asset => ({ ...asset, moving_parts: [] })) };
    // When
    const action = () => parseAssetManifestValue(input);
    // Then
    expect(action).toThrow(AssetManifestError);
  });

  it('rejects example metadata at the production admission boundary', () => {
    // Given
    const raw = rawFixture();
    // When
    const action = () => parseProductionAssetManifest(raw);
    // Then
    expect(action).toThrow(/production/);
  });
});


it.each(corpus.cases)('license_or_binding_missing rejects shared $name', row => {
  // Given
  const before = JSON.stringify(row.manifest);
  // When
  const action = () => parseAssetManifestValue(row.manifest);
  // Then
  expect(action).toThrow(AssetManifestError);
  expect(JSON.stringify(row.manifest)).toBe(before);
});

it('valid returns deeply immutable data independent of mutable caller input', () => {
  // Given
  const input = fixture();
  // When
  const parsed = parseAssetManifestValue(input);
  // Then
  expect(frozen(parsed)).toBe(true);
  required(input.assets[0]).nodes.length = 0;
  expect(parsed.assets[0]?.nodes).toHaveLength(3);
});

it.each(corruptions)('rejects $name with a classified error', ({ edit, code }) => {
  // Given
  const input = changed(edit);
  // When
  const action = () => parseAssetManifestValue(input);
  // Then
  expect(action).toThrow(expect.objectContaining({ code }));
});

it.each(['"schema_version": 1,', '"schema_versi\\u006fn": 1,'])('rejects duplicate decoded JSON keys %s', duplicate => {
  // Given
  const raw = rawFixture().replace('{', `{${duplicate}`);
  // When
  const action = () => parseAssetManifest(raw);
  // Then
  expect(action).toThrow(/duplicate key: schema_version/);
});

it('rejects mismatched clock bindings with both clip and procedure selectors', () => {
  // Given
  const input = changed(asset => { Object.assign(required(asset.moving_parts[0]).binding, { clip_id: 'clip' }); });
  // When
  const action = () => parseAssetManifestValue(input);
  // Then
  expect(action).toThrow(expect.objectContaining({ code: 'schema' }));
});

it.each(policy.policies)('valid applies the common metadata rubric to $category/$kind', row => {
  // Given
  const input = policyExample(row);
  // When
  const parsed = parseAssetManifestValue(input);
  // Then
  expect(parsed.assets[0]?.kind).toBe(row.kind);
  expect(frozen(parsed)).toBe(true);
});

it.each(policy.policies.filter(row => row.required_functions.length > 0))('rejects decorative operational substitution for $category/$kind', row => {
  // Given
  const input = policyExample(row);
  required(required(input.assets[0]).moving_parts[0]).role = 'decorative';
  // When
  const action = () => parseAssetManifestValue(input);
  // Then
  expect(action).toThrow(expect.objectContaining({ code: 'requirements' }));
});

it.each(policy.policies.filter(row => row.fixed_functions.length > 0))('rejects missing fixed function for $category/$kind', row => {
  // Given
  const input = policyExample(row);
  required(input.assets[0]).fixed_parts = [];
  // When
  const action = () => parseAssetManifestValue(input);
  // Then
  expect(action).toThrow(expect.objectContaining({ code: 'requirements' }));
});

it.each(policy.policies.filter(row => row.roof_required))('rejects cutaway deleting interior for $category/$kind', row => {
  // Given
  const input = policyExample(row);
  required(required(input.assets[0]).nodes.find(node => node.id === 'support_bed')).parent_id = 'roof';
  // When
  const action = () => parseAssetManifestValue(input);
  // Then
  expect(action).toThrow(expect.objectContaining({ code: 'requirements' }));
});

it('valid accepts quaternion sign equivalence without permitting a changed orientation', () => {
  // Given
  const input = changed(asset => { required(required(asset.lods[1]).nodes[1]).transform.rotation_xyzw = [0, 0, 0, -1]; });
  // When
  const parsed = parseAssetManifestValue(input);
  // Then
  expect(parsed.assets[0]?.lods[1]?.nodes[1]?.transform.rotation_xyzw).toEqual([0, 0, 0, -1]);
});

it('valid preserves internal pitch instead of reducing it to root yaw', () => {
  // Given
  const input = changed(asset => {
    required(asset.nodes[1]).transform.rotation_xyzw = [0.5, 0, 0, Math.sqrt(0.75)];
    for (const lod of asset.lods) required(lod.nodes[1]).transform.rotation_xyzw = [0.5, 0, 0, Math.sqrt(0.75)];
  });
  // When
  const parsed = parseAssetManifestValue(input);
  // Then
  expect(parsed.assets[0]?.nodes[1]?.transform.rotation_xyzw[0]).toBe(0.5);
});

it('valid admits a clip binding with the same authoritative phase clock', () => {
  // Given
  const input = changed(asset => {
    const binding = required(asset.moving_parts[0]).binding;
    Reflect.deleteProperty(binding, 'procedure_id');
    Object.assign(binding, { type: 'clip', clip_id: 'shear.clip' });
  });
  // When
  const parsed = parseAssetManifestValue(input);
  // Then
  expect(parsed.assets[0]?.moving_parts[0]?.binding).toMatchObject({ type: 'clip', clip_id: 'shear.clip', clock: 'server_sim' });
});

it.each(['clock', 'progress_source', 'pause', 'fault', 'rest', 'phase'])('license_or_binding_missing rejects missing binding %s', key => {
  // Given
  const input = changed(asset => { Reflect.deleteProperty(required(asset.moving_parts[0]).binding, key); });
  // When
  const action = () => parseAssetManifestValue(input);
  // Then
  expect(action).toThrow(expect.objectContaining({ code: 'schema' }));
});

it('rejects consumer-declared production status for unbuilt artifacts', () => {
  // Given
  const input = { ...fixture(), purpose: 'production' };
  // When
  const action = () => parseProductionAssetManifest(JSON.stringify(input));
  // Then
  expect(action).toThrow(expect.objectContaining({ code: 'artifact' }));
});

it.each([
  { name: 'reused LOD artifact path', edit: (asset: ExampleAsset) => { required(asset.lods[1]).artifact.path = required(asset.lods[0]).artifact.path; } },
  { name: 'GLB source instead of editable blend', edit: (asset: ExampleAsset) => { asset.source.artifact.path = 'source/asset.glb'; } },
  { name: 'non-GLB export', edit: (asset: ExampleAsset) => { required(asset.lods[0]).artifact.path = 'source/asset.txt'; } },
])('rejects $name', ({ edit }) => {
  // Given
  const input = changed(edit);
  // When
  const action = () => parseAssetManifestValue(input);
  // Then
  expect(action).toThrow(AssetManifestError);
});

it('rejects decor laundering even when a caller mutates its imported policy object', () => {
  // Given
  const row = required(policy.policies.find(candidate => candidate.category === 'equipment' && candidate.kind === 'shear'));
  const functions = row.required_functions;
  const input = changed(asset => { required(asset.moving_parts[0]).role = 'decorative'; });
  row.required_functions = [];
  try {
    // When
    const action = () => parseAssetManifestValue(input);
    // Then
    expect(action).toThrow(expect.objectContaining({ code: 'requirements' }));
  } finally { row.required_functions = functions; }
});

it.each(policy.policies.filter(row => row.state_bound_fixed_functions.length > 0))('license_or_binding_missing rejects an unbound fixed operating state for $category/$kind', row => {
  // Given
  const input = policyExample(row);
  const asset = required(input.assets[0]);
  const parts: unknown = asset.fixed_parts;
  if (!Array.isArray(parts)) throw new RangeError('fixed fixture parts');
  const part: unknown = parts.find(item => typeof item === 'object' && item !== null && 'function' in item && item.function === row.state_bound_fixed_functions[0]);
  if (typeof part !== 'object' || part === null) throw new RangeError('fixed state fixture missing');
  Object.assign(part, { binding: null });
  // When
  const action = () => parseAssetManifestValue(input);
  // Then
  expect(action).toThrow(expect.objectContaining({ code: 'requirements' }));
});

it('valid represents air knives as fixed gas-wiping states rather than geometric motion', () => {
  // Given
  const input = policyExample(required(policy.policies.find(row => row.kind === 'galvanizing')));
  // When
  const parsed = parseAssetManifestValue(input);
  // Then
  expect(parsed.assets[0]?.fixed_parts.find(part => part.function === 'air_knife')?.binding).toMatchObject({ type: 'operational_state', clock: 'server_sim' });
  expect(parsed.assets[0]?.moving_parts.map(part => part.function)).toEqual(['sink_roll']);
});

it('rejects renamed minimum semantic anchors even in a single otherwise consistent variant', () => {
  // Given
  const input = changed(asset => {
    required(asset.nodes[1]).id = 'renamed';
    required(asset.moving_parts[0]).id = 'renamed';
    required(asset.moving_parts[0]).node_id = 'renamed';
    required(asset.collision_proxies[1]).part_id = 'renamed';
    for (const lod of asset.lods) { required(lod.nodes[1]).id = 'renamed'; lod.part_ids = ['renamed']; }
  });
  // When
  const action = () => parseAssetManifestValue(input);
  // Then
  expect(action).toThrow(expect.objectContaining({ code: 'requirements' }));
});

it('rejects renamed required socket anchors even when all references are updated', () => {
  // Given
  const input = changed(asset => {
    required(asset.sockets[0]).id = 'renamed';
    for (const proxy of asset.collision_proxies) proxy.contact_socket_ids = proxy.contact_socket_ids.map(id => id === 'support' ? 'renamed' : id);
    for (const lod of asset.lods) lod.socket_ids = lod.socket_ids.map(id => id === 'support' ? 'renamed' : id);
  });
  // When
  const action = () => parseAssetManifestValue(input);
  // Then
  expect(action).toThrow(expect.objectContaining({ code: 'requirements' }));
});

it('valid admits independently authored fixed-state galvanizing metadata', () => {
  // Given
  const raw = readFileSync('shared/fixtures/asset-manifest-fixed-state-valid.json', 'utf8');
  // When
  const parsed = parseAssetManifest(raw);
  // Then
  expect(parsed.assets[0]?.variant).toBe('variant:galvanizing:CS-GI-05');
  expect(parsed.assets[0]?.fixed_parts.find(part => part.function === 'air_knife')?.binding).toMatchObject({ type: 'operational_state', clock: 'server_sim' });
});

it.each(policy.existing_bindings)('valid binds registered family and placement for $variant', binding => {
  // Given
  const input = equipmentExample(binding.variant);
  // When
  const parsed = parseAssetManifestValue(input);
  // Then
  expect(parsed.assets[0]).toMatchObject({ variant: binding.variant, family: binding.allowed_families[0], placement_ids: binding.placement_ids });
});

it.each([
  { variant: 'variant:shear:CUT-SLAB', wrongFamily: 'titanium' },
  { variant: 'variant:shear:TI-SHEET-09', wrongFamily: 'steelmaking' },
  { variant: 'variant:shear:STS-PLATE-09', wrongFamily: 'hot-rolling' },
])('rejects family laundering for $variant even when its kind permits $wrongFamily', ({ variant, wrongFamily }) => {
  // Given
  const input = equipmentExample(variant), asset = required(input.assets[0]);
  asset.family = wrongFamily;
  // When
  const action = () => parseAssetManifestValue(input);
  // Then
  expect(action).toThrow(new AssetManifestError('requirements', `${asset.id}:variant-family`));
});

it('rejects the exact H1 family swap after retagging requirement and source metadata', () => {
  // Given
  const input = changed(asset => {
    asset.family = 'titanium';
    asset.requirement_ids.push('src:ti-sheet-09');
    asset.source_refs = [{ id: 'src:ti-sheet-09', uri: '.omo/plans/steelflow-uniform-fidelity-factory.md', note: 'Adversarial relabel; this is still the unchanged carbon slab placement.' }];
  });
  // When
  const action = () => parseAssetManifestValue(input);
  // Then
  expect(action).toThrow(new AssetManifestError('requirements', 'example:shear:CUT-SLAB:variant-family'));
});

it('rejects family laundering despite caller mutation of imported variant-family policy', () => {
  // Given
  const binding = required(policy.existing_bindings.find(row => row.variant === 'variant:shear:CUT-SLAB'));
  const families = binding.allowed_families;
  const input = changed(asset => { asset.family = 'titanium'; });
  binding.allowed_families = ['titanium'];
  try {
    // When
    const action = () => parseAssetManifestValue(input);
    // Then
    expect(action).toThrow(new AssetManifestError('requirements', 'example:shear:CUT-SLAB:variant-family'));
  } finally { binding.allowed_families = families; }
});

it('valid permits explicit shared source ownership with distinct correct variant families', () => {
  // Given
  const carbon = required(equipmentExample('variant:shear:CUT-SLAB').assets[0]);
  const titanium = required(equipmentExample('variant:shear:TI-SHEET-09').assets[0]);
  const input = { ...fixture(), assets: [carbon, titanium] };
  // When
  const parsed = parseAssetManifestValue(input);
  // Then
  expect(parsed.assets.map(asset => asset.family)).toEqual(['steelmaking', 'titanium']);
  expect(parsed.assets[0]?.source).toEqual(parsed.assets[1]?.source);
});
