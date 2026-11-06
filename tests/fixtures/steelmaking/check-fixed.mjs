import { readFileSync } from 'node:fs';
import { readGlb, validateAssetGlb } from '../../../scripts/assets/glb.mjs';
import { productionParser } from '../../../scripts/assets/production-parser.mjs';
try {
  const input=JSON.parse(readFileSync(process.argv[2],'utf8'));
  const asset=(await productionParser())(JSON.stringify({schema_version:1,purpose:'production',assets:[input.asset]})).assets[0];
  const proof=validateAssetGlb(asset,readGlb(readFileSync(input.bytesPath)),{axis_origin:[0,0,0],axis_front:[1,0,0],axis_up:[0,1,0],axis_side:[0,0,-1]});
  console.log(JSON.stringify(proof.fixed_states));
}catch(error){if(!(error instanceof Error))throw error;console.error(error.message);process.exitCode=1;}
