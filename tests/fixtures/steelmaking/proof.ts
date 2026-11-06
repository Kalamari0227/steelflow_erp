import { expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { Matrix4, Quaternion, Vector3 } from 'three';
import { z } from 'zod';
import type { Asset } from '../../../src/operations/scene/assets/manifest';
import { AuthoritySchema } from '../../helpers/factory';

const number=z.number().finite(),vector=z.array(number).length(3),quaternion=z.array(number).length(4),matrix=z.array(number).length(16);
export const stateShape=z.object({key:z.string(),rootUuid:z.string(),variant:z.string(),lod:number.nullable(),cutaway:z.boolean(),triangles:number,
  parts:z.array(z.object({id:z.string(),position:vector,quaternion,matrix})),fixed:z.array(z.object({id:z.string(),state:number.nullable(),localMatrix:matrix,matrix})),
  sockets:z.array(z.object({id:z.string(),position:vector,normal:vector})),materialNodes:z.array(z.object({id:z.string(),attachmentId:z.string(),versionId:z.string(),form:z.string(),position:vector,min:vector,max:vector,supportDistanceM:number})),carrierNodes:z.array(z.object({id:z.string(),position:vector,materialContactDistanceM:number,supportContactDistanceM:number})),
  pose:z.object({socket_id:z.string(),contact_m:vector,position_m:vector,channels:z.array(z.object({function_id:z.string(),kind:z.string(),value:number}))}),frame:z.object({index:number,name:z.string(),progress:number,clock:z.string()}),stage:z.string()}).passthrough();
export type State=z.infer<typeof stateShape>;
export const contractShape=z.object({authority:AuthoritySchema,manifestSha256:z.string(),familyHashes:z.array(z.string()).length(2),policySha256:z.string(),recipesSha256:z.string(),envelope:z.object({run_id:z.string(),revision:number,bundle_hash:z.string(),confirmed_sim_ms:number,material:z.object({material_id:z.string()})}).passthrough(),snapshot:z.object({run:z.object({id:z.string(),revision:number,elapsed_ms:number}).passthrough(),attachments:z.array(z.object({material_id:z.string(),released_at_ms:number.nullable()}).passthrough())}).passthrough()});
export const state=async(page:Page)=>stateShape.parse(JSON.parse(await page.locator('canvas').getAttribute('data-asset-state')??'null'));
export const contract=async(page:Page)=>contractShape.parse(JSON.parse(await page.getByTestId('fixture-contract').textContent()??'null'));
export const button=(page:Page,name:string)=>page.getByRole('button',{name,exact:true});
const xyz=(values:readonly number[])=>new Vector3(values[0]??NaN,values[1]??NaN,values[2]??NaN);
const xyzw=(values:readonly number[])=>new Quaternion(values[0]??NaN,values[1]??NaN,values[2]??NaN,values[3]??NaN);

/** Compare the real bound transforms to admitted scalar values, including every follower. */
export function assertMechanics(asset:Asset,current:State){
  expect(current.materialNodes).toHaveLength(1);expect(current.materialNodes[0]?.supportDistanceM).toBeLessThanOrEqual(.01);
  const support=current.sockets.find(s=>s.id===current.pose.socket_id);if(!support)throw new RangeError('Actual supporting socket missing');
  expect(xyz(current.pose.contact_m).distanceTo(xyz(support.position))).toBeLessThanOrEqual(.01);
  for(const part of asset.moving_parts){
    const actual=current.parts.find(p=>p.id===part.id),node=asset.nodes.find(n=>n.id===part.node_id);if(!actual||!node)throw new RangeError('Actual operational node missing');
    const binding=part.binding;
    const driver=binding.type==='mechanical_follower' ? asset.moving_parts.find(p=>p.id===binding.driver_part_id) : part;
    if(!driver)throw new RangeError('Canonical driver absent');
    const channel=current.pose.channels.find(c=>c.function_id===driver.function);if(!channel)throw new RangeError('Authoritative scalar absent');
    const displacement=(channel.value-driver.range.rest)*(part.binding.type==='mechanical_follower'?part.binding.ratio:1);
    if(part.motion==='rotation'){
      const expected=new Quaternion().setFromAxisAngle(xyz(part.axis),displacement).multiply(xyzw(node.transform.rotation_xyzw));
      expect(Math.abs(expected.dot(xyzw(actual.quaternion)))).toBeCloseTo(1,5);
      expect(xyz(actual.position).distanceTo(xyz(node.transform.position_m))).toBeLessThan(2e-5);
    }else{
      const expected=xyz(node.transform.position_m).addScaledVector(xyz(part.axis),displacement);
      expect(xyz(actual.position).distanceTo(expected)).toBeLessThan(2e-5);
    }
  }
  for(const part of asset.fixed_parts){
    const actual=current.fixed.find(p=>p.id===part.id),node=asset.nodes.find(n=>n.id===part.node_id);if(!actual||!node)throw new RangeError('Actual fixed support missing');
    const rest=new Matrix4().compose(xyz(node.transform.position_m),xyzw(node.transform.rotation_xyzw),new Vector3(1,1,1));
    expect(actual.localMatrix.every((v,i)=>Math.abs(v-(rest.elements[i]??Infinity))<2e-5)).toBe(true);
    const parentId='fixed_to_part_id' in part ? z.string().parse(part.fixed_to_part_id) : null;
    if(parentId){const parent=current.parts.find(p=>p.id===parentId);if(!parent)throw new RangeError('Actual fixed frame parent missing');const expected=new Matrix4().fromArray(parent.matrix).multiply(rest);expect(actual.matrix.every((v,i)=>Math.abs(v-(expected.elements[i]??Infinity))<3e-5)).toBe(true);}
    if(part.binding!==null)expect(actual.state).toBe(current.pose.channels.find(c=>c.function_id===part.function)?.value);
  }
  const value=(fn:string)=>current.pose.channels.find(c=>c.function_id===fn)?.value??0,max=(fn:string)=>asset.moving_parts.find(p=>p.id===fn)?.range.max??NaN;
  if(asset.kind==='eaf'){
    if(value('roof_swing')>1e-5)expect(value('electrode_lift')).toBeCloseTo(max('electrode_lift'),6);
    if(current.stage==='스크랩 장입'){expect(value('roof_swing')).toBeCloseTo(max('roof_swing'),6);expect(current.materialNodes[0]?.form).toBe('SCRAP');}
    if(value('vessel_tilt')>1e-5)expect(value('roof_swing')).toBeCloseTo(max('roof_swing'),6);
  }
  if(asset.kind==='bof'&&value('vessel_tilt')>1e-5)expect(value('oxygen_lance')).toBeCloseTo(max('oxygen_lance'),6);
  if(asset.kind==='aod'&&value('vessel_tilt')>1e-5)expect(value('gas_tuyere')).toBe(0);
  if(asset.kind==='ladle_furnace'){expect(current.carrierNodes).toHaveLength(1);expect(current.carrierNodes[0]?.materialContactDistanceM).toBeLessThanOrEqual(.01);expect(current.carrierNodes[0]?.supportContactDistanceM).toBeLessThanOrEqual(.01);}
}
