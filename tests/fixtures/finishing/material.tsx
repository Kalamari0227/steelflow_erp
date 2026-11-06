import {useEffect,useMemo} from 'react';
import {BoxGeometry,Matrix4,Quaternion,Vector3} from 'three';
import type {Asset} from '../../../src/operations/scene/assets/manifest';
import type {FamilySample} from './poses';
import {batchCoil,coldReduction,woundStrip,upperFirstSheet,bathPath,bathThreading,looperAccumulation} from './forming';
import recipe from '../../../assets/source/finishing/recipe.json';

export function MaterialEntity({asset,sample}:{readonly asset:Asset;readonly sample:FamilySample}){
  const d=sample.pose.material.dimensions;
  const shape=useMemo(()=>{
    if(sample.frame.name.startsWith('supplement:')){
      const fn=sample.frame.name.split(':')[1];if(fn!=='entry_looper_lift'&&fn!=='exit_looper_lift')throw new RangeError('Actual supplemental forming law absent');const lift=sample.pose.channels.find(c=>c.function_id===fn)?.value,t=(d.thickness_mm??0)/1000;if(lift===undefined||t<=0||'internal_feed'in sample.pose.material)throw new RangeError('Canonical looper lift and strip required');const p=looperAccumulation(lift,t);return {geometry:p.geometry,proof:{mode:'finite-looper-accumulation',centerlineM:p.centerlineM,targetVolumeM3:p.targetVolumeM3,storedPathM:p.storedPathM,releasedM:p.releasedM,scalar:lift},matrix:new Matrix4()};
    }
    const cfg=recipe.models.find(m=>m.variant===asset.variant)?.source_internal_sequence;
    if(cfg&&(sample.pose.socket_id==='line_coil_support'||sample.pose.socket_id==='line_strip_support'||'internal_feed' in sample.pose.material)){
      const part=asset.moving_parts.find(p=>p.function==='line_unwinding_mandrel'),scalar=sample.pose.channels.find(c=>c.function_id==='line_unwinding_mandrel')?.value;if(!part||scalar===undefined)throw new RangeError('Actual auxiliary source absent');
      const isCoil=sample.pose.socket_id==='line_coil_support',p=woundStrip(isCoil?scalar:0,1.2,cfg.thickness_m,part.range.max);
      if(!isCoil){const alpha=Math.PI+Math.atan((cfg.thickness_m+.0002)/(2*Math.PI)/(.44+cfg.thickness_m/2));p.geometry.rotateZ(alpha);p.geometry.translate(-2,0,0);}
      return {geometry:p.geometry,proof:{mode:isCoil?'finite-auxiliary-coil':'retained-auxiliary-straight',centerlineM:p.centerlineM,targetVolumeM3:p.targetVolumeM3,tailM:p.tailM,scalar},matrix:new Matrix4()};
    }
    if(asset.kind==='coiler'||asset.kind==='uncoiler'){const fn=asset.kind==='coiler'?'winding_mandrel':'unwinding_mandrel',part=asset.moving_parts.find(p=>p.function===fn&&p.binding.type==='clip'),channel=sample.pose.channels.find(c=>c.function_id===fn);if(!part||!channel)throw new RangeError('Canonical forming scalar absent');const p=woundStrip(channel.value,(d.width_mm??1200)/1000,(d.thickness_mm??2)/1000,part.range.max);return {geometry:p.geometry,proof:{mode:'finite-coil',centerlineM:p.centerlineM,targetVolumeM3:p.targetVolumeM3,tailM:p.tailM,scalar:channel.value},matrix:new Matrix4()};}
    if(asset.kind==='pickling'||asset.kind==='galvanizing'){
      const spec=recipe.models.find(m=>m.variant===asset.variant);if(!spec)throw new RangeError('Exact bath source absent');const path=bathPath(asset.kind==='pickling'?'pickling':'galvanizing',spec.stage,spec.thickness_m),part=asset.moving_parts.find(p=>p.function===path.driver&&p.binding.type==='clip'),scalar=sample.pose.channels.find(c=>c.function_id===path.driver)?.value;if(!part||scalar===undefined||'internal_feed'in sample.pose.material)throw new RangeError('Canonical bent bath scalar absent; rigid feed forbidden');const p=bathThreading(path,scalar,spec.thickness_m,part.range.max);return {geometry:p.geometry,proof:{mode:'finite-bath-threading',centerlineM:p.centerlineM,targetVolumeM3:p.targetVolumeM3,travelM:p.travelM,pathLengthM:p.pathLengthM,workPathCoordinateM:0,materialIntervalM:[p.travelM-4,p.travelM],wholeStockExternalCompletion:false,scalar},matrix:new Matrix4()};
    }
    if(asset.kind==='heat_treatment')return {geometry:batchCoil(),proof:{mode:'batch-annulus',outerDiameterM:1.4,innerDiameterM:.6,axis:'Y'},matrix:new Matrix4()};
    if(asset.kind==='cold_mill'&&!('internal_feed' in sample.pose.material)){const scalar=sample.pose.channels.find(c=>c.function_id==='cold_reduction_roll')?.value,spec=recipe.models.find(m=>m.variant===asset.variant);if(scalar===undefined||!spec?.cold_reduction)throw new RangeError('Sealed cold scalar/descriptor absent');const p=coldReduction(scalar),owner=sample.ownerPose,reference=new Matrix4().compose(new Vector3(...owner.position),new Quaternion().setFromAxisAngle(new Vector3(0,1,0),owner.yaw_rad),new Vector3(1,1,1)).multiply(new Matrix4().makeTranslation(spec.cold_reduction.nip_x_m,2.001,0)),material=new Matrix4().compose(new Vector3(...sample.pose.position_m),new Quaternion(...sample.pose.orientation_xyzw),new Vector3(1,1,1));return {geometry:upperFirstSheet(p.geometry),proof:{mode:'cold-reduction',centerlineM:p.centerlineM,targetVolumeM3:.0192,tailXM:p.tailXM,tipXM:p.tipXM,scalar},matrix:material.invert().multiply(reference)};}
    const length=(d.length_mm??4000)/1000,width=(d.width_mm??1200)/1000,t=(d.thickness_mm??2)/1000;
    return {geometry:new BoxGeometry(length,t,width),proof:{mode:asset.internal_feeds?'admitted-linear-feed':asset.kind==='inspection'?'stationary-domain-refinement':'forming-proof-pending',targetVolumeM3:length*t*width},matrix:new Matrix4()};
  },[asset,sample,d]);
  useEffect(()=>()=>shape.geometry.dispose(),[shape]);
  return <group name={'material-root:'+sample.pose.material.material_id} position={[...sample.pose.position_m]} quaternion={[...sample.pose.orientation_xyzw]} userData={{businessMaterialRoot:true,materialId:sample.pose.material.material_id,versionId:sample.pose.material.material_version_id,attachmentId:sample.pose.attachment_id}}><mesh name={'material:'+sample.pose.material.material_id} matrix={shape.matrix} matrixAutoUpdate={false} castShadow userData={{poseMaterial:true,proof:shape.proof,materialId:sample.pose.material.material_id,versionId:sample.pose.material.material_version_id,attachmentId:sample.pose.attachment_id}}><primitive object={shape.geometry} attach="geometry"/><meshStandardMaterial color={sample.pose.material.form==='COATED_STRIP'?'#92a5a8':'#8799a0'} metalness={.8} roughness={.38}/></mesh></group>;
}
