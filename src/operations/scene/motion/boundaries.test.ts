import { describe, expect, it } from 'vitest';
import { motionJson } from './json';
import { parseMotionContext } from './context';
import { fixture } from './testFixtures';

const strictSnapshotFields = [
  'seed', 'elapsed_ms', 'duration_ms', 'revision', 'event_sequence', 'speed',
  'quantity_kg', 'route_version', 'planned_kg', 'received_at_ms', 'weight_kg',
  'ordinal', 'transferred_kg', 'start_ms', 'end_ms', 'ready_at_ms',
  'planned_duration_ms', 'at_ms', 'sequence', 'capacity_kg', 'available_at_ms',
  'acquired_at_ms', 'released_at_ms', 'eta_ms',
];

describe('public motion boundaries after independent review', () => {
  it.each(strictSnapshotFields)('preserves nested T5 strict lexical integer %s', key => {
    for (const spelling of ['1.0', '1e0']) {
      expect(() => motionJson(`{"context":{"snapshot":{"rows":[{"${key}":${spelling}}]}}}`)).toThrow(expect.objectContaining({ code: 'invalid_contract' }));
    }
  });
  it('retains T3 integral decimal compatibility and fractional geometry', () => {
    const raw = '{"context":{"world":{"version":2.0,"capacity_kg":500.0,"position":[0.25,1e-2,3.5]},"snapshot":{"schema_version":3.0,"position_m":[0.25,1e-2,3.5],"length_mm":0.5}}}';
    expect(motionJson(raw)).toEqual(JSON.parse(raw));
  });
  it('translates actual world validation failure at the public context boundary', () => {
    const input = fixture().context;
    const owner = input.world.owners[0];
    if (owner === undefined) throw new Error('fixture owner absent');
    input.world.owners.push(structuredClone(owner));
    expect(() => parseMotionContext(input)).toThrow(expect.objectContaining({ code: 'invalid_contract' }));
  });
  it.each([0.01, 0.0100000000005, 0.010001])('uses exact REST tolerance for %s metres', delta => {
    const input = fixture().context;
    const binding = input.asset_bindings[0];
    if (binding === undefined) throw new Error('fixture binding absent');
    const socket = binding.sockets[0];
    if (socket === undefined) throw new Error('fixture socket absent');
    socket.position_m[0] = (socket.position_m[0] ?? 0) + delta;
    if (delta <= 0.01) expect(() => parseMotionContext(input)).not.toThrow();
    else expect(() => parseMotionContext(input)).toThrow(expect.objectContaining({ code: 'binding' }));
  });
});
