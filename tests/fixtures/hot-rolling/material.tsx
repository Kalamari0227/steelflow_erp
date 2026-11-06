import { useEffect, useMemo, useState } from 'react';
import { BufferGeometry, CurvePath, LineCurve3, Float32BufferAttribute, TubeGeometry, Vector3 } from 'three';
import { requireAsset } from '../../../src/operations/scene/assets/errors';
import type { MotionPose } from '../../../src/operations/scene/motion/contracts';

export function woundStrip(progress: number, width: number, thickness: number) {
  const radius=.44+thickness/2,angle=progress*Math.PI*2,growth=(thickness+.0002)*progress;
  const spiral:Vector3[]=[],segments=Math.max(1,Math.ceil(angle*128));
  for(let i=0;i<=segments;i++){
    if(angle===0 && i>0)break;
    const t=i/segments,a=-Math.PI/2+angle*t,r=radius+growth*(1-t);
    spiral.push(new Vector3(.7+r*Math.cos(a),radius+r*Math.sin(a),0));
  }
  const lead=Array.from({length:41},(_,i)=>{const x=.3+.4*i/40,t=Math.max(0,(x-.4)/.3);return new Vector3(x,-growth*(1-Math.cos(Math.PI*t))/2,0);});
  const length=(path:readonly Vector3[])=>path.slice(1).reduce((sum,p,i)=>sum+p.distanceTo(path[i]!),0);
  const flatLength=4-length(spiral)-length(lead);requireAsset(flatLength>0,'binding','Original four metre strip retains a visible incoming tail');
  const path=[...Array.from({length:20},(_,i)=>new Vector3(.3-flatLength+flatLength*i/20,0,0)),...lead.slice(0,-1),...spiral];
  const vertices:number[]=[],indices:number[]=[];
  for(let i=0;i<path.length;i++){
    const p=path[i],a=path[Math.max(0,i-1)],b=path[Math.min(path.length-1,i+1)];if(!p||!a||!b)throw new Error('Authored strip sample missing');
    const before=(i===0?b.clone().sub(p):p.clone().sub(a)).normalize(),after=(i===path.length-1?p.clone().sub(a):b.clone().sub(p)).normalize();
    const previousNormal=new Vector3(-before.y,before.x,0),normal=previousNormal.clone().add(new Vector3(-after.y,after.x,0)).normalize();
    normal.multiplyScalar(thickness/(2*normal.dot(previousNormal)));
    for(const [side,z]of[[-1,-width/2],[1,-width/2],[1,width/2],[-1,width/2]]){if(side===undefined||z===undefined)throw new Error('Strip profile missing');vertices.push(p.x+normal.x*side,p.y+normal.y*side,z);}
    if(i>0)for(let j=0;j<4;j++){const n=i*4+j,m=i*4+(j+1)%4;indices.push(n-4,m-4,m,n-4,m,n);}
  }
  indices.push(0,2,1,0,3,2);const last=(path.length-1)*4;indices.push(last,last+1,last+2,last,last+2,last+3);
  const geometry=new BufferGeometry();geometry.setAttribute('position',new Float32BufferAttribute(vertices,3));geometry.setIndex(indices);geometry.computeVertexNormals();
  geometry.userData={syntheticCenterlineLengthM:length(path),originalLengthM:4,widthM:width,thicknessM:thickness,remainingFlatTailM:flatLength};return geometry;
}

export function laidWire(progress:number) {
  const rotation=progress*Math.PI*5,cos=Math.cos(rotation),sin=Math.sin(rotation);
  const points=[new Vector3(-2,0,0),new Vector3(-.2,0,0),new Vector3(-.07,0,0)];
  for(let i=1;i<=8;i++){const a=-Math.PI/2+i*Math.PI/16;points.push(new Vector3(-.07+.12*Math.cos(a),.12+.12*Math.sin(a),0));}
  points.push(new Vector3(.05,.50,0),new Vector3(.18,.77,0),new Vector3(.40,.95,0),new Vector3(1.04,.95,0));
  for (const p of [[-.15,0,0],[.3,0,.1],[.65,-.22,.42],[.9,-.25,.64],[1.25,-.32,.75]]) {
    const x=p[0] ?? 0,y=p[1] ?? 0,z=p[2] ?? 0;
    points.push(new Vector3(1.2+x,.95+y*cos-z*sin,y*sin+z*cos));
  }
  const turns=.2+progress*2.5,last=Math.ceil(turns*80);
  const tip=points.at(-1);if (!tip) throw new Error('Actual laying pipe outlet absent');
  const topAngle=Math.PI+last*Math.PI*2/80,top=new Vector3(4+.9*Math.cos(topAngle),last/80*.065,.9*Math.sin(topAngle));
  const approachY=Math.max(tip.y+.10,top.y+.15);
  points.push(new Vector3(2.8,approachY,tip.z),new Vector3(top.x,approachY,top.z));
  for(let i=last;i>=0;i--){const angle=Math.PI+i*Math.PI*2/80;points.push(new Vector3(4+.9*Math.cos(angle),i/80*.065,.9*Math.sin(angle)));}
  const path=new CurvePath<Vector3>();
  for(let i=1;i<points.length;i++){const a=points[i-1],b=points[i];if(!a || !b)throw new Error('Material path segment missing');path.add(new LineCurve3(a,b));}
  const geometry=new TubeGeometry(path,400,.03,32,false),position=geometry.getAttribute('position'),vertices=Array.from(position.array),indices=Array.from(geometry.index?.array ?? []);
  for(const end of [0,1]){
    const base=end*400*33,center=new Vector3();for(let j=0;j<32;j++)center.add(new Vector3().fromBufferAttribute(position,base+j));center.multiplyScalar(1/32);
    const centerId=vertices.length/3;vertices.push(...center.toArray());const outward=path.getTangent(end).multiplyScalar(end===0?-1:1);
    for(let j=0;j<32;j++){const a=base+j,b=base+(j+1)%32,normal=new Vector3().fromBufferAttribute(position,a).sub(center).cross(new Vector3().fromBufferAttribute(position,b).sub(center));indices.push(centerId,...(normal.dot(outward)>0?[a,b]:[b,a]));}
  }
  geometry.setAttribute('position',new Float32BufferAttribute(vertices,3));geometry.setIndex(indices);geometry.deleteAttribute('normal');geometry.deleteAttribute('uv');geometry.computeVertexNormals();return geometry;
}

/** One business material mesh. Geometry deforms; custody and entity identity remain singular. */
export function MaterialEntity({pose,kind,feed,heat,formingRange}:{readonly pose:MotionPose;readonly kind:string;readonly feed:number;readonly heat:number;readonly formingRange?:{readonly function:string;readonly min:number;readonly max:number}}) {
  const [selected,setSelected]=useState(true),d=pose.material.dimensions;
  const winding=pose.channels.find(c => c.function_id===formingRange?.function);
  if(kind==='coiler' || kind==='laying_head') requireAsset(winding && formingRange && formingRange.max>formingRange.min,'binding','canonical winding scalar/range');
  const mechanismProgress=(kind==='coiler' || kind==='laying_head') && winding && formingRange ? (winding.value-formingRange.min)/(formingRange.max-formingRange.min) : feed;
  const geometry=useMemo(() => kind==='coiler' ? woundStrip(mechanismProgress,(d.width_mm ?? 1200)/1000,(d.thickness_mm ?? 12)/1000) : kind==='laying_head' ? laidWire(mechanismProgress) : null,[kind,feed,mechanismProgress,d.width_mm,d.thickness_mm]);
  useEffect(() => () => geometry?.dispose(),[geometry]);
  return <mesh name={`material:${pose.material.material_id}`} castShadow userData={{poseMaterial:true,materialId:pose.material.material_id,attachmentId:pose.attachment_id,versionId:pose.material.material_version_id,contact:pose.contact_m,mechanismProgress,syntheticStripLengthM:kind==='coiler' ? 4 : null,selected}} position={[...pose.position_m]} quaternion={[...pose.orientation_xyzw]} onClick={event => {event.stopPropagation();setSelected(v => !v);}}>
    {geometry ? <primitive object={geometry} attach="geometry" /> : <boxGeometry args={[(d.length_mm ?? 1000)/1000,(d.thickness_mm ?? 100)/1000,(d.width_mm ?? 500)/1000]} />}
    <meshStandardMaterial color={heat ? '#dd793d' : '#6c7f85'} metalness={.65} roughness={.46} emissive={heat ? '#702000' : selected ? '#10232a' : '#000000'} emissiveIntensity={.2} />
  </mesh>;
}
