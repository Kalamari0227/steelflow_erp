"""Approved T2 section order and T9 receipt entries, independent of the generator.

These IDs transcribe the approved source branches and recipe entry table. They
are not learned from candidate coordinates or candidate coverage counts.
"""
from typing import Final

RECEIPT_ENTRIES: Final = {
    'ORE': ('CHARGE-A',), 'COAL': ('CHARGE-A',), 'LIMESTONE': ('CHARGE-A',),
    'NICKEL_ORE': ('STS-HR-02',), 'SCRAP': ('STS-HR-02', 'STS-PLATE-02'),
    'TI_INGOT': ('TI-HR-02', 'TI-PLATE-02'),
    'SLAB': ('CS-HR-02', 'CS-PLATE-02'), 'BLOOM': ('CS-WIRE-02',),
    'BILLET': ('CS-WIRE-06',),
    'HR_COIL': ('CS-CR-02', 'CS-HGI-02', 'CS-GO-02', 'CS-NGO-02'),
    'CR_COIL': ('CS-GI-02', 'CS-GA-02', 'CS-EG-02'),
    'STS_HR_COIL': ('STS-CR-02',), 'TI_HR_COIL': ('TI-CR-02', 'TI-SHEET-02'),
}
# source function, product, upstream work owner, downstream work owner.
FUNCTION_SECTIONS: Final = (
    ('go-base-coating', 'go', 'CS-GO-06', 'CS-GO-07'),
    ('cr-cold-mill-output-cutter', 'cr', 'CS-CR-04', 'CS-CR-05'),
    ('cr-finished-output-cutter', 'cr', 'CS-CR-08', 'CS-CR-09'),
    ('go-pickling-output-cutter', 'go', 'CS-GO-04', 'CS-GO-05'),
    ('go-basecoat-output-cutter', 'go', 'func-go-base-coating-go', 'CS-GO-07'),
    ('go-finished-output-cutter', 'go', 'CS-GO-10', 'CS-GO-11'),
    ('ngo-pickling-output-cutter', 'ngo', 'CS-NGO-04', 'CS-NGO-05'),
    ('ngo-finished-output-cutter', 'ngo', 'func-ngo-drying-ngo', 'CS-NGO-08'),
    ('sts-hapl-output-cutter', 'sts-hr', 'STS-HR-12', 'STS-HR-13'),
    ('sts-capl-output-cutter', 'sts-cr', 'STS-CR-05', 'STS-CR-06'),
    ('hotdip-output-cutter', 'gi', 'CS-GI-08', 'CS-GI-09'),
    ('hotdip-output-cutter', 'ga', 'CS-GA-09', 'CS-GA-10'),
    ('hgi-output-cutter', 'hgi', 'CS-HGI-08', 'CS-HGI-09'),
    ('eg-output-cutter', 'eg', 'CS-EG-08', 'CS-EG-09'),
    ('gi-coating-cooling', 'gi', 'func-coating-air-knife-gi', 'CS-GI-06'),
    ('ga-coating-cooling', 'ga', 'CS-GA-06', 'CS-GA-07'),
    ('hgi-coating-cooling', 'hgi', 'func-coating-air-knife-hgi', 'CS-HGI-06'),
)

OPTIONAL_EXIT_BRANCHES: Final = (
    ('src:ti-tll-coil', 'ti-cr', ('TI-CR-08', 'func-ti-stl-skelp-ti-cr')),
    ('src:ti-shl-sheet', 'ti-sheet', ('TI-SHEET-08', 'TI-CR-08', 'func-ti-stl-skelp-ti-cr')),
)
