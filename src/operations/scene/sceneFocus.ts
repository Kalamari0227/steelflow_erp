import type { World } from '../../contracts';
import { factoryLayout } from './layout';

type FocusSelection = { readonly materialId: string | undefined; readonly stageId: string | undefined; readonly follow: boolean };
export function sceneFocus(world: World, selection: FocusSelection): string | undefined {
  const process = world.processes.find(row => row.material_id === selection.materialId && row.status === 'RUNNING');
  const processStage = factoryLayout.equipment.find(row => row.id === process?.equipment_id)?.stage_id;
  if (!selection.follow) return selection.stageId ?? processStage;
  if (processStage) return processStage;
  const material = world.materials.find(row => row.id === selection.materialId);
  const transfer = world.transfers.find(row => row.material_id === material?.id && row.status !== 'ARRIVED');
  const locationId = transfer ? (transfer.status === 'WAITING' || transfer.status === 'LOADING' ? transfer.from_location_id : transfer.to_location_id) : material?.location_id;
  const location = factoryLayout.locations.find(row => row.id === locationId);
  const ownerStage = factoryLayout.equipment.find(row => row.id === location?.owner_id)?.stage_id;
  if (ownerStage) return ownerStage;
  if (world.shipment_materials.some(row => row.material_id === material?.id && row.active)) return 'logistics';
  return selection.stageId;
}
