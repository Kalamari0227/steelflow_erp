/** Compile exact current/private source exports; every candidate records its selected code root. */
import {resolve} from 'node:path';
import {build} from 'esbuild';
import {realpathSync as realPath} from 'node:fs';
export async function contractModule(root,entry){
  const repo=realPath(resolve('.')),actual=realPath(resolve(root));
  if(actual!==repo&&!actual.startsWith(resolve(repo,'.omo/evidence/uniform-fidelity/uf-20261030-resume06/task-28/implementation')+'/'))throw new Error('Unowned contract source');
  const result=await build({entryPoints:[resolve(actual,entry)],bundle:true,write:false,platform:'node',format:'esm',target:'node24',logLevel:'silent'});
  return import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].contents).toString('base64')}`);
}
