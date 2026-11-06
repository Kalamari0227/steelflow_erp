# 2026-10-30 통합 운영 시연

**상태: 최신 필수9 preview 통과·원본 녹화 보존·전용 데모 기동 확인.** [데모 열기](http://127.0.0.1:4175) · [정상/비교 원본 영상](evidence/operations/T20-demo.webm) · [2D 장애 대체 영상](evidence/operations/T20-fallback.webm). [실제 수동 F3](evidence/operations/F3-manual.md)는 PASS, F1·F2·F4는 APPROVE입니다. 기존4173 데모와 기본dist는 변경하지 않았습니다.

## 준비

[README](../README.md)의 독립 DB·빌드·8002/4175 명령으로 실행합니다. 합성 데이터, AI 미사용, kg/UTC와 **가속 시뮬레이션**임을 먼저 알립니다. 초기 계산이 끝난 `/health`와 `/api/v1/world`를 확인한 뒤 Chrome에서 열고 1440×1000 크기로 녹화합니다.

NORMAL을 새 실행으로 초기화하고 GA 주문 `ORD-ga`, 소재 `MAT-ga-01`을 선택합니다. `제선·제강` 공정을 선택하고 `소재 따라가기`를 켭니다. 속도 4×를 선택한 뒤 `재생`을 누릅니다. 정상 실행은 처음부터 마지막 배송까지 중단 없이 원본 영상으로 남깁니다. 공정 완료·검사·포장·차량 적재·배송은 서버의 실제 전이입니다. 4×에서 약 2분 남짓이 예상되지만 실제 녹화 길이와 완료 시각을 기록합니다.

## 3분 설명 순서

| 발표 구간 | 화면과 말할 내용 |
| --- | --- |
| 0:00–0:20 | 초기 GA 주문 60,300 kg, 2로트·3소재. 같은 ID로 공장 전경과 소재 상세를 연결한다. 합성 데이터·4× 가속·AI 미사용을 밝힌다. |
| 0:20–2:10 | 정상 연속 녹화에서 가공 → 운송 → 최종검사 → 포장 → 출하를 따라간다. GA 첫 두 소재 40,200 kg 배송 후 잔량 20,100 kg, 세 번째 소재 배송 후 60,300 kg 완료를 보여 준다. 연속 원본은 별도 보존한다. |
| 2:10–2:40 | DELAY를 선택하면 새 실행임을 알리고 HSM-A 중단/대기를 보여 준다. RECOVERY는 또 다른 새 실행이다. HSM-B 실제 우회와 추가 이동을 확인하고 '배송 개선 이득 없음' 및 주문별 같음/더 늦음을 그대로 읽는다. |
| 2:40–3:00 | 소재 검사 대상 버전·출하 명세·계보와 2D 대체 화면을 보여 준다. 마지막으로 로컬 합성 모델의 경계를 설명한다. |

이 3분 대본은 녹화 구간을 선택해 설명하는 발표 구성입니다. 정상 전체 연속 실행과 지연/회복 비교를 모두 실시간으로 연달아 수행하면 3분을 넘을 수 있습니다. 편집 구간은 명시하고 정상 연속 원본을 함께 보존합니다. 제품 UI에는 임의 시간으로 이동하는 seek가 없습니다. 자동 시연의 비교/후판 장면은 공용 Step API의 최대 48단계 가속을 사용할 수 있으며 화면 녹화 주석과 실행 JSON에 API 가속 구간을 표시합니다. 정상 연속 장면은 API step으로 건너뛰지 않습니다.

## 2D·연결 장애 대체 대본

같은 GA 소재를 선택한 상태에서 API 조회 연결을 차단하는 테스트를 수행합니다. '마지막 확인 상태', 마지막 수신 시각과 선택 ID를 보여 주고 실행 명령 비활성을 확인합니다. 2D를 선택해 마지막 확인된 공정·소재·검사/출하 연결을 읽습니다. 연결을 복구하고 `다시 연결`을 누른 뒤 같은 run/order/material과 정상 명령 상태를 확인합니다. AI는 이 과정에서도 꺼져 있습니다. 이는 테스트가 의도적으로 만든 브라우저 요청 장애이며 실제 기존 서버를 종료하는 시연이 아닙니다.

## 자동 검증·녹화 명령

```sh
# 저장소 루트, 8002/4175가 이번 작업에 비어 있을 때만 실행
STEELFLOW_E2E_PREVIEW=1 \
  STEELFLOW_EVIDENCE_DIR=/absolute/path/to/owned/evidence \
  npm run test:e2e -- tests/operations-demo.spec.ts
```

Playwright는 독립 DB와 빌드를 만들고 실제 Chrome/Chromium을 사용합니다. 정상 연속 실행, 지연/회복 및 2D 장애 시나리오가 각 영상/trace/JSON을 남깁니다. 녹화는 테스트 성공뿐 아니라 실제 사람이 화면·움직임·가림·선택 연속성을 검토한 후 승인합니다. 최종 retained preview는 테스트가 끝난 다음 별도 DB/빌드로 기동하고 PID·주소·로그를 기록합니다.

| 산출물 | 실제 기록 |
| --- | --- |
| 유지 데모 | [http://127.0.0.1:4175](http://127.0.0.1:4175), backend PID78616 / preview PID78711, 2026-10-25 기동 확인 |
| 소스/DB/build | `/Users/ethanlee/.local/share/steelflow/demos/2026-10-30-unified` 하위 `backend`, `shared`, `state/steelflow.sqlite`, `dist` |
| 정상 연속 영상 | [T20-demo.webm](evidence/operations/T20-demo.webm), VP9 1440×1000/25fps, 전체148.36초. 정상4× 연속 구간123.689초, 이후 새run 비교/계보 장면 포함 |
| 정상 이행 | [실제 JSON](evidence/operations/T20-continuous-normal.json): 첫 배송40,200kg / 잔량20,100kg → 마지막60,300kg / 잔량0 |
| 비교 | [실제 JSON](evidence/operations/T20-comparison.json): NO_BENEFIT, 단축0/동일9/더늦음11 |
| 2D 장애/재연결 | [T20-fallback.webm](evidence/operations/T20-fallback.webm), 9.56초. 같은run/소재 유지, AIoff, 예상 밖 오류0 |
| preview 검증 | [최신9 report](evidence/operations/playwright-preview9.json), [원시 로그](evidence/operations/T20-preview.log), [기동 영수증](evidence/operations/retained-demo.json) |
| 수동 화면/가공 가시성 최종 검토 | [F3 PASS](evidence/operations/F3-manual.md), [F4 IS1–10 APPROVE](evidence/operations/F4-fidelity.md) |

두 영상은 재생 속도를 후처리하지 않은 실제 브라우저 녹화 원본입니다. [영상 검사](evidence/operations/media-probe.json)와 [원본 복사 SHA256](evidence/operations/artifact-copy-receipt.json)을 보존했습니다. 3분 발표는 위 원본을 사용한 설명 구성이고 정확히180초로 편집된 파일이 따로 생성되었다는 뜻은 아닙니다. 정상4×의 시뮬레이션 가속과 후반 Step API 가속을 각각 표시합니다.

첫 GA 출하는 실제 UTC07:26, 두 번째는07:53에 배송되었습니다. [완료 화면](evidence/operations/T20-GA-complete.png)은 예정 ETA 대신 실제 배송시각을 표시하는 최종 수정본입니다. [첫 부분 배송](evidence/operations/T18-GA-first-partial-delivery.png), [최종 배송](evidence/operations/T18-GA-final-delivery.png), [분할 부모/자식](evidence/operations/T18-PLATE-child-lineage.png), [장애 상태](evidence/operations/T20-fallback-last-state.png), [재연결](evidence/operations/T20-fallback-restored.png)도 보존했습니다.

[최초 기동 영수증](evidence/operations/retained-demo-initial.json)과 [최종 영수증](evidence/operations/retained-demo.json)을 구분했습니다. 수동 검증 후 run `OPS-RUN-41b0c1168629413396717ff2f58c5f69`를 NORMAL·elapsed0·revision0·정지·1×·20주문·22소재·AI off로 초기화하고 GA 선택/3D 전경/따라가기 해제 상태로 남겼습니다. [최종 World](evidence/operations/F3-manual/22-final-reset-world.json). 이후 사용자의 재생/초기화로 현재 run은 달라질 수 있습니다. 종료·재시작은 [운영 안내](OPERATIONS.md)를 따르며, 기존8000/4173은 그대로 유지합니다. 전체59 통과와 마지막 도착 표시3파일 수정 뒤 필수9 통과의 범위는 [검증 기록](TEST_RESULTS.md)에 구분했습니다.
