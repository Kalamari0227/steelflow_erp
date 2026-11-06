import { create } from 'zustand';
import { CanonicalUnavailable, CommandConflict, CommandTransportError, getWorld, sendCommand } from './api';
import type { CommandEnvelope, SimulationCommand } from './api';
import type { ApiCommandReply, ApiWorld, Selection } from './contracts';
import { useNavigationStore } from './operations/navigation';

type WorldState = {
  readonly world: ApiWorld | null;
  readonly busy: boolean;
  readonly fetching: boolean;
  readonly error: string | null;
  readonly unavailable: boolean;
  readonly stale: boolean;
  readonly receivedAt: number | null;
  readonly revision: number;
  readonly appliedRevision: number | null;
  readonly appliedRunId: string | null;
  readonly replayed: boolean;
  readonly refresh: () => Promise<void>;
  readonly command: (command: SimulationCommand) => Promise<void>;
  readonly acquirePolling: () => () => void;
};
type WorldApi = { readonly getWorld: () => Promise<ApiWorld>; readonly sendCommand: (command: CommandEnvelope) => Promise<ApiCommandReply> };
const errorMessage = (error: unknown): string => error instanceof CommandConflict || error instanceof CanonicalUnavailable ? error.message : '로컬 서버 응답을 확인하지 못했습니다. 마지막 확인 상태를 표시합니다.';

export function createWorldStore(api: WorldApi = { getWorld, sendCommand }) {
  let owners = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let pollingEpoch = 0;
  let requestSequence = 0;
  let acceptedSequence = 0;
  let uncertainCommand: CommandEnvelope | null = null;
  let pendingPause: CommandEnvelope | null = null;
  const retiredRuns = new Set<string>();
  return create<WorldState>((set, get) => {
    const accept = (world: ApiWorld, request: { readonly epoch: number; readonly sequence: number }): boolean => {
      const current = get();
      if (request.epoch !== current.revision || retiredRuns.has(world.run.id)) return false;
      if (current.world?.run.id === world.run.id && (world.run.revision < current.world.run.revision || (world.run.revision === current.world.run.revision && request.sequence < acceptedSequence))) return false;
      if (current.world && current.world.run.id !== world.run.id) retiredRuns.add(current.world.run.id);
      acceptedSequence = request.sequence;
      set({ world, stale: false, error: null, unavailable: false, receivedAt: Date.now() });
      useNavigationStore.getState().revalidate(world);
      return true;
    };
    const refresh = async (): Promise<void> => {
      if (get().busy || get().fetching) return;
      const request = { epoch: get().revision, sequence: ++requestSequence };
      set({ fetching: true });
      try { accept(await api.getWorld(), request); }
      catch (error) {
        if (!(error instanceof Error)) throw error;
        if (request.epoch === get().revision) set({ error: errorMessage(error), unavailable: error instanceof CanonicalUnavailable, stale: true });
      }
      finally { set({ fetching: false }); }
    };
    const poll = async (epoch: number): Promise<void> => {
      await refresh();
      if (owners > 0 && epoch === pollingEpoch) timer = setTimeout(() => void poll(epoch), get().world?.run.playing ? 250 : 1000);
    };
    return {
      world: null, unavailable: false, appliedRunId: null, busy: false, fetching: false, error: null, stale: true, receivedAt: null, revision: 0, appliedRevision: null, replayed: false,
      refresh,
      acquirePolling: () => {
        owners += 1;
        if (owners === 1) void poll(++pollingEpoch);
        let released = false;
        return () => {
          if (released) return;
          released = true;
          owners -= 1;
          if (owners === 0) { pollingEpoch += 1; clearTimeout(timer); }
        };
      },
      command: async command => {
        if (get().busy || get().unavailable) return;
        if (uncertainCommand && (uncertainCommand.action !== command.action
          || ('speed' in command && command.speed !== ('speed' in uncertainCommand ? uncertainCommand.speed : undefined))
          || ('scenario' in command && command.scenario !== ('scenario' in uncertainCommand ? uncertainCommand.scenario : undefined)))) {
          set({ error: '이전 명령 응답이 확인되지 않았습니다. 같은 명령을 다시 눌러 결과를 확인해 주세요.', stale: true });
          return;
        }
        const current = get().world;
        if (!current) { set({ error: '현재 실행을 먼저 불러와 주세요.', stale: true }); return; }
        const request = { epoch: get().revision + 1, sequence: ++requestSequence };
        set({ busy: true, revision: request.epoch });
        const resets = command.action === 'reset' || command.action === 'scenario';
        let envelope: CommandEnvelope = uncertainCommand ?? { ...command, run_id: current.run.id, command_id: crypto.randomUUID(), ...(resets ? { expected_revision: current.run.revision } : {}) };
        const commandRunId = envelope.run_id;
        let conflicts = 0;
        let lostReplies = 0;
        const pauseForReset = async (world: ApiWorld): Promise<ApiWorld> => {
          if (world.run.id !== commandRunId) {
            pendingPause = null; uncertainCommand = null;
            throw new CommandConflict('다른 실행으로 변경되어 명령을 재실행하지 않았습니다. 현재 실행을 확인해 주세요.');
          }
          if (!pendingPause && !world.run.playing) return world;
          pendingPause ??= { action: 'pause', run_id: commandRunId, command_id: crypto.randomUUID() };
          uncertainCommand = envelope;
          try {
            let reply: ApiCommandReply;
            try { reply = await api.sendCommand(pendingPause); }
            catch (error) { if (!(error instanceof CommandTransportError)) throw error; reply = await api.sendCommand(pendingPause); }
            pendingPause = null;
            uncertainCommand = null;
            accept(reply, request);
            if (reply.run.id !== commandRunId) throw new CommandConflict('다른 실행으로 변경되어 명령을 재실행하지 않았습니다. 현재 실행을 확인해 주세요.');
            return reply;
          } catch (error) {
            if (!(error instanceof CommandTransportError)) { pendingPause = null; uncertainCommand = null; }
            throw error;
          }
        };
        try {
          if (resets && (!uncertainCommand || pendingPause)) {
            const stable = await pauseForReset(current);
            envelope = { ...envelope, expected_revision: stable.run.revision };
          }
          for (;;) {
            try {
              const reply = await api.sendCommand(envelope);
              uncertainCommand = null;
              if (accept(reply, request)) set({ appliedRevision: reply.applied_revision, appliedRunId: reply.schema_version === 3 ? reply.applied_run_id : reply.run.id, replayed: reply.replayed });
              break;
            } catch (error) {
              if (error instanceof CommandTransportError) {
                uncertainCommand = envelope;
                if (lostReplies < 1) { lostReplies += 1; continue; }
              }
              if (error instanceof CommandConflict) uncertainCommand = null;
              if (!(error instanceof CommandConflict) || !resets || conflicts >= 2) throw error;
              const latest = await api.getWorld();
              accept(latest, request);
              if (latest.run.id !== commandRunId) throw new CommandConflict('다른 실행으로 변경되어 명령을 재실행하지 않았습니다. 현재 실행을 확인해 주세요.');
              conflicts += 1;
              const stable = await pauseForReset(latest);
              envelope = { ...envelope, expected_revision: stable.run.revision, command_id: crypto.randomUUID() };
            }
          }
        } catch (error) {
          if (!(error instanceof Error)) throw error;
          if (request.epoch === get().revision) set({ error: errorMessage(error), unavailable: error instanceof CanonicalUnavailable, stale: true });
        } finally {
          set({ busy: false });
          if (owners > 0) {
            clearTimeout(timer);
            const epoch = ++pollingEpoch;
            timer = setTimeout(() => void poll(epoch), get().world?.run.playing ? 250 : 1000);
          }
        }
      },
    };
  });
}
export const useWorldStore = createWorldStore();

/** Interpolate at most 350ms beyond a confirmed server frame; failed reads freeze immediately. */
export function renderElapsed(state: Pick<WorldState, 'world' | 'receivedAt' | 'stale'>, now: number): number {
  if (!state.world) return 0;
  const run = state.world.run;
  const delta = run.playing && !state.stale && state.receivedAt !== null ? Math.min(350, Math.max(0, now - state.receivedAt)) * run.speed : 0;
  return Math.min(run.duration_ms, run.elapsed_ms + delta);
}

type ViewState = {
  readonly selection: Selection | null; readonly view: '3d' | '2d'; readonly tab: 'orders' | 'shipments' | 'events'; readonly query: string;
  readonly select: (selection: Selection | null) => void; readonly setView: (view: '3d' | '2d') => void;
  readonly setTab: (tab: 'orders' | 'shipments' | 'events') => void; readonly setQuery: (query: string) => void;
};
export const useViewStore = create<ViewState>(set => ({
  selection: null, view: '3d', tab: 'orders', query: '',
  select: selection => set({ selection }), setView: view => set({ view }), setTab: tab => set({ tab }), setQuery: query => set({ query }),
}));
