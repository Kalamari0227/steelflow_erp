import {createRoot} from 'react-dom/client';
import {LoaderProbe} from './loader';
import './style.css';

/** Keep structural GLB checks independent of the large process-fixture corpus. */
async function start(){
  const target=document.getElementById('root');if(!target)throw new RangeError('Owned loader root absent');const root=createRoot(target),query=new URLSearchParams(location.search);
  try{const response=await fetch('/assets/steelworks/finishing/manifest.json',{redirect:'error'});if(!response.ok)throw new Error('Exact candidate manifest absent');const manifest=await response.text(),bytes=new TextEncoder().encode(manifest),digest=await crypto.subtle.digest('SHA-256',bytes),manifestHash=Array.from(new Uint8Array(digest),v=>v.toString(16).padStart(2,'0')).join('');if(manifestHash!==query.get('expected-sha'))throw new Error('Pinned raw manifest SHA mismatch');root.render(<LoaderProbe manifest={manifest} manifestHash={manifestHash}/>);}catch(error){root.render(<main><h1>로더 검증 준비 오류</h1><p role="alert">{error instanceof Error?error.message:String(error)}</p></main>);}
}
void start();
