/** Exact source-byte rigid linear handling sweep; separate from durable runtime admission. */
import {readFileSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {build} from 'esbuild';
import {hash,readGlb,requireProof} from '../../../scripts/assets/glb.mjs';
const root=resolve(process.argv[2]),out=resolve(process.argv[3]);
const bundled=await build({entryPoints:[resolve('tests/fixtures/transport/node-entry.ts')],bundle:true,write:false,platform:'node',format:'esm',target:'node24',logLevel:'silent'});
const lib=await import(`data:text/javascript;base64,${Buffer.from(bundled.outputFiles[0].contents).toString('base64')}`);
const bytes=readFileSync(resolve(root,'public/assets/steelworks/transport/manifest-candidate.json')),manifest=lib.assetManifestShape.parse(JSON.parse(bytes)),rows=[];
const phases=['grip','lift','translate','lower','release','load-grip','load-lift','load-translate','load-lower','load-release'];
const geometry=lib.coilGeometry(lib.retainedMaterial.material.dimensions),cargo=new lib.Mesh(geometry,new lib.MeshStandardMaterial());
const positions=geometry.getAttribute('position'),indices=geometry.index;let signedVolume=0;
for(let i=0;i<indices.count;i+=3){const a=new lib.Vector3().fromBufferAttribute(positions,indices.getX(i)),b=new lib.Vector3().fromBufferAttribute(positions,indices.getX(i+1)),c=new lib.Vector3().fromBufferAttribute(positions,indices.getX(i+2));signedVolume+=a.dot(b.cross(c))/6;}
for(const level of [0,1,2]){
  const loaded=[];
  try{
    for(const key of ['truck-flatbed','crane-yard','receiving-cradle']){const asset=manifest.assets.find(a=>a.id==='steelflow:transport:'+key),lod=asset?.lods.find(l=>l.level===level);requireProof(asset&&lod,'source','priority model missing');const actual=readFileSync(resolve(root,lod.artifact.path));requireProof(hash(actual)===lod.artifact.sha256,'hash',key);const decoded=await lib.loadAsset(asset,lod,{origin:'http://127.0.0.1:43128',read:async()=>actual.buffer.slice(actual.byteOffset,actual.byteOffset+actual.byteLength)});decoded.scene.name=asset.id;if(key==='receiving-cradle')decoded.scene.position.z=6;loaded.push(decoded);}
    const frames=[];
    for(const phase of phases){const first=lib.geometryFrame(phase,0),last=lib.geometryFrame(phase,1);for(const l of loaded)lib.applySourceGeometry(l,first);const before=lib.decodedFrames(loaded.map(l=>l.scene),first.material);for(const l of loaded)lib.applySourceGeometry(l,last);const after=lib.decodedFrames(loaded.map(l=>l.scene),last.material);const swept=lib.continuousCoilSweep(before,after);frames.push({phase,first,last,...swept});}
    const contacts=[];
    for(const phase of ['lift','lower','load-lift','load-lower'])for(const progress of [0,1]){const frame=lib.geometryFrame(phase,progress);for(const l of loaded)lib.applySourceGeometry(l,frame);cargo.position.fromArray(frame.material);cargo.updateMatrixWorld(true);const hook=loaded.find(l=>l.asset.kind==='crane'),support=loaded.find(l=>l.asset.kind===(frame.material[2]===0?'truck':'receiving-cradle'));const borePoint=[0,frame.material[1]+.3,frame.material[2]],bottomPoint=[0,frame.material[1]-.6,frame.material[2]];contacts.push({phase,progress,root:frame.material,machineBore:lib.surface(hook.scene,borePoint,[0,1,0]),materialBore:lib.surface(cargo,borePoint,[0,-1,0]),...(frame.hoist===0?{machineBottom:lib.surface(support.scene,bottomPoint,[0,1,0]),materialBottom:lib.surface(cargo,bottomPoint,[0,-1,0])}:{})});}
    rows.push({lod:level,frames,contacts});
  }finally{for(const l of loaded)l.dispose();}
}
const hitCount=rows.flatMap(r=>r.frames.flatMap(f=>f.hits)).length,contactBad=rows.flatMap(r=>r.contacts).flatMap(c=>Object.entries(c).filter(([k])=>k.startsWith('machine')||k.startsWith('material')).filter(([,v])=>v.distance>.01));
const result={status:hitCount===0&&contactBad.length===0?'SOURCE_LINEAR_SWEEP_PASS_RUNTIME_ADMISSION_PENDING':'SOURCE_PHYSICAL_RED',authority:'actual decoded equipment GLBs + separate exact-version source QA coil; NOT installed product material or T58/T16 runtime',manifestSha256:hash(bytes),bundledCurrentToolSha256:hash(bundled.outputFiles[0].contents),material:{source:lib.retainedMaterial,vertexCount:positions.count,triangleCount:indices.count/3,signedVolumeM3:signedVolume,analyticVolumeM3:Math.PI*.27,geometrySha256:hash(Buffer.from(positions.array.buffer)),topologyUnchangedAcrossAllFrames:true,rootScale:[1,1,1]},hitCount,contactBad,rows};
writeFileSync(out,JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({status:result.status,hitCount,contactBad:contactBad.length,sourceHash:result.manifestSha256}));geometry.dispose();cargo.material.dispose();process.exitCode=hitCount||contactBad.length?1:0;
