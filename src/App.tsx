import { lazy, Suspense, useEffect } from 'react';
import { useWorldStore } from './store';
import { connectNavigationUrl } from './operations/navigation';
import { FactoryWorkspace } from './operations/FactoryWorkspace';
import { OperationsWorkspace } from './operations/OperationsWorkspace';

const OperationsScene = lazy(async () => ({ default: (await import('./operations/scene/OperationsScene')).OperationsScene }));

export function App() {
  const { world, error, unavailable, refresh, acquirePolling } = useWorldStore();
  useEffect(() => connectNavigationUrl(), []);
  useEffect(() => acquirePolling(), [acquirePolling]);
  return <div className="operations-app"><a className="skip-link" href="#main-content">운영 화면으로 건너뛰기</a><header className="ops-brand"><strong>SteelFlow <span>OPERATIONS</span></strong><span>합성 운영 데이터 · 로컬 시뮬레이션</span></header><main id="main-content">{world ? world.schema_version === 3 ? <FactoryWorkspace world={world} /> : <OperationsWorkspace world={world} renderScene={props => <Suspense fallback={<div className="ops-empty" role="status">공장 장면을 불러오는 중입니다.</div>}><OperationsScene {...props} /></Suspense>} /> : <section className={unavailable ? "initial-state factory-unavailable" : "initial-state"} aria-live="polite"><h1>{unavailable ? '공장 번들 준비가 필요합니다' : error ? '운영 서버에 연결할 수 없습니다' : '운영 상태를 불러오는 중입니다'}</h1><p>{error ?? '주문과 소재의 현재 실행을 확인합니다.'}</p>{unavailable && <div aria-label="실행 제어"><button disabled>재생</button><button disabled>한 단계</button><button disabled>초기화</button></div>}{error && <button className="secondary-button" onClick={() => void refresh()}>다시 연결</button>}</section>}</main></div>;
}
