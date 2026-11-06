import { readFileSync } from 'node:fs';
import example from '../../../../shared/fixtures/asset-manifest-valid.json';
import policy from '../../../../shared/asset-requirements.json';
import coverage from '../../../../shared/coverage-registry.json';

export function rawFixture(): string { return readFileSync('shared/fixtures/asset-manifest-valid.json', 'utf8'); }

export type ExampleAsset = (typeof example)['assets'][number];
export function required<T>(value: T | undefined): T { if (value === undefined) throw new RangeError('fixture missing'); return value; }
export function fixture() { return structuredClone(example); }
export function changed(edit: (asset: ExampleAsset) => void) {
  const input = fixture();
  edit(required(input.assets[0]));
  return input;
}
export function frozen(value: unknown): boolean {
  return typeof value !== 'object' || value === null || (Object.isFrozen(value) && Object.values(value).every(frozen));
}

export const corruptions: readonly { readonly name: string; readonly edit: (asset: ExampleAsset) => void; readonly code: string }[] = [
  { name: 'unknown nested field', edit: asset => { Object.assign(asset.sockets[0] ?? {}, { exemption: true }); }, code: 'schema' },
  { name: 'nonunit quaternion', edit: asset => { required(asset.nodes[1]).transform.rotation_xyzw = [0, 0, 0, 0.5]; }, code: 'numeric' },
  { name: 'tilted root', edit: asset => { required(asset.nodes[0]).transform.rotation_xyzw = [Math.SQRT1_2, 0, 0, Math.SQRT1_2]; }, code: 'numeric' },
  { name: 'offset root', edit: asset => { required(asset.nodes[0]).transform.position_m = [1, 0, 0]; }, code: 'numeric' },
  { name: 'wrong exporter conversion', edit: asset => { asset.export.conversion_rotation_xyzw = [0, 0, 0, 1]; }, code: 'numeric' },
  { name: 'cycle', edit: asset => { required(asset.nodes[1]).parent_id = required(asset.nodes[1]).id; }, code: 'reference' },
  { name: 'unknown parent', edit: asset => { required(asset.nodes[1]).parent_id = 'unknown'; }, code: 'reference' },
  { name: 'duplicate locator', edit: asset => { required(asset.nodes[1]).locator = 'root'; }, code: 'identity' },
  { name: 'bad normal', edit: asset => { required(asset.sockets[0]).normal = [0, 0, 0]; }, code: 'numeric' },
  { name: 'rest outside range', edit: asset => { required(asset.moving_parts[0]).range.rest = 1; }, code: 'numeric' },
  { name: 'equal range bounds', edit: asset => { required(asset.moving_parts[0]).range.max = 0; }, code: 'numeric' },
  { name: 'unsafe coordinate', edit: asset => { required(asset.nodes[1]).transform.position_m[0] = Number.MAX_SAFE_INTEGER; }, code: 'schema' },
  { name: 'nonfinite coordinate', edit: asset => { required(asset.nodes[1]).transform.position_m[0] = Infinity; }, code: 'schema' },
  { name: 'NaN coordinate', edit: asset => { required(asset.nodes[1]).transform.position_m[0] = NaN; }, code: 'schema' },
  { name: 'missing motion sweep', edit: asset => { asset.collision_proxies = asset.collision_proxies.filter(proxy => proxy.purpose === 'body'); }, code: 'collision' },
  { name: 'unknown contact', edit: asset => { required(asset.collision_proxies[0]).contact_socket_ids = ['unknown']; }, code: 'reference' },
  { name: 'body posing as moving sweep', edit: asset => { required(asset.collision_proxies[0]).part_id = 'cutting_tool'; }, code: 'collision' },
  { name: 'missing LOD0', edit: asset => { asset.lods = asset.lods.filter(lod => lod.level !== 0); }, code: 'lod' },
  { name: 'duplicate LOD', edit: asset => { required(asset.lods[1]).level = 0; }, code: 'identity' },
  { name: 'LOD material drift', edit: asset => { required(asset.lods[1]).material_ids = ['unknown']; }, code: 'lod' },
  { name: 'LOD part drift', edit: asset => { required(asset.lods[1]).part_ids = []; }, code: 'lod' },
  { name: 'unknown texture', edit: asset => { required(required(asset.materials[0]).textures[0]).texture_id = 'unknown'; }, code: 'reference' },
  { name: 'texture color space', edit: asset => { required(asset.textures[0]).color_space = 'linear'; }, code: 'requirements' },
  { name: 'duplicate material slot', edit: asset => { required(asset.materials[0]).textures.push(structuredClone(required(required(asset.materials[0]).textures[0]))); }, code: 'identity' },
  { name: 'untracked third-party source', edit: asset => { Object.assign(asset.source.provenance, { third_party_inputs: ['unknown'] }); }, code: 'license' },
  { name: 'self-created input laundering', edit: asset => { Object.assign(asset.source.provenance, { third_party_inputs: ['paint_color'] }); }, code: 'license' },
  { name: 'self-referential license', edit: asset => { Object.assign(asset.source.provenance, { third_party_inputs: [asset.id] }); }, code: 'license' },
  { name: 'empty creator', edit: asset => { asset.source.provenance.creator = ' '; }, code: 'schema' },
  { name: 'path traversal', edit: asset => { asset.source.artifact.path = 'source/../secret.blend'; }, code: 'schema' },
  { name: 'source url injection', edit: asset => { required(asset.source_refs[0]).id = 'unknown'; }, code: 'reference' },
  { name: 'wrong registered kind', edit: asset => { asset.kind = 'stock'; asset.family = 'campus'; asset.requirement_ids.push('scope:asset-family:stock'); }, code: 'requirements' },
  { name: 'category swap', edit: asset => { asset.category = 'campus'; asset.kind = 'raw-yard'; asset.family = 'campus'; asset.requirement_ids.push('scope:receiving:store'); }, code: 'requirements' },
  { name: 'missing placement mapping', edit: asset => { asset.placement_ids = ['equipment:CUT-BLOOM']; }, code: 'requirements' },
  { name: 'unrelated QA row', edit: asset => { asset.qa_row_ids.push('qa:equipment:BF-A'); }, code: 'requirements' },
  { name: 'required work hidden as decor', edit: asset => { required(asset.moving_parts[0]).role = 'decorative'; }, code: 'requirements' },
  { name: 'generic loop replacing cutter', edit: asset => { required(asset.moving_parts[0]).function = 'generic_loop'; }, code: 'requirements' },
];
export function policyExample(row: (typeof policy.policies)[number]) {
  const input = fixture();
  const asset = required(input.assets[0]);
  const binding = policy.planned_bindings.find(candidate => candidate.category === row.category && candidate.kind === row.kind);
  const extension = policy.existing_bindings.find(candidate => 'extension_policy_id' in candidate && candidate.extension_policy_id === row.id);
  const variant = coverage.observed_inventory.semantic_variants.find(candidate => extension === undefined ? candidate.kind === row.kind : candidate.id === extension.variant);
  if (extension !== undefined) Object.assign(asset, { motion_policy_id: row.id });
  asset.id = `example:${row.category}:${row.kind}`;
  asset.category = row.category;
  asset.kind = row.kind;
  asset.family = required(row.families[0]);
  if (binding) {
    asset.variant = binding.variant;
    asset.placement_ids = [...binding.placement_ids];
    asset.requirement_ids = [...binding.requirement_ids];
    asset.qa_row_ids = [...binding.qa_row_ids];
  } else {
    const known = required(variant);
    const registered = required(policy.existing_bindings.find(candidate => candidate.variant === known.id));
    asset.family = required(registered.allowed_families[0]);
    asset.variant = known.id;
    asset.placement_ids = known.equipment_ids.map(id => `equipment:${id}`);
    asset.requirement_ids = [...known.requirement_ids];
    asset.qa_row_ids = [...known.qa_row_ids, ...coverage.observed_inventory.equipment.filter(equipment => asset.placement_ids.includes(equipment.id)).flatMap(equipment => equipment.qa_row_ids)];
  }
  asset.source_refs = [{ id: required(asset.requirement_ids[0]), uri: '.omo/plans/steelflow-uniform-fidelity-factory.md', note: 'Metadata-only contract test; unbuilt, no actual model asserted.' }];
  const root = structuredClone(required(asset.nodes[0]));
  const mechanicalNode = structuredClone(required(asset.nodes[1]));
  asset.nodes = [root, { ...mechanicalNode, id: 'support_bed', locator: 'root/support_bed' }];
  asset.moving_parts = row.required_functions.map(fn => ({ ...structuredClone(required(example.assets[0]?.moving_parts[0])), id: fn, function: fn, node_id: fn }));
  asset.fixed_parts = [];
  for (const fn of row.required_functions) asset.nodes.push({ ...structuredClone(mechanicalNode), id: fn, locator: `root/${fn}` });
  // The baseline example has no fixed part; this explicit structural object is test input only.
  Object.assign(asset, { fixed_parts: row.fixed_functions.map(fn => ({ id: fn, node_id: fn, function: fn, reason: 'Stationary physical component; state binding does not imply movement.', binding: row.state_bound_fixed_functions.includes(fn) ? { type: 'operational_state', clock: 'server_sim', phase: 'work', progress_source: 'server_phase_progress', pause: 'hold', fault: 'hold', rest: 'inactive', state_id: `${fn}.state` } : null })) });
  for (const fn of row.fixed_functions) asset.nodes.push({ ...structuredClone(mechanicalNode), id: fn, locator: `root/${fn}` });
  asset.sockets = row.required_socket_roles.map(role => ({ ...structuredClone(required(example.assets[0]?.sockets[0])), id: role, role, node_id: 'support_bed' }));
  asset.collision_proxies = [{ ...structuredClone(required(example.assets[0]?.collision_proxies[0])), contact_socket_ids: asset.sockets.map(socket => socket.id) }, ...asset.moving_parts.map(part => ({ ...structuredClone(required(example.assets[0]?.collision_proxies[1])), id: `${part.id}_sweep`, part_id: part.id, contact_socket_ids: [] }))];
  if (row.roof_required) {
    asset.nodes.push({ ...structuredClone(mechanicalNode), id: 'roof', locator: 'root/roof' });
    Object.assign(asset, { cutaway: { roof_node_ids: ['roof'], interior_node_ids: ['support_bed'], retained_socket_ids: asset.sockets.map(socket => socket.id) } });
  }
  for (const lod of asset.lods) {
    lod.nodes = structuredClone(asset.nodes);
    lod.socket_ids = asset.sockets.map(socket => socket.id);
    lod.part_ids = [...row.required_functions, ...row.fixed_functions];
  }
  return input;
}


export function equipmentExample(variant: string) {
  const binding = required(policy.existing_bindings.find(row => row.variant === variant));
  const input = policyExample(required(policy.policies.find(row => row.id === binding.policy_group_id)));
  const asset = required(input.assets[0]);
  asset.id = `example:${variant}`;
  asset.variant = binding.variant;
  asset.family = required(binding.allowed_families[0]);
  asset.placement_ids = [...binding.placement_ids];
  asset.requirement_ids = [...binding.requirement_ids];
  asset.qa_row_ids = [...binding.qa_row_ids];
  asset.source_refs = [{ id: required(asset.requirement_ids[0]), uri: '.omo/plans/steelflow-uniform-fidelity-factory.md', note: 'Metadata-only shared source recipe; correct independently registered variant ownership retained.' }];
  return input;
}
