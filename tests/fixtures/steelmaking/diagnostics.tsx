import { useLayoutEffect, useState } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { Box3, Mesh, Triangle, Vector3 } from 'three';
import type { AssetEntity } from '../../../src/operations/scene/assets/registry';
import { isQaProbeEnabled, QaProbe } from '../../../src/operations/scene/qaProbe';
import type { QaAuthority } from '../../../src/operations/scene/qaProbe';
import type { phaseSample } from './poses';

export function Diagnostics({entity,sample,angle,revision}:{readonly entity:AssetEntity;readonly sample:ReturnType<typeof phaseSample>;readonly angle:string;readonly revision:number}){
  const {camera,gl,scene,invalidate}=useThree();
  const [probe]=useState(()=>new QaProbe(isQaProbeEnabled(location.search,import.meta.env.VITE_STEELFLOW_QA_PROBE==='1')));
  useLayoutEffect(()=>{
    const body=entity.asset.collision_proxies.find(p=>p.purpose==='body'),size=body?.size_m??[10,8,6],center=body?.transform.position_m??[0,3,0];
    let scale=Math.max(...size)*(angle==='close' ? .74 : 1.4);const target=new Vector3(...center);
    const detailNode=entity.asset.kind==='aod'?'gas_tuyere':entity.asset.kind==='blast_furnace'?'tap_control':entity.asset.kind==='shear'?'cutting_tool':null;
    if(angle==='close'&&detailNode){entity.root.updateMatrixWorld(true);entity.nodes.get(detailNode)?.getWorldPosition(target);scale=4.5;}
    const offset=angle==='close'&&entity.asset.kind==='aod' ? new Vector3(-1,.45,.9) : angle==='side' ? new Vector3(0,.55,1.4) : angle==='rear' ? new Vector3(-1,.65,-1.1) : new Vector3(1,.65,1.1);
    camera.position.copy(target.clone().add(offset.multiplyScalar(scale)));camera.lookAt(target);camera.updateProjectionMatrix();invalidate();
  },[entity,angle,camera,invalidate]);
  useLayoutEffect(()=>{invalidate();},[revision,invalidate]);
  useFrame(()=>{
    scene.updateMatrixWorld(true);camera.updateMatrixWorld(true);
    let triangles=0;
    entity.root.traverse(node=>{if(node instanceof Mesh)triangles+=(node.geometry.index?.count??node.geometry.getAttribute('position')?.count??0)/3;});
    const parts=entity.asset.moving_parts.map(part=>{const node=entity.nodes.get(part.node_id);return {id:part.id,position:node?.position.toArray(),quaternion:node?.quaternion.toArray(),matrix:node?.matrixWorld.toArray()};});
    const fixed=entity.asset.fixed_parts.map(part=>{const node=entity.nodes.get(part.node_id);return {id:part.id,state:node?.userData.operationalState??null,localMatrix:node?.matrix.toArray(),matrix:node?.matrixWorld.toArray()};});
    const materialNodes:{readonly id:string;readonly attachmentId:string;readonly versionId:string;readonly form:string;readonly position:readonly number[];readonly min:readonly number[];readonly max:readonly number[];readonly supportDistanceM:number}[]=[];
    const carrierNodes:{readonly id:string;readonly position:readonly number[];readonly materialContactDistanceM:number;readonly supportContactDistanceM:number}[]=[];
    scene.traverse(node=>{
      if(node.userData.fixtureCarrier===true){
        const materialPoint=new Vector3(...sample.pose.contact_m),support=entity.level===null?undefined:entity.sockets().find(s=>s.id==='support'),supportPoint=support?new Vector3(...support.position):null;
        let materialDistance=Infinity,supportDistance=Infinity;
        node.traverse(child=>{if(!(child instanceof Mesh))return;const positions=child.geometry.getAttribute('position'),indices=child.geometry.index;
          for(let i=0;i<(indices?.count??positions.count);i+=3){const vertices=[0,1,2].map(j=>new Vector3().fromBufferAttribute(positions,indices?.getX(i+j)??i+j).applyMatrix4(child.matrixWorld)),a=vertices[0],b=vertices[1],c=vertices[2];if(!a||!b||!c)throw new RangeError('Actual carrier triangle missing');const triangle=new Triangle(a,b,c);materialDistance=Math.min(materialDistance,triangle.closestPointToPoint(materialPoint,new Vector3()).distanceTo(materialPoint));if(supportPoint)supportDistance=Math.min(supportDistance,triangle.closestPointToPoint(supportPoint,new Vector3()).distanceTo(supportPoint));}
        });
        carrierNodes.push({id:String(node.userData.ownerId),position:node.getWorldPosition(new Vector3()).toArray(),materialContactDistanceM:materialDistance,supportContactDistanceM:supportDistance});
      }
      if(node instanceof Mesh&&node.userData.poseMaterial===true){
        const bounds=new Box3().setFromObject(node),point=new Vector3(...sample.pose.contact_m),positions=node.geometry.getAttribute('position'),indices=node.geometry.index;
        let distance=Infinity;
        for(let i=0;i<(indices?.count??positions.count);i+=3){
          const vertices=[0,1,2].map(j=>new Vector3().fromBufferAttribute(positions,indices?.getX(i+j)??i+j).applyMatrix4(node.matrixWorld)),a=vertices[0],b=vertices[1],c=vertices[2];
          if(!a||!b||!c)throw new RangeError('Actual material triangle missing');
          distance=Math.min(distance,new Triangle(a,b,c).closestPointToPoint(point,new Vector3()).distanceTo(point));
        }
        materialNodes.push({id:String(node.userData.materialId),attachmentId:String(node.userData.attachmentId),versionId:String(node.userData.versionId),form:String(node.userData.form),position:node.getWorldPosition(new Vector3()).toArray(),min:bounds.min.toArray(),max:bounds.max.toArray(),supportDistanceM:distance});
      }
    });
    const authority:QaAuthority={source:'t58-fixed-contract',runId:sample.pose.run_id,revision:sample.pose.revision,bundleHash:sample.envelope.bundle_hash,authoritativeElapsedMs:sample.envelope.confirmed_sim_ms,stale:false};
    if(entity.level!==null&&probe.enabled)gl.domElement.dataset.qaBoundState=JSON.stringify(probe.observeAssets([entity],authority,camera));
    gl.domElement.dataset.assetState=JSON.stringify({key:entity.key,rootUuid:entity.root.uuid,identity:entity.identity,variant:entity.asset.variant,lod:entity.level,cutaway:entity.cutaway,triangles,parts,fixed,sockets:entity.level===null?[]:entity.sockets(),materialNodes,carrierNodes,pose:sample.pose,frame:sample.frame,stage:sample.stage,camera:{position:camera.position.toArray()}});
  });
  return null;
}
