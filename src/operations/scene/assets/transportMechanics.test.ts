import {describe,expect,it} from 'vitest';
import {z} from 'zod';
import casesSource from '../../../../shared/fixtures/transport-mechanics-cases.json';
import source from '../../../../tests/fixtures/transport/transport-mechanism-manifest.json';
import {parseProductionAssetManifest} from './manifest';
import type {Asset} from './manifest';
import {validateTransportMechanics} from './transportMechanics';
const fixture=z.strictObject({format:z.literal('transport-mechanism-test-manifest-v1'),source_manifest_sha256:z.literal('4e2446f73a8b44430adf2c47b0b672ad719709378e34d91ccd67b45b0dee80f0'),selected_asset_ids:z.array(z.string()).length(7),manifest:z.unknown()}).parse(source);
const manifest=parseProductionAssetManifest(JSON.stringify(fixture.manifest));
const golden=z.strictObject({schema_version:z.literal(1),qualification:z.string(),cases:z.array(z.strictObject({id:z.string(),asset_id:z.string(),patches:z.array(z.strictObject({path:z.array(z.union([z.string(),z.number()])),value:z.json()})),expected:z.literal('transport_mechanics')}))}).parse(casesSource);
type Json=null|boolean|number|string|Json[]|{[key:string]:Json};
function patch(input:unknown,patches:typeof golden.cases[number]['patches']):unknown{
 const root:Json=JSON.parse(JSON.stringify(input));
 for(const change of patches){let cursor=root;for(const key of change.path.slice(0,-1)){if(cursor===null||typeof cursor!=='object')throw new Error('invalid fixture path');const next=Array.isArray(cursor)?cursor[Number(key)]:cursor[String(key)];if(next===undefined)throw new Error('missing fixture path');cursor=next;}const key=change.path.at(-1);if(key===undefined||cursor===null||typeof cursor!=='object')throw new Error('invalid fixture leaf');if(Array.isArray(cursor))cursor[Number(key)]=change.value;else cursor[String(key)]=change.value;}
 return root;
}
describe('sealed seven transport mechanisms — metadata only, no decoded geometry claim',()=>{
 it('accepts exact captured seven metadata assemblies and ignores legacy identities',()=>{expect(manifest.assets.map(a=>a.id)).toEqual(fixture.selected_asset_ids);expect(manifest.assets.filter(a=>validateTransportMechanics(a))).toHaveLength(7);expect(validateTransportMechanics({...manifest.assets[0]!,id:'legacy:truck' as Asset['id']})).toBeUndefined();});
 for(const row of golden.cases)it(`rejects metadata ${row.id}`,()=>{const original=manifest.assets.find(a=>a.id===row.asset_id);expect(original).toBeDefined();expect(()=>validateTransportMechanics(patch(original,row.patches) as Asset)).toThrow(/transport_mechanics/);});
});
