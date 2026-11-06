import {defineConfig,mergeConfig} from 'vite';
import {resolve} from 'node:path';
import {realpathSync,readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import base from '../../../vite.config';

if(!process.env.STEELFLOW_QA_FINISHING_ROOT||!process.env.STEELFLOW_FINISHING_RUN_DIR)throw new Error('Explicit owned finishing source and run roots required');
const source=realpathSync(process.env.STEELFLOW_QA_FINISHING_ROOT),evidence=realpathSync(process.env.STEELFLOW_FINISHING_EVIDENCE_BASE??resolve('.omo/evidence/uniform-fidelity/uf-20261030-resume06/task-21'));
if(!source.startsWith(evidence+'/'))throw new Error('Finishing candidate must be an owned immutable evidence root');
const bytes=readFileSync(resolve(source,'public/assets/steelworks/finishing/manifest.json'));
if(createHash('sha256').update(bytes).digest('hex')!==process.env.STEELFLOW_FINISHING_EXPECTED_SHA)throw new Error('Wrong pinned finishing manifest SHA');
const manifest=JSON.parse(bytes.toString('utf8')),owners=manifest.assets.map((a:{placement_ids:string[];family:string;lods:{level:number}[]})=>{if(a.family!=='finishing'||a.lods.length!==3||a.lods.some((l,i)=>l.level!==i))throw new Error('Wrong family or LOD set');return a.placement_ids[0]?.replace('equipment:','');}).sort();
if(JSON.stringify(owners)!==JSON.stringify((process.env.STEELFLOW_FINISHING_EXPECTED_OWNERS??'').split(',').sort()))throw new Error('Wrong independently selected owner set');
export default mergeConfig(base,defineConfig({publicDir:resolve(source,'public'),cacheDir:resolve(process.env.STEELFLOW_FINISHING_RUN_DIR,'vite-cache'),build:{rollupOptions:{input:resolve('tests/fixtures/finishing/index.html')}}}));
