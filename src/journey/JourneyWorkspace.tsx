import { lazy, Suspense, useEffect, useState } from 'react';
import { ArrowRight, Box, ExternalLink, Focus, List, LoaderCircle } from 'lucide-react';
import { useJourneyStore } from './store';
import { JourneyPlayback } from './components/JourneyPlayback';
import { MaterialPassport } from './components/MaterialPassport';
import { JourneyTable, ProcessStepList } from './components/ProcessStepList';
import './journey.css';

const JourneyScene = lazy(async () => ({ default: (await import('./scene/JourneyScene')).JourneyScene }));

export function JourneyWorkspace() {
  const { products, snapshot, busy, fetching, error, refresh, command } = useJourneyStore();
  const [focusedStepId, setFocusedStepId] = useState<string | null>(null);
  const [followMaterial, setFollowMaterial] = useState(false);
  const [view, setView] = useState<'3d' | '2d'>('3d');
  const [resetKey, setResetKey] = useState(0);
  const [fallback, setFallback] = useState(false);
  const playing = snapshot?.playing ?? false;
  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), playing ? 250 : 1000);
    return () => window.clearInterval(timer);
  }, [refresh, playing]);

  const product = products.find(item => item.id === snapshot?.product_id);
  const families = [...new Set(products.map(item => item.family))];
  const focused = product?.steps.find(step => step.id === focusedStepId);
  const displayedStep = focused ?? product?.steps.find(step => step.id === snapshot?.active_step_id);
  const selectProduct = (id: string) => {
    setFocusedStepId(null);
    setResetKey(value => value + 1);
    void command({ action: 'select', product_id: id });
  };
  const selectMaterial = () => {
    setFocusedStepId(null);
    setFollowMaterial(true);
    document.getElementById('journey-material-passport')?.focus({ preventScroll: true });
  };

  return <div className="journey-workspace">
    <header className="journey-heading"><h1>소재에서 제품까지</h1><span className="journey-synthetic">합성 데이터 · 공정 시연</span></header>
    {error && <div className="journey-error" role="alert"><span>{error} 재생 화면은 멈춰 있습니다.</span><button disabled={fetching || busy} onClick={() => void refresh()}>다시 연결</button></div>}
    {!snapshot || !product ? <div className="journey-loading" role="status">{error ? '공정 서버 연결을 기다리고 있습니다.' : <><LoaderCircle size={22} />제품 공정을 불러오고 있습니다…</>}</div> : <>
      <nav className="journey-family-tabs" aria-label="제품군 선택">{families.map(family => <button key={family} disabled={busy || Boolean(error)} aria-pressed={family === product.family} onClick={() => {
        const first = products.find(item => item.family === family);
        if (first && family !== product.family) selectProduct(first.id);
      }}>{family}</button>)}</nav>
      <div className="journey-product-heading"><div><h2>{product.name}</h2><p>{product.description}</p></div>
        <label>제조 경로<select aria-label="제조 경로" value={product.id} disabled={busy || Boolean(error)} onChange={event => selectProduct(event.target.value)}>{products.filter(item => item.family === product.family).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      </div>
      <section className="journey-scene-panel" aria-label="제품 제조 미니어처">
        <div className="journey-scene-toolbar"><span role="status">{error ? '연결 끊김 · 마지막 상태' : busy ? '공정 상태 변경 중…' : snapshot.completed ? '제품 완성' : snapshot.playing ? '공정 가동 중' : '공정 일시정지'}</span>
          <div className="journey-scene-tools"><label><input type="checkbox" checked={followMaterial} onChange={event => { setFollowMaterial(event.target.checked); if (event.target.checked) setFocusedStepId(null); }} />소재 따라가기</label><button disabled={view === '2d'} onClick={() => { setResetKey(value => value + 1); setFocusedStepId(null); setFollowMaterial(false); }}><Focus size={14} />전체 보기</button><button aria-pressed={view === '3d'} onClick={() => { setView('3d'); setFallback(false); }}><Box size={14} />3D</button><button aria-pressed={view === '2d'} onClick={() => setView('2d')}><List size={14} />2D</button></div>
        </div>
        <div className="journey-stage-layout">
          <div className="journey-primary-surface">{view === '3d' ? <div className="journey-canvas">
            <Suspense fallback={<div className="journey-loading" role="status">제조 설비를 준비하고 있습니다…</div>}><JourneyScene product={product} snapshot={snapshot} focusedStepId={focused?.id ?? null} followMaterial={followMaterial} resetKey={resetKey} onSelectStep={id => { setFocusedStepId(id); setFollowMaterial(false); }} onSelectMaterial={selectMaterial} onFallback={() => { setView('2d'); setFallback(true); }} stale={Boolean(error) || busy} /></Suspense>
            <div className="journey-canvas-hint">드래그 회전 · 휠 확대 · 설비와 소재 선택</div>
          </div> : <>{fallback && <p className="journey-fallback-note" role="status">3D를 사용할 수 없어 동일한 공정과 소재를 2D로 표시합니다.</p>}<JourneyTable product={product} snapshot={snapshot} focusedStepId={focused?.id ?? null} onSelect={setFocusedStepId} /></>}</div>
          <ProcessStepList product={product} snapshot={snapshot} focusedStepId={focused?.id ?? null} onSelect={id => { setFocusedStepId(id); setFollowMaterial(false); }} />
        </div>
        <JourneyPlayback snapshot={snapshot} disabled={busy || Boolean(error)} onCommand={value => { if (value.action === 'reset') { setFocusedStepId(null); setResetKey(key => key + 1); } void command(value); }} />
      </section>
      <div className="journey-detail-grid"><section className="journey-process-detail" aria-label="선택 공정 설명"><span className="journey-eyebrow">{focused ? '선택한 설비 · 공정 위치는 그대로 유지됩니다' : '현재 소재가 거치는 공정'}</span><h2>{displayedStep?.name}</h2><p>{displayedStep?.description}</p><div className="journey-transformation"><span>{displayedStep?.input_form}</span><ArrowRight size={18} /><strong>{displayedStep?.output_form}</strong></div><a href={product.source_url} target="_blank" rel="noreferrer">{product.source_title}<ExternalLink size={13} /></a></section><MaterialPassport product={product} snapshot={snapshot} /></div>
      <p className="journey-footnote">공개된 제품 제조 흐름을 바탕으로 재구성한 미니어처입니다. 시간과 질량은 설명용 합성 데이터이며, 실제 생산 속도·설비 제어와 연결되지 않습니다. 소재의 이동과 변환은 로컬 서버가 결정합니다.</p>
    </>}
  </div>;
}
