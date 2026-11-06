from functools import lru_cache
from pathlib import Path

from pydantic import TypeAdapter

from .journey_schemas import InvalidProductRoute, ProductDefinition


@lru_cache(maxsize=1)
def products() -> tuple[ProductDefinition, ...]:
    catalog = TypeAdapter(tuple[ProductDefinition, ...]).validate_json(
        (Path(__file__).parent / "data" / "journey_products.json").read_text()
    )
    if not catalog or len({product.id for product in catalog}) != len(catalog):
        raise InvalidProductRoute("catalog", "empty or duplicate product IDs")
    return catalog


def product(product_id: str) -> ProductDefinition:
    found = next((item for item in products() if item.id == product_id), None)
    if found is None:
        raise UnknownProduct(product_id)
    return found


class UnknownProduct(ValueError):
    def __init__(self, product_id: str) -> None:
        self.product_id = product_id
        super().__init__(f"Unknown journey product: {product_id}")
