import { readFileSync } from 'node:fs';
import { readGlb, validateAssetGlb } from '../../../scripts/assets/glb.mjs';

try {
  const input = JSON.parse(readFileSync(process.argv[2], 'utf8'));
  validateAssetGlb(input.asset, readGlb(readFileSync(input.bytesPath)), { axis_origin: [0, 0, 0], axis_front: [1, 0, 0], axis_up: [0, 1, 0], axis_side: [0, 0, -1] });
  console.log('ACTUAL_MUTANT_ACCEPTED');
} catch (error) {
  if (!(error instanceof Error)) throw error;
  console.error(error.message); process.exitCode = 1;
}
