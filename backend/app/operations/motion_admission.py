"""Admit every server binding against the reviewed policy and actual graph rest pose."""

from __future__ import annotations

from math import dist

from .motion_bindings import AssetBinding
from .world_contract import FactoryWorld
from .motion_policy import load_policies
from .motion_effective_policy import effective_policy
from .motion_types import MotionError, require


def validate_binding(binding: AssetBinding, world: FactoryWorld) -> None:
    from .motion_bindings import BathPathAssetBinding
    if isinstance(binding, BathPathAssetBinding):
        from .motion_bath_path import validate_bath_binding
        validate_bath_binding(binding, world)
    if hasattr(binding, 'internal_feeds'):
        from .motion_internal_feed import validate_internal_feed
        for feed in binding.internal_feeds:
            validate_internal_feed(feed,binding)
    owner = next((o for o in world.owners if o.id == binding.owner_id), None)
    if owner is None:
        raise MotionError("binding", binding.owner_id)
    for socket in binding.sockets:
        graph_socket = next(
            (s for s in owner.sockets if s.id == socket.socket_id), None
        )
        if graph_socket is None:
            raise MotionError("unknown_socket", socket.socket_id)
        require(
            dist(graph_socket.pose.position, socket.position_m) <= 0.01,
            "binding",
            socket.socket_id,
        )
    policies = load_policies()
    policy = next((p for p in policies.policies if p.id == binding.policy_id), None)
    if policy is None:
        raise MotionError("binding", binding.policy_id)
    policy = effective_policy(policies, policy.category, policy.kind, binding.owner_id, binding.policy_id)
    admitted = set(policy.required_functions) | set(policy.state_bound_fixed_functions)
    require(
        {f.function_id for f in binding.functions} == admitted,
        "unknown_function",
        binding.policy_id,
    )
    for function in binding.functions:
        require(
            (function.kind == "state")
            == (function.function_id in policy.state_bound_fixed_functions),
            "binding",
            function.function_id,
        )
