import {describe,it,expect} from 'vitest';
import {BufferGeometry,Float32BufferAttribute,Mesh,Object3D} from 'three';
import {validateCylinderSurface} from './internalFeedGeometry';
function cylinder(n:number,radius=.22,width=2){
  const vertices:number[]=[],indices:number[]=[];
  for(const z of [-width/2,width/2])for(let i=0;i<n;i++){const a=2*Math.PI*i/n;vertices.push(radius*Math.cos(a),radius*Math.sin(a),z);}
  for(let i=0;i<n;i++){const j=(i+1)%n;indices.push(i,j,n+j,i,n+j,n+i);}
  for(let i=1;i<n-1;i++)indices.push(0,i+1,i,n,n+i,n+i+1);
  const g=new BufferGeometry();g.setAttribute('position',new Float32BufferAttribute(vertices,3));g.setIndex(indices);return new Mesh(g);
}
function inspect(mesh:Mesh,r=.22,width=2){const part=new Object3D();part.add(mesh);part.updateMatrixWorld(true);return validateCylinderSurface(mesh,part,r,width,'test-feed:roller');}
describe('actual closed regular polygon cylinder admission',()=>{
  for(const n of [16,32,48])for(const r of [.16,.18,.2,.22,.38,.46])it(`${n} real angular vertices R${r} supports every angle`,()=>{const proof=inspect(cylinder(n,r),r);expect(proof.angularVertices).toBe(n);expect(proof.triangles).toBe(4*n-4);expect(proof.maximumGapM).toBeLessThanOrEqual(.01);expect(proof.minimumNormalY).toBeGreaterThanOrEqual(.97);});
  for(const mode of ['empty','missing-side','missing-cap','wrong-radius','wrong-width','displaced','flipped','duplicate','deformed'] as const)it(`rejects ${mode} actual geometry`,()=>{const mesh=cylinder(16),index=mesh.geometry.index;if(!index)throw Error('Indexed fixture required');
    if(mode==='empty')mesh.geometry.setIndex([]);
    if(mode==='missing-side')mesh.geometry.setIndex(Array.from(index.array).slice(3));
    if(mode==='missing-cap')mesh.geometry.setIndex(Array.from(index.array).slice(0,16*6));
    if(mode==='wrong-radius')mesh.geometry.scale(1.1,1.1,1);
    if(mode==='wrong-width')mesh.geometry.scale(1,1,1.1);
    if(mode==='displaced')mesh.position.x=.02;
    if(mode==='flipped'){const values=Array.from(index.array);[values[0],values[1]]=[values[1] ?? 0,values[0] ?? 0];mesh.geometry.setIndex(values);}
    if(mode==='duplicate')mesh.geometry.setIndex([...index.array,...index.array.slice(0,3)]);
    if(mode==='deformed'){const p=mesh.geometry.getAttribute('position');p.setX(3,p.getX(3)+.03);}
    expect(()=>inspect(mesh)).toThrow('binding: test-feed:roller');
  });
  it('rejects radius/N violating continuous one-centimetre gap',()=>expect(()=>inspect(cylinder(16,.6),.6)).toThrow('binding:'));
  it('rejects a plate with advertised circular bounds',()=>{const mesh=cylinder(16);mesh.geometry.scale(1,0,1);expect(()=>inspect(mesh)).toThrow('binding:');});
});

// Metadata and decoded frame checks are separate from part-local cylinder topology.
import {Quaternion,Vector3} from 'three';
import {assetManifestShape} from './manifestShape';
import {equipmentExample} from './manifestTestFixtures';
import {validateAssetInternalFeeds,validateInternalFeedGeometry} from './internalFeedGeometry';
function feedRig(rest:Quaternion=new Quaternion()){
  const raw=equipmentExample('variant:roughing:CS-HR-03'),base=raw.assets[0];if(!base)throw Error('Asset seed absent');const source=base.moving_parts[0],template=base.nodes.find(n=>n.id===source?.node_id);if(!source || !template)throw Error('Canonical node absent');
  const node=(id:string,parent_id:string,position_m:number[],q:number[])=>({...template,id,parent_id,locator:`root/${id}`,transform:{position_m,rotation_xyzw:q}});
  const part=(id:string,x:number,driver:boolean)=>({...source,id,node_id:id,function:source.function,role:'operational',motion:'rotation',axis:[0,0,-1],pivot_m:[x,1.1,0],range:{min:0,max:4,rest:0,unit:'rad'},binding:driver ? {type:'clip',clock:'server_sim',phase:'work',progress_source:'server_phase_progress',pause:'hold',fault:'hold',rest:'range_rest',clip_id:'feed-test'} : {type:'mechanical_follower',driver_part_id:'driver',ratio:1}});
  const rootNode=base.nodes.find(n=>n.id==='root');if(!rootNode)throw Error('Root absent');
  const manifest=assetManifestShape.parse({...raw,assets:[{...base,nodes:[rootNode,node('driver','root',[-1,1.1,0],[0,0,0,1]),node('following','root',[1,1.1,0],rest.toArray()),node('driver-surface','driver',[0,0,0],[0,0,0,1]),node('following-surface','following',[0,0,0],[0,0,0,1])],sockets:[{...base.sockets[0],id:'work',node_id:'root',transform:{position_m:[0,1.32,0],rotation_xyzw:[0,0,0,1]}}],moving_parts:[part('driver',-1,true),part('following',1,false)],internal_feeds:[{schema_version:1,id:'internal-feed:test',kind:'linear_roller_feed',custody_socket_id:'work',driver_part_id:'driver',start_m:[-.44,1.32,0],end_m:[.44,1.32,0],rollers:[{part_id:'driver',surface_node_id:'driver-surface',radius_m:.22,width_m:2},{part_id:'following',surface_node_id:'following-surface',radius_m:.22,width_m:2}]}]}]});const asset=manifest.assets[0];if(!asset)throw Error('Typed asset absent');
  const root=new Object3D(),driver=new Object3D(),following=new Object3D(),a=cylinder(16),b=cylinder(16);driver.position.set(-1,1.1,0);following.position.set(1,1.1,0);following.quaternion.copy(rest);driver.add(a);following.add(b);root.add(driver,following);root.updateMatrixWorld(true);const nodes=new Map([['root',root],['driver',driver],['following',following],['driver-surface',a],['following-surface',b]]);return {asset,nodes,root,following};
}
it('rejects tilted metadata rest barrel despite declared -Z scalar rotation',()=>{const rig=feedRig(new Quaternion().setFromAxisAngle(new Vector3(1,0,0),Math.PI/2));expect(()=>validateAssetInternalFeeds(rig.asset)).toThrow('barrel-axis');});
for(const mode of ['axis','center','scale'] as const)it(`rejects decoded-only ${mode} frame mismatch`,()=>{const rig=feedRig();if(mode==='axis')rig.following.rotateX(Math.PI/2);if(mode==='center')rig.following.position.x+=.02;if(mode==='scale')rig.following.scale.setScalar(1.01);rig.root.updateMatrixWorld(true);expect(()=>validateInternalFeedGeometry(rig.asset,rig.nodes)).toThrow('decoded-frame');});
for(const rest of [new Quaternion().setFromAxisAngle(new Vector3(1,0,0),Math.PI),new Quaternion().setFromAxisAngle(new Vector3(0,0,1),.37)])it(`accepts parallel barrel rest ${rest.toArray().join(',')}`,()=>{const rig=feedRig(rest);expect(validateInternalFeedGeometry(rig.asset,rig.nodes)).toHaveLength(1);});
it('keeps geometry admission relative to equipment root under owner yaw and translation',()=>{const rig=feedRig();rig.root.position.set(12,0,7);rig.root.rotateY(.7);rig.root.updateMatrixWorld(true);expect(validateInternalFeedGeometry(rig.asset,rig.nodes)).toHaveLength(1);});

function liftedRig(mode='valid'){
  const seed=feedRig(),source=seed.asset,first=source.moving_parts[0];if(!first)throw Error('Driver required');
  const driver='strip_feed',lift='line_feed_lift';
  const liftPart={...first,id:lift,node_id:lift,function:lift,motion:'translation',axis:mode==='axis' ? [0,-1,0] : [0,1,0],pivot_m:[0,0,0],range:{min:-.02,max:mode==='max' ? .01 : 0,rest:mode==='rest' ? -.01 : 0,unit:'m'}};
  const liftNode={id:lift,parent_id:'root',locator:'root/line_feed_lift',transform:{position_m:[0,0,0],rotation_xyzw:[0,0,0,1]}};
  const nodes=source.nodes.map(node=>({...node,id:node.id==='driver' ? driver : node.id,parent_id:node.parent_id==='driver' ? driver : ['driver','following'].includes(node.id) ? (mode==='ancestry' && node.id==='following' ? 'root' : lift) : node.parent_id}));
  const parts=source.moving_parts.map(part=>({...part,id:part.id==='driver' ? driver : part.id,node_id:part.node_id==='driver' ? driver : part.node_id,function:driver,binding:part.binding.type==='mechanical_follower' ? {...part.binding,driver_part_id:driver} : part.binding}));
  const feeds=source.internal_feeds?.map(feed=>({...feed,driver_part_id:driver,...(mode==='omitted' ? {} : {support_lift_part_id:mode==='unknown' ? 'absent' : lift}),rollers:feed.rollers.map(r=>({...r,part_id:r.part_id==='driver' ? driver : r.part_id}))}));
  const candidate={...source,motion_policy_id:'policy:equipment:finishing:CS-CR-05:v1',placement_ids:[mode==='owner' ? 'equipment:CS-GI-05' : 'equipment:CS-CR-05'],nodes:[...nodes,liftNode],moving_parts:[...parts,liftPart],internal_feeds:feeds};
  if(mode==='kind')Reflect.set(liftPart,'motion','rotation');
  const asset=assetManifestShape.parse({schema_version:1,purpose:'contract_example',assets:[candidate]}).assets[0];if(!asset)throw Error('Asset required');
  const driverNode=seed.nodes.get('driver'),following=seed.nodes.get('following');if(!driverNode || !following)throw Error('Physical roller required');
  const liftObject=new Object3D();seed.root.add(liftObject);liftObject.add(driverNode,following);seed.root.updateMatrixWorld(true);
  const actual=new Map(seed.nodes);actual.delete('driver');actual.set(driver,driverNode);actual.set(lift,liftObject);
  return {asset,nodes:actual,lift:liftObject,root:seed.root,following};
}
it('accepts real feed participants under their registered rest lift',()=>{const rig=liftedRig();expect(validateInternalFeedGeometry(rig.asset,rig.nodes)).toHaveLength(1);});
for(const mode of ['omitted','unknown','owner','kind','axis','max','rest','ancestry'])it(`rejects registered lift metadata ${mode}`,()=>expect(()=>validateAssetInternalFeeds(liftedRig(mode).asset)).toThrow('binding:'));
it('rejects a lowered decoded lift even with falsely advertised zero rest metadata',()=>{const rig=liftedRig();rig.lift.position.y=-.02;rig.root.updateMatrixWorld(true);expect(()=>validateInternalFeedGeometry(rig.asset,rig.nodes)).toThrow('decoded-frame');});
it('rejects a decoded-only extra rotating ancestor of an otherwise valid feeder',()=>{const rig=liftedRig(),other=new Object3D();other.rotateX(.04);rig.lift.add(other);other.add(rig.following);rig.root.updateMatrixWorld(true);expect(()=>validateInternalFeedGeometry(rig.asset,rig.nodes)).toThrow('decoded-frame');});

it('rejects an undeclared identity ancestor even without a geometric displacement',()=>{const rig=liftedRig(),other=new Object3D();rig.lift.add(other);other.add(rig.following);rig.root.updateMatrixWorld(true);expect(()=>validateInternalFeedGeometry(rig.asset,rig.nodes)).toThrow('decoded-frame');});
it('rejects a decoded-only roller spin while retaining valid parallel-axis rest authoring',()=>{const rig=feedRig();rig.following.rotateZ(.04);rig.root.updateMatrixWorld(true);expect(()=>validateInternalFeedGeometry(rig.asset,rig.nodes)).toThrow('decoded-frame');});
