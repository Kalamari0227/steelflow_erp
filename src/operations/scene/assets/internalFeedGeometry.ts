import { Matrix4, Mesh, Object3D, Quaternion, Triangle, Vector3 } from 'three';
import type { Asset } from './manifestShape';
import { requireAsset } from './errors';
import type { InternalFeedAsset } from '../motion/internalFeed';
import { sequenceFor } from '../motion/finishingContinuity';

const tolerance=1e-6;
function rootMatrix(asset:Asset,id:string):Matrix4 {
  const n=asset.nodes.find(n=>n.id===id);requireAsset(n,'binding',`feed node:${id}`);
  const local=new Matrix4().compose(new Vector3(...n.transform.position_m),new Quaternion(...n.transform.rotation_xyzw),new Vector3(1,1,1));
  return n.parent_id===null ? local : rootMatrix(asset,n.parent_id).multiply(local);
}

function equipmentFrame(asset:Asset,id:string):Matrix4 {
  return rootMatrix(asset,asset.root_node_id).invert().multiply(rootMatrix(asset,id));
}

export function isFeedLiftAncestor(asset:Asset,partId:string,ancestorId:string):boolean {
  return (asset.internal_feeds ?? []).some(feed=>feed.support_lift_part_id===ancestorId && feed.rollers.some(r=>r.part_id===partId));
}

export function validateAssetInternalFeeds(asset:Asset):void {
  if(!asset.internal_feeds)return;
  for(const feed of asset.internal_feeds){
    const liftId=feed.support_lift_part_id;
    requireAsset(liftId!==undefined || !asset.moving_parts.some(p=>p.function==='line_feed_lift'),'binding',feed.id);
    if(liftId!==undefined){
      const owner=asset.placement_ids[0]?.replace(/^equipment:/,'') ?? '',sequence=sequenceFor({owner_id:owner,policy_id:asset.motion_policy_id ?? ''}),lift=asset.moving_parts.find(p=>p.id===liftId);
      requireAsset(sequence && lift && lift.id===sequence.lift_function_id && lift.function===sequence.lift_function_id && lift.node_id===lift.id && lift.role==='operational' && lift.motion==='translation' && lift.binding.type==='clip' && lift.range.min<0 && lift.range.max===0 && lift.range.rest===0 && lift.range.unit==='m','binding',feed.id);
      const liftNode=asset.nodes.find(n=>n.id===lift.node_id);requireAsset(liftNode,'binding',feed.id);
      const frame=liftNode.parent_id===null ? new Matrix4() : equipmentFrame(asset,liftNode.parent_id);
      requireAsset(new Vector3(...lift.axis).transformDirection(frame).distanceTo(new Vector3(0,1,0))<=1e-9 && feed.driver_part_id===sequence.feed_function_id && feed.custody_socket_id===sequence.feed_socket_id,'binding',feed.id);
      let ancestor=liftNode.parent_id;
      while(ancestor!==null){requireAsset(!asset.moving_parts.some(p=>p.node_id===ancestor),'binding',feed.id);const node=asset.nodes.find(n=>n.id===ancestor);requireAsset(node,'binding',feed.id);ancestor=node.parent_id;}
    }
    const driver=asset.moving_parts.find(p=>p.id===feed.driver_part_id),socket=asset.sockets.find(s=>s.id===feed.custody_socket_id);
    requireAsset(driver && driver.role==='operational' && driver.motion==='rotation' && driver.binding.type==='clip' && socket,'binding',feed.id);
    const ancestorIds=new Set<string>();let node=asset.nodes.find(n=>n.id===socket.node_id);while(node){ancestorIds.add(node.id);node=asset.nodes.find(n=>n.id===node?.parent_id);}
    requireAsset(!asset.moving_parts.some(p=>ancestorIds.has(p.node_id)),'binding',feed.id);
    requireAsset(feed.start_m[0]<feed.end_m[0] && feed.start_m[1]===feed.end_m[1] && feed.start_m[2]===0 && feed.end_m[2]===0,'binding',feed.id);
    requireAsset(new Set(feed.rollers.map(r=>r.part_id)).size===feed.rollers.length && new Set(feed.rollers.map(r=>r.surface_node_id)).size===feed.rollers.length,'binding',feed.id);
    const drive=feed.rollers.find(r=>r.part_id===driver.id);requireAsset(drive,'binding',feed.id);
    requireAsset(Math.abs(feed.end_m[0]-feed.start_m[0]-drive.radius_m*(driver.range.max-driver.range.min))<=1e-9,'binding',feed.id);
    for(const r of feed.rollers){
      const part=asset.moving_parts.find(p=>p.id===r.part_id),surface=asset.nodes.find(n=>n.id===r.surface_node_id);requireAsset(part && surface,'binding',r.part_id);
      requireAsset(surface.id===part.node_id || surface.parent_id===part.node_id && !asset.moving_parts.some(p=>p.node_id===surface.id),'binding',r.surface_node_id);
      let ancestor=asset.nodes.find(n=>n.id===part.node_id)?.parent_id,hasLift=false;
      while(ancestor!==null && ancestor!==undefined){
        const moving=asset.moving_parts.find(p=>p.node_id===ancestor);
        requireAsset(!moving || moving.id===liftId,'binding',`${feed.id}:${part.id}:moving-ancestor`);
        if(moving?.id===liftId)hasLift=true;
        const node=asset.nodes.find(n=>n.id===ancestor);requireAsset(node,'binding',feed.id);ancestor=node.parent_id;
      }
      requireAsset(liftId===undefined || hasLift,'binding',`${feed.id}:${part.id}:lift-ancestry`);
      const partNode=asset.nodes.find(n=>n.id===part.node_id);requireAsset(partNode,'binding',part.id);
      const parent=partNode.parent_id===null ? new Matrix4() : equipmentFrame(asset,partNode.parent_id),axis=new Vector3(...part.axis).transformDirection(parent),frame=equipmentFrame(asset,part.node_id),center=new Vector3().setFromMatrixPosition(frame),barrelAxis=new Vector3(0,0,1).transformDirection(frame);
      requireAsset(Math.abs(barrelAxis.dot(axis))>=1-1e-9,'binding',`${feed.id}:${part.id}:barrel-axis`);
      requireAsset(part.motion==='rotation' && axis.distanceTo(new Vector3(0,0,-1))<=1e-9 && Math.abs(center.z)<=1e-9 && Math.abs(center.y+r.radius_m-feed.start_m[1])<=1e-9,'binding',part.id);
      if(part.id!==driver.id)requireAsset(part.binding.type==='mechanical_follower' && part.binding.driver_part_id===driver.id && part.binding.ratio>0 && Math.abs(part.binding.ratio-drive.radius_m/r.radius_m)<=1e-9,'binding',part.id);
    }
  }
}

/** Closed regular cylinder proof from every actual triangle, independent of shading normals. */
export function validateCylinderSurface(surface:Mesh,part:Object3D,radius:number,width:number,reference:string) {
  const position=surface.geometry.getAttribute('position'),index=surface.geometry.index,transform=part.matrixWorld.clone().invert().multiply(surface.matrixWorld);
  requireAsset(position && position.itemSize===3,'binding',reference);
  const count=index?.count ?? position.count;requireAsset(count>0 && count%3===0,'binding',reference);
  const vertices=Array.from({length:position.count},(_,i)=>new Vector3().fromBufferAttribute(position,i).applyMatrix4(transform));
  const rings:[Vector3[],Vector3[]]=[[],[]],mapping:number[]=[];
  for(const v of vertices){
    requireAsset(Number.isFinite(v.x+v.y+v.z) && Math.abs(Math.hypot(v.x,v.y)-radius)<=tolerance,'binding',reference);
    const layer=Math.abs(v.z+width/2)<=tolerance ? 0 : Math.abs(v.z-width/2)<=tolerance ? 1 : -1;requireAsset(layer!==-1,'binding',reference);
    const ring=rings[layer===0 ? 0 : 1];let id=ring.findIndex(p=>p.distanceTo(v)<=tolerance);if(id===-1){id=ring.length;ring.push(v);}mapping.push((layer===0 ? 0 : 256)+id);
  }
  const n=rings[0].length;requireAsset(n>=16 && n<=256 && rings[1].length===n && count/3<=4*n,'binding',reference);
  const angle=(v:Vector3)=>Math.atan2(v.y,v.x),ordered=rings[0].map((v,id)=>({v,id,angle:angle(v)})).sort((a,b)=>a.angle-b.angle),canonical=new Map<number,number>();
  for(let i=0;i<n;i++){
    const a=ordered[i],b=ordered[(i+1)%n];requireAsset(a && b,'binding',reference);
    const delta=(b.angle-a.angle+2*Math.PI)%(2*Math.PI);requireAsset(Math.abs(delta-2*Math.PI/n)*radius<=tolerance,'binding',reference);
    canonical.set(a.id,i);const other=rings[1].findIndex(v=>Math.hypot(v.x-a.v.x,v.y-a.v.y)<=tolerance);requireAsset(other!==-1,'binding',reference);canonical.set(256+other,n+i);
  }
  const edges=new Map<string,{count:number;balance:number}>(),bands=Array.from({length:n},()=>({count:0,ids:new Set<number>()})),caps=[0,0];
  for(let t=0;t<count;t+=3){
    const raw=[0,1,2].map(j=>index?.getX(t+j) ?? t+j),ids=raw.map(i=>canonical.get(mapping[i] ?? -1)),points=raw.map(i=>vertices[i]);const [a,b,c]=points;
    requireAsset(ids.every(id=>id!==undefined) && new Set(ids).size===3 && a && b && c,'binding',reference);
    const triangle=new Triangle(a,b,c),normal=triangle.getNormal(new Vector3());requireAsset(triangle.getArea()>1e-12,'binding',reference);
    for(let j=0;j<3;j++){const x=ids[j],y=ids[(j+1)%3];requireAsset(x!==undefined && y!==undefined,'binding',reference);const key=`${Math.min(x,y)}:${Math.max(x,y)}`,edge=edges.get(key) ?? {count:0,balance:0};edge.count++;edge.balance+=x<y ? 1 : -1;edges.set(key,edge);}
    const layer=ids.map(id=>(id ?? -1)<n ? 0 : 1);
    if(layer.every(x=>x===layer[0])){const end=layer[0];requireAsset(end!==undefined && normal.z*(end===0 ? -1 : 1)>.999999,'binding',reference);caps[end]=(caps[end] ?? 0)+1;}
    else {const angles=[...new Set(ids.map(id=>(id ?? -1)%n))].sort((a,b)=>a-b);requireAsset(angles.length===2,'binding',reference);const lo=angles[0],hi=angles[1];requireAsset(lo!==undefined && hi!==undefined && (hi-lo===1 || lo===0 && hi===n-1),'binding',reference);const band=bands[hi-lo===1 ? lo : n-1];requireAsset(band,'binding',reference);band.count++;for(const id of ids)if(id!==undefined)band.ids.add(id);const center=triangle.getMidpoint(new Vector3());requireAsset(normal.x*center.x+normal.y*center.y>0,'binding',reference);}
  }
  requireAsset(caps[0]===n-2 && caps[1]===n-2 && bands.every(b=>b.count===2 && b.ids.size===4) && [...edges.values()].every(e=>e.count===2 && e.balance===0),'binding',reference);
  const maximumGapM=radius*(1-Math.cos(Math.PI/n)),minimumNormalY=Math.cos(Math.PI/n);requireAsset(maximumGapM<=.01+1e-12 && minimumNormalY>=.97,'binding',reference);
  return {vertices:n*2,triangles:count/3,angularVertices:n,maximumGapM,minimumNormalY,closedRegularCylinder:true as const};
}

/** Actual decoded machine triangles must support every registered internal handoff point. */
export function validateFinishingContactSurfaces(asset:Asset,nodes:ReadonlyMap<string,Object3D>) {
  const owner=asset.placement_ids[0]?.replace(/^equipment:/,'') ?? '',sequence=sequenceFor({owner_id:owner,policy_id:asset.motion_policy_id ?? ''}),root=nodes.get(asset.root_node_id);
  requireAsset(root,'binding',`${asset.id}:contact-root`);
  const checks:{socket:string;surface:string;normal:Vector3}[]=[];
  if(sequence && asset.sockets.some(s=>s.id===sequence.strip_socket_id))checks.push({socket:sequence.strip_socket_id,surface:'line_unwinding_mandrel_clamp_jaw',normal:new Vector3(0,-1,0)});
  if(['CS-CR-04','CS-GO-05','CS-NGO-05'].includes(owner) && asset.sockets.some(s=>s.id==='cold_entry_support'))checks.push({socket:'cold_entry_support',surface:'cold_reduction_roll_barrel',normal:new Vector3(0,1,0)});
  return checks.map(check=>{
    const socket=asset.sockets.find(s=>s.id===check.socket),surface=nodes.get(check.surface);
    requireAsset(socket && surface instanceof Mesh,'binding',`${asset.id}:contact-surface:${check.surface}`);
    const host=nodes.get(socket.node_id);requireAsset(host,'binding',check.socket);
    if(check.surface==='line_unwinding_mandrel_clamp_jaw')requireAsset(surface.parent===nodes.get('line_unwinding_mandrel'),'binding',check.surface);
    const point=new Vector3(...socket.transform.position_m).applyMatrix4(host.matrixWorld),position=surface.geometry.getAttribute('position'),index=surface.geometry.index;
    requireAsset(position && position.itemSize===3,'binding',check.surface);
    const count=index?.count ?? position.count;requireAsset(count>0 && count%3===0,'binding',check.surface);
    const desired=check.normal.transformDirection(root.matrixWorld),matches:{gap:number;normal:number;triangle:number}[]=[];
    for(let i=0;i<count;i+=3){
      const vertices=[0,1,2].map(j=>new Vector3().fromBufferAttribute(position,index?.getX(i+j) ?? i+j).applyMatrix4(surface.matrixWorld)),[a,b,c]=vertices;
      requireAsset(a && b && c,'binding',check.surface);
      const triangle=new Triangle(a,b,c),gap=triangle.closestPointToPoint(point,new Vector3()).distanceTo(point),normal=triangle.getNormal(new Vector3()).dot(desired);
      if(gap<=.01+1e-12 && normal>=.97)matches.push({gap,normal,triangle:i/3});
    }
    matches.sort((a,b)=>a.gap-b.gap || a.triangle-b.triangle);const matched=matches[0];requireAsset(matched,'binding',`${asset.id}:contact-triangle:${check.surface}`);
    if(check.surface==='cold_reduction_roll_barrel'){
      const part=asset.moving_parts.find(p=>p.id==='cold_reduction_roll'),pivot=part && nodes.get(part.node_id);requireAsset(pivot && surface.parent===pivot,'binding',check.surface);
      validateCylinderSurface(surface,pivot,.36,1.6,check.surface);
      const local=point.clone().applyMatrix4(pivot.matrixWorld.clone().invert());requireAsset(Math.abs(Math.hypot(local.x,local.y)-.36)<=1e-6 && Math.abs(local.z)<=.6,'binding',check.surface);
    }
    return {socket_id:check.socket,surface_node_id:check.surface,...matched};
  });
}

export function validateInternalFeedGeometry(asset:Asset,nodes:ReadonlyMap<string,Object3D>) {
  validateAssetInternalFeeds(asset);
  validateFinishingContactSurfaces(asset,nodes);
  const root=nodes.get(asset.root_node_id);requireAsset(root,'binding',`${asset.id}:feed-root`);const inverseRoot=root.matrixWorld.clone().invert();
  return (asset.internal_feeds ?? []).map((feed:InternalFeedAsset)=>({feed:feed.id,rollers:feed.rollers.map(r=>{
    const part=asset.moving_parts.find(p=>p.id===r.part_id),surface=nodes.get(r.surface_node_id),pivot=part && nodes.get(part.node_id);requireAsset(part!==undefined && surface instanceof Mesh && pivot && (surface===pivot || surface.parent===pivot),'binding',`${feed.id}:${r.part_id}`);
    const declaredNode=asset.nodes.find(n=>n.id===part.node_id);requireAsset(declaredNode && declaredNode.parent_id!==null && pivot.parent===nodes.get(declaredNode.parent_id),'binding',`${feed.id}:${r.part_id}:decoded-frame`);
    const actual=inverseRoot.clone().multiply(pivot.matrixWorld),expected=equipmentFrame(asset,part.node_id),center=new Vector3(),rotation=new Quaternion(),scale=new Vector3();actual.decompose(center,rotation,scale);
    const expectedRotation=new Quaternion().setFromRotationMatrix(expected);requireAsset(Math.abs(rotation.dot(expectedRotation))>=1-1e-9,'binding',`${feed.id}:${r.part_id}:decoded-frame`);
    requireAsset(center.distanceTo(new Vector3().setFromMatrixPosition(expected))<=tolerance && Math.abs(new Vector3(0,0,1).transformDirection(actual).z)>=1-1e-9 && scale.distanceTo(new Vector3(1,1,1))<=tolerance,'binding',`${feed.id}:${r.part_id}:decoded-frame`);
    return {part_id:r.part_id,...validateCylinderSurface(surface,pivot,r.radius_m,r.width_m,`${feed.id}:${r.part_id}`)};
  })}));
}
