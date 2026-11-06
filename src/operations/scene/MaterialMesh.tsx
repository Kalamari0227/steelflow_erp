import { memo, useLayoutEffect, useRef } from 'react';
import type { RefObject } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { Color, Mesh, MeshStandardMaterial } from 'three';
import type { Group } from 'three';
import type { World } from '../../contracts';
import type { Material } from '../contracts';
import { useNavigationStore } from '../navigation';
import { Box, Coil, colors, Cylinder } from '../../journey/scene/parts';
import { processPose } from './processPose';
import { transferPose } from './transferPose';
import { SceneLabel } from './SceneLabel';
import { useSceneHover } from './useSceneHover';
import { updateCoilGeometry } from './coilGeometry';

export const MaterialMesh = memo(function MaterialMesh({ material, worldRef, elapsed, selected }: { readonly material: Material; readonly worldRef: RefObject<World>; readonly elapsed: RefObject<number>; readonly selected: boolean }) {
  const root = useRef<Group>(null), flat = useRef<Group>(null), coil = useRef<Group>(null), liquid = useRef<Group>(null);
  const { camera } = useThree();
  const marker = useRef<Group>(null);
  const surfaces = useRef<MeshStandardMaterial[]>([]);
  const heatedColor = useRef(new Color());
  const previousCoilAmount = useRef(-1);
  const hover = useSceneHover(`material:${material.id}`);
  const form = material.form;
  const isCoil = form.includes('COIL');
  const isLiquid = form === 'LIQUID_STEEL' || form === 'HOT_METAL';
  const hot = /^(HOT_|LIQUID)/.test(form);
  const color = hover.hovered ? '#dceaf0' : hot ? colors.hot : form === 'ORE' ? '#796457' : form === 'SCRAP' ? colors.frame : selected ? '#168e9c' : colors.steel;
  const hotColor = useRef(new Color(colors.hot));
  useLayoutEffect(() => {
    const next: MeshStandardMaterial[] = [];
    root.current?.traverse(object => { if (object instanceof Mesh && object.material instanceof MeshStandardMaterial && object.material.color.getHexString() !== colors.frame.slice(1)) next.push(object.material); });
    surfaces.current = next;
  }, [form, color]);
  useFrame(() => {
    if (!root.current) return;
    const world = worldRef.current;
    const currentMaterial = world.materials.find(row => row.id === material.id);
    if (!currentMaterial) return;
    if (marker.current) marker.current.scale.setScalar(4 / (0.15 * camera.zoom));
    const transport = transferPose(currentMaterial, world, elapsed.current);
    const process = transport ? null : processPose(currentMaterial, world, elapsed.current);
    const pose = transport ?? process;
    if (!pose) return;
    root.current.position.set(...pose.position); root.current.rotation.y = pose.rotationY;
    const phase = process?.phase ?? 0, kind = process?.kind ?? '';
    heatedColor.current.set(color);
    if (process?.hot) heatedColor.current.copy(hotColor.current);
    for (const surface of surfaces.current) { surface.color.copy(heatedColor.current); surface.emissive.set(process?.hot || hot ? colors.hot : selected ? '#168e9c' : '#000000'); surface.emissiveIntensity = process?.hot || hot ? 0.2 + phase * 0.45 : selected ? 0.12 : 0; }
    const winding = kind === 'coiler' || kind === 'laying_head';
    const unwinding = kind === 'uncoiler';
    const mix = winding ? phase : unwinding ? 1 - phase : isCoil ? 1 : 0;
    if (coil.current) {
      coil.current.visible = mix > 0.015;
      if (form === 'WIRE_COIL') coil.current.scale.setScalar(Math.max(0.05, mix));
      else {
        coil.current.scale.setScalar(1);
        if (previousCoilAmount.current !== mix) {
          coil.current.traverse(object => { if (object instanceof Mesh) updateCoilGeometry(object.geometry, mix); });
          previousCoilAmount.current = mix;
        }
      }
      coil.current.rotation.z = winding || unwinding ? phase * Math.PI * 8 : 0;
    }
    if (liquid.current) liquid.current.visible = isLiquid && kind !== 'caster';
    if (flat.current) {
      flat.current.visible = mix < 0.985 && (!isLiquid || kind === 'caster');
      const rolling = ['roughing', 'finishing_mill', 'cold_mill', 'wire_mill', 'bloom_mill'].includes(kind);
      const thin = /STRIP|SHEET|PLATE/.test(form) || isCoil;
      const castForm = world.processes.find(row => row.material_id === material.id && row.status === 'RUNNING')?.output_form;
      const narrow = /BLOOM|BILLET|WIRE/.test(kind === 'caster' ? castForm ?? form : form);
      flat.current.scale.set((thin ? 1.8 : 1) * (rolling ? 1 + phase : 1) * (1 - mix * 0.9), thin ? 0.075 : (narrow ? 0.36 : 0.24) * (rolling ? 1 - phase * 0.75 : 1), narrow ? (castForm === 'BILLET' || form.includes('BILLET') ? 0.22 : 0.4) : 1);
    }
    root.current.userData = { pickKind: 'material', pickId: material.id, materialId: material.id, worldRunId: world.run.id, worldRevision: world.run.revision, form, versionId: currentMaterial.current_version_id, phase, equipmentId: process?.equipmentId ?? null, custody: transport?.custody ?? 'process', selected };
  }, -1);
  const select = () => { const world = worldRef.current; const navigation = useNavigationStore.getState(); const lot = world.lots.find(row => row.id === material.lot_id); navigation.select({ ...navigation.selection, run_id: world.run.id, material_id: material.id, order_id: lot?.order_id }); };
  return <group ref={root} {...hover.events} name={`material:${material.id}`} userData={{ pickKind: 'material', pickId: material.id }} onClick={event => { event.stopPropagation(); select(); }}>
    <group ref={flat} name={`body-flat:${material.id}`}><Box at={[0, 0.5, 0]} size={[2.1, 1, 1.14]} color={color} glow={hot} /></group>
    <group ref={coil} name={`body-coil:${material.id}`} position={[0, 0.7, 0]}><Coil wire={form === 'WIRE_COIL'} color={color} /></group>
    <group ref={liquid} name={`body-liquid:${material.id}`}><Cylinder at={[0, 0.16, 0]} radius={0.65} length={0.3} color={colors.hot} rotation={[0, 0, 0]} /></group>
    {selected && <><group ref={marker} position={[0, 3.9, 0]} name={`material-pick:${material.id}`}><mesh renderOrder={10}><coneGeometry args={[0.15, 0.4, 16]} /><meshBasicMaterial color={colors.hot} depthTest={false} /></mesh></group><SceneLabel text={material.id} at={[0, 4.5, 0]} active /></>}
  </group>;
}, (before, after) => before.material.id === after.material.id && before.material.form === after.material.form && before.worldRef === after.worldRef && before.elapsed === after.elapsed && before.selected === after.selected);
