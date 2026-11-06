# SteelFlow Visual Operations ERP

> 저장소 복제 시 Git LFS를 설치하고 `git lfs pull`로 대형 테스트 입력을 받으십시오. 이 저장소는 개발 중인 스냅샷이며, 정리 시점의 검증 결과와 알려진 실패는 [2026-11-06 기록](docs/maintenance/cleanup-2026-11-06.md)에 있습니다. 디스크 정리와 Git 보관 범위는 [저장소 관리 원칙](docs/REPOSITORY_HYGIENE.md)을 따릅니다. 아래 데모 설명과 과거 검증 기록을 현재 전체 기능의 완료 판정으로 사용하지 않습니다.

합성 주문부터 생산·검사·재고·출하·배송까지 **같은 실행과 소재 ID**로 추적하는 로컬 데모입니다. 공장 전경 → 공정 → 설비 → 소재 상세는 하나의 백엔드 World를 다른 깊이로 보여 줍니다. 실제 ERP·설비·회사 데이터에 연결하지 않습니다.

**로컬 데모: [http://127.0.0.1:4175](http://127.0.0.1:4175)** · [가상 제철소 배치와 조작](docs/FACTORY_CAMPUS.md) · [실제 검증 범위](docs/TEST_RESULTS.md) · [시연 안내](docs/DEMO_2026_10_30.md). 원료장부터 압연·도금 공장, 창고·해안 부두까지 도로·철도·롤러로 연결합니다. 이전 배치의 [정상 영상](docs/evidence/operations/T20-demo.webm)과 [2D 장애 영상](docs/evidence/operations/T20-fallback.webm)은 과거 기록이며 새 배치의 시연 증거로 사용하지 않습니다.

20개 제품 주문, 최초 소재 22개와 분할 후 활성 소재 24개를 다룹니다. GA는 2개 로트·3개 소재·2회 출하이며, 후판과 티타늄 박판은 부모를 소비하고 자식 소재 둘로 분할합니다. 질량은 kg, 업무 시각은 UTC입니다. 소재의 과거 버전과 소비된 부모를 현재 재고에 다시 합산하지 않습니다.

## 로컬 실행

macOS ARM64에서 Docker 없이 Node.js 22.12 이상(또는 24), Python 3.13과 uv를 사용합니다. 설치에는 인터넷이 필요하며 앱의 핵심 운영에는 API 키·외부 AI·외부 자산이 필요하지 않습니다. 다음 명령은 저장소 루트에서 실행합니다.

```sh
npm ci
cd backend
uv sync --frozen --python 3.13
cd ..
```

기존 8000/4173 데모를 유지하기 위해 아래 독립 DB·8002/4175 예시를 사용합니다. 다른 터미널 두 개에서 실행하고, 생성된 절대 경로를 두 번째 터미널에도 그대로 사용합니다. 동일 포트의 E2E와 동시 실행하지 않습니다. 위 유지 데모가 8002/4175를 사용 중이므로 아래 새 실행 명령은 해당 유지 서버를 소유 정보로 확인해 종료한 뒤 사용하거나, 다른 비점유 포트로 조정해야 합니다.

```sh
# 터미널 1, 저장소 루트
export STEELFLOW_DEMO_DIR="$(mktemp -d "${TMPDIR:-/tmp}/steelflow-demo.XXXXXX")"
printf '%s\n' "$STEELFLOW_DEMO_DIR"
cd backend
STEELFLOW_DATABASE_URL="sqlite+aiosqlite:///$STEELFLOW_DEMO_DIR/steelflow.sqlite" \
  STEELFLOW_AI_ENABLED=false .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8002
```

```sh
# 터미널 2, 저장소 루트. 위에서 출력된 절대 경로를 지정합니다.
export STEELFLOW_DEMO_DIR=/absolute/path/from/terminal-1
VITE_API_TARGET=http://127.0.0.1:8002 npm run build -- --outDir "$STEELFLOW_DEMO_DIR/dist"
VITE_API_TARGET=http://127.0.0.1:8002 npm run preview -- --port 4175 --strictPort --outDir "$STEELFLOW_DEMO_DIR/dist"
```

[앱](http://127.0.0.1:4175) · [2D 화면](http://127.0.0.1:4175/?view=2d) · [API 문서](http://127.0.0.1:8002/docs) · [프록시 상태 확인](http://127.0.0.1:4175/health). 이 주소는 위 명령 실행 중에만 유효합니다. 최종 유지 데모의 실제 실행 영수증은 [시연 안내](docs/DEMO_2026_10_30.md)에 기록합니다.

최초 기동은 실제 전체 공정 예측 계산 때문에 수십 초 걸릴 수 있습니다. `/health` 응답 후 앱을 엽니다. 브라우저 HTTP 제한은 8초이며 실패 시 마지막 스냅샷을 유지하고 `다시 연결`로 복구합니다. 각 터미널의 `Ctrl+C`로 자신이 시작한 서버만 종료합니다. 기본 `dist/`와 `backend/steelflow.db`는 위 명령에서 사용하지 않습니다.

개발 서버가 필요하면 별도 비점유 포트에서 `VITE_API_TARGET=http://127.0.0.1:8002 npm run dev -- --port 5174 --strictPort`를 실행합니다.

## 조작과 사실 경계

- 주문 검색 → GA 주문 → 소재 선택 → 공정·설비 확대 → 검사·출하·이벤트를 확인합니다. 탐색은 실행을 새로 만들거나 생산 상태를 변경하지 않습니다.
- 3D 아래 화살표로 시점을 이동하고 확대·축소·범위 맞춤을 사용합니다. 방향키, `+`·`-`, `Home`도 지원합니다. 직접 카메라를 움직이면 소재 따라가기를 해제합니다. 선택 공장은 벽을 낮추고 설비 이름은 불투명 배경 없이 표시합니다.
- `재생`, `일시 정지`, `한 단계`, 1×/2×/4×가 공통 시계를 제어합니다. 한 단계는 1000 시뮬레이션 ms이며 제조 업무 시간 1분에 해당합니다. 시나리오 변경과 초기화는 새 실행을 만들고 기존 이벤트를 보관합니다.
- NORMAL/DELAY/RECOVERY는 실제 자원 대기·운송·가공·배송 계산을 사용합니다. 현재 RECOVERY는 DELAY보다 후판 주문 2건이 빨라지고 18건은 동일합니다. GA와 전체 완료 시각의 개선은 없습니다. 화면의 주문별 실제 계산 결과를 확인합니다.
- WebGL을 사용할 수 없으면 같은 선택과 업무 데이터를 유지하는 2D 표로 전환합니다. AI는 기본 비활성이며 켜더라도 기본 공급자가 없어 핵심 운영은 로컬 계산으로 계속됩니다.

## 구조와 검증

React/Zustand와 React Three Fiber는 FastAPI의 원자적 World를 표시합니다. SQLAlchemy/SQLite에 실행과 명령 영수증, 소재 계보, 불변 이벤트를 저장하고 Alembic으로 추가 마이그레이션합니다. 단일 백엔드 프로세스만 지원합니다.

```sh
cd backend
.venv/bin/python -m pytest -q
cd ..
npm test
npm run typecheck
npm run test:e2e
# 독립 DB, 8002/4175, 독립 outDir를 자동 소유하는 preview 검증
STEELFLOW_E2E_PREVIEW=1 npm run test:e2e -- tests/operations-demo.spec.ts
```

E2E는 일반 모드 8001/5174, preview 모드 8002/4175를 사용합니다. `STEELFLOW_E2E_RUN_DIR`·`STEELFLOW_EVIDENCE_DIR`로 실행·증거 경로를 명시할 수 있습니다. Playwright가 시작한 서버는 테스트 종료 시 종료합니다. 실제 통과 여부는 [검증 기록](docs/TEST_RESULTS.md)을 확인하십시오. 과거 별도 물류/생산/제품 제조 화면의 결과를 현재 통합 버전 통과로 사용하지 않습니다.

[운영·API·백업](docs/OPERATIONS.md) · [백엔드](backend/README.md) · [생산 규칙](docs/PRODUCTION.md) · [20개 제품 경로](docs/PRODUCT_JOURNEY.md) · [화면 설계](DESIGN.md) · [3분 시연](docs/DEMO_2026_10_30.md).

공개 제조공정 참고 자료를 바탕으로 만든 절차적 3D 설명 모형입니다. 실제 공장 측량, POSCO CAD 복제, 공정 열역학·충돌 해석·실생산 수율·최적화·인증·다중 사용자 운영·외부 배포는 범위 밖입니다.
