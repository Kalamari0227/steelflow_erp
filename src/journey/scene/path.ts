import { CatmullRomCurve3, Vector3 } from 'three';

export type Station = { readonly position: readonly [number, number, number]; readonly rotation: number };
export function makeLine(count: number) {
  const rows = count > 10 ? 3 : 2;
  const columns = Math.ceil(count / rows);
  const stations: Station[] = Array.from({ length: count }, (_, index) => {
    const row = Math.floor(index / columns);
    const returning = row % 2 === 1;
    const column = index % columns;
    return { position: [(returning ? columns - column - 1 : column) * 6 - (columns - 1) * 3, 0, row * 8 - (rows - 1) * 4], rotation: returning ? Math.PI : 0 };
  });
  const points: Vector3[] = [];
  const first = stations[0];
  if (first) points.push(new Vector3(first.position[0] - 3, 0.94, first.position[2]));
  stations.forEach((station, index) => {
    points.push(new Vector3(station.position[0], 0.94, station.position[2]));
    const next = stations[index + 1];
    if (next) points.push(new Vector3((station.position[0] + next.position[0]) / 2 + (next.position[2] !== station.position[2] ? Math.cos(station.rotation) * 4 : 0), 0.94, (station.position[2] + next.position[2]) / 2));
    else points.push(new Vector3(station.position[0] + Math.cos(station.rotation) * 3, 0.94, station.position[2]));
  });
  return { stations, curve: new CatmullRomCurve3(points, false, 'catmullrom', 0.15), width: columns * 6 + 8, depth: rows * 8 + 1 };
}

export function phasePosition(index: number, phase: number, count: number) {
  return Math.max(0, Math.min(1, (index + phase) / count));
}

export function stepPose(line: ReturnType<typeof makeLine>, index: number, phase: number) {
  const t = phasePosition(index, phase, line.stations.length);
  const position = line.curve.getPoint(t), tangent = line.curve.getTangent(t);
  const station = line.stations[index];
  const rotation = -Math.atan2(tangent.z, tangent.x), stationRotation = station?.rotation ?? 0;
  const dx = position.x - (station?.position[0] ?? 0), dz = position.z - (station?.position[2] ?? 0);
  return { position, rotation, localX: Math.cos(stationRotation) * dx - Math.sin(stationRotation) * dz, localZ: Math.sin(stationRotation) * dx + Math.cos(stationRotation) * dz, localRotation: rotation - stationRotation };
}

export const MAX_EXTRAPOLATION_MS = 350;
export function projectedPhase(elapsedMs: number, durationMs: number, sinceSnapshotMs: number, speed: number) {
  return Math.min(0.97, (elapsedMs + Math.min(MAX_EXTRAPOLATION_MS, Math.max(0, sinceSnapshotMs)) * speed) / durationMs);
}
