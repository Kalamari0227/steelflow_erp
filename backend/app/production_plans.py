"""Immutable demonstration plans, independent of order/coil fixtures."""
from dataclasses import dataclass

from .production_schemas import Product, StageId


@dataclass(frozen=True, slots=True)
class StepPlan:
    stage: StageId
    name: str
    equipment: str
    output_form: str


@dataclass(frozen=True, slots=True)
class BatchPlan:
    product: Product
    mass_kg: int
    start_tick: int
    steps: tuple[StepPlan, ...]


STAGE_NAMES: tuple[tuple[StageId, str], ...] = (
    ("ironmaking", "제선"), ("steelmaking", "제강"), ("casting", "연속주조"),
    ("hot_rolling", "열간압연"), ("cold_rolling", "냉간압연"),
    ("coating", "도금"), ("finishing", "정정·검사"), ("stock", "제품 재고"),
)


def make_plan(product: Product, index: int) -> BatchPlan:
    casting = product if product in ("SLAB", "BLOOM", "BILLET") else "SLAB"
    steps = [
        StepPlan("ironmaking", "원료 장입", "BF-01", "ORE"),
        StepPlan("ironmaking", "고로 환원·출선", "BF-01", "HOT_METAL"),
        StepPlan("steelmaking", "전로 취련·출강", "BOF-01", "LIQUID_STEEL"),
        StepPlan("steelmaking", "2차 정련", "LF-01", "LIQUID_STEEL"),
        StepPlan("casting", f"{casting} 연속주조", f"CASTER-{casting}", casting),
        StepPlan("casting", "절단·냉각", f"CASTER-{casting}", casting),
    ]
    if product not in ("SLAB", "BLOOM", "BILLET"):
        steps += [StepPlan("hot_rolling", "가열로 재가열", "REHEAT-01", "SLAB"),
                  StepPlan("hot_rolling", "조압연·사상압연", "HSM-A", "HR")]
    if product in ("CR", "GI", "GA", "EG"):
        steps += [StepPlan("cold_rolling", "산세", "PICKLE-01", "HR"),
                  StepPlan("cold_rolling", "냉간압연", "CRM-01", "CR"),
                  StepPlan("cold_rolling", "소둔", "ANNEAL-01", "CR")]
    if product == "HGI":
        steps += [StepPlan("coating", "산세·표면준비", "HGI-PICKLE-01", "HR")]
    if product in ("GI", "GA", "HGI"):
        steps += [StepPlan("coating", "용융아연 도금", "HDG-01", "GI" if product == "GA" else product)]
        if product == "GA":
            steps += [StepPlan("coating", "합금화 열처리", "ALLOY-01", "GA")]
    if product == "EG":
        steps += [StepPlan("coating", "전해 아연 도금", "EGL-01", "EG")]
    steps += [StepPlan("finishing", "형상·표면 검사", "QC-01", product),
              StepPlan("finishing", "포장·라벨", "PACK-01", product),
              StepPlan("stock", "제품 입고", "PRODUCTION-STOCK", product)]
    return BatchPlan(product, 18000 + index * 1000, -index, tuple(steps))


PLANS = tuple(make_plan(product, index) for index, product in enumerate(
    ("SLAB", "BLOOM", "BILLET", "HR", "CR", "GI", "GA", "EG", "HGI")
))
