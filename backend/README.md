# SteelFlow 통합 운영 백엔드

FastAPI 단일 프로세스가 공통 실행 시계와 모든 생산·물류 상태를 소유합니다. 데이터는 모두 합성입니다. 단일 작업자만 실행하며 `--workers`를 늘리지 않습니다. 프로세스 내부 트랜잭션 잠금과 시계를 사용하므로 다중 서버 운영은 지원하지 않습니다.

```sh
# backend 디렉터리에서 최초 설치
uv sync --frozen --python 3.13
# 새 독립 DB 경로를 선택한 후 실행
STEELFLOW_DATABASE_URL=sqlite+aiosqlite:////absolute/path/demo/steelflow.sqlite \
  STEELFLOW_AI_ENABLED=false .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8002
```

시작 시 Alembic head를 적용하고, 통합 실행이 없을 때만 최초 실행을 만듭니다. 기존 실행은 재시작 시 일시정지로 복원됩니다. 기본 DB는 `backend/steelflow.db`이므로 기존 데모가 있으면 반드시 별도 경로를 지정합니다. 초기 전체 스케줄 계산 중에는 `/health`가 준비되기까지 시간이 걸릴 수 있습니다.

| 변수 | 기본값 | 의미 |
| --- | --- | --- |
| `STEELFLOW_DATABASE_URL` | `backend/steelflow.db` 절대 경로 SQLite URL | 독립 DB 선택 |
| `STEELFLOW_TICK_SECONDS` | `0.1` | 백엔드 wake 간격; 유한한 양수 |
| `STEELFLOW_AI_ENABLED` | `false` | 선택 설명 어댑터; 외부 공급자 기본 미제공 |
| `VITE_API_TARGET` | `http://127.0.0.1:8000` | 프런트 dev/preview 프록시; 백엔드 변수가 아님 |

업무 기준 시각은 `2026-10-30T00:00:00Z`입니다. 1000 시뮬레이션 ms는 제조 업무 1분입니다. 기본 1× 재생은 실제 약 1초에 업무 1분을 진행하며, 2×/4×는 같은 전이를 더 빠르게 진행합니다. UI 한 단계와 API `steps=1`도 1000 ms를 진행합니다. 시계는 프로세스가 실행 중일 때만 전진하고, 브라우저를 닫아도 재생 중인 백엔드는 진행합니다.

현재 fixture는 20주문·21작업지시·21로트·22투입소재·21출하를 계획합니다. 분할 후 활성 소재는 24개입니다. GA는 3소재(각 최종 20,100 kg), 2로트 및 2출하(40,200 + 20,100 kg)입니다. PLATE/TI_SHEET 분할 부모는 계보에 남고 활성 재고에서 제외됩니다. 모든 질량 증가·손실은 명시적 mass movement로 기록합니다.

`app/operations/`의 engine·transport·fulfillment가 업무 상태를 전이하고 `service.py`가 트랜잭션·명령 중복·실행 복원 경계를 담당합니다. `forecast.py`는 같은 전체 엔진을 복제 상태에서 끝까지 실행해 ETA를 계산합니다. 예측 캐시는 불변 계획과 소스 서명으로 구분하며 조회로 현재 실행을 전진시키지 않습니다. 현재 RECOVERY 비교는 `NO_BENEFIT`이며 납기 개선을 가정하지 않습니다.

```sh
.venv/bin/python -m pytest -q
# 수동 추가 마이그레이션이 필요한 독립 DB에서만
STEELFLOW_DATABASE_URL=sqlite+aiosqlite:////absolute/path/demo/steelflow.sqlite uv run alembic upgrade head
```

API 필수 경로·deprecated alias·명령 충돌·백업/복원 절차는 [운영 문서](../docs/OPERATIONS.md), 실제 실행 결과는 [검증 기록](../docs/TEST_RESULTS.md)을 참조하십시오. 별도 6주문 물류 시계와 제품별 독립 제조 시계는 현재 서비스의 authoritative engine이 아닙니다. 기존 테이블·이벤트는 보존되지만 신규 업무는 통합 operations 실행에만 기록합니다.
