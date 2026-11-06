/** Own every real Chrome/server process; no API or database is started. */
import {parseArgs} from 'node:util';
import {readFileSync,realpathSync} from 'node:fs';
import {resolve} from 'node:path';
import {hash,snapshot,processOwner,json} from '../../../tools/qa/runtime.mjs';
import {choosePorts,createOwnedEvidenceDirectory} from '../../../tools/qa/ownership.mjs';
const {values}=parseArgs({options:{root:{type:'string'},'expected-sha':{type:'string'},evidence:{type:'string'},grep:{type:'string'}}});
for(const key of ['root','expected-sha','evidence','grep'])if(!values[key])throw new Error('Missing explicit argument '+key);
const root=realpathSync(values.root),evidence=resolve(values.evidence),base=realpathSync('.omo/evidence/uniform-fidelity/uf-20261030-resume06/task-28/implementation');
if(!root.startsWith(base+'/')||!evidence.startsWith(base+'/'))throw new Error('Owned T28 source/evidence required');
const raw=readFileSync(resolve(root,'public/assets/steelworks/transport/manifest.json'));if(hash(raw)!==values['expected-sha'])throw new Error('Exact immutable candidate hash mismatch');
const deadline=Date.parse('2026-10-30T18:07:32.983135Z');if(Date.now()>=deadline)throw new Error('T28 checkpoint deadline reached');
createOwnedEvidenceDirectory(evidence);json(resolve(evidence,'invocation.json'),{argv:process.argv,root,sha256:hash(raw),startedAt:new Date().toISOString(),authority:'authored-source-and-actual-product-loader; runtime-handling-pending'});
const ports=await choosePorts(),env={...process.env,STEELFLOW_TRANSPORT_SOURCE:root,STEELFLOW_TRANSPORT_RUN:evidence,STEELFLOW_TRANSPORT_MANIFEST_SHA:values['expected-sha'],STEELFLOW_TRANSPORT_WEB_PORT:String(ports.web)};
const owner=processOwner(evidence,env),paths=['assets/source/transport','tests/fixtures/transport','tests/assets/transport.spec.ts','src/operations/scene/assets','src/operations/scene/motion','shared/asset-requirements.json','shared/asset-manifest.schema.json','shared/coverage-registry.json'].map(p=>resolve(p)),before=snapshot(paths);let code=1,failure=null;
json(resolve(evidence,'source-before.json'),before);json(resolve(evidence,'ports.json'),{web:ports.web,apiStarted:false,databaseStarted:false,protectedPortsTouched:false});
const abort=()=>void owner.cleanup();process.on('SIGINT',abort);process.on('SIGTERM',abort);const stop=setTimeout(abort,deadline-Date.now());
try{const server=owner.start(process.execPath,[resolve('node_modules/vite/bin/vite.js'),'--config',resolve('tests/fixtures/transport/vite.config.mts'),'--host','127.0.0.1','--port',String(ports.web),'--strictPort']);let ready=false;
  for(let i=0;i<120;i++){if(server.exit_code!==null||server.error||server.signal)throw new Error('Owned server terminated');try{const response=await fetch(`http://127.0.0.1:${ports.web}/tests/fixtures/transport/index.html`);if(response.ok){ready=true;break;}}catch(error){if(!(error instanceof TypeError))throw error;}await new Promise(r=>setTimeout(r,250));}if(!ready)throw new Error('Owned server readiness failed');
  await owner.execute(process.execPath,[resolve('node_modules/@playwright/test/cli.js'),'test','--config',resolve('tests/fixtures/transport/playwright.config.mts'),'--grep',values.grep,'--workers=1','--retries=0']);code=0;
}catch(error){failure=error instanceof Error?error.message:String(error);console.error(failure);}
finally{clearTimeout(stop);const stopped=await owner.cleanup(),after=snapshot(paths),unchanged=JSON.stringify(before)===JSON.stringify(after);json(resolve(evidence,'source-after.json'),after);if(!unchanged){code=1;failure=(failure??'')+' imported source changed';}json(resolve(evidence,'exit.json'),{exitCode:code,failure,sourceUnchanged:unchanged,finishedAt:new Date().toISOString()});json(resolve(evidence,'cleanup.json'),{processes:stopped,protectedPortsTouched:false});process.removeListener('SIGINT',abort);process.removeListener('SIGTERM',abort);}
process.exitCode=code;
