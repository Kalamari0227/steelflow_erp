# 통합 운영 계약 (erp-v1, schema_version=2)

`backend/app/operations/contracts.py`와 `src/operations/contracts.ts`는 같은 JSON 경계를 읽는다. 서비스의 전체 상태 원본은 기존 `GET /api/v1/world` 하나다. `OperationsSnapshot`은 이 응답에 합칠 내부 타입 경계다. T10/T11은 schema_version/materials 등 필드를 기존 World 최상위에 합치며, 중첩 operations 객체에 현재 상태를 복제하거나 별도 endpoint/원격 store를 만들지 않는다. 기존 호환 필드와의 결합은 T11/T12가 담당한다.

## 값과 식별

- 행의 실질 식별자는 `(run_id, id)`다. 모든 스냅샷 행은 `run.id`와 같은 실행이어야 하며, 각 컬렉션의 ID는 유일하다. 외부 master인 customer/location/equipment ID의 존재는 DB 복합/일반 FK와 서비스가 검사한다.
- `EntityId`는 업무 식별자, `RunId`는 실행 식별자다. Python `Kilograms`/`Milliseconds`는 단위가 구별되는 값이다. kg는 0 이상 정수이고 소재·계획량·수용량은 양수다. 문자열·불리언·소수 kg를 거부하며 JS 안전 정수 범위를 사용한다.
- 제품 ID는 소문자 20종이다. form은 `MaterialForm`의 canonical 이름이다. 기존 HR/CR 문자열을 묵시 변환하지 않는다. upstream form은 ORE/HOT_METAL/LIQUID_STEEL, Ti 경계는 TI_INGOT이다.
- width_mm/thickness_mm는 제품에 해당하지 않거나 생략하면 `null`이다. 후판·시트의 폭·두께처럼 해당 제품에 적용되는 치수를 제공하면 유한한 양수여야 한다. 0 치수를 만들어 넣지 않는다.
- UTC date-time만 허용한다. naive와 UTC가 아닌 offset은 거부한다. wire 출력은 ISO UTC, `epoch_at=2026-10-30T00:00:00Z`이다. 업무시각은 epoch + elapsed_ms × 60 ms다. 가상 occurred_at과 실제 recorded_at을 구분하며 pure engine은 recorded_at을 null로 둔다.

## 권위와 불변성

`OperationsRun`만 elapsed_ms/duration_ms/revision/event_sequence/playing/speed/plan_revision을 소유한다. epoch는 고정이고 elapsed_ms는 duration_ms를 넘을 수 없다. speed는 1/2/4, step은 1000ms × 1..48이다. 선택·카메라·HTTP 조회에 별도 clock을 만들지 않는다.

Pydantic 행은 `frozen=True`, extra 필드는 거부한다. 배열은 tuple이다. Zod 행과 배열은 readonly다. status는 모든 단계에서 명시한 literal union을 사용한다.

| 개념 | 상태 |
| --- | --- |
| 공정 | QUEUED / RUNNING / BLOCKED / COMPLETED |
| 운송 | WAITING / LOADING / IN_TRANSIT / UNLOADING / ARRIVED |
| 품질 | PENDING / PASSED / HOLD / FAILED |
| 가용성 | WIP / QUARANTINED / AVAILABLE / RESERVED / SHIPPED / CONSUMED |
| 출하 | PLANNED / ALLOCATED / LOADING / LOADED / DISPATCHED / AT_PORT / IN_TRANSIT / DELIVERED |

현재 소재와 current_version은 material ID/form/weight가 일치해야 한다. 이동·검사는 ID를 유지하며 1→1 공정은 version만 추가한다. 분할은 부모 inactive/CONSUMED, 자식 두 개와 lineage, 배정, 손실 원장을 원자 반영한다. 부모는 이력에서 제거하지 않는다. 자기 계보·순환·중복 계보, 중복 version ordinal, 중복 활성 운송·배정·출하, 다른 주문 출하를 거부한다. future child는 PlanSeed 계획 정보이며 active 재고에 선행 생성하지 않는다.

`MassMovement`는 input+additions=output+loss, 공정당 하나다. `MassBalance`는 initial+additions=active+loss이고 active는 현재 활성 소재를 한 번씩 합산한다. 배송된 소재도 active 질량에 남는다. 버전·차량·배정은 질량을 더하지 않는다. 검사 통과/최종 버전/도착/적재/용량 gate의 실행은 T7–T9 서비스 책임이다.

## 공통 전이 인터페이스

```python
build_fixture(seed: int) -> PlanSeed                         # T6 구현
advance_model(model: SimulationModel, target_ms: Milliseconds) -> TransitionResult  # T7
ready_transfers(model: SimulationModel) -> tuple[EntityId, ...]                    # T8
transport_transition(model: SimulationModel, transfer_id: EntityId,
                     at_ms: Milliseconds) -> TransitionResult                    # T8
fulfillment_transition(model: SimulationModel, entity_id: EntityId,
                       at_ms: Milliseconds) -> TransitionResult                  # T9
next_boundary(model: SimulationModel) -> Milliseconds | None  # T8/T9 각각
```

`PlanSeed`는 nullable due_at을 갖는 `OrderPlan`, 예정 행, `ResourceSpec`을 담는 순수 입력이다. persisted `OperationsOrder.due_at`은 필수다. T10은 NORMAL을 메모리에서 실행하여 due/duration을 확정한 다음 새 run을 한 transaction으로 저장한다. fixture를 구성할 때 run_id를 함께 결정하고 모든 행에 동일 값을 넣는다.

`SimulationModel`은 유일하게 의도적으로 mutable한 엔진 작업 상태다. 필드는 run, 그리고 orders/work_orders/lots/materials/material_versions/lineage_edges/allocations/processes/transfers/inspections/shipments/shipment_materials/mass_movements/events/resources의 `dict[EntityId, Row]`다. `from_snapshot(snapshot, resources=())`로 만들고 `clone()`으로 독립 컬렉션을 확보한다. 행은 불변이므로 clone 사이 공유해도 안전하다. 값 변경 시 새 행으로 교체한다.

각 전이 함수는 **입력 model을 수정하지 않고** clone을 반환한다. 반환값 `TransitionResult(model, delta)`에서 `TransitionDelta`는 변경 행의 immutable tuple upsert와 순서 있는 이벤트다. 삭제 목록은 없다. 소비/종료는 행 갱신이다. 중복 적용/부적합 전이는 도메인 모듈이 명시적으로 거부하거나 빈 delta로 처리하고 그 정책을 테스트한다. 이벤트 sequence와 결정적 경계 순서는 T7이 배정하고, 실제 recorded_at/SQL transaction은 writer가 배정한다. delta와 반환 model이 같은 전이를 나타내야 한다.

`ProcessExecution`은 route_step_id, source_step_id, step_ordinal, predecessor_id, equipment_id, ready_at_ms, positive planned_duration_ms, 시간 창, 입출력 form, addition/loss, split_count를 갖는다. `source_step_id`는 `hr-04`, `cs-charge` 등 T2/T4의 원본/합성 ID를 그대로 받는다. RUNNING/COMPLETED는 start/end를 요구한다. `ResourceSpec`은 위치·폼/강종·폭·kg 호환성, 예약·중단·reserve 상태를 포함한다. T1에는 scheduler 구현이 없다.

## 명령과 스냅샷

`SimulationCommand`는 play/pause/reset/step/speed/scenario 중 하나와 선택적인 run_id/expected_revision/command_id를 받는다. step의 steps 누락은 기존 API 기본 1을 의미한다. 다른 action의 필드 혼입을 거부한다. 새 UI는 run_id/command_id를 항상 보내고 reset/scenario에 expected_revision을 보낸다. body 없는 기존 호출을 위해 경계에서는 metadata를 optional로 유지한다. command_id 중복·payload digest·revision conflict와 최대 2회 재시도 정책은 T10/T12가 구현한다.

`OperationsSnapshot`은 run, orders, 기존 이름을 유지한 lots/shipments 및 새 업무 컬렉션, mass_balance/forecast를 담는다. Python의 최종 검증과 TS 파싱은 같은 run/존재하는 참조/현재 version/분할/질량 규칙을 검사한다. 모든 행은 해당 snapshot의 현재 run 소속이다. legacy 조회는 별도 보존 projection이며 새 현재 snapshot에 섞지 않는다.

## 검증 명령

```sh
cd backend && .venv/bin/python -m pytest tests/operations/test_contracts.py -q
npm test -- src/operations/contracts.test.ts
npm run typecheck
```

첫 명령 이후 root로 돌아와 npm 명령을 실행한다. T01 증거는 실행 폴더의 T01-contracts.log/T01-invalid.json/T01-done.md에 있다. 직접 JSON 파싱 결과는 Python과 Node/Zod 양쪽에서 저장한다. Biome LSP는 사용 불가이며 설치하지 않았고 TypeScript compiler로 검증한다.
