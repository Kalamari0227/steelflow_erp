import {z} from 'zod';
import {Mesh,Triangle,Vector3} from 'three';
import type {Object3D} from 'three';
import source from '../../../../shared/transport-mechanics.json';
import type {Asset} from './manifestShape';
import {effectivePolicy} from '../motion/effectivePolicy';

const text=z.string().min(1),number=z.number().finite(),vector=z.tuple([number,number,number]).readonly();
const range=z.strictObject({min:number,max:number,rest:number}).readonly();
const fields={id:text,function:text,parent_id:text,axis:vector,pivot_m:vector,range,ancestors:z.array(text).min(1).readonly(),motion:z.enum(['rotation','translation'])};
const part=z.discriminatedUnion('representation',[
  z.strictObject({...fields,representation:z.literal('canonical'),driver_id:z.null()}).readonly(),
  z.strictObject({...fields,representation:z.literal('mechanical_follower'),driver_id:text,ratio:number.refine(v=>v!==0)}).readonly(),
]);
const relation=z.strictObject({part_id:text,parent_part_id:text,parent_id:text,ancestors:z.array(text).min(1).readonly()}).readonly();
const registration=z.strictObject({asset_id:text,variant:text,category:z.literal('fleet'),kind:text,policy_id:text,required_parts:z.array(part).min(1).readonly(),nested_followers:z.array(text).readonly(),relative_fixed_parts:z.array(relation).readonly(),follower_socket_descendants:z.array(text).length(0).readonly()}).readonly();
export const transportMechanicsShape=z.strictObject({schema_version:z.literal(1),source_proposal_sha256:z.string().regex(/^[a-f0-9]{64}$/),source_sha256:z.record(text,z.string().regex(/^[a-f0-9]{64}$/)).readonly(),registrations:z.array(registration).length(7).readonly(),scope:text}).readonly();
const trusted=transportMechanicsShape.parse(source);
type Registration=z.infer<typeof registration>;
export class TransportMechanicsError extends Error{readonly code='transport_mechanics';constructor(readonly reference:string){super(`transport_mechanics: ${reference}`);}}
function requireTransport(condition:boolean,reference:string):asserts condition{if(!condition)throw new TransportMechanicsError(reference);}
const same=(a:readonly(string|number)[],b:readonly(string|number)[]):boolean=>a.length===b.length&&a.every((v,i)=>v===b[i]);
function selected(asset:Asset):Registration|undefined{return trusted.registrations.find(r=>r.asset_id===asset.id);}
function ancestors(asset:Asset,id:string):readonly string[]{
  const result:string[]=[],seen=new Set<string>([id]);let cursor=asset.nodes.find(n=>n.id===id)?.parent_id;
  requireTransport(cursor!==undefined,`${id}:node`);
  while(cursor!==null){requireTransport(!seen.has(cursor),`${id}:cycle`);seen.add(cursor);result.push(cursor);const node=asset.nodes.find(n=>n.id===cursor);requireTransport(node!==undefined,`${id}:parent`);cursor=node.parent_id;}
  return result;
}
function descendant(asset:Asset,id:string,root:string):boolean{return id===root||ancestors(asset,id).includes(root);}

/** Closed seven-source opt-in. Callers cannot supply a replacement authority table. */
export function validateTransportMechanics(asset:Asset):Registration|undefined{
  const row=selected(asset);if(!row)return undefined;
  requireTransport((asset.motion_policy_id??null)===null&&asset.category===row.category&&asset.kind===row.kind&&asset.variant===row.variant&&asset.family==='transport',`${asset.id}:identity`);
  requireTransport(effectivePolicy(asset.category,asset.kind,'',asset.motion_policy_id).id===row.policy_id,`${asset.id}:policy`);
  requireTransport(asset.moving_parts.length===row.required_parts.length&&new Set(asset.moving_parts.map(p=>p.id)).size===asset.moving_parts.length,`${asset.id}:part-universe`);
  for(const expected of row.required_parts){
    const actual=asset.moving_parts.find(p=>p.id===expected.id),node=asset.nodes.find(n=>n.id===expected.id);requireTransport(actual!==undefined&&node!==undefined,`${expected.id}:required-part`);
    requireTransport(actual.node_id===expected.id&&actual.function===expected.function&&actual.role==='operational'&&actual.motion===expected.motion,`${expected.id}:function`);
    requireTransport(node.parent_id===expected.parent_id&&same(ancestors(asset,node.id),expected.ancestors),`${expected.id}:ancestry`);
    requireTransport(same(actual.axis,expected.axis)&&same(actual.pivot_m,expected.pivot_m)&&same(node.transform.position_m,expected.pivot_m),`${expected.id}:frame`);
    requireTransport(actual.range.min===expected.range.min&&actual.range.max===expected.range.max&&actual.range.rest===expected.range.rest&&actual.range.unit===(actual.motion==='rotation'?'rad':'m'),`${expected.id}:range`);
    const binding=actual.binding;
    switch(expected.representation){
      case'canonical':requireTransport(binding.type==='clip'&&binding.clip_id===`${asset.id.split(':').at(-1)}.${expected.id}`,`${expected.id}:clip`);break;
      case'mechanical_follower':{
        requireTransport(binding.type==='mechanical_follower'&&binding.driver_part_id===expected.driver_id&&binding.ratio===expected.ratio,`${expected.id}:driver`);
        const driver=asset.moving_parts.find(p=>p.id===expected.driver_id);requireTransport(driver?.binding.type==='clip',`${expected.id}:canonical-driver`);
        for(const socket of asset.sockets)requireTransport(!descendant(asset,socket.node_id,actual.node_id),`${expected.id}:follower-socket`);
        break;
      }
      default:{const never:never=expected;throw new TransportMechanicsError(String(never));}
    }
    if(expected.function==='wheel_rotation')for(const suffix of ['_tyre','_rim','_rotation_index']){const surface=asset.nodes.find(n=>n.id===expected.id+suffix);requireTransport(surface?.parent_id===expected.id,`${expected.id}:whole-wheel:${suffix}`);}
  }
  for(const fixed of row.relative_fixed_parts){
    const part=asset.fixed_parts.find(p=>p.id===fixed.part_id),node=asset.nodes.find(n=>n.id===fixed.part_id),parent=asset.moving_parts.find(p=>p.id===fixed.parent_part_id);
    requireTransport(part!==undefined&&part.id===part.node_id&&part.id===part.function&&part.binding===null&&part.fixed_to_part_id===fixed.parent_part_id,`${fixed.part_id}:relative-fixed`);
    requireTransport(node?.parent_id===fixed.parent_id&&same(ancestors(asset,fixed.part_id),fixed.ancestors)&&parent?.binding.type==='clip',`${fixed.part_id}:fixed-parent`);
    requireTransport(ancestors(asset,parent.id).every(id=>!asset.moving_parts.some(p=>p.node_id===id)),`${fixed.part_id}:fixed-parent-ancestors`);
    for(const child of asset.nodes.filter(n=>descendant(asset,n.id,fixed.part_id))){requireTransport(!asset.moving_parts.some(p=>p.node_id===child.id)&&!asset.sockets.some(s=>s.node_id===child.id)&&!asset.fixed_parts.some(p=>p.id!==part.id&&p.node_id===child.id),`${fixed.part_id}:static-branch`);}
  }
  return row;
}

export function reviewedTransportFollower(asset:Asset,id:string):boolean{return selected(asset)?.nested_followers.includes(id)??false;}
export function reviewedTransportFixed(asset:Asset,id:string):boolean{return selected(asset)?.relative_fixed_parts.some(p=>p.part_id===id)??false;}

/** Required wheel surfaces are independently decoded; a lone rotating index cannot substitute. */
export function validateTransportDecodedGeometry(asset:Asset,nodes:ReadonlyMap<string,Object3D>):void{
  const row=validateTransportMechanics(asset);if(!row)return;
  for(const part of row.required_parts){const surfaces=part.function==='wheel_rotation'?['_tyre','_rim','_rotation_index'].map(s=>part.id+s):part.id==='grab_open'?['grab_left_floor','grab_left_outer_wall']:part.id==='grab_right'?['grab_right_floor','grab_right_outer_wall']:[];
    for(const id of surfaces){const mesh=nodes.get(id);requireTransport(mesh instanceof Mesh,`${part.id}:surface-mesh:${id}`);const p=mesh.geometry.getAttribute('position'),index=mesh.geometry.index;requireTransport(p!==undefined&&p.itemSize===3,`${id}:positions`);let positive=false;for(let i=0;i<(index?.count??p.count);i+=3){const [a,b,c]=[0,1,2].map(j=>new Vector3().fromBufferAttribute(p,index?index.getX(i+j):i+j));requireTransport(a!==undefined&&b!==undefined&&c!==undefined,`${id}:triangle`);if(new Triangle(a,b,c).getArea()>0)positive=true;}requireTransport(positive,`${id}:real-surface`);}
  }
}
