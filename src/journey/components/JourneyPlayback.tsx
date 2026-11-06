import { Pause, Play, RotateCcw, SkipForward } from 'lucide-react';
import type { JourneyCommand, JourneySnapshot } from '../contracts';
import { playbackTime } from '../presentation';

type Props = {
  readonly snapshot: JourneySnapshot;
  readonly disabled: boolean;
  readonly onCommand: (command: JourneyCommand) => void;
};

export function JourneyPlayback({ snapshot, disabled, onCommand }: Props) {
  return <div className="journey-playback" aria-label="제품 공정 재생">
    <div className="journey-playback-buttons">
      <button className="journey-play" disabled={disabled || snapshot.completed} onClick={() => onCommand({ action: snapshot.playing ? 'pause' : 'play' })}>
        {snapshot.playing ? <Pause size={16} /> : <Play size={16} />}{snapshot.playing ? '일시정지' : '재생'}
      </button>
      <button disabled={disabled} onClick={() => onCommand({ action: 'reset' })}><RotateCcw size={15} />처음부터</button>
      <button disabled={disabled || snapshot.completed} onClick={() => onCommand({ action: 'step' })}><SkipForward size={15} />다음 단계</button>
    </div>
    <div className="journey-clock"><span>시연 시간</span><strong>{playbackTime(snapshot.elapsed_ms)} / {playbackTime(snapshot.duration_ms)}</strong>
      <progress aria-label="전체 공정 진행률" max={snapshot.duration_ms} value={snapshot.elapsed_ms} />
    </div>
    <div className="journey-speeds" role="group" aria-label="재생 속도">{([1, 2, 4] as const).map(speed => <button key={speed} disabled={disabled} aria-pressed={speed === snapshot.speed} onClick={() => onCommand({ action: 'speed', speed })}>{speed}×</button>)}</div>
  </div>;
}
