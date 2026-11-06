import { useEffect, useMemo } from 'react';
import { BoxGeometry, BufferGeometry, Float32BufferAttribute, IcosahedronGeometry, LatheGeometry, Triangle, Vector2, Vector3 } from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import type { MotionPose } from '../../../src/operations/scene/motion/contracts';

function mergeBulk(chunks:readonly BufferGeometry[]){
  const compatible=chunks.map(geometry=>{if(!geometry.index)return geometry;const flat=geometry.toNonIndexed();geometry.dispose();return flat;});
  const merged=mergeGeometries(compatible);compatible.forEach(geometry=>geometry.dispose());
  if(!merged)throw new RangeError('Tracked bulk geometry merge failed');return merged;
}

export function pile(width:number,height:number){
  const chunks:BufferGeometry[]=[new BoxGeometry(width,.015,width).translate(0,-height/2+.0075,0)];
  for(let i=0;i<22;i++){
    const angle=i*2.399963,ring=Math.sqrt(i/22)*width*.36,radius=width*(.075+(i%4)*.014);
    const chunk=new IcosahedronGeometry(radius,1);chunk.rotateX(i*.37);chunk.rotateZ(i*.61);
    chunk.translate(Math.cos(angle)*ring,-height/2+.08+height*.45*(1-ring/(width*.5)),Math.sin(angle)*ring);chunks.push(chunk);
  }
  return mergeBulk(chunks);
}

export function chargingScrap(progress:number,width:number,height:number){
  const floor=-height/2,t=(progress-.25)/.125,chunks:BufferGeometry[]=[new BoxGeometry(width,.015,width).translate(0,floor+.0075,0)];
  for(let i=0;i<32;i++){
    const angle=i*2.399963,radius=.045+(i%3)*.012,fall=(t*1.8+i/32)%1;
    const deposited=i/32<t*.7,grain=new IcosahedronGeometry(radius,1);grain.rotateX(i*.41);grain.rotateZ(i*.83);
    grain.translate(Math.cos(angle)*width*(deposited ? .32 : .18),floor+(deposited ? .06+t*.25 : .15+(1-fall)*(height-.3)),Math.sin(angle)*width*(deposited ? .32 : .18));chunks.push(grain);
  }
  return mergeBulk(chunks);
}

export function strand(width:number,height:number,progress:number,origin:readonly number[]){
  const ox=origin[0],oy=origin[1],oz=origin[2];if(ox===undefined||oy===undefined||oz===undefined)throw new RangeError('Material origin missing');
  const points:{readonly p:Vector3;readonly normal:Vector3}[]=[];
  for(let i=0;i<=32;i++){const a=i/32*Math.PI/2;points.push({p:new Vector3(.1-3.65*Math.cos(a),4.98+height/2-3.65*Math.sin(a),0),normal:new Vector3(Math.cos(a),Math.sin(a),0)});}
  for(const x of [.5,1.6,2.4,3+progress*1.7])points.push({p:new Vector3(x,1.33+height/2,0),normal:new Vector3(0,1,0)});
  const vertices:number[]=[],indices:number[]=[];
  points.forEach(({p,normal},i)=>{
    for(const [side,z] of [[-1,-width/2],[1,-width/2],[1,width/2],[-1,width/2]]){if(side===undefined||z===undefined)throw new RangeError('Strand section missing');vertices.push(p.x+normal.x*side*height/2-ox,p.y+normal.y*side*height/2-oy,z-oz);}
    if(i>0)for(let j=0;j<4;j++){const a=(i-1)*4+j,b=(i-1)*4+(j+1)%4,c=i*4+(j+1)%4,d=i*4+j;indices.push(a,b,c,a,c,d);}
  });
  indices.push(0,2,1,0,3,2);const end=(points.length-1)*4;indices.push(end,end+1,end+2,end,end+2,end+3);
  const geometry=new BufferGeometry();geometry.setAttribute('position',new Float32BufferAttribute(vertices,3));geometry.setIndex(indices);geometry.computeVertexNormals();return geometry;
}

/** The lathe's axis endpoints close the floor without emitting zero-area polar faces. */
export function carrierGeometry(){
  const geometry=new LatheGeometry([new Vector2(0,0),new Vector2(1.2,0),new Vector2(1.5,2.45),new Vector2(1.3,2.45),new Vector2(1.04,.34),new Vector2(0,.34)],48);
  const positions=geometry.getAttribute('position'),index=geometry.index;
  if(!index)throw new RangeError('Indexed carrier geometry required');
  const indices:number[]=[];
  for(let i=0;i<index.count;i+=3){
    const a=index.getX(i),b=index.getX(i+1),c=index.getX(i+2);
    const triangle=new Triangle(new Vector3().fromBufferAttribute(positions,a),new Vector3().fromBufferAttribute(positions,b),new Vector3().fromBufferAttribute(positions,c));
    if(triangle.getArea()>0)indices.push(a,b,c);
  }
  geometry.setIndex(indices);return geometry;
}

/** A transport ladle is an independent fixture carrier, never baked into the LF machine asset. */
export function FixtureCarrier({kind}:{readonly kind:string}){
  const geometry=useMemo(carrierGeometry,[]);
  useEffect(()=>()=>geometry.dispose(),[geometry]);
  if(kind!=='ladle_furnace')return null;
  return <group name="fixture-carrier:LF-A:ladle" position={[0,.8,0]} userData={{fixtureCarrier:true,ownerId:'fixture:ladle:LF-A',synthetic:true}}>
    <mesh geometry={geometry} castShadow><meshStandardMaterial color="#638f94" roughness={.72} metalness={.12} side={2}/></mesh>
    {[-1,1].map(z=><mesh key={z} position={[0,1.65,z*1.48]} rotation={[Math.PI/2,0,0]}><cylinderGeometry args={[.17,.17,.45,24]}/><meshStandardMaterial color="#aeb8bb" metalness={.9} roughness={.38}/></mesh>)}
  </group>;
}

/** One business material mesh, whose form comes from the admitted synthetic snapshot. */
export function MaterialEntity({pose,kind,progress}:{readonly pose:MotionPose;readonly kind:string;readonly progress:number}){
  const d=pose.material.dimensions,form=pose.material.form,width=(d.width_mm??700)/1000,height=(d.thickness_mm??150)/1000;
  const charging=kind==='eaf'&&progress>=.25&&progress<.375;
  const geometry=useMemo(()=>charging ? chargingScrap(progress,width,height) : form==='ORE'||form==='SCRAP' ? pile(width,height) : kind==='caster'&&form!=='LIQUID_STEEL' ? strand(width,height,progress,pose.position_m) : null,[form,width,height,kind,progress,pose.position_m,charging]);
  useEffect(()=>()=>geometry?.dispose(),[geometry]);
  const liquid=form==='HOT_METAL'||form==='LIQUID_STEEL';
  return <mesh name={`material:${pose.material.material_id}`} position={[...pose.position_m]} quaternion={[...pose.orientation_xyzw]} castShadow userData={{poseMaterial:true,materialId:pose.material.material_id,attachmentId:pose.attachment_id,versionId:pose.material.material_version_id,form,synthetic:true}}>
    {geometry ? <primitive object={geometry} attach="geometry"/> : liquid ? <cylinderGeometry args={[width/2,width/2,height,48]}/> : <boxGeometry args={[(d.length_mm??2400)/1000,height,width]}/>}
    <meshStandardMaterial color={liquid ? '#ff581c' : form==='ORE' ? '#63513c' : '#aeb8bb'} metalness={liquid ? .45 : .9} roughness={liquid ? .32 : .38} emissive={liquid ? '#b3290c' : '#000000'} emissiveIntensity={liquid ? .7 : 0}/>
  </mesh>;
}
