import { Box3, Mesh, Vector3 } from 'three';
import type { Camera, Scene, WebGLRenderer } from 'three';
import type { World } from '../../contracts';
import type { AssetEntity } from './assets/registry';

/** Explicit QA URL takes priority over the owned QA build's opt-in. DEV alone never enables it. */
export function isQaProbeEnabled(search: string, ownedQaBuild = false): boolean {
  const values = new URLSearchParams(search).getAll('steelflow-qa');
  return values.length === 0 ? ownedQaBuild : values.length === 1 && values[0] === '1';
}
export type QaAuthority = {
  readonly source: 't58-fixed-contract'; readonly runId: string; readonly revision: number;
  readonly bundleHash: string; readonly authoritativeElapsedMs: number; readonly stale: boolean;
};
export type BoundQaNode = { readonly entityId: string; readonly id: string; readonly kind: 'node' | 'part' | 'socket'; readonly matrixWorld: readonly number[]; readonly visible: boolean };
export type BoundQaSample = {
  readonly authority: QaAuthority; readonly sampledAtMs: number; readonly rafSequence: number;
  readonly nodes: readonly BoundQaNode[]; readonly camera: { readonly matrixWorld: readonly number[]; readonly projectionMatrix: readonly number[] };
};
type LegacyQaFrame = {
  readonly gl: WebGLRenderer; readonly scene: Scene; readonly camera: Camera & { readonly zoom: number };
  readonly world: World; readonly elapsedMs: number; readonly reduced: boolean; readonly stale: boolean;
};

/** Counters describe observer work only; renderer/framework matrix work is outside this observer. */
export class QaProbe {
  readonly work = { frames: 0, traversals: 0, serializations: 0, matrixUpdates: 0, boundNodes: 0 };
  private readonly times: number[] = [];
  constructor(readonly enabled: boolean) {}
  observeLegacy(frame: LegacyQaFrame): void {
    if (!this.enabled) return;
    const { gl, scene, camera, world, elapsedMs, reduced, stale } = frame;
    this.work.frames += 1;
    this.times.push(performance.now());
    if (this.times.length > 1200) this.times.shift();
    this.work.serializations += 3;
    gl.domElement.dataset.renderStats = JSON.stringify({ frames: this.work.frames, times: this.times, dpr: gl.getPixelRatio(), calls: gl.info.render.calls, triangles: gl.info.render.triangles, geometries: gl.info.memory.geometries, textures: gl.info.memory.textures });
    this.work.matrixUpdates += 2;
    scene.updateMatrixWorld(true); camera.updateMatrixWorld(true);
    const rect = gl.domElement.getBoundingClientRect();
    let focusStage: string | null = null;
    const picks: object[] = [], materials: object[] = [], contacts: object[] = [], vehicles: object[] = [];
    this.work.traversals += 1;
    scene.traverse(object => {
      const data = object.userData;
      if (typeof data.focusStage === 'string') focusStage = data.focusStage;
      if (typeof data.pickId === 'string' && typeof data.pickKind === 'string') {
        const anchor = object.getWorldPosition(new Vector3());
        const target = anchor.clone();
        if (data.pickKind === 'equipment') target.y += 1;
        if (data.pickKind === 'material') {
          const marker = data.selected ? object.getObjectByName(`material-pick:${data.pickId}`) : undefined;
          if (marker) marker.getWorldPosition(target);
          else {
            let found = false;
            object.traverseVisible(body => { if (!found && body instanceof Mesh) { body.getWorldPosition(target); found = true; } });
          }
        }
        const pickWorld = target.toArray();
        const projected = target.project(camera);
        if (projected.z > -1 && projected.z < 1 && Math.abs(projected.x) <= 1 && Math.abs(projected.y) <= 1) picks.push({ kind: data.pickKind, id: data.pickId, x: rect.left + (projected.x + 1) * rect.width / 2, y: rect.top + (1 - projected.y) * rect.height / 2, world: pickWorld });
        if (data.pickKind === 'vehicle' && typeof data.carrierMode === 'string') vehicles.push({ id: data.pickId, position: anchor.toArray(), matrixWorld: object.matrixWorld.toArray(), mode: data.carrierMode });
        const bodyBounds = new Box3();
        if (data.pickKind === 'material') for (const kind of ['flat', 'coil', 'liquid']) { const body = object.getObjectByName(`body-${kind}:${data.pickId}`); if (body?.visible) bodyBounds.union(new Box3().setFromObject(body)); }
        if (data.pickKind === 'material') materials.push({ bodyBounds: { min: bodyBounds.min.toArray(), max: bodyBounds.max.toArray() }, id: data.pickId, worldRunId: data.worldRunId, worldRevision: data.worldRevision, form: data.form, versionId: data.versionId, position: anchor.toArray(), phase: data.phase, equipmentId: data.equipmentId, custody: data.custody, matrixWorld: object.matrixWorld.toArray() });
      }
      if (typeof data.contactKind === 'string') contacts.push({ equipmentId: data.equipmentId, kind: data.contactKind, position: object.getWorldPosition(new Vector3()).toArray() });
    });
    gl.domElement.dataset.pickTargets = JSON.stringify(picks);
    gl.domElement.dataset.sceneState = JSON.stringify({ runId: world.run.id, revision: world.run.revision, elapsedMs: elapsedMs, authoritativeElapsedMs: world.run.elapsed_ms, materials, contacts, vehicles, focusStage, camera: { position: camera.position.toArray(), projectionMatrix: camera.projectionMatrix.toArray(), matrixWorld: camera.matrixWorld.toArray(), zoom: camera.zoom }, reduced, stale });
  }
  observeAssets(entities: readonly AssetEntity[], authority: QaAuthority, camera: Camera): BoundQaSample | null {
    if (!this.enabled) return null;
    if (authority.stale || !Number.isInteger(authority.revision) || authority.revision < 0 || !Number.isFinite(authority.authoritativeElapsedMs) || authority.authoritativeElapsedMs < 0) throw new RangeError('QA authority is stale or malformed');
    const count = entities.reduce((total, entity) => total + entity.nodes.size + entity.asset.sockets.length, 0);
    if (entities.length === 0 || count > 256) throw new RangeError('QA bound node budget exceeded or empty');
    const nodes: BoundQaNode[] = [];
    for (const entity of entities) {
      if (entity.identity.run_id !== authority.runId || entity.identity.bundle_hash !== authority.bundleHash || entity.level === null) throw new RangeError('QA bound entity run/bundle or loaded level mismatch');
      entity.root.updateMatrixWorld(true); this.work.matrixUpdates += 1;
      for (const [id, node] of entity.nodes) {
        const part = entity.asset.moving_parts.some(value => value.node_id === id) || entity.asset.fixed_parts.some(value => value.node_id === id);
        nodes.push({ entityId: entity.identity.entity_id, id, kind: part ? 'part' : 'node', matrixWorld: node.matrixWorld.toArray(), visible: node.visible && entity.root.visible });
      }
      for (const socket of entity.sockets()) nodes.push({ entityId: entity.identity.entity_id, id: socket.id, kind: 'socket', matrixWorld: socket.matrix, visible: entity.root.visible });
    }
    camera.updateMatrixWorld(true); this.work.matrixUpdates += 1;
    this.work.frames += 1; this.work.boundNodes += nodes.length;
    return { authority, sampledAtMs: performance.now(), rafSequence: this.work.frames, nodes, camera: { matrixWorld: camera.matrixWorld.toArray(), projectionMatrix: camera.projectionMatrix.toArray() } };
  }
}
