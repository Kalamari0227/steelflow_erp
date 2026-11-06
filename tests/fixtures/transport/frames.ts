export const phases=['idle','grip','lift','translate','lower','release','empty-return','load-grip','load-lift','load-translate','load-lower','load-release','blocked','paused'] as const;
export type Phase=typeof phases[number];
type Point=readonly[number,number,number];
export type GeometryFrame={readonly bridge:number;readonly trolley:number;readonly hoist:number;readonly material:Point;readonly owner:'truck'|'handler'|'cradle';readonly phase:Phase;readonly progress:number;readonly authority:'source-geometry-candidate-runtime-admission-pending'};
/** Source kinematics only. No fixture state is claimed to be a durable business command. */
export function geometryFrame(phase:Phase,progress:number):GeometryFrame{
  let bridge=0,trolley=0,hoist=0,material:Point=[0,2.6,0],owner:GeometryFrame['owner']='truck';
  switch(phase){
    case'idle':break;
    case'grip':trolley=1.6*progress;break;
    case'lift':trolley=1.6;hoist=2*progress;material=[0,2.6+hoist,0];owner='handler';break;
    case'translate':trolley=1.6;hoist=2;bridge=6*progress;material=[0,4.6,bridge];owner='handler';break;
    case'lower':trolley=1.6;hoist=2*(1-progress);bridge=6;material=[0,2.6+hoist,6];owner='handler';break;
    case'release':trolley=1.6*(1-progress);bridge=6;material=[0,2.6,6];owner='cradle';break;
    case'empty-return':hoist=2;bridge=6*(1-progress);material=[0,2.6,6];owner='cradle';break;
    case'load-grip':trolley=1.6*progress;bridge=6;material=[0,2.6,6];owner='cradle';break;
    case'load-lift':trolley=1.6;hoist=2*progress;bridge=6;material=[0,2.6+hoist,6];owner='handler';break;
    case'load-translate':trolley=1.6;hoist=2;bridge=6*(1-progress);material=[0,4.6,bridge];owner='handler';break;
    case'load-lower':trolley=1.6;hoist=2*(1-progress);material=[0,2.6+hoist,0];owner='handler';break;
    case'load-release':trolley=1.6*(1-progress);break;
    case'blocked':case'paused':trolley=1.6;hoist=2;bridge=3;material=[0,4.6,3];owner='handler';break;
    default:{const unreachable:never=phase;throw new RangeError(String(unreachable));}
  }
  return{bridge,trolley,hoist,material,owner,phase,progress,authority:'source-geometry-candidate-runtime-admission-pending'};
}
