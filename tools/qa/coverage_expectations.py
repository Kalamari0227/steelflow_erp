"""Independent source/scope obligations, transcribed from the T2 research and plan.

These are reviewable semantic predicates, never generated from observed inventory.
The legacy ordinal table preserves identity; additional diagram parts remain separate.
"""
import re
from typing import Final

from tools.qa.coverage_models import CoverageError, Registry

PRODUCTS: Final[frozenset[str]] = frozenset('slab bloom billet hr plate wire cr gi ga hgi eg go ngo sts-hr sts-cr sts-plate ti-hr ti-cr ti-sheet ti-plate'.split())
COUNTS: Final[dict[str, int]] = dict(zip('hr plate wire cr gi ga hgi eg go ngo sts-hr sts-cr sts-plate ti-hr ti-cr ti-sheet ti-plate'.split(), (9, 10, 11, 11, 11, 12, 11, 11, 13, 10, 15, 11, 12, 10, 10, 11, 9), strict=True))
PACKAGED: Final = frozenset('hr-08 wire-10 cr-10 gi-10 ga-11 hgi-10 eg-10 go-12 ngo-09 sts-hr-14 sts-cr-10 ti-hr-09 ti-sheet-10'.split())
SHOWROOM: Final[dict[str, str]] = dict(zip(COUNTS, 'M0z M10 M11 M12 M13 M13 M13 M13 M14 M14 M15 M15 M15 M16 M16 M16 M16'.split(), strict=True))
DIAGRAMS: Final = {
    'M0z': 'hot-rolled', 'M10': 'plate plate-line', 'M11': 'wire-rod', 'M12': 'cold-rolled',
    'M13': 'coated electrogalvanized', 'M14': 'electrical electrical-non-oriented',
    'M15': 'stainless stainless-cold stainless-plate', 'M16': 'titanium titanium-cold titanium-plate',
}
OFFICIAL: Final = {
    'P1': 'https://www.poscointl.com/eng/steelProduct',
    'P2': 'https://www.posco.com/homepage/servlet/FileDownLoad?fileCategory=prdMda&fileNum=12',
    'P3': 'https://posco.com/homepage/docs/kor5/dn/product/info/Titanium.pdf',
    'P4': 'https://www.posco.com/homepage/docs/eng6/jsp/dn/company/archive/2011_eng_brochure.pdf',
    'P5': 'https://www.poscoflow.com/en/business/steel',
    'P6': 'https://www.poscoflow.com/en/business/raw-materials/steel',
    'P7': 'https://www.poscoflow.com/en/business/cts',
}
# Ordered manufacturing meanings from the source diagrams; boundary rows are excluded below.
CORE: Final = {
    'hr': 'heat,rough,finish,cool,wind,level',
    'plate': 'heat,roll,cool,cool,cut,heat,level',
    'wire': 'heat,rough,roll,condition,reheat,roll,(lay|ring)',
    'cr': 'unwind,pickl,cold,clean,anneal,temper,oil,rewind',
    'gi': 'unwind,clean,anneal,zinc,temper,treat,oil,rewind',
    'ga': 'unwind,clean,anneal,zinc,alloy,temper,treat,oil,rewind',
    'hgi': 'hot rolled,clean,heat,zinc,condition,treat,oil,rewind',
    'eg': 'unwind,level,surface,electrochem,phosph,fingerprint,oil,rewind',
    'go': 'unwind,anneal,pickl,cold,decarb,high temperature,flatten,insulation,domain,rewind',
    'ngo': 'unwind,anneal,pickl,cold,anneal,insulation,rewind',
    'sts-hr': 'melt,refine,cast,heat,rough,roll,coil,anneal,unwind,anneal,pickl,rewind',
    'sts-cr': 'unwind,cold,anneal,pickl,temper,level,slit,rewind',
    'sts-plate': 'melt,refine,cast,heat,roll,level,cool,cut,level,heat',
    'ti-hr': 'forge,heat,rough,roll,anneal,pickl,coil',
    'ti-cr': 'unwind,cold,recoil,vacuum,reintroduce,level,optional.*skelp,tll',
    'ti-sheet': 'unwind,cold,recoil,vacuum,feed,level,alternate.*skelp,shl',
    'ti-plate': 'forge,heat,roll,anneal,pickl,level,gas cut',
}
# Required product(s), source(s), semantic predicate, and explicit branch when material.
PARTS: Final = {
    'plate-ultrasonic': ('plate', 'M10', 'ultrasonic', ''),
    'plate-marking': ('plate', 'M10', 'mark', ''),
    'plate-gas-cut': ('plate', 'M10', 'gas cut', ''),
    'wire-shears': ('wire', 'M11', 'shear.*cutter', ''),
    'cold-scale-breaker': ('cr', 'M12', 'scale.*pickl', ''),
    'cold-welder': ('cr', 'M12', '(join|weld).*strip', ''),
    'cold-looper': ('cr', 'M12', 'entry.*exit.*looper', ''),
    'coating-air-knife': ('gi ga hgi', 'M13', 'air knife.*bath', ''),
    'coating-welder': ('gi ga hgi eg', 'M13', 'join.*strip', ''),
    'coating-looper': ('gi ga hgi eg', 'M13', 'looper', ''),
    'coating-inspection': ('gi ga hgi eg', 'M13', 'inspect.*coating', ''),
    'eg-oven-cooler': ('eg', 'M13', 'oven.*cool', ''),
    'go-domain-refinement': ('go', 'M14 P2', 'domain.*manufacturing', ''),
    'electrical-shot-blasting': ('go ngo', 'M14 P2', 'blast.*scale', ''),
    'electrical-welder': ('go ngo', 'M14 P2', 'weld.*strip', ''),
    'electrical-looper': ('go ngo', 'M14 P2', 'accumulate.*strip', ''),
    'ngo-electrocleaning': ('ngo', 'M14 P2', 'electrolyt.*clean', ''),
    'ngo-drying': ('ngo', 'M14 P2', 'dry.*insulation', ''),
    'sts-shot-blasting': ('sts-hr', 'M15', 'shot blast.*hapl', ''),
    'sts-welder': ('sts-cr', 'M15', 'weld.*capl', ''),
    'sts-looper': ('sts-hr sts-cr', 'M15', 'hapl.*capl.*looper', ''),
    'ti-tll-coil': ('ti-cr', 'M16 P3', 'tll without mandatory stl', 'TLL -> TI_CR_COIL'),
    'ti-stl-skelp': ('ti-cr', 'M16 P3', 'stl.*skelp', 'TLL -> STL -> TI_SKELP'),
    'ti-shl-sheet': ('ti-sheet', 'M16 P3', 'shl.*without mandatory stl', 'TLL -> SHL -> TI_SHEET'),
    'hgi-hr-feed': ('hgi', 'M13 P1', 'hot rolled.*without mandatory cold', 'HR_COIL -> HGI; no mandatory CR'),
    'go-base-coating': ('go', 'M14', 'base.*coat', ''),
    'cr-cold-mill-output-cutter': ('cr', 'M12', '(cut|shear)', ''),
    'cr-finished-output-cutter': ('cr', 'M12', '(cut|shear)', ''),
    'go-pickling-output-cutter': ('go', 'M14', '(cut|shear)', ''),
    'go-basecoat-output-cutter': ('go', 'M14', '(cut|shear)', ''),
    'go-finished-output-cutter': ('go', 'M14', '(cut|shear)', ''),
    'ngo-pickling-output-cutter': ('ngo', 'M14', '(cut|shear)', ''),
    'ngo-finished-output-cutter': ('ngo', 'M14', '(cut|shear)', ''),
    'sts-hapl-output-cutter': ('sts-hr', 'M15', '(cut|shear)', ''),
    'sts-capl-output-cutter': ('sts-cr', 'M15', '(cut|shear)', ''),
    'hotdip-output-cutter': ('gi ga', 'M13', '(cut|shear)', ''),
    'hgi-output-cutter': ('hgi', 'M13 P1', '(cut|shear)', ''),
    'eg-output-cutter': ('eg', 'M13', '(cut|shear)', ''),
    'gi-coating-cooling': ('gi', 'M13', 'cool', ''),
    'ga-coating-cooling': ('ga', 'M13', 'cool', ''),
    'hgi-coating-cooling': ('hgi', 'M13 P1', 'cool', ''),
}
POSITIONED: Final = {
    'go-base-coating': ('decarb', 'base', 'high.temperature'),
    'cr-cold-mill-output-cutter': ('cold.*(mill|roll)', '(cut|shear)', '(coil|wind)'),
    'cr-finished-output-cutter': ('(temper|oil|finish)', '(cut|shear)', '(coil|wind)'),
    'go-pickling-output-cutter': ('pickl', '(cut|shear)', '(coil|wind)'),
    'go-basecoat-output-cutter': ('base', '(cut|shear)', '(coil|wind)'),
    'go-finished-output-cutter': ('(domain|insulation|finish)', '(cut|shear)', '(coil|wind)'),
    'ngo-pickling-output-cutter': ('pickl', '(cut|shear)', '(coil|wind|cold.*mill)'),
    'ngo-finished-output-cutter': ('(insulation|dry|finish)', '(cut|shear)', '(coil|wind)'),
    'sts-hapl-output-cutter': ('(hapl|pickl)', '(cut|shear)', '(coil|wind)'),
    'sts-capl-output-cutter': ('(capl|pickl)', '(cut|shear)', '(coil|wind)'),
    'hotdip-output-cutter': ('(treat|oil|finish)', '(cut|shear)', '(coil|wind)'),
    'hgi-output-cutter': ('(treat|oil|finish)', '(cut|shear)', '(coil|wind)'),
    'eg-output-cutter': ('(cool|oil|finish)', '(cut|shear)', '(coil|wind)'),
    'gi-coating-cooling': ('(bath|knife)', 'cool', 'temper'),
    'ga-coating-cooling': ('alloy', 'cool', 'temper'),
    'hgi-coating-cooling': ('(bath|knife)', 'cool', 'temper'),
}
FAMILIES: Final = {
    'charge': 'charge', 'blast_furnace': 'hot metal', 'bof': 'oxygen', 'ladle_furnace': 'refine',
    'caster': 'strand', 'shear': 'cut', 'furnace': 'heat', 'roughing': 'rough',
    'finishing_mill': 'finish', 'cooling': 'cool', 'coiler': 'wind', 'leveler': 'level',
    'cooling_bed': 'cool', 'heat_treatment': 'heat treat', 'bloom_mill': 'bloom.*billet',
    'wire_mill': 'billet.*wire', 'laying_head': 'wire rings', 'uncoiler': 'coil',
    'pickling': 'pickl', 'cold_mill': 'cold', 'electrocleaning': 'clean', 'annealing': 'anneal',
    'temper': 'temper', 'oiling': 'oil', 'galvanizing': 'zinc', 'coating': 'coat',
    'alloying': 'alloy', 'electroplating': 'electrode', 'decarburizing': 'decarb',
    'inspection': 'inspect', 'eaf': 'melt', 'aod': 'refine', 'slitter': 'slit',
    'forging': 'forge', 'vacuum_annealing': 'vacuum', 'packaging': 'protect',
    'stock': 'store', 'port': 'berth', 'ship': 'vessel', 'delivery': 'customer',
}
LEGS: Final = {
    'raw-sea': 'load-port bulk-voyage berth unload yard-store process-feed',
    'receiving': 'arrival inspection weigh unload store downstream-feed',
    'road': 'dispatch wait load secure weigh gate-out travel customer-unload customer-accept empty-return',
    'rail': 'consist shunt wagon-load block-move destination-unload destination-store last-mile customer-delivery empty-return',
    'sea': 'quay-transfer berth-wait load-survey voyage unload-survey hub-store last-mile customer-delivery empty-return',
    'internal': 'approach load move unload empty-return idle',
    'quality': 'inspect quarantine reinspect package store custody',
    'receipt': 'ORE COAL LIMESTONE NICKEL_ORE SCRAP TI_INGOT SLAB BLOOM BILLET HR_COIL CR_COIL STS_HR_COIL TI_HR_COIL',
    'fleet': 'truck slab-carrier coil-carrier forklift torpedo ladle-car locomotive railcar ship crane unloader stacker reclaimer conveyor',
}
SCOPE: Final = {
    'receiving': 'receiv.*custody', 'inspection': 'ultrasonic', 'packaging': 'sale',
    'dispatch': 'road.*rail.*sea.*customer', 'carbon-upstream': 'slab/bloom/billet',
    'uniform-fidelity': 'variant.*placement.*route.*leg', 'material-ledger': 'lineage.*conservation',
    'ti-purchased-ingot': 'purchased ingot.*external', 'intermediate-sale': 'sell.*downstream',
    'fleet:dump-truck': 'dump-truck',
    'fleet:ship-bulk': 'ship-bulk',
    'fleet:overhead-crane': 'overhead-crane',
    'fleet:port-crane': 'port-crane',
    'fleet:railcar-coil': 'railcar-coil',
    'fleet:railcar-bulk': 'railcar-bulk',
    'handling:receiving-cradle': 'receiving-cradle',
}
PRODUCT_SEMANTICS: Final = {
    'slab': 'slab.*sale.*feed', 'bloom': 'bloom.*sale.*feed', 'billet': 'billet.*sale.*feed',
    'hr': 'slab.*cool.*coil.*sale.*feed', 'plate': 'plate.*ultrasonic',
    'wire': 'bloom.*billet.*wire.*cool', 'cr': 'hr.*cold.*anneal.*sale.*feed',
    'gi': 'cr.*zinc', 'ga': 'cr.*alloy', 'hgi': 'hr.*without compulsory cold',
    'eg': 'cr.*electroplat.*oven', 'go': 'decarb.*insulation.*domain', 'ngo': 'non oriented.*insulation',
    'sts-hr': 'scrap.*eaf.*hapl', 'sts-cr': 'cold.*capl.*tll.*stl',
    'sts-plate': 'eaf.*hot leveling.*cold leveling', 'ti-hr': 'purchased.*ingot.*no in-plant',
    'ti-cr': 'tll.*coil or stl', 'ti-sheet': 'shl.*without forcing.*stl',
    'ti-plate': 'purchased.*ingot.*gas cutting',
}


def boundary(step_id: str) -> str:
    """Classify the independently recorded 49 replaced demo boundaries."""
    product, ordinal = step_id.rsplit('-', 1)
    if ordinal == '01':
        return 'receiving'
    if step_id in {'plate-09', 'wire-09'}:
        return 'inspection'
    if step_id in PACKAGED:
        return 'packaging'
    if int(ordinal) == COUNTS[product]:
        return 'dispatch'
    return 'retained'


def require(condition: bool, code: str, reference: str) -> None:
    if not condition:
        raise CoverageError(code, reference)


def matches(pattern: str, value: str, reference: str) -> None:
    require(re.search(pattern, value, re.IGNORECASE) is not None, 'missing_or_generic_semantics', reference)


def validate_expected(registry: Registry) -> None:
    """Check independently transcribed identities, functions, provenance and branch obligations."""
    requirements = {row.id: row for row in registry.requirements()}
    expected: dict[str, str] = {}
    for product, count in COUNTS.items():
        core_ids = [f'{product}-{n:02}' for n in range(1, count + 1) if boundary(f'{product}-{n:02}') == 'retained']
        for step_id, semantic in zip(core_ids, CORE[product].split(','), strict=True):
            expected[f'src:{step_id}'] = semantic
    expected.update({f'src:{key}': row[2] for key, row in PARTS.items()})
    source_ids = frozenset(expected)
    expected.update({f'scope:{key}': value for key, value in SCOPE.items()})
    expected.update({f'scope:product:{key}': value for key, value in PRODUCT_SEMANTICS.items()})
    expected.update({f'scope:asset-family:{key}': value for key, value in FAMILIES.items()})
    expected.update({f'scope:{family}:{phase}': re.escape(phase) for family, phases in LEGS.items() for phase in phases.split()})
    scope_ids = frozenset(expected) - source_ids
    for rows, allowed_ids in ((registry.source_requirements, source_ids), (registry.approved_scope_requirements, scope_ids)):
        for row in rows:
            require(row.id in allowed_ids, 'requirement_collection', row.id)
    for key, semantic in expected.items():
        require(key in requirements, 'missing_requirement', key)
        row = requirements[key]
        matches(semantic, row.expected_function, key)
        require(set(row.products) <= PRODUCTS, 'unknown_product', key)
        require(bool({'T40', 'T43', 'T44'} & set(row.delivery_tasks)) and any(int(t[1:]) < 40 for t in row.delivery_tasks), 'missing_delivery_task', key)
    require(set(expected) == set(requirements), 'unknown_requirement', ','.join(sorted(set(requirements) - set(expected))))
    for row in registry.source_requirements:
        suffix = row.id.removeprefix('src:')
        synthetic = suffix in {'ti-cr-04', 'ti-cr-06', 'ti-sheet-04', 'ti-sheet-06', 'hgi-output-cutter', 'hgi-coating-cooling'} or (suffix.startswith('hgi-') and suffix[-2:].isdigit())
        require(row.requirement_origin == ('synthetic_design' if synthetic else 'public_source'), 'source_origin', row.id)
        if suffix in PARTS:
            products, sources, _, branch = PARTS[suffix]
            required_sources = {f'showroom:{s}' if s.startswith('M') else f'official:{s}' for s in sources.split()} | ({'scope:approved-plan'} if synthetic else set[str]())
            require(set(row.products) == set(products.split()) and set(row.source_ids) == required_sources, 'source_product_mapping', row.id)
            require(not branch or row.source_branch == branch, 'source_branch', row.id)
            if suffix in POSITIONED:
                matches('.*'.join(POSITIONED[suffix]), row.source_branch, f'{row.id}/source_branch')
        else:
            product = suffix.rsplit('-', 1)[0]
            required_sources = {f'showroom:{SHOWROOM[product]}'} | ({'official:P1', 'scope:approved-plan'} if product == 'hgi' else set[str]())
            require(row.products == (product,) and set(row.source_ids) == required_sources, 'source_product_mapping', row.id)
    for row in registry.approved_scope_requirements:
        require('scope:approved-plan' in row.source_ids and row.requirement_origin != 'public_source', 'scope_origin', row.id)
        if row.id.startswith('scope:product:'):
            require(row.products == (row.id.removeprefix('scope:product:'),), 'scope_product_mapping', row.id)
