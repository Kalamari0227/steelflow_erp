import { equipmentExample, required } from '../../../src/operations/scene/assets/manifestTestFixtures';

/** Metadata-only admission inputs. Actual Blender exports are generated separately. */
export function followerMetadata(variant = 'variant:roughing:CS-HR-03', count = 3) {
  const input = equipmentExample(variant), original = required(input.assets[0]);
  const driver = { ...required(original.moving_parts[0]), motion: 'rotation', axis: [0, 0, 1], pivot_m: [-1, 1.6, 0],
    range: { min: 0, max: 4 * Math.PI, rest: 0.35, unit: 'rad' },
    binding: { type: 'clip', clock: 'server_sim', phase: 'work', progress_source: 'server_phase_progress', pause: 'hold', fault: 'hold', rest: 'range_rest', clip_id: 'miniature.roughing_roll' } };
  const frame = { id: 'roll_frame', parent_id: 'root', locator: 'root/roll_frame', transform: { position_m: [0.2, 0.1, -0.3], rotation_xyzw: [0, Math.sin(0.2), 0, Math.cos(0.2)] } };
  const followers = [-1, 0.5, -0.5].slice(0, count).map((ratio, index) => {
    const rest = 0.7 + index * 0.2, ends = [rest + ratio * (driver.range.min - driver.range.rest), rest + ratio * (driver.range.max - driver.range.rest)];
    const id = `roughing_roll_follower_${index + 1}`;
    return { id, node_id: id, function: driver.function, role: 'operational', motion: 'rotation', axis: [0, 0, 1], pivot_m: [-1 + index * 1.1, 0.8, 0],
      range: { min: Math.min(...ends), max: Math.max(...ends), rest, unit: 'rad' }, binding: { type: 'mechanical_follower', driver_part_id: driver.id, ratio } };
  });
  const parts = [driver, ...followers];
  const nodes = [...original.nodes.filter(node => node.id !== driver.node_id), frame,
    ...parts.map(part => ({ id: part.node_id, parent_id: frame.id, locator: `${frame.locator}/${part.node_id}`, transform: { position_m: [...part.pivot_m], rotation_xyzw: [0, 0, 0, 1] } }))];
  const asset = { ...original, nodes, moving_parts: parts,
    collision_proxies: [required(original.collision_proxies[0]), ...parts.map(part => ({ ...required(original.collision_proxies[1]), id: `${part.id}_sweep`, part_id: part.id }))],
    lods: original.lods.map(lod => ({ ...lod, nodes: structuredClone(nodes), part_ids: parts.map(part => part.id) })) };
  return { ...input, assets: [asset] };
}
