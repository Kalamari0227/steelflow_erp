import { BufferGeometry, Float32BufferAttribute, Vector3 } from 'three';

export type Section = {readonly center:Vector3;readonly normal:Vector3;readonly thickness:number};
export type SheetProof = {readonly geometry:BufferGeometry;readonly centerlineM:number;readonly volumeM3:number;readonly targetVolumeM3:number;readonly tailM:number;readonly segments:number};

function lengthOf(points:readonly Vector3[]):number {return points.slice(1).reduce((s,p,i)=>{const a=points[i];if(!a)throw new RangeError('Path segment absent');return s+p.distanceTo(a);},0);}

/** One connected, closed sheet, with true mitered thickness at every bend. */
export function sheet(sections:readonly Section[],width:number,targetVolume:number,tailM=0):SheetProof {
  if(sections.length<2 || width<=0)throw new RangeError('Finite nonempty sheet required');
  const vertices:number[]=[],indices:number[]=[];
  for(const [i,s] of sections.entries()){
    const previous=sections[Math.max(0,i-1)],next=sections[Math.min(sections.length-1,i+1)];
    if(!previous || !next)throw new RangeError('Sheet neighbour absent');
    const incoming=i===0 ? next.center.clone().sub(s.center).normalize() : s.center.clone().sub(previous.center).normalize();
    const outgoing=i===sections.length-1 ? s.center.clone().sub(previous.center).normalize() : next.center.clone().sub(s.center).normalize();
    const n0=new Vector3(incoming.y,-incoming.x,0),n1=new Vector3(outgoing.y,-outgoing.x,0),normal=n0.add(n1).normalize();
    if(normal.dot(s.normal)<0)normal.negate();
    const factor=s.thickness/(2*Math.abs(normal.dot(new Vector3(incoming.y,-incoming.x,0))));
    if(!Number.isFinite(factor) || factor>s.thickness*4)throw new RangeError('Disconnected or reversing sheet tangent');
    for(const [sign,z] of [[-1,-width/2],[1,-width/2],[1,width/2],[-1,width/2]]){
      if(sign===undefined || z===undefined)throw new RangeError('Sheet profile absent');
      vertices.push(s.center.x+normal.x*factor*sign,s.center.y+normal.y*factor*sign,z);
    }
    if(i>0)for(let j=0;j<4;j++){const a=(i-1)*4+j,b=(i-1)*4+(j+1)%4,c=i*4+(j+1)%4,d=i*4+j;indices.push(a,b,c,a,c,d);}
  }
  indices.push(0,2,1,0,3,2);const end=(sections.length-1)*4;indices.push(end,end+1,end+2,end,end+2,end+3);
  const first=sections[0],second=sections[1];if(!first||!second)throw new RangeError('Sheet orientation absent');
  if(second.center.clone().sub(first.center).cross(first.normal).z<0)for(let i=0;i<indices.length;i+=3){const b=indices[i+1],c=indices[i+2];if(b===undefined||c===undefined)throw new RangeError('Oriented triangle absent');indices[i+1]=c;indices[i+2]=b;}
  const geometry=new BufferGeometry();geometry.setAttribute('position',new Float32BufferAttribute(vertices,3));geometry.setIndex(indices);geometry.computeVertexNormals();
  const positions=geometry.getAttribute('position');let signedVolume=0;
  for(let i=0;i<indices.length;i+=3){const a=indices[i],b=indices[i+1],c=indices[i+2];if(a===undefined||b===undefined||c===undefined)throw new RangeError('Triangle absent');signedVolume+=new Vector3().fromBufferAttribute(positions,a).dot(new Vector3().fromBufferAttribute(positions,b).cross(new Vector3().fromBufferAttribute(positions,c)))/6;}
  return {geometry,centerlineM:lengthOf(sections.map(s=>s.center)),volumeM3:Math.abs(signedVolume),targetVolumeM3:targetVolume,tailM,segments:sections.length-1};
}

export function spiralLength(theta:number,thickness:number):number {
  const r0=.44+thickness/2,k=(thickness+.0002)/(2*Math.PI);
  const f=(r:number)=>(r*Math.sqrt(r*r+k*k)+k*k*Math.asinh(r/k))/(2*k);
  return f(r0+k*theta)-f(r0);
}

/** Geometry is in the admitted rotating clamp/material frame. No second feed. */
export function woundStrip(theta:number,width:number,thickness:number,maximum:number):SheetProof {
  if(!Number.isFinite(theta) || theta<0 || theta>maximum)throw new RangeError('Winding scalar outside sealed authored range');
  const r0=.44+thickness/2,k=(thickness+.0002)/(2*Math.PI),count=Math.max(1,Math.ceil(theta*512));
  const sections:Section[]=[];
  for(let i=0;i<=count;i++){
    if(theta===0 && i>0)break;
    const phi=theta*i/count,r=r0+k*phi;
    sections.push({center:new Vector3(-r*Math.sin(phi),r*Math.cos(phi)-r0,0),normal:new Vector3(-Math.sin(phi),Math.cos(phi),0),thickness});
  }
  const measured=spiralLength(theta,thickness),tail=theta===maximum ? 0 : 4-measured;
  if(tail< -1e-8 || Math.abs(spiralLength(maximum,thickness)-4)>1e-8)throw new RangeError('Finite 4m range is inconsistent with source');
  if(tail>0){const last=sections.at(-1);if(!last)throw new RangeError('Coil endpoint absent');const r=r0+k*theta,tangent=new Vector3(-k*Math.sin(theta)-r*Math.cos(theta),k*Math.cos(theta)-r*Math.sin(theta),0).normalize(),tailSections=Math.ceil(tail/.075);for(let i=1;i<=tailSections;i++)sections.push({center:last.center.clone().addScaledVector(tangent,tail*i/tailSections),normal:last.normal,thickness});}
  return sheet(sections,width,4*width*thickness,tail);
}

/** The one rectangular batch coil is a true annulus, not a solid cylinder. */
export function batchCoil():BufferGeometry {
  const vertices:number[]=[],indices:number[]=[],n=128;
  for(const y of [-.3,.3])for(const r of [.3,.7])for(let i=0;i<n;i++){const a=i*2*Math.PI/n;vertices.push(r*Math.cos(a),y,r*Math.sin(a));}
  for(let i=0;i<n;i++){const j=(i+1)%n;for(const q of [[i,j,n+j,n+i],[2*n+i,3*n+i,3*n+j,2*n+j],[n+i,n+j,3*n+j,3*n+i],[i,2*n+i,2*n+j,j]]){const [a,b,c,d]=q;if(a===undefined||b===undefined||c===undefined||d===undefined)throw new RangeError('Coil ring absent');indices.push(a,c,b,a,d,c);}}
  const g=new BufferGeometry();g.setAttribute('position',new Float32BufferAttribute(vertices,3));g.setIndex(indices);g.computeVertexNormals();return g;
}

export const coldLaw={radiusM:.36,inletM:.004,outletM:.002,lengthM:4,widthM:1.2,biteM:.026814175355583798,biteAreaM:.03574726230069509,maximumRad:22.32152017305749,entryHandoffRad:22.22222222222222,nipHandoffRad:22.29677508587558} as const;
export function coldThickness(x:number):number{if(x<=-coldLaw.biteM)return coldLaw.inletM;if(x>=0)return coldLaw.outletM;return coldLaw.outletM+2*(coldLaw.radiusM-Math.sqrt(coldLaw.radiusM**2-x*x));}
export function coldArea(x:number):number{
  const {radiusM:r,inletM:tin,outletM:tout,biteM:b,biteAreaM:a0}=coldLaw;
  if(x<=-b)return tin/tout*(x+b);if(x>=0)return a0+x;
  const f=(s:number)=>(s*Math.sqrt(r*r-s*s)+r*r*Math.asin(s/r))/2;
  return (tout+2*r)/tout*(x+b)-2/tout*(f(x)-f(-b));
}
export function inverseColdArea(area:number):number{
  if(area<=0)return -coldLaw.biteM+area*coldLaw.outletM/coldLaw.inletM;
  if(area>=coldLaw.biteAreaM)return area-coldLaw.biteAreaM;
  let low=-coldLaw.biteM,high=0;for(let i=0;i<70;i++){const m=(low+high)/2;if(coldArea(m)<area)low=m;else high=m;}return (low+high)/2;
}
/** The complete raw strip enters the bite; the final tail actually leaves it. */
export function coldReduction(theta:number):SheetProof&{readonly tailXM:number;readonly tipXM:number;readonly nipReferenceY:number}{
  if(!Number.isFinite(theta)||theta<0||theta>coldLaw.maximumRad)throw new RangeError('Cold scalar outside sealed complete travel');
  const q=theta===coldLaw.maximumRad?8+coldLaw.biteAreaM:coldLaw.radiusM*theta;
  const tip=theta===coldLaw.maximumRad?8:inverseColdArea(q),tail=theta===coldLaw.maximumRad?0:inverseColdArea(q-8);
  const xs=[tail,tip];if(theta===0){const count=Math.ceil(4/.075);for(let i=1;i<count;i++)xs.push(tail+4*i/count);}for(let i=0;i<=256;i++){const x=-coldLaw.biteM+coldLaw.biteM*i/256;if(x>tail&&x<tip)xs.push(x);}
  const sections=[...new Set(xs)].sort((a,b)=>a-b).map(x=>({center:new Vector3(x,0,0),normal:new Vector3(0,1,0),thickness:coldThickness(x)}));
  return {...sheet(sections,1.2,.0192),tailXM:tail,tipXM:tip,nipReferenceY:.001};
}

/** Stable upper-first section IDs match the source coil's fixed-alpha straight end. */
export function upperFirstSheet(geometry:BufferGeometry):BufferGeometry{
  const p=geometry.getAttribute('position'),index=geometry.index;if(p.count%4!==0||!index)throw new RangeError('Actual indexed four-vertex sections required');const order=[1,0,3,2],positions:number[]=[],indices:number[]=[];
  for(let ring=0;ring<p.count/4;ring++)for(const offset of order){const i=ring*4+offset;positions.push(p.getX(i),p.getY(i),p.getZ(i));}
  for(let i=0;i<index.count;i++){const old=index.getX(i),offset=order[old%4];if(offset===undefined)throw new RangeError('Stable section vertex absent');indices.push(Math.floor(old/4)*4+offset);}
  geometry.setAttribute('position',new Float32BufferAttribute(positions,3));geometry.setIndex(indices);geometry.computeVertexNormals();return geometry;
}

export type BathPiece = {readonly kind:'line';readonly from:readonly [number,number];readonly to:readonly [number,number]} | {readonly kind:'arc';readonly center:readonly [number,number];readonly radius:number;readonly start:number;readonly end:number};
export type BathPath = {readonly pieces:readonly BathPiece[];readonly driver:string;readonly radiusM:number;readonly datumM:number;readonly immersedY:number;readonly knifeX:number|null};

/** Authored family-local tangent path; not a T62 rigid-feed descriptor. */
export function bathPath(kind:'pickling'|'galvanizing',stage:string,t:number):BathPath {
  const pieces:BathPiece[]=[];
  if(kind==='pickling'){
    const r=.24+t/2,s=.12+t/2,span=2*(r+s),count=stage==='cr'?3:2;
    for(let i=0;i<count;i++){
      const x=i*(span+.08),cy=2-.24-.06;
      pieces.push({kind:'arc',center:[x,2-.24],radius:r,start:Math.PI/2,end:0},{kind:'line',from:[x+r,2-.24],to:[x+r,cy]},{kind:'arc',center:[x+r+s,cy],radius:s,start:Math.PI,end:2*Math.PI},{kind:'line',from:[x+r+2*s,cy],to:[x+r+2*s,2-.24]},{kind:'arc',center:[x+span,2-.24],radius:r,start:Math.PI,end:Math.PI/2});
      if(i<count-1)pieces.push({kind:'line',from:[x+span,2+t/2],to:[x+span+.08,2+t/2]});
    }
    return {pieces,driver:'pickling_feed',radiusM:.24,datumM:2,immersedY:1.88,knifeX:null};
  }
  const r=.22+t/2,s=.42+t/2,sinkX=r+s,exitX=r+2*s,upperR=.26+t/2;
  pieces.push({kind:'arc',center:[0,1.54],radius:r,start:Math.PI/2,end:0},{kind:'line',from:[r,1.54],to:[r,1.15]},{kind:'arc',center:[sinkX,1.15],radius:s,start:Math.PI,end:2*Math.PI},{kind:'line',from:[exitX,1.15],to:[exitX,3.35]},{kind:'arc',center:[exitX+upperR,3.35],radius:upperR,start:Math.PI,end:Math.PI/2});
  return {pieces,driver:'sink_roll',radiusM:.42,datumM:1.76,immersedY:1.64,knifeX:exitX};
}
function pieceLength(p:BathPiece):number{return p.kind==='arc'?Math.abs(p.end-p.start)*p.radius:Math.hypot(p.to[0]-p.from[0],p.to[1]-p.from[1]);}
function onPiece(p:BathPiece,u:number):{readonly center:Vector3;readonly normal:Vector3}{
  if(p.kind==='arc'){const a=p.start+(p.end-p.start)*u,sign=Math.sign(p.end-p.start),normal=new Vector3(-sign*Math.cos(a),-sign*Math.sin(a),0);return {center:new Vector3(p.center[0]+p.radius*Math.cos(a),p.center[1]+p.radius*Math.sin(a),0),normal};}
  const dx=p.to[0]-p.from[0],dy=p.to[1]-p.from[1],n=Math.hypot(dx,dy);return {center:new Vector3(p.from[0]+dx*u,p.from[1]+dy*u,0),normal:new Vector3(-dy/n,dx/n,0)};
}
/** One finite 4m sheet translated by the admitted R*theta along an exact path. */
export function bathThreading(path:BathPath,theta:number,t:number,maximum:number):SheetProof&{readonly travelM:number;readonly pathLengthM:number}{
  if(!Number.isFinite(theta)||theta<0||theta>maximum||Math.abs(path.radiusM*maximum-4)>1e-9)throw new RangeError('Exact finite bath stroke outside authored range');
  const q=theta===maximum?4:path.radiusM*theta,from=q-4,to=q,sections:Section[]=[],lengths=path.pieces.map(pieceLength),total=lengths.reduce((a,b)=>a+b,0);
  const at=(s:number):Section=>{
    if(s<=0)return {center:new Vector3(s,path.datumM+t/2,0),normal:new Vector3(0,1,0),thickness:t};
    let offset=0;for(const [i,p]of path.pieces.entries()){const length=lengths[i];if(length===undefined)throw new RangeError('Path segment absent');if(s<=offset+length+1e-12)return {...onPiece(p,(s-offset)/length),thickness:t};offset+=length;}
    const last=path.pieces.at(-1);if(!last)throw new RangeError('Bath outlet absent');const end=onPiece(last,1),tangent=new Vector3(end.normal.y,-end.normal.x,0);return {center:end.center.addScaledVector(tangent,s-total),normal:end.normal,thickness:t};
  };
  const stations=[from,to,0];let offset=0;for(const [i,p]of path.pieces.entries()){const length=lengths[i];if(length===undefined)throw new RangeError('Path segment absent');const count=p.kind==='arc'?Math.ceil(Math.abs(p.end-p.start)*1024):1;for(let j=0;j<=count;j++){const s=offset+length*j/count;if(s>from&&s<to)stations.push(s);}offset+=length;}
  for(const s of [...new Set(stations.filter(s=>s>=from&&s<=to))].sort((a,b)=>a-b)){const section=at(s);section.center.y-=path.datumM+t/2;const previous=sections.at(-1);if(!previous||previous.center.distanceTo(section.center)>1e-10)sections.push(section);}
  const proof=sheet(sections,1.2,4*1.2*t);return {...proof,travelM:q,pathLengthM:total};
}

/** Exact internal common tangents to the two fixed rolls and lifted bottom roll. */
export function looperAccumulation(lift:number,t:number):SheetProof&{readonly storedPathM:number;readonly releasedM:number}{
  if(!Number.isFinite(lift)||lift<0||lift>.6)throw new RangeError('Canonical looper lift outside authored range');
  const r=.22+t/2,cy=1.35+lift,dx=.6,dy=cy-1.78,distance=Math.hypot(dx,dy),alpha=Math.atan2(dy,dx)+Math.acos(2*r/distance);
  const first:BathPiece={kind:'arc',center:[-.6,1.78],radius:r,start:Math.PI/2,end:alpha},bottom:BathPiece={kind:'arc',center:[0,cy],radius:r,start:alpha+Math.PI,end:2*Math.PI-alpha},last:BathPiece={kind:'arc',center:[.6,1.78],radius:r,start:Math.PI-alpha,end:Math.PI/2},p1=onPiece(first,1),p2=onPiece(bottom,0),p3=onPiece(bottom,1),p4=onPiece(last,0),pieces:BathPiece[]=[first,{kind:'line',from:[p1.center.x,p1.center.y],to:[p2.center.x,p2.center.y]},bottom,{kind:'line',from:[p3.center.x,p3.center.y],to:[p4.center.x,p4.center.y]},last],length=pieces.reduce((sum,p)=>sum+pieceLength(p),0),tail=4-.4-length;
  if(tail<0)throw new RangeError('Looper path exceeds actual finite stock');
  const sections:Section[]=[{center:new Vector3(-1,2+t/2,0),normal:new Vector3(0,1,0),thickness:t}];
  for(const piece of pieces){const count=piece.kind==='arc'?Math.ceil(Math.abs(piece.end-piece.start)*1024):1;for(let j=0;j<=count;j++){const point=onPiece(piece,j/count),previous=sections.at(-1);if(!previous||previous.center.distanceTo(point.center)>1e-10)sections.push({...point,thickness:t});}}
  sections.push({center:new Vector3(.6+tail,2+t/2,0),normal:new Vector3(0,1,0),thickness:t});
  for(const section of sections){section.center.x+=.6;section.center.y-=2+t/2;}
  const restDy=1.35-1.78,restDistance=Math.hypot(.6,restDy),restAlpha=Math.atan2(restDy,.6)+Math.acos(2*r/restDistance),restLength=2*Math.sqrt(restDistance**2-(2*r)**2)+r*(2*(Math.PI/2-restAlpha)+Math.PI-2*restAlpha);
  return {...sheet(sections,1.2,4*1.2*t),storedPathM:length,releasedM:restLength-length};
}
