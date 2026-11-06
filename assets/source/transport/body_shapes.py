"""Conservative source-bound wheel assemblies without shrinking any actual solid.

Static mesh boxes are exact evaluated bounds. Rolling wheels are grouped around
actual individual wheel pivots and enclosed for every roll angle and the complete
registered parallel-steering range, using a cylinder's radial support function.
"""
import math
from mathutils import Vector
from geometry import CONVERSION,Model


def body_boxes(model: Model,solids: list[str],static_boxes):
    if model.key not in ('truck-flatbed','truck-dump'):return static_boxes
    nodes={n['id']:n for n in model.nodes};groups={};remaining=[]
    for name in solids:
        cursor=name
        while cursor!='root' and cursor!='wheel_rotation' and not cursor.endswith('_roll'):
            cursor=nodes[cursor]['parent_id']
        if cursor=='root':remaining.append(name)
        else:groups.setdefault(cursor,[]).append(name)
    boxes=[b for b in static_boxes if b['mesh_node_ids'][0] in remaining]
    for pivot,names in sorted(groups.items()):
        parent=model.objects[pivot];inverse=parent.matrix_world.inverted()
        points=[CONVERSION@inverse@model.objects[name].matrix_world@v.co for name in names for v in model.objects[name].data.vertices]
        radial=max(math.hypot(p[0],p[1]) for p in points);half_z=max(abs(p[2]) for p in points)
        node=nodes[pivot];steered=node['parent_id'] in ('steering','steering_right')
        if steered:
            limit=next(m.maximum for m in model.motions if m.name=='steering')
            half_x=math.hypot(radial,half_z)
            extent_z=max(half_z,half_z*math.cos(limit)+radial*math.sin(limit))
        else:half_x=radial;extent_z=half_z
        center=CONVERSION@parent.matrix_world@Vector((0.,0.,0.))
        boxes.append({'id':'box:'+pivot,'mesh_node_ids':sorted(names),'center_m':list(center),'size_m':[2*half_x+.00002,2*radial+.00002,2*extent_z+.00002],'yaw_rad':0.})
    return boxes
