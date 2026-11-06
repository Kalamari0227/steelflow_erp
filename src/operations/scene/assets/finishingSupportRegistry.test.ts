import {expect,it} from 'vitest';
import requirements from '../../../../shared/asset-requirements.json';
import intermediate from '../../../../assets/source/finishing/contracts/intermediate-support-additions.json';
import additions from '../../../../assets/source/finishing/contracts/support-registration-additions.json';
import {supportSocketRegistrations} from '../motion/finishingContinuity';
import {bindingsFromAssetManifest} from '../motion/assetAdapter';
import {parseAssetManifestValue,parseFinishingAssetManifestValue} from './manifest';
import {equipmentExample,fixture,policyExample,required} from './manifestTestFixtures';

/** Metadata fixtures only; real source GLB surfaces remain a separate gate. */
function family(){return {...fixture(),assets:requirements.existing_bindings.filter(b=>b.allowed_families.includes('finishing')).map(binding=>{
  const extension='extension_policy_id'in binding?binding.extension_policy_id:undefined,asset=required((extension===undefined?equipmentExample(binding.variant):policyExample(required(requirements.policies.find(p=>p.id===extension)))).assets[0]);asset.id='support-example:'+binding.variant;
  for(const row of supportSocketRegistrations.filter(r=>binding.placement_ids.includes('equipment:'+r.owner_id))){const seed=required(asset.sockets[0]);asset.sockets.push({...seed,id:row.socket_id,node_id:row.motion_function_ids[0]??asset.root_node_id,role:'support',forms:[row.family]});for(const lod of asset.lods)lod.socket_ids.push(row.socket_id);if(asset.cutaway.roof_node_ids.length)Object.assign(asset.cutaway,{retained_socket_ids:[...asset.cutaway.retained_socket_ids,row.socket_id]});}
  return asset;
})};}
it('admits registered fixed source supports together without making them common to absent mechanisms',()=>{
  // Given: all71 exact source registrations and all58 profile alternatives.
  const raw=family();
  // When
  const parsed=parseFinishingAssetManifestValue(raw);
  // Then
  expect(parsed.assets).toHaveLength(58);expect(supportSocketRegistrations.filter(r=>additions.some(a=>a.owner_id===r.owner_id&&a.socket_id===r.socket_id))).toEqual(additions);
  const projected=bindingsFromAssetManifest(parsed,parsed.assets.map(asset=>({owner_id:required(asset.placement_ids[0]).replace(/^equipment:/,''),asset_id:asset.id,socket_families:Object.fromEntries(asset.sockets.map(s=>[s.id,required(s.forms[0])]))})));
  for(const row of additions){const binding=required(projected.find(b=>b.owner_id===row.owner_id));expect(binding.sockets.find(s=>s.socket_id===row.socket_id)).toMatchObject({family:'STRIP',motion_function_ids:[]});}
});
for(const mode of ['owner','family','chain','missing','forged','base-entry'] as const)it(`rejects unsupported fixed support metadata: ${mode}`,()=>{
  // Given: a complete metadata family with the actual selected cutter host identity.
  const raw=family(),asset=required(raw.assets.find(a=>a.placement_ids.includes('equipment:CS-CR-04'))),socket=required(asset.sockets.find(s=>s.id==='cutter_in_support'));
  // When: one contract boundary is corrupted.
  if(mode==='owner')socket.id='weld_in_support';
  if(mode==='family')socket.forms=['COIL'];
  if(mode==='chain')socket.node_id=required(asset.moving_parts.find(p=>p.function==='output_cutter')).node_id;
  if(mode==='missing')asset.sockets=asset.sockets.filter(s=>s.id!==socket.id);
  if(mode==='forged')socket.id='unregistered_cutter_support';
  if(mode==='base-entry')asset.sockets=asset.sockets.filter(s=>s.id!=='entry');
  // Then: registration cannot hide a wrong moving frame or missing common port.
  expect(()=>parseFinishingAssetManifestValue(raw)).toThrow();
});
it('retains ordinary base-only finishing admission without required extension sockets',()=>{
  // Given / When / Then
  expect(()=>parseAssetManifestValue(equipmentExample('variant:cold_mill:CS-CR-04'))).not.toThrow();
});

it('retains the exact moving intermediate clamp chain for both strip and coil sockets',()=>{
  const parsed=parseFinishingAssetManifestValue(family());for(const row of intermediate){const asset=required(parsed.assets.find(a=>a.placement_ids.some(id=>id==='equipment:'+row.owner_id))),socket=required(asset.sockets.find(s=>s.id===row.socket_id));expect(socket.forms).toEqual([row.family]);expect(socket.node_id).toBe('intermediate_winding_mandrel');}
  const broken=family(),asset=required(broken.assets.find(a=>a.placement_ids.some(id=>id==='equipment:CS-CR-04')));required(asset.sockets.find(s=>s.id==='intermediate_strip_support')).node_id='root';expect(()=>parseFinishingAssetManifestValue(broken)).toThrow();
});
