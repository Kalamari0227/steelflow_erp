import { bindingsFromAssetManifest, evaluateMotion, parseMotionContext, parseMotionEnvelopeValue } from '../../../src/operations/scene/motion/contracts';
import type { AssetManifest } from '../../../src/operations/scene/assets/manifest';
import { fixture, recipes } from '../../../src/operations/scene/motion/testFixtures';
import { requireAsset } from '../../../src/operations/scene/assets/errors';
import identity from './identity.json';

/** Explicit fixed-contract authority samples, independent of wall time or a production scheduler. */
export function miniatureRequest(manifest: AssetManifest, progress: number, clock: 'paused' | 'blocked' | 'running' = 'paused') {
  const asset = manifest.assets[0]; requireAsset(asset, 'binding', 'miniature asset');
  const input = fixture(), ownerId = 'CS-HR-03';
  const families: Record<string, string> = {};
  for (const socket of asset.sockets) { const form = socket.forms[0]; requireAsset(form, 'binding', socket.id); families[socket.id] = form; }
  const bindings = bindingsFromAssetManifest(manifest, [{ owner_id: ownerId, asset_id: asset.id, socket_families: families }]);
  const binding = bindings[0], support = binding?.sockets.find(socket => socket.socket_id === 'work');
  requireAsset(binding && support, 'binding', 'miniature canonical binding');
  for (const owner of input.context.world.owners) {
    owner.id = ownerId;
    owner.sockets.push(...binding.sockets.map(socket => ({ id: socket.socket_id, pose: { position: [...socket.position_m], yaw_rad: 0 } })));
  }
  for (const row of [...input.context.world.slots, ...input.context.world.ports, ...input.context.world.footprints, ...input.context.world.allowed_interiors]) row.owner_id = ownerId;
  const dimensions = { length_mm: 1000, width_mm: 500, thickness_mm: 200, diameter_mm: null, inner_diameter_mm: null };
  Object.assign(input.envelope, { bundle_id: identity.bundleId, bundle_hash: identity.bundleHash, recipe_id: 'motion:source:hr-03', frozen_progress: clock === 'running' ? null : progress, clock_state: clock, confirmed_sim_ms: Math.round(progress * 2000), effective_sim_ms: Math.round(progress * 2000), anchor: { owner_id: ownerId, socket_id: support.socket_id, position_m: [...support.position_m], orientation_xyzw: [...support.orientation_xyzw] } });
  Object.assign(input.context.snapshot.run, { bundle_id: identity.bundleId, bundle_hash: identity.bundleHash, elapsed_ms: input.envelope.confirmed_sim_ms, playing: clock === 'running' });
  Object.assign(input.envelope.material, { form: 'SLAB', dimensions, support_local_mm: [0, -100, 0], orientation_xyzw: [0, 0, 0, 1] });
  input.envelope.channels = binding.functions.map(fn => ({ function_id: fn.function_id, node_id: fn.node_id, kind: fn.kind, window_id: 'work', axis: [...fn.axis], pivot_m: [...fn.pivot_m], start_value: fn.min_value, end_value: fn.max_value }));
  for (const process of input.context.snapshot.processes) Object.assign(process, { equipment_id: ownerId, route_step_id: 'hr:hr-03' });
  for (const material of input.context.snapshot.materials) if (material.id === input.envelope.material.material_id) Object.assign(material, { form: 'SLAB', dimensions: structuredClone(dimensions) });
  for (const version of input.context.snapshot.material_versions) if (version.id === input.envelope.material.material_version_id) Object.assign(version, { form: 'SLAB', dimensions: structuredClone(dimensions) });
  for (const stock of input.context.snapshot.stock_lots) if (stock.id === input.envelope.material.material_id) stock.form = 'SLAB';
  for (const attachment of input.context.snapshot.attachments) if (attachment.id === input.envelope.attachment_id) Object.assign(attachment, { kind: 'equipment', owner_id: ownerId, socket_id: support.socket_id, acquired_at_ms: 0 });
  const envelope = parseMotionEnvelopeValue(input.envelope);
  const context = parseMotionContext({ ...input.context, asset_bindings: bindings, authorizations: [envelope] });
  return { envelope, context, pose: evaluateMotion(envelope, context, recipes) };
}
