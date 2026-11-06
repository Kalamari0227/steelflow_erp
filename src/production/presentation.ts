import type { Product, ProductionBatch, ProductionStep, ProductionTransport, StageId } from './contracts';

export const productNames: Record<Product, string> = {
  SLAB: '슬래브', BLOOM: '블룸', BILLET: '빌렛', HR: '열연', CR: '냉연',
  GI: 'GI · 용융아연', GA: 'GA · 합금화아연', EG: 'EG · 전기아연', HGI: 'HGI · 열연도금',
};
export const formNames: Record<string, string> = { ORE: '철원료', HOT_METAL: '용선', LIQUID_STEEL: '용강', ...productNames };
export const statusNames = { queued: '대기', running: '작업 중', in_transit: '운송 중', completed: '완료' };
export const vehicleNames: Record<ProductionTransport['vehicle_kind'], string> = { flatbed_truck: '소재 운반 트럭', hot_metal_car: '용선 운반차', ladle_car: '용강 운반차' };
export const stageDescriptions: Record<StageId, string> = {
  ironmaking: '원료에서 용선으로. 출선 작업과 제강 인계를 확인합니다.',
  steelmaking: '용선에서 용강으로. 취련·출강·정련 작업을 따라갑니다.',
  casting: '용강에서 반제품으로. 슬래브·블룸·빌렛의 경로가 갈라집니다.',
  hot_rolling: '슬래브에서 열연 코일로. 판매하거나 다음 공정의 소재로 보냅니다.',
  cold_rolling: '열연 소재의 두께와 표면을 가공합니다. 냉연 제품과 도금 소재가 나뉩니다.',
  coating: 'GI·GA·EG·HGI. 소재와 도금 방식에 따라 서로 다른 작업을 거칩니다.',
  finishing: '품질을 확인하고 제품을 정정·포장합니다.',
  stock: '완성 제품의 형태와 출하 가능 상태를 확인합니다.',
};
export const stageShortNames: Record<StageId, string> = {
  ironmaking: '제선·출선', steelmaking: '제강·출강', casting: '연주', hot_rolling: '열연',
  cold_rolling: '냉연', coating: '도금', finishing: '정정·검사', stock: '제품 재고',
};
export function phaseFor(batch: ProductionBatch, stageId: StageId): ProductionStep['status'] {
  const steps = batch.steps.filter(step => step.stage_id === stageId);
  if (steps.some(step => step.status === 'running')) return 'running';
  return steps.length > 0 && steps.every(step => step.status === 'completed') ? 'completed' : 'queued';
}
export function materialName(form: string): string { return formNames[form] ?? form; }
export function mass(kg: number): string { return new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 1 }).format(kg / 1000); }
