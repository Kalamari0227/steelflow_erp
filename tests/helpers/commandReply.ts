import { CommandReplySchema, type World } from '../../src/contracts';

export function commandWorld(payload: unknown): World {
  const { applied_revision: _appliedRevision, replayed: _replayed, ...world } = CommandReplySchema.parse(payload);
  return world;
}
