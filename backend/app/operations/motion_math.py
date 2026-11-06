"""Pure quaternion/contact projection in metres; no wall-clock or state transitions."""

from math import cos, sin, sqrt
from typing import assert_never

from .motion_bindings import AssetBinding
from .motion_types import (
    Anchor,
    ChannelValue,
    MaterialSupport,
    MotionEnvelope,
    MotionError,
    MotionRecipe,
    Quaternion,
    Vector,
    require,
)
from .world_types import Pose


def normalize(q: Quaternion) -> Quaternion:
    n = sqrt(sum(x * x for x in q))
    return q[0] / n, q[1] / n, q[2] / n, q[3] / n


def multiply(a: Quaternion, b: Quaternion) -> Quaternion:
    x, y, z, w = a
    X, Y, Z, W = b
    return normalize(
        (
            w * X + x * W + y * Z - z * Y,
            w * Y - x * Z + y * W + z * X,
            w * Z + x * Y - y * X + z * W,
            w * W - x * X - y * Y - z * Z,
        )
    )


def rotate(q: Quaternion, p: Vector) -> Vector:
    x, y, z, w = normalize(q)
    a, b, c = p
    tx, ty, tz = 2 * (y * c - z * b), 2 * (z * a - x * c), 2 * (x * b - y * a)
    return (
        a + w * tx + y * tz - z * ty,
        b + w * ty + z * tx - x * tz,
        c + w * tz + x * ty - y * tx,
    )


def add(a: Vector, b: Vector) -> Vector:
    return a[0] + b[0], a[1] + b[1], a[2] + b[2]


def subtract(a: Vector, b: Vector) -> Vector:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def progress(envelope: MotionEnvelope) -> float:
    if envelope.frozen_progress is not None:
        return envelope.frozen_progress
    return max(
        0.0,
        min(
            1.0,
            (envelope.effective_sim_ms - envelope.phase_start_ms)
            / (envelope.phase_end_ms - envelope.phase_start_ms),
        ),
    )


def channel_values(
    envelope: MotionEnvelope, recipe: MotionRecipe
) -> tuple[ChannelValue, ...]:
    windows = {w.id: w for w in recipe.windows}
    result: list[ChannelValue] = []
    for c in envelope.channels:
        window = windows[c.window_id]
        t = max(
            0.0,
            min(1.0, (progress(envelope) - window.start) / (window.end - window.start)),
        )
        if c.start_value == c.end_value or t == 0:
            value = c.start_value
        elif t == 1:
            value = c.end_value
        else:
            value = (1 - t) * c.start_value + t * c.end_value
        result.append(
            ChannelValue(
                function_id=c.function_id,
                node_id=c.node_id,
                kind=c.kind,
                value=value,
                axis=c.axis,
                pivot_m=c.pivot_m,
            )
        )
    return tuple(result)


def moved_anchor(
    anchor: Anchor, binding: AssetBinding, channels: tuple[ChannelValue, ...]
) -> Anchor:
    socket = next(s for s in binding.sockets if s.socket_id == anchor.socket_id)
    moved = anchor
    for function_id in reversed(socket.motion_function_ids):
        motion = next((c for c in channels if c.function_id == function_id), None)
        require(motion is not None, "binding", socket.socket_id)
        if motion is None:
            raise MotionError("binding", socket.socket_id)
        moved = apply_channel(moved, motion)
    return moved


def apply_channel(anchor: Anchor, motion: ChannelValue) -> Anchor:
    """Compose one root-rest joint delta; parent deltas carry child axes and pivots."""
    match motion.kind:
        case "translation":
            delta = (
                motion.axis[0] * motion.value,
                motion.axis[1] * motion.value,
                motion.axis[2] * motion.value,
            )
            return anchor.model_copy(
                update={"position_m": add(anchor.position_m, delta)}
            )
        case "rotation":
            sine = sin(motion.value / 2)
            q = (
                motion.axis[0] * sine,
                motion.axis[1] * sine,
                motion.axis[2] * sine,
                cos(motion.value / 2),
            )
            position = add(
                motion.pivot_m, rotate(q, subtract(anchor.position_m, motion.pivot_m))
            )
            return anchor.model_copy(
                update={
                    "position_m": position,
                    "orientation_xyzw": multiply(q, anchor.orientation_xyzw),
                }
            )
        case "state":
            return anchor
        case unreachable:
            assert_never(unreachable)


def contact_pose(
    root: Pose, anchor: Anchor, material: MaterialSupport
) -> tuple[Vector, Vector, Quaternion]:
    root_q = (0.0, sin(root.yaw_rad / 2), 0.0, cos(root.yaw_rad / 2))
    contact = add(root.position, rotate(root_q, anchor.position_m))
    orientation = multiply(
        multiply(root_q, anchor.orientation_xyzw), material.orientation_xyzw
    )
    support = (
        material.support_local_mm[0] / 1000,
        material.support_local_mm[1] / 1000,
        material.support_local_mm[2] / 1000,
    )
    return subtract(contact, rotate(orientation, support)), contact, orientation
