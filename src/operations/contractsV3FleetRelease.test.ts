// @vitest-environment node
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { factorySnapshotSchema } from './contractsV3';
import { EventContextSchema } from './contractsV3Rows';
import { ResourceReservationSchema } from './contractsV3Transport';

const raw: unknown = JSON.parse(readFileSync('shared/fixtures/factory-contract-test-v3/domain.json','utf8'));
const base = () => factorySnapshotSchema.parse(raw);
const reservation = { run_id:'r',id:'reservation',resource_id:'lane',job_id:'job',start_ms:2000,end_ms:3000 };
function state() {
  const initial = base();
  const job = { run_id:initial.run.id,id:'job',fleet_id:null,equipment_id:'BF-A',material_id:null,shipment_leg_id:null,from_node_id:'from',to_node_id:'to',status:'ASSIGNED' as const,ready_at_ms:0,start_ms:2000,end_ms:3000,blocked_resource_id:null };
  return { ...initial,transport_jobs:[job],reservations:[{ ...reservation,run_id:initial.run.id }] };
}

describe('retained reservation release',() => {
  it('normalizes omitted historical fields to null without loosening strict objects',() => {
    expect(ResourceReservationSchema.parse(reservation).released_at_ms).toBeNull();
    expect(EventContextSchema.parse({}).reservation_id).toBeNull();
    expect(ResourceReservationSchema.safeParse({ ...reservation,arbitrary:true }).success).toBe(false);
  });
  it.each([true,1.5,'1000',-1,4193483040000])('rejects malformed release %s',released_at_ms => {
    expect(ResourceReservationSchema.safeParse({ ...reservation,released_at_ms }).success).toBe(false);
  });
  it('retains future original window while cancelling occupancy before start',() => {
    const initial = state();
    const original = { ...initial.reservations[0],released_at_ms:1000 };
    const next = { ...initial.reservations[0],id:'new',end_ms:2500,released_at_ms:null };
    const parsed = factorySnapshotSchema.parse({ ...initial,reservations:[original,next] });
    expect(parsed.reservations.map(r => [r.start_ms,r.end_ms,r.released_at_ms])).toEqual([[2000,3000,1000],[2000,2500,null]]);
    expect(factorySnapshotSchema.safeParse({ ...initial,reservations:[{ ...original,released_at_ms:1001 },next] }).success).toBe(false);
  });
  it('uses effective nonempty intervals including same-job conflicts and adjacency',() => {
    const initial = state();
    const first = { ...initial.reservations[0],start_ms:0,released_at_ms:1000 };
    const adjacent = { ...initial.reservations[0],id:'next',start_ms:1000,released_at_ms:null };
    expect(factorySnapshotSchema.safeParse({ ...initial,reservations:[first,adjacent] }).success).toBe(true);
    expect(factorySnapshotSchema.safeParse({ ...initial,reservations:[first,{ ...adjacent,start_ms:999 }] }).success).toBe(false);
  });
  it('binds non-null event reservation to its exact owner and release timestamp',() => {
    const initial = state();
    const row = { ...initial.reservations[0],released_at_ms:1000 };
    const event = { run_id:initial.run.id,id:'release',sequence:initial.run.event_sequence+1,source_id:'release',event_type:'RESERVATION_RELEASED' as const,entity_type:'job' as const,entity_id:'job',at_ms:1000,occurred_at:new Date(Date.parse(initial.run.epoch_at)+1000*60).toISOString(),payload:{ job_id:'job',resource_id:'lane',reservation_id:'reservation' } };
    const candidate = { ...initial,run:{ ...initial.run,event_sequence:initial.run.event_sequence+1 },reservations:[row],events:[...initial.events,event] };
    expect(factorySnapshotSchema.safeParse(candidate).success).toBe(true);
    expect(factorySnapshotSchema.safeParse({ ...candidate,events:[...initial.events,{ ...event,payload:{ ...event.payload,resource_id:'other' } }] }).success).toBe(false);
    expect(factorySnapshotSchema.safeParse({ ...candidate,reservations:[{ ...row,released_at_ms:999 }] }).success).toBe(false);
  });
});
