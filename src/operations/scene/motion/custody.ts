import type { MotionContext } from './context';
import { assertNever, equalData, requireMotion } from './errors';
import type { Anchor, MotionEnvelope, MotionRecipe, MaterialSupport } from './shapes';

type Attachment = MotionContext['snapshot']['attachments'][number];
export function resolvedAttachment(attachment: Attachment, context: MotionContext): { readonly owner_id: string; readonly socket_id: string } {
  switch (attachment.kind) {
    case 'slot': {
      const location = [...context.world.slots, ...context.world.ports].find(s => s.id === attachment.owner_id);
      requireMotion(location !== undefined && location.socket_id === attachment.socket_id, 'attachment', attachment.id);
      return location;
    }
    case 'equipment': case 'hook': case 'vehicle': case 'railcar': case 'ship': case 'customer': return attachment;
    default: return assertNever(attachment.kind);
  }
}
function matchAnchor(attachment: Attachment, anchor: Anchor, context: MotionContext): void {
  const resolved = resolvedAttachment(attachment, context);
  requireMotion(resolved.owner_id === anchor.owner_id && resolved.socket_id === anchor.socket_id, 'attachment', attachment.id);
}
export function materialVersion(material: MaterialSupport, context: MotionContext): void {
  const version = context.snapshot.material_versions.find(v => v.id === material.material_version_id);
  requireMotion(version !== undefined && version.material_id === material.material_id && version.form === material.form && equalData(version.dimensions, material.dimensions), 'material_version', material.material_id);
}
export function validateCustody(envelope: MotionEnvelope, context: MotionContext): Attachment {
  const material = context.snapshot.materials.find(m => m.id === envelope.material.material_id);
  requireMotion(material !== undefined, 'material_version', envelope.material.material_id);
  requireMotion(material.active && material.availability_status !== 'CONSUMED', 'consumed_material', material.id);
  requireMotion(material.current_version_id === envelope.material.material_version_id, 'material_version', material.id);
  materialVersion(envelope.material, context);
  const current = context.snapshot.attachments.filter(a => a.material_id === material.id && a.acquired_at_ms <= envelope.confirmed_sim_ms && (a.released_at_ms === null || envelope.confirmed_sim_ms < a.released_at_ms));
  requireMotion(current.length === 1 && current[0]?.id === envelope.attachment_id, 'attachment', envelope.attachment_id);
  const attachment = current[0];
  requireMotion(attachment !== undefined && attachment.released_at_ms === null, 'attachment', envelope.attachment_id);
  matchAnchor(attachment, envelope.anchor, context);
  return attachment;
}

export function validateExecution(envelope: MotionEnvelope, context: MotionContext, recipe: MotionRecipe): void {
  requireMotion(envelope.execution_kind === recipe.execution_kind, 'execution', envelope.execution_id);
  let status: string;
  switch (envelope.execution_kind) {
    case 'process': {
      const process = context.snapshot.processes.find(p => p.id === envelope.execution_id);
      requireMotion(process !== undefined && process.equipment_id === envelope.anchor.owner_id, 'execution', envelope.execution_id);
      requireMotion([...recipe.compiled_step_ids, ...recipe.compiled_step_ids.map(id => id.replace(/^step:/, '')), ...recipe.source_step_ids].includes(process.route_step_id), 'execution', process.id);
      requireMotion(process.start_ms === envelope.phase_start_ms && process.end_ms === envelope.phase_end_ms, 'execution', process.id);
      const batches = context.snapshot.process_batches.filter(b => b.process_id === process.id);
      requireMotion(context.snapshot.batch_io.some(io => batches.some(b => b.id === io.batch_id) && io.material_version_id === envelope.material.material_version_id && ['INPUT', 'STOCK_ADDITION', 'OUTPUT', 'BYPRODUCT'].includes(io.role)), 'execution', process.id);
      status = process.status; break;
    }
    case 'transport': {
      const job = context.snapshot.transport_jobs.find(j => j.id === envelope.execution_id);
      requireMotion(job !== undefined && job.material_id === envelope.material.material_id && (job.equipment_id ?? job.fleet_id) === envelope.anchor.owner_id, 'execution', envelope.execution_id);
      requireMotion(context.world.nodes.some(n => n.id === job.from_node_id) && context.world.nodes.some(n => n.id === job.to_node_id), 'execution', job.id);
      if (job.fleet_id !== null) {
        const vehicle = context.snapshot.vehicle_states.find(v => v.fleet_id === job.fleet_id);
        requireMotion(vehicle !== undefined && vehicle.current_job_id === job.id && context.world.nodes.some(n => n.id === vehicle.node_id), 'execution', job.id);
      }
      requireMotion(job.start_ms === envelope.phase_start_ms && job.end_ms === envelope.phase_end_ms, 'execution', job.id);
      status = job.status; break;
    }
    case 'logistics': requireMotion(envelope.execution_id === envelope.attachment_id, 'execution', envelope.execution_id); status = 'HELD'; break;
    default: return assertNever(envelope.execution_kind);
  }
  if (status === 'BLOCKED' || status === 'STRUCTURAL_BLOCKED') requireMotion(envelope.clock_state === 'blocked' && envelope.frozen_progress !== null, 'held_progress_required', envelope.execution_id);
  if (['QUEUED', 'IDLE', 'ASSIGNED'].includes(status) || !context.snapshot.run.playing) requireMotion(envelope.clock_state !== 'running' && envelope.frozen_progress !== null, 'held_progress_required', envelope.execution_id);
  requireMotion(envelope.clock_state !== 'running' || envelope.effective_sim_ms === envelope.confirmed_sim_ms || envelope.frozen_progress !== null, 'held_progress_required', envelope.execution_id);
}

/** Event metadata is checked after current execution, anchor and channel geometry. */
export function validateBoundary(envelope: MotionEnvelope, context: MotionContext): void {
  const boundary = envelope.boundary;
  if (boundary === null) return;
  requireMotion(boundary.at_ms === envelope.confirmed_sim_ms, 'boundary', 'boundary requires exact event snapshot');
  const old = context.snapshot.attachments.find(a => a.id === boundary.released_attachment_id);
  const current = context.snapshot.attachments.find(a => a.id === boundary.acquired_attachment_id);
  requireMotion(old !== undefined && current !== undefined, 'boundary', envelope.execution_id);
  requireMotion(old.id !== current.id && current.id === envelope.attachment_id, 'boundary', current.id);
  requireMotion(old.released_at_ms === current.acquired_at_ms && current.acquired_at_ms === boundary.at_ms, 'boundary', current.id);
  requireMotion(old.material_id === boundary.previous_material.material_id && old.material_id === envelope.material.material_id, 'boundary', old.id);
  const resolved = resolvedAttachment(old, context);
  requireMotion(resolved.owner_id === boundary.previous_anchor.owner_id && resolved.socket_id === boundary.previous_anchor.socket_id, 'boundary', old.id);
  materialVersion(boundary.previous_material, context);
}
