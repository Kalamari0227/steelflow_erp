import type { ProductionTransport } from '../contracts';

export type ProductionSceneProps = {
  readonly stageId: string | null;
  readonly stages: readonly { id: string; name: string; status: string; active_batches: number }[];
  readonly materials: readonly { id: string; stage_id: string; form: string; status: string }[];
  readonly selectedMaterialId: string | null;
  readonly selectedStep: number | null;
  readonly stepDescriptors: readonly { name: string; equipment_id: string }[];
  readonly stepNames: readonly string[];
  readonly onSelectStage: (id: string) => void;
  readonly onSelectMaterial: (id: string) => void;
  readonly onSelectStep: (index: number) => void;
  readonly transports: readonly ProductionTransport[];
  readonly tick: number;
  readonly runId: string;
  readonly speed: number;
  readonly tickDurationSeconds: number;
  readonly playing: boolean;
  readonly resetKey: number;
  readonly onFallback: () => void;
};
