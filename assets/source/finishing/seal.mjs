/** Freeze the real current inputs before each independent build invocation. */
import { readFileSync, writeFileSync, readdirSync, statSync } from 'node:fs';
import { resolve, relative } from 'node:path';
import { createHash } from 'node:crypto';
const root=resolve('.'),out=process.argv[2];
if(!out)throw new Error('seal.mjs OUTPUT');
function files(path){return readdirSync(path).flatMap(n=>{const p=resolve(path,n);return statSync(p).isDirectory()?files(p):[p];});}
const sha=p=>createHash('sha256').update(readFileSync(p)).digest('hex');
const paths=[...files(resolve('assets/source/finishing')).filter(p=>/\.(py|mjs|json|txt|md)$/.test(p) && !p.endsWith('/inventory.json') && !p.endsWith('/mechanics.json')),...['scripts/assets/build.py','assets/toolchain.json','shared/asset-requirements.json','shared/coverage-registry.json'].map(p=>resolve(p))].sort();
const inventory=JSON.parse(readFileSync('.omo/evidence/uniform-fidelity/uf-20261030-resume06/task-21/preparation/inventory.json','utf8'));
if(inventory.rows.length!==58 || new Set(inventory.rows.map(r=>r.owner_id)).size!==58)throw new Error('Independent prep owner universe changed');
writeFileSync(out,JSON.stringify({family:'finishing',owner_count:58,lod_count:174,owner_ids:inventory.rows.map(r=>r.owner_id).sort(),inputs:paths.map(p=>({path:relative(root,p),sha256:sha(p)}))},null,2)+'\n');
console.log(sha(out));
