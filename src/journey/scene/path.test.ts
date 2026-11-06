import { describe, expect, it } from 'vitest';
import { makeLine, phasePosition, projectedPhase, stepPose } from './path';

describe('continuous manufacturing route', () => {
  it.each([5, 8, 12, 15])('keeps every %i-step station on the tracked material path', count => {
    const line = makeLine(count);
    line.stations.forEach((station, index) => {
      const point = line.curve.getPoint(phasePosition(index, 0.5, count));
      expect(point.x).toBeCloseTo(station.position[0], 8);
      expect(point.z).toBeCloseTo(station.position[2], 8);
    });
  });
  it('does not teleport at a server-approved step boundary including U turns', () => {
    const count = 12; const line = makeLine(count);
    for (let index = 0; index < count - 1; index++) {
      const departure = line.curve.getPoint(phasePosition(index, 1, count));
      const arrival = line.curve.getPoint(phasePosition(index + 1, 0, count));
      expect(departure.distanceTo(arrival)).toBe(0);
    }
  });
  it('keeps cargo exactly on the truck anchor throughout inbound and outbound transport', () => {
    const line = makeLine(9);
    for (const index of [0, 8]) {
      const station = line.stations[index];
      if (!station) throw new Error('Fixture requires both transport stations');
      for (const phase of [0, 0.2, 0.5, 0.8, 1]) {
        const pose = stepPose(line, index, phase);
        const x = station.position[0] + Math.cos(station.rotation) * pose.localX + Math.sin(station.rotation) * pose.localZ;
        const z = station.position[2] - Math.sin(station.rotation) * pose.localX + Math.cos(station.rotation) * pose.localZ;
        expect(x).toBeCloseTo(pose.position.x, 10);
        expect(z).toBeCloseTo(pose.position.z, 10);
        expect(station.rotation + pose.localRotation).toBeCloseTo(pose.rotation, 10);
      }
    }
  });
  it('freezes extrapolation after one polling window even if a request hangs for seconds', () => {
    expect(projectedPhase(1000, 8000, 350, 1)).toBe(projectedPhase(1000, 8000, 8000, 1));
    expect(projectedPhase(1000, 8000, 350, 4)).toBe(projectedPhase(1000, 8000, 8000, 4));
    expect(projectedPhase(1000, 8000, 100, 1)).toBeLessThan(projectedPhase(1000, 8000, 350, 1));
  });
  it('never projects frontend completion beyond the authoritative current step', () => {
    expect(projectedPhase(7990, 8000, 350, 4)).toBe(0.97);
  });
});
