import type { World } from '../../contracts';
import type { Material } from '../contracts';
import type { Point } from './layout';

const indexedWorlds = new WeakMap<World, ReadonlyMap<string, number>>();

function materialIndices(world: World): ReadonlyMap<string, number> {
  const cached = indexedWorlds.get(world);
  if (cached) return cached;
  const children = new Set(world.lineage_edges.map(edge => edge.child_material_id));
  const roots = world.materials.filter(row => !children.has(row.id)).sort((a, b) => a.id.localeCompare(b.id));
  const result = new Map<string, number>();
  for (const [index, root] of roots.entries()) {
    result.set(root.id, index * 3);
    const descendants = world.materials.filter(row => row.lineage_id === root.lineage_id && row.id !== root.id).sort((a, b) => a.id.localeCompare(b.id));
    descendants.forEach((row, child) => result.set(row.id, index * 3 + child));
  }
  indexedWorlds.set(world, result);
  return result;
}

/** Slots are attached to persistent identity, never the set of currently visible materials. */
export function storagePosition(material: Material, world: World, anchor: { readonly id: string; readonly position: Point }, elapsedMs = world.run.elapsed_ms): Point {
  if (!/^OPS-(ORE-SOURCE|SCRAP-SOURCE|TI-SOURCE|WAREHOUSE|PORT|CUSTOMER)-BUFFER$/.test(anchor.id)) {
    const siblings = world.lineage_edges.filter(edge => world.materials.find(row => row.id === edge.child_material_id)?.lineage_id === material.lineage_id).map(edge => edge.child_material_id).sort();
    const index = siblings.indexOf(material.id);
    if (index > 0 && /-(ENTRY|EXIT|BUFFER)$/.test(anchor.id)) {
      const edge = world.lineage_edges.find(row => row.child_material_id === material.id);
      const split = world.processes.find(row => row.id === edge?.process_id);
      const settled = Math.max(0, Math.min(1, (elapsedMs - (split?.end_ms ?? elapsedMs - 1000)) / 1000));
      return [anchor.position[0], anchor.position[1] + settled * index * (/STRIP|SHEET|PLATE/.test(material.form) ? 0.15 : 1.5), anchor.position[2]];
    }
    return anchor.position;
  }
  const index = materialIndices(world).get(material.id) ?? 0;
  return [anchor.position[0] + (index % 12) * 4.2 - 23.1, anchor.position[1], anchor.position[2] + Math.floor(index / 12) * 2 + 3];
}

export function shipmentSlot(material: Material, world: World): Point {
  const member = world.shipment_materials.find(row => row.material_id === material.id && row.active);
  if (!member) return [0, 0, 0];
  const members = world.shipment_materials.filter(row => row.shipment_id === member.shipment_id).sort((a, b) => a.material_id.localeCompare(b.material_id));
  const index = members.findIndex(row => row.material_id === material.id);
  const forms = members.map(row => world.materials.find(item => item.id === row.material_id)?.form ?? material.form);
  if (members.length <= 2 && forms.every(form => form.includes('COIL'))) return [index * 1.5 - (members.length - 1) * 0.75, 0, 0];
  const height = Math.max(...forms.map(form => form.includes('COIL') ? 1.4 : /STRIP|SHEET|PLATE/.test(form) ? 0.075 : 0.36));
  return [0, index * (height + 0.075), 0];
}
