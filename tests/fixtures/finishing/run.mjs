/** Isolated real Chrome fixture runner. It never starts an API or touches a DB. */
import {parseArgs} from 'node:util';
import {readFileSync,mkdirSync,realpathSync} from 'node:fs';
import {resolve} from 'node:path';
import {hash,snapshot,processOwner,json} from '../../../tools/qa/runtime.mjs';
import {choosePorts,createOwnedEvidenceDirectory} from '../../../tools/qa/ownership.mjs';

const {values}=parseArgs({options:{root:{type:'string'},'expected-sha':{type:'string'},owners:{type:'string'},evidence:{type:'string'},grep:{type:'string'},project:{type:'string'},'stop-at':{type:'string'}}});
for(const key of ['root','expected-sha','owners','evidence','grep'])if(!values[key])throw new Error('Missing explicit finishing runner argument '+key);
const root=realpathSync(values.root),evidence=resolve(values.evidence),base=realpathSync('.omo/evidence/uniform-fidelity/uf-20261030-resume06/task-21');
const project=values.project?realpathSync(values.project):resolve('.');
if(values.project&&!project.startsWith(base+'/'))throw new Error('Isolated combined source must be an owned T21 snapshot');
if(!root.startsWith(base+'/')||!evidence.startsWith(base+'/'))throw new Error('Owned T21 root required');
const raw=readFileSync(resolve(root,'public/assets/steelworks/finishing/manifest.json'));
if(hash(raw)!==values['expected-sha'])throw new Error('Preflight candidate SHA mismatch before any process');
const prep=JSON.parse(readFileSync('.omo/evidence/uniform-fidelity/uf-20261030-resume06/task-21/preparation/inventory.json','utf8')),selected=values.owners.split(',');
if(new Set(selected).size!==selected.length||selected.some(id=>!prep.rows.some(r=>r.owner_id===id)))throw new Error('Unknown/duplicate owner from independent prep');
const actual=JSON.parse(raw).assets;
if(JSON.stringify(actual.map(a=>a.placement_ids[0].replace('equipment:','')).sort())!==JSON.stringify([...selected].sort())||actual.some(a=>a.family!=='finishing'||a.lods.length!==3))throw new Error('Preflight actual family/owner/LOD mismatch');
const stopAt=values['stop-at']?Date.parse(values['stop-at']):null;if(stopAt!==null&&(!Number.isFinite(stopAt)||stopAt<=Date.now()))throw new Error('Owned QA stop-at must be a future UTC deadline');
createOwnedEvidenceDirectory(evidence);json(resolve(evidence,'invocation.json'),{argv:process.argv,root,manifestSha256:values['expected-sha'],owners:selected,startedAt:new Date().toISOString(),stopAt:values['stop-at']??null,productClaim:false});
const ports=await choosePorts(),env={...process.env,STEELFLOW_QA_FINISHING_ROOT:root,STEELFLOW_FINISHING_RUN_DIR:evidence,STEELFLOW_FINISHING_WEB_PORT:String(ports.web),STEELFLOW_FINISHING_EXPECTED_SHA:values['expected-sha'],STEELFLOW_FINISHING_EXPECTED_OWNERS:values.owners,STEELFLOW_FINISHING_EVIDENCE_BASE:base};
const owner=processOwner(evidence,env),sourcePaths=['assets/source/finishing','tests/fixtures/finishing','tests/assets/finishing.spec.ts','shared','src/operations/scene/assets','src/operations/scene/motion'].map(p=>resolve(project,p)),before=snapshot(sourcePaths);let code=1,failure=null;
json(resolve(evidence,'source-before.json'),before);json(resolve(evidence,'ports.json'),{web:ports.web,apiStarted:false,protectedPortsTouched:false});
const abort=()=>void owner.cleanup();process.on('SIGINT',abort);process.on('SIGTERM',abort);
let budgetReached=false;const budgetTimer=stopAt===null?null:setTimeout(()=>{budgetReached=true;void owner.cleanup();},Math.max(1,stopAt-Date.now()));
try{
  const server=owner.start(process.execPath,[resolve('node_modules/vite/bin/vite.js'),'--config',resolve(project,'tests/fixtures/finishing/vite.config.mts'),'--host','127.0.0.1','--port',String(ports.web),'--strictPort'],{cwd:project});
  let ready=false;for(let i=0;i<120;i++){if(server.exit_code!==null||server.error||server.signal)throw new Error('Owned fixture server exited');try{const response=await fetch(`http://127.0.0.1:${ports.web}/tests/fixtures/finishing/index.html`);if(response.ok){ready=true;break;}}catch(error){if(!(error instanceof TypeError))throw error;}await new Promise(r=>setTimeout(r,250));}if(!ready)throw new Error('Owned fixture readiness timeout');
  await owner.execute(process.execPath,[resolve('node_modules/@playwright/test/cli.js'),'test','--config',resolve(project,'tests/fixtures/finishing/playwright.config.mts'),'--grep',values.grep,'--workers=1','--retries=0'],{cwd:project});if(budgetReached)throw new Error('Owned QA stop-at reached');code=0;
}catch(error){failure=error instanceof Error?error.message:String(error);console.error(failure);}
finally{if(budgetTimer!==null)clearTimeout(budgetTimer);const stopped=await owner.cleanup(),after=snapshot(sourcePaths),unchanged=JSON.stringify(before)===JSON.stringify(after);json(resolve(evidence,'source-after.json'),after);if(!unchanged){code=1;failure=(failure??'')+' Source changed during actual verification';}json(resolve(evidence,'exit.json'),{exitCode:code,failure,budgetReached,sourceUnchanged:unchanged,finishedAt:new Date().toISOString()});json(resolve(evidence,'cleanup.json'),{processes:stopped,protectedPortsTouched:false});process.removeListener('SIGINT',abort);process.removeListener('SIGTERM',abort);}
process.exitCode=code;
