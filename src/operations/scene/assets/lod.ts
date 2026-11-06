import { requireAsset } from './errors';
import { visualTokens } from '../visualTokens';
export function chooseLod(distanceM: number, current: 0 | 1 | 2, detail: boolean): 0 | 1 | 2 {
  requireAsset(Number.isFinite(distanceM) && distanceM >= 0, 'binding', 'LOD distance');
  if (detail) return 0;
  const [near, far] = visualTokens.lod.thresholdsM, h = visualTokens.lod.hysteresisRatio;
  if (distanceM > far * (1 + h)) return 2;
  if (distanceM < near * (1 - h)) return 0;
  switch (current) {
    case 0: return distanceM > near * (1 + h) ? 1 : 0;
    case 1: return 1;
    case 2: return distanceM < far * (1 - h) ? 1 : 2;
  }
}
