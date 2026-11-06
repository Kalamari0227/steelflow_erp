import type {Phase} from './frames';
export type TransportProof={readonly sample:(phase:Phase,progress:number)=>unknown;readonly physical:()=>unknown;readonly negatives:()=>Promise<unknown>};
declare global{interface Window{readonly transportProof:TransportProof}}
