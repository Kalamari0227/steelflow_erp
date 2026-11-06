export type OwnedIdentity = {
  readonly attempt_id: string;
  readonly db_fingerprint: string;
  readonly pid: number;
  readonly web_pid: number;
  readonly api_origin: string;
  readonly web_origin: string;
};
export const protectedPorts: readonly number[];
export function assertNoSymlink(path: string): void;
export function assertFreshEvidenceDirectory(path: string): void;
export function createOwnedEvidenceDirectory(path: string): string;
export function verifyOwnedEvidenceDirectory(path: string, token: string | undefined): string;
export function assertAllowedPort(port: unknown): number;
export function fingerprintDatabase(path: string): string;
export function assertOwnedHealth(health: unknown, expected: OwnedIdentity, options?: { readonly verifyWeb?: boolean }): void;
export function portAvailable(port: number): Promise<boolean>;
export function choosePorts(api?: string, web?: string): Promise<{ api: number; web: number; requested: { api: number; web: number }; occupied: { api: number; web: number }[] }>;
