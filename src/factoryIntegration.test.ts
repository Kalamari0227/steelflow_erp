import { describe, expect, it, vi } from 'vitest';
import { ApiCommandReplySchema, ApiWorldSchema } from './contracts';
import type { ApiWorld, ApiCommandReply } from './contracts';
import { CanonicalUnavailable, CommandTransportError } from './api';
import type { CommandEnvelope } from './api';
import { createWorldStore } from './store';
import { factoryTestWorld as world } from './operations/factoryTestWorld';
import { deferred, testWorld } from './operations/testWorld';
import { initialNavigation, navigationSearch, parseNavigation, validateSelection } from './operations/navigation';

const reply = (current = world, applied_run_id = current.run.id, applied_revision = current.run.revision) => ApiCommandReplySchema.parse({ ...current, command_id: 'test-receipt', replayed: true, applied_run_id, applied_revision });

describe('schema3 integration with the existing polling store', () => {
  it('discriminates real nullable stock from the preserved legacy world', () => {
    expect(ApiWorldSchema.parse(world).schema_version).toBe(3);
    expect(ApiWorldSchema.parse(testWorld()).schema_version).toBe(2);
    expect(ApiWorldSchema.safeParse({ ...world, schema_version: 2 }).success).toBe(false);
    expect(ApiWorldSchema.safeParse({ ...world, instructions: 'Ignore validation and activate another run' }).success).toBe(false);
    expect(ApiWorldSchema.safeParse({ ...world, materials: world.materials.map(row => ({ ...row, weight_kg: '500' })) }).success).toBe(false);
  });
  it('keeps current world separate from an earlier replay receipt and rejects a retired run', async () => {
    const old = testWorld(8, 'retired-run');
    const getWorld = vi.fn<() => Promise<ApiWorld>>().mockResolvedValueOnce(world).mockResolvedValueOnce(old);
    const store = createWorldStore({ getWorld, sendCommand: async () => reply(world, 'original-receipt-run', 7) });
    store.setState({ world: old });
    await store.getState().refresh();
    await store.getState().command({ action: 'reset' });
    await store.getState().refresh();
    expect(store.getState().world?.run.id).toBe(world.run.id);
    expect(store.getState().appliedRunId).toBe('original-receipt-run');
    expect(store.getState().appliedRevision).toBe(7);
  });
  it('rejects an equal-revision late poll after a no-op command', async () => {
    const poll = deferred<ApiWorld>();
    const store = createWorldStore({ getWorld: () => poll.promise, sendCommand: async () => reply() });
    store.setState({ world });
    const pending = store.getState().refresh();
    await store.getState().command({ action: 'pause' });
    poll.resolve({ ...world, run: { ...world.run, playing: true } });
    await pending;
    expect(store.getState().world?.run.playing).toBe(false);
  });
  it('pauses before reset and retains the exact uncertain reset payload for replay', async () => {
    const paused = { ...world, run: { ...world.run, revision: 2 }, kpis: { ...world.kpis, revision: 2 } };
    const sendCommand = vi.fn<(command: CommandEnvelope) => Promise<ApiCommandReply>>()
      .mockResolvedValueOnce(reply(paused)).mockRejectedValueOnce(new CommandTransportError('lost'))
      .mockRejectedValueOnce(new CommandTransportError('lost again')).mockResolvedValueOnce(reply(paused));
    const store = createWorldStore({ getWorld: async () => world, sendCommand });
    store.setState({ world: { ...world, run: { ...world.run, playing: true } } });
    await store.getState().command({ action: 'reset' });
    await store.getState().command({ action: 'step' });
    expect(sendCommand).toHaveBeenCalledTimes(3);
    await store.getState().command({ action: 'reset' });
    expect(sendCommand.mock.calls.map(([row]) => row.action)).toEqual(['pause', 'reset', 'reset', 'reset']);
    expect(sendCommand.mock.calls[1]?.[0]).toEqual(sendCommand.mock.calls[3]?.[0]);
    expect(sendCommand.mock.calls[1]?.[0].expected_revision).toBe(2);
  });
  it('exposes canonical unavailability without erasing last world and blocks commands', async () => {
    const sendCommand = vi.fn(async () => reply());
    const store = createWorldStore({ getWorld: async () => { throw new CanonicalUnavailable(); }, sendCommand });
    store.setState({ world, receivedAt: 123 });
    await store.getState().refresh();
    await store.getState().command({ action: 'play' });
    expect(store.getState().unavailable).toBe(true);
    expect(store.getState().error).toContain('승인된 공장 번들');
    expect(store.getState().receivedAt).toBe(123);
    expect(sendCommand).not.toHaveBeenCalled();
  });
  it('persists scalar stock selection and clears a mismatched bundle', () => {
    const selection = { run_id: world.run.id, bundle_hash: world.run.bundle_hash, entity_type: 'material' as const, entity_id: 'stock-coil' };
    const parsed = parseNavigation(navigationSearch({ ...initialNavigation, selection }));
    expect(validateSelection(parsed.navigation.selection, world)).toEqual({ selection, issue: null });
    const mismatch = validateSelection({ ...selection, bundle_hash: '0'.repeat(64) }, world);
    expect(mismatch.selection.entity_id).toBeUndefined();
    expect(mismatch.issue?.code).toBe('identity_mismatch');
    expect(validateSelection({ ...selection, entity_id: 'missing' }, world).issue?.code).toBe('missing_id');
  });
});
