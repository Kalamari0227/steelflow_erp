import { parseAssetManifestValue } from '../assets/manifest';
import type { Asset } from '../assets/manifest';
import { effectivePolicy } from './effectivePolicy';
import { composeTransform, rotatePoint, transformPoint } from './geometry';
import type { Transform } from './geometry';
import { bindingShape } from './shapes';
import type { AssetBinding } from './shapes';
import { requireMotion } from './errors';

export type AssetSelection = { readonly owner_id: string; readonly asset_id: string; readonly socket_families: Readonly<Record<string, string>> };

function nodeTransform(asset: Asset, nodeId: string): Transform {
  const node = asset.nodes.find(n => n.id === nodeId);
  requireMotion(node !== undefined, 'binding', nodeId);
  return node.parent_id === null ? node.transform : composeTransform(nodeTransform(asset, node.parent_id), node.transform);
}

/** T4 metadata adapter only; this does not certify GLB nodes or animation implementations. */
export function bindingsFromAssetManifest(input: unknown, selections: readonly AssetSelection[]): readonly AssetBinding[] {
  const manifest = parseAssetManifestValue(input);
  return Object.freeze(selections.map(selection => {
    const asset = manifest.assets.find(a => a.id === selection.asset_id);
    requireMotion(asset !== undefined, 'binding', selection.asset_id);
    requireMotion(asset.category !== 'equipment' || asset.placement_ids.some(p => p === `equipment:${selection.owner_id}`), 'binding', selection.owner_id);
    const policy = effectivePolicy(asset.category, asset.kind, selection.owner_id, asset.motion_policy_id);
    const sockets = asset.sockets.map(socket => {
      const family = selection.socket_families[socket.id];
      requireMotion(family !== undefined && socket.forms.some(form => form === family), 'form', socket.id);
      const transform = composeTransform(nodeTransform(asset, socket.node_id), socket.transform);
      const ancestors: string[] = [];
      let node = asset.nodes.find(n => n.id === socket.node_id);
      while (node !== undefined) { ancestors.push(node.id); node = asset.nodes.find(n => n.id === node?.parent_id); }
      const motion_function_ids = ancestors.reverse().flatMap(id => asset.moving_parts.filter(p => p.role === 'operational' && p.binding.type !== 'mechanical_follower' && p.node_id === id).map(p => p.function));
      return { socket_id: socket.id, family, motion_function_ids, position_m: transform.position_m, orientation_xyzw: transform.rotation_xyzw };
    });
    const moving = asset.moving_parts.filter(p => p.role === 'operational' && p.binding.type !== 'mechanical_follower').map(part => {
      const node = asset.nodes.find(n => n.id === part.node_id);
      requireMotion(node !== undefined, 'binding', part.node_id);
      const parent: Transform = node.parent_id === null ? { position_m: [0, 0, 0], rotation_xyzw: [0, 0, 0, 1] } : nodeTransform(asset, node.parent_id);
      return { function_id: part.function, node_id: part.node_id, kind: part.motion, axis: rotatePoint(parent.rotation_xyzw, part.axis),
        pivot_m: transformPoint(parent, part.pivot_m), min_value: part.range.min, max_value: part.range.max };
    });
    const states = asset.fixed_parts.filter(p => p.binding !== null).map(part => ({
      function_id: part.function, node_id: part.node_id, kind: 'state', axis: [0, 1, 0], pivot_m: [0, 0, 0], min_value: 0, max_value: 1,
    }));
    const internalFeeds=asset.internal_feeds?.map(feed=>{
      const driver=asset.moving_parts.find(p=>p.id===feed.driver_part_id);requireMotion(driver!==undefined,'binding',feed.id);
      const {driver_part_id: _part,support_lift_part_id,...rest}=feed;
      const lift=support_lift_part_id===undefined ? undefined : asset.moving_parts.find(p=>p.id===support_lift_part_id);
      requireMotion(support_lift_part_id===undefined || lift!==undefined,'binding',feed.id);
      return {...rest,driver_function_id:driver.function,...(lift===undefined ? {} : {support_lift_function_id:lift.function}),rollers:feed.rollers.map(r=>{const part=asset.moving_parts.find(p=>p.id===r.part_id);requireMotion(part!==undefined,'binding',r.part_id);return {...r,center_m:nodeTransform(asset,part.node_id).position_m,ratio:part.binding.type==='mechanical_follower' ? part.binding.ratio : 1};})};
    });
    return bindingShape.parse({ owner_id: selection.owner_id, policy_id: policy.id, sockets, functions: [...moving, ...states],...(internalFeeds ? {internal_feeds:internalFeeds} : {}) });
  }));
}
