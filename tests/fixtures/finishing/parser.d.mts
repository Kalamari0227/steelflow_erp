import type { AssetManifest } from '../../../src/operations/scene/assets/manifest';
export function productionParser(): Promise<(raw: string) => AssetManifest>;
