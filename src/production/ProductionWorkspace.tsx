import type { World } from '../contracts';
import { OperationsWorkspace } from '../operations/OperationsWorkspace';

export function ProductionWorkspace({ world }: { readonly world: World }) {
  return <OperationsWorkspace world={world} />;
}
