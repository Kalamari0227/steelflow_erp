import { describe, expect, it } from 'vitest';
import { composeTransform, materialPose, transformPoint } from './geometry';

describe('full quaternion support geometry', () => {
  it('preserves roll when root yaw composes internal socket rotation', () => {
    // Given: root yaw 90 degrees, socket roll 90 degrees.
    const half = Math.SQRT1_2;
    const root = { position_m: [10, 2, 3], rotation_xyzw: [0, half, 0, half] } as const;
    const local = { position_m: [1, 0, 0], rotation_xyzw: [half, 0, 0, half] } as const;
    // When
    const combined = composeTransform(root, local);
    // Then: local +Y rotates to world +X; local +X rotates to world -Z.
    expect(transformPoint(combined, [0, 1, 0])).toEqual([expect.closeTo(11, 12), expect.closeTo(2, 12), expect.closeTo(2, 12)]);
    expect(transformPoint(combined, [1, 0, 0])).toEqual([expect.closeTo(10, 12), expect.closeTo(2, 12), expect.closeTo(1, 12)]);
  });
  it('keeps the transformed support in contact when material thickness changes', () => {
    // Given: 180-degree roll, support half a meter beneath local center.
    const socket = { position_m: [4, 6, 8], rotation_xyzw: [1, 0, 0, 0] } as const;
    // When
    const pose = materialPose(socket, [0, -0.5, 0]);
    // Then
    expect(pose.position_m).toEqual([4, 5.5, 8]);
    expect(transformPoint(pose, [0, -0.5, 0])).toEqual([4, 6, 8]);
  });
});
