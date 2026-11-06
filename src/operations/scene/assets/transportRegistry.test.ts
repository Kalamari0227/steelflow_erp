import {expect,it} from 'vitest';
import {z} from 'zod';
import baselineSource from '../../../../tests/fixtures/transport/transport-registry-baseline.json';
import requirements from '../../../../shared/asset-requirements.json';
import coverage from '../../../../shared/coverage-registry.json';
import motion from '../../../../shared/motion-recipes.json';
import {parseMotionRegistryValue} from '../motion/contracts';
import type {MotionRegistry} from '../motion/contracts';
type Mutable<T>={-readonly[P in keyof T]:Mutable<T[P]>};
const mutableMotion:Mutable<MotionRegistry>=JSON.parse(JSON.stringify(motion));

const jsonRows=z.array(z.json());
const baseline=z.strictObject({format:z.literal('transport-registry-baseline-v1'),source_sha256:z.strictObject({'asset-requirements.json':z.string().regex(/^[a-f0-9]{64}$/),'coverage-registry.json':z.string().regex(/^[a-f0-9]{64}$/),'motion-recipes.json':z.string().regex(/^[a-f0-9]{64}$/)}),projections:z.strictObject({asset_requirements:z.strictObject({policies:jsonRows,existing_bindings:jsonRows,planned_bindings:jsonRows}),coverage:z.strictObject({source_requirements:jsonRows,observed_inventory:z.json()}),motion:z.strictObject({recipe_identities:z.array(z.strictObject({id:z.string(),semantic_id:z.string(),source_step_ids:z.array(z.string()),compiled_step_ids:z.array(z.string()),binding_status:z.literal('pending_delivery')})),applicability:jsonRows})})}).parse(baselineSource).projections;
const addedIds=['scope:fleet:dump-truck','scope:fleet:ship-bulk','scope:fleet:overhead-crane','scope:fleet:port-crane','scope:fleet:railcar-coil','scope:fleet:railcar-bulk','scope:handling:receiving-cradle'];
it('preserves all old policy and variant rows byte-for-value while adding exact four and seven',()=>{
 const old=baseline.asset_requirements;
 expect(requirements.policies.slice(0,old.policies.length)).toEqual(old.policies);
 expect(requirements.existing_bindings.slice(0,old.existing_bindings.length)).toEqual(old.existing_bindings);
 expect(requirements.policies.slice(old.policies.length).map(p=>p.id)).toEqual(['policy:fleet:dump-truck','policy:fleet:overhead-crane','policy:fleet:port-crane','policy:campus:receiving-cradle:coil-v1']);
 expect(requirements.planned_bindings.slice(0,old.planned_bindings.length)).toEqual(old.planned_bindings);
 expect(requirements.planned_bindings.length-old.planned_bindings.length).toBe(7);
});
it('keeps source and compiled denominator identities, pending status, and exact current motion registry valid',()=>{
 const old=baseline.motion;
 const beforeCoverage=baseline.coverage;
 expect(motion.recipes).toHaveLength(243);expect(coverage.source_requirements).toHaveLength(179);expect(coverage.approved_scope_requirements).toHaveLength(155);
 expect(coverage.source_requirements).toEqual(beforeCoverage.source_requirements);
 expect(coverage.observed_inventory).toEqual(beforeCoverage.observed_inventory);
 expect(motion.recipes.map(r=>[r.id,r.semantic_id,r.source_step_ids,r.compiled_step_ids,r.binding_status])).toEqual(old.recipe_identities.map(r=>[r.id,r.semantic_id,r.source_step_ids,r.compiled_step_ids,r.binding_status]));
 expect(motion.recipes.every(r=>r.binding_status==='pending_delivery')).toBe(true);
 expect(motion.applicability.slice(0,old.applicability.length)).toEqual(old.applicability);
 const appended=motion.applicability.slice(old.applicability.length);
 expect(appended.filter(a=>a.kind==='requirement').map(a=>a.reference_id).sort()).toEqual([...addedIds].sort());
 expect(appended.filter(a=>a.kind==='fleet').map(a=>a.reference_id).sort()).toEqual(addedIds.slice(0,6).sort());
 expect(appended).toHaveLength(13);expect(new Set(motion.applicability.map(a=>`${a.kind}:${a.reference_id}`)).size).toBe(motion.applicability.length);
 expect(parseMotionRegistryValue(motion).recipes).toHaveLength(243);
});
it('rejects missing, wrong-family, duplicate applicability and missing alternative function',()=>{
 const missing=structuredClone(mutableMotion);missing.applicability=missing.applicability.filter(r=>r.reference_id!=='scope:handling:receiving-cradle');expect(()=>parseMotionRegistryValue(missing)).toThrow();
 const wrong=structuredClone(mutableMotion),row=wrong.applicability.find(r=>r.reference_id==='scope:fleet:dump-truck')!;row.recipe_ids=['motion:scope:sea:load'];expect(()=>parseMotionRegistryValue(wrong)).toThrow();
 const duplicate=structuredClone(mutableMotion);duplicate.applicability.push(duplicate.applicability.at(-1)!);expect(()=>parseMotionRegistryValue(duplicate)).toThrow();
 const absent=structuredClone(mutableMotion),recipe=absent.recipes.find(r=>r.policy_ids.includes('policy:fleet:dump-truck'))!;recipe.functions=recipe.functions.filter(f=>f.policy_id!=='policy:fleet:dump-truck');expect(()=>parseMotionRegistryValue(absent)).toThrow();
});
