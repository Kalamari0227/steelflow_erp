"""Emit exact actual source assemblies for Astra's closed composition decision."""
from pathlib import Path
import hashlib
import json
import sys

SOURCE=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path.insert(0,str(SOURCE))
from build import shape
from geometry import Model


def main() -> None:
    recipe=json.loads((SOURCE/'recipe.json').read_text());rows=[]
    for spec in recipe['models']:
        model=Model(spec['key'],0);shape(model,spec)
        nodes={n['id']:n for n in model.nodes};motions={m.name:m for m in model.motions}
        def ancestors(name: str) -> list[str]:
            result=[];parent=nodes[name]['parent_id']
            while parent is not None:result.append(parent);parent=nodes[parent]['parent_id']
            return result
        parts=[]
        for motion in model.motions:
            parts.append({'id':motion.name,'function':motion.name,'driver_id':None,'parent_id':nodes[motion.name]['parent_id'],'axis':motion.axis,'pivot_m':nodes[motion.name]['transform']['position_m'],'range':{'min':motion.minimum,'max':motion.maximum,'rest':motion.rest},'ancestors':ancestors(motion.name),'motion':motion.mode,'representation':'canonical'})
        for follower in model.followers:
            driver=motions[follower['driver']];lo=(driver.minimum-driver.rest)*follower['ratio'];hi=(driver.maximum-driver.rest)*follower['ratio'];name=follower['node_id']
            parts.append({'id':name,'function':driver.name,'driver_id':driver.name,'ratio':follower['ratio'],'parent_id':nodes[name]['parent_id'],'axis':follower['axis'],'pivot_m':nodes[name]['transform']['position_m'],'range':{'min':min(lo,hi),'max':max(lo,hi),'rest':0},'ancestors':ancestors(name),'motion':'rotation','representation':'mechanical_follower'})
        rows.append({'variant':spec['variant'],'key':spec['key'],'kind':spec['kind'],'parts':parts,'fixed_relations':[{'part_id':a,'parent_part_id':b,'parent_id':nodes[a]['parent_id'],'ancestors':ancestors(a)} for a,b in model.relative_fixed.items()],'parallel_steering':'source uses equal knuckle angles, not Ackermann/no-slip dynamics certification' if spec['kind'] in ('truck','slab-carrier','coil-carrier','forklift') else None,'sockets':model.sockets})
    output=Path(sys.argv[sys.argv.index('--')+1]);output.write_text(json.dumps({'format':'transport-exact-mechanics-proposal-v1','approval':'PENDING_ASTRA','source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.glob('*.py')},'rows':rows},indent=2)+'\n')
    print('EXACT_SOURCE_ASSEMBLIES '+str(output))


if __name__=='__main__':main()
