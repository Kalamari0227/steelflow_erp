"""Bind requested poses to actual server identities, material IO and custody."""

from math import dist
from typing import assert_never

from .contracts_v3_transport import Attachment
from .motion_bindings import AssetBinding, FORM_FAMILIES
from .motion_context import MotionContext
from .motion_admission import validate_binding
from .motion_types import (
    Anchor,
    ChannelValue,
    MaterialSupport,
    MotionEnvelope,
    MotionError,
    MotionRecipe,
    require,
)
from .world_types import Pose


def resolved_attachment(row: Attachment, context: MotionContext) -> tuple[str, str]:
    if row.kind == "slot":
        location = next(
            (s for s in (*context.world.slots, *context.world.ports) if s.id == row.owner_id),
            None,
        )
        if location is None:
            raise MotionError("attachment", row.id)
        require(location.socket_id == row.socket_id, "attachment", row.id)
        return location.owner_id, location.socket_id
    return row.owner_id, row.socket_id


def root_pose(owner_id: str, context: MotionContext) -> Pose:
    owner = next((o for o in context.world.owners if o.id == owner_id), None)
    if owner is None:
        raise MotionError("unknown_socket", owner_id)
    vehicle = next(
        (v for v in context.snapshot.vehicle_states if v.fleet_id == owner_id), None
    )
    require(
        owner.kind not in {"vehicle", "railcar", "ship"} or vehicle is not None,
        "execution",
        owner_id,
    )
    if vehicle is not None:
        return Pose(position=vehicle.position_m, yaw_rad=vehicle.yaw_rad)
    return owner.pose


def validate_anchor(
    anchor: Anchor, material: MaterialSupport, context: MotionContext
) -> AssetBinding:
    binding = next(
        (b for b in context.asset_bindings if b.owner_id == anchor.owner_id), None
    )
    if binding is None:
        raise MotionError("binding", anchor.owner_id)
    socket = next((s for s in binding.sockets if s.socket_id == anchor.socket_id), None)
    if socket is None:
        raise MotionError("unknown_socket", anchor.socket_id)
    owner = next((o for o in context.world.owners if o.id == anchor.owner_id), None)
    require(
        owner is not None and any(s.id == anchor.socket_id for s in owner.sockets),
        "unknown_socket",
        anchor.socket_id,
    )
    if owner is None:
        raise MotionError("unknown_socket", anchor.socket_id)
    graph_socket = next(s for s in owner.sockets if s.id == anchor.socket_id)
    require(
        dist(graph_socket.pose.position, socket.position_m) <= 0.01,
        "binding",
        anchor.socket_id,
    )
    require(socket.family in FORM_FAMILIES[material.form], "form", material.form)
    require(
        (socket.position_m, socket.orientation_xyzw)
        == (anchor.position_m, anchor.orientation_xyzw),
        "binding",
        anchor.socket_id,
    )
    validate_binding(binding, context.world)
    return binding


def validate_channel_values(
    channels: tuple[ChannelValue, ...], binding: AssetBinding
) -> None:
    require(
        len({c.function_id for c in channels}) == len(channels), "duplicate", "channels"
    )
    for channel in channels:
        descriptor = next(
            (f for f in binding.functions if f.function_id == channel.function_id), None
        )
        if descriptor is None:
            raise MotionError("unknown_function", channel.function_id)
        require(
            (descriptor.node_id, descriptor.kind, descriptor.axis, descriptor.pivot_m)
            == (channel.node_id, channel.kind, channel.axis, channel.pivot_m),
            "binding",
            channel.function_id,
        )
        require(
            descriptor.min_value <= channel.value <= descriptor.max_value,
            "binding",
            channel.function_id,
        )


def validate_execution(
    envelope: MotionEnvelope, context: MotionContext, recipe: MotionRecipe
) -> None:
    state = context.snapshot
    start: int | None = None
    end: int | None = None
    status: str = "CUSTODY"
    match envelope.execution_kind:
        case "process":
            process = next(
                (p for p in state.processes if p.id == envelope.execution_id), None
            )
            if process is None:
                raise MotionError("execution", envelope.execution_id)
            steps = (
                set(recipe.source_step_ids)
                | set(recipe.compiled_step_ids)
                | {s.removeprefix("step:") for s in recipe.compiled_step_ids}
            )
            require(
                process.route_step_id in steps
                and process.equipment_id == envelope.anchor.owner_id,
                "execution",
                process.id,
            )
            batches = {
                b.id for b in state.process_batches if b.process_id == process.id
            }
            require(
                any(
                    io.batch_id in batches
                    and io.material_version_id == envelope.material.material_version_id
                    for io in state.batch_io
                ),
                "execution",
                process.id,
            )
            start, end, status = process.start_ms, process.end_ms, process.status
        case "transport":
            job = next(
                (j for j in state.transport_jobs if j.id == envelope.execution_id), None
            )
            if job is None:
                raise MotionError("execution", envelope.execution_id)
            require(
                job.material_id == envelope.material.material_id
                and (job.fleet_id or job.equipment_id) == envelope.anchor.owner_id,
                "execution",
                job.id,
            )
            require(
                {job.from_node_id, job.to_node_id}
                <= {n.id for n in context.world.nodes},
                "execution",
                job.id,
            )
            if job.fleet_id is not None:
                vehicle = next(
                    (v for v in state.vehicle_states if v.fleet_id == job.fleet_id),
                    None,
                )
                require(
                    vehicle is not None
                    and vehicle.current_job_id == job.id
                    and vehicle.node_id in {n.id for n in context.world.nodes},
                    "execution",
                    job.id,
                )
            start, end, status = job.start_ms, job.end_ms, job.status
        case "logistics":
            require(
                envelope.execution_id == envelope.attachment_id,
                "execution",
                envelope.execution_id,
            )
        case unreachable:
            assert_never(unreachable)
    if envelope.execution_kind != "logistics":
        require(
            start == envelope.phase_start_ms and end == envelope.phase_end_ms,
            "execution",
            envelope.execution_id,
        )
    if status in {"BLOCKED", "STRUCTURAL_BLOCKED"}:
        require(
            envelope.clock_state == "blocked" and envelope.frozen_progress is not None,
            "held_progress_required",
            envelope.execution_id,
        )
    if status in {"QUEUED", "IDLE", "ASSIGNED"} or not state.run.playing:
        require(
            envelope.clock_state != "running" and envelope.frozen_progress is not None,
            "held_progress_required",
            envelope.execution_id,
        )
