/** Inspect real family GLBs using the established production parser and T12 geometry oracle. */
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { productionParser } from '../../../scripts/assets/production-parser.mjs';
import { readGlb, validateAssetGlb, requireProof, hash } from '../../../scripts/assets/glb.mjs';
import { localArtifact } from '../../../scripts/assets/verify.mjs';

export async function verifyFamily(root, { stamp = false } = {}) {
  const path = resolve(root, 'public/assets/steelworks/hot-rolling/manifest.json');
  const raw = JSON.parse(readFileSync(path, 'utf8'));
  if (stamp) {
    for (const asset of raw.assets) for (const lod of asset.lods) {
      requireProof(lod.semantic_geometry_sha256 === null, 'stamp', 'refuse existing digest');
      lod.semantic_geometry_sha256 = readGlb(localArtifact(root, lod.artifact)).semantic;
    }
    writeFileSync(path, JSON.stringify(raw, null, 2) + '\n');
  }
  const parse = await productionParser(), manifest = parse(readFileSync(path, 'utf8'));
  const recipe = JSON.parse(readFileSync(resolve(root, 'assets/source/hot-rolling/recipe.json'), 'utf8'));
  const inventory=JSON.parse(readFileSync(resolve(root,'assets/source/hot-rolling/inventory.json'),'utf8'));
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
  return { status: 'PASS', variants: results.length, placements: results.flatMap(r => r.placements).length, manifestSha256: hash(readFileSync(path)), assets: results, limits: ['Synthetic family fixture; live business scheduler integration remains outside T20.'] };
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const args = process.argv.slice(2), root = args[args.indexOf('--root') + 1];
    requireProof(args.includes('--root') && root, 'usage', 'verify.mjs --root ROOT [--stamp]');
    console.log(JSON.stringify(await verifyFamily(resolve(root), { stamp: args.includes('--stamp') }), null, 2));
  } catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; }
}
