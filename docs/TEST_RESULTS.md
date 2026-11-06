# 통합 운영 검증 기록

## 2026-10-25 가상 제철소 배치 변경

격자 배치를 [가상 해안 제철소](FACTORY_CAMPUS.md)로 바꾸고 도로·철도·롤러 이동, 투명 이름 표시, 시점 이동 버튼을 추가했다. 아래의 기존 389/193/59/9 및 F1–F4 기록은 이전 배치의 결과이며 이번 변경의 통과 수에 합산하지 않는다.

- 프런트엔드 전체 **21파일 204개 통과**, 타입 검사 통과. 실제 서버의 공정 완료 전후 23쌍과 분할 2쌍을 다시 수집해 위치 연속성을 검사했다.
- 백엔드 관련 **9파일 단일 실행 179개 통과, 228.06초**. 공정 엔진·운송·출하·세 시나리오·계약·질량·배치·fixture를 검사했다. 중간 실행의 통과 수를 더하지 않았다.
- 최종 동결 빌드에서 브라우저 집중 검사 **8개 통과, 178.215초**, 실패·skip·flaky 0. 8개 오류 기록 모두 빈 배열이다. 주문·소재 선택, 2D 왕복, 공정 접촉 8종, 데스크톱·모바일 범위 맞춤, 운송 인계·정지·재개·초기화, 방향 버튼과 키보드를 실제 Chrome에서 확인했다.
- 도로 트럭·일반 롤러·용선차·용강차 각각 실제 재생 중 60–61개 프레임 위치를 수집했다. 각각 47–50개 서로 다른 위치가 관찰됐고 공유 경로와의 최대 오차는 `8.9e-16` 장면 단위였다. 롤러의 별도 `IN_TRANSIT` 상태도 확인했다.
- 1440×1000 Chrome에서 재생 10초 동안 1,151프레임, 프레임 간격 중앙값 8.3ms·p95 9.3ms였다. 정지 후 1.5초의 프레임 수는 1,282→1,282였다. 짧은 측정 범위의 결과이며 장시간·모든 기기 성능을 보장하지 않는다.
- 세 시나리오의 실제 전체 엔진 실행에서 각각 20주문·21출하가 완료되었다. 전체 완료 1,091,800ms, GA 완료 1,077,200ms. 질량은 `408,000 + 1,200 = 407,300 + 1,900kg`이며 읽기 전용 예측과 실제 완료 결과가 일치했다.
- 일반 롤러 이동은 NORMAL/DELAY 각각 290회, RECOVERY 291회이며 모두 출발보다 도착 시각이 뒤였다. RECOVERY의 예비 설비 우회는 5,000ms이다.
- 거리 기반 운송과 실제 자원 대기를 적용한 비교는 `REVIEW_BENEFIT`: STS 후판 14,800ms, Ti 후판 10,200ms 단축, 나머지 18주문 동일. GA 및 전체 완료 시각의 개선은 없다.
- 이송 구간 추가 후 초기화가 **109.359초로 기존 60초 검사에 실패**했다. 동일한 불변 행을 반복 비교하는 비용을 줄인 뒤 새 프로세스에서 **31.467초**, 첫 World 조회 0.055초, 시나리오 변경 0.872초로 통과했다. 계산 결과를 고정하거나 성능 기준을 완화하지 않았다.
- 최적화 전후 NORMAL 3,986개, DELAY 3,994개, RECOVERY 3,996개 이벤트를 포함한 전체 상태·변경 행·이벤트 순서의 해시가 정확히 같았다. 최적화 전 검사를 돌리는 동안 소스가 바뀌어 생긴 fingerprint 실패 1건은 중단 기록으로 보존하고, 소스를 동결한 후 위 179개를 다시 검사했다.

원본 로그·실제 실행 JSON은 `.omo/evidence/20261025-factory-usability/`에 보존한다. 프런트엔드 초기 실패는 새 롤러 계약에 맞지 않는 과거 경계 fixture와 크레인 위치 ID 불일치였다. 정확한 인계 ID를 수정하고 실제 엔진에서 fixture를 재생성한 뒤 동일한 연속성 검사를 통과했다. 실패를 skip하거나 검사 조건을 낮추지 않았다.

최종 빌드는 3.59초에 완료했다. Zod annotation과 큰 3D chunk 경고는 남는다. 검증 전후 소스 162파일·실행 복사본 43파일은 같았고 기존 기본 `dist` 및 원래 서버는 유지했다. 새 합성 DB 서버의 실제 health 준비 시간은 33.145초였다. 핵심 로그와 실행 영수증은 [현재 증거 폴더](evidence/campus/)에 복사하며 원본 경로·SHA256을 함께 기록한다.

[백엔드179](evidence/campus/backend-tests.log) · [프런트엔드204](evidence/campus/frontend-204.log) · [브라우저8](evidence/campus/browser-report.json) · [4종 실제 이동](evidence/campus/network-motion.json) · [성능](evidence/campus/performance.json) · [최적화 동등성](evidence/campus/optimization-equivalence.jsonl) · [복사 해시](evidence/campus/copy-receipt.json).

검증 복사본을 동일하게 옮겨 [127.0.0.1:4175](http://127.0.0.1:4175)에 기동했다. 실제 사용자 탭에서 전경·제선/제강 상세·맞춤·GA 주문/소재 선택을 확인했고 console warning/error 조회는 빈 배열이었다. [전경 화면](evidence/campus/retained-overview.png), [공정 상세](evidence/campus/retained-stage.png), [실행 영수증](evidence/campus/retained-demo.json). 초기 NORMAL·정지·1× 상태를 유지했다. QA8003/4176만 종료했으며 새 발표 서버와 원래8000/4173은 유지한다. [정리 영수증](evidence/campus/qa-cleanup.json).

## 이전 통합 버전 검증 기록

아래는 가상 제철소 재배치 **이전**의 자동 검증과 영상이다. 백엔드 389건, 단위 193건, 전체 preview 59건 및 도착 표시 수정 후 필수 preview 9건이 통과했다. 전체59와 수정 후9는 서로 다른 소스 범위이며 합쳐서 '최종 동일 소스 68건'이라고 계산하지 않는다. 수동 F3 PASS, F1·F2·F4 APPROVE도 해당 이전 버전에 한정한다.

## 실제 실행 결과와 범위

| 시나리오·실행 | 관찰한 결과 | 원본 근거 |
| --- | --- | --- |
| `cd backend && .venv/bin/python -m pytest -q` | 389 passed, 874.65초 | [백엔드 로그](evidence/operations/backend-389.log) |
| `npm test` — 도착 표시 수정/기대값 교정 후 | 19파일, 193 passed, 1.40초 | [단위 로그](evidence/operations/unit-193.log) |
| `npm run build -- --outDir <owned-final-dist-shipment-arrival>` | tsc와 Vite build 완료, Vite 3.05초 | [빌드 로그](evidence/operations/build-final.log) |
| `STEELFLOW_E2E_PREVIEW=1 npm run test:e2e -- --headed --workers=1 --retries=0` | 전체 59 passed, 실패/skip/flaky 0, exit0, 전체 1030.836초 | [report](evidence/operations/playwright-full59.json), [실행 설정](evidence/operations/full59-invocation.json), [exit](evidence/operations/full59-exit.json) |
| 도착 표시 수정 후 `STEELFLOW_E2E_PREVIEW=1 npm run test:e2e -- tests/operations-demo.spec.ts tests/operations-fulfillment.spec.ts tests/operations-resilience.spec.ts --headed --workers=1 --retries=0` | 9 passed, 실패/skip/flaky 0, exit0, 전체 280.836초 | [report](evidence/operations/playwright-preview9.json), [실행 설정](evidence/operations/invocation.json), [exit](evidence/operations/preview9-exit.json), [원시 로그](evidence/operations/T20-preview.log) |
| 별도 보존본 기동: 전용 backend/shared snapshot·새 DB·전용 build·8002/4175 | build exit0, 두 health HTTP200, 직접/프록시 World 동일, 초기 NORMAL 정지·20주문·22활성·GA60,300 kg·AI off | [기동 영수증](evidence/operations/retained-demo.json), [전용 build 영수증](evidence/operations/retained-build.json) |

전체59의 실행 전후 소스는 644개 모두 동일했습니다. 이후 변경은 `src/operations/WorkflowTimeline.tsx`, `src/operations/OperationsWorkspace.test.tsx`, `src/Inspector.test.tsx`의 정확히 3개 파일입니다. 배송 완료 시 ETA null을 '미확정'으로 표시하던 문제를 실제 `delivered_at`의 '도착 완료'와 미배송 ETA의 '도착 예정'으로 구분했습니다. 백엔드/렌더 엔진 변경은 없습니다. 이후 193단위·빌드·필수9를 다시 실행했고 해당9 실행 전후 644개 소스도 동일했습니다. [3파일 delta](evidence/operations/source-delta-from-full59.json), [전체59 source](evidence/operations/full59-source-integrity.json), [수정 후9 source](evidence/operations/source-integrity.json).

## 확인한 업무·화면 관찰

- GA 정상 실행은 같은 run에서 UI 4×로 **123.689초 연속** 재생해 0→491,000 시뮬레이션 ms까지 완료했습니다. 첫 배송 40,200 kg/잔량20,100 kg, 두 번째 배송 후60,300 kg/잔량0을 관찰했습니다. 정상 구간은 Step API로 건너뛰지 않았습니다. [JSON](evidence/operations/T20-continuous-normal.json), [148.36초 원본 영상](evidence/operations/T20-demo.webm).
- DELAY/RECOVERY 비교는 각각 새 실행이며, 후반 비교 장면은 명시된 서버 Step API 가속입니다. 실제 HSM-B 우회가 있으나 배송 단축 주문은0, 같은 주문9, 더 늦는 주문11이며 `NO_BENEFIT`입니다. [비교 JSON](evidence/operations/T20-comparison.json), [RECOVERY 화면](evidence/operations/T20-RECOVERY.png).
- GA 분할 배송·검사·적재 명세, PLATE의 소비 부모와 두 검사 자식, 키보드·390px·WebGL 상실/미지원·실제8초 timeout·재연결·오래된 응답 차단·reduced-motion을 필수9에서 확인했습니다. [첫 배송](evidence/operations/T18-GA-first-partial-delivery.png), [최종 배송](evidence/operations/T18-GA-final-delivery.png), [분할 계보](evidence/operations/T18-PLATE-child-lineage.png), [390px](evidence/operations/T17-mobile.png).
- 의도적 API 연결 차단에서 같은 run/order/material의 마지막 상태를2D로 유지하고 재연결했습니다. AI는 비활성이며 예상하지 않은 오류 배열은 비어 있습니다. [fallback JSON](evidence/operations/T20-fallback.json), [9.56초 원본 영상](evidence/operations/T20-fallback.webm).
- 전체59의 1440×1000/DPR1/활성24 측정은 재생560프레임 median9.10 ms, p95 19.80 ms입니다. 정지60초에 조회51회가 있었고 렌더 프레임은791→791입니다. [성능](evidence/operations/T19-performance.json), [idle](evidence/operations/T19-idle-60s.json), [실제 macOS ARM/M4 Max 환경](evidence/operations/runtime-hardware.json). 이는 기록한 환경의 결과이며 모든 기기의 성능 보장이 아닙니다.

## 실패·오류·경고 기록

이전 전체 preview1은58통과1실패였습니다. 최초 reduced-motion 구독 변화가 누락되는 문제를 수정하고 회귀2건을 추가한 뒤 전체59를 다시 실행했습니다. 수정된 도착 라벨의 첫 단위 실행은192통과1실패였으며, 옛 문자열을 기대하던 Inspector 테스트를 교정한 뒤193통과를 확인했습니다. [실패 원본](evidence/operations/unit-arrival-before-expectation-fix.log). 실패를 건너뛰거나 통과 합계에 포함하지 않았습니다. 더 이전 버전의6주문/별도 생산/독립 journey 결과도 현재 통합 버전 통과로 사용하지 않습니다.

브라우저 장애 시나리오의 HTTP500, timeout 취소, `net::ERR_FAILED`와 해당 console 오류는 테스트가 의도적으로 만든 요청에 정확히 연결되어 있습니다. 일반7개 시나리오의 예상하지 않은 오류 배열은0이며, 의도적2개 시나리오도 `unexpected`가 비어 있습니다. [오류 분류 원본](evidence/operations/intentional-error-audit.json). '어떤 오류 로그도 없었다'고 표현하지 않습니다.

최신9 종료 중 SQLAlchemy `Exception terminating connection`/`asyncio.CancelledError` 로그가 남았습니다. 실제 원시 로그에서9개 테스트가 먼저 완료되고, 뒤이어 `Application shutdown complete`와 프로세스 종료가 기록됨을 확인했습니다. 종료 취소로 분류했으며 런타임 브라우저 실패로 집계하지 않았습니다. 로그는 삭제/억제하지 않았고 소유 QA 프로세스0/포트 정리를 확인했습니다. [원시 로그](evidence/operations/T20-preview.log), [종료 분류](evidence/operations/teardown-observation.json), [cleanup](evidence/operations/cleanup.json).

빌드에는 Zod 주석 annotation과500kB 초과 chunk 경고가 남습니다. 빌드 실패는 아니며 현재 국소 데모 범위에서 별도 번들 최적화는 수행하지 않았습니다.

## 보존·수동 승인

실제 최신 영상/trace/캡처/JSON은 `docs/evidence/operations/`에 고정 이름으로 복사했고 원본과 SHA256/크기를 대조했습니다. [복사 영수증](evidence/operations/artifact-copy-receipt.json), [영상 형식/길이 검사](evidence/operations/media-probe.json). 최종9 원본 OS 임시 폴더는 영구 증거 폴더로 복사 검증 후 정리되었으므로 report 안의 옛 임시 절대 경로 대신 이 색인과 복사 영수증을 사용합니다.

유지 데모는 [http://127.0.0.1:4175](http://127.0.0.1:4175)이며 기존8000/4173과 기본dist를 보존했습니다. Root가 독립적으로 IAB를 조작한 [F3 수동 검증](evidence/operations/F3-manual.md)은 PASS입니다. GA 소재 형태 변화, 운송 인계, 일시정지/재개, 부분/최종 배송, 실제 도착시각, 2D 왕복을 확인했습니다. 수동 실행에는 일시정지가 있으므로 위의 자동 연속4× 영상과 구분합니다. 수동 console error/warn 조회는 비어 있었으나 CUA가 raw pageerror/network stream을 제공하지 않아 그 항목의 자동 검증 결과를 수동 결과로 옮기지 않았습니다. 이름이 잘못 붙은 `13-partial-ax`는 실제 완료 상태여서 부분 배송 증거에서 제외했습니다.

[F1 계획 준수](evidence/operations/F1-compliance.md), [F2 코드 검토](evidence/operations/F2-code-review.md), [F4 시각 품질 IS1–10](evidence/operations/F4-fidelity.md)는 모두 APPROVE입니다. 최초 기동 상태는 [초기 영수증](evidence/operations/retained-demo-initial.json)에 보존했고, [최종 영수증](evidence/operations/retained-demo.json)에 수동 검증 후 새 run `OPS-RUN-41b0c1168629413396717ff2f58c5f69`의 NORMAL·elapsed0·revision0·정지·1×·20주문·22소재·AI off를 별도로 기록했습니다. [최종 World 원본](evidence/operations/F3-manual/22-final-reset-world.json). Root의 임시 캐시 정리와 영구 증거 보존은 [정리 영수증](evidence/operations/root-resource-cleanup.json)에 있습니다. 유지 데모와 사용자 탭은 의도적으로 남겼습니다.

[시연 대본](DEMO_2026_10_30.md) · [증거 색인](evidence/operations/README.md) · [운영/재시작](OPERATIONS.md).
