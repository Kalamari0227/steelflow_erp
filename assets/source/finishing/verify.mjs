/** Inspect real family GLBs using the established production parser and T12 geometry oracle. */
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { productionParser } from '../../../scripts/assets/production-parser.mjs';
import { readGlb, validateAssetGlb, requireProof, hash } from './oracle.mjs';
import { localArtifact } from '../../../scripts/assets/verify.mjs';

export async function verifyFamily(root, { stamp = false, expectedSha, expectedOwners, preAdmission = false } = {}) {
  const path = resolve(root, 'public/assets/steelworks/finishing/manifest.json');
  requireProof(expectedSha && hash(readFileSync(path))===expectedSha,'preflight','exact raw manifest SHA');
  const raw = JSON.parse(readFileSync(path, 'utf8'));
  const actualOwners=raw.assets.flatMap(a=>a.placement_ids).map(p=>p.replace('equipment:','')).sort();
  requireProof(expectedOwners?.length && JSON.stringify(actualOwners)===JSON.stringify([...expectedOwners].sort()),'preflight','independently pinned exact owner set');
  requireProof(raw.assets.every(a=>a.family==='finishing' && a.lods.length===3 && a.lods.every((l,i)=>l.level===i)),'preflight','family and exact 3 LOD levels');
  if (stamp) {
    for (const asset of raw.assets) for (const lod of asset.lods) {
      requireProof(lod.semantic_geometry_sha256 === null, 'stamp', 'refuse existing digest');
      lod.semantic_geometry_sha256 = readGlb(localArtifact(root, lod.artifact)).semantic;
    }
    writeFileSync(path, JSON.stringify(raw, null, 2) + '\n');
  }
  const manifest=preAdmission ? JSON.parse(readFileSync(path,'utf8')) : (await productionParser())(readFileSync(path,'utf8'));
  const recipe = JSON.parse(readFileSync(resolve(root, 'assets/source/finishing/recipe.json'), 'utf8'));
  const inventory=JSON.parse(readFileSync(resolve(root,'assets/source/finishing/inventory.json'),'utf8'));
  const tool=JSON.parse(readFileSync(resolve(root,'assets/toolchain.json'),'utf8'));
  requireProof(recipe.external_asset_count===0 && inventory.external_asset_count===0,'license','original family inventory');
  requireProof(tool.version==='4.5.15' && hash(readFileSync(tool.executable_path))===tool.executable_sha256,'toolchain','actual pinned Blender');
  requireProof(hash(readFileSync(tool.tool_license_path))===tool.tool_license_sha256,'license','retained Blender tool license');
  for (const resource of [inventory.license,...inventory.inputs,...inventory.authored_assets,...inventory.textures]) localArtifact(root,resource);
  const results = [];
  for (const asset of manifest.assets) {
    localArtifact(root, asset.source.artifact); localArtifact(root, asset.export.recipe); localArtifact(root, asset.export.tool_artifact);
    for (const resource of [asset.source,...asset.materials,...asset.textures]) {
      requireProof(resource.provenance.origin==='self_created' && resource.provenance.third_party_inputs.length===0,'license','direct family authorship');
      localArtifact(root,resource.provenance.recipe);
    }
    const lods = asset.lods.map(lod => {
      const parsed = readGlb(localArtifact(root, lod.artifact));
      const proof = validateAssetGlb(asset, parsed, recipe.axis_markers);
      requireProof(parsed.semantic === lod.semantic_geometry_sha256, 'semantic', asset.id);
      requireProof(parsed.gltf.materials.length === asset.materials.length, 'materials', 'exact semantic PBR set');
      for (const material of asset.materials) {
        const actual = parsed.gltf.materials.find(m => m.name === material.id && m.extras?.semantic_id === material.id)?.pbrMetallicRoughness;
        requireProof(actual && Math.abs(actual.metallicFactor - material.metallic) < 1e-5 && Math.abs(actual.roughnessFactor - material.roughness) < 1e-5, 'material', material.id);
      }
      return { level: lod.level, semantic: parsed.semantic, ...proof };
    });
    requireProof(lods.length === 3 && lods[0].triangles > lods[1].triangles && lods[1].triangles > lods[2].triangles, 'lod', asset.id);
    results.push({ variant: asset.variant, placements: asset.placement_ids, lods });
  }
  return { status: preAdmission ? 'GEOMETRY_ORACLE_PASS_ADMISSION_PENDING' : 'PASS', variants: results.length, placements: results.flatMap(r => r.placements).length, manifestSha256: hash(readFileSync(path)), assets: results, limits: ['Synthetic family fixture; live business scheduler integration remains outside T21.'] };
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const args = process.argv.slice(2), root = args[args.indexOf('--root') + 1];
    requireProof(args.includes('--root') && root, 'usage', 'verify.mjs --root ROOT [--stamp]');
    console.log(JSON.stringify(await verifyFamily(resolve(root), { stamp: args.includes('--stamp'), expectedSha:args[args.indexOf('--expected-sha')+1], expectedOwners:args[args.indexOf('--expected-owners')+1]?.split(','), preAdmission:args.includes('--pre-admission') }), null, 2));
  } catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; }
}
