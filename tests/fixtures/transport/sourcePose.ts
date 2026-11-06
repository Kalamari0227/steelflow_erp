import {Quaternion,Vector3} from 'three';
import type {LoadedAsset} from '../../../src/operations/scene/assets/loader';
import type {GeometryFrame} from './frames';
/** Source-preview scalars obey exact authored parent frames; no public pose or server clock. */
export function applySourceGeometry(loaded:LoadedAsset,frame:GeometryFrame):void{
  const values:Readonly<Record<string,number>>=loaded.asset.kind==='crane'?{bridge_travel:frame.bridge,trolley_travel:frame.trolley,hoist:frame.hoist}:{};
  for(const part of loaded.asset.moving_parts){const node=loaded.nodes.get(part.node_id),rest=loaded.asset.nodes.find(n=>n.id===part.node_id);if(!node||!rest)throw new RangeError('Source moving part absent');const binding=part.binding,driver=binding.type==='mechanical_follower'?loaded.asset.moving_parts.find(p=>p.id===binding.driver_part_id):part;if(!driver)throw new RangeError('Source driver missing');const scalar=values[driver.function]??driver.range.rest,delta=binding.type==='mechanical_follower'?binding.ratio*(scalar-driver.range.rest):scalar-driver.range.rest;node.position.fromArray(rest.transform.position_m);node.quaternion.fromArray(rest.transform.rotation_xyzw);if(part.motion==='translation')node.position.addScaledVector(new Vector3(...part.axis),delta);else node.quaternion.premultiply(new Quaternion().setFromAxisAngle(new Vector3(...part.axis),delta));}
  loaded.scene.updateMatrixWorld(true);
}
