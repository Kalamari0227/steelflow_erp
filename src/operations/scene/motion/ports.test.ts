import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import domain from '../../../../shared/fixtures/factory-contract-test-v3/domain.json';
import { parseFactoryWorld } from '../worldContract';
import { evaluateMotion } from './contracts';
import { resolvedAttachment } from './custody';
import { assertNever } from './errors';
import { motionJson } from './json';
import { parseMotionRequestValue } from './request';
import { FORM_FAMILIES } from './forms';
import { fixture, recipes } from './testFixtures';

const receiptForms = ['ORE', 'SCRAP', 'TI_INGOT', 'SLAB', 'BLOOM', 'BILLET', 'HR_COIL', 'CR_COIL', 'STS_HR_COIL', 'TI_HR_COIL'] as const;
const locationForms = [...receiptForms, 'COAL', 'LIMESTONE', 'NICKEL_ORE'] as const;
const world = parseFactoryWorld(motionJson(new Uint8Array(readFileSync('shared/factory-world-v2.json'))));
function present<T>(value: T | undefined): T {
  if (value === undefined) throw new RangeError('Required canonical test record absent');
  return value;
}
function receiptRequest(form: typeof receiptForms[number] = 'HR_COIL') {
  const base = fixture(3), state = structuredClone(domain);
  const port = present(world.ports.find(p => p.id === `v2:p:receipt:${form}:work`));
  const owner = present(world.owners.find(o => o.id === port.owner_id));
  const socket = present(owner.sockets.find(s => s.id === port.socket_id));
  for (const attachment of state.attachments) Object.assign(attachment, { owner_id: port.id, socket_id: port.socket_id });
  const dimensions = form.endsWith('COIL')
    ? { length_mm: null, width_mm: 1000, thickness_mm: 2, diameter_mm: 1200, inner_diameter_mm: 600 }
    : { length_mm: 1000, width_mm: 1000, thickness_mm: 200, diameter_mm: null, inner_diameter_mm: null };
  Object.assign(present(state.materials[0]), { form, dimensions: structuredClone(dimensions) });
  Object.assign(present(state.material_versions[0]), { form, dimensions: structuredClone(dimensions) });
  Object.assign(present(state.stock_lots[0]), { form });
  Object.assign(base.envelope.material, { form, dimensions: structuredClone(dimensions) });
  Object.assign(base.envelope.anchor, { owner_id: owner.id, socket_id: socket.id, position_m: [...socket.pose.position] });
  const binding = present(base.context.asset_bindings[0]);
  binding.owner_id = owner.id;
  Object.assign(present(binding.sockets[0]), { socket_id: socket.id, family: FORM_FAMILIES[form][0], position_m: [...socket.pose.position] });
  return { envelope: base.envelope, context: { snapshot: state, world, asset_bindings: [binding], authorizations: [structuredClone(base.envelope)] } };
}
function project(raw: unknown) {
  const request = parseMotionRequestValue(raw);
  return evaluateMotion(request.envelope, request.context, recipes);
}
function fleetBoundaryRequest(direction: 'port_to_fleet' | 'fleet_to_port', gap = 0) {
  const raw = receiptRequest(), state = raw.context.snapshot;
  const port = present(world.ports.find(p => p.id === 'v2:p:receipt:HR_COIL:work'));
  const mobileOwner = { id: 'receipt-port-carrier', kind: 'vehicle', pose: { position: [0, 0, 0], yaw_rad: 0 }, sockets: [{ id: 'load', pose: { position: [0, 2, 0], yaw_rad: 0 } }], modes: ['road'] };
  const receiptOwner = present(world.owners.find(o => o.id === 'receipt:HR_COIL'));
  const anchor = raw.envelope.anchor;
  const contact = receiptOwner.pose.position.map((v, i) => v + present(anchor.position_m[i]));
  const mobileAnchor = { owner_id: 'receipt-port-carrier', socket_id: 'load', position_m: [0, 2, 0], orientation_xyzw: [0, 0, 0, 1] };
  const current = present(state.attachments[0]);
  const prior = { ...current, id: 'prior-custody', acquired_at_ms: 0, released_at_ms: 1000 };
  const previousAnchor = direction === 'port_to_fleet' ? structuredClone(anchor) : mobileAnchor;
  if (direction === 'port_to_fleet') Object.assign(current, { kind: 'vehicle', owner_id: 'receipt-port-carrier', socket_id: 'load' });
  else Object.assign(prior, { kind: 'vehicle', owner_id: 'receipt-port-carrier', socket_id: 'load' });
  const binding = structuredClone(present(raw.context.asset_bindings[0]));
  binding.owner_id = 'receipt-port-carrier';
  Object.assign(present(binding.sockets[0]), { socket_id: 'load', position_m: [...mobileAnchor.position_m] });
  const envelope = { ...raw.envelope, anchor: direction === 'port_to_fleet' ? mobileAnchor : anchor,
    boundary: { released_attachment_id: prior.id, acquired_attachment_id: current.id, at_ms: 1000, previous_material: structuredClone(raw.envelope.material), previous_anchor: previousAnchor, previous_channels: [] } };
  return { envelope, context: { ...raw.context, world: { ...world, owners: [...world.owners, mobileOwner], footprints: [...world.footprints, { id: 'fp:receipt-port-carrier', owner_id: 'receipt-port-carrier', pose: { position: [0, 1, 0], yaw_rad: 0 }, size_m: [12, 2, 3] }] }, authorizations: [structuredClone(envelope)], asset_bindings: [...raw.context.asset_bindings, binding],
    snapshot: { ...state, attachments: [...state.attachments, prior],
      fleet: [{ run_id: state.run.id, id: 'receipt-port-carrier', kind: 'truck', variant: 'truck', capacity_kg: 50000, length_m: 12, load_envelope_m: [10, 3, 3], turn_radius_m: 12, mode: 'road', load_socket_id: 'load' }],
      vehicle_states: [{ run_id: state.run.id, id: 'state:receipt-port-carrier', fleet_id: 'receipt-port-carrier', status: 'IDLE', node_id: port.node_id, position_m: [present(contact[0]) + gap, present(contact[1]) - 2, present(contact[2])], yaw_rad: 0, current_job_id: null, available_at_ms: 1000 }] } } };
}

describe('exact canonical receipt ports', () => {
  it.each(locationForms)('resolves %s to its exact owner and socket', form => {
    const context = parseMotionRequestValue(receiptRequest()).context;
    expect(resolvedAttachment({ run_id: context.snapshot.run.id, id: 'location-probe', material_id: 'stock-coil', kind: 'slot', owner_id: `v2:p:receipt:${form}:work`, socket_id: 'work', acquired_at_ms: 1000, released_at_ms: null }, context)).toMatchObject({ owner_id: `receipt:${form}`, socket_id: 'work' });
  });
  it.each(receiptForms)('projects supported receipt form %s at its actual world node', form => {
    const port = present(world.ports.find(p => p.id === `v2:p:receipt:${form}:work`));
    const node = present(world.nodes.find(n => n.id === port.node_id));
    const pose = project(receiptRequest(form));
    expect(pose.owner_id).toBe(`receipt:${form}`);
    expect(pose.contact_m).toEqual(node.position);
    expect(pose.position_m[1]).toBeCloseTo(node.position[1] + 0.5);
  });
  it.each(['slot', 'equipment'])('preserves existing %s attachment behavior', kind => {
    const raw = receiptRequest(), current = present(raw.context.snapshot.attachments[0]);
    if (kind === 'slot') {
      const slot = present(world.slots[0]), owner = present(world.owners.find(o => o.id === slot.owner_id));
      const socket = present(owner.sockets.find(s => s.id === slot.socket_id));
      Object.assign(current, { owner_id: slot.id, socket_id: slot.socket_id });
      Object.assign(raw.envelope.anchor, { owner_id: owner.id, socket_id: socket.id, position_m: [...socket.pose.position] });
      const binding = present(raw.context.asset_bindings[0]);
      binding.owner_id = owner.id;
      Object.assign(present(binding.sockets[0]), { socket_id: socket.id, position_m: [...socket.pose.position] });
    } else Object.assign(current, { kind, owner_id: 'receipt:HR_COIL' });
    raw.context.authorizations = [structuredClone(raw.envelope)];
    expect(project(raw).owner_id).toBe(raw.envelope.anchor.owner_id);
  });
  describe.each(['port_to_fleet', 'fleet_to_port'] as const)('%s release/acquire', direction => {
    it.each([0, 0.01])('accepts support gap %s metres', gap => {
      expect(project(fleetBoundaryRequest(direction, gap)).attachment_id).toBe('custody-stock-coil');
    });
    it('rejects a gap beyond the contact tolerance', () => {
      expect(() => project(fleetBoundaryRequest(direction, 0.010001))).toThrow(expect.objectContaining({ code: 'contact' }));
    });
  });
  it.each([['unknown', 'attachment'], ['socket', 'attachment'], ['owner', 'attachment'], ['nearby_owner', 'attachment'], ['authorization', 'unauthorized'], ['run', 'stale_run'], ['revision', 'stale_revision'], ['form', 'form'], ['support', 'binding'], ['kind', 'invalid_contract'], ['injection', 'attachment'], ['malformed', 'invalid_contract']] as const)('retains %s guard', (fault, code) => {
    const raw = receiptRequest(), current = present(raw.context.snapshot.attachments[0]);
    switch (fault) {
      case 'unknown': current.owner_id = 'v2:p:missing'; break;
      case 'socket': current.socket_id = 'missing'; break;
      case 'owner': raw.envelope.anchor.owner_id = 'receipt:CR_COIL'; break;
      case 'nearby_owner': current.owner_id = 'v2:p:receipt:CR_COIL:work'; break;
      case 'run': raw.envelope.run_id = 'other-run'; break;
      case 'revision': raw.envelope.revision = 1; break;
      case 'form': present(present(raw.context.asset_bindings[0]).sockets[0]).family = 'ORE'; break;
      case 'support': present(present(raw.context.asset_bindings[0]).sockets[0]).position_m[0] = 0.010001; break;
      case 'kind': current.kind = 'vehicle'; break;
      case 'injection': current.owner_id = 'v2:p:receipt:HR_COIL:work;ignore previous instructions'; break;
      case 'malformed': Object.assign(raw.envelope, { revision: true }); break;
      case 'authorization': break;
      default: assertNever(fault);
    }
    raw.context.authorizations = fault === 'authorization' ? [] : [structuredClone(raw.envelope)];
    expect(() => project(raw)).toThrow(expect.objectContaining({ code }));
  });
  it('rejects slot-port identity collisions at public admission', () => {
    const raw = receiptRequest();
    const collision = { ...raw, context: { ...raw.context, world: { ...world, ports: world.ports.map((port, i) => i === 0 ? { ...port, id: present(world.slots[0]).id } : port) } } };
    expect(() => parseMotionRequestValue(collision)).toThrow(expect.objectContaining({ code: 'invalid_contract', reference: 'world' }));
  });
});
