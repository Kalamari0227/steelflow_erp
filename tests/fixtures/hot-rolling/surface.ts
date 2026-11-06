import { Mesh, Triangle, Vector3 } from 'three';

/** Closest actual rendered triangle, including world-space orientation and provenance. */
export function nearestSurface(mesh:Mesh,point:Vector3,orientation:'any'|'up'|'down'='any') {
  const positions=mesh.geometry.getAttribute('position'),index=mesh.geometry.index;
  let unorientedDistance=Infinity,distance=Infinity,triangleId=-1,worldVertices:number[][]=[],closestPoint:number[]=[],normal:number[]=[];
  for(let i=0;i<(index?.count ?? positions.count);i+=3) {
    const vertices=[0,1,2].map(j => new Vector3().fromBufferAttribute(positions,index?.getX(i+j) ?? i+j).applyMatrix4(mesh.matrixWorld));
    const a=vertices[0],b=vertices[1],c=vertices[2];if(!a || !b || !c)throw new Error('Rendered triangle absent');
    const triangle=new Triangle(a,b,c),closest=triangle.closestPointToPoint(point,new Vector3()),candidate=closest.distanceTo(point);
    unorientedDistance=Math.min(unorientedDistance,candidate);const facing=triangle.getNormal(new Vector3());
    if(orientation!=='any' && facing.y*(orientation==='up' ? 1 : -1)<.97)continue;
    if(candidate<distance) { distance=candidate;triangleId=i/3;worldVertices=vertices.map(v => v.toArray());closestPoint=closest.toArray();normal=triangle.getNormal(new Vector3()).toArray(); }
  }
  if(!Number.isFinite(distance))return null;
  return {distance,unorientedDistance,orientation,triangleId,worldVertices,closestPoint,normal,meshName:mesh.name,matrixWorld:mesh.matrixWorld.toArray()};
}

export function connectedComponents(mesh:Mesh) {
  const n=mesh.geometry.getAttribute('position').count,index=mesh.geometry.index,parent=Array.from({length:n},(_,i) => i);
  const root=(v:number):number => {while(parent[v]!==v){const p=parent[v];if(p===undefined)throw new Error('Vertex topology absent');v=p;}return v;};
  for(let i=0;i<(index?.count ?? n);i+=3){const a=root(index?.getX(i) ?? i);for(let j=1;j<3;j++)parent[root(index?.getX(i+j) ?? i+j)]=a;}
  return new Set(parent.map((_,i) => root(i))).size;
}

/** Actual transformed feed assembly vertices inside the strip width's overlapping meshes. */
export function feedAssemblyClearance(nodes:ReadonlyMap<string,import('three').Object3D>,contact:Vector3,stripMinZ:number,stripMaxZ:number) {
  const meshes:{name:string;maxY:number;highestVertex:number[];matrixWorld:number[]}[]=[];
  for(const [name,node] of nodes)if(name.startsWith('feed_roller') && node instanceof Mesh) {
    const positions=node.geometry.getAttribute('position'),vertices=Array.from({length:positions.count},(_,i) => new Vector3().fromBufferAttribute(positions,i).applyMatrix4(node.matrixWorld));
    if(Math.max(...vertices.map(v => v.z))<stripMinZ || Math.min(...vertices.map(v => v.z))>stripMaxZ)continue;
    const highest=vertices.reduce((a,b) => a.y>b.y ? a : b);meshes.push({name,maxY:highest.y,highestVertex:highest.toArray(),matrixWorld:node.matrixWorld.toArray()});
  }
  return {planeY:contact.y,stripWidthZ:[stripMinZ,stripMaxZ],meshes,maxPenetrationM:Math.max(...meshes.map(m => m.maxY-contact.y))};
}

/** Bounds only prune candidates; the returned proof always measures actual GLB triangles. */
export function nearestMachineSurface(root:import('three').Object3D,point:Vector3) {
  let nearest:ReturnType<typeof nearestSurface>|null=null;
  root.traverse(node => {if(node instanceof Mesh){
    if(node.geometry.boundingBox===null)node.geometry.computeBoundingBox();const bounds=node.geometry.boundingBox?.clone().applyMatrix4(node.matrixWorld);
    if(bounds && bounds.distanceToPoint(point)<=.025){const actual=nearestSurface(node,point,'up');if(actual && (!nearest || actual.distance<nearest.distance))nearest=actual;}
  }});
  return nearest;
}

/** Exact triangle/solid SAT for the actual rendered rigid BoxGeometry; bounds only prune. */
export function rigidMaterialClearance(root:import('three').Object3D,material:Mesh) {
  if(material.geometry.type!=='BoxGeometry')throw new Error('Rigid feed requires actual rectangular material geometry');
  material.geometry.computeBoundingBox();const inner=material.geometry.boundingBox?.clone();if(!inner)throw new Error('Actual rigid material bounds absent');
  inner.min.addScalar(.00001);inner.max.addScalar(-.00001);
  const inverse=material.matrixWorld.clone().invert(),hits:{mesh:string;triangle:number;worldVertices:number[][];matrixWorld:number[]}[]=[];let testedTriangles=0;
  root.traverse(node=>{if(node instanceof Mesh){if(node.geometry.boundingBox===null)node.geometry.computeBoundingBox();const transform=inverse.clone().multiply(node.matrixWorld),bounds=node.geometry.boundingBox?.clone().applyMatrix4(transform);if(!bounds || !inner.intersectsBox(bounds))return;
    const positions=node.geometry.getAttribute('position'),index=node.geometry.index;
    for(let i=0;i<(index?.count ?? positions.count);i+=3){const points=[0,1,2].map(j=>new Vector3().fromBufferAttribute(positions,index?.getX(i+j) ?? i+j).applyMatrix4(transform));const a=points[0],b=points[1],c=points[2];if(!a || !b || !c)throw new Error('Actual clearance triangle absent');testedTriangles++;
      if(inner.intersectsTriangle(new Triangle(a,b,c)))hits.push({mesh:node.name,triangle:i/3,worldVertices:points.map(v=>v.applyMatrix4(material.matrixWorld).toArray()),matrixWorld:node.matrixWorld.toArray()});}
  }});
  return {method:'actual triangle versus rigid rendered solid SAT',interiorToleranceM:.00001,testedTriangles,hits,materialMatrixWorld:material.matrixWorld.toArray()};
}
