import {Mesh,Ray,Triangle,Vector3} from 'three';
import type {Object3D} from 'three';
type Point=readonly[number,number,number];
type Face=readonly[Point,Point,Point];
export type MeshFrame={readonly id:string;readonly triangles:readonly Face[]};
export function decodedFrames(roots:readonly Object3D[],origin:Point):readonly MeshFrame[]{
  const result:MeshFrame[]=[];
  for(const root of roots){root.updateMatrixWorld(true);root.traverse(node=>{if(!(node instanceof Mesh)||String(node.userData.semantic_id).startsWith('axis_'))return;const p=node.geometry.getAttribute('position'),index=node.geometry.index,count=index?.count??p.count,triangles:Face[]=[];
    for(let i=0;i<count;i+=3){const points=[0,1,2].map(j=>new Vector3().fromBufferAttribute(p,index?index.getX(i+j):i+j).applyMatrix4(node.matrixWorld).sub(new Vector3(...origin)));const [a,b,c]=points;if(!a||!b||!c)throw new RangeError('Decoded triangle incomplete');triangles.push([[a.x,a.y,a.z],[b.x,b.y,b.z],[c.x,c.y,c.z]]);}
    result.push({id:root.name+':'+node.name,triangles});
  });}return result;
}
function cross(a:Point,b:Point,c:Point):number{return(b[1]-a[1])*(c[2]-a[2])-(b[2]-a[2])*(c[1]-a[1]);}
function radialRange(points:readonly Point[]):readonly[number,number]{
  const sorted=[...points].sort((a,b)=>a[1]-b[1]||a[2]-b[2]),lower:Point[]=[],upper:Point[]=[];
  for(const p of sorted){while(lower.length>1){const a=lower.at(-2),b=lower.at(-1);if(!a||!b||cross(a,b,p)>0)break;lower.pop();}lower.push(p);}
  for(const p of sorted.reverse()){while(upper.length>1){const a=upper.at(-2),b=upper.at(-1);if(!a||!b||cross(a,b,p)>0)break;upper.pop();}upper.push(p);}
  const hull=[...lower.slice(0,-1),...upper.slice(0,-1)];if(!hull.length)throw new RangeError('Empty projected hull');let min=Infinity,max=0,positive=false,negative=false;
  for(let i=0;i<hull.length;i++){const a=hull[i],b=hull[(i+1)%hull.length];if(!a||!b)throw new RangeError('Projected hull incomplete');max=Math.max(max,Math.hypot(a[1],a[2]));const dy=b[1]-a[1],dz=b[2]-a[2],denom=dy*dy+dz*dz,t=denom?Math.max(0,Math.min(1,-(a[1]*dy+a[2]*dz)/denom)):0;min=Math.min(min,Math.hypot(a[1]+t*dy,a[2]+t*dz));const sign=a[1]*b[2]-a[2]*b[1];if(sign>1e-12)positive=true;if(sign< -1e-12)negative=true;}
  if(hull.length>=3&&positive!==negative)min=0;return[min,max];
}
function intersectsAnnulus(points:readonly Point[]):boolean{
  if(Math.max(...points.map(p=>p[0]))<=-.5+1e-6||Math.min(...points.map(p=>p[0]))>=.5-1e-6)return false;
  const inside:Point[]=points.filter(p=>p[0]>=-.5&&p[0]<=.5);
  for(let i=0;i<points.length;i++)for(let j=i+1;j<points.length;j++){const a=points[i],b=points[j];if(!a||!b)throw new RangeError('Prism incomplete');for(const x of [-.5,.5])if((a[0]<x&&b[0]>x)||(a[0]>x&&b[0]<x)){const t=(x-a[0])/(b[0]-a[0]);inside.push([x,a[1]+t*(b[1]-a[1]),a[2]+t*(b[2]-a[2])]);}}
  if(!inside.length)return false;const [min,max]=radialRange(inside);return min<.6-1e-6&&max>.3+1e-6;
}
function contains(face:readonly Face[],point:Point):boolean{
  const probe=new Vector3(...point),ray=new Ray(probe,new Vector3(.93231,.24717,.26419).normalize()),hits:number[]=[];
  for(const f of face){const t=new Triangle(...f.map(p=>new Vector3(...p)));if(t.closestPointToPoint(probe,new Vector3()).distanceTo(probe)<1e-6)return false;const hit=ray.intersectTriangle(t.a,t.b,t.c,false,new Vector3());if(hit){const distance=hit.distanceTo(probe);if(distance>1e-6&&!hits.some(d=>Math.abs(d-distance)<1e-7))hits.push(distance);}}
  return hits.length%2===1;
}
/** A triangle translated linearly sweeps the exact convex prism of its endpoints.
 * Clip that prism to the finite coil width, then conservatively test its complete
 * radial interval against the annulus. No temporal sample can miss an intrusion.
 * This is source-only rigid/linear proof; changing rotations rejects this method.
 */
export function continuousCoilSweep(before:readonly MeshFrame[],after:readonly MeshFrame[]):{readonly triangles:number;readonly hits:readonly{readonly mesh:string;readonly triangle:number;readonly kind:string}[]}{
  if(before.length!==after.length)throw new RangeError('Mesh universe changed');const hits:{mesh:string;triangle:number;kind:string}[]=[];let triangles=0;
  for(let i=0;i<before.length;i++){const a=before[i],b=after[i];if(!a||!b||a.id!==b.id||a.triangles.length!==b.triangles.length)throw new RangeError('Source topology changed');
    for(let j=0;j<a.triangles.length;j++){const p=a.triangles[j],q=b.triangles[j];if(!p||!q)throw new RangeError('Source face missing');const delta=new Vector3(...q[0]).sub(new Vector3(...p[0]));for(const k of [1,2]){const start=p[k],end=q[k];if(!start||!end||new Vector3(...end).sub(new Vector3(...start)).distanceTo(delta)>1e-5)throw new RangeError('Non-affine/rotated geometry requires another sweep law');}if(intersectsAnnulus([...p,...q]))hits.push({mesh:a.id,triangle:j,kind:'continuous-triangle-prism'});triangles++;}
    if(contains(a.triangles,[0,.45,0])||contains(b.triangles,[0,.45,0]))hits.push({mesh:a.id,triangle:-1,kind:'material-solid-point-inside-closed-machine'});
  }return{triangles,hits};
}
