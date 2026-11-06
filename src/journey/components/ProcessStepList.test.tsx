import { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { JourneySnapshot, ProductDefinition } from '../contracts';
import { JourneyTable, ProcessStepList } from './ProcessStepList';

const product: ProductDefinition = {
  id: 'HR', family: '열연', name: '열연', description: '열연 시연', source_url: 'https://my.posco.com', source_title: '공정 참고', input_form: '슬래브', output_form: '열연코일', mass_kg: 22000,
  steps: [
    { id: 'furnace', name: '가열', equipment_kind: 'furnace', duration_ms: 10000, input_form: '슬래브', output_form: '가열 슬래브', description: '가열' },
    { id: 'rolling', name: '압연', equipment_kind: 'mill', duration_ms: 10000, input_form: '가열 슬래브', output_form: '열연코일', description: '압연' },
  ],
};
const snapshot: JourneySnapshot = {
  data_scope: 'synthetic_product_journey', run_id: 'run', revision: 1, product_id: 'HR', playing: true, speed: 1, elapsed_ms: 3000, duration_ms: 20000,
  active_step_id: 'furnace', step_elapsed_ms: 3000, step_duration_ms: 10000, completed: false,
  material: { lineage_id: 'material-1', version_id: 'material-v0', parent_version_id: null, form: '슬래브', role: 'feedstock', location_id: 'furnace', mass_kg: 22000 }, history: [],
};

function Navigator() {
  const [focused, setFocused] = useState<string | null>(null);
  return <ProcessStepList product={product} snapshot={snapshot} focusedStepId={focused} onSelect={setFocused} />;
}

describe('manufacturing navigation', () => {
  it('focuses downstream equipment without advancing the active material step', async () => {
    // Given the material is still in its furnace.
    render(<Navigator />);
    // When the user selects the rolling equipment.
    await userEvent.click(screen.getByRole('button', { name: /압연/ }));
    // Then focus changes while server-reported processing remains in the furnace.
    expect(screen.getByRole('button', { name: /압연/ })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: /가열/ })).toHaveAttribute('aria-current', 'step');
    expect(screen.getByRole('button', { name: /압연/ })).not.toHaveAttribute('aria-current');
  });

  it('exposes both the route and current material without WebGL', () => {
    // Given a running route.
    // When the accessible table is rendered.
    render(<JourneyTable product={product} snapshot={snapshot} focusedStepId={null} onSelect={() => undefined} />);
    // Then all stages and the single material location are available as text.
    expect(screen.getAllByRole('row')).toHaveLength(3);
    expect(screen.getByText('material-1 · 22,000 kg')).toBeVisible();
    expect(screen.getByText('현재 위치: 가열')).toBeVisible();
  });
});
