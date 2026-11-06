import type { Asset, AssetManifest } from '../../../src/operations/scene/assets/manifest';
import { bindingsFromAssetManifest, evaluateMotion, parseMotionContext, parseMotionEnvelopeValue } from '../../../src/operations/scene/motion/contracts';
import { fixture, recipes } from '../../../src/operations/scene/motion/testFixtures';
import { requireAsset } from '../../../src/operations/scene/assets/errors';

/** Explicit synthetic contract fixture, evaluated by T58. This is not a scheduler or a live v3 API run. */
export function representativePose(manifest: AssetManifest, asset: Asset, frozenProgress = 0.5) {
  const input = fixture();
  const ownerId = asset.placement_ids[0]?.replace(/^equipment:/, '');
  requireAsset(ownerId, 'binding', 'representative placement');
  const families: Record<string, string> = {};
  for (const socket of asset.sockets) { const family = socket.forms[0]; requireAsset(family, 'binding', socket.id); families[socket.id] = family; }
  const bindings = bindingsFromAssetManifest(manifest, [{ owner_id: ownerId, asset_id: asset.id, socket_families: families }]);
  const binding = bindings[0], support = binding?.sockets.find(s => s.socket_id === 'work');
  requireAsset(binding && support, 'binding', 'representative support');
  for (const owner of input.context.world.owners) {
    owner.id = ownerId;
    owner.sockets.push(...binding.sockets.map(socket => ({ id: socket.socket_id, pose: { position: [...socket.position_m], yaw_rad: 0 } })));
  }
  for (const row of [...input.context.world.slots, ...input.context.world.ports, ...input.context.world.footprints, ...input.context.world.allowed_interiors]) row.owner_id = ownerId;
  const slab = asset.kind === 'shear', thickness = slab ? 200 : 2;
  const dimensions = { length_mm: 1000, width_mm: 500, thickness_mm: thickness, diameter_mm: null, inner_diameter_mm: null };
  input.envelope.recipe_id = slab ? 'motion:source:cs-cut-slab' : 'motion:source:gi-05';
  input.envelope.frozen_progress = frozenProgress;
  input.envelope.anchor = { owner_id: ownerId, socket_id: support.socket_id, position_m: [...support.position_m], orientation_xyzw: [...support.orientation_xyzw] };
  Object.assign(input.envelope.material, { form: slab ? 'SLAB' : 'STRIP', dimensions, support_local_mm: [0, -thickness / 2, 0], orientation_xyzw: [0, 0, 0, 1] });
  input.envelope.channels = binding.functions.map(fn => ({ function_id: fn.function_id, node_id: fn.node_id, kind: fn.kind, window_id: 'work', axis: [...fn.axis], pivot_m: [...fn.pivot_m], start_value: fn.min_value, end_value: fn.max_value }));
  for (const process of input.context.snapshot.processes) Object.assign(process, { equipment_id: ownerId, route_step_id: slab ? 'slab:cs-cut-slab' : 'gi:gi-05' });
  for (const material of input.context.snapshot.materials) if (material.id === input.envelope.material.material_id) Object.assign(material, { form: input.envelope.material.form, dimensions: structuredClone(dimensions) });
  for (const version of input.context.snapshot.material_versions) if (version.id === input.envelope.material.material_version_id) Object.assign(version, { form: input.envelope.material.form, dimensions: structuredClone(dimensions) });
  for (const stock of input.context.snapshot.stock_lots) if (stock.id === input.envelope.material.material_id) stock.form = input.envelope.material.form;
  for (const attachment of input.context.snapshot.attachments) if (attachment.id === input.envelope.attachment_id) Object.assign(attachment, { kind: 'equipment', owner_id: ownerId, socket_id: support.socket_id });
  const envelope = parseMotionEnvelopeValue(input.envelope);
  const context = parseMotionContext({ ...input.context, asset_bindings: bindings, authorizations: [envelope] });
  return { pose: evaluateMotion(envelope, context, recipes), envelope, context };
}
