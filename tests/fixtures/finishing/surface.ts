import {Mesh,Triangle,Vector3} from 'three';
import type {Object3D} from 'three';

export function contactSurfaces(root:Object3D,point:Vector3,expected:Vector3){
  let nearest=Infinity;const candidates:{distance:number;normal:number[];alignment:number;mesh:string;triangle:number;vertices:number[][]}[]=[];
  root.traverse(node=>{if(!(node instanceof Mesh))return;if(node.geometry.boundingBox===null)node.geometry.computeBoundingBox();const bounds=node.geometry.boundingBox?.clone().applyMatrix4(node.matrixWorld);if(!bounds||bounds.distanceToPoint(point)>.03)return;const p=node.geometry.getAttribute('position'),index=node.geometry.index;
    for(let i=0;i<(index?.count??p.count);i+=3){const a=new Vector3().fromBufferAttribute(p,index?.getX(i)??i).applyMatrix4(node.matrixWorld),b=new Vector3().fromBufferAttribute(p,index?.getX(i+1)??i+1).applyMatrix4(node.matrixWorld),c=new Vector3().fromBufferAttribute(p,index?.getX(i+2)??i+2).applyMatrix4(node.matrixWorld),t=new Triangle(a,b,c);if(t.getArea()<1e-14)continue;const distance=t.closestPointToPoint(point,new Vector3()).distanceTo(point),normal=t.getNormal(new Vector3());nearest=Math.min(nearest,distance);if(distance<=.03)candidates.push({distance,normal:normal.toArray(),alignment:normal.dot(expected),mesh:node.name,triangle:i/3,vertices:[a.toArray(),b.toArray(),c.toArray()]});}
  });
  const closest=candidates.filter(c=>c.distance<=nearest+1e-6),aligned=candidates.filter(c=>c.alignment>=.97).sort((a,b)=>a.distance-b.distance)[0];return {nearestDistanceM:Number.isFinite(nearest)?nearest:null,nearestSurfaces:closest,aligned:aligned??null};
}

export function actualMeshStats(mesh:Mesh){
  const p=mesh.geometry.getAttribute('position'),index=mesh.geometry.index,parent=Array.from({length:p.count},(_,i)=>i),positions=new Map<string,number>();
  const root=(i:number):number=>{let value=i;while(parent[value]!==value){const next=parent[value];if(next===undefined)throw new RangeError('Topology node absent');value=next;}return value;};
  for(let i=0;i<p.count;i++){const key=[p.getX(i),p.getY(i),p.getZ(i)].map(v=>v.toFixed(8)).join(':'),other=positions.get(key);if(other===undefined)positions.set(key,i);else parent[root(i)]=root(other);}
  let volume=0;const origin=new Vector3().fromBufferAttribute(p,0);
  for(let i=0;i<(index?.count??p.count);i+=3){const a=index?.getX(i)??i,b=index?.getX(i+1)??i+1,c=index?.getX(i+2)??i+2;parent[root(b)]=root(a);parent[root(c)]=root(a);const av=new Vector3().fromBufferAttribute(p,a).sub(origin),bv=new Vector3().fromBufferAttribute(p,b).sub(origin),cv=new Vector3().fromBufferAttribute(p,c).sub(origin);volume+=av.dot(bv.cross(cv))/6;}
  return {vertices:p.count,triangles:(index?.count??p.count)/3,components:new Set(parent.map((_,i)=>root(i))).size,signedVolumeM3:volume,volumeM3:Math.abs(volume),matrixWorld:mesh.matrixWorld.toArray(),worldVertices:Array.from({length:p.count},(_,i)=>new Vector3().fromBufferAttribute(p,i).applyMatrix4(mesh.matrixWorld).toArray())};
}

/** Bounds only prune; every returned intrusion contains its actual triangle. */
export function rigidClearance(root:Object3D,body:Mesh){
  if(body.geometry.type!=='BoxGeometry')return null;body.geometry.computeBoundingBox();const box=body.geometry.boundingBox?.clone();if(!box)throw new RangeError('Rigid solid absent');box.min.addScalar(1e-5);box.max.addScalar(-1e-5);const inverse=body.matrixWorld.clone().invert(),hits:{mesh:string;triangle:number;worldVertices:number[][]}[]=[];let tested=0;
  root.traverse(node=>{if(!(node instanceof Mesh)||node.userData.process_medium===true)return;if(node.geometry.boundingBox===null)node.geometry.computeBoundingBox();const matrix=inverse.clone().multiply(node.matrixWorld),bounds=node.geometry.boundingBox?.clone().applyMatrix4(matrix);if(!bounds||!box.intersectsBox(bounds))return;const p=node.geometry.getAttribute('position'),index=node.geometry.index;for(let i=0;i<(index?.count??p.count);i+=3){const vertices=[0,1,2].map(j=>new Vector3().fromBufferAttribute(p,index?.getX(i+j)??i+j).applyMatrix4(matrix)),[a,b,c]=vertices;if(!a||!b||!c)throw new RangeError('Solid triangle absent');tested++;if(box.intersectsTriangle(new Triangle(a,b,c)))hits.push({mesh:node.name,triangle:i/3,worldVertices:vertices.map(v=>v.applyMatrix4(body.matrixWorld).toArray())});}});return {method:'actual triangle versus shrunken rendered solid SAT',interiorToleranceM:1e-5,testedTriangles:tested,hits};
}
