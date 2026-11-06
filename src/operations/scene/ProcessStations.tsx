import { useSceneHover } from './useSceneHover';
import { memo, useRef } from 'react';
import { DoubleSide } from 'three';
import type { RefObject } from 'react';
import { useFrame } from '@react-three/fiber';
import type { World } from '../../contracts';
import type { ProcessExecution } from '../contracts';
import { Equipment as ExistingEquipment } from '../../journey/scene/Equipment';
import type { PhaseClock } from '../../journey/scene/Equipment';
import { Box, colors, Cylinder, Rail, RollerBed } from '../../journey/scene/parts';
import { useNavigationStore } from '../navigation';
import { factoryLayout, stationAnchorPosition } from './layout';
import type { Equipment } from './layout';
import { processPhase, validateEquipment } from './processPose';
import { FactoryGround } from './FactoryGround';
import { IndustrialHalls } from './IndustrialHalls';
import { SiteInfrastructure } from './SiteInfrastructure';
import { SteelworksLandmarks } from './SteelworksLandmarks';
import { SceneLabel } from './SceneLabel';
import { factoryCampus } from './campus';
import { equipmentLabel } from '../presentation';
import { sceneFocus } from './sceneFocus';

function Metallurgy({ kind }: { readonly kind: string }) {
  const blast = kind === 'blast_furnace';
  if (blast) return <group>
    <mesh position={[0, 5.2, -0.7]} castShadow><cylinderGeometry args={[2.1, 2.6, 8.4, 24, 1, true, Math.PI / 2, Math.PI]} /><meshStandardMaterial color="#8f7767" side={DoubleSide} roughness={0.8} /></mesh>
    <mesh position={[0, 11.2, -0.7]} castShadow><cylinderGeometry args={[1.1, 2.1, 3.8, 24]} /><meshStandardMaterial color={colors.steel} roughness={0.65} /></mesh>
    <Cylinder at={[0, 14, -0.7]} radius={1.1} length={1.8} rotation={[0, 0, 0]} color={colors.shadow} />
    <Cylinder at={[0, 1.1, 0]} radius={1.4} length={0.2} rotation={[0, 0, 0]} color={colors.hot} />
    {[4.2, 8.4, 12.6].map(y => <group key={y}><Box at={[0, y, -3]} size={[7, 0.16, 1.4]} color={colors.steel} />{[-3.4, 3.4].map(x => <Box key={x} at={[x, y + 0.5, -3]} size={[0.07, 1, 1.5]} color={colors.rail} />)}</group>)}
    {[-3.5, 3.5].map(x => <group key={x}><Box at={[x, 6.5, -2.4]} size={[0.35, 13, 0.35]} color={colors.blue} /><Cylinder at={[x * 0.78, 8.5, -2]} radius={0.3} length={11} rotation={[0, 0, 0]} color={colors.steel} /></group>)}
    <Box at={[0, 0.92, 0]} size={[5.2, 0.12, 1.35]} color={colors.hot} glow /><Rail z={2.5} length={6} />
  </group>;
  const converter = kind === 'bof';
  return <group>
    <mesh position={[0, 2.6, 0]} castShadow><cylinderGeometry args={[1.4, 1.05, 3.2, 24, 1, true, Math.PI / 2, Math.PI]} /><meshStandardMaterial color={colors.shadow} side={DoubleSide} roughness={0.55} metalness={0.35} /></mesh>
    <Cylinder at={[0, 1.05, 0]} radius={1} length={0.15} rotation={[0, 0, 0]} color={colors.hot} />
    <Box at={[0, 0.92, 0]} size={[5.2, 0.12, 1.35]} color={colors.hot} glow />
    {[-2.5, 2.5].map(x => <group key={x}><Box at={[x, 2.8, -1.4]} size={[0.4, 5.6, 0.4]} color={colors.blue} /><Cylinder at={[x / 2, 3.1, -0.4]} radius={0.3} length={2} rotation={[0, 0, Math.PI / 2]} color={colors.steel} /></group>)}
    <Box at={[0, 5.7, -1.4]} size={[5.5, 0.4, 0.6]} color={colors.blue} />
    {converter ? <><mesh position={[0, 6.9, -0.4]}><cylinderGeometry args={[0.5, 1.8, 2, 16, 1, true]} /><meshStandardMaterial color={colors.steel} side={DoubleSide} /></mesh><Cylinder at={[0, 7.6, 0]} radius={0.12} length={4.8} rotation={[0, 0, 0]} color={colors.water} /></> : [-0.5, 0, 0.5].map(x => <Cylinder key={x} at={[x, 5, 0]} radius={0.13} length={3.2} rotation={[0, 0, 0]} color={colors.frame} />)}
    <Rail z={2} />
  </group>;
}
function Silhouette({ kind }: { readonly kind: string }) {
  if (kind === 'blast_furnace') return <Metallurgy kind={kind} />;
  if (['blast_furnace', 'bof', 'ladle_furnace', 'eaf', 'aod'].includes(kind)) return <group><Cylinder at={[0, 2, 0]} radius={0.85} length={kind === 'blast_furnace' ? 4 : 2.4} rotation={[0, 0, 0]} color={colors.blue} /><Cylinder at={[0, 3.3, 0]} radius={0.5} length={0.15} rotation={[0, 0, 0]} color={colors.hot} /></group>;
  if (['furnace', 'annealing', 'alloying', 'heat_treatment', 'decarburizing', 'vacuum_annealing'].includes(kind)) return <group>{[-1, 1].map(z => <Box key={z} at={[0, 1.2, z]} size={[3.8, 2, 0.25]} color={kind === 'furnace' ? colors.panel : colors.annealing} />)}<Box at={[0, 2.3, 0]} size={[3.8, 0.25, 2.3]} color={colors.panel} /><Box at={[0, 0.95, 0]} size={[3.5, 0.05, 1.7]} color={colors.hot} /></group>;
  if (['coiler', 'uncoiler', 'laying_head'].includes(kind)) return <group><Box at={[0, 0.4, 0]} size={[2.5, 0.7, 2.4]} color={colors.blue} /><Cylinder at={[0, 1.25, 0]} radius={0.55} length={2.1} /><Cylinder at={[0, 1.25, 0]} radius={0.2} length={2.5} color={colors.shadow} /></group>;
  if (['pickling', 'galvanizing', 'electrocleaning', 'electroplating', 'coating', 'oiling'].includes(kind)) return <group><Box at={[0, 0.6, 0]} size={[4.5, 1, 2.5]} color={kind === 'pickling' ? colors.treatment : colors.zinc} /><Box at={[0, 1.12, 0]} size={[4.1, 0.04, 2.1]} color={colors.water} />{[-1.8, 1.8].map(x => <Cylinder key={x} at={[x, 1.3, 0]} radius={0.22} length={2.2} />)}</group>;
  if (kind === 'caster') return <group><Cylinder at={[-1.5, 2, 0]} radius={0.75} length={1.5} rotation={[0, 0, 0]} color={colors.panel} /><Cylinder at={[-1.5, 1, 0]} radius={0.1} length={1.4} rotation={[0, 0, 0]} color={colors.hot} /><Box at={[1, 1.3, 0]} size={[1.5, 0.6, 2.2]} color={colors.blue} /></group>;
  if (['roughing', 'finishing_mill', 'cold_mill', 'wire_mill', 'bloom_mill', 'temper', 'leveler'].includes(kind)) return <group>{[-1.4, 0, 1.4].map(x => <group key={x}>{[-1, 1].map(z => <Box key={z} at={[x, 1.4, z]} size={[0.5, 2.2, 0.3]} color={colors.blue} />)}<Cylinder at={[x, 1.2, 0]} radius={0.3} length={2.2} /><Box at={[x, 2.45, 0]} size={[0.7, 0.3, 2.3]} color={colors.blue} /></group>)}</group>;
  if (['stock', 'port', 'ship', 'delivery'].includes(kind)) return <group>{[-1, 1].map(z => <Box key={z} at={[0, 0.65, z]} size={[4.8, 0.25, 0.2]} color={colors.rail} />)}</group>;
  return <group>{[-1, 1].map(z => <Box key={z} at={[0, 1.4, z]} size={[0.3, 2.3, 0.25]} color={colors.blue} />)}<Box at={[0, 2.55, 0]} size={[3, 0.2, 2.5]} color={colors.panel} /><Cylinder at={[0, 1.2, 0]} radius={0.2} length={2.2} /></group>;
}
const Station = memo(function Station({ station, runId, active, elapsed, detail }: { readonly station: Equipment; readonly runId: string; readonly active: ProcessExecution | undefined; readonly elapsed: RefObject<number>; readonly detail: boolean }) {
  validateEquipment(station);
  const hover = useSceneHover(`equipment:${station.id}`);
  const clock = useRef<PhaseClock>({ phase: 0, index: -1, localX: 0, localZ: 0, localRotation: 0 });
  useFrame(() => { clock.current.phase = active ? processPhase(active, elapsed.current) : 0; clock.current.index = active ? 0 : -1; }, -2);
  const selected = useNavigationStore(state => state.selection.equipment_id === station.id);
  const position = stationAnchorPosition(factoryLayout, station.id, 'work');
  const stage = factoryLayout.stages.find(row => row.id === station.stage_id);
  const metallurgy = ['blast_furnace', 'bof', 'ladle_furnace'].includes(station.kind);
  const pick = () => { const navigation = useNavigationStore.getState(); navigation.select({ ...navigation.selection, run_id: runId, equipment_id: station.id, stage_id: station.stage_id }); navigation.setLevel('equipment'); };
  return <group {...hover.events} position={[position[0], position[1] - station.anchors.work.position[1], position[2]]} rotation={[0, station.rotation + (stage?.rotation ?? 0), 0]} onClick={event => { event.stopPropagation(); pick(); }} userData={{ pickKind: 'equipment', pickId: station.id }}>
    <Box at={[0, -0.1, 0]} size={[5.8, 0.2, 3.8]} color={selected || hover.hovered ? '#b9ced8' : colors.base} />
    {detail ? <><RollerBed length={5.2} contactHeight={station.anchors.work.position[1]} />{metallurgy ? <Metallurgy kind={station.kind} /> : station.kind === 'charge' ? <group><Box at={[-1, 1.4, -1]} size={[2.5, 1, 0.25]} color={colors.blue} /><Box at={[-1, 1.4, 1]} size={[2.5, 1, 0.25]} color={colors.blue} /><Rail /></group> : ['port', 'ship', 'delivery'].includes(station.kind) ? <Rail /> : <ExistingEquipment kind={station.kind} clock={clock} index={0} contactHeight={station.anchors.work.position[1]} cutaway />}</> : <><Box at={[0, 0.35, 0]} size={[5.2, 0.6, 1.7]} color={colors.frame} /><Silhouette kind={station.kind} /></>}
    {(selected || hover.hovered) && <SceneLabel text={equipmentLabel(station.id)} at={[0, 3.6, 3.8]} active={selected} />}
    <group position={[...station.anchors.work.position]} userData={{ contactKind: 'work', equipmentId: station.id }} />
  </group>;
}, (before, after) => before.station === after.station && before.runId === after.runId && before.elapsed === after.elapsed && before.detail === after.detail && before.active?.id === after.active?.id && before.active?.status === after.active?.status && before.active?.start_ms === after.active?.start_ms && before.active?.end_ms === after.active?.end_ms);
const Campus = memo(function Campus({ focus, materialFocus }: { readonly focus: string | undefined; readonly materialFocus: string | undefined }) {
  const overview = useNavigationStore(state => state.level === 'overview');
  return <><FactoryGround focus={focus} /><IndustrialHalls focus={focus} materialFocus={materialFocus} /><SiteInfrastructure reserveCutaway={focus === 'hr' || materialFocus === 'hr'} /><SteelworksLandmarks upstreamCutaway={focus === 'carbon-upstream' || materialFocus === 'carbon-upstream'} />{overview && factoryCampus.districts.map(district => <SceneLabel key={district.id} text={district.label} at={district.position} />)}</>;
});
export const ProcessStations = memo(function ProcessStations({ world, elapsed }: { readonly world: World; readonly elapsed: RefObject<number> }) {
  const level = useNavigationStore(state => state.level);
  const selectedStage = useNavigationStore(state => state.selection.stage_id);
  const selectedMaterial = useNavigationStore(state => state.selection.material_id);
  const selectedEquipment = useNavigationStore(state => state.selection.equipment_id);
  const follow = useNavigationStore(state => state.followMaterial);
  const focus = sceneFocus(world, { materialId: selectedMaterial, stageId: selectedStage, follow });
  const materialFocus = sceneFocus(world, { materialId: selectedMaterial, stageId: undefined, follow: true });
  return <group userData={{ focusStage: focus ?? null }}><Campus focus={focus} materialFocus={materialFocus} />{factoryLayout.equipment.map(station => <Station key={station.id} station={station} runId={world.run.id} active={world.processes.find(row => row.equipment_id === station.id && row.status === 'RUNNING')} elapsed={elapsed} detail={station.stage_id === focus || (level !== 'overview' && station.id === selectedEquipment)} />)}</group>;
});
