"""Read one contract-only projection request from stdin; emit pose or typed error."""

import json
import sys
from pathlib import Path

from pydantic import ValidationError

from .contracts_v3_core import ContractViolation
from .motion import evaluate_motion, parse_motion_registry
from .motion_types import MotionError
from .motion_request import MotionRequest, parse_motion_request

from .world_types import WorldContractError

ProjectionRequest = MotionRequest


def main() -> int:
    """Run the actual pure evaluator without a service, DB, clock or port."""
    try:
        request = parse_motion_request(sys.stdin.buffer.read())
        registry_path = (
            Path(__file__).resolve().parents[3] / "shared/motion-recipes.json"
        )
        registry = parse_motion_registry(registry_path.read_bytes())
        result = evaluate_motion(request.envelope, request.context, registry)
    except (MotionError, WorldContractError) as error:
        print(json.dumps({"error": {"code": error.code, "reference": error.reference}}))
        return 2
    except (ValidationError, ContractViolation) as error:
        print(
            json.dumps({"error": {"code": "invalid_contract", "reference": str(error)}})
        )
        return 2
    print(result.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
