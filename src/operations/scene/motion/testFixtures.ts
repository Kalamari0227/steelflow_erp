import corpus from '../../../../shared/fixtures/motion-cases.json';
import registry from '../../../../shared/motion-recipes.json';
import { evaluateMotion, parseMotionContext, parseMotionEnvelopeValue, parseMotionRegistryValue } from './contracts';

export function fixture(index = 0) {
  const first = corpus.cases[index];
  if (first === undefined) throw new RangeError('Shared motion fixture missing');
  const cloned = structuredClone(first);
  return { ...cloned, context: { ...cloned.context, asset_bindings: cloned.context.asset_bindings.map(b => ({ ...b, sockets: b.sockets.map(s => ({ ...s, motion_function_ids: [...s.motion_function_ids] })) })) } };
}
export type Fixture = ReturnType<typeof fixture>;
export const recipes = parseMotionRegistryValue(registry);
export function authorize(testCase: Fixture): Fixture {
  testCase.context.authorizations = [structuredClone(testCase.envelope)];
  return testCase;
}
export function evaluate(testCase: Fixture) {
  return evaluateMotion(parseMotionEnvelopeValue(testCase.envelope), parseMotionContext(testCase.context), recipes);
}
export function sampled(time: number): Fixture {
  const testCase = fixture();
  Object.assign(testCase.envelope, { phase_start_ms: 500, phase_end_ms: 2500, confirmed_sim_ms: time, effective_sim_ms: time, frozen_progress: null, clock_state: 'running' });
  Object.assign(testCase.context.snapshot.run, { elapsed_ms: time, playing: true });
  for (const process of testCase.context.snapshot.processes) Object.assign(process, { start_ms: 500, end_ms: 2500 });
  for (const attachment of testCase.context.snapshot.attachments) attachment.acquired_at_ms = 0;
  return authorize(testCase);
}
export function boundaryCase(gap: number): Fixture {
  const testCase = fixture();
  const envelope = testCase.envelope;
  const material = testCase.context.snapshot.materials.find(m => m.id === envelope.material.material_id);
  const original = testCase.context.snapshot.material_versions.find(v => v.id === envelope.material.material_version_id);
  const binding = testCase.context.asset_bindings[0];
  const current = testCase.context.snapshot.attachments.find(a => a.id === envelope.attachment_id);
  if (material === undefined || original === undefined || binding === undefined || current === undefined) throw new RangeError('Boundary fixture missing');
  const previousMaterial = structuredClone(envelope.material);
  Object.assign(envelope.material, { material_version_id: 'stock-coil-v2', form: 'SLAB', dimensions: { length_mm: 1000, width_mm: 500, thickness_mm: 200, diameter_mm: null, inner_diameter_mm: null }, support_local_mm: [0, -100, 0] });
  Object.assign(material, { current_version_id: envelope.material.material_version_id, form: envelope.material.form, dimensions: structuredClone(envelope.material.dimensions) });
  testCase.context.snapshot.material_versions.push({ ...original, id: envelope.material.material_version_id, ordinal: 2, form: envelope.material.form, dimensions: structuredClone(envelope.material.dimensions) });
  for (const io of testCase.context.snapshot.batch_io) if (io.material_version_id === original.id) io.material_version_id = envelope.material.material_version_id;
  for (const owner of testCase.context.world.owners) for (const socket of owner.sockets) if (socket.id === 'road-b') socket.pose.position = [1 + gap, 0, 0];
  for (const node of testCase.context.world.nodes) if (node.id === 'v2:road-b') node.position = [1 + gap, 0, 0];
  for (const segment of testCase.context.world.segments) if (segment.to_node_id === 'v2:road-b') segment.points[segment.points.length - 1] = [1 + gap, 0, 0];
  const previousAnchor = { ...envelope.anchor, socket_id: 'road-b', position_m: [1 + gap, 0, 0] };
  for (const socket of binding.sockets) socket.family = 'SLAB';
  const previousSocket = structuredClone(binding.sockets[0]);
  if (previousSocket === undefined) throw new RangeError('Socket fixture missing');
  Object.assign(previousSocket, { socket_id: previousAnchor.socket_id, family: 'ORE', position_m: previousAnchor.position_m, orientation_xyzw: previousAnchor.orientation_xyzw, motion_function_ids: [] });
  binding.sockets.push(previousSocket);
  testCase.context.snapshot.attachments.push(Object.assign(structuredClone(current), { id: 'previous-custody', kind: 'equipment', owner_id: 'BF-A', socket_id: 'road-b', acquired_at_ms: 0, released_at_ms: 1000 }));
  Object.assign(envelope, { boundary: { released_attachment_id: 'previous-custody', acquired_attachment_id: current.id, at_ms: 1000, previous_material: previousMaterial, previous_anchor: previousAnchor, previous_channels: [] } });
  return authorize(testCase);
}
export function furnaceCase(): Fixture {
  const input = fixture(), ownerId = 'CS-HR-02';
  const channel = input.envelope.channels[0], binding = input.context.asset_bindings[0], descriptor = binding?.functions[0];
  if (channel === undefined || binding === undefined || descriptor === undefined) throw new RangeError('Mechanics fixture missing');
  for (const owner of input.context.world.owners) owner.id = ownerId;
  for (const row of [...input.context.world.slots, ...input.context.world.ports, ...input.context.world.footprints, ...input.context.world.allowed_interiors]) row.owner_id = ownerId;
  input.envelope.anchor.owner_id = ownerId;
  input.envelope.recipe_id = 'motion:source:hr-02';
  for (const process of input.context.snapshot.processes) Object.assign(process, { equipment_id: ownerId, route_step_id: 'hr:hr-02' });
  Object.assign(binding, { owner_id: ownerId, policy_id: 'policy:equipment:furnace' });
  for (const socket of binding.sockets) Object.assign(socket, { motion_function_ids: [] });
  const functions = ['furnace_door', 'furnace_feed', 'thermal_chamber'];
  input.envelope.channels = functions.map(id => ({ ...channel, function_id: id, node_id: id, kind: id === 'thermal_chamber' ? 'state' : 'translation', axis: [0, 1, 0], start_value: 0, end_value: 1 }));
  binding.functions = functions.map(id => ({ ...descriptor, function_id: id, node_id: id, kind: id === 'thermal_chamber' ? 'state' : 'translation', axis: [0, 1, 0], min_value: 0, max_value: 1 }));
  return authorize(input);
}
export function chainCase(): Fixture {
  const input = fixture();
  for (const binding of input.context.asset_bindings) for (const socket of binding.sockets) socket.motion_function_ids = ['tap_control', 'charge_gate'];
  return authorize(input);
}
