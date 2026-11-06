import { useNavigationStore } from '../navigation';
import { CraneActor, VehicleActor } from './TransferActors';
import type { TransportActorProps } from './TransferActors';
import { shipmentVehiclePose, transferPose } from './transferPose';

export function LogisticsActors({ world, elapsed }: TransportActorProps) {
  const carriers = new Set<string>();
  const shipments = world.shipments.filter(row => row.status !== 'PLANNED' && row.status !== 'ALLOCATED' && row.status !== 'DELIVERED');
  return <group>{shipments.map(shipment => {
    const candidate = shipmentVehiclePose(shipment, elapsed.current);
    const vehicle = candidate?.carrierId && !carriers.has(candidate.carrierId) ? candidate : null;
    if (vehicle?.carrierId) carriers.add(vehicle.carrierId);
    const members = world.shipment_materials.filter(row => row.shipment_id === shipment.id && row.active);
    const hooked = members.flatMap(member => {
      const material = world.materials.find(row => row.id === member.material_id);
      return material?.location_id.includes('-HOOK') ? [material] : [];
    });
    return <group key={shipment.id} name={`shipment-${shipment.id}`}>
      {vehicle?.carrierId && <VehicleActor id={vehicle.carrierId} elapsed={elapsed} onSelect={() => useNavigationStore.getState().select({ run_id: world.run.id, shipment_id: shipment.id, material_id: members.find(row => row.material_id === useNavigationStore.getState().selection.material_id)?.material_id ?? members[0]?.material_id })} getPose={time => shipmentVehiclePose(shipment, time)} />}
      {hooked.map(material => {
        const hook = transferPose(material, world, elapsed.current);
        return hook?.carrierId ? <CraneActor key={material.id} id={hook.carrierId} elapsed={elapsed} onSelect={() => useNavigationStore.getState().select({ run_id: world.run.id, material_id: material.id, shipment_id: shipment.id })} getPose={time => transferPose(material, world, time)} /> : null;
      })}
    </group>;
  })}</group>;
}
