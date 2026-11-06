import { z } from 'zod';
import { requireContract } from './worldContractJson';

export const CONTACT_TOLERANCE_M = 0.01;
export const EPOCH_MS = 1793318400000;
export const DATE_LIMIT_MS = 8640000000000000;
export const finiteNumber = z.number().finite();
export const safeMilliseconds = z.number().int().nonnegative().max(Number.MAX_SAFE_INTEGER).brand('SimMilliseconds');
export const pointSchema = z.tuple([finiteNumber, finiteNumber, finiteNumber]).readonly();
export const sizeSchema = z.tuple([finiteNumber.positive(), finiteNumber.positive(), finiteNumber.positive()]).readonly();
export const poseSchema = z.strictObject({ position: pointSchema, yaw_rad: finiteNumber }).readonly();
export type Point = z.infer<typeof pointSchema>;
export type Pose = z.infer<typeof poseSchema>;

export function transformPoint(point: Point, pose: Pose): Point {
  const local = pointSchema.parse(point), parent = poseSchema.parse(pose);
  const c = Math.cos(parent.yaw_rad), s = Math.sin(parent.yaw_rad);
  return pointSchema.parse([parent.position[0] + c * local[0] + s * local[2], parent.position[1] + local[1], parent.position[2] - s * local[0] + c * local[2]]);
}
export function composePose(local: Pose, parent: Pose): Pose {
  return poseSchema.parse({ position: transformPoint(local.position, parent), yaw_rad: parent.yaw_rad + local.yaw_rad });
}
export function mmToM(value: number): number { return finiteNumber.positive().parse(value) / 1000; }
export function supportPose(socketWorld: Point, localSupport: Point, yawRad: number): Pose {
  const socket = pointSchema.parse(socketWorld);
  const offset = transformPoint(localSupport, poseSchema.parse({ position: [0, 0, 0], yaw_rad: yawRad }));
  return poseSchema.parse({ position: [socket[0] - offset[0], socket[1] - offset[1], socket[2] - offset[2]], yaw_rad: yawRad });
}
export function distance(a: Point, b: Point): number { return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]); }
export function contactDistance(materialPose: Pose, localSupport: Point, socketWorld: Point): number {
  return finiteNumber.parse(distance(transformPoint(localSupport, materialPose), pointSchema.parse(socketWorld)));
}
export function contactWithinTolerance(materialPose: Pose, localSupport: Point, socketWorld: Point): boolean {
  return contactDistance(materialPose, localSupport, socketWorld) <= CONTACT_TOLERANCE_M;
}
export function businessEpochMs(simMs: number): number {
  const result = EPOCH_MS + safeMilliseconds.parse(simMs) * 60;
  requireContract(result <= DATE_LIMIT_MS, 'time_range', String(simMs));
  return result;
}
export function wallToSimMs(wallMs: number, speed: number): number {
  const elapsed = safeMilliseconds.parse(wallMs), factor = safeMilliseconds.parse(speed);
  requireContract(factor === 1 || factor === 2 || factor === 4, 'speed', String(speed));
  return safeMilliseconds.parse(elapsed * factor);
}
export function phaseAt(simMs: number, startMs: number, endMs: number): number {
  const now = safeMilliseconds.parse(simMs), start = safeMilliseconds.parse(startMs), end = safeMilliseconds.parse(endMs);
  requireContract(end > start, 'time_interval', `${start}:${end}`);
  return Math.min(1, Math.max(0, (now - start) / (end - start)));
}
export function insideEnvelope(point: Point, pose: Pose, size: Point): boolean {
  const delta: Point = [point[0] - pose.position[0], point[1] - pose.position[1], point[2] - pose.position[2]];
  const local = transformPoint(delta, { position: [0, 0, 0], yaw_rad: -pose.yaw_rad });
  return ([0, 1, 2] as const).every(axis => Math.abs(local[axis]) <= size[axis] / 2 + 1e-12);
}
