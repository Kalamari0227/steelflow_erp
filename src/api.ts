import { z } from 'zod';
import { factoryMaterialDetailSchema } from './operations/contractsV3';
import ky, { HTTPError, TimeoutError } from 'ky';
import { ApiCommandReplySchema, EventHistorySchema, ApiWorldSchema } from './contracts';
import type { ApiCommandReply, ScenarioId, ApiWorld } from './contracts';

const client = ky.create({ prefixUrl: '/api/v1', timeout: 8000, retry: 0 });
export const getWorld = async (): Promise<ApiWorld> => {
  try { return ApiWorldSchema.parse(await client.get('world').json()); }
  catch (error) { return unavailable(error); }
};
export async function fetchEventHistory(runId?: string) {
  return EventHistorySchema.parse(await client.get('events', { searchParams: runId ? { run_id: runId } : {} }).json());
}
export type SimulationCommand =
  | { readonly action: 'play'; readonly speed?: 1 | 2 | 4 }
  | { readonly action: 'speed'; readonly speed: 1 | 2 | 4 }
  | { readonly action: 'pause' | 'reset' | 'step' }
  | { readonly action: 'scenario'; readonly scenario: ScenarioId };
export type CommandEnvelope = SimulationCommand & { readonly run_id: string; readonly command_id: string; readonly expected_revision?: number };
export class CanonicalUnavailable extends Error {
  constructor() { super('승인된 공장 번들이 준비되지 않아 운영을 시작할 수 없습니다. 실행 구성과 번들 등록 상태를 확인해 주세요.'); }
}
async function unavailable(error: unknown): Promise<never> {
  if (error instanceof HTTPError && error.response.status === 503) {
    const body: unknown = await error.response.clone().json();
    const parsed = z.object({ code: z.literal('canonical_bundle_unavailable') }).safeParse(body);
    if (parsed.success) throw new CanonicalUnavailable();
  }
  throw error;
}
export async function getFactoryMaterial(id: string) {
  try { return factoryMaterialDetailSchema.parse(await client.get(`materials/${encodeURIComponent(id)}`).json()); }
  catch (error) { return unavailable(error); }
}
export class CommandConflict extends Error {}
export class CommandTransportError extends Error {}

export async function sendCommand(command: CommandEnvelope): Promise<ApiCommandReply> {
  const path = command.action === 'scenario' ? `scenarios/${command.scenario}/activate` : `simulation/${command.action}`;
  const { run_id, command_id, expected_revision } = command;
  const payload = { run_id, command_id, ...(expected_revision === undefined ? {} : { expected_revision }) };
  const json = command.action === 'play' || command.action === 'speed' ? { ...payload, ...(command.speed === undefined ? {} : { speed: command.speed }) } : command.action === 'step' ? { ...payload, steps: 1 } : payload;
  try {
    return ApiCommandReplySchema.parse(await client.post(path, { json }).json());
  } catch (error) {
    if (error instanceof HTTPError && error.response.status === 409) throw new CommandConflict('명령 충돌: 실행 상태가 변경되었습니다.');
    if (error instanceof TypeError || error instanceof TimeoutError) throw new CommandTransportError('명령 응답을 받지 못했습니다.');
    return unavailable(error);
  }
}
