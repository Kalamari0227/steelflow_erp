/** Continuous translation SAT against convex cells extracted from actual product triangles. */
import {Ray,Vector3,Triangle} from 'three';
const sub=(a,b)=>a.map((v,i)=>v-b[i]);
const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const length=a=>Math.hypot(...a);
export const bounds=points=>({min:[0,1,2].map(i=>Math.min(...points.map(p=>p[i]))),max:[0,1,2].map(i=>Math.max(...points.map(p=>p[i])))});
const overlaps=(a,b,tolerance=1e-6)=>[0,1,2].every(i=>a.max[i]>b.min[i]+tolerance&&b.max[i]>a.min[i]+tolerance);
function edges(points,pairs){return pairs.map(([a,b])=>sub(points[b],points[a])).filter(v=>length(v)>1e-10);}
function normals(points,faces){return faces.map(([a,b,c])=>cross(sub(points[b],points[a]),sub(points[c],points[a]))).filter(v=>length(v)>1e-10);}
const trianglePairs=[[0,1],[1,2],[2,0]],prismPairs=[...trianglePairs,...trianglePairs.map(([a,b])=>[a+3,b+3]),[0,3],[1,4],[2,5]];
const prismFaces=[[0,1,2],[3,5,4],[0,1,4],[1,2,5],[2,0,3]];
function convex(points,pairs,faces){return{points,bounds:bounds(points),edges:edges(points,pairs),normals:normals(points,faces)};}
function intersects(a,b){
 if(!overlaps(a.bounds,b.bounds))return false;
 const axes=[...a.normals,...b.normals];for(const x of a.edges)for(const y of b.edges)axes.push(cross(x,y));
 for(const raw of axes){const norm=length(raw);if(norm<1e-10)continue;const axis=raw.map(v=>v/norm),ap=a.points.map(p=>dot(p,axis)),bp=b.points.map(p=>dot(p,axis));if(Math.max(...ap)<=Math.min(...bp)+1e-6||Math.max(...bp)<=Math.min(...ap)+1e-6)return false;}
 return true;
}
/** The factory's exact 64-sided annulus is the union of64 convex radial prisms. */
export function actualCoilCells(geometry){
 const p=geometry.getAttribute('position'),segments=geometry.userData.angularSegments;if(segments!==64||p.count!==512)throw Error('Unsupported actual product annulus topology');const point=i=>[p.getX(i),p.getY(i),p.getZ(i)],cells=[];
 for(let i=0;i<64;i++){const j=(i+1)%64;const vertices=[point(2*i),point(2*j),point(128+2*j),point(128+2*i),point(2*i+1),point(2*j+1),point(128+2*j+1),point(128+2*i+1)];const pairs=[[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]],faces=[[0,1,2],[4,6,5],[0,4,5],[1,5,6],[2,6,7],[3,7,4]];cells.push(convex(vertices,pairs,faces));}
 return cells;
}
export function continuousMaterialSweep(before,after,cells){
 if(before.length!==after.length)throw Error('Mesh universe changed');let triangles=0,candidates=0;const hits=[];
 for(let i=0;i<before.length;i++){const a=before[i],b=after[i];if(a.id!==b.id||a.triangles.length!==b.triangles.length)throw Error('Actual mesh topology changed');
  for(let j=0;j<a.triangles.length;j++){const first=a.triangles[j],last=b.triangles[j],delta=sub(last[0],first[0]);if([1,2].some(k=>length(sub(sub(last[k],first[k]),delta))>1e-5))throw Error('Nonlinear/rotated triangle requires a separately qualified sweep');const prism=convex([...first,...last],prismPairs,prismFaces);triangles++;
   for(let k=0;k<cells.length;k++){if(!overlaps(prism.bounds,cells[k].bounds))continue;candidates++;if(intersects(prism,cells[k])){if(hits.length<100)hits.push({mesh:a.id,triangle:j,cell:k,kind:'actual-product-cell-vs-continuous-triangle-prism'});break;}}
  }
  const samplePoints=cells.map(cell=>[0,1,2].map(k=>cell.points.reduce((sum,p)=>sum+p[k],0)/cell.points.length));
  for(const endpoint of[a,b]){const box=bounds(endpoint.triangles.flat());for(const point of samplePoints){if([0,1,2].every(k=>point[k]>box.min[k]+1e-6&&point[k]<box.max[k]-1e-6)&&insideClosed(endpoint.triangles,point)){hits.push({mesh:a.id,triangle:-1,kind:'actual-material-cell-inside-closed-machine'});break;}}}
 }
 return{triangles,candidates,hits};
}

function insideClosed(triangles,point){const probe=new Vector3(...point),ray=new Ray(probe,new Vector3(.93231,.24717,.26419).normalize()),hits=[];for(const points of triangles){const t=new Triangle(...points.map(p=>new Vector3(...p)));if(t.closestPointToPoint(probe,new Vector3()).distanceTo(probe)<1e-6)return false;const hit=ray.intersectTriangle(t.a,t.b,t.c,false,new Vector3());if(hit){const d=hit.distanceTo(probe);if(d>1e-6&&!hits.some(h=>Math.abs(h-d)<1e-7))hits.push(d);}}return hits.length%2===1;}

/** Real surface intersections between different relative motions, not box hits. */
export function continuousMachineSweep(before,after){
 if(before.length!==after.length)throw Error('Machine universe changed');const moving=before.map((m,i)=>{const n=after[i];if(m.id!==n.id||m.triangles.length!==n.triangles.length)throw Error('Topology changed');const delta=sub(n.triangles[0][0],m.triangles[0][0]);return{...m,delta,end:n,box:bounds([...m.triangles.flat(),...n.triangles.flat()])};});let pairs=0,trianglePairsChecked=0;const hits=[];
 for(let i=0;i<moving.length;i++)for(let j=i+1;j<moving.length;j++){const a=moving[i],b=moving[j],relative=sub(a.delta,b.delta);const sameOwner=a.id.split(':').slice(0,3).join(':')===b.id.split(':').slice(0,3).join(':');if((length(relative)<1e-10&&sameOwner)||!overlaps(a.box,b.box))continue;pairs++;if(insideClosed(a.triangles,b.triangles[0][0])||insideClosed(b.triangles,a.triangles[0][0])||insideClosed(a.end.triangles,b.end.triangles[0][0])||insideClosed(b.end.triangles,a.end.triangles[0][0])){hits.push({a:a.id,b:b.id,kind:'actual-closed-solid-containment'});continue;}
  const bTriangles=b.triangles.map(t=>convex(t,trianglePairs,[[0,1,2]]));let hit=false;
  for(let t=0;t<a.triangles.length&&!hit;t++){const first=a.triangles[t],last=first.map(p=>p.map((v,k)=>v+relative[k])),prism=convex([...first,...last],prismPairs,prismFaces);
   for(let u=0;u<bTriangles.length;u++){if(!overlaps(prism.bounds,bTriangles[u].bounds))continue;trianglePairsChecked++;if(intersects(prism,bTriangles[u])){hits.push({a:a.id,a_triangle:t,b:b.id,b_triangle:u,kind:'continuous-actual-surface-intersection'});hit=true;break;}}
  }
 }
 return{mesh_pairs:pairs,triangle_pairs_checked:trianglePairsChecked,hits};
}
