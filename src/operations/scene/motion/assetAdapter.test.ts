import { describe, expect, it } from 'vitest';
import manifest from '../../../../shared/fixtures/asset-manifest-valid.json';
import policies from '../../../../shared/asset-requirements.json';
import { policyExample } from '../assets/manifestTestFixtures';
import { bindingsFromAssetManifest } from './contracts';

const selection = { owner_id: 'CUT-SLAB', asset_id: 'example:shear:CUT-SLAB', socket_families: { support: 'SLAB', entry: 'SLAB', work: 'SLAB', exit: 'SLAB' } } as const;
const closePoint = (values: readonly number[]) => values.map(v => expect.closeTo(v, 10));
function fixture() {
  const input = structuredClone(manifest), asset = input.assets[0];
  if (asset === undefined) throw new RangeError('Asset fixture missing');
  return { input, asset };
}
describe('T4 full manifest adapter', () => {
  it('derives immutable mechanics from admitted T4 metadata and preserves explicit families', () => {
    // Given
    const { input } = fixture();
    // When
    const bindings = bindingsFromAssetManifest(input, [selection]);
    // Then
    expect(bindings[0]?.functions[0]).toMatchObject({ function_id: 'cutting_tool', node_id: 'cutting_tool', axis: [0, -1, 0], min_value: 0, max_value: 0.5 });
    expect(bindings[0]?.sockets[0]).toMatchObject({ family: 'SLAB', position_m: [0, 0.5, 0], motion_function_ids: [] });
    expect(Object.isFrozen(bindings[0]?.sockets)).toBe(true);
  });
  it('composes the real parent hierarchy and links a socket under its moving node', () => {
    // Given: parent roll90, child +Y1m, socket child +Y0.5m.
    const { input, asset } = fixture();
    for (const node of asset.nodes) {
      if (node.id === 'support_bed') node.transform.rotation_xyzw = [Math.SQRT1_2, 0, 0, Math.SQRT1_2];
      if (node.id === 'cutting_tool') node.parent_id = 'support_bed';
    }
    for (const socket of asset.sockets) socket.node_id = 'cutting_tool';
    for (const lod of asset.lods) lod.nodes = structuredClone(asset.nodes);
    // When
    const bindings = bindingsFromAssetManifest(input, [selection]);
    // Then
    expect(bindings[0]?.sockets[0]?.position_m).toEqual(closePoint([0, 0, 1.5]));
    expect(bindings[0]?.sockets[0]?.motion_function_ids).toEqual(['cutting_tool']);
    expect(bindings[0]?.functions[0]?.axis).toEqual(closePoint([0, 0, -1]));
  });
  it('refuses an unrelated equipment owner', () => {
    // Given
    const { input } = fixture();
    // When
    const action = () => bindingsFromAssetManifest(input, [{ ...selection, owner_id: 'BF-A' }]);
    // Then
    expect(action).toThrow(expect.objectContaining({ code: 'binding' }));
  });
  it('refuses substituting a coil family for a slab socket', () => {
    // Given
    const { input } = fixture();
    // When
    const action = () => bindingsFromAssetManifest(input, [{ ...selection, socket_families: { ...selection.socket_families, support: 'COIL' } }]);
    // Then
    expect(action).toThrow(expect.objectContaining({ code: 'form' }));
  });
  it('refuses moving parts disguised as decorative before producing a descriptor', () => {
    // Given
    const { input, asset } = fixture(); for (const part of asset.moving_parts) part.role = 'decorative';
    // When
    const action = () => bindingsFromAssetManifest(input, [selection]);
    // Then
    expect(action).toThrow(expect.objectContaining({ code: 'requirements' }));
  });
});

it('preserves every moving crane ancestor in root-to-leaf order', () => {
  // Given: admitted T4 crane metadata, with a bridge/trolley/hoist ancestry chain.
  const policy = policies.policies.find(p => p.category === 'fleet' && p.kind === 'crane');
  if (policy === undefined) throw new RangeError('Crane policy missing');
  const input = policyExample(policy), asset = input.assets[0];
  if (asset === undefined) throw new RangeError('Crane asset missing');
  let parent = asset.root_node_id;
  for (const part of asset.moving_parts) {
    const node = asset.nodes.find(n => n.id === part.node_id);
    if (node === undefined) throw new RangeError('Crane node missing');
    node.parent_id = parent; parent = node.id;
  }
  const support = asset.nodes.find(n => n.id === 'support_bed');
  if (support === undefined) throw new RangeError('Crane support missing');
  support.parent_id = parent;
  for (const lod of asset.lods) lod.nodes = structuredClone(asset.nodes);
  const families = Object.fromEntries(asset.sockets.map(s => [s.id, 'SLAB']));
  // When
  const bindings = bindingsFromAssetManifest(input, [{ owner_id: 'contract-crane', asset_id: asset.id, socket_families: families }]);
  // Then
  expect(bindings[0]?.sockets.every(s => JSON.stringify(s.motion_function_ids) === JSON.stringify(asset.moving_parts.map(p => p.function)))).toBe(true);
  expect(bindings[0]?.sockets[0]?.motion_function_ids).toHaveLength(3);
});
