import { describe, expect, it } from 'vitest';
import { chooseLod } from './lod';

describe('LOD hysteresis', () => {
  it('retains the current overview detail inside the hysteresis band', () => {
    // Given / When / Then
    expect(chooseLod(190, 0, false)).toBe(0);
    expect(chooseLod(199, 0, false)).toBe(1);
    expect(chooseLod(170, 1, false)).toBe(1);
    expect(chooseLod(161, 1, false)).toBe(0);
    expect(chooseLod(714, 1, false)).toBe(1);
    expect(chooseLod(716, 1, false)).toBe(2);
    expect(chooseLod(584, 2, false)).toBe(1);
  });
  it('uses the actual source LOD for detail regardless of distance', () => {
    // Given / When / Then
    expect(chooseLod(1000, 2, true)).toBe(0);
    expect(() => chooseLod(Number.NaN, 0, false)).toThrow();
  });
});
