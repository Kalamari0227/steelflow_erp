/** Produce actual fixture requests and exercise both public motion CLIs. */
import {build} from 'esbuild';
import {parseArgs} from 'node:util';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {resolve} from 'node:path';
import {spawnSync} from 'node:child_process';
import {hash,snapshot} from '../../../tools/qa/runtime.mjs';
const {values}=parseArgs({options:{root:{type:'string'},'expected-sha':{type:'string'},out:{type:'string'},owners:{type:'string'}}});
for(const k of ['root','expected-sha','out','owners'])if(!values[k])throw new Error('Explicit pinned argument required: '+k);
const root=resolve(values.root),out=resolve(values.out),manifestPath=resolve(root,'public/assets/steelworks/finishing/manifest.json'),raw=readFileSync(manifestPath);if(hash(raw)!==values['expected-sha'])throw new Error('Exact raw manifest SHA required');
mkdirSync(out,{recursive:false});const selected=values.owners.split(','),before=snapshot(['shared','src/operations/scene/motion','src/operations/scene/assets','backend/app/operations'].map(p=>resolve(p)));
const bundle=resolve(out,'fixture-runtime.mjs');
await build({stdin:{contents:"export {phaseRequest,sampleRequest,frames} from './tests/fixtures/finishing/poses.ts';export {parseProductionAssetManifest} from './src/operations/scene/assets/manifest.ts';",resolveDir:resolve('.')},outfile:bundle,bundle:true,platform:'node',format:'esm',target:'node24',packages:'external',plugins:[{name:'exact-raw-json',setup(b){b.onResolve({filter:/\?raw$/},args=>({path:resolve(args.resolveDir,args.path.slice(0,-4)),namespace:'raw-text'}));b.onLoad({filter:/.*/,namespace:'raw-text'},args=>({contents:'export default '+JSON.stringify(readFileSync(args.path,'utf8')),loader:'js'}));}}]});
await build({entryPoints:[resolve('src/operations/scene/motion/cli.ts')],outfile:resolve(out,'motion-cli.mjs'),bundle:true,platform:'node',format:'esm',target:'node24',packages:'external'});
const runtime=await import(bundle),manifest=runtime.parseProductionAssetManifest(raw.toString('utf8')),results=[];
if(manifest.assets.length!==58||manifest.assets.some(a=>a.family!=='finishing'||a.lods.length!==3)||new Set(selected).size!==selected.length||selected.some(o=>!manifest.assets.some(a=>a.placement_ids[0]==='equipment:'+o)))throw new Error('Pinned family/owners/LOD preflight');
for(const asset of manifest.assets.filter(a=>selected.includes(a.placement_ids[0].replace('equipment:',''))))for(const frame of runtime.frames.slice(0,9)){
 const request=runtime.phaseRequest(manifest,asset,frame,values['expected-sha']),input={envelope:request.envelope,context:request.context},name=asset.placement_ids[0].replace('equipment:','')+'-'+frame.name,path=resolve(out,name+'.json');writeFileSync(path,JSON.stringify(input)+'\n');
 const row={name,input_sha256:hash(readFileSync(path)),results:[]};for(const [language,command,args]of [['python',resolve('backend/.venv/bin/python'),['-m','app.operations.motion_cli']],['typescript',process.execPath,[resolve(out,'motion-cli.mjs'),path]]]){const r=spawnSync(command,args,{cwd:resolve('.'),env:{...process.env,PYTHONPATH:resolve('backend'),PYTHONDONTWRITEBYTECODE:'1'},input:language==='python'?readFileSync(path):undefined,encoding:'utf8',timeout:25000});writeFileSync(resolve(out,name+'.'+language+'.stdout.log'),r.stdout??'');writeFileSync(resolve(out,name+'.'+language+'.stderr.log'),r.stderr??'');row.results.push({language,exit_code:r.status,error:r.error?.message??null,response:r.stdout?JSON.parse(r.stdout):null});}
 results.push(row);writeFileSync(resolve(out,'partial.json'),JSON.stringify(results,null,2)+'\n');
}
const after=snapshot(['shared','src/operations/scene/motion','src/operations/scene/assets','backend/app/operations'].map(p=>resolve(p))),unchanged=JSON.stringify(before)===JSON.stringify(after),failed=results.filter(r=>r.results.some(v=>v.exit_code!==0));writeFileSync(resolve(out,'result.json'),JSON.stringify({status:failed.length||!unchanged?'FAIL':'PASS_METADATA_ONLY_NOT_CURVED_GEOMETRY',manifest_sha256:values['expected-sha'],source_before:before,source_after:after,source_unchanged:unchanged,results},null,2)+'\n');console.log(JSON.stringify({cases:results.length,failed:failed.map(r=>({name:r.name,errors:r.results.map(v=>v.response?.error)})),source_unchanged:unchanged}));process.exitCode=failed.length||!unchanged?1:0;
