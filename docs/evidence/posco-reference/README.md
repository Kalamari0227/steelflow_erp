# POSCO product manufacturing references

Observed on 2026-10-24 in the public myPOSCO product showroom. The manufacturing tab and each available process variant were opened in a real browser. Screenshots below record the source view, not SteelFlow output. No login, private data, original 3D assets or operating-system integration was used.

| Family / source page | Observed variants and distinctive process | Captured reference |
| --- | --- | --- |
| [Hot rolled](https://my.posco.com/s/exshowrmproductmain?lv1=a0uTJ000004pM0zYAE) | Reheating → roughing → finishing → cooling/coiling → finishing | [View](hot-rolled.png) |
| [Plate](https://my.posco.com/s/exshowrmproductmain?lv1=a0uTJ000004pM10YAE) | Rolling → accelerated cooling → cooling bed → cutting → heat treatment → ultrasonic inspection | [Upper](plate.png), [line](plate-line.png) |
| [Wire rod](https://my.posco.com/s/exshowrmproductmain?lv1=a0uTJ000004pM11YAE) | Bloom reheating → billet rolling/finishing → wire reheating/rolling → cooling/inspection | [View](wire-rod.png) |
| [Cold rolled](https://my.posco.com/s/exshowrmproductmain?lv1=a0uTJ000004pM12YAE) | Pickling → cold rolling → electrolytic cleaning → annealing → temper rolling | [View](cold-rolled.png) |
| [Coated](https://my.posco.com/s/exshowrmproductmain?lv1=a0uTJ000004pM13YAE) | Hot dip: pretreatment, annealing, zinc bath, alloying, temper, post-treatment, oiling. Electrogalvanized: electrolytic cells, phosphate and anti-fingerprint treatment | [Hot dip](coated.png), [EG](electrogalvanized.png) |
| [Electrical steel](https://my.posco.com/s/exshowrmproductmain?lv1=a0uTJ000004pM14YAE) | GO: decarburizing, high-temperature annealing, flattening, insulation, domain refinement. NGO: preliminary/final annealing and insulation | [GO](electrical.png), [NGO](electrical-non-oriented.png) |
| [Stainless](https://my.posco.com/s/exshowrmproductmain?lv1=a0uTJ000004pM15YAE) | Hot rolled: EAF, refining, casting, rolling, CAF/HAPL. Cold rolled: rolling, CAPL, temper, TLL/STL. Plate: rolling, leveling, cooling, cutting and heat treatment | [HR](stainless.png), [CR](stainless-cold.png), [plate](stainless-plate.png) |
| [Titanium](https://my.posco.com/s/exshowrmproductmain?lv1=a0uTJ000004pM16YAE) | Hot rolled: ingot forging and rolling/HAPL. Cold rolled: rolling, vacuum annealing, TLL/STL/SHL with coil/sheet branch. Plate: forging, rolling, annealing, pickling and leveling | [HR](titanium.png), [CR](titanium-cold.png), [plate](titanium-plate.png) |

Eight families expose fourteen diagram variants. SteelFlow offers seventeen selectable demo routes: the hot-dip example is separated into GI/GA/HGI, and titanium cold rolling into coil/sheet outputs. HGI is an explicitly identified adaptation of the hot-dip flow with HR feedstock; a separate HGI 3D reference was not present. Inbound/outbound trucks, packaging where needed, durations and fixed masses are synthetic demo additions.

The source uses a continuous raised roller line, compact furnace and mill modules, pale ground, blue machine housings, metallic rolls, process-specific baths and visible material transformation. SteelFlow recreates these principles with selectable procedural meshes. It does not reuse source screenshots as an interactive scene, reproduce surveyed plant dimensions, or claim to contain POSCO's original CAD/animation assets.
