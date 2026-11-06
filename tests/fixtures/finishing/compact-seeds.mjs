/** Deduplicate identical fixture contexts while preserving every public request. */
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {basename,resolve} from 'node:path';
import {createHash} from 'node:crypto';
import {isDeepStrictEqual} from 'node:util';
const args=process.argv.slice(2),value=k=>args[args.indexOf(k)+1];
for(const key of ['--continuity','--sequence','--out'])if(!args.includes(key)||!value(key))throw new Error('Explicit compact seed argument required: '+key);
const out=resolve(value('--out'));if(existsSync(out))throw new Error('Preserve previous fixture output');
const contexts={},sources=[],hash=b=>createHash('sha256').update(b).digest('hex'),compact={schema_version:1,provenance:{sources,materialized_request_semantics_equal:true},contexts};
for(const [field,key]of [['continuity_cases','--continuity'],['sequence_cases','--sequence']]){const path=resolve(value(key)),bytes=readFileSync(path),source=JSON.parse(bytes);sources.push({path:basename(path),sha256:hash(bytes)});compact[field]=source.cases.map(c=>{const {world,asset_bindings,...rest}=c.request.context,shared={world,asset_bindings},id=hash(JSON.stringify(shared));contexts[id]??=shared;const next={...c,context_id:id,request:{envelope:c.request.envelope,context:rest}};if(!isDeepStrictEqual({...next.request,context:{...next.request.context,...contexts[id]}},c.request))throw new Error('Materialized public request differs: '+c.name);return next;});}
const text=JSON.stringify(compact,null,2)+'\n';writeFileSync(out,text);console.log(JSON.stringify({sha256:hash(text),contexts:Object.keys(contexts).length,continuity:compact.continuity_cases.length,sequence:compact.sequence_cases.length,bytes:Buffer.byteLength(text)}));
