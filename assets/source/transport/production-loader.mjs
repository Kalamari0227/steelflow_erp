/** Bundle the current product loader in memory; no alternate validation implementation. */
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';
export async function productionLoader(){
  const result=await build({entryPoints:[fileURLToPath(new URL('../../../src/operations/scene/assets/loader.ts',import.meta.url))],bundle:true,write:false,platform:'node',format:'esm',target:'node24',logLevel:'silent'});
  return import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].contents).toString('base64')}`);
}
