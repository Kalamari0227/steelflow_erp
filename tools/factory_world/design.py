"""Synthetic functional envelopes and placements, not surveyed plant dimensions."""
from dataclasses import dataclass
from typing import Final
from app.operations.world_spatial_types import DesignProfile
from app.operations.world_types import Point, Size, Mode

SIZES: Final[dict[str, Size]] = {
 'charge':(28,22,20),'blast_furnace':(46,65,40),'bof':(32,38,28),'ladle_furnace':(25,24,24),
 'caster':(70,20,22),'shear':(12,6,12),'furnace':(55,12,24),'roughing':(28,14,22),
 'finishing_mill':(100,16,24),'cooling':(90,8,16),'coiler':(18,8,16),'leveler':(18,8,16),
 'cooling_bed':(80,5,26),'heat_treatment':(65,14,24),'bloom_mill':(38,16,22),
 'wire_mill':(72,10,16),'laying_head':(28,8,16),'uncoiler':(16,8,14),'pickling':(75,10,18),
 'cold_mill':(35,16,20),'electrocleaning':(35,10,16),'annealing':(90,18,22),
 'temper':(24,12,18),'oiling':(12,6,12),'galvanizing':(35,24,20),'coating':(30,12,16),
 'alloying':(32,22,18),'electroplating':(55,10,18),'decarburizing':(85,18,22),
 'inspection':(22,8,16),'eaf':(38,34,30),'aod':(28,26,24),'forging':(36,24,26),
 'vacuum_annealing':(48,16,22),'slitter':(20,8,16),'packaging':(35,10,20),
 'stock':(85,12,36),'port':(100,20,32),'ship':(150,25,30),'delivery':(65,10,28),
 'welder':(12,8,12),'looper':(38,20,16),'scale-breaker':(18,9,14),'air-knife':(10,14,14),
 'shot-blasting':(24,10,16),'domain-refinement':(22,10,16),'drying':(25,12,16),'marking':(12,6,12),
}
# name, product, after owner, function kind. Each product gets actual placement.
FUNCTIONS: Final = [
 ('plate-ultrasonic','plate','CS-PLATE-08','inspection'),
 ('plate-marking','plate','func-plate-ultrasonic-plate','marking'),
 ('plate-gas-cut','plate','func-plate-marking-plate','shear'),
 ('wire-shears','wire','CS-WIRE-04','shear'),
 ('cold-scale-breaker','cr','CS-CR-02','scale-breaker'),
 ('cold-welder','cr','CS-CR-02','welder'),('cold-looper','cr','func-cold-welder-cr','looper'),
 ('coating-welder','eg','CS-EG-02','welder'),('coating-looper','eg','CS-EG-03','looper'),
 ('coating-inspection','eg','CS-EG-08','inspection'),('eg-oven-cooler','eg','CS-EG-07','drying'),
 ('go-domain-refinement','go','CS-GO-09','domain-refinement'),
 ('ngo-electrocleaning','ngo','CS-NGO-05','electrocleaning'),('ngo-drying','ngo','CS-NGO-07','drying'),
 ('sts-shot-blasting','sts-hr','STS-HR-11','shot-blasting'),('sts-welder','sts-cr','STS-CR-02','welder'),
 ('sts-looper','sts-hr','STS-HR-10','looper'),('sts-looper','sts-cr','STS-CR-02','looper'),
 ('ti-tll-coil','ti-cr','TI-CR-07','coiler'),('ti-stl-skelp','ti-cr','TI-CR-08','slitter'),
 ('ti-shl-sheet','ti-sheet','TI-SHEET-07','shear'),('hgi-hr-feed','hgi','CS-HGI-02','uncoiler'),
 ('go-base-coating','go','CS-GO-06','coating'),
 ('cr-cold-mill-output-cutter','cr','CS-CR-04','shear'),('cr-finished-output-cutter','cr','CS-CR-08','shear'),
 ('go-pickling-output-cutter','go','CS-GO-04','shear'),
 ('go-basecoat-output-cutter','go','func-go-base-coating-go','shear'),
 ('go-finished-output-cutter','go','CS-GO-10','shear'),
 ('ngo-pickling-output-cutter','ngo','CS-NGO-04','shear'),('ngo-finished-output-cutter','ngo','func-ngo-drying-ngo','shear'),
 ('sts-hapl-output-cutter','sts-hr','STS-HR-12','shear'),('sts-capl-output-cutter','sts-cr','STS-CR-05','shear'),
 ('hotdip-output-cutter','gi','CS-GI-08','shear'),('hotdip-output-cutter','ga','CS-GA-09','shear'),
 ('hgi-output-cutter','hgi','CS-HGI-08','shear'),('eg-output-cutter','eg','CS-EG-08','shear'),
 ('gi-coating-cooling','gi','func-coating-air-knife-gi','cooling'),
 ('ga-coating-cooling','ga','CS-GA-06','cooling'),('hgi-coating-cooling','hgi','func-coating-air-knife-hgi','cooling'),
]
# Prepend shared functions before rows that reference them.
FUNCTIONS[:0] = [(name,p,anchor.format(p=p.upper(),lower=p),kind)
 for p in ('gi','ga','hgi') for name,anchor,kind in (
 ('coating-air-knife','CS-{p}-05','air-knife'),('coating-welder','CS-{p}-02','welder'),
 ('coating-looper','func-coating-welder-{lower}','looper'),('coating-inspection','CS-{p}-08','inspection'))]
FUNCTIONS[:0] = [(name,p,anchor.format(p=p.upper()),kind) for p in ('go','ngo') for name,anchor,kind in (
 ('electrical-shot-blasting','CS-{p}-03','shot-blasting'),('electrical-welder','CS-{p}-02','welder'),
 ('electrical-looper','CS-{p}-02','looper'))]
STAGE_ORIGINS: Final[dict[str, Point]] = {
 'carbon-upstream':(100,0,-450),'casting-slab':(600,0,-450),
 'casting-bloom':(620,0,-200),'casting-billet':(1000,0,-200),
 'hr':(180,0,100),'plate':(1300,0,100),'wire':(1100,0,400),
 'cr':(120,0,680),'gi':(100,0,1000),'ga':(1250,0,1000),
 'hgi':(1300,0,680),'eg':(120,0,1480),'go':(1600,0,1300),'ngo':(2100,0,1300),
 'sts-hr':(120,0,2110),'sts-cr':(120,0,2450),'sts-plate':(2200,0,2450),
 'ti-hr':(120,0,2800),'ti-cr':(120,0,3130),'ti-sheet':(1800,0,3130),
 'ti-plate':(1800,0,2800),'hot-rolling-reserve':(180,0,400),
}
FLEET: Final = {'truck':32,'slab-carrier':12,'coil-carrier':12,'forklift':16,'torpedo':4,
 'ladle-car':4,'locomotive':4,'railcar':12,'ship':4}
PROFILE_INPUTS: Final = (
 ('truck','road',(18,4,3),(14,4,3),1,15,18,True),
 ('slab-carrier','road',(14,4,4),(14,3,4),1,16,14,True),
 ('coil-carrier','road',(12,4,4),(10,4,4),1,14,12,True),
 ('forklift','road',(5,4,3),(4,4,3),.5,5,5,True),
 ('torpedo','hot_metal',(30,6,5),(22,6,5),2,80,34,True),
 ('ladle-car','ladle',(15,7,6),(12,7,6),2,60,20,True),
 ('locomotive','rail',(20,5,4),(18,5,4),2,120,85,True),
 ('railcar','rail',(20,5,4),(18,5,4),2,120,85,True),
 ('ship','sea',(150,25,30),(130,20,26),5,250,150,True),
 ('roller','roller',(2,2,2),(12,2,3),.25,0,2,False),
 ('conveyor','conveyor',(2,2,2),(2,2,2),.25,15,2,False),
)

def profiles() -> tuple[DesignProfile, ...]:
    return tuple(DesignProfile(id=kind,kind=kind,mode=mode,size_m=size,load_size_m=load,
      clearance_m=clearance,min_turn_radius_m=radius,consist_length_m=length,reverse_allowed=reverse,
      body_offset_m=(0,{'road':2,'rail':3,'hot_metal':4,'ladle':4,'sea':15,'roller':2,'conveyor':12}[mode]*-1+size[1]/2,0) if mode in ('road','rail','hot_metal','ladle','sea') else (0,0,0),
      load_offset_m=(0,load[1]/2,0))
      for kind,mode,size,load,clearance,radius,length,reverse in PROFILE_INPUTS)

@dataclass(frozen=True, slots=True)
class Placement:
    id: str
    kind: str
    zone: str
    position: Point
    size: Size
    mode: Mode = 'roller'
