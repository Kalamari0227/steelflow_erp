import {useEffect,useState} from 'react';
import {AssetRegistry} from '../../../src/operations/scene/assets/registry';

/** Real production loader isolation, without a material or motion completion claim. */
export function LoaderProbe({manifest,manifestHash}:{readonly manifest:string;readonly manifestHash:string}){
  const [result,setResult]=useState<Readonly<Record<string,unknown>>>({status:'loading'});
  useEffect(()=>{const registry=new AssetRegistry(manifest,{origin:location.origin}),q=new URLSearchParams(location.search),id=q.get('asset'),level=Number(q.get('lod')??0);if(!id)throw new RangeError('Exact loader asset absent');const asset=registry.asset(id),owner=asset.placement_ids[0]?.replace('equipment:','');if(!owner)throw new RangeError('Exact loader owner absent');registry.beginRun('factory-contract-run',manifestHash);const entity=registry.entity({run_id:'factory-contract-run',entity_type:'equipment',entity_id:owner,bundle_hash:manifestHash},id);let active=true;
    void entity.show(level).then(()=>{if(active)setResult({status:'loaded',assetId:id,lod:entity.level,children:entity.root.children.length,rootUuid:entity.root.uuid,nodes:[...entity.nodes.keys()]});},(e:unknown)=>{if(active)setResult({status:'rejected',error:e instanceof Error?e.message:String(e),assetId:id,lod:entity.level,children:entity.root.children.length,resources:registry.resources()});});return()=>{active=false;registry.dispose();};
  },[manifest,manifestHash]);
  return <main><h1>실제 GLB 로더 검증</h1><p>제작 파일의 구조 검증이며 전체 공정 완료를 뜻하지 않습니다.</p><pre data-testid="loader-result">{JSON.stringify(result)}</pre></main>;
}
