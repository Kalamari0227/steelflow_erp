import { describe, expect, it, vi } from 'vitest';
import type { CommandReply, World } from './contracts';
import { createWorldStore, renderElapsed } from './store';
import { deferred, testReply, testWorld } from './operations/testWorld';

describe('authoritative world updates', () => {
  it('rejects old polling response after command completion', async () => {
    const poll = deferred<World>();
    const store = createWorldStore({ getWorld: () => poll.promise, sendCommand: async () => testReply(testWorld(1)) });
    store.setState({ world: testWorld() });
    const pending = store.getState().refresh();
    await store.getState().command({ action: 'step' });
    poll.resolve(testWorld());
    await pending;
    expect(store.getState().world?.run.revision).toBe(1);
  });
  it('preserves the last snapshot and receive time on outage then recovers', async () => {
    const getWorld = vi.fn<() => Promise<World>>().mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce(testWorld(4));
    const store = createWorldStore({ getWorld, sendCommand: async () => testReply(testWorld()) });
    store.setState({ world: testWorld(3), receivedAt: 100 });
    await store.getState().refresh();
    expect([store.getState().world?.run.revision, store.getState().receivedAt, store.getState().stale]).toEqual([3, 100, true]);
    expect(store.getState().error).not.toBeNull();
    await store.getState().refresh();
    expect([store.getState().world?.run.revision, store.getState().stale, store.getState().error]).toEqual([4, false, null]);
  });
  it('coalesces duplicate clicks during a pending mutation', async () => {
    const result = deferred<CommandReply>();
    const sendCommand = vi.fn(() => result.promise);
    const store = createWorldStore({ getWorld: async () => testWorld(), sendCommand });
    store.setState({ world: testWorld() });
    const first = store.getState().command({ action: 'step' });
    await store.getState().command({ action: 'step' });
    expect(sendCommand).toHaveBeenCalledTimes(1);
    result.resolve(testReply(testWorld(1)));
    await first;
    expect(store.getState().busy).toBe(false);
  });
  it('caps rendering extrapolation and immediately freezes stale snapshots', () => {
    const world = testWorld();
    const playing = { ...world, run: { ...world.run, playing: true, speed: 4 as const } };
    expect(renderElapsed({ world: playing, receivedAt: 100, stale: false }, 1000)).toBe(1400);
    expect(renderElapsed({ world: playing, receivedAt: 100, stale: true }, 1000)).toBe(0);
  });
});
