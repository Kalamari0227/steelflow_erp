# steelflow-uniform-fidelity-factory - Work Plan

## TL;DR (For humans)
**Who this is for and what changes for them:** 철강 영업·생산·물류 사용자와 강의 관객이 주문·소재를 지정하여 입고에서 생산, 출하, 고객 하역까지 같은 미니어처 공장 안에서 따라갑니다. 어느 제품·공정을 열어도 동일한 정밀도와 작동 기준을 제공합니다.

**What you'll get:** 전체 20개 제품 경로, 실제 대기·복귀하는 차량과 철송·항만, 설비 내부와 소재 변형, 계보·품질·재고·출하가 연결된 로컬 웹 앱입니다. 무료 제작 도구와 직접 만든 자산, 검증된 출처 관리, 전체 기능의 화면·동작·성능 증거를 포함합니다.

**Why this approach:** 하나의 업무 시계와 소재 보관 관계를 모든 장비·화면이 공유해야, 공장의 움직임과 ERP 기록이 일치합니다. 모든 구역의 상세 원본을 제작하고 화면 거리만으로 표시 비용을 조절합니다.

**What it will NOT do:** 대표 공정만 완성해 전체 완료로 부르지 않습니다. 실제 회사 데이터나 공장을 제어하지 않고, 유료 서비스·외부 게시·기존 이력 삭제를 수행하지 않습니다.

**Effort:** XL
**Risk:** High — 정밀 자산 제작, 교통·생산 동시 실행, 기존 이력 보존, 전수 시각 검증이 함께 필요합니다.
**Decisions to sanity-check:** 주문 100건·활성 소재 1,000개·운송 장비 100대, 무료 Blender와 직접 제작, 전체 동일 품질. 10월 30일은 진행 시연이며 최종 완성일은 전체 작업량으로 산정합니다. 모든 값은 합성 데이터입니다.

Your next move: 고정밀 검토가 승인된 동일 계획으로 별도 구현 작업을 시작합니다. 이 문서 작성·검토 자체는 구현 완료가 아닙니다.

---

> TL;DR (machine): XL / High; 7waves,49implementationtodos,4finalverifiers;full20routes+receiving/ROAD/RAIL/SEA/customer,uniform-fidelity;100orders/1000materials/100fleet;categories={"unspecified-high": 16, "deep-high": 12, "visual-engineering": 19, "ultrabrain": 1, "writing": 1}.

## Scope
### Affected user and ideal state
사용자가 2026-10-25에 전체 계획 작성과 고정밀 이중 검토를 승인했다. 이 계획의 작성은 제품 구현·설치 완료를 뜻하지 않는다. 기존 steelflow-visual-operations-erp 계획과 완료 기록을 덮어쓰지 않는다. 새 계획은 기존 통합 ERP를 기반으로 전 구역의 미니어처 품질과 실제 운영 동작을 확장한다.

대상 사용자:
- 철강 영업·생산·물류 관찰자: 현재 기본 도형과 제한된 운송을 해석한다. 완료 후 주문과 소재를 지정하여 입고에서 고객 하역까지 같은 공장에서 관찰한다.
- 시연자와 2026-10-30 강의 관객: 현재 대표 경로 중심의 화면을 본다. 완료 후 어느 제품·공정을 선택해도 같은 수준의 설명 가능한 동작과 품질을 본다. 10월 30일은 진행 시연이며 최종 완성 기한으로 강제하지 않는다.
- 후속 구현자·자산 제작자: 현재 절차적 메시와 분리된 정의를 해석한다. 완료 후 하나의 공간·자산·동작·업무 계약과 전수 검증 목록을 사용한다.

| ID | 이상 상태 | 이유 |
| --- | --- | --- |
| IS-01 | 밝은 미니어처 조감도에서 원료 입고·생산·창고·도로 출하·철송·항만·고객 하역의 공간 관계를 읽는다. | 사용자가 요구한 전체 ERP 관찰의 출발점이다. |
| IS-02 | 기존 20개 제품, 24개 구역, 모든 기존·추가 설비에 같은 외관·내부·작동·인계·검증 기준을 적용한다. | 대표 공정만 정교하고 다른 공정은 placeholder인 결과를 금지한다. |
| IS-03 | 같은 주문·소재·run·시각을 유지한 채 조감도→구역→설비 내부→물류→조감도로 이동한다. | 제조공정 전시 화면이 별도로 분리되는 기존 오해를 반복하지 않는다. |
| IS-04 | 소재를 받침·롤러·훅·차량·설비가 실제로 지지하고, 인계 시 보관 주체가 원자적으로 바뀐다. | 순간이동, 공중 부유, 적재물 중복을 제거한다. |
| IS-05 | 운영 차량·크레인·기관차·화차·선박은 작업 유무와 무관하게 존재하고, 대기·접근·작업·복귀를 한다. | 작업 종료 후 사라지는 차량으로는 공장의 흐름을 설명할 수 없다. |
| IS-06 | 차선·회전·대기장·교차로·철도 블록·상하차 슬롯이 연결되고 자원 점유가 충돌과 교착을 방지한다. | 도로 모양만 있는 지도에서 실제 운영 네트워크로 바뀐다. |
| IS-07 | 원료 입고, 외부 구입 슬래브/코일 등의 후공정 투입, 중간재 직접 판매를 사실대로 표시한다. | 수행하지 않은 상류 공정을 완료 이력으로 만들어서는 안 된다. |
| IS-08 | SLAB/BLOOM/BILLET, HR/CR, GI/GA/HGI/EG, 전기강판, STS, Ti의 서로 다른 공정·제품 형태를 보존한다. | 모든 소재를 같은 코일 공정으로 처리하지 않는다. |
| IS-09 | 분할·합류/배치·첨가·손실과 주문 배정·출하 잔량을 설명하며, 물리적 소재 계보와 질량을 보존한다. | 원료와 제품의 업무 이력을 끝까지 연결한다. |
| IS-10 | NORMAL/DELAY/RECOVERY가 같은 공장·소재·차량에 원인→대기→납기 영향→복구 동작으로 드러난다. | 시나리오마다 별도 애니메이션 영상을 재생하는 결과를 금지한다. |
| IS-11 | M4 Max에서 주문100·활성소재1000·운송장비100의 합의 규모를 실제 검증하고, 확대 구역 외에서도 업무 상태가 계속 진행된다. | 규모와 동일 품질을 동시에 검증한다. |
| IS-12 | 정지·배속·초기화·연결 오류·재연결·재시작에 상태와 동작이 일치하며, 2D와 AI 비활성 모드가 유지된다. | 로컬 데모 신뢰성과 접근성을 보존한다. |
| IS-13 | 기존 합성 DB·사건 이력·보존 데모를 손상하지 않고 새 계약과 공간 버전으로 전환한다. | 현재 작업과 완료 증거를 보호한다. |
| IS-14 | 모든 제품·설비·물류 구간의 완료를 실제 화면·연속 동작·API·저장 이력과 독립 검토로 증명한다. | 자기 보고, screenshot 저장만으로 완료를 주장하지 않는다. |

| GAP | 현재 차이와 이유 | 연결 IS | 계획 책임 영역 |
| --- | --- | --- | --- |
| GAP-01 | 기본 도형 중심이며 편집 가능한 정밀 GLB/Blend 자산이 없다. | 01,02 | C1,C4 |
| GAP-02 | 40종 설비 중 모델 자체의 가동부가 정적인 종류가 있고 미지원 kind는 일반 롤러로 대체된다. | 02,08 | C4 |
| GAP-03 | 운영 차량은 활성 작업 동안만 생성되어 빈차 접근·귀환·차고 대기가 없다. | 05 | C3,C4 |
| GAP-04 | 도로를 이송 좌표열에서 그리며 독립 차선·교차로·철도 블록 계약이 없다. | 01,06 | C1,C3 |
| GAP-05 | 일반 기관차·화차·편성·입환이 없고 출하는 특정 트럭→선박 조합에 고정된다. | 05,06,07 | C2,C3,C4 |
| GAP-06 | 입고는 시간0에 재고가 이미 존재하며 구입재 후공정 입고가 없다. | 04,07,09 | C2,C3 |
| GAP-07 | 정적 배경 크레인과 동적 작업 훅이 별도 생성되어 동일 운영 개체로 연결되지 않는다. | 02,04,05 | C1,C3,C4 |
| GAP-08 | 소재는 생산 lot/주문에 필수 연결되고 분할은 두 위치의 1→2로 제한된다. | 07,09 | C2 |
| GAP-09 | 기존 카메라·선택은 재사용 가능하지만 길게 연결된 실제 공장 내부와 절개 자산은 없다. | 02,03 | C4,C5 |
| GAP-10 | 전체 상태 반복 전송과 매 프레임 scene 순회/경계/JSON 진단이 규모 비용을 키운다. | 11,12 | C2,C5,C6 |
| GAP-11 | 자산·이동부품·상태 바인딩·외부 다운로드·누락 texture 전수 검증이 없다. | 02,14 | C4,C6 |
| GAP-12 | 현재 시각 검사는 일부 구역·24개 활성소재 중심으로 전수 동일 품질을 증명하지 못한다. | 02,11,14 | C6 |
| GAP-13 | preview QA 포트8002/4175가 보존 데모와 겹치며 과거 demo scenario 기대값도 최신 기록과 다르다. | 13,14 | C6 |
| GAP-14 | 좌표가 scene 단위이고 새 차량·공장 크기와의 축척·시간 연결 계약이 없다. | 04,06 | C1,C2,C3 |
| GAP-15 | 로컬 Blender가 없으며 모델의 출처·라이선스·재현 가능한 제작 경로가 없다. | 02,13,14 | C4,C6 |


### Must have
- 전체20제품: slab,bloom,billet,hr,plate,wire,cr,gi,ga,hgi,eg,go,ngo,sts-hr,sts-cr,sts-plate,ti-hr,ti-cr,ti-sheet,ti-plate. 기존24구역/158설비/40kind/31hall은 현재 분모이며 새 물류 설비도 빠짐없이 포함한다.
- 무료 Blender4.5 LTS Apple Silicon, 직접 제작 모델·procedural textures를 기본으로 한다. 외부 무료 자산은 검증된 라이선스와 provenance manifest가 있어야 하며 기본 실행에는 필요하지 않다.
- 주문100/활성소재1000/이동장비100, 고정 생산 설비와 크레인은 별도 집계. 기계적으로 고정된 본체는 고정하고 작업 부품·소재·차량은 각자의 업무 상태에 반응한다.
- 10월30일은 진행 시연일이다. 전체 완료는 모든 작업과 F1–F4 기준 충족 후에만 판단한다. 제작 순서·병렬 묶음은 최종 품질 범위를 줄이지 않는다.

제품 커버리지(현재 코드에서 확인한 경로이며 제조 사실성은 공정별 공개 근거와 설비/소재 접점 검증으로 보완):

| 제품 | 필수 제조 연결 |
| --- | --- |
| slab / bloom / billet | 원료 입고→제선→전로/정련→각 연주 형상→절단/냉각→반제품 출하 |
| hr | 슬래브→가열→조압연→사상압연→냉각→권취→정정→제품 출하 또는 후공정 소재 |
| plate | 슬래브→가열/압연→냉각→절단→열처리→교정 |
| wire | 블룸→빌렛 압연/정정→선재 가열/압연→권취/냉각 |
| cr | HR→풀기/산세→냉간압연→청정→소둔→조질→도유/권취 |
| gi / ga | CR→전처리/소둔→용융도금, GA는 합금화 포함→후처리/권취 |
| hgi | HR→열연 소재 도금 경로; 냉간압연 경유를 강제하지 않음 |
| eg | CR→전처리→전기도금→표면처리→권취 |
| go / ngo | 방향성/무방향성별 압연·소둔·절연코팅·권취, GO 추가 공정 보존 |
| sts-hr / sts-cr / sts-plate | 스크랩 입고→EAF/AOD→연주→제품별 열연/산세/냉연/후판 처리 |
| ti-hr / ti-cr / ti-sheet / ti-plate | 외부 조달 Ti 잉곳 입고→단조→제품별 압연·열처리·산세·정정/절단 |

공간·물류 범위:
- 원료선/벌크 하역, 육상 원료 입고·검수·계량·하역·원료장·컨베이어, 스크랩 및 구입 반제품/코일 입고.
- 모든 기존 생산 구역과 내부 이송·크레인·롤러·용선/래들차, 품질/격리/재검·포장·제품 창고.
- 트럭 배차·대기·상차·결박/계량·출문·고객 하역; 철도 편성·입환·화차 적재·블록 이동·목적지 하역; 제품 부두 대기·선적·해상 운송·양하/인수.
- 차량/크레인/기관차/화차/선박, 각각의 작업부품, 모든 소재의 상태 기반 동작과 독립 선택.


### 결정된 아키텍처와 소유권
경로는 작업 루트 /Users/ethanlee/Desktop/ERP 기준이다. 아래 (new)는 새 파일/계약이며 현재 존재한다고 주장하지 않는다. 현행 기반은 package.json, backend/pyproject.toml, backend/app/operations, src/operations이다. 버전 업그레이드나 게임엔진 교체를 요구하지 않는다.

1. **공간:** shared/factory-world-v2.json(new), schema(new), asset/motion/recipe/coverage bundle의 SHA256을 run에 고정한다. 단위 meter/Y-up/+X전방, 소재 치수 mm, 질량 integer kg, 시뮬레이션 ms, 업무 UTC=epoch(2026-10-30T00:00Z)+sim_ms×60. 1x/2x/4x는 wall→sim에 한 번만 적용한다. motion velocity는 m/sim-second로 명시한 합성 값이며 실제 운송속도나 생산시간이라고 표현하지 않는다. v1 scene 좌표는 그대로 보존한다.
2. **부지:** north receiving/raw yard, central carbon upstream→casting→rolling/finishing, south STS/Ti와제품출하, east 원료/제품 분리부두. 고객거점은외곽연결구역이다. 가상부지의설비치수·footprint·운송clearance를표준단위로설계하고원거리운송은연결항로/외부구간으로표시한다. 건물등간격격자나도로가없는직선이동금지. 레이아웃의목표는실존제철소측량복제가아닌일관된가상공간이다.
3. **시간/실체:** 서버가경계이벤트를결정한다. 작업이없어도fleet/고정crane/stock개체는존재한다. frontend의body는(run_id,entity_type,entity_id,bundle_hash)로매핑하고LOD/절개/camera는identity나업무시계를바꾸지않는다. scene환경에는운영기구를장식으로중복생성하지않는다.
4. **부착:** material의현재보관주체는하나의Attachment(kind=slot/equipment/hook/vehicle/railcar/ship/customer,owner_id,socket_id)다. location/current_transfer는읽기projection이다. acquire/release와stock/원장/event가한transaction에반영되고socket/worldtransform거리와support/인계불연속은≤0.01m. geometry가바뀌어도지지접점이기준이며중심점일치만검사하지않는다.
5. **재고/계보:** Material은own grade/form/dimensions/origin_stock_lot과nullable production_lot을갖는다. Allocation이order/work_order를연결하고한물리소재는동시에한주문에배정한다. 여러주문을한heat로생산하면batch출력을주문별물리단위로분할후배정한다. ProcessBatch와VersionEdge는N:M,투입/출력/첨가/부산물/손실kg를명시한다. 폐기/기체/슬래그등합성손실/부산물은원장으로보존하며광석kg=철강kg라는숨은가정을하지않는다. 단위kg의물질수지만검증하고실제수율/화학반응의공학해석은표방하지않는다.
6. **전체 질량:** opening_stock+external_receipts+external_additions=active_materials(including customer stock)+byproduct_stock+irrecoverable_loss. stock에서소비한첨가물은external_additions에재합산하지않는다. 원장원천ID가unique여야한다. rootversion개수로opening을추정하지않는다. batch각각 inputs+stock_additions+external_additions=outputs+byproducts+loss;출력잔여kg는sorted outputID순배분.
7. **운송:** FleetAsset/VehicleState/TransportJob/MovementSegment/ResourceReservation/Consist/ShipmentLeg. FIFO(ready_at_ms,job_id),동시시각release/completion→ready→dispatch. 안전정차slot까지필요자원을atomic예약하고미점유partialhold를남기지않는다. route선택deterministicDijkstra(이동+기예약대기,tie segmentID). 차로·교차로·도크·railblock·berth는시간interval로점유한다. 1h sim 미래window안계획불가면structural_blocked와충돌자원을표시,끝없는loop금지. 이window는run전체duration상한이아니다.
8. **교통 기구:** 차량은가감속/turn radius/length/load envelope를사용한다. railconsist는순서·coupler거리·후진·분기lock을소유하고tail이빠져야block해제. 사고강체물리엔진은필요하지않다. staticclearance와서버예약+trajectory swept검사로운영중관통을검증한다. 초기충돌배치는실행전에거절한다.
9. **운영 자산:** 모든40kind 및semanticvariant를registry로관리한다. 19/20/21/26/27/28/29가원료·제강/연주,열연·후판·선재,냉연·도금·전기강판,STS,Ti,운송,건축·물류자산을모두소유한다. 공용mesh를재사용해도variant별기구/동작/접점/출처및개별배치검사는필수다. blade/roll/coil/strip/bridge/trolley/hoist/bogie/coupler/roof등의part ID가명시된다.
10. **화면:** 조감도→공정→설비내부는동일scene,원거리LOD와비동기자산캐시는허용하지만특정공정을저정밀최종품으로남길수없다. 선택은entity_type/entity_id와run/contractversion,관계context를갖고빈차량·입고stock·배치·leg도패널이있다. legacyURL은compatparser로해석하고공간버전변경은camera만초기화한다.

### API·DB 이관 계약
현재 GET /api/v1/world가현재상태bootstrap의권위이며별도원격store를만들지않는다. schema_version3 및fixture factory-v2를새run에사용하고기존schema2/erp-v1은immutable reader로보존한다. migration위치는backend/migrations/versions/ops_factory_v3.py(new),이전head는ops_20261024_unified다. 새표는factory_v3_ prefix를사용해기존CHECK/trigger/원장보존을명확히한다. 기존run→layout/catalog/assets/motion/fixture/scenario version mapping을고정번들로보관하고v2: location namespace로전역Location충돌을피한다.

| API/표현 | 결정 |
| --- | --- |
| health | 기존응답호환; QA실행에서만attempt_id와DBfingerprint 제공. 비밀경로는일반UI에표시하지않음. |
| world | run/bundle,orders/materials/versions/lineage/batches/stock/receipts/processes/fleet/jobs/segments/reservations/attachments/consists/shipments/legs/quality/kpis. inactive는삭제하지않음. |
| world/delta (new) | run_id/after_revision; from/to_revision,bundlehash,typed upserts,eventrange. 256revision ring에서gap이면409 resync_required. fullbootstrap fallback. |
| orders/kpis/shipments/events/scenarios | 같은writer/projection. events는run/sequence로읽으며기존경로유지. 전체history를매250ms재전송하지않아도된다. |
| materials/{id} | provenance,nullableorder/productionlot,stock/batch/lineage/currentcustody·job/leg. 구입재를가짜order로위장하지않음. |
| coils/{id} | 실제coil form만;비코일404;stockcoil의ordernullable계약을schema3에명시. |
| simulation reset/play/pause/step/speed, scenario activate | 기존명령의idempotency/run/revision보호를유지. reset=새run/이력보존,객체선택은업무명령이아님. |
| archive run read (new GET /api/v1/runs/{id}/world) | 고정old bundle에맞는read-onlyWorld. unsupportedversion명시오류;과거run재개를묵시제공하지않음. |
| production/journey legacy | 동일활성run의호환읽기projection;별도clock/상태재생성금지. 기존deprecated globalcommandalias의문서를갱신. |

새계약consumer인모든API/TSvalidator/KPI/검색/상세/URL을함께수정한다. legacy완료run을현재v3공간으로재해석하지않으며실행중이전run은기존보존서버에서유지한다. 복귀는보존DB+oldbundle전환으로하며새event삭제downgrade가아니다. 실제사용자DB이관은새합성복사본검증결과와분리한다.

### 데이터·시나리오·규모 정책
- demo와scale는동일engine의별도합성fixtureprofile. 모든제품20종에서슬래브/블룸/빌렛,중간제품판매,후공정구입입력,분할/배치,운송각모드와품질hold를명시cover한다. Ti잉곳이전은외부조달경계이며허구의상류이력을만들지않는다.
- 60제품×scenario조합을무결성검증하고각제품에장애/대기/회복fixture를명시한다. 대체설비없으면수리후재개도recovery이며납기이득을만들어내지않는다. DELAY/RECOVERY의동일원인/seed와forecast/실제결과를비교한다.
- scale100fleet 구성은truck32/carrier24/forklift16/torpedo4/ladle4/locomotive4/railcar12/ship4다. carrier24는slab12/coil12. 고정crane·unloader·stacker와모든생산기구는별도다. 선박/철도대기중에도개체는존재한다.
- scale의측정창은사전생성한100orders,1000active physicalmaterial,100fleet를유지한다. active는소비된parent/version이아닌현재물리단위이며고객재고도포함하지만측정내내≥40fleet이실제로이동하고≥10서로다른생산설비가가동되어야한다. 분할/합류로분모가변하는별도정확성fixture와분리하여미리분할이끝난stock+1:1공정의결정적steadywindow를쓴다. dummy화면장식/engine정지로숫자만맞추지않는다. scale run duration≥10,800,000sim_ms로soak동안자동종료하지않는다.
- 기본샘플값/품질/수율/속도/납기는모두합성이며실제회사data/실측운영값처럼표시하지않는다.

### 동일 정밀도 완료 규약
모든kind/variant/배치/route/leg가외형(실루엣/지지구조/재질/주요기구),동작(정상/대기/장애/정지/재개),인계(정확한접점/custody),업무(선택/원인/주문/계보),검증(원본API+실제node+픽셀+연속영상)의동일rubric를통과해야한다. 40개모델만제작했거나158개기존배치만맞았다는이유로새물류설비를면제하지않는다. 골재입자는시각효과일수있으나raw lot의이동/수량/소유권은실제엔티티다. 실제연속체유동/열역학/FEM은이업무시각화의검증대상이아니다.

### Must NOT have (guardrails, anti-slop, scope boundaries)
- 대표공정완성으로전체완료선언,미지원설비genericrollerfallback,정적운영장비/배경PNG로시안복제,별도공정전시clock.
- 실제ERP·credential·회사data접근,실물시스템명령,외부게시/메시지/구매/유료AI. core에APIkey/인터넷/Docker필수화.
- 기존DB/event/Location/원본자산/보존demo덮어쓰기,port충돌프로세스kill,데모서버에QAreset/step,기본dist덮어쓰기.
- 성능통과를위해합의분모/전체품질기준/검사assertion을줄이거나오류·실패·skip을숨기기.
- 원래20제품밖의제품군,Ti상류공급망,임의과거time-scrub,실제산업제어/공학안전검증을요청없이추가.

## Verification strategy
> Zero human intervention - all verification is agent-executed.
- 결정: 계약·원장·예약/스케줄러는TDD. 자산·장면은tests-after+실제기구/화면/영상검증. 구현과검사는각todo의일부다.
- 모든명령은작업루트 /Users/ethanlee/Desktop/ERP에서실행한다. backend/.venv/bin/python pytest는backend pyproject를명시검출하며필요시 -c backend/pyproject.toml로고정한다. 새test파일/runner는해당todo가생성하는deliverable이다.
- evidence root는.omo/evidence/uniform-fidelity/<attempt-id>/로T1이생성한다. 아래E_N은그root/task-NN/이다. 재실행은새attempt로보존하고실패로그를덮어쓰지않는다. task명령의--evidence경로는확정attempt로치환한다.
- tools/qa/run.mjs(new T1)의browser subcommand는 --spec, --grep, --evidence를필수검증하고Playwright를retries0/workers1/headed실제Chrome으로실행한다. 구문/파일/grep무매치도실패하며단순자기보고JSON으로성공하지않는다. 실제명령·env허용목록·OS/arch/browser/GPU·sourcehash·DB/PID/port·exitcode·duration·assertion수·trace/video/imagehash를저장한다. screenshot/png저장만으로시각PASS를만들지않는다.
- protected8000/4173/8002/4175는denylist. 기본QA8003/4176이점유면오류후unusedpair를할당하고receipt에저장;다른프로세스종료금지. health attempt/DBfingerprint와생성PID가일치해야POST가능. fixtures/build는attempt경로만쓰고검증중canonicalsource자동재생성금지.
- 정상 happy는실제기능성공, failure는의도한오염/오류가정확하게거절되고state불변임을assert하는별도case다. 파일자산오염은복사본만사용. 예상오류와예상외오류를요청ID로구분하며blanketconsoleignore금지.
- 단위기본: npm run typecheck; npm test. backend기본: backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations -q. build: npm run build -- --outDir <attempt>/dist. full browser는runner가최종동결source로productionpreview를기동한다.
- 실제픽셀/영상검수는read-only검토자와구현자를분리한다. 매kind/variant3각도,각구역overview/detail/cutaway,각placement의접점/clearance,20제품연속영상과60상태검사를registry행에연결. 구현자self-report만으로완료금지. 시각결함은원래소유todo로수정후재검수.
- 정상연속제품영상에는Step API0,별도경계/invariant검사에만Step허용. 같은시각·seed·bundle·run/revision으로API/sceneMatrix/part/픽셀을연결한다.
- 성능: 실제M4MaxChrome1920×1080/DPR1,30swarmup,overview/detail/follow×1x/2x/4x각60s,30minsoak,20회scope/reset반복. 분모100/1000/100과clock/업무진행을매sample기록. p95frameinterval≤25ms,p99≤50ms,선택/상세진입p95≤500ms,coldhealth≤60s,scale tickp95≤100ms. 60fps는목표이며측정전보장아님. RAF/useFrame과GPU/presented frame측정을혼동하지않는다. warm후20회반복geometry/texture누적증가0,정지60s불필요render0. 모든임계값은승인된설계목표이며실패시최적화하고완화하지않는다.
- baseline과최종증거의소스·기기·분모를구분. 이전204/179/8이나389/193/59/9를이번결과에합산하지않는다. 최종전수실행에서실패/skip/flaky0이어야완료;불가환경은INCONCLUSIVE이며통과로대체하지않는다.

## Execution strategy
### Parallel execution waves
각wave7개todo,총7wave49개다. wave는분업/통합순서이지완료범위축소가아니다. 같은wave의depends-on도반드시따르며동일파일을동시에수정하지않는다. 현재4concurrency slot제약으로root+최대3workers만활성화한다. 작업별owner는아래What/References의신규모듈·해당test이며공유contracts/manifest에대한변경은해당원소유자(T3/T4/T5/T6)에게통합요청한다. 다른사람의수정이나기존데모를revert하지않는다.

- Wave 1: 보존·커버리지·공통계약·미술기준 — T01–T07.
- Wave 2: 전체배치·입고/계보·영속장비·자산도구 — T08–T14.
- Wave 3: 교통/작업스케줄러·전공정실행·핵심자산 — T15–T21.
- Wave 4: 도로/철송/항만/이행·STS/Ti/운송자산 — T22–T28.
- Wave 5: 전체공장통합·기구/인계·조감/상세ERP — T29–T35.
- Wave 6: 시나리오·규모·동기화·최적화·복구 — T36–T42.
- Wave 7: 전수검증·보존이관·시연패키지 — T43–T49.

Critical dependency spine: 1→2→3/4→5/6→8/9/10/11→15→16→17/18→22/23/24→25→30/31/32/33→34/35→36/37/38/39→40/41/42→43/44/45/46/47/48→49→F1–F4. 자산제작12→19/20/21→26/27/28→29는서버와병렬이지만30통합전완료해야한다. 세부DAG가spine보다우선한다.

Effort XL. 10월30일진행시연은그시점의검증된상태와미완료목록을명확히보여주고,이를전체완료라고부르지않는다. 작업량은7자산군·40+kind/variant·기존158+추가placement·20route/신규물류,전체QA를분모로산정한다. T12–21에서실제제작/검수소요를기록해남은family와criticalpath의최종일정범위를갱신한다. 사람수/비용/완료일을근거없이가정하지않으며범위/품질축소로날짜를맞추지않는다.

### Dependency matrix
| Todo | Depends on | Blocks | Can parallelize with |
| --- | --- | --- | --- |
| 1 | none | 2,14 | none; ownership 충돌시직렬 |
| 2 | 1 | 3,4,7,14,40 | none; ownership 충돌시직렬 |
| 3 | 2 | 4,5,6,8 | none; ownership 충돌시직렬 |
| 4 | 2,3 | 5,6,7,12,13 | none; ownership 충돌시직렬 |
| 5 | 3,4 | 6,9,10,11,35,38,48 | 7; ownership 충돌시직렬 |
| 6 | 3,4,5 | 11,13,14,15,18,31 | 7; ownership 충돌시직렬 |
| 7 | 2,4 | 8,12,13,19,20,21,28,45 | 5,6; ownership 충돌시직렬 |
| 8 | 3,7 | 9,11,15,19,20,21,28,29,30 | 12,13,14; ownership 충돌시직렬 |
| 9 | 5,8 | 10,17,18,35 | 11,12,13,14; ownership 충돌시직렬 |
| 10 | 5,9 | 17,18,25,48 | 11,12,13,14; ownership 충돌시직렬 |
| 11 | 5,6,8 | 15,16,38 | 9,10,12,13,14; ownership 충돌시직렬 |
| 12 | 4,7 | 19,20,21,26,27,28,29,41 | 8,9,10,11,13,14; ownership 충돌시직렬 |
| 13 | 4,6,7 | 14,30,31,34,39 | 8,9,10,11,12; ownership 충돌시직렬 |
| 14 | 1,2,6,13 | 19,20,21,26,27,28,29 | 8,9,10,11,12; ownership 충돌시직렬 |
| 15 | 6,8,11 | 16,18,22,23,24,37 | 19,20,21; ownership 충돌시직렬 |
| 16 | 11,15 | 17,22,23,24,32,37,42 | 18,19,20,21; ownership 충돌시직렬 |
| 17 | 9,10,16 | 22,23,24,32 | 18,19,20,21; ownership 충돌시직렬 |
| 18 | 6,9,10,15 | 22,23,24,25,31,36,42 | 16,17,19,20,21; ownership 충돌시직렬 |
| 19 | 7,8,12,14 | 26,29,30,41 | 15,16,17,18,20,21; ownership 충돌시직렬 |
| 20 | 7,8,12,14 | 26,27,29,30,41 | 15,16,17,18,19,21; ownership 충돌시직렬 |
| 21 | 7,8,12,14 | 26,27,29,30,41 | 15,16,17,18,19,20; ownership 충돌시직렬 |
| 22 | 15,16,17,18 | 25,32,33,44 | 23,24,26,27,28; ownership 충돌시직렬 |
| 23 | 15,16,17,18 | 25,32,33,44 | 22,24,26,27,28; ownership 충돌시직렬 |
| 24 | 15,16,17,18 | 25,32,33,44 | 22,23,26,27,28; ownership 충돌시직렬 |
| 25 | 10,18,22,23,24 | 32,35,36,37,40,42,44 | 26,27,28; ownership 충돌시직렬 |
| 26 | 19,20,21,12,14 | 29,30,41 | 22,23,24,25,27,28; ownership 충돌시직렬 |
| 27 | 20,21,12,14 | 29,30,41 | 22,23,24,25,26,28; ownership 충돌시직렬 |
| 28 | 7,8,12,14 | 29,30,32,33,41 | 22,23,24,25,26,27; ownership 충돌시직렬 |
| 29 | 8,12,14,19,20,21,26,27,28 | 30,40,41 | none; ownership 충돌시직렬 |
| 30 | 8,13,19,20,21,26,27,28,29 | 31,32,33,34,39,45 | none; ownership 충돌시직렬 |
| 31 | 6,13,18,30 | 32,34,39,40,45 | none; ownership 충돌시직렬 |
| 32 | 16,17,22,23,24,25,28,30,31 | 33,40,44,45 | none; ownership 충돌시직렬 |
| 33 | 22,23,24,28,30,32 | 34,39,40,44,45 | none; ownership 충돌시직렬 |
| 34 | 13,30,31,33 | 35,40,45,47 | none; ownership 충돌시직렬 |
| 35 | 5,9,25,34 | 36,38,40,47 | none; ownership 충돌시직렬 |
| 36 | 18,25,35 | 37,40,43 | none; ownership 충돌시직렬 |
| 37 | 15,16,25,36 | 38,46 | none; ownership 충돌시직렬 |
| 38 | 5,11,35,37 | 39,40,42,46,48 | none; ownership 충돌시직렬 |
| 39 | 13,30,31,33,38 | 41,42,46 | 40; ownership 충돌시직렬 |
| 40 | 2,25,29,31,32,33,34,35,36,38 | 41,43,44,45,48 | 39,42; ownership 충돌시직렬 |
| 41 | 12,19,20,21,26,27,28,29,39,40 | 43,45,46,47,48 | 42; ownership 충돌시직렬 |
| 42 | 16,18,25,38,39 | 43,44,46,47,48 | 40,41; ownership 충돌시직렬 |
| 43 | 36,40,41,42 | 45,46,49 | 44,47,48; ownership 충돌시직렬 |
| 44 | 22,23,24,25,32,33,40,42 | 45,46,49 | 43,47,48; ownership 충돌시직렬 |
| 45 | 7,30,31,32,33,34,40,41,43,44 | 46,49 | 47,48; ownership 충돌시직렬 |
| 46 | 37,38,39,41,42,43,44,45 | 49 | 47,48; ownership 충돌시직렬 |
| 47 | 34,35,41,42 | 49 | 43,44,45,46,48; ownership 충돌시직렬 |
| 48 | 5,10,38,40,41,42 | 49 | 43,44,45,46,47; ownership 충돌시직렬 |
| 49 | 43,44,45,46,47,48 | F1–F4 | none; ownership 충돌시직렬 |

## Todos
> Implementation + Test = ONE todo. Every row below includes exact evidence and happy/failure QA.
<!-- APPEND TASK BATCHES BELOW THIS LINE WITH edit/apply_patch - never rewrite the headers above. -->

- [ ] 1. 기존 작업 보존과 격리 QA 실행기
  Recommended task executor category: unspecified-high — 여러기존모듈의정해진연결.
  What to do / Ownership: 신규 tools/qa/run.mjs와 tests/factory-harness.spec.ts를 만들고 Playwright 모든 포트/preview 내부 문자열을 한 설정으로 통일한다. 기본 QA8003/4176은 비점유 확인 후 사용하고 보호8000/4173/8002/4175는 거절한다. health에 QA일 때만 attempt_id/db fingerprint를 추가하고 mutation helper가 실행 소유권·DB·PID를 확인한다. 실행 전 소스와 보존 dist/snapshot의 hash를 기록한다. 기존 NO_BENEFIT 기대는 실제 현 엔진 결과와 대조해 최신 계약 근거로 수정하며 결과를 억지로 맞추지 않는다.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-13.
  Parallelization: Wave 1 | Blocked by: none | Blocks: 2,14.
  References: playwright.config.ts:15; tests/helpers/operations.ts:12; docs/TEST_RESULTS.md:3; backend/app/main.py; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 보호 포트/타 서버/점유 포트/다른 DB에서 POST 0회, 종료도 소유 PID만. 기본 dist·DB 불변. 기존 테스트를 삭제/skip하지 않음.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-harness.spec.ts --grep owned-isolation --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-01/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-01/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-harness.spec.ts --grep reject-foreign --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-01/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-01/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-01/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 2. 전 제품·공정·물류의 독립 커버리지 등록부
  Recommended task executor category: unspecified-high — 여러기존모듈의정해진연결.
  What to do / Ownership: 신규 shared/coverage-registry.json, docs/FACTORY_PROCESS_REFERENCES.md, tools/qa/coverage.py, backend/tests/operations/test_factory_coverage.py. 20제품·187원본 단계·모든 컴파일 단계/연결·158기존 설비·40kind/모든 의미 variant·모든 신규 장비/물류 leg를 고정 ID로 등록한다. 공개 POSCO source_url의 공정 설명/그림을 출처와 읽은 날짜로 보존하고 49개 기존 경계 치환을 receiving/inspection/packaging/dispatch로 명시 매핑한다. 기존 구현에서 expected를 역생성하지 말고 원문과 승인 범위로 expected manifest를 작성한다.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-02, GAP-05, GAP-06, GAP-11, GAP-12.
  Parallelization: Wave 1 | Blocked by: 1 | Blocks: 3,4,7,14,40.
  References: backend/app/data/journey_products.json; backend/app/data/operations_routes.json; backend/app/operations/catalog.py:143; shared/factory-layout.json; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 제품20개 전부와 원본187개 disposition 누락0; 신규 엔티티도 QA행을 자동 요구. source inaccessible은 명시하고 동일 주제를 설명하는 공식 공개 자료로 근거를 확보한다; 확인되지 않은 공정 구조를 검증됨으로 표시하지 않음.
  QA happy (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_coverage.py -k complete -q ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-02/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_coverage.py -k missing_or_generic -q ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-02/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-02/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 3. 공간·단위·버전 계약
  Recommended task executor category: deep-high — 공유계약과불변조건을함께보장.
  What to do / Ownership: 신규 shared/factory-world-v2.schema.json과 Python/TS 공간 validator. meter/Y-up/+X 차량 전방, yaw Y, mm소재 치수→m 변환을 고정한다. Node/Segment/ConflictZone/Slot/Port/Footprint/AllowedInteriorEnvelope 및 immutable bundle hash를 정의한다. LOD/카메라와 무관한 물리 경로를 소유한다. 이전 위치는 보존하고 v2 location은 v2: namespace, 사용자 equipment ID는 유지한다.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-04, GAP-14.
  Parallelization: Wave 1 | Blocked by: 2 | Blocks: 4,5,6,8.
  References: shared/factory-layout.json; shared/factory-campus.json; backend/app/operations/layout.py:158; src/operations/scene/layout.ts; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 양쪽 parser가 동일 fixtures를 승인/거절; 접점·support·시간경계 위치 오차≤0.01m. 차선/철도/용선/롤러/컨베이어/항로 모드 분리, 좌표와 camera scale로 speed를 바꾸지 않음.
  QA happy (agent-executed): npm test -- src/operations/scene/worldContract.test.ts -t valid ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-03/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): npm test -- src/operations/scene/worldContract.test.ts -t invalid ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-03/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-03/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 4. 자산·동작부·라이선스 규약
  Recommended task executor category: unspecified-high — 여러기존모듈의정해진연결.
  What to do / Ownership: 신규 shared/asset-manifest.schema.json 및 docs/ASSET_STANDARD.md. 단위 검사는 src/operations/scene/assets/manifest.test.ts에 만들며 현재 Vitest include 안에 둔다. family/kind/variant/LOD, root/axis/pivot, support/load/grip sockets, moving parts, roof nodes, materials, collision proxies, source/export hash와 license를 필수화한다. 기본 운영 모델/텍스처는 직접 제작한다. 외부 자산은 CC0 또는 CC-BY4.0로 재배포/수정 가능한 명시 출처와 attribution이 있는 경우만 등록 가능하고 미확인/NC/ND는 빌드 거절한다. 이 계획의 기본 자산목록은 외부 자산0개이므로 다운로드 실패로 막히지 않는다.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-01, GAP-11, GAP-15.
  Parallelization: Wave 1 | Blocked by: 2,3 | Blocks: 5,6,7,12,13.
  References: design/mockups/2026-10-25/prompts.md; src/journey/scene/Equipment.tsx:90; src/operations/scene/processPose.ts:7; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 40kind와 신규 운영 자산은 동일 rubric; 모든 움직이는 파트에 의미/축/범위/clip 또는 procedural binding. 단순 반복 decor로 운영 설비를 대체하지 않음.
  QA happy (agent-executed): npm test -- src/operations/scene/assets/manifest.test.ts -t valid ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-04/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): npm test -- src/operations/scene/assets/manifest.test.ts -t license_or_binding_missing ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-04/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-04/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 5. 새 운영 계약·DB·API의 원자적 전환
  Recommended task executor category: deep-high — 공유계약과불변조건을함께보장.
  What to do / Ownership: 신규 contracts_v3.py/models_v3.py 및 migration ops_factory_v3.py, TS discriminated schema3. v3 run은 factory-v2 contract bundle을 고정한다. 별도 StockLot/MaterialVersion/BatchIO/Fleet/Job/Segment/Reservation/Leg/Receipt/Attachment 표를 추가하며 v1/v2 snapshot은 read-only adapter로 유지한다. 기존 parent_version/lot/order 필수 조회는 v3에서 금지하고 nullable provenance+별도 allocation으로 전환한다. World·material detail·KPI·orders·production 호환 projection을 함께 타입화한다.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-05, GAP-06, GAP-08, GAP-10.
  Parallelization: Wave 1 | Blocked by: 3,4 | Blocks: 6,9,10,11,35,38,48.
  References: backend/app/operations/{contracts,models,service,projection}.py; backend/migrations/versions/ops_20261024_unified.py; src/operations/contracts.ts; src/contracts.ts; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 기존 event/위치/trigger/ID/순서 보존; v3 active writer 하나. stock detail에서 order/work_order/production_lot은 null 가능, 조회 오류 없음. 불지원 bundle은 명시 거절하며 최신 자원으로 재해석 금지.
  QA happy (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_contracts.py -k roundtrip -q ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-05/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_contracts.py -k reject_or_legacy -q ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-05/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-05/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 6. 작업 단계와 소재 인계의 공통 동작 계약
  Recommended task executor category: deep-high — 공유계약과불변조건을함께보장.
  What to do / Ownership: 신규 shared/motion-recipes.json, backend/app/operations/motion.py, src/operations/scene/motion/contracts.ts. 모든 단계에 entry/work/exit, start/end sim_ms, material form/geometry parameters, part phase windows, attachment acquire/release boundary를 지정한다. 업무 clock factor60과 speed1/2/4를 분리하고 phase는 서버 시간만 소비한다. 지연 중 기계/소재가 임의로 계속 움직이지 않는다.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-02, GAP-07, GAP-14.
  Parallelization: Wave 1 | Blocked by: 3,4,5 | Blocks: 11,13,14,15,18,31.
  References: src/operations/scene/{processPose,transferPose}.ts; backend/app/operations/{engine,transport}.py; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 모든 coverage phase에 정의1개; single/large step 같은 pose와 custody. 1cm 인계 오차, planned completion 밖으로 frontend가 상태를 진행하지 않음.
  QA happy (agent-executed): npm test -- src/operations/scene/motion/contracts.test.ts -t boundary ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-06/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): npm test -- src/operations/scene/motion/contracts.test.ts -t stale_or_missing ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-06/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-06/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 7. 전체 미술·인터랙션 기준 고정
  Recommended task executor category: visual-engineering — 시각구조와실제상호작용/기구표현.
  What to do / Ownership: 신규 docs/FACTORY_VISUAL_STANDARD.md, src/operations/scene/visualTokens.ts, shared/visual-review-matrix.json. A외관+B운영+C동일세계절개를 기준으로 palette/재질/조명/표식/선택색/카메라를 고정한다. AI이미지의 잘못된 기계구조는 source evidence와 교정하고 PNG를 3D대용으로 쓰지 않는다. 질적 rubric 각 항목 pass/fail 정의와 독립 시각 검토 기록 형식을 만든다.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-01, GAP-09, GAP-12.
  Parallelization: Wave 1 | Blocked by: 2,4 | Blocks: 8,12,13,19,20,21,28,45.
  References: design/mockups/2026-10-25/{a-miniature-overview,b-operations-map,c-material-follow}.png; src/operations/operations.css; src/operations/scene/SceneLabel.tsx; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 모든 구역 동일 silhouette/기구부/support/재질/근접검수 항목; 큰 label 배경이 공정을 가리지 않고 선택 대상만 강조. kind별 다르지만 동일 polygon수를 강제하지 않음.
  QA happy (agent-executed): npm test -- src/operations/scene/visualTokens.test.ts -t complete ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-07/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): npm test -- src/operations/scene/visualTokens.test.ts -t unreviewed_variant ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-07/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-07/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 8. 가상 해안 제철소 전체 레이아웃
  Recommended task executor category: visual-engineering — 시각구조와실제상호작용/기구표현.
  What to do / Ownership: 신규 tools/build_factory_world_v2.py와 shared/factory-world-v2.json. north 입고, central 탄소강 제강/압연/도금, south STS/Ti/출하, east 원료/제품 분리 부두로 배치한다. 기존 구역24+신규 물류구역을 포함한다. 일관된 미터 크기/차량 swept envelope를 적용하고 국지 교차만 허용; 격자 칸/건물 관통/동선 교차 그래픽으로 대체 금지. 모든 crane coverage/road/rail/staging/빈차고/고객하역이 실제 node/slot에 연결.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-01, GAP-04, GAP-14.
  Parallelization: Wave 2 | Blocked by: 3,7 | Blocks: 9,11,15,19,20,21,28,29,30.
  References: tools/build_factory_campus.py; shared/factory-campus.json; shared/factory-layout.json; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 모든 설비/포트 접근가능, forbidden footprint 교차0, turn radius 충족; 생성기는 출력 인수 필수이며 기존 shared 파일 덮어쓰기 금지. 조감도와 24+구역 blueprint 이미지 검수.
  QA happy (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_world.py -k reachable -q ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-08/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_world.py -k obstruction_or_deadend -q ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-08/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-08/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 9. 주문 이전 입고 재고와 후공정 진입
  Recommended task executor category: unspecified-high — 여러기존모듈의정해진연결.
  What to do / Ownership: 신규 receipts.py/stock.py와 route-entry policy. ORE/SCRAP/TI_INGOT 외 SLAB/BLOOM/BILLET/HR_COIL/CR_COIL/STS_HR_COIL/TI_HR_COIL 구입재 입고를 지원한다. stock가 grade/dimensions/origin/quality를 소유하고 주문 배정 없이 검수·이동·조회 가능. entry table은 SLAB→hr/plate, BLOOM/BILLET→wire의 해당 가열 시작, HR→cr/hgi/go/ngo 또는 cr를 거치는gi/ga/eg, CR→gi/ga/eg, STS_HR→sts-cr, TI_HR→ti-cr/ti-sheet로 고정. 직판은 해당 동일 제품 레시피의 검사/포장 경계에서 시작.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-06, GAP-08.
  Parallelization: Wave 2 | Blocked by: 5,8 | Blocks: 10,17,18,35.
  References: backend/app/operations/fixtures.py:31; projection.py:86; engine.py:35; transport.py:45; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 미실행 상류 완료 event0; 부적합 form/grade/width/quality 거절; 고객주문 배정 전 재고의 KPI/상세/UI 계약 정상.
  QA happy (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_receipts.py -k purchased_hr -q ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-09/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_receipts.py -k incompatible_entry -q ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-09/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-09/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 10. 배치·분할·합류·질량 원장
  Recommended task executor category: deep-high — 공유계약과불변조건을함께보장.
  What to do / Ownership: 신규 batches.py와 version별 N:M lineage. 입력/첨가/출력/부산물/손실을 배치 행으로 기록하며 root version 개수로 초기 질량을 추측하지 않는다. kg 정수, remainder는 output ID 정렬순 배분. 첨가물은 재고 소비 또는 외부유입 하나로만 계상한다. 소비 부모 비활성, 출력 물리단위 각각 생성, 여러 주문 배정은 분할 출력별로 하여 한 개체 이중배정 방지. delivered는 고객 custody active 재고로 유지.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-08.
  Parallelization: Wave 2 | Blocked by: 5,9 | Blocks: 17,18,25,48.
  References: backend/app/operations/lineage.py:8; models.py:139; catalog.py:99; test_lineage_mass.py; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 두입력+첨가→세출력→두주문 fixture의 batch/global 잔차0, cycle/중복소비/이중배정0; 재전송·재시작 같은 결과.
  QA happy (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_batches.py -k merge_split -q ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-10/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_batches.py -k double_count_or_cycle -q ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-10/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-10/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 11. 영속 장비·작업·예약 상태
  Recommended task executor category: unspecified-high — 여러기존모듈의정해진연결.
  What to do / Ownership: 신규 fleet.py/jobs.py. fleet ID와 작업/출하 leg ID를 분리하고 위치·load socket·carrier length/capacity/turn radius/mode·현재 작업·가용시각을 저장한다. fixed cranes는 fleet100에 포함하지 않는다. job state IDLE/ASSIGNED/EMPTY_APPROACH/QUEUED/LOADING/MOVING/UNLOADING/RETURNING/IDLE 및 BLOCKED, current movement/attachment/예약을 원자 저장. 예약 release도 event와 같은 transaction.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-03, GAP-05, GAP-07.
  Parallelization: Wave 2 | Blocked by: 5,6,8 | Blocks: 15,16,38.
  References: backend/app/operations/{resources,transport,fulfillment}.py; shared/factory-layout.json:19392; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 대기/복귀/작업교체에서도 stable ID 유지, 한장비 동시job1개, 위치/예약 재시작 복원; snapshot에 장비와 예약을 누락하지 않음.
  QA happy (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_fleet.py -k lifecycle -q ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-11/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_fleet.py -k duplicate_assignment -q ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-11/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-11/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 12. 무료 Blender와 재현 가능한 자산 제작 파이프라인
  Recommended task executor category: unspecified-high — 여러기존모듈의정해진연결.
  What to do / Ownership: 실행 단계에 공식 Blender4.5 LTS Apple Silicon4.5.15를 user-local tools 디렉터리에 설치하며 official release checksums를 검증하고 version/hash를 assets/toolchain.json에 고정한다. 파일이 없거나 공식검증 불가면 실패하고 임의미러/버전변경 금지. 신규 scripts/assets/{build.py,verify.mjs}, assets/source와 public/assets/steelworks를 만든다. pipeline 검사는 src/operations/scene/assets/pipeline.test.ts에 두고 @vitest-environment node와 120초 명시 timeout을 적용한다. Blender background 검사를 Node 프로세스에서 실행하고 exit/output을 검증한다. build.py는 Blender background로 family recipe→.blend+LOD GLB+procedural textures를 재생성. 원본/배포목록 및 license hash, deterministic geometry semantic hash를 저장한다.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-01, GAP-11, GAP-15.
  Parallelization: Wave 2 | Blocked by: 4,7 | Blocks: 19,20,21,26,27,28,29,41.
  References: backend/pyproject.toml; docs/ASSET_STANDARD.md(new T4); https://www.blender.org/releases/4-5/; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 외부 유료/AI서비스 없이 build; Blender 산출물 timestamp 차이를 제외한 geometry/mesh/name/animation semantic hash 동일. 잘못된 axis/pivot/texture/scale/기계 node 누락을 거절.
  QA happy (agent-executed): npm test -- src/operations/scene/assets/pipeline.test.ts -t reproducible ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-12/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): npm test -- src/operations/scene/assets/pipeline.test.ts -t reject_corrupt ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-12/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-12/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 13. 3D 자산 로더·캐시·동일 개체 LOD
  Recommended task executor category: visual-engineering — 시각구조와실제상호작용/기구표현.
  What to do / Ownership: 신규 scene/assets/{loader,registry,lod}.ts. 로컬 GLB/texture 로딩·캐시, geometry/material 공유, 해제 소유권, hover/pick instance ID→업무ID 매핑. 상세 원본은 전부 존재하며 overview에만 거리 LOD. 로딩중 label을 실제 작업 완료로 오인시키지 않으며 실패한 운영자산은 명시적 오류/2D자료로 전환하고 일반롤러 fallback 제거.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-01, GAP-09, GAP-10, GAP-11.
  Parallelization: Wave 2 | Blocked by: 4,6,7 | Blocks: 14,30,31,34,39.
  References: src/operations/scene/OperationsScene.tsx; FactoryGround.tsx:42; navigation.ts:5; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: LOD/절개/재진입에도 same entityID; 누락파일과 binding은 오류, 외부network0; pause시 자산로딩 완료가 simulation을 진행시키지 않음.
  QA happy (agent-executed): npm test -- src/operations/scene/assets/registry.test.ts -t identity ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-13/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): npm test -- src/operations/scene/assets/registry.test.ts -t missing_asset ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-13/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-13/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 14. 실제 기구·픽셀·영상 QA 관측기
  Recommended task executor category: unspecified-high — 여러기존모듈의정해진연결.
  What to do / Ownership: 신규 scene/qaProbe.ts와 tests/helpers/factory.ts. 개발/QA 플래그에서만 bound node/part/socket matrix와 API revision을 기록; 운영 빌드의 전체scene traversal 제거. Playwright screenshot/video/trace, presented-frame 보조 Chrome tracing과 RAF(구분 보고), backend payload/custody를 한 receipt로 저장. mutation 전 소유권확인과 연속영상 Step0 카운터를 제공.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-11, GAP-12, GAP-13.
  Parallelization: Wave 2 | Blocked by: 1,2,6,13 | Blocks: 19,20,21,26,27,28,29.
  References: src/operations/scene/OperationsScene.tsx:41; tests/helpers/operations.ts; tests/operations-visual.spec.ts:25; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 명시 qa off일 때 진단 traversal/JSON0; 보이는 픽셀에 물체가 없으면 metadata만 있어도 fail. 잘못된 run/revision/video 누락을 거절.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-observer.spec.ts --grep actual-frame --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-14/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-14/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-observer.spec.ts --grep metadata-only --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-14/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-14/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-14/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 15. 결정론적 교통 예약과 교착 종료
  Recommended task executor category: ultrabrain — 교통예약·경합·결정론을한문제로검증.
  What to do / Ownership: 신규 traffic.py. 같은 시각 completion/release→ready→dispatch 순서; FIFO(ready_at_ms,job_id). directed mode graph에서 deterministic Dijkstra 비용=travel+예약대기, tie=segmentID. 안전정차slot까지의 conflict set을 atomic 예약하고 목적지slot 없으면 진입하지 않는다. 미래 interval search는 충돌 end로 전진하며 hold-and-wait를 금지하고 rail선두→마지막화차 이탈까지 block점유. 끝없는 wait는 finite horizon3,600,000 sim_ms에서 structural_blocked 이유로 종료; 자동 teleport/겹침허용 금지.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-04, GAP-14.
  Parallelization: Wave 3 | Blocked by: 6,8,11 | Blocks: 16,18,22,23,24,37.
  References: backend/app/operations/engine.py:55; transport.py:39; new factory-world-v2 contract T3; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 교차로4방향·단선대향·도크만석·복구경쟁 fixture에서 충돌0, 각 feasible case deadline 안 완료, infeasible은 이유. 큰/작은 step·배속·재시작 정규화 event/reservation 동일.
  QA happy (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_traffic.py -k feasible -q ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-15/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_traffic.py -k deadlock_or_blocked -q ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-15/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-15/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 16. 배차·빈차 접근·대기·복귀 스케줄러
  Recommended task executor category: deep-high — 공유계약과불변조건을함께보장.
  What to do / Ownership: 신규 dispatch.py가 호환 fleet를 earliest feasible arrival→assetID 순으로 선택하고 새 일정을 traffic에 예약한다. 적재/하역은 station resource와socket attachment를 포함한다. 작업 후 depot가예약되면복귀, 다른job할당은 안전정차slot에서만 변경; 고장시현재안전상태·적재물유지. 기존 transfer는job의 호환 projection이며독립 writer없음.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-03, GAP-05.
  Parallelization: Wave 3 | Blocked by: 11,15 | Blocks: 17,22,23,24,32,37,42.
  References: backend/app/operations/transport.py:172; service.py:115; new fleet/jobs T11; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 동일차량2작업+복귀, 빈차도 실제시간·경로소모, capacity/thermal/form 적합성, 다른장비와경합. 차량도착만으로소재도착을가정하지않음.
  QA happy (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_dispatch.py -k two_jobs_return -q ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-16/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_dispatch.py -k no_capacity_or_fault -q ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-16/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-16/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 17. 실제 입고 하역·계량·재고 전이
  Recommended task executor category: unspecified-high — 여러기존모듈의정해진연결.
  What to do / Ownership: receiving.py에서 원료선/육상원료/스크랩/구입반제품의 도착→대기→계량/검수→하역→stock slot까지 job을 생성. 수입시점에 외부 custody에서 내부로 원장 경계유입을 한 번 기록하며 지연/보류를 갖는다. bulk는lot 단위로 추적하고 입자는 업무ID가 아님. 생산은검사통과/배정/도착후에만 시작.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-06, GAP-08.
  Parallelization: Wave 3 | Blocked by: 9,10,16 | Blocks: 22,23,24,32.
  References: backend/app/operations/fixtures.py:31; new receipts/stock/dispatch T9,T16; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 초기입고완료로미리생성하지않음; 동일 receipt중복요청/중량불일치/품질hold에재고중복0, 미실행상류event0.
  QA happy (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_receiving.py -k unloading -q ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-17/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_receiving.py -k duplicate_or_hold -q ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-17/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-17/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 18. 전 공정의 서버 동작 단계와 재료 변환
  Recommended task executor category: deep-high — 공유계약과불변조건을함께보장.
  What to do / Ownership: process_execution_v3.py에서 catalog 모든 source step을 phase recipe에 연결하고 고유 equipment reservation·entry/work/exit·투입/완료를 결정한다. batch input/material form변경은event경계원자반영. 현재final-inspection/packaging를 공정line별물리station instance에 매핑해중앙한동으로강제하지않음. 연속strip은설비내부경로와coiler누적형상을동작계약으로표현한다.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-02, GAP-08, GAP-14.
  Parallelization: Wave 3 | Blocked by: 6,9,10,15 | Blocks: 22,23,24,25,31,36,42.
  References: backend/app/operations/{catalog,engine,lineage}.py; src/operations/scene/processPose.ts; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 모든20경로와각step이원천/다음단계/실제position으로이어짐; unsupported kind명시실패; 작업정지에서part/material동시정지.
  QA happy (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_processes.py -k all_routes -q ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-18/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_processes.py -k wrong_form_or_blocked -q ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-18/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-18/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 19. 원료·제선·제강·연주 자산 전종
  Recommended task executor category: visual-engineering — 시각구조와실제상호작용/기구표현.
  What to do / Ownership: assets/source/steelmaking/의 Blender recipe와 .blend, public/assets/steelworks/steelmaking/의 GLB/LOD/재질을 제작한다. 범위: charge/blast_furnace/bof/ladle_furnace/eaf/aod/caster; slab/bloom/billet mold/절단 variants, 원료층·출선·출강·래들handoff. T2의 모든 variant와배치에적용하며단순박스/이미지대체금지. 각모델은공개공정근거·미술기준·작업파트/축/범위/접점/roof/collision proxy를가진다. scripts/assets/build.py --family steelmaking로재생성되고 manifest와 licenses를등록한다. 가족별tests/assets/steelmaking.spec.ts를동시에작성한다.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-01, GAP-02, GAP-07, GAP-11, GAP-15.
  Parallelization: Wave 3 | Blocked by: 7,8,12,14 | Blocks: 26,29,30,41.
  References: design/mockups/2026-10-25; shared/coverage-registry.json(T2); shared/asset-manifest.schema.json(T4); src/journey/scene/Equipment.tsx; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: steelmaking 모든kind/variant의3각도·근접·idle/running/blocked/full-cycle캡처와video, 독립visual reviewer전항목PASS. 인계접점1cm,무의미한무한반복없음; unsupported/누락은실패.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/assets/steelmaking.spec.ts --grep full-cycle --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-19/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-19/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/assets/steelmaking.spec.ts --grep bad-pivot-or-binding --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-19/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-19/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-19/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 20. 열연·후판·선재·가열·절단 자산 전종
  Recommended task executor category: visual-engineering — 시각구조와실제상호작용/기구표현.
  What to do / Ownership: assets/source/hot-rolling/의 Blender recipe와 .blend, public/assets/steelworks/hot-rolling/의 GLB/LOD/재질을 제작한다. 범위: furnace/roughing/finishing_mill/bloom_mill/wire_mill/cooling/cooling_bed/coiler/laying_head/shear/heat_treatment/leveler; plate gas-cut variant. T2의 모든 variant와배치에적용하며단순박스/이미지대체금지. 각모델은공개공정근거·미술기준·작업파트/축/범위/접점/roof/collision proxy를가진다. scripts/assets/build.py --family hot-rolling로재생성되고 manifest와 licenses를등록한다. 가족별tests/assets/hot-rolling.spec.ts를동시에작성한다.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-01, GAP-02, GAP-07, GAP-11, GAP-15.
  Parallelization: Wave 3 | Blocked by: 7,8,12,14 | Blocks: 26,27,29,30,41.
  References: design/mockups/2026-10-25; shared/coverage-registry.json(T2); shared/asset-manifest.schema.json(T4); src/journey/scene/Equipment.tsx; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: hot-rolling 모든kind/variant의3각도·근접·idle/running/blocked/full-cycle캡처와video, 독립visual reviewer전항목PASS. 인계접점1cm,무의미한무한반복없음; unsupported/누락은실패.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/assets/hot-rolling.spec.ts --grep full-cycle --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-20/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-20/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/assets/hot-rolling.spec.ts --grep bad-pivot-or-binding --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-20/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-20/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-20/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 21. 냉연·도금·전기강판 자산 전종
  Recommended task executor category: visual-engineering — 시각구조와실제상호작용/기구표현.
  What to do / Ownership: assets/source/finishing/의 Blender recipe와 .blend, public/assets/steelworks/finishing/의 GLB/LOD/재질을 제작한다. 범위: uncoiler/pickling/cold_mill/electrocleaning/annealing/temper/oiling/galvanizing/alloying/electroplating/coating/decarburizing; GI/GA/HGI/EG와GO/NGO기구·라인차이. T2의 모든 variant와배치에적용하며단순박스/이미지대체금지. 각모델은공개공정근거·미술기준·작업파트/축/범위/접점/roof/collision proxy를가진다. scripts/assets/build.py --family finishing로재생성되고 manifest와 licenses를등록한다. 가족별tests/assets/finishing.spec.ts를동시에작성한다.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-01, GAP-02, GAP-07, GAP-11, GAP-15.
  Parallelization: Wave 3 | Blocked by: 7,8,12,14 | Blocks: 26,27,29,30,41.
  References: design/mockups/2026-10-25; shared/coverage-registry.json(T2); shared/asset-manifest.schema.json(T4); src/journey/scene/Equipment.tsx; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: finishing 모든kind/variant의3각도·근접·idle/running/blocked/full-cycle캡처와video, 독립visual reviewer전항목PASS. 인계접점1cm,무의미한무한반복없음; unsupported/누락은실패.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/assets/finishing.spec.ts --grep full-cycle --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-21/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-21/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/assets/finishing.spec.ts --grep bad-pivot-or-binding --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-21/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-21/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-21/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 22. 도로 트러킹·지게차·캐리어 운영
  Recommended task executor category: unspecified-high — 여러기존모듈의정해진연결.
  What to do / Ownership: road_logistics.py에덤프/평판트럭/슬래브·코일캐리어/지게차의차로·swept envelope·속도/가감속·정지선·인양/상차/결박/계량gate를구현한다. 도로차량과용선철도를구분하고연속뜨거운strip은트럭에싣지않는다. staged pendingjob와returnpath도동일scheduler소유.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-03, GAP-04, GAP-05.
  Parallelization: Wave 4 | Blocked by: 15,16,17,18 | Blocks: 25,32,33,44.
  References: backend/app/operations/transport.py; new traffic/dispatch T15,T16; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 교차로/좁은커브/상차장경합에서차체·적재물관통0, 규격·온도등급부적합거절; 차량방향·바퀴속도와거리일치.
  QA happy (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_road.py -k loaded_and_empty -q ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-22/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_road.py -k clearance_or_thermal -q ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-22/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-22/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 23. 기관차·화차·편성·입환·철송 운영
  Recommended task executor category: deep-high — 공유계약과불변조건을함께보장.
  What to do / Ownership: rail_logistics.py와Consist(orderedassetIDs,coupler distances,total length)를추가한다. 분기기lock,연결/분리,후진입환,대기선→작업선→발차,화차slot상차/목적지역하역을구현한다. 마지막화차가벗어나기전block반납금지; 용선전용철도와일반철송네트워크를명시분리한다.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-05.
  Parallelization: Wave 4 | Blocked by: 15,16,17,18 | Blocks: 25,32,33,44.
  References: backend/app/operations/contracts.py:227; models.py:241; shared/factory-layout.json rail paths; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 기관차·화차각각클릭ID유지, 마지막차량clearance·결합거리보존. 상차중발차/점유분기변경/모드오입선거절.
  QA happy (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_rail.py -k shunting_delivery -q ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-23/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_rail.py -k tail_block_or_switch -q ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-23/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-23/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 24. 원료·제품 부두와 선적·양하 운영
  Recommended task executor category: unspecified-high — 여러기존모듈의정해진연결.
  What to do / Ownership: port_logistics.py에원료/제품분리berth, 선박대기·접안·선창slot/적재순서·하역장비작업범위·이안·항로·고객부두양하를구현한다. 원료unloader와제품crane은각fleet/장비실체에연결. 선박은job전후에도존재하고customer재고확정은양하/검수이후.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-05, GAP-06, GAP-07.
  Parallelization: Wave 4 | Blocked by: 15,16,17,18 | Blocks: 25,32,33,44.
  References: backend/app/operations/fulfillment.py:198; src/operations/scene/LogisticsActors.tsx; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 두선박berth경합·선창용량·크레인reach검사, 출항전적재완료gate; 바다/육상순간전환없음.
  QA happy (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_port.py -k berth_unload -q ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-24/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_port.py -k capacity_or_reach -q ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-24/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-24/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 25. 품질·분할 출하·운송수단별 이행
  Recommended task executor category: deep-high — 공유계약과불변조건을함께보장.
  What to do / Ownership: fulfillment_v3.py에ROAD/RAIL/SEA legs를연결. 허용정책은ROAD직송,RAIL직송,ROAD→SEA→ROAD,RAIL→SEA→ROAD이고출발/도착터미널custody가맞아야한다. 정상기본20제품각ROAD/RAIL/SEA시연조합을fixture로배정한다. 검사/정정/포장은각라인별station, HOLD재검slot,출하승인과제품창고예약은별도. 주문별부분출하·납품수량KPI를같은원장에서계산한다.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-05, GAP-08.
  Parallelization: Wave 4 | Blocked by: 10,18,22,23,24 | Blocks: 32,35,36,37,40,42,44.
  References: backend/app/operations/{fulfillment,projection}.py; test_fulfillment.py:111; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 모든모드에서정확한order/lot/lineage·remaining kg, 두부분납품·반제품판매. HOLD/미적재/과다출하거절, mode문자만바꾼고정해상흐름금지.
  QA happy (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_fulfillment.py -k all_modes -q ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-25/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_fulfillment.py -k hold_or_overallocation -q ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-25/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-25/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 26. 스테인리스 전 공정 자산과 배치
  Recommended task executor category: visual-engineering — 시각구조와실제상호작용/기구표현.
  What to do / Ownership: assets/source/stainless/의 Blender recipe와 .blend, public/assets/steelworks/stainless/의 GLB/LOD/재질을 제작한다. 범위: EAF/AOD/caster, STS-HR/CR/plate의CAF/HAPL/CAPL/TLL/STL·조질·후판열처리 variants; 공용기구는검증된source mesh재사용가능. T2의 모든 variant와배치에적용하며단순박스/이미지대체금지. 각모델은공개공정근거·미술기준·작업파트/축/범위/접점/roof/collision proxy를가진다. scripts/assets/build.py --family stainless로재생성되고 manifest와 licenses를등록한다. 가족별tests/assets/stainless.spec.ts를동시에작성한다.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-01, GAP-02, GAP-07, GAP-11, GAP-15.
  Parallelization: Wave 4 | Blocked by: 19,20,21,12,14 | Blocks: 29,30,41.
  References: design/mockups/2026-10-25; shared/coverage-registry.json(T2); shared/asset-manifest.schema.json(T4); src/journey/scene/Equipment.tsx; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: stainless 모든kind/variant의3각도·근접·idle/running/blocked/full-cycle캡처와video, 독립visual reviewer전항목PASS. 인계접점1cm,무의미한무한반복없음; unsupported/누락은실패.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/assets/stainless.spec.ts --grep full-cycle --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-26/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-26/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/assets/stainless.spec.ts --grep bad-pivot-or-binding --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-26/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-26/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-26/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 27. 티타늄 전 공정 자산과 배치
  Recommended task executor category: visual-engineering — 시각구조와실제상호작용/기구표현.
  What to do / Ownership: assets/source/titanium/의 Blender recipe와 .blend, public/assets/steelworks/titanium/의 GLB/LOD/재질을 제작한다. 범위: forging/vacuum_annealing/slitter 및Ti-HR/CR/sheet/plate의재투입·TLL/STL/SHL·gas-cut variants; Ti잉곳입고와공정내형상변환. T2의 모든 variant와배치에적용하며단순박스/이미지대체금지. 각모델은공개공정근거·미술기준·작업파트/축/범위/접점/roof/collision proxy를가진다. scripts/assets/build.py --family titanium로재생성되고 manifest와 licenses를등록한다. 가족별tests/assets/titanium.spec.ts를동시에작성한다.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-01, GAP-02, GAP-07, GAP-11, GAP-15.
  Parallelization: Wave 4 | Blocked by: 20,21,12,14 | Blocks: 29,30,41.
  References: design/mockups/2026-10-25; shared/coverage-registry.json(T2); shared/asset-manifest.schema.json(T4); src/journey/scene/Equipment.tsx; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: titanium 모든kind/variant의3각도·근접·idle/running/blocked/full-cycle캡처와video, 독립visual reviewer전항목PASS. 인계접점1cm,무의미한무한반복없음; unsupported/누락은실패.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/assets/titanium.spec.ts --grep full-cycle --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-27/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-27/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/assets/titanium.spec.ts --grep bad-pivot-or-binding --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-27/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-27/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-27/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 28. 모든 운송 장비·크레인·선박 자산
  Recommended task executor category: visual-engineering — 시각구조와실제상호작용/기구표현.
  What to do / Ownership: assets/source/transport/의 Blender recipe와 .blend, public/assets/steelworks/transport/의 GLB/LOD/재질을 제작한다. 범위: 덤프/평판트럭/슬래브·코일캐리어/지게차/용선차/래들차/기관차/화차/벌크선/제품선·천장/야드/항만크레인·unloader/stacker/reclaimer;바퀴·조향·권상·붐·coupler. T2의 모든 variant와배치에적용하며단순박스/이미지대체금지. 각모델은공개공정근거·미술기준·작업파트/축/범위/접점/roof/collision proxy를가진다. scripts/assets/build.py --family transport로재생성되고 manifest와 licenses를등록한다. 가족별tests/assets/transport.spec.ts를동시에작성한다.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-01, GAP-02, GAP-07, GAP-11, GAP-15.
  Parallelization: Wave 4 | Blocked by: 7,8,12,14 | Blocks: 29,30,32,33,41.
  References: design/mockups/2026-10-25; shared/coverage-registry.json(T2); shared/asset-manifest.schema.json(T4); src/journey/scene/Equipment.tsx; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: transport 모든kind/variant의3각도·근접·idle/running/blocked/full-cycle캡처와video, 독립visual reviewer전항목PASS. 인계접점1cm,무의미한무한반복없음; unsupported/누락은실패.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/assets/transport.spec.ts --grep full-cycle --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-28/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-28/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/assets/transport.spec.ts --grep bad-pivot-or-binding --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-28/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-28/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-28/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 29. 공장동·입고·검사·포장·창고·고객 구역 자산
  Recommended task executor category: visual-engineering — 시각구조와실제상호작용/기구표현.
  What to do / Ownership: assets/source/campus/의 Blender recipe와 .blend, public/assets/steelworks/campus/의 GLB/LOD/재질을 제작한다. 범위: 31기존hall과신규입고/철송/항만/고객동,stock/port/ship/delivery/inspection/packaging;절개지붕·도어·랙·코일받침·계량대·bulk컨베이어. 운영장비는transport/공정ID참조만하고정적복제금지. T2의 모든 variant와배치에적용하며단순박스/이미지대체금지. 각모델은공개공정근거·미술기준·작업파트/축/범위/접점/roof/collision proxy를가진다. scripts/assets/build.py --family campus로재생성되고 manifest와 licenses를등록한다. 가족별tests/assets/campus.spec.ts를동시에작성한다.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-01, GAP-02, GAP-07, GAP-11, GAP-15.
  Parallelization: Wave 5 | Blocked by: 8,12,14,19,20,21,26,27,28 | Blocks: 30,40,41.
  References: design/mockups/2026-10-25; shared/coverage-registry.json(T2); shared/asset-manifest.schema.json(T4); src/journey/scene/Equipment.tsx; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: campus 모든kind/variant의3각도·근접·idle/running/blocked/full-cycle캡처와video, 독립visual reviewer전항목PASS. 인계접점1cm,무의미한무한반복없음; unsupported/누락은실패.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/assets/campus.spec.ts --grep full-cycle --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-29/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-29/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/assets/campus.spec.ts --grep bad-pivot-or-binding --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-29/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-29/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-29/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 30. 전체 공장 자산 배치와 고정 환경 통합
  Recommended task executor category: visual-engineering — 시각구조와실제상호작용/기구표현.
  What to do / Ownership: scene/environment/FactoryCampus.tsx와layout→asset instance factory를작성하고기존일반silhouette/정적운영장비를교체한다. 모든physicalport/worldtransform을manifest로계산,환경소품과운영기구를분리. coastal raw/productquay,공장별긴line/외부yard,서비스도로·rail·컨베이어를같은좌표로연결.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-01, GAP-04, GAP-07, GAP-09.
  Parallelization: Wave 5 | Blocked by: 8,13,19,20,21,26,27,28,29 | Blocks: 31,32,33,34,39,45.
  References: src/operations/scene/FactoryGround.tsx:61; ProcessStations.tsx:43; new factory-world-v2; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 모든coverage배치누락0; 현물량에맞는stock슬롯, 건물interior보임; 항만crane단일entity, scene에PNG factoryplane없음.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-campus.spec.ts --grep complete-campus --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-30/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-30/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-campus.spec.ts --grep duplicate-or-obstructed --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-30/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-30/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-30/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 31. 모든 기계 가동부와 소재 형상 투영
  Recommended task executor category: visual-engineering — 시각구조와실제상호작용/기구표현.
  What to do / Ownership: scene/motion/project.ts와entities/EquipmentEntity/MaterialEntity를구현. phase별기계축·소재길이/두께·권취보어·열색/냉각·도금상태를serverclock에서계산한다. blendclip은업무phase에동기화하고누적localtime금지. 실루엣·근접원본·collisionproxy를동일ID아래보관. 모든150+고유공정phase mapping을연결.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-02, GAP-07, GAP-08.
  Parallelization: Wave 5 | Blocked by: 6,13,18,30 | Blocks: 32,34,39,40,45.
  References: src/operations/scene/{MaterialMesh,ProcessStations}.tsx; coilGeometry.ts; new motion-recipes; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 40kind/모든variant가실제job에서동작; slit/merge부모소비와자식등장시각일치;정지·stale·배속·reducedmotion규칙전체에일관.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-mechanisms.spec.ts --grep all-bindings --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-31/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-31/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-mechanisms.spec.ts --grep frozen-or-invalid --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-31/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-31/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-31/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 32. 소재 받침·크레인 인계·적재 접촉
  Recommended task executor category: visual-engineering — 시각구조와실제상호작용/기구표현.
  What to do / Ownership: scene/motion/attachments.ts를통해source slot→hook→차량/화차/선창→destination을서버custody와동일boundary로전환한다. 크레인bridge/trolley/hoist·grip·케이블길이·차량loadsocket을동일entityrig에서계산한다. path중재료위치를각actor가독립으로추정하지않음. linkedpair기준으로worldtransform오차를측정.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-07, GAP-14.
  Parallelization: Wave 5 | Blocked by: 16,17,22,23,24,25,28,30,31 | Blocks: 33,40,44,45.
  References: src/operations/scene/transferPose.ts:35; TransferActors.tsx:43; tests/operations-transfers.spec.ts; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 모든materialhandoff≤1cm,중복body/분리소재/부유0;장비고장중에도하중안정/phase재개;질량source둘이중계산0.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-handoffs.spec.ts --grep all-custody --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-32/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-32/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-handoffs.spec.ts --grep wrong-socket-or-fault --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-32/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-32/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-32/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 33. 항상 존재하는 차량·철도·항만 개체 렌더링
  Recommended task executor category: visual-engineering — 시각구조와실제상호작용/기구표현.
  What to do / Ownership: scene/entities/FleetEntity/CraneEntity/ConsistEntity를운송job배열이아닌fleet registry에서생성. idle/queue/return/load행동과바퀴·조향·연결/역방향열차·선박접안/하역을표현. 현재작업이없어도위치와선택가능성을유지한다. shadowLOD와그림자품질도고정rubric에맞춘다.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-03, GAP-05, GAP-07.
  Parallelization: Wave 5 | Blocked by: 22,23,24,28,30,32 | Blocks: 34,39,40,44,45.
  References: src/operations/scene/TransferActors.tsx:76; LogisticsActors.tsx; new fleet snapshot; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 100fleet ID가두작업과복귀전후유지,빈화차/크레인클릭가능,마지막화차와railblock의screen/API일치.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-fleet.spec.ts --grep persistent --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-33/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-33/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-fleet.spec.ts --grep disappearance-or-overlap --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-33/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-33/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-33/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 34. 같은 공장에서 조감·절개·소재 추적
  Recommended task executor category: visual-engineering — 시각구조와실제상호작용/기구표현.
  What to do / Ownership: Selection을run/contract_version/entity_type/entity_id+관계context로확장(차량/크레인/stock/batch/leg포함). overview/stage/equipment scope에layoutversion추가,legacyURL명시변환. 카메라확대에맞춰지붕열기/벽절개,pan/zoom/orbit/focus/복귀,소재분할시계보자식선택. 카메라밖작업계속진행하고세계/clock재생성금지.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-09.
  Parallelization: Wave 5 | Blocked by: 13,30,31,33 | Blocks: 35,40,45,47.
  References: src/operations/{navigation.ts,scene/CameraRig.tsx,scene/CameraToolbar.tsx,OperationsWorkspace.tsx}; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 전24+구역동일전환,빈차량선택유지,split시부모이력과자식분기;잘못된run/layoutURL은안전하게선택/카메라만교정.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-navigation.spec.ts --grep same-world --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-34/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-34/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-navigation.spec.ts --grep invalid-url-or-split --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-34/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-34/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-34/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 35. 주문·재고·설비·운송 ERP 패널과 2D
  Recommended task executor category: visual-engineering — 시각구조와실제상호작용/기구표현.
  What to do / Ownership: 선택entity별업무패널을확장하고주문없는stock provenance,version계보,batch투입/산출,작업/예약/다음목적지,철도편성/leg와지연이유를표시한다. 한국어단위kg/UTC변환표시·검색·shipmenttimeline·현재/과거run읽기,2D동일정보. 패널은scene외측에두고hover소형라벨만표시. user-facing내부진단메타금지.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-08, GAP-09.
  Parallelization: Wave 5 | Blocked by: 5,9,25,34 | Blocks: 36,38,40,47.
  References: src/operations/{OrderNavigator,MaterialInspector,OperationsTable,WorkflowTimeline}.tsx; operations.css; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 주문/소재/차량선택상호링크정확,1000행검색/키보드/스크린리더,구입재order null정상;2D가별도시계를갖지않음.
  QA happy (agent-executed): npm test -- src/operations/FactoryInspector.test.tsx -t relationships ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-35/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): npm test -- src/operations/FactoryInspector.test.tsx -t unallocated-or-invalid ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-35/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-35/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 36. 전 제품 장애·대기·회복 시나리오
  Recommended task executor category: deep-high — 공유계약과불변조건을함께보장.
  What to do / Ownership: shared/scenario-coverage.json에20제품의장애지점·원인·예약영향·대안/수리재개를고정한다. NORMAL/DELAY/RECOVERY의seed동일,DELAY는원인중단과queue,RECOVERY는호환우회또는더이른수리후재개. 모든경로에실제지연/해제case를두되항상배송단축을강요하지않는다. 예측은동일engine복사로계산하며DBevent생성금지.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-02, GAP-05, GAP-12.
  Parallelization: Wave 6 | Blocked by: 18,25,35 | Blocks: 37,40,43.
  References: backend/app/operations/{scenarios,forecast}.py; src/operations/RecoveryPanel.tsx; tests/operations-demo.spec.ts:93; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 20×3결정론검증과원인→blockedreason→납기영향→resume 연결;이득없음/불가도정직표시. 과거고정NO_BENEFIT값을새세계정답으로재사용금지.
  QA happy (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_scenarios.py -k all_products -q ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-36/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_scenarios.py -k incompatible_recovery -q ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-36/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-36/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 37. 100주문·1000소재·100장비의 결정론 fixture와 엔진 비용
  Recommended task executor category: deep-high — 공유계약과불변조건을함께보장.
  What to do / Ownership: fixture profile demo/scale를version bundle에정의. scale의100fleet는truck32/carrier24/forklift16/torpedo4/ladle4/locomotive4/railcar12/ship4,고정crane별도. 100orders와1000active physical materials를실제작업/재고에연결한다. 성능window는분모가소실되지않는안정schedule로구성하고최소40운송과10생산작업동시진행. 불변row공유/변경row지속화/forecast캐시를사용하되event결과를고정하지않음.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-10, GAP-12.
  Parallelization: Wave 6 | Blocked by: 15,16,25,36 | Blocks: 38,46.
  References: backend/app/operations/{fixtures,service,engine,forecast}.py; backend/app/main.py:30; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 정규화event/최종state가최적화전후같음. 초기run60초내,scale tick p95≤100ms 목표,모든sample100/1000/100과작업진행증거. 목표미달시scope축소/분모낮춤금지.
  QA happy (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_scale.py -k equivalence -q ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-37/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_scale.py -k stalled_or_overbudget -q ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-37/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-37/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 38. 버전된 변경분 동기화·재연결
  Recommended task executor category: unspecified-high — 여러기존모듈의정해진연결.
  What to do / Ownership: 전체World bootstrap은유지하고같은writer에서GET /api/v1/world/delta?run_id=&after_revision=을추가. payload는from/to_revision,bundle_hash,immutable upserts와event범위,entity삭제대신inactive. 최대256revision ring; gap/다른run은409 resync_required로fullbootstrap. polling250ms(active)/1000ms(paused) 유지,성능충족위해WebSocket필수화하지않음. stale시업무완료예측금지,한원격store만유지.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-10.
  Parallelization: Wave 6 | Blocked by: 5,11,35,37 | Blocks: 39,40,42,46,48.
  References: src/store.ts:55; src/api.ts; backend/app/operations/{events,projection,service}.py; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: late/duplicate/outoforder/gap 응답에서state역행0;다른bundle은원자bootstrap. delta와fullWorld정규화동일;eventhistory는별도읽기projection도가능하나현재state복제금지.
  QA happy (agent-executed): npm test -- src/operations/factorySync.test.ts -t contiguous ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-38/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): npm test -- src/operations/factorySync.test.ts -t gap-or-stale ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-38/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-38/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 39. 고정밀 렌더링 비용·LOD·선택 최적화
  Recommended task executor category: visual-engineering — 시각구조와실제상호작용/기구표현.
  What to do / Ownership: 공유geometry/material,instancing+instanceIDmap,시야culling,동일원본LOD,선택instance분리,shadow/texture메모리상한을적용한다. GPU/CPU렌더와UIupdate를분리하고useFrame setState금지. 상세구역진입시이미load된asset재사용,QA probe는sample설정에만동작. 정지/reducedmotion은demand rendering.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-10, GAP-12.
  Parallelization: Wave 6 | Blocked by: 13,30,31,33,38 | Blocks: 41,42,46.
  References: src/operations/scene/OperationsScene.tsx:41; FactoryGround.tsx:42; R3F scaling-performance docs; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 1000material/100fleet선택가능,LOD절체selection/custody불변,미표시영역의서버진행보존. 최적화전후시각품질rubric동일;실제프레임측정으로판정.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-rendering.spec.ts --grep instanced-identity --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-39/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-39/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-rendering.spec.ts --grep lod-stale-bounds --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-39/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-39/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-39/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 40. 전체 제품·공간·모델·동작 연결 통합
  Recommended task executor category: unspecified-high — 여러기존모듈의정해진연결.
  What to do / Ownership: tools/qa/coverage.py를runtimebundle과照合하여모든route-step/variant/instance/port/leg/asset/motion/selection이연결됨을검사. 새장비나source치환이추가되면expected와근거를갱신하고교체이력보존. independent source기반expected와implementationmapping을별도로관리한다. 결과엔unmapped/placeholder/waived목록을항상출력.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-02, GAP-05, GAP-06, GAP-08, GAP-09, GAP-11.
  Parallelization: Wave 6 | Blocked by: 2,25,29,31,32,33,34,35,36,38 | Blocks: 41,43,44,45,48.
  References: shared/coverage-registry.json(T2); backend/app/operations/catalog.py; tests/fixtures/operations_route_expectations.json; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 20제품과모든기존/신규행mapping누락0,범용fallback0,운영장비정적장식0. summarycount만맞추고실제binding없는경우실패.
  QA happy (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_integration.py -k full_matrix -q ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-40/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_integration.py -k orphan_or_placeholder -q ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-40/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-40/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 41. 자산 배포·출처·오프라인 무결성
  Recommended task executor category: unspecified-high — 여러기존모듈의정해진연결.
  What to do / Ownership: bundle packaging이원본.blend/recipe·export GLB/texture·license attribution·SHA256·nodebinding을고정하며manifest밖asset사용을거절한다. runtime외부fetch차단하에서전체구역load,missingtexture/잘못된clip/LOD누락을검출한다. timestamp제외semantic export재현성을검사하고assetcache는bundlehash별분리.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-11, GAP-15.
  Parallelization: Wave 6 | Blocked by: 12,19,20,21,26,27,28,29,39,40 | Blocks: 43,45,46,47,48.
  References: scripts/assets/{build.py,verify.mjs}(T12); public/assets/steelworks; shared/asset-manifest.json; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 기본thirdpartyasset0 또는명시verifiedlicense만,외부요청0,key0. 전체오프라인3D/2D가작동하고누락자산오류가숨겨지지않음.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-offline.spec.ts --grep offline-all-assets --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-41/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-41/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-offline.spec.ts --grep corrupt-or-unlicensed --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-41/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-41/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-41/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 42. 정지·초기화·재시작·연결 상실 복구
  Recommended task executor category: deep-high — 공유계약과불변조건을함께보장.
  What to do / Ownership: 저장된clock/job/segment/attachment/reservation/consist/bundle을같은snapshotrevision으로복원한다. 재시작은paused,예약이나입출고완료를재추정하지않는다. pause/speed/reset명령멱등과run-epoch를유지하고reset은새run이력보존. stale표시와2Dfallback,복귀후동일개체위치복원. 임의과거시점scrub기능은추가하지않는다.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-03, GAP-08, GAP-10.
  Parallelization: Wave 6 | Blocked by: 16,18,25,38,39 | Blocks: 43,44,46,47,48.
  References: backend/app/operations/service.py; src/store.ts; tests/operations-resilience.spec.ts; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 작업각phase에서restart→samepose/custody(1cm)·중복event0. timeout/resend/oldrun응답·WebGLloss에서업무state손실0.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-resilience.spec.ts --grep restart-at-phases --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-42/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-42/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-resilience.spec.ts --grep stale-reset-webgl --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-42/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-42/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-42/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 43. 20제품 전 경로의 연속 추적 검증
  Recommended task executor category: unspecified-high — 여러기존모듈의정해진연결.
  What to do / Ownership: tests/factory-routes.spec.ts를작성해20제품별입고/후공정entry→제조→품질→출고→하역을실제UI로추적한다. 60scenario조합은serverboundary검사,20제품NORMAL연속4x영상은Step/reset없이각각기록하고각공정확대샷과연결. 가공이너무빠르면pause는허용하되연속시간계측에서분리해표시. 검사대상이선택과다른소재로바뀌면실패.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-12.
  Parallelization: Wave 7 | Blocked by: 36,40,41,42 | Blocks: 45,46,49.
  References: tests/operations-demo.spec.ts:36; tests/helpers/factory.ts(T14); shared/coverage-registry.json; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 20연속영상+60상태결과+전수경계artifact가registry와1:1. 모든shipmentmode·구입재entry·반제품판매포함,AIoff. 실패/skip/flaky0.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-routes.spec.ts --grep all-product-continuous --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-43/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-43/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-routes.spec.ts --grep reject-disconnected-lineage --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-43/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-43/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-43/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 44. 전 운송·교통·인계의 독립 증거
  Recommended task executor category: unspecified-high — 여러기존모듈의정해진연결.
  What to do / Ownership: tests/factory-logistics-proof.spec.ts에서모든mode/leg와phase의before/mid/after API+rigmatrix+화면을수집. 도로4방향경합·철도tail block/후진편성·제품부두선적·고객하역·emptyreturn을실제생산작업과함께재생. QAfixture만충돌proxy/예약을오염시켜검출기가실패하는지도증명.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-03, GAP-04, GAP-05, GAP-07, GAP-14.
  Parallelization: Wave 7 | Blocked by: 22,23,24,25,32,33,40,42 | Blocks: 45,46,49.
  References: tests/factory-handoffs.spec.ts(T32); backend/tests/operations/test_factory_traffic.py(T15); 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: collision/custody error0; tail과부품까지관측. 각입고·출고mode조합의필수coverage미검증0,loopingdecor는진행event없어서실패.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-logistics-proof.spec.ts --grep all-legs --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-44/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-44/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-logistics-proof.spec.ts --grep injected-conflict --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-44/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-44/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-44/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 45. 모든 구역·설비의 동등 품질 검수
  Recommended task executor category: visual-engineering — 시각구조와실제상호작용/기구표현.
  What to do / Ownership: tests/factory-fidelity.spec.ts로모든stage의전경/근접/절개(기존24개최소72장)+모든kind/variant3각도+모든배치접점화면을고정camera/seed/time에서수집. 별도읽기전용visual reviewer가구현자와독립으로전항목검수하고family재사용외형평가와개별배치평가를구분. 발견사항은ID와수정후재검수artifact연결,면제행금지.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-01, GAP-02, GAP-09, GAP-11, GAP-12.
  Parallelization: Wave 7 | Blocked by: 7,30,31,32,33,34,40,41,43,44 | Blocks: 46,49.
  References: shared/visual-review-matrix.json(T7); design/mockups/2026-10-25; tests/helpers/factory.ts; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: rubric모든행PASS,누락/보류/placeholder0. 이미지저장/자동픽셀similarity만으로승인불가; AI시안과형상수정은근거기록.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-fidelity.spec.ts --grep all-views --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-45/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-45/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-fidelity.spec.ts --grep hidden-or-generic --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-45/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-45/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-45/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 46. 합의 규모·실기기 성능·장시간 검증
  Recommended task executor category: unspecified-high — 여러기존모듈의정해진연결.
  What to do / Ownership: tests/factory-performance.spec.ts. 실제M4Max/Chrome1920×1080DPR1,30초warmup후overview/detail/follow×1/2/4 각각60초,별도30분soak/20회구역왕복+reset.매sample분모100/1000/100과최소40movingfleet/10activeprocess,clock/APIprogress를기록. RAF분포와Chrome trace/render계측을구분하고GPU지원없는측정은그사실표시. 초기모든assetwarm후geometry/texture가20회반복에누적증가0.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-10, GAP-12.
  Parallelization: Wave 7 | Blocked by: 37,38,39,41,42,43,44,45 | Blocks: 49.
  References: tests/operations-visual.spec.ts:25; tests/factory-rendering.spec.ts(T39); docs/TEST_RESULTS.md:3; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: p95≤25ms,p99≤50ms,선택/진입p95≤500ms;정지60초불필요render증가0(최초settle제외),coldhealth≤60초,예상치못한error0. snapshot/tick/network/memory별도보고. 기준완화/분모감소금지.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-performance.spec.ts --grep full-envelope --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-46/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-46/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-performance.spec.ts --grep reject-idle-cheat --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-46/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-46/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-46/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 47. 키보드·2D·작은 화면·오류 접근성 검증
  Recommended task executor category: visual-engineering — 시각구조와실제상호작용/기구표현.
  What to do / Ownership: tests/factory-accessibility.spec.ts. 한국어검색/키보드pan·orbit·zoom/focus·dialogfocus와스크린리더label,390px/1440px/1920px레이아웃,WebGL불가/손실/reduced-motion/AIunavailable에서동일주문·소재자료유지. 2D에서도fleet/job/stock/lineage/배송관계접근가능. 큰labels가장비를덮는회귀를검사.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-09, GAP-12.
  Parallelization: Wave 7 | Blocked by: 34,35,41,42 | Blocks: 49.
  References: tests/operations-navigation.spec.ts; tests/operations-resilience.spec.ts; src/operations/OperationsTable.tsx; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 모든핵심동작mouse없이가능,가로overflow0,focus손실0,오류를false-success로표시하지않음. WebKit기능smoke는Chrome실기기성능증거와구분.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-accessibility.spec.ts --grep keyboard-and-2d --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-47/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-47/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-accessibility.spec.ts --grep unavailable-and-reduced --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-47/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-47/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-47/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 48. 기존 이력·마이그레이션·복귀 번들 검증
  Recommended task executor category: deep-high — 공유계약과불변조건을함께보장.
  What to do / Ownership: test_factory_migration.py와tools/qa/migration_receipt.py. 합성populated DB복사본에만v3migration,기존run/event/trigger/행hash·FK/integrity·위치의미/oldbundle불변검사. 중간실패rollback/재실행/구버전reader조회와신버전writer를같이검사. rollback은보존DB+이전실행bundle전환이며새event삭제downgrade금지. 오래된layout/resource를현재값으로복원하지않음.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-08, GAP-13.
  Parallelization: Wave 7 | Blocked by: 5,10,38,40,41,42 | Blocks: 49.
  References: backend/tests/operations/test_migration_preservation.py:93; backend/migrations/versions; docs/TEST_RESULTS.md; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 원본DB/보존demo변경0,이전run읽기정상,unsupportedbundle명시거절,부분migration잔여0;phase별restart정보유지.
  QA happy (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_migration.py -k preserve_and_restore -q ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-48/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations/test_factory_migration.py -k interrupted_or_wrong_bundle -q ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-48/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-48/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

- [ ] 49. 로컬 실행·전체 시연 패키지·증거 색인
  Recommended task executor category: writing — 실제검증결과에근거한사용설명.
  What to do / Ownership: README와docs/FACTORY_V2_RUNBOOK.md/FACTORY_V2_RESULTS.md를실제최종결과로작성. ARM64설치/Blender원본재생성/로컬backendfrontend시작/port충돌/DBbackup/복귀/오프라인/AIoff와전체20제품데모절차. 10월30일진행시연은완료/미완료coverage를정직표시하고최종전체완료와구분. 동일소스동결bundle·실제영상/스크린샷·실행명령/버전/exit/해시목록을보존하고사용자보존서버를자동교체하지않음.
  Must NOT do: 범위/품질/증거를줄이거나다른작업자의변경을되돌리지않음. product/source변경은실행단계에만하고기존보존demo를사용하지않음.
  Closes: GAP-11, GAP-12, GAP-13, GAP-15.
  Parallelization: Wave 7 | Blocked by: 43,44,45,46,47,48 | Blocks: F1–F4.
  References: README.md; docs/{DEMO_2026_10_30,TEST_RESULTS,OPERATIONS_CONTRACT,FACTORY_CAMPUS}.md; 이계획의공간/업무/동일품질계약; .omo/drafts/steelflow-uniform-fidelity-factory.md
  Acceptance criteria: 문서명령을깨끗한작업소유복사본에서실행해재현. 최종테스트실패/skip/flaky0 또는미완료명시,과거합계재사용금지. 실제full-quality완료는F1–F4승인이후만표현.
  QA happy (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-release.spec.ts --grep clean-local-demo --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-49/happy ; assertion은위Acceptance의정상전이/표시/산출물을검증한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-49/happy/ (command.log,exit.json,assertions.json; browser/asset이면trace/video/screenshots와독립visual-review.json).
  QA failure (agent-executed): node tools/qa/run.mjs browser --spec tests/factory-release.spec.ts --grep offline-or-port-conflict --evidence .omo/evidence/uniform-fidelity/<attempt-id>/task-49/failure ; 의도한오류를assert하고예상치못한성공/부분state변경을실패로처리한다. Evidence: .omo/evidence/uniform-fidelity/<attempt-id>/task-49/failure/ (원래오류로그,assertions.json,변경전후state/hash).
  Commit: N — 현재작업폴더에Git저장소없음; .omo/evidence/uniform-fidelity/<attempt-id>/task-49/change-manifest.json에소유파일전후hash/diff와검증exit를기록. 임의git init/PR/publish금지.

## Final verification wave
> Runs in parallel after ALL todos. ALL must APPROVE. Product execution completion requires every criterion below; review artifacts do not substitute for tests.
- [ ] F1. Plan compliance audit
  Recommended task executor category: unspecified-high.
  Read-only reviewer maps all49 task manifests,allIS/GAP rows,coverage registry andfinalsourcehash. Compare approvedplan vsactualdiff,unmapped/waived0. Check licenses,oldDB/demo hashes and100/1000/100 denominator. Evidence: <attempt>/final/F1-compliance.md. Anyunclosedrequirement becomesa numberedimplementationtodo andisreverified;no self-report approval.
- [ ] F2. Code quality review
  Recommended task executor category: unspecified-high.
  Independent read-only review ofactualchangedfiles/contracts/migrations/scheduler/rendering/owned-processcleanup. Run npm run typecheck; npm test; backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/operations -q againstfrozenfinalsourceandisolatedDBs. Recordactualexit/failures,no oldpasscounts. Evidence: <attempt>/final/F2-review.md pluslogs.
- [ ] F3. Real manual QA
  Recommended task executor category: visual-engineering.
  Independent QA agent opensownedproductionpreviewusingbrowserautomation,actuallyselectsall20productsandall24+stages,checksvehiclesidle/load/return,railshunt/tail,raw/productquay,customerunload,split/merge,follow/pan/reset,2D/stale/WebGLrecovery. ReadactualrenderedUI,notDOMstatusalone. Link20continuousvideos/60scenarioresults;errors0. Evidence: <attempt>/final/F3-manual.md,UIactions,screenshots/video/console.
- [ ] F4. Ideal-state fidelity
  Recommended task executor category: visual-engineering.
  Read-only fidelity reviewer inspectseveryIS-01…14andallvisualregistryrowsagainst3mockups+processreference+approvedrubric. Full-detailmodelsforallregions,movingparts/truehandoffs/persistentfleet,accurateERPcontext,actualperformanceevidence. Assetfamilyreviewreuseallowedonlyforidenticalsourcevariant;placementclearance/selectioneveryinstance. Evidence: <attempt>/final/F4-fidelity.md withpass/failperrowandartifactlinks. Unreviewed/placeholder/notesinplaceofmissingfeature=FAIL.

F1–F4 run afterfinalsourcefreeze andmayparallelizewithinavailable3worker slots. No reviewer may approveownimplementation. Afterallapprovalsreportrealresultsandawaituseracceptanceofdeliveredproduct;thisisnotanadditionalpermissionrequestforreversiblefixesrequiredtopass.

## Commit strategy
현재 /Users/ethanlee/Desktop/ERP는Git저장소가아니다. 모든todo의Commit:N은작업소유change manifest와복구가능파일사본을뜻한다. Git을초기화하거나기존작업을branch/worktree로옮기는것은이계획에포함되지않는다. 사용자후속요청으로Git을도입하면그때관련skill을읽고원자commit을사용한다. 기존plan/draft/완료증거는새계획명과경로로보존하며overwrite하지않는다.

## Success criteria
> Every IS row requires both delivering tasks and proof. F4 checks rows 1:1. Alltasks+finalverifiersmustpass;currentplanreviewdoesnotclaimimplementationcompletion.
| IS | Delivering todo(s) | Proving QA scenario | Evidence |
| --- | --- | --- | --- |
| IS-01 | 8,29,30,45 | all-views; F4 corresponding row | <attempt>/task-45/happy/; <attempt>/final/F4-fidelity.md |
| IS-02 | 2,7,19,20,21,26,27,28,29,40,45 | all-views; F4 corresponding row | <attempt>/task-45/happy/; <attempt>/final/F4-fidelity.md |
| IS-03 | 34,35,43,47 | same-world; F4 corresponding row | <attempt>/task-34/happy/; <attempt>/final/F4-fidelity.md |
| IS-04 | 6,31,32,44 | all-custody; F4 corresponding row | <attempt>/task-32/happy/; <attempt>/final/F4-fidelity.md |
| IS-05 | 11,16,22,23,24,33,44 | persistent; F4 corresponding row | <attempt>/task-33/happy/; <attempt>/final/F4-fidelity.md |
| IS-06 | 3,8,15,22,23,24,44 | all-legs; F4 corresponding row | <attempt>/task-44/happy/; <attempt>/final/F4-fidelity.md |
| IS-07 | 9,17,25,43 | all-product-continuous; F4 corresponding row | <attempt>/task-43/happy/; <attempt>/final/F4-fidelity.md |
| IS-08 | 2,18,19,20,21,26,27,40,43 | all-product-continuous; F4 corresponding row | <attempt>/task-43/happy/; <attempt>/final/F4-fidelity.md |
| IS-09 | 5,9,10,25,35,43,48 | merge_split; F4 corresponding row | <attempt>/task-10/happy/; <attempt>/final/F4-fidelity.md |
| IS-10 | 36,43 | all_products; F4 corresponding row | <attempt>/task-36/happy/; <attempt>/final/F4-fidelity.md |
| IS-11 | 37,38,39,46 | full-envelope; F4 corresponding row | <attempt>/task-46/happy/; <attempt>/final/F4-fidelity.md |
| IS-12 | 38,41,42,47 | restart-at-phases; F4 corresponding row | <attempt>/task-42/happy/; <attempt>/final/F4-fidelity.md |
| IS-13 | 1,5,48,49 | preserve_and_restore; F4 corresponding row | <attempt>/task-48/happy/; <attempt>/final/F4-fidelity.md |
| IS-14 | 14,40,43,44,45,46,47,48,49 | all-views; F4 corresponding row | <attempt>/task-45/happy/; <attempt>/final/F4-fidelity.md |

Gate: registryunreviewed/waived/placeholder0;all20productsandnewlogisticscovered;mass/custody/orderinginvariants0violation;legacydata/demochange0;unexpectedbrowsererror0;agreedperformancepassesontargethardware;allF1–F4approve. Ifanyfail,workremainsunfinishedregardlessofdemo-dateoramountofcompletedcode.

