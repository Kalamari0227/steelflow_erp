import { createHash } from 'node:crypto';
import { inflateSync } from 'node:zlib';
import { Matrix4, Quaternion, Triangle, Vector3 } from 'three';

export const hash = bytes => createHash('sha256').update(bytes).digest('hex');
export function requireProof(condition, code, detail) {
  if (!condition) throw new Error(`${code}: ${detail}`);
}
export function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value !== null && typeof value === 'object') return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
  return JSON.stringify(value);
}
export function png(bytes) {
  requireProof(bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])), 'texture', 'PNG signature');
  let offset=8, width, height; const compressed=[];
  while (offset+12<=bytes.length) {
    const size=bytes.readUInt32BE(offset), type=bytes.toString('ascii',offset+4,offset+8);
    requireProof(offset+12+size<=bytes.length,'texture','PNG chunk bounds');
    if(type==='IHDR'){width=bytes.readUInt32BE(offset+8);height=bytes.readUInt32BE(offset+12);}
    if(type==='IDAT')compressed.push(bytes.subarray(offset+8,offset+8+size));
    offset+=12+size;
    if(type==='IEND')break;
  }
  requireProof(width>0&&height>0&&width<=4096&&height<=4096&&compressed.length>0,'texture','PNG pixels');
  const pixels=inflateSync(Buffer.concat(compressed),{maxOutputLength:128*1024*1024});
  requireProof(pixels.length>=width*height,'texture','PNG decompressed pixels');
  return {width,height,pixel_sha256:hash(pixels)};
}

export function readGlb(bytes) {
  requireProof(bytes.length>=28&&bytes.length<=64*1024*1024,'glb','length');
  requireProof(bytes.toString('ascii',0,4)==='glTF'&&bytes.readUInt32LE(4)===2&&bytes.readUInt32LE(8)===bytes.length,'glb','header');
  const length=bytes.readUInt32LE(12);
  requireProof(length%4===0&&20+length+8<=bytes.length&&bytes.readUInt32LE(16)===0x4e4f534a,'glb','JSON chunk');
  const gltf=JSON.parse(bytes.subarray(20,20+length).toString('utf8'));
  requireProof(gltf.asset?.version==='2.0','glb','version');
  const binaryLength=bytes.readUInt32LE(20+length);
  requireProof(bytes.readUInt32LE(24+length)===0x004e4942&&binaryLength%4===0&&28+length+binaryLength===bytes.length,'glb','BIN chunk');
  const bin=bytes.subarray(28+length);
  requireProof(gltf.buffers?.length===1&&gltf.buffers[0].uri===undefined&&gltf.buffers[0].byteLength<=bin.length&&bin.length-gltf.buffers[0].byteLength<=3,'glb','embedded buffer');
  requireProof(!gltf.extensionsRequired?.length,'glb','unsupported required extension');
  function view(index) {
    const v=gltf.bufferViews?.[index];
    requireProof(v&&v.buffer===0&&Number.isInteger(v.byteLength)&&v.byteLength>0&&Number.isInteger(v.byteOffset??0)&&(v.byteOffset??0)>=0&&(v.byteOffset??0)+v.byteLength<=gltf.buffers[0].byteLength,'glb','bufferView bounds');
    return v;
  }
  const layouts={5120:[1,'readInt8'],5121:[1,'readUInt8'],5122:[2,'readInt16LE'],5123:[2,'readUInt16LE'],5125:[4,'readUInt32LE'],5126:[4,'readFloatLE']};
  const arities={SCALAR:1,VEC2:2,VEC3:3,VEC4:4,MAT4:16};
  function accessor(index) {
    const a=gltf.accessors?.[index];
    requireProof(a&&!a.sparse&&layouts[a.componentType]&&arities[a.type]&&Number.isInteger(a.count)&&a.count>0&&a.count<=2000000,'glb','accessor layout');
    const v=view(a.bufferView),[size,read]=layouts[a.componentType],arity=arities[a.type],stride=v.byteStride??size*arity;
    requireProof(stride>=size*arity&&stride%size===0&&Number.isInteger(a.byteOffset??0)&&(a.byteOffset??0)>=0&&(a.byteOffset??0)+(a.count-1)*stride+size*arity<=v.byteLength,'glb','accessor bounds');
    const start=(v.byteOffset??0)+(a.byteOffset??0); const values=[];
    for(let i=0;i<a.count;i++) {
      const row=[];
      for(let j=0;j<arity;j++) {const value=bin[read](start+i*stride+j*size);requireProof(Number.isFinite(value),'glb','nonfinite accessor');row.push(value);}
      values.push(row);
    }
    return values;
  }
  for(let i=0;i<(gltf.bufferViews?.length??0);i++)view(i);
  for(let i=0;i<(gltf.accessors?.length??0);i++)accessor(i);
  const textures=[];
  for(const image of gltf.images??[]) {
    requireProof(image.uri===undefined&&image.mimeType==='image/png','texture','only embedded PNG');
    const v=view(image.bufferView),data=bin.subarray(v.byteOffset??0,(v.byteOffset??0)+v.byteLength);
    textures.push({bytes:data,sha256:hash(data),...png(data)});
  }
  for(const texture of gltf.textures??[]) requireProof(Number.isInteger(texture.source)&&textures[texture.source]!==undefined,'texture','dangling image source');
  let triangles=0;
  for(const mesh of gltf.meshes??[]) for(const primitive of mesh.primitives??[]) {
    requireProof((primitive.mode??4)===4&&primitive.attributes?.POSITION!==undefined,'mesh','triangles/POSITION required');
    const positions=accessor(primitive.attributes.POSITION);
    requireProof(positions.every(row=>row.length===3),'mesh','position arity');
    const indices=accessor(primitive.indices).flat();
    requireProof(indices.length%3===0&&indices.every(index=>Number.isInteger(index)&&index>=0&&index<positions.length),'mesh','index bounds');
    const normals=accessor(primitive.attributes.NORMAL);
    requireProof(normals.length===positions.length&&normals.every(n=>Math.abs(Math.hypot(...n)-1)<1e-4),'mesh','normals');
    const material=gltf.materials?.[primitive.material];requireProof(material,'material','missing material');
    for(const slot of [material.pbrMetallicRoughness?.baseColorTexture,material.pbrMetallicRoughness?.metallicRoughnessTexture,material.normalTexture,material.emissiveTexture,material.occlusionTexture].filter(Boolean)) {
      requireProof(gltf.textures?.[slot.index]!==undefined,'texture','dangling material slot');
      const uv=accessor(primitive.attributes[`TEXCOORD_${slot.texCoord??0}`]);requireProof(uv.length===positions.length&&uv.every(v=>v.length===2),'texture','UV binding');
    }
    triangles+=indices.length/3;
  }
  requireProof(triangles>0,'mesh','empty GLB');
  const semantic=hash(Buffer.concat([Buffer.from(canonical(gltf)),Buffer.from('\0'),bin]));
  return {gltf,bin,accessor,textures,triangles,semantic};
}

const close=(a,b,tolerance=1e-5)=>a.length===b.length&&a.every((v,i)=>Math.abs(v-b[i])<=tolerance);
const rotationClose=(a,b)=>Math.abs(Math.abs(a.reduce((s,v,i)=>s+v*b[i],0))-1)<1e-5;
const vector=values=>new Vector3(...values);
export function validateAssetGlb(asset, parsed, markerPositions) {
  const {gltf,accessor}=parsed;
  requireProof(Array.isArray(gltf.nodes),'missing-node','nodes');
  const indexed=new Map();const parents=new Map();
  gltf.nodes.forEach((node,index)=>{
    requireProof(typeof node.extras?.semantic_id==='string'&&!indexed.has(node.extras.semantic_id),'missing-node','unique semantic id');
    indexed.set(node.extras.semantic_id,{node,index});
    requireProof(node.matrix===undefined&&close(node.scale??[1,1,1],[1,1,1]),'scale',node.name);
    requireProof(Math.abs(Math.hypot(...(node.rotation??[0,0,0,1]))-1)<1e-5,'rotation',node.name);
    for(const child of node.children??[]) {requireProof(Number.isInteger(child)&&gltf.nodes[child]&&!parents.has(child),'hierarchy','single existing parent');parents.set(child,index);}
  });
  for(const expected of asset.nodes)requireProof(indexed.has(expected.id),'missing-node',expected.id);
  requireProof(indexed.size===asset.nodes.length,'missing-node','undeclared nodes');
  const world=new Map();
  function matrix(index, stack=new Set()) {
    requireProof(!stack.has(index),'hierarchy','cycle');if(world.has(index))return world.get(index);
    stack.add(index);const n=gltf.nodes[index];
    const local=new Matrix4().compose(vector(n.translation??[0,0,0]),new Quaternion(...(n.rotation??[0,0,0,1])),new Vector3(1,1,1));
    const result=parents.has(index)?matrix(parents.get(index),stack).clone().multiply(local):local;
    stack.delete(index);world.set(index,result);return result;
  }
  for(const expected of asset.nodes) {
    const {node,index}=indexed.get(expected.id);const parent=parents.get(index);
    requireProof((parent===undefined?null:gltf.nodes[parent].extras.semantic_id)===expected.parent_id,'hierarchy',expected.id);
    const locator=[];let cursor=index;const seen=new Set();
    while(cursor!==undefined){requireProof(!seen.has(cursor),'hierarchy','cycle');seen.add(cursor);locator.unshift(gltf.nodes[cursor].name);cursor=parents.get(cursor);}
    requireProof(locator.join('/')===expected.locator,'locator',expected.id);
    const code=expected.id.startsWith('axis_')?'axis':asset.moving_parts.some(p=>p.node_id===expected.id)?'pivot':'rest-frame';
    requireProof(close(node.translation??[0,0,0],expected.transform.position_m)&&rotationClose(node.rotation??[0,0,0,1],expected.transform.rotation_xyzw),code,expected.id);
    matrix(index);
  }
  const root=indexed.get(asset.root_node_id).index;
  requireProof(gltf.scenes?.[gltf.scene??0]?.nodes?.length===1&&gltf.scenes[gltf.scene??0].nodes[0]===root,'hierarchy','single asset scene root');
  for(const [id,position] of Object.entries(markerPositions)) {
    const entry=indexed.get(id);requireProof(entry,'axis',id);
    const actual=new Vector3().applyMatrix4(matrix(entry.index));requireProof(close(actual.toArray(),position),'axis',id+' actual world metre baseline');
    requireProof(entry.node.mesh!==undefined,'axis',id+' actual geometry');
    const mesh=gltf.meshes[entry.node.mesh];const points=mesh.primitives.flatMap(p=>accessor(p.attributes.POSITION));
    if(id==='axis_front')requireProof(Math.max(...points.map(p=>p[0]))>.13&&Math.min(...points.map(p=>p[0]))<-.07&&Math.max(...points.map(p=>Math.abs(p[1])))<.03,'axis','asymmetric forward arrow');
  }
  const animationReport=[];
  const canonicalDriver=part=>{
    const driver=part.binding.type==='mechanical_follower'?asset.moving_parts.find(row=>row.id===part.binding.driver_part_id):part;
    requireProof(driver&&driver.binding.type==='clip','animation','canonical clip driver '+part.id);
    return driver;
  };
  for(const part of asset.moving_parts) {
    const driver=canonicalDriver(part);
    const entry=indexed.get(part.node_id);
    requireProof(close(part.pivot_m,entry.node.translation??[0,0,0]),'pivot',part.id+' parent-frame origin');
    const clips=(gltf.animations??[]).filter(a=>a.name===driver.binding.clip_id);requireProof(clips.length===1,'animation','unique clip '+driver.binding.clip_id);
    const path=part.motion==='translation'?'translation':'rotation';
    const channels=clips[0].channels.filter(c=>c.target.node===entry.index&&c.target.path===path);requireProof(channels.length===1,'animation','actual bound channel '+part.id);
    const sampler=clips[0].samplers[channels[0].sampler];requireProof(sampler&&(sampler.interpolation??'LINEAR')==='LINEAR','animation','linear sampled channel');
    const times=accessor(sampler.input).flat(),values=accessor(sampler.output);
    requireProof(times.length===values.length&&times.length>=3&&times[0]===0&&times.at(-1)>0&&times.every((t,i)=>i===0||t>times[i-1]),'animation','sampled timeline');
    if(part.binding.type==='mechanical_follower') {
      const driverChannels=clips[0].channels.filter(channel=>channel.target.node===indexed.get(driver.node_id).index&&channel.target.path==='rotation');
      requireProof(driverChannels.length===1,'animation','canonical rotation track '+part.id);
      const driverTimes=accessor(clips[0].samplers[driverChannels[0].sampler].input).flat();
      requireProof(close(times,driverTimes,0),'animation','follower timeline '+part.id);
    }
    let previous;
    for(let i=0;i<times.length;i++) {
      const progress=times[i]/times.at(-1);
      if(part.motion==='translation') {
        const displacement=(1-Math.abs(2*progress-1))*(part.range.min<0 ? part.range.min : part.range.max);
        const expected=part.pivot_m.map((v,k)=>v+part.axis[k]*displacement);
        requireProof(close(values[i],expected,2e-5),'animation',part.id+' translation axis/range');
      } else {
        const scalar=driver.range.min+(driver.range.max-driver.range.min)*progress;
        const value=part.binding.type==='mechanical_follower'?part.range.rest+part.binding.ratio*(scalar-driver.range.rest):scalar;
        const displacement=value-part.range.rest;
        requireProof(previous===undefined||Math.abs(displacement-previous)<Math.PI,'animation',part.id+' undersampled rotation');
        const expected=new Quaternion().setFromAxisAngle(vector(part.axis),displacement).multiply(new Quaternion(...asset.nodes.find(row=>row.id===part.node_id).transform.rotation_xyzw));
        requireProof(values[i].length===4&&Math.abs(Math.hypot(...values[i])-1)<2e-5&&rotationClose(values[i],expected.toArray()),'animation',part.id+' rotation axis/range/rest');
        previous=displacement;
      }
    }
    animationReport.push({part:part.id,clip:clips[0].name,node:entry.index,path,samples:times.length,seconds:times.at(-1),pivot_m:part.pivot_m});
  }
  for(const animation of gltf.animations??[]) {
    requireProof(asset.moving_parts.some(part=>part.binding.type==='clip'&&part.binding.clip_id===animation.name),'animation','undeclared clip');
    for(const channel of animation.channels) {
    requireProof(gltf.nodes[channel.target.node]&&animation.samplers[channel.sampler],'animation','dangling target/sampler');
    const declaredPart=asset.moving_parts.find(p=>indexed.get(p.node_id).index===channel.target.node);
    requireProof(declaredPart,'animation','undeclared animated operational node');
    requireProof(canonicalDriver(declaredPart).binding.clip_id===animation.name,'animation','wrong clip for declared target');
    requireProof(channel.target.path===(declaredPart.motion==='translation'?'translation':'rotation'),'animation','unexpected motion path or animated scale');
    }
  }
  const fixed=asset.fixed_parts.map(part=>{
    const entry=indexed.get(part.node_id),inherited=part.fixed_to_part_id===undefined?undefined:indexed.get(part.fixed_to_part_id)?.index;
    requireProof(entry,'fixed-state','actual fixed node');
    if(part.fixed_to_part_id!==undefined)requireProof(inherited!==undefined&&parents.get(entry.index)===inherited,'fixed-state','direct fixed parent');
    function stationaryBranch(index){
      requireProof(!(gltf.animations??[]).some(a=>a.channels.some(c=>c.target.node===index)),'fixed-state','fixed descendant moves');
      for(const child of gltf.nodes[index].children??[])stationaryBranch(child);
    }
    if(part.fixed_to_part_id!==undefined)stationaryBranch(entry.index);
    let index=entry.index;
    while(index!==undefined){
      if(index!==inherited)requireProof(!(gltf.animations??[]).some(a=>a.channels.some(c=>c.target.node===index)),'fixed-state','physical fixed part moves');
      index=parents.get(index);
    }
    requireProof(part.binding===null||part.binding.type==='operational_state','fixed-state','declared state binding');
    requireProof(trianglesFor(entry.index).some(triangle=>{const area=triangle.getArea();return Number.isFinite(area)&&area>0;}),'fixed-state',part.id+' actual fixed-part triangle mesh');
    const state={id:part.id,state_id:part.binding?.state_id??null,state_bound:part.binding!==null,runtime_integration:'pending T6/T13'};
    return inherited===undefined?{...state,physical_motion:false}:{...state,local_physical_motion:false,inherited_from_part_id:part.fixed_to_part_id};
  });
  function trianglesFor(index) {
    const node=gltf.nodes[index], output=[];
    if(node.mesh!==undefined)for(const primitive of gltf.meshes[node.mesh].primitives) {
      const positions=accessor(primitive.attributes.POSITION),indices=accessor(primitive.indices).flat();
      for(let i=0;i<indices.length;i+=3)output.push(new Triangle(...indices.slice(i,i+3).map(v=>vector(positions[v]).applyMatrix4(matrix(index)))));
    }
    for(const child of node.children??[])output.push(...trianglesFor(child));return output;
  }
  for(const part of asset.moving_parts.filter(row=>row.binding.type==='mechanical_follower')) {
    requireProof(trianglesFor(indexed.get(part.node_id).index).some(triangle=>{const area=triangle.getArea();return Number.isFinite(area)&&area>0;}),'mesh',part.id+' actual renderable follower triangle');
  }
  const sockets=asset.sockets.map(socket=>{
    const parent=indexed.get(socket.node_id).index;
    const socketLocal=new Matrix4().compose(vector(socket.transform.position_m),new Quaternion(...socket.transform.rotation_xyzw),new Vector3(1,1,1));
    const socketWorld=matrix(parent).clone().multiply(socketLocal);
    const point=new Vector3().applyMatrix4(socketWorld),normal=vector(socket.normal).transformDirection(socketWorld);
    let nearest=Infinity, alignment=-1;
    for(const triangle of trianglesFor(parent)) {
      const distance=triangle.closestPointToPoint(point,new Vector3()).distanceTo(point);
      const dot=triangle.getNormal(new Vector3()).dot(normal);
      if(dot>.99&&distance<nearest){nearest=distance;alignment=dot;}
    }
    requireProof(nearest<=.01&&alignment>.99,'socket',socket.id+' actual surface/normal contact');
    return {id:socket.id,world_position_m:point.toArray(),world_normal:normal.toArray(),surface_distance_m:nearest,normal_alignment:alignment,matrix:socketWorld.elements};
  });
  const tilted=sockets.find(s=>s.id==='service_support');requireProof(tilted&&Math.abs(tilted.world_normal[0])+Math.abs(tilted.world_normal[2])>.1,'socket','full quaternion tilted contact');
  function descendants(index) {
    return [index,...(gltf.nodes[index].children??[]).flatMap(descendants)];
  }
  function sampleMatrix(index,target,path,value) {
    const node=gltf.nodes[index];
    const position=index===target&&path==='translation'?value:(node.translation??[0,0,0]);
    const rotation=index===target&&path==='rotation'?value:(node.rotation??[0,0,0,1]);
    const local=new Matrix4().compose(vector(position),new Quaternion(...rotation),new Vector3(1,1,1));
    return parents.has(index)?sampleMatrix(parents.get(index),target,path,value).multiply(local):local;
  }
  function meshPoints(indices,matrixFor) {
    return indices.flatMap(index=>{
      const mesh=gltf.meshes?.[gltf.nodes[index].mesh];
      return (mesh?.primitives??[]).flatMap(primitive=>accessor(primitive.attributes.POSITION).map(p=>vector(p).applyMatrix4(matrixFor(index))));
    });
  }
  const collisions=asset.collision_proxies.map(proxy=>{
    const proxyMatrix=matrix(indexed.get(proxy.node_id).index).clone().multiply(new Matrix4().compose(vector(proxy.transform.position_m),new Quaternion(...proxy.transform.rotation_xyzw),new Vector3(1,1,1)));
    const inverse=proxyMatrix.invert();let points;
    if(proxy.purpose==='body')points=meshPoints([...gltf.nodes.keys()],matrix);
    else {
      const part=asset.moving_parts.find(p=>p.id===proxy.part_id),target=indexed.get(part.node_id).index;
      const clip=gltf.animations.find(a=>a.name===canonicalDriver(part).binding.clip_id),path=part.motion==='translation'?'translation':'rotation';
      const channel=clip.channels.find(c=>c.target.node===target&&c.target.path===path);
      const values=accessor(clip.samplers[channel.sampler].output);
      points=values.flatMap(value=>meshPoints(descendants(target),index=>sampleMatrix(index,target,path,value)));
    }
    requireProof(proxy.purpose!=='moving_sweep'||points.length>0,'collision',proxy.id+' empty actual moving sweep');
    for(const point of points) {
      const local=point.applyMatrix4(inverse).toArray();
      requireProof(local.every((v,i)=>Math.abs(v)<=proxy.size_m[i]/2+.001),'collision',proxy.id+' actual mesh/swept envelope');
    }
    return {id:proxy.id,purpose:proxy.purpose,actual_vertex_samples:points.length,contained:true};
  });
  return {nodes:indexed.size,triangles:parsed.triangles,animations:animationReport,fixed_states:fixed,sockets,collisions,axis_markers:'actual transformed asymmetric mesh + 1m baselines'};
}
