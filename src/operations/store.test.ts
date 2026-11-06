import { afterEach, describe, expect, it, vi } from 'vitest';
import { CommandConflict, CommandTransportError } from '../api';
import type { CommandEnvelope } from '../api';
import type { CommandReply, World } from '../contracts';
import { WorldSchema } from '../contracts';
import { createWorldStore } from '../store';
import { deferred, testReply, testWorld } from './testWorld';

afterEach(() => vi.useRealTimers());
describe('command receipts and response ordering', () => {
  it('retains the receipt identity after both transport attempts fail', async () => {
    const sendCommand = vi.fn<(command: CommandEnvelope) => Promise<CommandReply>>()
      .mockRejectedValueOnce(new CommandTransportError('lost')).mockRejectedValueOnce(new CommandTransportError('lost again'))
      .mockResolvedValueOnce(testReply(testWorld(1), true));
    const store = createWorldStore({ getWorld: async () => testWorld(), sendCommand });
    store.setState({ world: testWorld() });
    await store.getState().command({ action: 'step' });
    await store.getState().command({ action: 'reset' });
    expect(sendCommand).toHaveBeenCalledTimes(2);
    await store.getState().command({ action: 'step' });
    expect(sendCommand.mock.calls[2]?.[0]).toEqual(sendCommand.mock.calls[0]?.[0]);
    expect(store.getState().world?.run.revision).toBe(1);
  });
  it('retries a lost response with the identical command id and payload', async () => {
    const sendCommand = vi.fn<(command: CommandEnvelope) => Promise<CommandReply>>()
      .mockRejectedValueOnce(new CommandTransportError('lost')).mockResolvedValueOnce(testReply(testWorld(1), true));
    const store = createWorldStore({ getWorld: async () => testWorld(), sendCommand });
    store.setState({ world: testWorld() });
    await store.getState().command({ action: 'step' });
    expect(sendCommand.mock.calls[0]?.[0]).toEqual(sendCommand.mock.calls[1]?.[0]);
    expect(store.getState().world?.run.revision).toBe(1);
    expect(store.getState().replayed).toBe(true);
  });
  it.each([{ action: 'reset' as const }, { action: 'scenario' as const, scenario: 'DELAY' as const }])('pauses the playing run before $action and uses the pause receipt revision', async command => {
    const paused = deferred<CommandReply>();
    const sendCommand = vi.fn<(command: CommandEnvelope) => Promise<CommandReply>>().mockReturnValueOnce(paused.promise).mockResolvedValueOnce(testReply(testWorld(0, 'new-run')));
    const getWorld = vi.fn(async () => testWorld());
    const store = createWorldStore({ getWorld, sendCommand });
    store.setState({ world: { ...testWorld(1), run: { ...testWorld(1).run, playing: true } } });
    const pending = store.getState().command(command);
    expect(store.getState().busy).toBe(true);
    expect(sendCommand.mock.calls[0]?.[0]).toMatchObject({ action: 'pause', run_id: testWorld().run.id });
    await store.getState().refresh();
    expect(getWorld).not.toHaveBeenCalled();
    paused.resolve(testReply(testWorld(20)));
    await pending;
    expect(sendCommand.mock.calls[1]?.[0]).toMatchObject({ ...command, run_id: testWorld().run.id, expected_revision: 20 });
    expect(store.getState().world?.run.id).toBe('new-run');
    expect(store.getState().busy).toBe(false);
    expect(store.getState().error).toBeNull();
  });
  it('retains a lost preparatory pause identity across user retries without sending the reset early', async () => {
    const sendCommand = vi.fn<(command: CommandEnvelope) => Promise<CommandReply>>()
      .mockRejectedValueOnce(new CommandTransportError('lost pause')).mockRejectedValueOnce(new CommandTransportError('lost pause again'))
      .mockResolvedValueOnce(testReply(testWorld(8), true)).mockResolvedValueOnce(testReply(testWorld(0, 'new-run')));
    const store = createWorldStore({ getWorld: async () => testWorld(), sendCommand });
    store.setState({ world: { ...testWorld(), run: { ...testWorld().run, playing: true } } });
    await store.getState().command({ action: 'reset' });
    expect(sendCommand.mock.calls.map(([row]) => row.action)).toEqual(['pause', 'pause']);
    await store.getState().command({ action: 'reset' });
    expect(sendCommand.mock.calls[2]?.[0]).toEqual(sendCommand.mock.calls[0]?.[0]);
    expect(sendCommand.mock.calls[3]?.[0]).toMatchObject({ action: 'reset', expected_revision: 8 });
    expect(store.getState().world?.run.id).toBe('new-run');
  });
  it('replays the identical reset after its reply is lost without issuing another preparatory pause', async () => {
    const sendCommand = vi.fn<(command: CommandEnvelope) => Promise<CommandReply>>()
      .mockResolvedValueOnce(testReply(testWorld(8))).mockRejectedValueOnce(new CommandTransportError('lost reset')).mockResolvedValueOnce(testReply(testWorld(0, 'new-run'), true));
    const store = createWorldStore({ getWorld: async () => testWorld(), sendCommand });
    store.setState({ world: { ...testWorld(), run: { ...testWorld().run, playing: true } } });
    await store.getState().command({ action: 'reset' });
    expect(sendCommand.mock.calls.map(([row]) => row.action)).toEqual(['pause', 'reset', 'reset']);
    expect(sendCommand.mock.calls[2]?.[0]).toEqual(sendCommand.mock.calls[1]?.[0]);
    expect(store.getState().replayed).toBe(true);
  });
  it('does not reset another client run discovered after the preparatory pause', async () => {
    const sendCommand = vi.fn<(command: CommandEnvelope) => Promise<CommandReply>>().mockResolvedValueOnce(testReply(testWorld(0, 'other-run')));
    const store = createWorldStore({ getWorld: async () => testWorld(), sendCommand });
    store.setState({ world: { ...testWorld(), run: { ...testWorld().run, playing: true } } });
    await store.getState().command({ action: 'reset' });
    expect(sendCommand.mock.calls.map(([row]) => row.action)).toEqual(['pause']);
    expect(store.getState().world?.run.id).toBe('other-run');
    expect(store.getState().error).not.toBeNull();
  });
  it('keeps the original run guard when another client replaces the paused run before reset', async () => {
    const sendCommand = vi.fn<(command: CommandEnvelope) => Promise<CommandReply>>().mockResolvedValueOnce(testReply(testWorld(8))).mockRejectedValueOnce(new CommandConflict('stale run'));
    const store = createWorldStore({ getWorld: async () => testWorld(0, 'other-run'), sendCommand });
    store.setState({ world: { ...testWorld(), run: { ...testWorld().run, playing: true } } });
    await store.getState().command({ action: 'reset' });
    expect(sendCommand.mock.calls.map(([row]) => row.action)).toEqual(['pause', 'reset']);
    expect(sendCommand.mock.calls[1]?.[0].run_id).toBe(testWorld().run.id);
    expect(store.getState().world?.run.id).toBe('other-run');
    expect(store.getState().error).not.toBeNull();
  });
  it('never pauses a different playing run after an uncertain pause and a newer poll', async () => {
    const other = { ...testWorld(3, 'other-run'), run: { ...testWorld(3, 'other-run').run, playing: true } };
    const sendCommand = vi.fn<(command: CommandEnvelope) => Promise<CommandReply>>().mockRejectedValue(new CommandTransportError('lost pause'));
    const store = createWorldStore({ getWorld: async () => other, sendCommand });
    store.setState({ world: { ...testWorld(), run: { ...testWorld().run, playing: true } } });
    await store.getState().command({ action: 'reset' });
    await store.getState().refresh();
    await store.getState().command({ action: 'reset' });
    expect(sendCommand).toHaveBeenCalledTimes(2);
    expect(sendCommand.mock.calls.every(([row]) => row.run_id === testWorld().run.id && row.action === 'pause')).toBe(true);
    expect(store.getState().world?.run.playing).toBe(true);
    expect(store.getState().error).not.toBeNull();
  });
  it('still replays an uncertain reset from the old run after polling its new run', async () => {
    const sendCommand = vi.fn<(command: CommandEnvelope) => Promise<CommandReply>>().mockRejectedValueOnce(new CommandTransportError('lost reset')).mockRejectedValueOnce(new CommandTransportError('lost reset again')).mockResolvedValueOnce(testReply(testWorld(0, 'new-run'), true));
    const store = createWorldStore({ getWorld: async () => testWorld(0, 'new-run'), sendCommand });
    store.setState({ world: testWorld() });
    await store.getState().command({ action: 'reset' });
    await store.getState().refresh();
    await store.getState().command({ action: 'reset' });
    expect(sendCommand.mock.calls[2]?.[0]).toEqual(sendCommand.mock.calls[0]?.[0]);
    expect(store.getState().replayed).toBe(true);
    expect(store.getState().error).toBeNull();
  });
  it('retries reset conflicts twice with fresh revision and command ids', async () => {
    const sendCommand = vi.fn<(command: CommandEnvelope) => Promise<CommandReply>>().mockRejectedValue(new CommandConflict('conflict'));
    const getWorld = vi.fn<() => Promise<World>>().mockResolvedValueOnce(testWorld(2)).mockResolvedValueOnce(testWorld(3));
    const store = createWorldStore({ getWorld, sendCommand });
    store.setState({ world: testWorld(1) });
    await store.getState().command({ action: 'reset' });
    expect(sendCommand.mock.calls.map(([command]) => command.expected_revision)).toEqual([1, 2, 3]);
    expect(new Set(sendCommand.mock.calls.map(([command]) => command.command_id)).size).toBe(3);
    expect(getWorld).toHaveBeenCalledTimes(2);
    expect(store.getState().error).not.toBeNull();
  });
  it('does not replay reset when a conflicting command changed the current run', async () => {
    const sendCommand = vi.fn<(command: CommandEnvelope) => Promise<CommandReply>>().mockRejectedValue(new CommandConflict('conflict'));
    const store = createWorldStore({ getWorld: async () => testWorld(0, 'new-run'), sendCommand });
    store.setState({ world: testWorld() });
    await store.getState().command({ action: 'reset' });
    expect(sendCommand).toHaveBeenCalledTimes(1);
    expect(store.getState().world?.run.id).toBe('new-run');
    expect(store.getState().error).not.toBeNull();
  });
  it('rejects a late previous-run poll after reset', async () => {
    const poll = deferred<World>();
    const store = createWorldStore({ getWorld: () => poll.promise, sendCommand: async () => testReply(testWorld(0, 'new-run')) });
    store.setState({ world: testWorld(10) });
    const pending = store.getState().refresh();
    await store.getState().command({ action: 'reset' });
    poll.resolve(testWorld(11));
    await pending;
    expect(store.getState().world?.run.id).toBe('new-run');
  });
  it('rejects older revisions and retired runs even from a subsequent read', async () => {
    const getWorld = vi.fn<() => Promise<World>>().mockResolvedValueOnce(testWorld(0, 'new-run')).mockResolvedValueOnce(testWorld(9)).mockResolvedValueOnce(testWorld(1, 'new-run')).mockResolvedValueOnce(testWorld(0, 'new-run'));
    const store = createWorldStore({ getWorld, sendCommand: async () => testReply(testWorld()) });
    store.setState({ world: testWorld(8) });
    for (let count = 0; count < 4; count += 1) await store.getState().refresh();
    expect([store.getState().world?.run.id, store.getState().world?.run.revision]).toEqual(['new-run', 1]);
  });
  it('rejects an older equal-revision poll after a command response', async () => {
    const poll = deferred<World>();
    const latest = { ...testWorld(2), run: { ...testWorld(2).run, playing: true } };
    const store = createWorldStore({ getWorld: () => poll.promise, sendCommand: async () => testReply(latest) });
    store.setState({ world: testWorld(1) });
    const pending = store.getState().refresh();
    await store.getState().command({ action: 'play' });
    poll.resolve(testWorld(2));
    await pending;
    expect(store.getState().world?.run.playing).toBe(true);
  });
  it('owns only one poll timer and releases it after the final subscriber', async () => {
    vi.useFakeTimers();
    const getWorld = vi.fn<() => Promise<World>>().mockResolvedValue(testWorld());
    const store = createWorldStore({ getWorld, sendCommand: async () => testReply(testWorld()) });
    const first = store.getState().acquirePolling();
    const second = store.getState().acquirePolling();
    await vi.advanceTimersByTimeAsync(0);
    expect(getWorld).toHaveBeenCalledTimes(1);
    first();
    await vi.advanceTimersByTimeAsync(999);
    expect(getWorld).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(getWorld).toHaveBeenCalledTimes(2);
    second();
    second();
    await vi.advanceTimersByTimeAsync(1000);
    expect(getWorld).toHaveBeenCalledTimes(2);
    expect(vi.getTimerCount()).toBe(0);
  });
  it('polls playing runs at 250ms and does not recreate timers after pending-read cleanup', async () => {
    vi.useFakeTimers();
    const pending = deferred<World>();
    const playing = { ...testWorld(), run: { ...testWorld().run, playing: true } };
    const getWorld = vi.fn<() => Promise<World>>().mockResolvedValueOnce(playing).mockReturnValueOnce(pending.promise);
    const store = createWorldStore({ getWorld, sendCommand: async () => testReply(testWorld()) });
    const release = store.getState().acquirePolling();
    await vi.advanceTimersByTimeAsync(250);
    expect(getWorld).toHaveBeenCalledTimes(2);
    release();
    pending.resolve(playing);
    await vi.advanceTimersByTimeAsync(0);
    expect(vi.getTimerCount()).toBe(0);
  });
  it('switches the owned poll cadence immediately when play succeeds', async () => {
    vi.useFakeTimers();
    const playing = { ...testWorld(), run: { ...testWorld().run, playing: true } };
    const getWorld = vi.fn<() => Promise<World>>().mockResolvedValueOnce(testWorld()).mockResolvedValue(playing);
    const store = createWorldStore({ getWorld, sendCommand: async () => testReply(playing) });
    const release = store.getState().acquirePolling();
    await vi.advanceTimersByTimeAsync(0);
    await store.getState().command({ action: 'play' });
    await vi.advanceTimersByTimeAsync(250);
    expect(getWorld).toHaveBeenCalledTimes(2);
    release();
    expect(vi.getTimerCount()).toBe(0);
  });
  it('keeps relational validation at the projected World boundary', () => {
    const world = testWorld();
    const result = WorldSchema.safeParse({ ...world, materials: world.materials.map(row => ({ ...row, lot_id: 'missing' })) });
    expect(result.success).toBe(false);
  });
});
