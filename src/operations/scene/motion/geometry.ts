import type { Point } from '../worldContractMath';

export type Quaternion = readonly [number, number, number, number];
export type Transform = { readonly position_m: Point; readonly rotation_xyzw: Quaternion };

export function normalizeQuaternion(q: Quaternion): Quaternion {
  const magnitude = Math.hypot(...q);
  return Object.freeze([q[0] / magnitude, q[1] / magnitude, q[2] / magnitude, q[3] / magnitude]);
}

export function multiplyQuaternion(a: Quaternion, b: Quaternion): Quaternion {
  const [ax, ay, az, aw] = a, [bx, by, bz, bw] = b;
  return Object.freeze([
    aw * bx + ax * bw + ay * bz - az * by,
    aw * by - ax * bz + ay * bw + az * bx,
    aw * bz + ax * by - ay * bx + az * bw,
    aw * bw - ax * bx - ay * by - az * bz,
  ]);
}

export function rotatePoint(q: Quaternion, point: Point): Point {
  const [x, y, z] = point, [qx, qy, qz, qw] = q;
  const tx = 2 * (qy * z - qz * y), ty = 2 * (qz * x - qx * z), tz = 2 * (qx * y - qy * x);
  return Object.freeze([x + qw * tx + qy * tz - qz * ty, y + qw * ty + qz * tx - qx * tz, z + qw * tz + qx * ty - qy * tx]);
}

export function transformPoint(transform: Transform, point: Point): Point {
  const rotated = rotatePoint(transform.rotation_xyzw, point);
  return Object.freeze([transform.position_m[0] + rotated[0], transform.position_m[1] + rotated[1], transform.position_m[2] + rotated[2]]);
}

export function composeTransform(parent: Transform, local: Transform): Transform {
  return Object.freeze({ position_m: transformPoint(parent, local.position_m), rotation_xyzw: multiplyQuaternion(parent.rotation_xyzw, local.rotation_xyzw) });
}

export function materialPose(socket: Transform, support: Point): Transform {
  const offset = rotatePoint(socket.rotation_xyzw, support);
  return Object.freeze({ position_m: Object.freeze([socket.position_m[0] - offset[0], socket.position_m[1] - offset[1], socket.position_m[2] - offset[2]] satisfies Point), rotation_xyzw: socket.rotation_xyzw });
}
