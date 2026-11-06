import { describe, expect, it } from 'vitest';
import policy from '../../../../shared/asset-requirements.json';
import { supportSocketRegistrations } from '../motion/finishingContinuity';
import { parseAssetManifestValue, parseFinishingAssetManifestValue } from './manifest';
import { equipmentExample, fixture, policyExample, required } from './manifestTestFixtures';
import { bindingsFromAssetManifest } from '../motion/assetAdapter';

const bindings = policy.existing_bindings.filter(b => b.allowed_families.includes('finishing'));
function fullFamily() {
  return { ...fixture(), assets: bindings.map(binding => {
    const extension = 'extension_policy_id' in binding ? binding.extension_policy_id : undefined;
    const example = extension === undefined ? equipmentExample(binding.variant) : policyExample(required(policy.policies.find(p => p.id === extension)));
    const asset = required(example.assets[0]);
    asset.id = `example:${binding.variant}`;
    for(const row of supportSocketRegistrations.filter(r=>binding.placement_ids.includes(`equipment:${r.owner_id}`))){
      const seed=required(asset.sockets[0]),parent=row.motion_function_ids[0] ?? asset.root_node_id;
      asset.sockets.push({...seed,id:row.socket_id,node_id:parent,role:'support',forms:[row.family]});
      for(const lod of asset.lods)lod.socket_ids.push(row.socket_id);
      if(asset.cutaway.roof_node_ids.length)Object.assign(asset.cutaway,{retained_socket_ids:[...asset.cutaway.retained_socket_ids,row.socket_id]});
    }
    return asset;
  }) };
}
function giProfile() {
  return policyExample(required(policy.policies.find(p => p.id === 'policy:equipment:finishing:CS-GI-05:v1')));
}

describe('new finishing completeness is separate from legacy admission', () => {
  it('admits all 42 explicit alternatives and 16 base assets together', () => {
    // Given / When
    const parsed = parseFinishingAssetManifestValue(fullFamily());
    // Then
    expect(parsed.assets).toHaveLength(58);
    expect(parsed.assets.filter(a => a.motion_policy_id !== undefined)).toHaveLength(42);
  });

  it('admits untouched GI base without the newly registered cooling state', () => {
    // Given / When
    const parsed = parseAssetManifestValue(equipmentExample('variant:galvanizing:CS-GI-05'));
    // Then
    expect(parsed.assets[0]?.motion_policy_id).toBeUndefined();
    expect(parsed.assets[0]?.fixed_parts.some(p => p.function === 'coating_cooling')).toBe(false);
  });

  it('projects only the explicitly selected policy to the existing binding field', () => {
    // Given
    const raw = giProfile(), asset = required(raw.assets[0]);
    // When
    const result = bindingsFromAssetManifest(raw, [{ owner_id: 'CS-GI-05', asset_id: asset.id, socket_families: Object.fromEntries(asset.sockets.map(s => [s.id, required(s.forms[0])])) }]);
    // Then
    expect(result[0]?.policy_id).toBe('policy:equipment:finishing:CS-GI-05:v1');
    expect(result[0]?.functions.map(f => f.function_id)).toContain('coating_cooling');
  });

  for (const value of [null, 'unknown', 'policy:equipment:finishing:CS-HGI-05:v1']) it(`rejects manifest choice ${value}`, () => {
    // Given
    const raw = giProfile();
    Object.assign(required(raw.assets[0]), { motion_policy_id: value });
    // When / Then
    expect(() => parseAssetManifestValue(raw)).toThrow();
  });

  it('rejects an extension-only part when the manifest omits its opt-in', () => {
    // Given
    const raw = giProfile();
    Reflect.deleteProperty(required(raw.assets[0]), 'motion_policy_id');
    // When / Then
    expect(() => parseAssetManifestValue(raw)).toThrow('requirements:');
  });

  it('rejects omission in a new complete family even if the individual base asset remains valid', () => {
    // Given
    const raw = fullFamily(), index = raw.assets.findIndex(a => a.variant === 'variant:galvanizing:CS-GI-05');
    raw.assets[index] = required(equipmentExample('variant:galvanizing:CS-GI-05').assets[0]);
    // When / Then
    expect(() => parseAssetManifestValue(raw)).not.toThrow();
    expect(() => parseFinishingAssetManifestValue(raw)).toThrow('finishing-profile');
  });

  it('retains base canonical parts while allowing different registered extensions of one kind', () => {
    // Given
    const gi = required(giProfile().assets[0]);
    const ga = required(equipmentExample('variant:galvanizing:CS-GA-05').assets[0]);
    // When / Then
    expect(() => parseAssetManifestValue({ ...fixture(), assets: [gi, ga] })).not.toThrow();
  });
});

for(const mode of ['wrong-owner','wrong-family','wrong-chain','forged-extra','missing-base'] as const)it(`keeps registered owner support sockets closed: ${mode}`,()=>{
  const manifest=fullFamily(),asset=required(manifest.assets.find(a=>a.placement_ids.includes('equipment:CS-GO-05'))),socket=required(asset.sockets.find(s=>s.id==='line_strip_support'));
  if(mode==='wrong-owner')socket.id='cold_nip_support';
  if(mode==='wrong-family')socket.forms=['COIL'];
  if(mode==='wrong-chain')socket.node_id=asset.root_node_id;
  if(mode==='forged-extra')socket.id='line_forged_support';
  if(mode==='missing-base')asset.sockets=asset.sockets.filter(s=>s.id!=='entry');
  expect(()=>parseAssetManifestValue(manifest)).toThrow();
});
it('permits registered extra omissions only in ordinary legacy admission',()=>{
  const manifest=fullFamily(),asset=required(manifest.assets.find(a=>a.placement_ids.includes('equipment:CS-GO-05')));
  asset.sockets=asset.sockets.filter(s=>s.id!=='line_strip_support');
  for(const lod of asset.lods)lod.socket_ids=lod.socket_ids.filter(id=>id!=='line_strip_support');
  asset.cutaway.retained_socket_ids=asset.cutaway.retained_socket_ids.filter(id=>id!=='line_strip_support');
  expect(()=>parseAssetManifestValue(manifest)).not.toThrow();
  expect(()=>parseFinishingAssetManifestValue(manifest)).toThrow('finishing-support');
});
