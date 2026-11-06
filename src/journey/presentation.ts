import type { JourneySnapshot, ProductDefinition } from './contracts';

export function stepStatus(product: ProductDefinition, snapshot: JourneySnapshot, index: number): string {
  const active = product.steps.findIndex(step => step.id === snapshot.active_step_id);
  if (snapshot.completed || index < active) return '완료';
  if (index === active) return snapshot.playing ? '가공 중' : '현재 단계';
  return '대기';
}

export function playbackTime(milliseconds: number): string {
  const seconds = Math.floor(milliseconds / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
}
