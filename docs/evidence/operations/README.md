# 통합 운영 증거 색인

최신 도착 표시 수정 후 필수9 preview가 통과했고, 아래 파일은 실제 결과를 원본 SHA256/크기 그대로 복사한 것입니다. [복사 영수증](artifact-copy-receipt.json)의 source/destination으로 원래 실행 위치와 대조할 수 있습니다. 전체59와 수정 후9는 서로 다른 소스 범위입니다. [수동 F3](F3-manual.md)는 PASS이고 [F1](F1-compliance.md)·[F2](F2-code-review.md)·[F4](F4-fidelity.md)는 APPROVE입니다.

## 실행과 시연

| 관찰 | 근거 |
| --- | --- |
| 같은 GA 소재의 초기→제조→두 출하 완료, UI4× 정상 구간123.689초 | [원본148.36초 영상](T20-demo.webm), [실제 run/수량 JSON](T20-continuous-normal.json), [trace](T20-demo.trace.zip) |
| DELAY/RECOVERY 새run, 후반 API가속, 단축0·동일9·더늦음11 | [비교 JSON](T20-comparison.json), [DELAY](T20-DELAY.png), [RECOVERY](T20-RECOVERY.png) |
| API 조회 차단→2D 마지막 상태→같은run 재연결, AI off | [원본9.56초 영상](T20-fallback.webm), [JSON](T20-fallback.json), [trace](T20-fallback.trace.zip), [장애 화면](T20-fallback-last-state.png), [복구 화면](T20-fallback-restored.png) |
| GA40,200kg 부분 배송과60,300kg 완료, 실제 도착시각 | [부분 배송](T18-GA-first-partial-delivery.png), [최종 배송](T18-GA-final-delivery.png), [시연 완료](T20-GA-complete.png) |
| PLATE 소비 부모와 검사 자식 둘 | [계보 화면](T18-PLATE-child-lineage.png), [계보 JSON](T20-plate-lineage.json) |
| 390px/키보드/WebGL 대체 | [모바일](T17-mobile.png), [WebGL 상실](T17-webgl-loss.png), [필수9 report](playwright-preview9.json) |
| 실제8초 timeout/HTTP500/지연 응답 차단 | [오류 JSON](T17-failures.json), [의도적 오류 분류](intentional-error-audit.json) |
| 활성24·DPR1·1440×1000에서 median9.10ms/p95 19.80ms, 정지60초791→791프레임 | [프레임 원본](T19-performance.json), [idle 원본](T19-idle-60s.json), [실제 환경](runtime-hardware.json) |
| 파일 형식·길이·해시 | [ffprobe 결과](media-probe.json), [복사 SHA256](artifact-copy-receipt.json) |

정상/비교 영상은1440×1000 VP9/25fps이고, 정상 연속 구간 후 새run 비교/계보 구간이 이어집니다. 가속은 실제UI4× 및 명시한 Step API이며 영상 파일을 후처리로 가속하지 않았습니다. 3분 대본은 발표 구성이고 별도180초 편집 파일을 뜻하지 않습니다. 기존 `../steelflow-demo.*`는 이전 버전의 자료로 현재 증거가 아닙니다.

## 명령과 결과

| 실행 | 근거 |
| --- | --- |
| backend pytest389 | [로그](backend-389.log) |
| 최종 단위193/19파일, tsc+전용build | [단위](unit-193.log), [빌드](build-final.log) |
| 도착 표시 수정 전 전체preview59/59 | [report](playwright-full59.json), [실행](full59-invocation.json), [exit0](full59-exit.json), [644개 소스 보존](full59-source-integrity.json), [cleanup](full59-cleanup.json) |
| 정확한 도착 표시3파일 delta | [delta](source-delta-from-full59.json), [라벨 종료 기록](arrival-label-closure.json) |
| 수정 후 필수preview9/9 | [report](playwright-preview9.json), [실행](invocation.json), [exit0](preview9-exit.json), [소스 보존](source-integrity.json), [원시 로그](T20-preview.log) |
| 실패를 숨기지 않은 기록 | [옛 라벨 기대값 실패](unit-arrival-before-expectation-fix.log), [종료 cancellation 분류](teardown-observation.json), [소유 프로세스 정리](cleanup.json) |

Report의 attachment 경로에는 이미 정리한 OS 임시 디렉터리가 남아 있습니다. 현재 유효한 파일은 이 색인과 [복사 영수증](artifact-copy-receipt.json)의 destination입니다. 원래 영구 보관본은 `.omo/evidence/ulw/01a16c69-07a2-71a2-b3dd-d8cf9daa88cd/G003-wave-3-all-api-and-frontend-state-en/a1/final-browser-preview-2/` 및 `G004-wave-4-and-final-deterministic-norma/a1/final-browser-arrival-1/`입니다.

## 유지 데모

[http://127.0.0.1:4175](http://127.0.0.1:4175) · [2D](http://127.0.0.1:4175/?view=2d). 전용 루트 `/Users/ethanlee/.local/share/steelflow/demos/2026-10-30-unified`, backend PID78616 / preview PID78711로 기동했고, 원래8000/4173 및 기본dist를 보존했습니다. DB/동결backend/shared/정적dist/로그를 남겼으며 자동기동 서비스는 만들지 않았습니다.

[최초 기동 영수증](retained-demo-initial.json), [최종 영수증](retained-demo.json), [전용 build](retained-build.json), [backend/shared 복사 해시](retained-runtime-source-copy.json). 최초 기동과 수동 검증 후 최종 reset은 서로 다른 run입니다. [최종 World](F3-manual/22-final-reset-world.json)는 NORMAL·elapsed0·revision0·정지·1×·20주문·22소재·AI off입니다. 이후 재생·초기화·재시작으로 run/PID는 달라질 수 있습니다. [Root 임시 자원 정리](root-resource-cleanup.json) 후에도 유지 데모와 사용자 탭은 남겼습니다.

[검증 결과와 제한](../../TEST_RESULTS.md) · [시연 순서](../../DEMO_2026_10_30.md) · [운영·재시작](../../OPERATIONS.md).
