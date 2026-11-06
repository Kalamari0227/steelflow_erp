import { Pause, Play, RotateCcw, SkipForward } from 'lucide-react';
import { ScenarioIdSchema } from '../contracts';
import { useWorldStore } from '../store';

export function SimulationControls() {
  const { world, busy, stale, command } = useWorldStore();
  if (!world || world.schema_version !== 2) return null;
  const run = world.run;
  const disabled = busy || stale;
  const complete = run.elapsed_ms >= run.duration_ms;
  return <div className="ops-controls" aria-label="공통 실행 제어">
    <button data-testid="simulation-play-pause" disabled={disabled || (!run.playing && complete)} onClick={() => void command({ action: run.playing ? 'pause' : 'play' })}>{run.playing ? <Pause size={16} /> : <Play size={16} />}{run.playing ? '일시 정지' : complete ? '실행 완료' : '재생'}</button>
    <button data-testid="simulation-step" disabled={disabled || run.playing || complete} onClick={() => void command({ action: 'step' })}><SkipForward size={16} />한 단계</button>
    <button data-testid="simulation-reset" disabled={disabled} onClick={() => void command({ action: 'reset' })} title="새 실행으로 초기화"><RotateCcw size={16} />초기화</button>
    <label>속도 <select aria-label="실행 속도" disabled={disabled} value={run.speed} onChange={event => { const speed = Number(event.target.value); if (speed === 1 || speed === 2 || speed === 4) void command({ action: 'speed', speed }); }}><option value={1}>1×</option><option value={2}>2×</option><option value={4}>4×</option></select></label>
    <label>시나리오 <select data-testid="simulation-scenario" aria-label="시나리오" disabled={disabled} value={run.scenario_id} onChange={event => void command({ action: 'scenario', scenario: ScenarioIdSchema.parse(event.target.value) })}><option value="NORMAL">정상 운영</option><option value="DELAY">설비 지연</option><option value="RECOVERY">회복 운영</option></select></label>
    <span className="ops-control-note">시나리오 변경·초기화는 새 실행을 시작합니다.</span><progress aria-label="전체 실행 진행률" value={run.elapsed_ms} max={run.duration_ms} />
  </div>;
}
