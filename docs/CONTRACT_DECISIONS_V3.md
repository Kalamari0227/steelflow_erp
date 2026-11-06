# Schema 3 이벤트 기본값·UTC 계약 결정

결정일: 2026-10-26. 상태: **계약 결정 확정, 제품 구현 미적용**. 이 문서는 현재 `EventContext`/`FactoryEvent`와 공통 UTC 경계의 Sol High 구현 기준이다. 새로운 반증 없이 구현자가 다른 계약을 선택하지 않는다. 보관 motion 오류 계약은 아래 연결 문서를 따른다.

## 범위와 모델 증거

- 프로젝트 `AGENTS.md`를 읽고 `gpt-6-astra` / `high`를 명시한 하위 작업으로 dispatch되었다. 증거는 요청·dispatch 메타데이터이며 독립적인 서버 모델 self-identification은 없다. 루트 모델을 추측하지 않는다.
- 여기서는 문서와 읽기 전용 프로브 증거만 만들었다. 구현은 GPT-6.1 Sol High, 구현 후 독립 계약·통합 검토는 GPT-6 Astra High에서 수행한다.
- 기존 T6/T55 중단 상태, candidate02 `STOPPED_UNVERIFIED_NOT_INSTALLED`, 원래 작업 체크포인트를 유지한다. 보관 후보 복원·설치나 과거 완료 판정 변경은 승인 범위에 포함되지 않는다.
- 현재 코드가 이미 고쳐졌거나 실제 HTTP 장애가 재현되었다고 주장하지 않는다. 이번 결정은 전체 생산 → 검사 → 재고 → 출하 구현 또는 검증 완료가 아니다.

## 결정 D1 — 생략을 기본값으로 확장하는 이벤트 입력

Python의 기존 이벤트 생성과 부분 payload 입력을 유지한다. TypeScript도 **동일한 JSON 입력**을 같은 완전한 출력으로 정규화한다. 다음 14개 키는 입력에서는 생략 가능하지만 출력에는 모두 존재한다.

| 필드 | 생략 시 출력 | 명시적 null | 그 외 허용값 |
| --- | --- | --- | --- |
| reason_code | null | 허용 | 길이 1 이상 문자열 |
| reason | null | 허용 | 길이 1 이상 문자열 |
| material_ids | [] | 거절 | 길이 1 이상 문자열의 배열, 빈 배열 허용 |
| order_id | null | 허용 | 길이 1 이상 문자열 |
| work_order_id | null | 허용 | 길이 1 이상 문자열 |
| process_id | null | 허용 | 길이 1 이상 문자열 |
| batch_id | null | 허용 | 길이 1 이상 문자열 |
| job_id | null | 허용 | 길이 1 이상 문자열 |
| shipment_leg_id | null | 허용 | 길이 1 이상 문자열 |
| resource_id | null | 허용 | 길이 1 이상 문자열 |
| from_attachment_id | null | 허용 | 길이 1 이상 문자열 |
| to_attachment_id | null | 허용 | 길이 1 이상 문자열 |
| from_owner_id | null | 허용 | 길이 1 이상 문자열 |
| to_owner_id | null | 허용 | 길이 1 이상 문자열 |

| JSON 입력 | 결과 | 정규화 |
| --- | --- | --- |
| context `{}` | 수락 | 위 14개 기본값 |
| context `{"reason":"lane occupied","job_id":"j"}` | 수락 | 제공한 값 보존, 나머지 기본값 |
| event에서 payload 키 생략 | 수락 | 완전한 14개 기본 context 생성 |
| event의 payload `{}` 또는 부분 객체 | 수락 | 완전한 14개 context로 확장 |
| payload null / 배열 / 문자열 / 숫자 | 거절 | 없음 |
| context 또는 event의 알 수 없는 키 | 거절 | 키 삭제로 성공 처리하지 않음 |
| nullable 필드의 숫자·boolean·배열·객체, 빈 문자열 | 거절 | 형 변환·trim·대체 기본값 없음 |
| material_ids null / 문자열 / 숫자 원소 / null 원소 / 빈 ID | 거절 | 없음 |

문자열 공백만 있는 값, material_ids 중복·순서는 현행 최소 길이 규칙을 그대로 따른다. 이번 변경으로 trim, dedup, ID 실재성 검사나 새로운 이벤트별 payload 필수 규칙을 추가하지 않는다. event의 나머지 필드는 여전히 필수이고 기존 enum, 안전한 정수, sequence > 0, at_ms 범위를 유지한다. JSON에는 undefined가 없다. JS 호출에서 optional 입력 키의 undefined가 생략으로 취급되는 것은 허용하지만 null을 생략으로 취급하지 않는다.

출력은 Python frozen 모델·tuple과 TypeScript readonly 객체·배열이다. event, payload, material_ids 각각 불변성을 보장해야 하며, 기본값 경로도 일반 parse 경로와 동일하게 검증·동결한다. 파싱 결과 사이에서 변경 가능한 기본 배열/객체를 공유하지 않는다. 입력 객체도 수정하지 않는다. TS의 입력 타입은 생략 가능, 출력 `z.output`/`z.infer` 타입은 완전한 필수 필드이며 UI 소비자에 optional 필드를 전파하지 않는다.

## 결정 D2 — 공통 JSON 입력, canonical 출력, 내부 datetime의 세 경계

**공통 raw JSON 입력은 정해진 UTC 문자열을 수락하고, 출력은 항상 `YYYY-MM-DDTHH:mm:ss.sssZ`로 정규화한다.** TypeScript `utcSchema`는 구현 후 canonical 형식만 수락하던 파서에서 허용 입력을 canonical 출력으로 변환하는 파서로 바뀐다. 기존 wire-only 수락 정책이 그대로라고 표현하지 않는다.

이 결정은 Python 기존 회귀 시험의 초 단위 `...00Z`를 보존하고 두 언어의 같은 JSON 수락 여부를 맞춘다. Python만 넓은 입력을 수락하는 현상을 모두 의도된 producer 전용 경계로 재분류하지 않는다. 대신 세 경계를 아래처럼 명시한다.

| 경계 | 허용되는 표현 | 결과 |
| --- | --- | --- |
| 공통 JSON 입력 | 아래 엄격한 UTC 문자열 문법 및 실제 달력 값 | Python datetime / TS canonical 문자열로 파싱 |
| JSON wire 출력 | 4자리 연도, 소수 3자리, 대문자 T와 Z | Python serializer와 TS parsed output이 같은 문자열 |
| Python 내부 생성·model_validate | 공통 문자열 또는 실제 aware UTC datetime | timezone offset 0, 정확한 밀리초만 허용; JSON 직렬화 시 canonical |

공통 입력 문자열의 전체 문법은 `YYYY-MM-DDTHH:mm:ss[.fraction](Z|+00:00)`이다. 연도는 정확히 4자리 0001..9999, 월·일·시·분·초는 정확히 2자리, 대문자 T/Z, fraction은 없거나 1..6자리 ASCII 숫자이다. fraction 4..6자리의 **네 번째 이후 숫자가 전부 0**이어야 한다. 빈 소수부, 공백, lowercase, 콤마, compact offset, 생략된 초, 앞뒤 공백은 거절한다. 문자열 자르기·반올림·timezone 변환으로 잘못된 입력을 보정하지 않는다.

| 입력 UTC 예 | 양쪽 수락 여부 | canonical 출력 / 거절 이유 |
| --- | --- | --- |
| `2026-10-30T00:00:00Z` | 수락 | `2026-10-30T00:00:00.000Z` |
| `2026-10-30T00:00:00.0Z` | 수락 | `2026-10-30T00:00:00.000Z` |
| `2026-10-30T00:00:00.12Z` | 수락 | `2026-10-30T00:00:00.120Z` |
| `2026-10-30T00:00:00.123Z` | 수락 | 동일 |
| `2026-10-30T00:00:00.1230Z`, `.123000Z` | 수락 | `2026-10-30T00:00:00.123Z` |
| `2026-10-30T00:00:00+00:00` | 수락 | `2026-10-30T00:00:00.000Z` |
| `2026-10-30T00:00:00.123+00:00` | 수락 | `2026-10-30T00:00:00.123Z` |
| `.1234Z`, `.123456Z`, `.000001Z` | 거절 | 밀리초보다 작은 실값 |
| `.1230000Z`, `.1230001Z` | 거절 | 6자리를 초과한 소수부; 파싱 전 거절 |
| `...-00:00` | 거절 | unknown offset 표기를 UTC 확정값으로 변환하지 않음 |
| `...+09:00`, `...-01:00` | 거절 | UTC 외 offset; UTC로 이동하지 않음 |
| timezone 없는 날짜·시각, 날짜만 | 거절 | UTC를 추정하지 않음 |
| 숫자 epoch 초/밀리초, 실수 epoch, 숫자 문자열, boolean, null, 배열, 객체 | 거절 | 문자열 UTC 외 입력 coercion 금지 |
| `2026-10-30t00:00:00z`, `2026-10-30 00:00:00Z`, `...00,123Z`, `...+0000`, `...T00:00Z` | 거절 | 문법 불일치 |
| `0001-01-01T00:00:00.000Z` | 수락 | 동일: UTC 최솟값 |
| `0099-12-31T23:59:59.999Z` | 수락 | 동일: 0..99 연도를 1900년대로 보정하지 않음 |
| `9999-12-31T23:59:59.999Z` | 수락 | 동일: UTC 최댓값 |
| 연도 0000, 10000, 음수 연도 | 거절 | Python/TS 공유 연도 범위 초과 |
| `2024-02-29...`, `2000-02-29...` | 수락 | 유효한 윤일 |
| `1900-02-29...`, `2026-02-29...`, `2026-02-30...`, 월13, 일00 | 거절 | Gregorian 달력상 불가능 |
| 시각 `24:00:00`, 초60, 분60 | 거절 | overflow·leap-second 보정 금지 |

표의 `...`와 `.fractionZ`는 앞부분을 바꾸지 않은 축약 표기다. 실제 테스트 입력은 완전한 문자열을 사용한다. 달력 검증은 단순 Date.parse 성공만으로 충분하지 않다. 정규화 후보와 달력 재직렬화 결과가 정확히 같은지 확인하거나 동등한 명시적 달력 검증을 한다. JS의 날짜 overflow 보정 및 0..99년 특수 처리에 의존하지 않는다. Python에서도 raw 문자열을 datetime으로 파싱하기 **전에** 문법·소수부를 검사한다. 현재 `.1230001Z`가 `.123Z`로 잘리는 현상은 후처리 validator만으로 막을 수 없다.

Python 내부 `datetime`은 `utcoffset() == 0`인 aware 값과 `microsecond % 1000 == 0`만 허용한다. naive와 nonzero offset은 `utc_required`, submillisecond는 `time_out_of_range`인 기존 `utc_only`/`canonical_utc` 직접 호출 계약을 보존한다. 새 raw JSON 문법 거절은 모델 validation 실패로 처리한다. Python/TS validator 내부 issue code·메시지·배열 순서까지 같을 필요는 없다. 이 변경 때문에 HTTP 공개 error code/status 매핑을 새로 정의하거나 바꾸지 않는다.

### UTC 범위와 시뮬레이션 시간 범위는 다르다

- 공통 UTC 값 범위: `0001-01-01T00:00:00.000Z` .. `9999-12-31T23:59:59.999Z`.
- `EPOCH_AT = 2026-10-30T00:00:00.000Z`, `BUSINESS_FACTOR = 60` 유지.
- `sim_ms_to_utc`의 정확한 정수 범위: `MIN_SIM_MS = -1065481920000`, `MAX_SIM_MS = 4193483039999`. 경계 밖·bool·실수는 기존 `time_out_of_range`로 거절한다.
- 변환 최솟값은 `0001-01-01T00:00:00.000Z`, 최댓값은 `9999-12-31T23:59:59.940Z`다. 60ms 격자 때문에 UTC 최대 .999Z와 다르다.
- 도메인 `Ms` 필드, event `at_ms`, run elapsed는 여전히 0..MAX_SIM_MS이며 signed adapter 허용 범위를 그대로 적용하지 않는다. `Duration`은 0보다 커야 한다. run epoch는 기존 고정 epoch 관계 검사를 유지한다.
- 유효한 일반 due_at/started_at/occurred_at UTC를 60ms 격자로 제한하지 않는다. 사건 시각과 at_ms의 기존 관계 검증을 변경하거나 새로운 관계 규칙을 추가하지 않는다.

## 호환성과 변경 경계

canonical wire 문자열과 완전한 payload 출력 모양, 키 의미, ID, event 순서, 질량·상태·시간 도메인 규칙은 유지한다. 초 단위 UTC와 부분 context를 사용하는 기존 Python 생성자·저장 fixture·회귀 시험은 계속 성공해야 한다. DB 저장본, fixture 원본 bytes와 bundle hashes, schema1/2 과거 기록을 재작성하지 않는다. legacy `contracts.py`/`contracts.ts`는 변경하지 않는다.

**입력 수락 범위의 의도된 변경은 있다.** TS는 생략된 기본값과 허용 UTC 별칭을 더 수락하며, Python은 숫자 시각·비표준 표현·6자리 초과 소수 등 명세 밖 coercion을 더 이상 수락하지 않는다. 조사한 코드·fixture에서는 이러한 거절 대상에 의존하는 정식 입력을 확인하지 못했지만 모든 외부 클라이언트나 실제 DB를 조사하지 않았다. 따라서 무조건적인 API 무변경·무호환성 위험 주장을 하지 않는다. 구현 전 새 반증이 발견되면 기록하고 Astra High에서 해당 좁은 문제를 다시 판단한다. 임의로 history 정리나 마이그레이션을 실행하지 않는다.

## 읽기 전용 실행 증거

새 프로브: `.omo/evidence/contract-decisions-20261026/utc-defaults/`.

- 같은 JSON을 현재 Python/TS production parser에 넣은 **93개**: 원본 기본값 46개 + UTC 47개. `cases.json`, `python.stdout`, `typescript.stdout`, `comparison.json`에 원자료가 있다.
- 기본값 46개는 수락 불일치19, 양쪽 수락/동일2, 양쪽 거절25를 재현했다.
- UTC47은 현 코드의 seconds-Z/zero-offset/precision 별칭 및 숫자 coercion 차이를 기록한다. 특히 `.1230001Z`가 Python에서 `.123Z`로 손실되는 실제 결과를 보존했다. 이것은 기대 결과가 아닌 수정 전 관측이다.
- Python이 수락하여 직렬화한 **47개 실제 결과**(기본값21 + UTC26)를 TS로 다시 전달했다. 모두 수락하고 동일한 JSON 값을 유지했다. `bridge-cases.json`, `bridge.stdout`, `bridge-result.json`. 이 producer → canonical wire 성공은 현재 raw-input parity 실패를 없애지 않는다.
- Python 내부 datetime6개와 정확한 adapter 양 끝값을 추가 기록했다(`python.stdout.internal`, `.bounds`). 새 parser 구현을 검증한 것이 아니다.
- `run-probes.py`, `run-bridge.py`를 `PYTHONDONTWRITEBYTECODE=1 python3 ...`로 실행했다. bounded child 총3개, 각 timeout20초, 모두 exit0/stderr0. exit0은 프로브 완료이며 계약 parity 통과라는 뜻이 아니다.
- 전후 **746개 경로** 해시·존재 상태 동일. `source-before.json`, `source-after.json`, `bridge-source-after.json`, `cleanup.json`, `bridge-cleanup.json`. task-owned runtime/cache만 제거했고 모든 child 종료, 서버/포트 생성 없음, 보관 exact44 현재 전부 absent.
- 네트워크 서비스·DB·서버·전체 테스트를 실행하지 않았다. 현재 계약과 실제 독립 실행 결과에 기초한 결정이며 운영 장애/전체 통합 통과 증명은 아니다.

현재 주요 source SHA256:

| 파일 | SHA256 |
| --- | --- |
| backend/app/operations/contracts_v3_rows.py | 915ff3fd9c04b66849b9d18750c9642d6c5abe1f179188888e3a5e9ecfe27fac |
| src/operations/contractsV3Rows.ts | e798f02bce1d76a0f477fb019ea396f34b44d0f1e7c0cd8ae02232c59e315f25 |

나머지 UTC/core/소비자/시험·보관 경로의 전체 해시는 위 manifest가 권위다. 명령별 argv/cwd와 환경 override는 각 `*-invocation.json`에 있다. 과거 probe/script를 덮어쓰거나 실행해 이전 증거를 갱신하지 않는다.

## 구현 메모와 문서 근거

설치 버전은 Pydantic 2.14.1, Zod 4.6.7이었다. Context7 skill을 읽고 resolve → query 순서로 확인했다. Pydantic은 정확한 2.14.1 문서를 조회했다. Zod는 exact4.6.7 index가 없어 가장 가까운 공식4.6.5 문서를 조회했으므로 구현자는 설치4.6.7에서 해당 동작을 회귀 시험해야 한다.

- [Pydantic 2.14.1 datetime 검증](https://github.com/pydantic/pydantic/blob/v2.14.1/docs/api/standard_library_types.md): 숫자와 숫자 문자열을 timestamp로 coercion할 수 있다. 프로젝트 정책이 그 전체 범위를 허용하는 것은 아니다.
- [Pydantic 2.14.1 before validators](https://github.com/pydantic/pydantic/blob/v2.14.1/docs/concepts/validators.md): raw 입력을 coercion 전에 검사하여 소수 손실을 방지할 지점이다.
- [Zod 4.6.5 defaults/prefault/readonly](https://github.com/colinhacks/zod/blob/v4.6.5/packages/docs/content/api.mdx): default는 parsing을 생략할 수 있고 prefault는 parsing을 거친다. composite 기본값이 검증과 동결을 우회하지 않게 구현한다. nullable scalar 기본값, input/output 타입 구분, 객체·배열 readonly 결과를 실제 검사한다.

## 결정 D3 — 생성 JSON Schema도 입력·출력을 구분한다

Python `UTCDateTime`의 validation JSON Schema는 공통 문자열 문법 pattern과 `type=string`, `format=date-time`를 제공한다. serialization JSON Schema는 canonical `.sssZ` pattern과 동일 type/format을 제공한다. validation pattern은 연도0000·6자리 초과·subms·-00:00 등 본문의 문자열 범위를 표현해야 한다. 실제 Gregorian 달력 유효성은 runtime validator와 `date-time` format 의미로 보장하며 pattern만으로 달력 전체를 증명했다고 주장하지 않는다. TypeScript 입력/출력 type은 모두 string이지만 실제 parse 결과의 canonical성은 runtime 시험으로 증명한다.

EventContext와 FactoryEvent의 **validation schema**는 D1의 기본값 필드를 required로 바꾸지 않는다. 반대로 두 모델의 **serialization schema**는 기본값으로 채워지는 14개 context 필드와 payload를 required로 표시해야 한다. 중첩 `$defs`도 확인한다. 이것은 항상 존재하는 실제 응답을 정확히 설명하는 metadata 수정이며 Python 입력을 필수 필드로 바꾸는 지시가 아니다. 다른 모든 모델의 serialization-required 정책을 일괄 변경하지 않는다.

현재 fixture `shared/fixtures/factory-contract-test-v3/schema.json`은 format/profile/purpose를 가진 **test-only descriptor**이며 생성 domain JSON Schema가 아니다. descriptor·bundle.json·domain.json bytes/hash 변경은 필요하지 않다. generated JSON Schema는 runtime `model_json_schema(mode='validation'|'serialization')`와, 관련 모델을 참조하는 FastAPI OpenAPI components에서 확인한다. 기존 API 예시·저장 fixture를 새 grammar에 맞추려고 재작성하지 않는다. OpenAPI 출력에 대한 확인은 격리된 import/subprocess로 수행하며 운영 서버·DB를 시작하지 않는다.

## 결정 D4 — 보관 motion stable code와 복수 오류 순서

이 규칙은 향후 승인된 T6 motion 재개용이다. 현재 없는 44개 파일을 이번 Sol 작업에서 복원하지 않는다. 상세 소스 참조·19개 golden 사례는 [motion 결정 근거](../.omo/drafts/steelflow-error-contract-decision-20261026.md), 원자료는 `.omo/evidence/contract-decisions-20261026/errors/`에 있다. 해당 문서의 구체적인 단계 내부 순서를 이 결정에 포함한다.

| 오류 종류 | 확정 stable code |
| --- | --- |
| 존재하는 policy의 required ∪ state-bound-fixed 함수 ID 집합과 전체 binding 집합이 다름(누락 포함) | unknown_function, reference=policy_id |
| 함수 ID 중복 | duplicate; 집합으로 지우지 않음 |
| owner/policy 부재, socket rest 위치, descriptor, state/moving kind, placement 위반 | binding |
| graph socket ID 부재 | unknown_socket |
| 비단위 축 | axis |
| JSON 구조/type/필수 필드/version 오류 | invalid_contract |

검사는 코드 이름의 전역 정렬이 아니라 아래 단계 순서로 수행한다. 첫 실패를 반환하며 배열은 입력 순서, 객체 필드는 선언 순서이다.

1. UTF-8·JSON 문법(`json`) → 유효한 JSON의 duplicate member(`duplicate`) → **envelope와 context 전체**의 strict scalar/닫힌 구조/type/필수/version(`invalid_contract`). 구조가 유효하지 않은 sibling이 남아 있을 때 semantic callback을 실행하지 않는 장벽을 둔다.
2. typed envelope 로컬 의미: 중첩 quaternion 등의 필드 제약 후 window → future_time → held_progress_required → channel ID duplicate → channel axis. 이어 context의 snapshot → world → authorizations(입력 순서, 각 envelope 동일 규칙) → asset_bindings 로컬 검증.
3. binding 로컬 의미: 중첩 socket quaternion 등 필드 제약, 각 function의 min<max(binding) → axis → node_id 일치(binding), socket ID duplicate → function ID duplicate → socket moving-function 참조(binding). 모든 binding 이후 context owner duplicate → authorization execution duplicate.
4. 각 binding admission: owner(binding) → 각 socket 존재(unknown_socket)·rest 거리≤0.01m(binding) → policy(binding) → 전체 함수 집합(unknown_function) → state/moving 분류(binding) → placement(binding).
5. 고정 registry 검증 → recipe lookup(unknown_recipe) → recipe/envelope execution_kind(execution) → stale_run → stale_bundle → stale_revision → stale_time → exact authorization(unauthorized).
6. Python 기존 validate_authority의 held progress/material/custody → validate_execution → validate_anchor → recipe/channel binding·기하 → boundary 순서. 공정/custody 규칙 자체를 변경하지 않는다.

따라서 P1+stale_revision은 unknown_function, P1+placement는 unknown_function, P1+axis는 axis, P1+missing-socket은 unknown_socket, P1+bad-version/type은 invalid_contract, unknown_recipe+stale는 unknown_recipe, execution-kind+stale는 execution, future_time+stale는 future_time이다. **admission을 staleness 뒤로 옮기지 않는다.** 구조 완료 장벽과 execution-kind 선검사는 실측 불일치를 해소하는 의도된 결정이다.

공통 motion CLI 거절은 exit2와 error.code를 모두 비교한다. 메시지·공백·JSON key 순서나 Pydantic/Zod 내부 issue code 동일성은 요구하지 않는다. 현재 HTTP의 400/409/422·staleness/idempotency 우선순위를 변경하지 않는다. 상세 근거 문서에 현재 `factory_routes.py`의 validation→422/invalid_contract, ServiceError의 지정 status, TimeAdapterError의 지정 status/code 경계를 기록했다.

candidate01 동일 소스의 19개 입력을 Python/TS 각각 실행한 38 bounded child가 종료했고 stderr0, 보호한682개 파일 해시 동일, 현재 exact44 absent이다. original P1 요청 SHA256 `afc24511e836e72fec313a5adfca0733285aad4fe0e75831b170137586d2264c`를 보존했다. candidate02는 실행하지 않았다. 이 결과를 현재 설치 API 오류나 새 구현 검증으로 표시하지 않는다.

실행 가능한 Sol High 인계는 [.omo/drafts/steelflow-contract-parity-sol-high.md](../.omo/drafts/steelflow-contract-parity-sol-high.md)를 따른다.
