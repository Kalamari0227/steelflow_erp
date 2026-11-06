# 로컬 운영·API 계약

이 문서는 현재 통합 operations 서비스의 계약입니다. [루트 실행 안내](../README.md), [제품 경로](PRODUCT_JOURNEY.md), [현재 검증 상태](TEST_RESULTS.md)와 함께 사용합니다. 실제 회사 데이터, 외부 시스템 연결, 인증, 비용 발생 API, 다중 작업자 운영은 포함하지 않습니다.

## World와 시간

`GET /api/v1/world`는 한 트랜잭션에서 읽은 현재 실행의 원자적 스냅샷입니다. run/revision, 주문·작업 지시·로트, 소재·버전·계보, 공정·운송·검사, 자원, 출하·적재 명세, 질량 수지, 이벤트, 생산 투영, KPI, ETA와 회복 비교를 포함합니다. 프런트의 Zod와 백엔드의 Pydantic이 계약을 검사합니다. 브라우저는 업무 상태를 만들지 않으며 오래된 응답이 새 명령 결과를 덮어쓰지 않게 처리합니다.

| 값 | 의미 |
| --- | --- |
| epoch | `2026-10-30T00:00:00Z` |
| `elapsed_ms`, 이벤트 `at_ms` | 시뮬레이션 ms; 1000은 제조 업무 1분 |
| UTC 시각 | `epoch + elapsed_ms × 60` 실제 밀리초 환산 |
| `revision` | 현재 실행의 권위 있는 상태 버전 |
| `plan_revision` | 공정/물류 사건에 따른 예측 계획 버전 |
| `recorded_at`, `started_at` | 기록/실행 생성의 실제 UTC 시각; 제조 시각과 구분 |
| kg | 정수 질량; 비활성 부모와 과거 버전은 현재 재고에서 제외 |

초기 fixture는 20주문·21작업 지시·21로트·22소재·21출하 계획입니다. 최종 활성 소재 24개는 분할로 생기며 전체 소재 이력 행 수와 다릅니다. GA 주문은 60,300 kg, 2로트·3소재, 배송 40,200 kg + 20,100 kg입니다. 합성 질량 수지는 408,000 + 1,200 = 407,300 + 1,900 kg이며 첨가·손실은 명시적 기록입니다. ORE는 추적 금속량, 티타늄 시작 경계는 입고된 TI_INGOT입니다.

NORMAL/DELAY/RECOVERY는 같은 초기 계획과 동일 납기를 비교합니다. ETA는 읽기 전용 복제 상태에서 실제 전체 엔진을 끝까지 실행해 계산합니다. 현재 합성 계획의 HSM-B 우회는 `NO_BENEFIT`입니다. 우회 가능성과 배송 이득은 다른 판단입니다. 완료 시각/주문별 차이는 실제 실행 영수증에서 확인하며 고정 숫자로 UI 결과를 만들지 않습니다.

## 필수 조회 API

모든 아래 경로 앞에 `/api/v1`을 붙입니다. 조회는 시계를 전진시키지 않습니다. 존재하지 않는 식별자는 404입니다.

| 메서드·경로 | 응답·용도 |
| --- | --- |
| `GET /world` | 현재 통합 World |
| `GET /kpis` | 같은 World에서 계산한 누적 실적 |
| `GET /orders?q=` | 주문 ID·강종·고객 이름 검색 배열 |
| `GET /orders/{order_id}` | 고객·작업 지시·로트·소재·출하 연결 |
| `GET /materials/{material_id}` | 소재·현재 위치·주문·버전·계보·공정·운송·검사·출하 |
| `GET /coils/{coil_id}` | 현재 형상이 코일인 소재의 호환 투영; 비코일 소재는 404 |
| `GET /shipments` | 현재 실행의 출하 배열 |
| `GET /production` | 같은 World의 공정·설비·배치 투영 |
| `GET /production/stages/{stage_id}` | 해당 공정과 연결 배치 |
| `GET /events` | 통합 실행 및 보존된 legacy 물류 이벤트 이력 |
| `GET /events?run_id=...` | 특정 실행 이력; 현재 World.events는 현재 실행만 포함 |
| `GET /scenarios` | NORMAL/DELAY/RECOVERY 설명 배열 |
| `GET /journey/products` | 제품 설명 카탈로그 |
| `GET /journey?material_id=...` | 같은 실행의 소재 투영; 기본 MAT-ga-01 |
| `GET /journey/events?run_id=...` | legacy journey 이력과 통합 소재/공정 이벤트 |

`GET /health`는 `/api/v1` 밖의 준비 상태 경로입니다. `/docs`, `/openapi.json`은 백엔드 포트에서 직접 엽니다. Vite 프록시는 `/api`와 `/health`를 전달합니다.

## 명령과 호환 alias

| POST 경로 | 본문 추가 필드 | 결과 |
| --- | --- | --- |
| `/api/v1/simulation/play` | 선택 `speed`: 1/2/4 | 같은 실행 재생 |
| `/api/v1/simulation/pause` | 없음 | 같은 실행 정지 |
| `/api/v1/simulation/speed` | 필수 `speed`: 1/2/4 | 재생/정지 상태를 유지한 속도 변경 |
| `/api/v1/simulation/step` | 선택 `steps`: 정수 1–48, 기본 1 | 한 단계당 1000 시뮬레이션 ms |
| `/api/v1/simulation/reset` | 없음 | 같은 시나리오의 새 실행, 정지 상태 |
| `/api/v1/scenarios/{NORMAL,DELAY,RECOVERY}/activate` | 없음 | 선택 시나리오의 새 실행, 정지 상태 |
| `/api/v1/journey/{play,pause,speed,step,reset}` | 위 공통 명령과 동일 | deprecated alias; **전체 통합 실행**에 적용 |
| `/api/v1/journey/select` | `product_id` | 해당 제품의 첫 활성 소재 조회; 업무 상태 변경 없음 |

공통 명령 본문에는 `run_id`, `command_id`, 필요 시 `expected_revision`을 넣습니다. 화면은 새 UUID의 command_id와 현재 run을 보내고, 초기화/시나리오 변경 전에 재생을 멈춰 revision 경합을 피합니다. 응답은 World 전체에 `applied_revision`, `replayed`가 추가된 **평탄한 객체**입니다. `{world: ...}` 포장 객체가 아닙니다.

같은 run/command ID와 동일 payload를 재전송하면 영수증의 적용 revision을 돌려주고 다시 변경하지 않습니다. 같은 ID를 다른 payload로 재사용하거나 오래된 run/revision을 보내면 409입니다. 부적합한 필드·속도·단계 수는 422입니다. 수동 스크립트는 정지 상태에서 현재 run/revision을 읽고 명령을 순서대로 보내십시오. 재생 중 UI `한 단계`는 비활성입니다.

과거 `?workspace=production`은 공정 깊이, `?workspace=journey`는 설비 깊이로 정규화합니다. `?view=2d`, `order_id`, `material_id`, `stage_id`, `equipment_id`, `shipment_id`를 초기 주소에 사용할 수 있고, 이후 URL `nav`는 탐색과 카메라를 보관합니다. 이전 실행/없는 ID는 안내 후 현재 실행에서 다시 확인합니다. 주소 이동이나 소재 선택은 reset이 아닙니다.

## 추가 마이그레이션과 백업·복원

`ops_20261024_unified`는 기존 `9db710a4c201` 위에 operations 테이블·제약·현재 실행 포인터를 추가합니다. legacy 물류/생산/journey 행과 이벤트를 삭제하거나 통합 재고로 합산하지 않습니다. 신규 업무는 통합 엔진에서만 기록하고 보존 이벤트는 이력 조회로 접근합니다. 이미 통합 실행이 있으면 시작할 때 새 fixture로 덮어쓰지 않습니다.

운영 중인 원본 DB 파일을 단순 복사하지 말고 SQLite backup API를 사용합니다. 다음은 **읽기 전용 원본 → 새 파일** 백업 예시입니다. 실제 데모 DB 경로와 새 백업 파일 경로를 지정하고 기존 파일을 덮어쓰지 않습니다.

```sh
python3 - /absolute/path/steelflow.sqlite /absolute/path/backup-before-upgrade.sqlite <<'PYBACKUP'
import sqlite3, sys
from pathlib import Path
source, backup = map(Path, sys.argv[1:])
if not source.is_file() or backup.exists():
    raise SystemExit('원본 파일이 필요하며 백업 대상은 새 경로여야 합니다.')
with sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True) as src:
    with sqlite3.connect(backup) as dst:
        src.backup(dst)
        assert dst.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert dst.execute('PRAGMA foreign_key_check').fetchall() == []
print(backup.resolve())
PYBACKUP
```

복원은 원본에 덮어쓰지 않습니다. 위 스크립트의 원본을 백업 파일로, 대상을 새 `restored.sqlite`로 지정해 복제하고 `STEELFLOW_DATABASE_URL`을 새 파일로 바꿔 별도 비점유 포트에서 실행합니다. health/world, 주문 수, 현재 run, 이벤트와 질량 수지를 확인한 뒤 사용할 복사본을 선택합니다. 현재 앱으로 legacy 백업을 열면 추가 마이그레이션이 적용되므로 원본 백업은 계속 보존합니다. 스키마 downgrade나 원본 삭제는 이 절차에 없습니다. 복원 가능성은 해당 백업 파일의 무결성과 실제 실행으로 검증해야 합니다.

## 장애와 로컬 검증

설치 후 앱의 핵심 운영은 로컬에서 실행됩니다. AI 기본값은 false이며 외부 공급자가 주입되지 않으면 활성화 플래그만으로 외부 호출이 발생하지 않습니다. 공급자가 없어도 규칙·생산·물류·ETA가 동작합니다. HTTP 제한 8초를 넘거나 연결이 실패하면 마지막 상태/수신 시각을 유지하고 명령을 잠근 뒤 다시 연결합니다. WebGL 실패는 2D를 사용합니다.

일반 E2E는 독립 SQLite·8001/5174, preview E2E는 독립 SQLite·8002/4175와 run 디렉터리의 dist를 소유합니다. 기존 8000/4173과 기본 dist를 재사용하지 않습니다. `STEELFLOW_E2E_PREVIEW=1`에서는 `VITE_API_TARGET`이 dev와 preview의 공통 프록시에 적용됩니다. 테스트가 끝나면 테스트가 시작한 서버만 종료합니다. 최종 유지 데모는 별도 디렉터리/프로세스 영수증을 보존합니다.

이 문서는 절차와 계약을 설명합니다. 실제 통과·녹화·유지 주소는 [검증 기록](TEST_RESULTS.md), [시연 안내](DEMO_2026_10_30.md), [증거 색인](evidence/operations/README.md)의 실제 파일이 존재하는 항목만 인정합니다.


## 현재 유지하는 데모와 재시작

2026-10-25에 [http://127.0.0.1:4175](http://127.0.0.1:4175)를 기동하고 health/World를 확인했습니다. 전용 루트는 `/Users/ethanlee/.local/share/steelflow/demos/2026-10-30-unified`, 초기 소유 PID는 backend **78616**, preview **78711**입니다. [최초 기동 영수증](evidence/operations/retained-demo-initial.json)에 실행 명령·시작 시각·DB·빌드 경로가 있고, [최종 영수증](evidence/operations/retained-demo.json)은 수동 F3 PASS·F1/F2/F4 APPROVE 및 별도 최종 reset을 기록합니다. 최종 reset은 NORMAL·elapsed0·revision0·정지·1×·20주문·22소재·AI off입니다. PID는 재시작 후 달라질 수 있으므로 종료 전 현재 명령/시작 시각을 대조해야 합니다. 원래 8000/4173 프로세스는 이 데모의 종료 대상이 아닙니다.

`backend/`는 동결 소스 복사본이고 `shared/factory-layout.json`도 같은 상대 위치로 복사했습니다. `app/data`의 두 카탈로그와 `migrations/`, `alembic.ini`를 포함하며 원본 DB/.env는 복사하지 않았습니다. [소스 복사 해시](evidence/operations/retained-runtime-source-copy.json)로 동일성을 확인합니다. 이 보존본은 기존 저장소의 Python venv와 Node/Vite 설치를 재사용하므로 완전한 독립 배포 패키지는 아닙니다.

이 작업은 테스트 임시 서버가 아니라 의도적으로 남겨 둔 단일 운영자용 localhost 데모입니다. DB는 `state/steelflow.sqlite`, 정적 파일은 `dist/`, 로그는 `logs/`, 영수증은 `receipts/`에 있습니다. 시스템 재부팅 시 자동 기동하는 서비스는 설치하지 않았습니다. 기존 소유 서버가 종료되어 8002/4175가 비어 있으면 다음 두 터미널로 같은 DB를 다시 열 수 있습니다.

```sh
# 터미널 1 — 보존한 backend 소스와 DB
cd /Users/ethanlee/.local/share/steelflow/demos/2026-10-30-unified/backend
STEELFLOW_DATABASE_URL=sqlite+aiosqlite:////Users/ethanlee/.local/share/steelflow/demos/2026-10-30-unified/state/steelflow.sqlite \
  STEELFLOW_AI_ENABLED=false PYTHONDONTWRITEBYTECODE=1 \
  /Users/ethanlee/Desktop/ERP/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8002
```

```sh
# 터미널 2 — 보존한 정적 빌드
cd /Users/ethanlee/Desktop/ERP
VITE_API_TARGET=http://127.0.0.1:8002 npm run preview -- --port 4175 --strictPort \
  --outDir /Users/ethanlee/.local/share/steelflow/demos/2026-10-30-unified/dist
```

재시작은 저장된 실행을 정지 상태로 복원합니다. 위 재시작 절차 자체의 추가 실연은 아직 수행하지 않았으며 현재 영수증은 새 DB로 최초 기동한 결과입니다. README 명령 구성의 독립 preview 검증과 보존본의 추가 기동은 [검증 기록](TEST_RESULTS.md)에서 구분합니다. 동작 중 브라우저 수동 검증은 해당 작업 담당자 한 명이 소유합니다.
