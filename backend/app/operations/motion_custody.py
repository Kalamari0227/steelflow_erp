"""Current server custody and exact release/acquire continuity checks."""

from math import dist
from .contracts_v3_transport import Attachment
from .motion_context import MotionContext
from .motion_types import ChannelValue, MotionEnvelope, MotionError, require
from .motion_internal_feed import project_support, validate_feed_boundary, FeedProjection
from .motion_validation import (
    resolved_attachment,
    root_pose,
    validate_anchor,
    validate_channel_values,
)


def validate_authority(envelope: MotionEnvelope, context: MotionContext) -> Attachment:
    state, run = context.snapshot, context.snapshot.run
    require(envelope.run_id == run.id, "stale_run", envelope.run_id)
    require(
        (envelope.bundle_id, envelope.bundle_hash) == (run.bundle_id, run.bundle_hash),
        "stale_bundle",
        envelope.bundle_id,
    )
    require(envelope.revision == run.revision, "stale_revision", envelope.execution_id)
    require(
        envelope.confirmed_sim_ms == run.elapsed_ms, "stale_time", envelope.execution_id
    )
    require(envelope in context.authorizations, "unauthorized", envelope.execution_id)
    require(
        envelope.frozen_progress is not None
        or envelope.effective_sim_ms == envelope.confirmed_sim_ms,
        "held_progress_required",
        envelope.execution_id,
    )
    material = next(
        (m for m in state.materials if m.id == envelope.material.material_id), None
    )
    if material is None:
        raise MotionError("material_version", envelope.material.material_id)
    require(
        material.active and material.availability_status != "CONSUMED",
        "consumed_material",
        material.id,
    )
    require(
        (material.current_version_id, material.form, material.dimensions)
        == (
            envelope.material.material_version_id,
            envelope.material.form,
            envelope.material.dimensions,
        ),
        "material_version",
        material.id,
    )
    current = [
        a
        for a in state.attachments
        if a.material_id == material.id
        and a.acquired_at_ms <= run.elapsed_ms
        and (a.released_at_ms is None or run.elapsed_ms < a.released_at_ms)
    ]
    require(len(current) == 1, "attachment", material.id)
    attachment = current[0]
    require(
        attachment.id == envelope.attachment_id and attachment.released_at_ms is None,
        "attachment",
        attachment.id,
    )
    require(
        resolved_attachment(attachment, context)
        == (envelope.anchor.owner_id, envelope.anchor.socket_id),
        "attachment",
        attachment.id,
    )
    return attachment


def validate_boundary(
    envelope: MotionEnvelope,
    context: MotionContext,
    contact: tuple[float, float, float],
    current_projection: FeedProjection | None = None,
    current_values: tuple[ChannelValue, ...] | None = None,
) -> None:
    boundary = envelope.boundary
    if boundary is None:
        return
    require(
        boundary.at_ms == envelope.confirmed_sim_ms,
        "boundary",
        "boundary requires exact event snapshot",
    )
    old = next(
        (
            a
            for a in context.snapshot.attachments
            if a.id == boundary.released_attachment_id
        ),
        None,
    )
    current = next(
        (
            a
            for a in context.snapshot.attachments
            if a.id == boundary.acquired_attachment_id
        ),
        None,
    )
    require(old is not None and current is not None, "boundary", envelope.execution_id)
    if old is None or current is None:
        raise MotionError("boundary", envelope.execution_id)
    require(
        old.id != current.id and current.id == envelope.attachment_id,
        "boundary",
        current.id,
    )
    require(
        old.released_at_ms == current.acquired_at_ms == boundary.at_ms,
        "boundary",
        current.id,
    )
    require(
        old.material_id
        == boundary.previous_material.material_id
        == envelope.material.material_id,
        "boundary",
        old.id,
    )
    require(
        resolved_attachment(old, context)
        == (boundary.previous_anchor.owner_id, boundary.previous_anchor.socket_id),
        "boundary",
        old.id,
    )
    version = next(
        (
            v
            for v in context.snapshot.material_versions
            if v.id == boundary.previous_material.material_version_id
        ),
        None,
    )
    require(
        version is not None
        and (version.material_id, version.form, version.dimensions)
        == (
            old.material_id,
            boundary.previous_material.form,
            boundary.previous_material.dimensions,
        ),
        "material_version",
        old.id,
    )
    binding = validate_anchor(
        boundary.previous_anchor, boundary.previous_material, context
    )
    validate_channel_values(boundary.previous_channels, binding)
    previous = project_support(boundary.previous_anchor,boundary.previous_material,boundary.previous_channels,binding,root_pose(boundary.previous_anchor.owner_id,context))
    receipt = None
    if current_projection is not None:
        from .motion_finishing_continuity import FinishingBoundary, qualified_contact
        current_binding = validate_anchor(envelope.anchor, envelope.material, context)
        # Current authoritative channel values are passed by the pure projector.
        values = current_values if current_values is not None else ()
        if binding == current_binding:
            receipt = qualified_contact(FinishingBoundary(envelope, binding, root_pose(envelope.anchor.owner_id, context), previous, current_projection, values))
    if receipt is None:
        require(dist(previous.contact_m,contact) <= 0.01+1e-12,"contact",current.id)
    if current_projection is not None:
        validate_feed_boundary(previous,current_projection,boundary.previous_material,envelope.material)
