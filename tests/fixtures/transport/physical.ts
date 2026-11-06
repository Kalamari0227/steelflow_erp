import {Mesh,Triangle,Vector3,Matrix4} from 'three';
import type {Object3D} from 'three';
type Point=readonly[number,number,number];
export type Surface={readonly distance:number;readonly mesh:string;readonly triangle:number;readonly normal:readonly number[];readonly vertices:readonly(readonly number[])[]};
/** Inspect actual decoded triangle surfaces, never source-provided pass metadata. */
export function surface(root:Object3D,point:Point,expected:Point):Surface{
  const probe=new Vector3(...point),normal=new Vector3(...expected);let result:Surface={distance:Infinity,mesh:'',triangle:-1,normal:[],vertices:[]};
  root.updateMatrixWorld(true);root.traverse(node=>{if(!(node instanceof Mesh))return;const p=node.geometry.getAttribute('position'),index=node.geometry.index,count=index?.count??p.count;for(let i=0;i<count;i+=3){const t=new Triangle(...[0,1,2].map(j=>new Vector3().fromBufferAttribute(p,index?index.getX(i+j):i+j).applyMatrix4(node.matrixWorld))),n=t.getNormal(new Vector3());if(n.dot(normal)<.99)continue;const d=t.closestPointToPoint(probe,new Vector3()).distanceTo(probe);if(d<result.distance)result={distance:d,mesh:node.name,triangle:i/3,normal:n.toArray(),vertices:[t.a.toArray(),t.b.toArray(),t.c.toArray()]};}});return result;
}
function clipX(points:readonly Vector3[],bound:number,side:number):Vector3[]{
  const out:Vector3[]=[];for(let i=0;i<points.length;i++){const a=points[i],b=points[(i+1)%points.length];if(!a||!b)throw new RangeError('Incomplete triangle polygon');const da=side*(a.x-bound),db=side*(b.x-bound);if(da>=0)out.push(a);if((da<0)!==(db<0))out.push(a.clone().lerp(b,da/(da-db)));}return out;
}
/** Exact finite annulus intersection of a machine triangle clipped to material axial extent.
 * The projected triangle is convex; its radial extrema bound all interior radii.
 * Actual float32 decoded vertices are used, and only a1µm contact allowance is applied.
 */
export function materialPenetrations(roots:readonly Object3D[],material:Point):readonly{readonly mesh:string;readonly triangle:number;readonly radialMin:number;readonly radialMax:number}[]{
  const inverse=new Matrix4().makeTranslation(-material[0],-material[1],-material[2]),hits:{mesh:string;triangle:number;radialMin:number;radialMax:number}[]=[];
  for(const root of roots){root.updateMatrixWorld(true);root.traverse(node=>{if(!(node instanceof Mesh)||String(node.userData.semantic_id).startsWith('axis_'))return;const p=node.geometry.getAttribute('position'),index=node.geometry.index,count=index?.count??p.count;
    for(let i=0;i<count;i+=3){const points=[0,1,2].map(j=>new Vector3().fromBufferAttribute(p,index?index.getX(i+j):i+j).applyMatrix4(node.matrixWorld).applyMatrix4(inverse));const xmax=Math.max(...points.map(v=>v.x)),xmin=Math.min(...points.map(v=>v.x));if(xmax<=-.5+1e-6||xmin>=.5-1e-6)continue;
      const poly=clipX(clipX(points,-.5,1),.5,-1);if(!poly.length)continue;
      let min=Infinity,max=0;let positive=false,negative=false;
      for(let k=0;k<poly.length;k++){const a=poly[k],b=poly[(k+1)%poly.length];if(!a||!b)throw new RangeError('Clipped polygon incomplete');const r=Math.hypot(a.y,a.z);max=Math.max(max,r);const dy=b.y-a.y,dz=b.z-a.z,denom=dy*dy+dz*dz,t=denom>0?Math.max(0,Math.min(1,-(a.y*dy+a.z*dz)/denom)):0;min=Math.min(min,Math.hypot(a.y+t*dy,a.z+t*dz));const cross=a.y*b.z-a.z*b.y;if(cross>1e-12)positive=true;if(cross< -1e-12)negative=true;}
      if(positive!==negative&&poly.length>=3)min=0;
      if(min<.6-1e-6&&max>.3+1e-6)hits.push({mesh:node.name,triangle:i/3,radialMin:min,radialMax:max});
    }
  });}return hits;
}
