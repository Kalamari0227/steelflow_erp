"""Transverse gas-cut carriage and mechanical billet shear: distinct mechanisms."""
from details import table
from geometry import Motion


def cutter(model, gas=False):
    model.length,model.width=9,4.2 if gas else 1.5
    w=model.width
    table(model,-4,-.45,w,'entry_table')
    table(model,.45,4,w,'exit_table')
    model.node('cutting_tool',position=(0,2.1,-w/2+.2) if gas else (0,2.0,0))
    if gas:
        for x,side in [(-.8,'entry'),(.8,'exit')]:
            model.box(side+'_gantry_rail',(.16,.2,w+1.3),(x,2.9,0),finish='steel')
            for z,label in [(-w/2-.5,'left'),(w/2+.5,'right')]:
                model.box(side+'_'+label+'_foot',(.65,.20,.65),(x,.24,z),finish='dark')
                model.box(side+'_'+label+'_pillar',(.28,2.6,.28),(x,1.6,z),finish='teal')
        model.box('torch_carriage',(1.8,.28,.55),(0,.55,0),'cutting_tool','teal')
        model.cylinder('torch_body',.10,.65,(0,.05,0),'cutting_tool','safety',axis='y')
        model.cylinder('gas_nozzle',.045,.25,(0,-.47,0),'cutting_tool','steel',axis='y')
        model.cylinder('torch_neck',.06,.22,(0,-.33,0),'cutting_tool','steel',axis='y')
        model.tube('oxygen_hose',[(.15,.35,0),(.4,.9,0),(-.3,1.05,0),(-.65,.8,0)],.04,'cutting_tool','dark')
        model.tube('fuel_hose',[(-.15,.35,0),(-.4,.8,0),(-.7,.9,0)],.035,'cutting_tool','red')
        model.box('clamp_bar',(.20,.10,w-.2),(1.5,1.55,0),finish='safety')
        model.motion(Motion('cutting_tool','translation',(0,0,1),w-.4))
    else:
        for z,side in [(-1.05,'left'),(1.05,'right')]:
            model.box(side+'_foot',(.95,.16,.7),(0,.22,z),finish='dark')
            model.box(side+'_column',(.75,2.9,.45),(0,1.7,z),finish='teal')
            model.box(side+'_blade_guide',(.20,1.3,.14),(.35,2.0,z),finish='steel')
        model.box('shear_crown',(1.1,.45,2.8),(0,3.15,0),finish='blue')
        model.box('blade_holder',(.50,.30,2.0),(0,.3,0),'cutting_tool','safety')
        model.box('upper_blade',(.16,.55,1.7),parent='cutting_tool',finish='steel',bevel=.008)
        model.box('blade_edge',(.08,.08,1.7),(.06,-.30,0),'cutting_tool','dark',bevel=.005)
        model.box('lower_blade',(.16,.2,1.7),(.16,1.22,0),finish='steel',bevel=.01)
        for z,side in [(-.65,'left'),(.65,'right')]:
            model.cylinder(side+'_hydraulic_barrel',.16,.65,(0,2.85,z),finish='dark',axis='y')
            model.cylinder(side+'_piston_rod',.075,.9,(0,.73,z),'cutting_tool','steel',axis='y')
        model.motion(Motion('cutting_tool','translation',(0,-1,0),.60))
