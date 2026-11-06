import {BufferGeometry,Float32BufferAttribute} from 'three';
import {z} from 'zod';
import source from './material-source.json';
export const retainedMaterial=source;
export const coilDimensions=z.strictObject({length_mm:z.null(),width_mm:z.literal(1000),thickness_mm:z.literal(2),diameter_mm:z.literal(1200),inner_diameter_mm:z.literal(600)});
/** Closed rigid annulus from the exact retained material version, axis+X. */
export function coilGeometry(input:unknown):BufferGeometry{
  const d=coilDimensions.parse(input),n=96,positions:number[]=[],indices:number[]=[];
  for(const x of [-d.width_mm/2000,d.width_mm/2000])for(const r of [d.inner_diameter_mm/2000,d.diameter_mm/2000])for(let i=0;i<n;i++){const a=i*Math.PI*2/n;positions.push(x,r*Math.cos(a),r*Math.sin(a));}
  for(let i=0;i<n;i++){const j=(i+1)%n;for(const [a,b,c,e]of [[i,j,n+j,n+i],[2*n+i,3*n+i,3*n+j,2*n+j],[n+i,n+j,3*n+j,3*n+i],[i,2*n+i,2*n+j,j]]){if(a===undefined||b===undefined||c===undefined||e===undefined)throw new RangeError('Annulus face incomplete');indices.push(a,b,c,a,c,e);}}
  const g=new BufferGeometry();g.setAttribute('position',new Float32BufferAttribute(positions,3));g.setIndex(indices);g.computeVertexNormals();g.computeBoundingBox();g.userData={materialId:'t16:material:1',versionId:'t16:version:1',dimensions:d,volumeM3:Math.PI*(.6**2-.3**2)};return g;
}
