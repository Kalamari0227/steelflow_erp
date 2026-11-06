import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { WorldSchema } from '../contracts';
import { testWorld } from './testWorld';
import { RecoveryPanel } from './RecoveryPanel';

afterEach(cleanup);
const fixture = () => WorldSchema.parse({ ...testWorld(),
  forecast: [{ order_id: 'ORD-ga', status: 'LATE', eta_at: '2026-10-30T07:03:00Z', completion_ms: 423000, reason: null, plan_revision: 0 }],
  recovery: { basis: 'INITIAL_PLAN', horizon_ms: 3600000, baseline_hash: 'baseline', plan_revision: 0,
    orders: [{ order_id: 'ORD-ga', delay_eta_at: '2026-10-30T06:58:00Z', recovery_eta_at: '2026-10-30T07:03:00Z', delay_completion_ms: 418000, recovery_completion_ms: 423000, improvement_ms: -5000 }],
    routed_material_ids: ['MAT-ga'], outage_ms: 150000, roller_duration_ms: [5000], current_available: true,
    current_reason: 'compatible_capacity_and_reservation', recommendation: 'NO_BENEFIT' },
});

describe('actual scheduler recovery comparison', () => {
  it('shows later ETA as negative benefit with optional AI off', () => {
    const world = fixture();
    render(<RecoveryPanel world={world} orderId="ORD-ga" />);
    expect(screen.getByTestId('comparison-ORD-ga')).toHaveAttribute('data-improvement-ms', '-5000');
    expect(screen.getByTestId('comparison-ORD-ga')).toHaveTextContent('5분 더 늦음');
    expect(screen.getByTestId('comparison-ORD-ga')).toHaveTextContent('2026-10-30 07:03:00 UTC');
    expect(screen.getByTestId('recovery-recommendation')).toHaveAttribute('data-recommendation', 'NO_BENEFIT');
    expect(screen.getByTestId('forecast-ORD-ga')).toHaveAttribute('data-status', 'LATE');
    expect(world.ai.enabled).toBe(false);
  });
  it('shows resource rejection and blocked ETA without manufacturing improvement', () => {
    const base = fixture();
    const world = WorldSchema.parse({ ...base,
      forecast: [{ ...base.forecast[0], status: 'BLOCKED', eta_at: null, completion_ms: null, reason: 'horizon_3600000: resource_unavailable' }],
      recovery: { ...base.recovery, current_available: false, current_reason: 'resource_reserved', recommendation: 'UNAVAILABLE',
        orders: base.recovery?.orders.map(row => ({ ...row, delay_eta_at: null, recovery_eta_at: null, delay_completion_ms: null, recovery_completion_ms: null, improvement_ms: 0 })) },
    });
    render(<RecoveryPanel world={world} orderId="ORD-ga" />);
    expect(screen.getByTestId('forecast-ORD-ga')).toHaveAttribute('data-status', 'BLOCKED');
    expect(screen.getByTestId('forecast-ORD-ga')).toHaveTextContent('예측 불가');
    expect(screen.getByTestId('recovery-recommendation')).toHaveAttribute('data-recommendation', 'UNAVAILABLE');
    expect(screen.getByTestId('recovery-availability')).toHaveTextContent('다른 작업이 예약 중');
    expect(screen.getByTestId('comparison-ORD-ga')).toHaveAttribute('data-improvement-ms', '0');
  });
  it('rejects malformed comparison fields at the World boundary', () => {
    const world = fixture();
    expect(WorldSchema.safeParse({ ...world, recovery: { ...world.recovery, horizon_ms: 1 } }).success).toBe(false);
    expect(WorldSchema.safeParse({ ...world, recovery: { ...world.recovery, recommendation: 'ALWAYS_RECOVER' } }).success).toBe(false);
    expect(WorldSchema.safeParse({ ...world, recovery: { ...world.recovery, orders: world.recovery?.orders.map(row => ({ ...row, improvement_ms: 5000 })) } }).success).toBe(false);
  });
});
