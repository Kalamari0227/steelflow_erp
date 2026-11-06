import type { Asset, AssetManifest } from '../../../src/operations/scene/assets/manifest';
import { bindingsFromAssetManifest, evaluateMotion, parseMotionContext, parseMotionEnvelopeValue } from '../../../src/operations/scene/motion/contracts';
import type { MotionPose } from '../../../src/operations/scene/motion/contracts';
import { fixture, recipes } from '../../../src/operations/scene/motion/testFixtures';
import { requireAsset } from '../../../src/operations/scene/assets/errors';
import { z } from 'zod';
import contracts from './contracts.json';

export type Clock = 'running' | 'paused' | 'blocked';
export type Frame = { readonly index: number; readonly progress: number; readonly clock: Clock; readonly name: string };
export const frameAt = (index: number, clock: Clock): Frame => ({ index, progress:index/64, clock, name:index===0 ? 'idle' : index===64 ? 'complete' : clock==='blocked' ? 'blocked' : clock==='paused' ? 'paused' : `running-${index}` });
const unit = (value:number) => Math.min(1,Math.max(0,value));
const ramp = (p:number,a:number,b:number) => unit((p-a)/(b-a));

/** Sequential EAF buckets open only after the electrodes clear the roof and charge path. */
export function mechanismValue(kind:string, fn:string, p:number):number {
  switch(kind){
    case 'eaf':
      switch(fn){
        case 'electrode_lift': return p<.125 ? ramp(p,0,.125) : p<.5 ? 1 : p<.625 ? 1-ramp(p,.5,.625) : p<.75 ? 0 : ramp(p,.75,.8125);
        case 'roof_swing': return p<.125 ? 0 : p<.25 ? ramp(p,.125,.25) : p<.375 ? 1 : p<.5 ? 1-ramp(p,.375,.5) : p<.8125 ? 0 : ramp(p,.8125,.875);
        case 'vessel_tilt': return ramp(p,.875,1);
        default: throw new RangeError(`Unregistered EAF function ${fn}`);
      }
    case 'bof': return fn==='oxygen_lance' ? p<.25 ? 1 : p<.45 ? 1-ramp(p,.25,.45) : ramp(p,.65,.8) : ramp(p,.8,1);
    case 'aod': return fn==='gas_tuyere' ? Number(p>=.125&&p<.75) : ramp(p,.75,1);
    case 'ladle_furnace': return p<.25 ? 1-ramp(p,0,.25) : ramp(p,.75,1);
    case 'caster': return fn==='mold_oscillation' ? .5-.5*Math.cos(p*16*Math.PI) : p;
    case 'shear': return p<.25 ? 0 : p<.65 ? ramp(p,.25,.65) : 1-ramp(p,.65,1);
    case 'blast_furnace': return fn==='charge_gate' ? p<.3 ? Math.sin(p/.3*Math.PI) : 0 : p<.45 ? 0 : p<.8 ? ramp(p,.45,.8) : 1-ramp(p,.8,1);
    case 'charge': return p<.2 ? 0 : p<.65 ? ramp(p,.2,.65) : 1-ramp(p,.65,1);
    default: throw new RangeError(`Unregistered steelmaking kind ${kind}`);
  }
}

export function stageName(kind:string,p:number):string {
  switch(kind){
    case 'eaf': return p<.125 ? '전극 후퇴' : p<.25 ? '지붕 회피' : p<.375 ? '스크랩 장입' : p<.5 ? '지붕 폐쇄' : p<.625 ? '전극 하강' : p<.75 ? '용해' : p<.8125 ? '출강 전 전극 후퇴' : p<.875 ? '출강 전 지붕 회피' : '용강 출강';
    case 'caster': return p<.125 ? '용강 수취' : p<.8 ? '단면별 응고 · 인출' : '주편 인계';
    case 'shear': return p<.25 ? '소재 지지 · 정렬' : p<.65 ? '단면 절단' : '공구 복귀 · 절단재 인계';
    case 'blast_furnace': return p<.3 ? '원료 장입' : p<.45 ? '제선' : p<.8 ? '출선구 개방' : '출선 종료';
    default: return p<.25 ? '소재 수취' : p<.75 ? '정련 작업' : '출강 · 인계';
  }
}
const formShape=z.enum(['ORE','HOT_METAL','LIQUID_STEEL','SCRAP','SLAB','BLOOM','BILLET']);

/** One admitted machine pose and one material custody, projected from explicit synthetic snapshots. */
export function phaseSample(manifest:AssetManifest,asset:Asset,frame:Frame){
  const specification=contracts.models.find(m=>m.variant===asset.variant);requireAsset(specification,'binding',asset.variant);
  const p=frame.progress,input=fixture(),ownerId=asset.placement_ids[0]?.replace(/^equipment:/,'');requireAsset(ownerId,'binding','placement');
  const recipe=recipes.recipes.find(r=>r.id===specification.recipeId);requireAsset(recipe,'binding',specification.recipeId);
  let form:MotionPose['material']['form']=formShape.parse(p<.45 ? specification.inputForm : specification.outputForm);
  if(asset.kind==='eaf')form=p<.625 ? 'SCRAP' : 'LIQUID_STEEL';
  if(asset.kind==='blast_furnace')form=p<.3 ? 'ORE' : 'HOT_METAL';
  if(asset.kind==='caster')form=formShape.parse(p<.125 ? specification.inputForm : specification.outputForm);
  const family=form==='HOT_METAL' ? 'LIQUID_IRON' : form;
  const families:Record<string,string>={};
  for(const socket of asset.sockets){const selected=socket.forms.includes(family) ? family : socket.forms[0];requireAsset(selected,'binding',socket.id);families[socket.id]=selected;}
  const bindings=bindingsFromAssetManifest(manifest,[{owner_id:ownerId,asset_id:asset.id,socket_families:families}]),binding=bindings[0];
  const socketId=(asset.kind==='caster'&&p<.125)||(asset.kind==='blast_furnace'&&p<.3) ? 'entry' : 'work';
  const support=binding?.sockets.find(s=>s.socket_id===socketId);requireAsset(binding&&support,'binding','actual material support');
  const solid=['SLAB','BLOOM','BILLET'].includes(form),width=form==='SLAB' ? 1350 : form==='BLOOM' ? 480 : form==='BILLET' ? 260 : asset.kind==='blast_furnace'&&form==='HOT_METAL' ? 400 : 700;
  const thickness=asset.kind==='eaf'&&p>=.25&&p<.375 ? 7000 : form==='SLAB' ? 200 : form==='BLOOM' ? 480 : form==='BILLET' ? 260 : form==='ORE'||form==='SCRAP' ? 500 : asset.kind==='blast_furnace' ? 80 : 150;
  const dimensions={length_mm:asset.kind==='caster'&&solid ? Math.PI/2*3650+(2.9+p*1.7)*1000 : asset.kind==='shear'&&p>=.65 ? 1200 : solid ? 2400 : 700,width_mm:width,thickness_mm:thickness,diameter_mm:null,inner_diameter_mm:null};
  const elapsed=frame.index*125;
  Object.assign(input.envelope,{recipe_id:recipe.id,frozen_progress:p,clock_state:frame.clock,confirmed_sim_ms:elapsed,effective_sim_ms:elapsed,phase_start_ms:0,phase_end_ms:8000});
  Object.assign(input.context.snapshot.run,{elapsed_ms:elapsed,playing:frame.clock==='running'});
  input.envelope.anchor={owner_id:ownerId,socket_id:support.socket_id,position_m:[...support.position_m],orientation_xyzw:[...support.orientation_xyzw]};
  Object.assign(input.envelope.material,{form,dimensions,support_local_mm:[0,-thickness/2,0],orientation_xyzw:[0,0,0,1]});
  input.envelope.channels=binding.functions.map(fn=>{
    const need=recipe.functions.find(f=>f.function_id===fn.function_id);requireAsset(need,'binding',fn.function_id);
    const value=fn.min_value+(fn.max_value-fn.min_value)*mechanismValue(asset.kind,fn.function_id,p);
    return {function_id:fn.function_id,node_id:fn.node_id,kind:fn.kind,window_id:need.window_id,axis:[...fn.axis],pivot_m:[...fn.pivot_m],start_value:value,end_value:value};
  });
  for(const owner of input.context.world.owners){owner.id=ownerId;owner.sockets.push(...binding.sockets.map(s=>({id:s.socket_id,pose:{position:[...s.position_m],yaw_rad:0}})));}
  for(const row of [...input.context.world.slots,...input.context.world.ports,...input.context.world.footprints,...input.context.world.allowed_interiors])row.owner_id=ownerId;
  for(const process of input.context.snapshot.processes)Object.assign(process,{equipment_id:ownerId,route_step_id:recipe.source_step_ids[0] ?? specification.recipeId.replace('motion:source:',''),status:frame.clock==='blocked' ? 'BLOCKED' : 'RUNNING',start_ms:0,end_ms:8000});
  // Snapshot-only lineage: immutable input and current output versions remain distinct.
  // These explicit contract rows do not claim the future production scheduler emitted them.
  const oldVersionId=input.envelope.material.material_version_id,initialVersionId=`fixture:${specification.key}:input`;
  const ordinal=asset.kind==='eaf' ? p<.25?1:p<.375?2:p<.625?3:4 : asset.kind==='caster' ? p<.125?1:frame.index-6 : asset.kind==='shear' ? p<.65?1:2 : form===specification.inputForm?1:2;
  const currentVersionId=ordinal===1?initialVersionId:`fixture:${specification.key}:version-${ordinal}`;
  const initialForm=formShape.parse(specification.inputForm),initialWidth=initialForm==='SLAB'?1350:initialForm==='BLOOM'?480:initialForm==='BILLET'?260:700;
  const initialThickness=initialForm==='SLAB'?200:initialForm==='BLOOM'?480:initialForm==='BILLET'?260:initialForm==='ORE'||initialForm==='SCRAP'?500:150;
  const initialDimensions={...dimensions,length_mm:['SLAB','BLOOM','BILLET'].includes(initialForm)?2400:700,width_mm:initialWidth,thickness_mm:initialThickness};
  const originalVersion=input.context.snapshot.material_versions.find(v=>v.id===oldVersionId);requireAsset(originalVersion,'binding','input material version');
  Object.assign(originalVersion,{id:initialVersionId,form:initialForm,dimensions:initialDimensions});
  for(const io of input.context.snapshot.batch_io)if(io.material_version_id===oldVersionId)io.material_version_id=initialVersionId;
  if(ordinal>1){
    input.context.snapshot.material_versions.push({...originalVersion,id:currentVersionId,ordinal,form,dimensions:structuredClone(dimensions)});
    input.context.snapshot.batch_io.push({run_id:input.envelope.run_id,id:`fixture:${specification.key}:output`,batch_id:'motion-batch',role:'OUTPUT',material_version_id:currentVersionId,quantity_kg:originalVersion.weight_kg,source_id:null});
    input.context.snapshot.version_edges.push({run_id:input.envelope.run_id,id:`fixture:${specification.key}:edge-${ordinal}`,batch_id:'motion-batch',input_version_id:initialVersionId,output_version_id:currentVersionId,transferred_kg:originalVersion.weight_kg});
  }
  input.envelope.material.material_version_id=currentVersionId;
  for(const batch of input.context.snapshot.process_batches)if(batch.id==='motion-batch')Object.assign(batch,{recipe_id:recipe.id,start_ms:0,end_ms:8000});
  for(const material of input.context.snapshot.materials)if(material.id===input.envelope.material.material_id)Object.assign(material,{form,dimensions:structuredClone(dimensions),current_version_id:currentVersionId});
  for(const stock of input.context.snapshot.stock_lots)if(stock.id===input.envelope.material.material_id)stock.form=initialForm;
  for(const attachment of input.context.snapshot.attachments)if(attachment.id===input.envelope.attachment_id)Object.assign(attachment,{kind:'equipment',owner_id:ownerId,socket_id:support.socket_id,acquired_at_ms:0});
  const envelope=parseMotionEnvelopeValue(input.envelope),context=parseMotionContext({...input.context,asset_bindings:bindings,authorizations:[envelope]});
  const pose=evaluateMotion(envelope,context,recipes);
  return {pose,envelope,snapshot:context.snapshot,frame,stage:stageName(asset.kind,p),synthetic:true};
}
