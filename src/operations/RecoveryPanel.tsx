import type { World } from '../contracts';

const availabilityLabels: Readonly<Record<string, string>> = {
  capacity_exceeded: '처리 용량 부족', resource_incompatible: '강종·폭·소재 형태 부적합', resource_reserved: '다른 작업이 예약 중',
  resource_busy: '가동·대기 시간 점유 중', resource_unavailable: '설비 사용 불가', already_routed_or_completed: '우회 또는 해당 가공 완료',
  compatible_capacity_and_reservation: '형태·강종·폭·용량·예약 조건 충족',
};
const time = (value: string | null): string => value ? `${value.replace('T', ' ').replace(/(?:Z|\+00:00)$/, '')} UTC` : '예측 불가';

export function RecoveryPanel({ world, orderId }: { readonly world: World; readonly orderId: string | null }) {
  const comparison = world.recovery;
  const rows = world.forecast.filter(row => orderId === null || row.order_id === orderId);
  return <section className="ops-workflow" aria-label="납기와 회복 비교" data-testid="recovery-panel">
    <div className="ops-panel-heading"><h2>납기와 회복 비교</h2><span>AI {world.ai.enabled && world.ai.available ? '선택 연결' : '미사용'} · 실제 공정·물류 계산</span></div>
    <div className="ops-workflow-grid"><div><h3>현재 실행 ETA · {world.run.scenario_id}</h3>
      {rows.length === 0 ? <p className="ops-empty">예측 자료를 기다리고 있습니다.</p> : <ul className="ops-events">{rows.map(row => <li key={row.order_id} data-testid={`forecast-${row.order_id}`} data-status={row.status}>
        <div><strong>{row.order_id} · {row.status === 'LATE' ? '납기 지연' : row.status === 'BLOCKED' ? '진행 불가' : '납기 내'}</strong>
          <small>ETA {time(row.eta_at)}</small><small>납기 {time(world.orders.find(order => order.id === row.order_id)?.due_at ?? null)}</small>
          {row.completion_ms === null && <small>현재 자원·검사 조건에서 완료 시점을 계산할 수 없습니다.</small>}</div>
      </li>)}</ul>}</div>
      <div><h3>동일 초기 계획의 새 실행 비교</h3><p className="ops-control-note">시나리오 전환은 새 실행을 만듭니다. 납기는 모든 비교에서 동일합니다.</p>
        {comparison ? <><p className="ops-record" data-testid="recovery-recommendation" data-recommendation={comparison.recommendation}>
          <strong>{comparison.recommendation === 'NO_BENEFIT' ? 'HSM-B 우회: 배송 개선 이득 없음' : comparison.recommendation === 'UNAVAILABLE' ? '현재 HSM-B 적용 불가' : '주문별 이득과 손실 검토 필요'}</strong>
          <span>HSM-A 12분 중단 · 장애 1분 후 우회 검토 · 롤러 이동 5분과 실제 대기 포함</span>
          <span>초기 계획 B 경유: {comparison.routed_material_ids.join(', ') || '없음'}</span>
          <span data-testid="recovery-availability">현재 조건: {availabilityLabels[comparison.current_reason] ?? comparison.current_reason}</span></p>
          <ul className="ops-events">{comparison.orders.filter(row => orderId === null || row.order_id === orderId).map(row => <li key={row.order_id} data-testid={`comparison-${row.order_id}`} data-improvement-ms={row.improvement_ms}>
            <div><strong>{row.order_id}</strong><small>DELAY {time(row.delay_eta_at)}</small><small>RECOVERY {time(row.recovery_eta_at)}</small>
              <small>{row.improvement_ms > 0 ? `${(row.improvement_ms / 1000).toLocaleString('ko-KR')}분 단축` : row.improvement_ms < 0 ? `${(-row.improvement_ms / 1000).toLocaleString('ko-KR')}분 더 늦음` : '배송 개선 없음'}</small></div></li>)}</ul>
        </> : <p className="ops-empty">초기 계획 비교 자료가 없습니다.</p>}</div></div>
  </section>;
}
