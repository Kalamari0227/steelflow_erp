/** Actual decoded triangles. Bounds accelerate candidates; they are never proof. */
import { Box3, Matrix4, Quaternion, Ray, Triangle, Vector3 } from 'three';

export function decodedScene(asset,parsed,channels={}){
  const {gltf,accessor}=parsed,parents=new Map(),matrices=new Map(),indexed=new Map();
  gltf.nodes.forEach((n,i)=>{indexed.set(n.extras.semantic_id,i);for(const c of n.children??[])parents.set(c,i);});
  function matrix(i){
    if(matrices.has(i))return matrices.get(i);
    const n=gltf.nodes[i],part=asset.moving_parts.find(p=>p.node_id===n.extras.semantic_id),position=new Vector3(...(n.translation??[0,0,0])),rotation=new Quaternion(...(n.rotation??[0,0,0,1]));
    if(part){const driver=part.binding.type==='mechanical_follower'?asset.moving_parts.find(p=>p.id===part.binding.driver_part_id):part;if(!driver)throw new Error('Decoded driver absent');const value=channels[driver.function]??driver.range.rest,delta=part.binding.type==='mechanical_follower'?part.binding.ratio*(value-driver.range.rest):value-part.range.rest;if(part.motion==='rotation')rotation.premultiply(new Quaternion().setFromAxisAngle(new Vector3(...part.axis),delta));else position.addScaledVector(new Vector3(...part.axis),delta);}
    const local=new Matrix4().compose(position,rotation,new Vector3(1,1,1)),world=parents.has(i)?matrix(parents.get(i)).clone().multiply(local):local;matrices.set(i,world);return world;
  }
  const meshes=[];
  for(const [i,node]of gltf.nodes.entries())if(node.mesh!==undefined){const transform=matrix(i),triangles=[],vertices=[];for(const p of gltf.meshes[node.mesh].primitives){const positions=accessor(p.attributes.POSITION).map(v=>new Vector3(...v).applyMatrix4(transform)),indices=accessor(p.indices).flat();vertices.push(...positions);for(let j=0;j<indices.length;j+=3)triangles.push(new Triangle(...indices.slice(j,j+3).map(k=>positions[k])));}meshes.push({id:node.extras.semantic_id,index:i,triangles,vertices,bounds:new Box3().setFromPoints(vertices)});}
  function descendant(i,root){return i===root || (parents.has(i)&&descendant(parents.get(i),root));}
  return {meshes,matrices,indexed,matrix,trianglesOf:(id)=>{const index=indexed.get(id);if(index===undefined)throw new Error('Actual node absent '+id);return meshes.filter(m=>descendant(m.index,index)).flatMap(m=>m.triangles);},socket:(id)=>{const s=asset.sockets.find(s=>s.id===id);if(!s)throw new Error('Actual socket absent '+id);const transform=matrix(indexed.get(s.node_id)).clone().multiply(new Matrix4().compose(new Vector3(...s.transform.position_m),new Quaternion(...s.transform.rotation_xyzw),new Vector3(1,1,1)));return {point:new Vector3().applyMatrix4(transform),normal:new Vector3(...s.normal).transformDirection(transform),transform};}};
}

export function geometryTriangles(geometry,matrix=new Matrix4()){
  const a=geometry.getAttribute('position'),index=geometry.index,result=[];
  for(let i=0;i<(index?.count??a.count);i+=3)result.push(new Triangle(...[0,1,2].map(j=>new Vector3().fromBufferAttribute(a,index?.getX(i+j)??i+j).applyMatrix4(matrix))));
  return result;
}

export function nearest(triangles,point){
  let best=null;
  for(const [i,triangle]of triangles.entries()){const closest=triangle.closestPointToPoint(point,new Vector3()),distance=closest.distanceTo(point);if(!best || distance<best.distance)best={distance,normal:triangle.getNormal(new Vector3()).toArray(),point:closest.toArray(),triangle:i,worldVertices:[triangle.a.toArray(),triangle.b.toArray(),triangle.c.toArray()]};}
  if(!best)throw new Error('No actual triangles for contact');return best;
}

/** Use the socket's real transported normal, including side and bore contacts. */
export function contact(triangles,point,expectedNormal){
  const any=nearest(triangles,point);let aligned=null;
  for(const [i,t]of triangles.entries()){const n=t.getNormal(new Vector3()),alignment=n.dot(expectedNormal);if(alignment<.99)continue;const closest=t.closestPointToPoint(point,new Vector3()),distance=closest.distanceTo(point);if(!aligned || distance<aligned.distance)aligned={distance,normal:n.toArray(),alignment,triangle:i,point:closest.toArray(),worldVertices:[t.a.toArray(),t.b.toArray(),t.c.toArray()]};}
  return {nearestAny:any,aligned};
}

/** Parity against the closed decoded mesh, retaining both surface orientations. */
export function contains(triangles,point,tolerance=1e-5){
  const surface=nearest(triangles,point);if(surface.distance<=tolerance)return false;
  const ray=new Ray(point,new Vector3(.93231,.24717,.26419).normalize()),hits=[];
  for(const t of triangles){const hit=ray.intersectTriangle(t.a,t.b,t.c,false,new Vector3());if(hit){const d=point.distanceTo(hit);if(d>tolerance&&!hits.some(v=>Math.abs(v-d)<1e-7))hits.push(d);}}
  return hits.length%2===1;
}

const prismFaces=[[0,1,2],[4,6,5],[0,4,5],[1,5,6],[2,6,7],[3,7,4]];
const prismEdges=[[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];
function overlapOn(axis,a,b,tolerance){
  const length=axis.length();if(length<1e-12)return true;axis.multiplyScalar(1/length);
  let amin=Infinity,amax=-Infinity,bmin=Infinity,bmax=-Infinity;for(const p of a){const d=p.dot(axis);amin=Math.min(amin,d);amax=Math.max(amax,d);}for(const p of b){const d=p.dot(axis);bmin=Math.min(bmin,d);bmax=Math.max(bmax,d);}
  return amax>bmin+tolerance&&bmax>amin+tolerance;
}

/** SAT of a machine triangle and the actual eight rendered sheet vertices. */
export function trianglePrism(triangle,vertices,tolerance=1e-5){
  const points=[triangle.a,triangle.b,triangle.c],edges=[triangle.b.clone().sub(triangle.a),triangle.c.clone().sub(triangle.b),triangle.a.clone().sub(triangle.c)];
  for(const face of prismFaces){const [a,b,c]=face,axis=vertices[b].clone().sub(vertices[a]).cross(vertices[c].clone().sub(vertices[a]));if(!overlapOn(axis,points,vertices,tolerance))return false;}
  if(!overlapOn(edges[0].clone().cross(edges[1]),points,vertices,tolerance))return false;
  for(const [a,b]of prismEdges){const e=vertices[b].clone().sub(vertices[a]);for(const t of edges)if(!overlapOn(e.clone().cross(t),points,vertices,tolerance))return false;}
  return true;
}

/** Uniform spatial grid bounds only prune; SAT returns actual triangle witnesses. */
export function sheetClearance(scene,geometry,materialMatrix,{exclude=[]}={}){
  const attribute=geometry.getAttribute('position'),rings=attribute.count/4,points=Array.from({length:attribute.count},(_,i)=>new Vector3().fromBufferAttribute(attribute,i).applyMatrix4(materialMatrix));
  if(!Number.isInteger(rings))throw new Error('Expected the actual closed four-vertex section sheet');
  const stockBounds=new Box3().setFromPoints(points),triangles=scene.meshes.filter(m=>!exclude.includes(m.id)&&m.bounds.intersectsBox(stockBounds)).flatMap(m=>m.triangles.map((triangle,i)=>({triangle,id:m.id,index:i,bounds:new Box3().setFromPoints([triangle.a,triangle.b,triangle.c])}))),grid=new Map(),cell=.2;
  function cells(bounds,fn){for(let x=Math.floor(bounds.min.x/cell);x<=Math.floor(bounds.max.x/cell);x++)for(let y=Math.floor(bounds.min.y/cell);y<=Math.floor(bounds.max.y/cell);y++)for(let z=Math.floor(bounds.min.z/cell);z<=Math.floor(bounds.max.z/cell);z++)fn(`${x}:${y}:${z}`);}
  triangles.forEach((t,i)=>cells(t.bounds,key=>{let list=grid.get(key);if(!list){list=[];grid.set(key,list);}list.push(i);}));
  let tested=0;const hits=[];
  for(let i=1;i<rings;i++){
    const prism=points.slice((i-1)*4,(i+1)*4),bounds=new Box3().setFromPoints(prism),candidates=new Set();cells(bounds,key=>{for(const id of grid.get(key)??[])candidates.add(id);});
    for(const id of candidates){const t=triangles[id];if(!bounds.intersectsBox(t.bounds))continue;tested++;if(trianglePrism(t.triangle,prism)){hits.push({mesh:t.id,triangle:t.index,section:i,worldVertices:[t.triangle.a.toArray(),t.triangle.b.toArray(),t.triangle.c.toArray()],prism:prism.map(p=>p.toArray())});if(hits.length>=20)return {tested,hits};}}
  }
  return {tested,hits};
}
