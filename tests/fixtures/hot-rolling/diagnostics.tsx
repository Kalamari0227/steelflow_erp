import { useLayoutEffect } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { Box3, Mesh, OrthographicCamera, Quaternion, Vector3 } from 'three';
import type { AssetEntity } from '../../../src/operations/scene/assets/registry';
import type { phaseSample } from './frames';
import { nearestSurface, connectedComponents, feedAssemblyClearance, nearestMachineSurface, rigidMaterialClearance } from './surface';

export function Diagnostics({ entity, sample, angle, revision, bindingRevision }: { readonly entity: AssetEntity; readonly sample: ReturnType<typeof phaseSample>; readonly angle: string; readonly revision: number; readonly bindingRevision:number }) {
  const { camera, gl, scene, invalidate } = useThree();
  useLayoutEffect(() => {
    const bounds=new Box3().setFromObject(entity.root),size=bounds.getSize(new Vector3()),target=new Vector3(0,1.5,0);
    if (angle==='close') entity.nodes.get(entity.asset.moving_parts[0]?.node_id ?? '')?.getWorldPosition(target);
    const p=angle==='side' ? [0,7,18] : angle==='rear' ? [-14,10,-15] : [12,9,12];
    camera.position.set((p[0] ?? 0)+target.x,(p[1] ?? 0)+target.y,(p[2] ?? 0)+target.z);
    camera.lookAt(target);
    if (camera instanceof OrthographicCamera) camera.zoom=(angle==='close' ? 115 : 70)*10/Math.max(8,size.x,size.z);
    camera.updateProjectionMatrix(); invalidate();
  }, [angle, camera, entity, revision, invalidate]);
  useLayoutEffect(() => { invalidate(); }, [revision, invalidate]);
  useFrame(() => {
    scene.updateMatrixWorld(true); camera.updateMatrixWorld(true);
    let triangles = 0;
    entity.root.traverse(node => { if (node instanceof Mesh) triangles += (node.geometry.index?.count ?? node.geometry.getAttribute('position')?.count ?? 0)/3; });
    const parts = entity.asset.moving_parts.map(part => { const n = entity.nodes.get(part.node_id); return { id: part.id, position: n?.position.toArray(), quaternion: n?.quaternion.toArray(), matrix: n?.matrixWorld.toArray() }; });
    const fixed = entity.asset.fixed_parts.map(part => ({ id: part.id, state: entity.nodes.get(part.node_id)?.userData.operationalState, matrix: entity.nodes.get(part.node_id)?.matrixWorld.toArray() }));
    const materialNodes: { readonly id:string;readonly attachmentId:string;readonly versionId:string;readonly position:number[];readonly min:number[];readonly max:number[];readonly supportDistanceM:number;readonly surface:NonNullable<ReturnType<typeof nearestSurface>>;readonly components:number;readonly matrixWorld:number[];readonly mechanismProgress:number }[]=[];
    let actualMaterial:Mesh|undefined;
    scene.traverse(node => {if(node instanceof Mesh && node.userData.poseMaterial===true){
      actualMaterial=node;
      const bounds=new Box3().setFromObject(node),surface=nearestSurface(node,new Vector3(...sample.pose.contact_m),'down');
      if(!surface)throw new Error('Actual downward material support triangles absent');
      materialNodes.push({id:String(node.userData.materialId),attachmentId:String(node.userData.attachmentId),versionId:String(node.userData.versionId),position:node.getWorldPosition(new Vector3()).toArray(),min:bounds.min.toArray(),max:bounds.max.toArray(),supportDistanceM:surface.distance,surface,components:connectedComponents(node),matrixWorld:node.matrixWorld.toArray(),mechanismProgress:Number(node.userData.mechanismProgress)});
    }});
    const material=actualMaterial;
    const feedWitnesses=sample.internalProjection && material ? sample.internalProjection.witnesses.map(w=>{
      const binding=sample.context.asset_bindings.find(b=>b.owner_id===sample.pose.owner_id);if(!binding || !('internal_feeds' in binding))throw new Error('Pinned feed binding absent');
      const roller=binding.internal_feeds[0]?.rollers.find(r=>r.part_id===w.part_id),surface=roller && entity.nodes.get(roller.surface_node_id);if(!(surface instanceof Mesh))throw new Error('Actual feed barrel absent');
      const point=new Vector3(...w.position_m),machine=nearestSurface(surface,point,'up'),body=nearestSurface(material,point,'down');if(!machine || !body)throw new Error('Actual opposite feed surfaces absent');return {...w,surfaceNodeId:roller?.surface_node_id,machine,material:body};
    }) : [];
    const rigidClearance=sample.internalProjection && material ? rigidMaterialClearance(entity.root,material) : null;
    const feedRoller=entity.nodes.get('feed_roller_idler_0');
    const machineContact=entity.level!==null ? nearestMachineSurface(entity.root,new Vector3(...sample.pose.contact_m)) : null;
    const body=materialNodes[0],feedClearance=feedRoller instanceof Mesh && body ? feedAssemblyClearance(entity.nodes,new Vector3(...sample.pose.contact_m),body.min[2] ?? 0,body.max[2] ?? 0) : null;
    const poseReady=entity.level!==null && material!==undefined && new Vector3(...sample.pose.position_m).distanceTo(material.getWorldPosition(new Vector3()))<1e-9 && entity.asset.moving_parts.every(part=>{
      const binding=part.binding,driver=binding.type==='mechanical_follower' ? entity.asset.moving_parts.find(p=>p.id===binding.driver_part_id) : part,node=entity.nodes.get(part.node_id),rest=entity.asset.nodes.find(n=>n.id===part.node_id),channel=sample.pose.channels.find(c=>c.function_id===driver?.function);if(!driver || !node || !rest || !channel)return false;
      const value=binding.type==='mechanical_follower' ? part.range.rest+binding.ratio*(channel.value-driver.range.rest) : channel.value,delta=value-part.range.rest;
      if(part.motion==='rotation'){const expected=new Quaternion().setFromAxisAngle(new Vector3(...part.axis),delta).multiply(new Quaternion(...rest.transform.rotation_xyzw));return Math.abs(expected.dot(node.quaternion))>1-1e-10;}
      return node.position.distanceTo(new Vector3(...rest.transform.position_m).addScaledVector(new Vector3(...part.axis),delta))<1e-9;
    });
    const sockets = entity.level === null ? [] : entity.sockets();
    const phaseInput={speed:sample.snapshot.run.speed,at_ms:sample.envelope.confirmed_sim_ms,frozen_progress:sample.envelope.frozen_progress,anchor:sample.envelope.anchor,attachment_id:sample.envelope.attachment_id,material:sample.envelope.material,boundary:sample.envelope.boundary,attachments:sample.snapshot.attachments.filter(a => a.material_id===sample.pose.material.material_id)};
    const authority = { source: 't58-fixed-contract', runId: sample.pose.run_id, revision: sample.pose.revision, bundleHash: sample.envelope.bundle_hash, authoritativeElapsedMs: sample.envelope.confirmed_sim_ms, stale: false };
    const nodes = [...parts.filter(p => p.matrix).map(p => ({ entityId: entity.identity.entity_id, id: p.id, kind: 'part', matrixWorld: p.matrix, visible: true })), ...sockets.map(s => ({ entityId: entity.identity.entity_id, id: s.id, kind: 'socket', matrixWorld: s.matrix, visible: true }))];
    gl.domElement.dataset.qaBoundState = JSON.stringify({ authority, sampledAtMs: performance.now(), rafSequence: revision+1, nodes, camera: { matrixWorld: camera.matrixWorld.toArray(), projectionMatrix: camera.projectionMatrix.toArray() } });
    gl.domElement.dataset.assetState = JSON.stringify({ key: entity.key, rootUuid: entity.root.uuid, identity: entity.identity, variant: entity.asset.variant, lod: entity.level, cutaway: entity.cutaway, triangles, parts, fixed, sockets, materialNodes, machineContact, feedClearance, phaseInput, poseReady, feedWitnesses, continuousSupport:sample.continuousSupport, rigidClearance, supportLaw:sample.supportLaw, bindingRevision, pose: sample.pose, frame: sample.frame, camera: { position: camera.position.toArray() } });
  });
  return null;
}
