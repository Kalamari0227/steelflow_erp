import {useEffect,useLayoutEffect,useMemo,useState} from 'react';
import {useThree} from '@react-three/fiber';
import {Vector3} from 'three';
import {AssetRegistry} from '../../../src/operations/scene/assets/registry';
import {phaseRequest,sampleRequest} from './poses';
import type {Frame} from './poses';
import {MaterialEntity} from './material';
import {Diagnostics} from './diagnostics';

export function AdmittedScene({assetId,level,frame,angle,cutaway,manifest,manifestHash}:{readonly assetId:string;readonly level:number;readonly frame:Frame;readonly angle:string;readonly cutaway:boolean;readonly manifest:string;readonly manifestHash:string}){
  const {gl,invalidate}=useThree(),[revision,setRevision]=useState(0),[loadError,setLoadError]=useState('');
  const registry=useMemo(()=>new AssetRegistry(manifest,{origin:location.origin}),[manifest]);
  const asset=registry.asset(assetId),outcome=useMemo(()=>{try{const request=phaseRequest(registry.manifest,asset,frame,manifestHash);gl.domElement.dataset.pendingRequest=JSON.stringify(request);return {kind:'ready' as const,sample:sampleRequest(request)};}catch(error){return {kind:'error' as const,error:error instanceof Error?error.message:String(error)};}},[registry,asset,frame,manifestHash,gl]);
  const ownerId=asset.placement_ids[0]?.replace('equipment:','');if(!ownerId)throw new RangeError('Exact asset owner absent');
  const entity=useMemo(()=>{registry.beginRun('factory-contract-run',manifestHash);return registry.entity({run_id:'factory-contract-run',entity_type:'equipment',entity_id:ownerId,bundle_hash:manifestHash},assetId);},[registry,assetId,ownerId,manifestHash]);
  useEffect(()=>()=>registry.dispose(),[registry]);
  useEffect(()=>{let active=true;setLoadError('');gl.domElement.dataset.ready='false';void entity.show(level).then(()=>{if(active){setRevision(n=>n+1);invalidate();}},(e:unknown)=>{if(active)setLoadError(e instanceof Error?e.message:String(e));});return()=>{active=false;};},[entity,level,gl,invalidate]);
  useLayoutEffect(()=>{if(outcome.kind==='error'){gl.domElement.dataset.ready='error';gl.domElement.dataset.error=outcome.error;return;}const sample=outcome.sample;entity.root.position.fromArray(sample.ownerPose.position);entity.root.quaternion.setFromAxisAngle(new Vector3(0,1,0),sample.ownerPose.yaw_rad);entity.applyPose(sample.pose);setRevision(n=>n+1);invalidate();},[entity,outcome,gl,invalidate]);
  useEffect(()=>{entity.setCutaway(cutaway);setRevision(n=>n+1);invalidate();},[entity,cutaway,invalidate]);
  useEffect(()=>{if(loadError){gl.domElement.dataset.ready='error';gl.domElement.dataset.error=loadError;}},[loadError,gl]);
  if(outcome.kind==='error'||loadError)return null;
  return <><primitive object={entity.root}/><MaterialEntity asset={asset} sample={outcome.sample}/><Diagnostics entity={entity} sample={outcome.sample} angle={angle} revision={revision} manifestHash={manifestHash}/></>;
}
