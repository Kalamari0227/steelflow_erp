# T21 — finishing 전체 자산 / 공유 계약 보완 실행 인계 (SEALED)

읽기 전용 Astra High 결정. 제품 수정0. T21 시간08:52:32Z→12:52:32Z 유지. 모델 역할 설정만 확인 가능한 근거이며 숨겨진 attestation은 주장하지 않는다. 기존 T19/T12 및 T62/T15 동시 작업을 보존한다.

**범위는58 variants /58 placements /16 kinds +29 원문 기능이다.** 원문 기능29개는 추가29 asset을 뜻하지 않으며, `supplement-map.json`의52 requirement-host associations로58개 안의 실제 서브어셈블리에 배치한다. HGI HR-feed는 비기하 진입 규칙이고, entry-and-exit 한 association은 실제 두 looper를 요구하므로52를 물리 부품 수로 세지 않는다. 모든 exact IDs/기존 routes/functions/세계 datum/3LOD 파일명은 `inventory.json`, 사람용 전수 표는 `matrix.md`,29개 host 표는 `supplement-map.md`가 이 결정의 일부다.

## 현재 사실과 실행 순서

CR8/GI8/GA9/HGI8/EG8/GO10/NGO7. Kind 수는 uncoiler7,pickling4,cold_mill3,electrocleaning4,annealing8,temper4,oiling5,coiler7,galvanizing3,coating7,alloying1,leveler1,electroplating1,decarburizing1,heat_treatment1,inspection1이다. 원 plan에 짧게 열거되지 않은 coiler/leveler/heat_treatment/inspection도 포함한다. source.blend58개, 실제 GLB174개가 최소 산출물이다. 같은 kind 색만 바꾼 복제는 variant 수락이 아니다.

`shared/factory-world-v2.json`의 work rest datum은55개 [0,2,0], galvanizing3개 [0,1.76,0]이다. 편의상 모두1.32m로 바꾼 world fixture를 최종 same-world 증거로 쓰지 않는다. asset rest support/실제접점이 해당 canonical datum에 맞아야 한다. 원631 owner/footprint/world bytes는 수정하지 않는다. 추가 support/entry/exit socket을 쓰는 고립 fixture는 명시적으로 derived test world이며 T52 최종 bundle integration을 대신하지 않는다.

실행은 (A) 아래 공유/domain correction을 ROOT가 새 supplemental row에 등록·소유권 배정한 뒤 구현, (B) 그동안 독립 finishing geometry/source authoring, (C) 교정된 immutable contract snapshot으로58+29 전체 테스트 순이다. B의 기본58개가 생성돼도 A/29기능/올바른 forms를 빼고 T21완료라고 하지 않는다. ROOT의 최신 인계에 따라 T15 최종 확인과 dependency hash freeze 해제는 완료됐다. 공유/domain 수정에는 여전히 ROOT의 별도 supplemental 등록·소유권 배정이 필요하며 T62 소유 경로는 현재 인계 전까지 유지한다. 이 문서 편집은 제품 변경 권한을 추가하지 않는다. T62 현재36Py/63TS/26CLI와 tilt repair는 부분근거이며 전체 physical gate 합격으로 승격하지 않는다.

## 선택한 공통 표현과 실제 full-cycle

기존 T58 canonical channels/실제 socket transform/retained custody를 사용한다. 독립 가동부는 독립 canonical channel, 같은 축속도에 실제로 결합되는 roller만 T61 follower다. 일괄 회전 parent, 장식 animation, mixer, wall-clock, frame마다 바뀌는 socket/support_local은 금지한다.

1. **직선 강체 strip**: T62 `linear_roller_feed`를 정확히 만족하는 구간만 사용. radius×angle=travel, 실제 regular cylinder/COM 양측/폭/원 범위/3LOD 전경로 증명을 재사용한다. bent path, coil, batch charge, 두께가 공간적으로 달라지는 reduction mesh에는 붙이지 않는다.
2. **coil winding/unwinding**: T20 고정점 일부권취를 전체완료 증거로 재사용하지 않는다. 이번 coiler/uncoiler는 실제 mandrel의 grip/clamp에 work socket을 두어 T58가 실제 회전점/방향을 투영한다. clamp는 시작 전에 실제 소재 끝을 잡고 끝까지 유지하며 외부 coil 제거/다음 설비 release는 T32 범위다. 4m finite strip 전체 centerline 길이를 보존하는 bounded family forming view를 사용하고, canonical angle만으로 shape를 구한다. reverse가 uncoiling이다. same material/version은 한 projection phase에서 불변; 완료 output version/폼은 명시적 retained fixture history로만 전환한다. 미완료 tail이 있으면 전체권취 완료라고 표시하지 않는다.
3. **bath/looper/curved threading**: 직선 T62를 억지 적용하지 않는다. 실제 roll tangent+원호 및 finite straight spans로 연결한 하나의 strip centerline, 정확 arc-length 좌표, 해당 canonical feed/looper scalar만 사용하는 family-local forming view. 재료 길이는 변하지 않는다. 고정된 work point는 선언한 phase 전체 동안 실제 소재와 기구가 접촉하는 위치여야 한다. 맞지 않으면 실제 moving grip/socket 또는 명시적 retained transfer를 설계한다. 거대한 소재로 모든 socket을 덮거나 고정 datum만 비교해 이동을 숨기는 방식은 금지. whole stock 통과와 finite feed stroke를 구별하여 recipe에 원래부터 선언하고 같은 범위를 끝까지 검증한다.
4. **cold reduction**: 하부/상부 work rolls와 backup rolls, 실제 nip를 만든다. 소재의 임의 순간 두께 치환은 금지. synthetic asset fixture의 finite strip 한 개가 nip을 통과하면서 전후 구간 길이×폭×두께가 보존되는 bounded piecewise forming law를 사용한다. 입력4m×1.2m×.004m→출력8m×1.2m×.002m가 기본 숫자다. 조질은 별도 얇은 skin-pass fixture이며 cold reduction 비율을 강제하지 않는다. business MaterialVersion에는 시작 input과 승인된 completion output을 별도 불변 레코드로 두고, view의 진행중 형상은 `synthetic forming view`임을 명시한다. T31의 라이브 생산형상 API 완료 주장은 하지 않는다.

모든 view는 기존 T58가 승인한 `MotionPose.channels[].value`만 받는다. 별도 독립 `feed` 값으로 소재를 움직이지 않는다. backend pose와 geometry/contact를 함께 기록한다. family-local forming renderer를 새 범용 motion wire/physics engine으로 만들지 않는다. T58 parser 통과 자체가 curved mesh/두께/체적/접촉 증명은 아니므로 실제 mesh 검증을 별도로 필수 수행한다.

### 실행 가능한 coil 수학 기준

core R=.44m, sheet t=.002/.004/.006m, width1.2m, total neutral-axis length4m. R0=R+t/2, k=(t+.0002)/(2π), spiral centerline radius r(φ)=R0+kφ. 식 `S(θ)=∫0..θ sqrt((R0+kφ)^2+k^2)dφ`로 전체길이4m가 되는 θmax를 유일하게 구한다. `forming-math.json`에서 θmax는 각각9.037865009,8.988668238,8.940304411rad이고 적분 길이4m를 직접 확인했다. .2mm layer clearance는 합성 mesh 설계값이지 실공장 winding tension/밀도 수치가 아니다.

world inner-end angle은 π/2−θ이고 mandrel/clamp도 정확히−θ로 회전한다. centerline φ=0의 실제 inner face를 clamp jaw에 고정하고, tail/guide 접속은 C1이며 arc-length 합이4m가 되도록 구성한다. work rest socket의 world-local 위치는 [0,2,0]에 맞추고 mandrel center는 그 아래 R만큼 배치한다. `support_local`은 clamp patch 기준으로 한 번 결정한 상수다. geometry는 이 실제 moving anchor 좌표계에서 작성한다. tail budget, adjacent layers/intersection, grip patch, shaft/bearing load path, entry/exit apron을 실제 모든 θ에서 검증한다. 위 적분만으로 접촉 PASS를 주장하지 않는다. guide 접속 길이가 필요하면 전체 길이 식에 포함하고 동일4m로 θmax를 다시 풀어 recipe/evidence에 명시한다;4m를 늘리거나 미권취 tail을 숨기지 않는다. 완전 uncoil 마지막에도 끝단은 실제 clamp에 남는 phase이며 외부 release를 완료한 척하지 않는다.

## 16종 제작 규칙 / IO / 원본 차이

모든 input/output form은 matrix의 현재값과 아래 교정표를 따르고, stage/제품 label·grade/route provenance를 보존한다. 표의 치수는 합성 fixture 입력이며 실제공장치수 아님. 기본 strip은 width1200mm, length4000mm, STRIP4mm(명시 HGI6mm), THIN_STRIP2mm, COATED_STRIP은 substrate와 같은 nominal bulk thickness다. coating 상태를 같은 면의 재질/검증값으로 표현하며 겹친 coplanar decal mesh를 만들지 않는다. 코팅 질량/화학은 현재 asset proof에서 새로 주장하지 않는다. form별 snapshot MaterialVersion와 envelope 치수는 항상 일치한다.

| kind / 주요 대상 | 실제 구조 및 declared cycle | canonical / 추가·follower | 소재/지원 |
|---|---|---|---|
| uncoiler7 | cantilever mandrel, 실제 clamp, bearing/headstock, coil cradle, threading apron; full finite4m winding shape의 reverse, 종료 후 끝단 clamp 유지 | unwinding_mandrel; roller만 ratio follower; outlet welder는 별도 채널 | HR/CR coil→STRIP 의미 유지; 실제 장력 경로/코일과 strip 한 connected mesh |
| pickling4 | acid_tank, liners, 덮개/배기/순환배관, 입출측 bridle와 rinse section; finite strip feed→처리상태→출측 | pickling_feed + acid_tank state; CR scale breaker, GO/NGO shot wheel/exit looper/cutter 별도 |4mm strip, 실제 bath 내부 clearance; 단순 roller line을 산세로 부르지 않음 |
| cold_mill3 | CR tandem 다중stand, GO/NGO 각 등록 variant의 reduction stand/backup rolls·screwdown/hydraulic chocks; 실제 nip 전후 두께/길이 | cold_reduction_roll, 같은속도 upper/lower backup roller followers; CR output cutter/intermediate winder | 위4→2mm 체적 보존; pressure 없는 dry-run을 reduction 완료라고 하지 않음 |
| electrocleaning4 | 실제 brush, conductive electrode section, spray/rinse/drain, 두 독립 drives | cleaning_brush + strip_feed; 고정부는 구조물, operational 표시가 필요하면 명시 state 등록 | CR thin2mm, GI/GA/EG strip4mm; brush/contact와 stock clearance 실제 확인 |
| annealing8 | CR/GI/GA/HGI/GO/NGO source 단계별 chamber/tube/zone/entry seal/exit cooling 차이; 예비/최종/평탄화 구분 | anneal_feed + thermal_chamber; loopers/uncoiler 추가 목록 적용 | 일반직선은 T62, 실제 multi-pass는 bounded curved strip. GO08 재투입 coil uncoiling 포함 |
| temper4 | compact skin-pass stand/backup rolls와 guide/tension section; cold mill처럼 과장된 reduction 금지 | temper_roll, 독립 roll followers | thin/coated strip, correct nip/support |
| oiling5 | oiling_feed, nozzle/spray header, catch tray, mist hood, service tank; feed/분사/hold 종료 | oiling_feed + spray_header state | substrate form/nominal dimensions 유지; marker/color-only 동작 금지 |
| coiler7 | 실제 mandrel clamp/wrapper/drive/headstock/supports; full finite4m winding, 실제 output coil family 구분 | winding_mandrel + wrapper/roller followers; mapped cutter/scan은 독립 | CR/GI/GA/HGI/EG/GO/NGO coil IO 별도; canonical clamp와 실제 mesh 접촉 |
| galvanizing3 | zinc pot/refractory, submerged sink roll, snout, stabilizers, 양면 air knife, 상향 strip와 cooling section | sink_roll + air_knife state, GI/HGI coating_cooling state; GA cooling은 alloying 뒤 | 실제 침지→원호→상향 wiping. work datum1.76m 유지, normal을 무조건 +Y로 검사하지 않음 |
| coating7 | GI/GA/HGI passivation, EG06 phosphate/EG07 anti-fingerprint, GO09/NGO07 insulation을 실제 applicator/tank/oven 배치로 구분 | coating_roll; GO base coater는 별도 GO06; EG oven/cooler/NGO drying 추가 | 올바른 input forms; 얇은 surface state는 실제 작업폭/진행위치에서만 |
| alloying1 | GA 전용 induction/radiant heating enclosure, 실제 feed, 후속 cooling | induction_feed+thermal_chamber+coating_cooling | coated strip; GI/HGI에 이 단계를 강제하지 않음 |
| leveler1 | EG tension leveller의 교대 small rolls, entry/exit bridle, tension/frame | leveling_roll+독립 roller followers | STRIP, 실제양면경로/지지; straight-feed가 정확맞는 경우만 T62 |
| electroplating1 | EG electrode banks/전원bus/solution cells, bridle, 배수/순환; electrochemical state는 actual electrode bank | plating_feed+electrode_bank state | STRIP→COATED_STRIP; 용융욕/AirKnife로 대체 금지 |
| decarburizing1 | GO 탈탄 chamber/radiant tubes/feeding, entry/exit loopers, 별도 downstream base coater/cutter/intermediate winder | decarb_feed+thermal_chamber + supplement-map | thin strip→base-coated intermediate cold-rolled coil; final insulation 아님 |
| heat_treatment1 | GO07 실제 batch-coil bell furnace: base/seal/hood, charge-car, guides/actuator/lifting support, 열상태 | treatment_feed=실제 coil charge-car translation; bell_lift 독립 translation; thermal_chamber state | CR_COIL intermediate→동일 form, closed bell에서 처리. 이동 thin-strip tunnel로 바꾸지 않음 |
| inspection1 | GO10 제조용 domain-refinement scanner/laser shielding/head traverse; 품질검사 station 아님 | 기존 inspection_scan=실제 제조 head traverse, domain_laser state 추가 | COATED_STRIP 유지; 제조이력과 검사판정 구별 |

같은 kind에서도 부품수·line layout·입력물·source function이 다르면 별도 recipe row다. 최초부터 side/front/top+closeup에서 실제 geometry를 확인한다. 대량 생성 후 실루엣을 뒤늦게 교정하는 순서를 쓰지 않는다. 첫 representative는 uncoiler, cold_mill, galvanizing, GO07, coating EG/GO 두 의미, looper/cutter다. 하지만 대표 합격이58 전체 합격을 대신하지 않는다.

## ROOT 신규 supplemental row용 공유 계약 보완 — T21 authoring와 별도 소유

### S1. 명시적 opt-in으로 선택하는 placement별 추가 독립 함수

`shared/asset-requirements.json.existing_bindings[]`에 선택 필드 `additional_functions`와 `extension_policy_id`를 한 쌍으로 등록한다. `additional_functions`의 정확 구조는 `{moving: Text[], state: Text[]}`, `extension_policy_id`는 `policy:equipment:finishing:<OWNER>:v1` 형식의 ID다. 두 필드 모두 누락이면 기존 base-only binding이다. 한쪽만 존재하거나 explicit null, unknown field, 중복 함수, base와 중복, moving/state 집합간 중복이면 reject한다. 등록 대상과 함수는 `supplement-map.json.additional_functions_by_owner`의42 owner 목록과 정확히 일치한다. **이 catalog 등록은 선택 가능한 확장 대안을 제공하며 해당 owner의 모든 자산에 확장을 강제하지 않는다.** user frame/manifest가 함수를 자기 선언해 admission을 늘릴 수 없다.

42개 binding의 기존 `policy_group_id`는 변경하지 않는다. 추가 policy42개는 base policy+exact additional 함수의 한 단계 평탄화된 복사다. base와 확장 함수집합의 차이는 등록한 additional과 정확히 같아야 하며 kind/family/socket/roof는 같다. 임의 상속/chain/cycle/다른 owner의 대안은 reject한다. base40 kind 목록을42새 kind로 세지 않는다.

Manifest Asset의 선택 필드 `motion_policy_id?: Id`를 `shared/asset-manifest.schema.json`과 `src/operations/scene/assets/manifestShape.ts`에 함께 등록한다. **필드 누락은 언제나 기존 base policy 선택**이다. explicit null/unknown ID/다른 placement의 extension은 reject한다.42개 새 finishing 자산은 자기 extension ID를 명시하고 나머지16개는 base를 유지한다. 기존 T12/T19/T20 manifest bytes는 필드 없이 그대로 base로 읽는다. 특히 보호된 `steelflow:galvanizing:CS-GI-05` T12 production asset은 같은 owner의 새 catalog에 `coating_cooling`이 등록돼도 base를 유지하며 그 부품을 새로 요구하지 않는다. 새 T21 CS-GI-05만 자기 extension을 명시하고 `coating_cooling`을 실제 구현한다. T21 신규 family 완전성 검사는42개 opt-in/16개 base를 assert하여 새 자산이 필드를 생략해 요구를 피하는 것을 막는다. 이 완전성 검사를 legacy manifest admission에 적용하지 않는다.

하나의 effective-policy helper는 (category, kind, 정확 placement binding, **asset의 명시 선택 또는 누락에 따른 base**)으로 선택된 한 policy를 검증한다. owner만으로 함수를 자동 합치거나 first matching kind로 extension을 고르지 않는다. `bindingsFromAssetManifest`는 이 선택을 기존 `AssetBinding.policy_id`로 투영한다. admission은 해당 owner의 base 또는 등록된 자기 extension만 허용한다. T58 wire에 새 필드는 없다.

source recipe는 compiled_steps의 `equipment_id`로 허용된 owner 대안을 찾는다.42개 확장 owner에 해당하는 host source recipe에는 기존 base policy 대안과 새 extended policy 대안을 함께 선언하고, 나머지16개의 base 함수집합은 S1 때문에 바꾸지 않는다. 각 대안의 functions는 해당 policy의 정확한 전체 함수집합이며 `f.policy_id === binding.policy_id`로 한 대안만 선택한다. 같은 source를 여러 compiled products가 재사용하면 owner/등록 대안 집합이 일치해야 한다. policy별 같은 function metadata 두 행은 선택 대안이며 두 실제 node/channel을 뜻하지 않는다. old base-only recipe는 계속 parse/evaluate 가능하다. extension binding+base-only recipe는 binding reject, extended 대안의 함수 누락은 registry/exact-function reject다. current new registry 완전성 검사는42개 extended 대안 전부를 별도로 assert한다.

선택된 extension의 모든 추가 moving은 id=node_id=function인 canonical part, 모든 추가 state는 같은 canonical fixed part 및 operational_state다. independently driven clamp/cutter/lift를 follower로 위장하지 않는다. follower는 선택된 policy의 실제 rotation canonical driver에만 연결한다. manifest kind lookup, follower canonical-driver, fixedFrames, state binding, variantSemantics 모두 같은 선택 규칙을 사용한다. legacy/base와 extension을 비교할 때 공통 base canonical parts를 계속 비교하고 선택된 exact 등록 extra만 차이를 허용한다. 미등록 extra 또는 base를 선택한 자산의 extension-only part는 manifest 단계부터 reject한다. 소켓 semantic role/identity 및 LOD 검사는 유지한다.

정확 신규 helper는 `backend/app/operations/motion_effective_policy.py`, `src/operations/scene/motion/effectivePolicy.ts`다(양언어 동등 closed catalog projection). 좁은 호출부는 `backend/app/operations/{motion_policy.py,motion_admission.py,motion_registry.py,motion_coverage_sources.py}`(CoverageStep에 equipment_id 읽기), `src/operations/scene/motion/{context.ts,registry.ts,assetAdapter.ts}`, `src/operations/scene/assets/manifest.ts`다. shared `asset-requirements.json`과 `motion-recipes.json`은 위42개 등록/선택 대안만 S1 범위로 변경한다. manifest schema/shape는 위 선택 필드만 확장한다. MaterialVersion/Attachment/SQL 확장은 없고 기존 closed channel shape를 유지한다.

필수 호환성 검사는 기존 T12 GI05 raw manifest/GLB를 수정하지 않은 base admission, 같은 owner의 명시적 새 extension admission, field 누락 시 base 선택, 잘못된 owner/unknown/null ID 거절, base-only legacy recipe 성공, extension+base-only recipe 거절, extended 함수 누락 거절, 새 family42/16 및 registry42 완전성이다. 세대가 다른 자산을 같은 manifest에 비교할 때도 base 공통부품 의미와 exact extra 허용을 검증한다.

`motion:src:<supplement>`의 현재 unresolved recipe를 근거 없이 resolved로 바꾸지 않는다. T21은 정확 host source recipe의 실제 canonical channel과29 source-ID별 QA로 이 기구를 증명한다. T18의 실제 source-subphase orchestration이 등록되기 전 그 generic recipe를 호출하면 계속 실패해야 한다. requirement→host association은 새 별도 `shared/finishing-subassemblies.json`(schema_version1, 목록은 supplement-map.rows의 exact fields)로 고정하고 T21 metadata/QA가 읽는다. 이것은 runtime graph/scheduler가 아니다. 요구 완료 상태는 실제 증거 뒤 ROOT가 반영하며 prep에서 coverage status를 바꾸지 않는다.

### S2. COATED_STRIP 직선 feed

현재 `evaluate_internal_feed`에 직사각형 COATED_STRIP을 넣으면 `form: COATED_STRIP`으로 거절되는 것을 실제 호출로 재현했다. Python `motion_internal_feed.py`와 TS `internalFeed.ts`의 허용 form에 **COATED_STRIP 한 값만** 추가한다. 기존 양의 L/W/T, diameter=null, identity orientation, constant lower-face offset, fullpath COM/actualroller/limits 모두 충족해야 한다. 코팅으로 body topology가 바뀌거나 coil/곡선인 경우에는 여전히 reject. 기존 `FORM_FAMILIES['COATED_STRIP']==['STRIP']`와 일치한다. 새 field/스키마/SQL 없음. 현재 T62 소유자가 완료 인계한 뒤 ROOT가 이 두 경로만 추가 등록한다. coated rigid positive + coil/curved/diameter/지지부족 negatives를 양언어 동일 seed로 검증.

### S3. 정확한 중간 coil 형태 교정 (새 enum/DB migration 없음)

실제 GO 고온소둔은 intermediate coil의 batch annealing이다. [Tenova 공식 brochure](https://tenova.com/sites/default/files/files/solutions/2023/LOI_Steel_Strip_HPH_EN.pdf)는 GO의 탈탄·도포 후 high-temperature bell annealing을 설명하고 실제 coil/bell 구조를 제시한다. 로컬 `electrical.png`도 베이스도포→절단/coil→고온소둔을 표시한다. 현재 GO07 THIN_STRIP→THIN_STRIP와 tunnel rendering은 이와 맞지 않는다.

기존 HR_COIL은 열연 기반 중간 coil, CR_COIL은 냉연된 중간 coil이라는 **물리 form**으로 재사용한다. 판매 제품/최종 GO 합격 여부는 product/grade/route lineage/quality로 결정한다. 중간 CR_COIL이라고 제품을 cr 주문으로 바꾸거나 GO_COIL 완제품으로 조기 선언하지 않는다. 기존 row에는 이 가공상태를 보여주는 cause event/batch lineage가 있고 화학명/새 재질을 발명하지 않는다.

원본 `backend/app/data/journey_products.json`은 불변. `backend/app/data/operations_routes.json`에 선택 `form_overrides` 목록을 추가하여 source compiler 뒤 정확 다음9 source IDs의 input/output만 교정한다. 구조 `{source_step_id, input_form: MaterialForm|null, output_form: MaterialForm|null}`; null=원래값 유지, 두 값 모두 null/중복/알수없는source/미등록override reject. default omitted=[]로 기존 pinned config를 그대로 읽는다.

| source | 새 input(빈칸=유지) | 새 output |
|---|---|---|
| cr-04 | 유지 | CR_COIL |
| cr-05 | CR_COIL | 유지 |
| go-04 | 유지 | HR_COIL |
| go-05 | HR_COIL | 유지 |
| ngo-04 | 유지 | HR_COIL |
| ngo-05 | HR_COIL | 유지 |
| go-06 | 유지 | CR_COIL |
| go-07 | CR_COIL | CR_COIL |
| go-08 | CR_COIL | 유지 |

CR04는 reduction→출측cutter→중간권취, CR05는 실제 line_unwinding_mandrel로 재투입. GO/NGO04 산세뒤 cutter/coil→05실제 uncoiler. GO06 탈탄뒤 basecoat/cutter/coil→07 bell batch→08실제 uncoiler/평탄화소둔. 총 source187/compiled step 수는 임의 삭제·증가하지 않으며 named subassemblies가 현재step내에 명시 매핑된다. 원래 function order/공정단계는 유지한다. HGI는HR직접투입이며CR강제없음. 신규 MATERIAL enum/SQL migration 필요없음.

정확 변경 경로: `backend/app/operations/catalog.py`의 RouteDefinition/compile 적용과9개검증, `backend/app/data/operations_routes.json`; catalog에서生成되는 현재 `shared/coverage-registry.json`의 해당 compiled step forms, 해당 motion recipe meaning/bindings/fixtures와 sourcehash를 정식 generator로 갱신. `tools/qa/coverage.py`/`coverage_inventory.py`는 실제生成명령에 필요한 경우만; 손으로 전체coverage를 재작성하지 않는다. 새 데이터는 새bundlehash, oldpinned bytes/187원본source 및 기존 T12/T19를 덮지 않는다. 기존 forms가 보존되는 old config parse regression, 새9개연결 continuity, GO07 COIL socket/material dimensions, HR/CR grade/provenance 보존, 부적합 직선feed 거절을 검증한다. 기존 catalog의20products/질량/분할/검사출하 경계 validators는 약화하지 않는다.

GO07 fixture 입력은 실제 intermediate CR_COIL(예:OD1400/ID600/폭600mm, 축Y로세운coil)이며 phase중 dimensions/version 불변이다. 실제 car→base support 인계는 retained T58 Boundary로 같을시각 actualcontact≤.01m. bell_lift는그후닫힘→열hold→냉각→열림; car가닫힌bell을관통하지않는다. work datum과 true world coil pose/방향을 함께 검사한다. 이 실제 batch기구를 임의 elevator feeding으로 재해석하지 않는다.

## 공통 제작·소유 파일

Sol의 기본 소유는 신규 `assets/source/finishing/` 전체: `recipe.json`, `build.py`, `geometry.py`, `details.py`, `transmission.py`, `uncoiling.py`, `strip_treatment.py`, `rolling.py`, `thermal.py`, `coating.py`, `electrical.py`, `subassemblies.py`, `manifest.py`, `render.py`, `verify.mjs`, `README.md`, `LICENSE.txt`, 생성58 `.blend`, `mechanics.json`, `inventory.json`, `contracts/source-contracts.json`. 기존 hot-rolling/steelmaking 코드를 live import하지 않고 필요한 primitive를 provenance/hash를 남겨 새 소유dir로 가져온다. source snapshot을 복사해 독립성 확보하되 보호된 원본은 편집하지 않는다. 무료 Blender4.5.15/직접 만든PBR재질만, 외부 유료asset0.

산출물은 `public/assets/steelworks/finishing/<exact-owner>-lod0/1/2.glb`,family manifest. 원본174GLB semantic ID/part/socket 동일,48/32/16 또는입증된그이상 원통세그먼트, 실제closeupLOD에서도 원형/얇은sheet/축/받침/곡면 유지. 뷰확대에서 reference planes/ground가기구와coplanar겹치지않게설계한다. T19 actual coplanar 검사의 triangle positive-area witness0 기준을 재사용하고 이름만다른겹친판을숨기지않는다.

신규 `tests/fixtures/finishing/{main.tsx,poses.ts,material.tsx,forming.ts,diagnostics.tsx,surface.ts,contracts.json,corrupt.ts,parser.mjs,parser.d.mts,vite.config.mts,index.html,style.css}` 및 `tests/assets/finishing.spec.ts`. T20/T19 fixture 자체를 수정하거나 테스트 출력 경로를 공유하지 않는다. synthetic snapshot에는 input/output version과release/acquire기록을보존하고기존ID의form/dim/socket을매frame몰래바꾸지않는다.

`scripts/assets/build.py`는 ROOT가 허용할 때 `--family finishing`을 새 build.py에 전달하는 dispatch 한 분기만 수정한다(기존 T19 dispatch/기본T12동작 보존). output root 필수, 새 빈 owned root만. source/manifest top aggregate설치, app catalog/world integration은prep/authoring밖이다. legacy wrapper가 oracle을 위해필요하면 isolated output root내부에서만 만들고 protected top-level 파일은안건드린다.

미술은 `docs/FACTORY_VISUAL_STANDARD.md`/visualTokens/T19 accepted재질 원칙 그대로다. teal/blue housings, 노출 steel, 실제 feet/bearing/shaft/support/light/cutaway. 열색은 승인된 phase상태, label은기구/접점가림0. 제품별실제차이를밝기/색만으로대체하지않는다.

## 기본값·오류·증거 / 완료 gate

- catalog의 additional_functions/extension_policy_id 쌍 누락은 legacy base-only, manifest의 motion_policy_id 누락은 해당 owner에 확장이 등록돼 있어도 base 선택, form_overrides 누락은 기존 forms 유지다. 부분 등록/explicit null/unknown fields/unsupported kind/channel/body는 fail closed(각 form_overrides 항목의 input_form/output_form null=유지 규칙은 S3대로다). unknown형상은placeholder나loop로통과시키지않는다. 움직임범위0→0 held도T63exact규칙보존.
- 각 테스트는 **명시 manifest root + expected raw SHA256 + family=finishing + exact owner/variant/LOD집합**을 preflight한 뒤시작한다. 루트가다르면첫단계실패. evidence는`.omo/evidence/uniform-fidelity/uf-20261030-resume06/task-21/<attempt>/<owner>/...`로고유하게잡고기존root/다른runproof를덮지않는다. buildA/B reproducibility도각기다른output과실제bytehash를기록한다. E↔C경로오표기재발금지.
- 전체58개3view+closeup, idle/running/blocked/paused/resume/fullcycle/end, video/decodedframes,3LOD재취득동일scalar/동일businessID.29개각요구별52host associations의명명기구·순서·독립채널·접촉 별도assert. 한host의동영상으로다른제품배치를자동PASS하지않는다.
- 실제 dual-surface triangle normals/vertices/거리≤.01; curved/side/borecontact는진짜기구normal을사용한다. upward-onlyfilter로반대면을없애지않는다. 동일시각hand-off에서oldpoint≤.01 유지, T62구간은추가root/quaternion/cornersguard유지. 모든 geometry 검사는현재decodedmesh와numericphase사용;boundingbox만으로접촉증명금지.
- stock/fulltravel/부품별sweep/COM/apron/door/hood/rollnip/shaft/index/guide/collision을초기대표부터검사한다. connector에서arc-length손실,mesh분리,curve끝튐,완성coil의숨은tail,coinincident두께판을negative로검사한다. weld두끝/clamp/접합, cutter하강/분리/복귀, looper축적/방출은실제두기구상태를보여야한다. 단순막대 왕복을용접/절단으로승격하지않는다.
- 현재 old58/T61/T63/T62형식·scalar·time·custodyregressions, 새effectivepolicy/catalog/COATED_STRIP양언어sharedseed·실제CLI. malformedextra,wrongownerextensions,forgedadditionalfunctions,coiledmaterialonlinearfeed,wrongGOform,wrongSHAroot,missingpart/emptyLOD/wrongpivot/binding 모두reject. 전체58 bad-pivot-or-binding negatives도각각기록한다.
- geometry完成한시점의독립visual reviewer全항목PASS+실제sourcehashseal+cleanup뒤T21완료. 全factory/T18/T31/T40/T43/T52완료는별도이다. 반대로그후속행을이유로이번29기구나현재assetfullcycle접촉을생략하지않는다.

## 현재 prep 증거 / 한계

`inventory.py`로trustedJSON의형태를읽고58/58/16/29 정확수를assert했다. `current-seam-probes.json`은현Python제품함수를직접호출하여COATED_STRIP form reject 및새independent clamp unknown_function을재현했다. `forming-math.json`은finite4mspiral각도해의수학feasibility일뿐actualmeshPASS아니다. localPOSCO4도식(cold/coated/GO/NGO)을직접열람했고Tenova공식GO자료를검색확인했다. sourcehash/정리는`evidence.json`.

제품수정0, DB/보호포트/서버/Blender/브라우저실행0, agent추가0. 짧은읽기/probe프로세스만종료했고신규evidence만남긴다. T62현재파일은계속변할수있으므로implementation시ROOT가최신seal에재바인딩해야한다.

## 최종 봉인 보충 — range와 실제 형태 전환

현재 T4 policy는 required function identity를 정하며 coiler/uncoiler의 전역2π 한계를 두지 않는다. 현재 `movingPart.range`는 instance manifest의 finite min/max/rest이고 T61는 unwrapped scalar 및 clip sample 회전분해를 검증한다. **accepted T20 range는 그대로2π**. T21 새 instance recipe에만 위4m의 θmax를 min0/maxθmax/rest0으로 고정한다. 해당 authored clip/node/manifest/fixture binding이 정확히 그 범위를 공유해야 한다. 원래2π asset을 읽고 frame binding만9rad로 늘리는 것은 reject이다. 모든 cycleθ는 이고정범위 안이며 endpoint는strict bound에맞춰exact수치로사용한다. 새 범용range helper나policy waiver는 필요없다.

범위표: initial uncoiler CR/GO/NGO(HR기재)t=.004→8.98866823752605rad; GI/GA/EG(CR기재)t=.002→9.037865009051153rad; HGI t=.006→8.940304411421494rad. final coiler CR/GI/GA/EG/GO/NGO는t=.002, HGI는t=.006. 중간 CR04/GO06 winding과다음unwinding은t=.002, GO04/NGO04와다음unwinding은t=.004. guide접속을추가하면동일4m integral에그길이를포함한해를recipe생성시한번구하고새manifest에고정한다. runtime은고정descriptor만읽는다. 이 표의 적분수치는guide없는centerline feasibility이며미완성guide/endpoint를PASS로인용할수없다.

**한 socket family는한번에STRIP/COIL둘을뜻하지않는다.** 현재 BindingSocket.family는단일값이므로동일work socket의family를frame마다바꾸는것은금지한다. 새coiler는실제mandrel clamp에동일물리point를갖는별도 `coil_support` socket을선언한다(work=STRIP,coil_support=COIL). uncoiler는work=COIL,종료용 `strip_support`=STRIP이다. 둘은같은실제clamp node/접촉면/동작chain을참조한다. actualfunction동일값에서옛/새socket world contact가같으며기존T58retained release/acquire를같은at_ms에만적용한다. 신·구attachment ID와material version레코드는모두남긴다. 이런추가socket을admit하는testworld는canonical owner/pose/footprint/segment를보존한명시derived copy에소켓만단조추가하고manifest를남긴다. 기존canonical bytes/pinned bundle은불변. 최종공장추가socket등록은T52에인계한다.

최종形成frame→새form/version frame은 **동일world material vertices/triangles**를사용해야한다. input/output geometry 객체를새로만드는경우전체world vertex대응거리≤1e-6m,동일surface topology/centerline길이/체적을확인한다. 버전/폼만바뀌었다고원통proxy로바꾸거나원점을이동해coil을튕기면실패. frameorigin표현이바뀌면 `M_new*vertices_new == M_old*vertices_old`를검증하고기존same-timecontact≤.01도별도로검사한다. 기존T58typedboundary에서actualsame material ID/previous version/current version과socketfamily를통과시킨정확seed를양언어로확인한다. 이는syntheticasset fixture의明示history이고실제T10/T18/T31producer가내보낸liveevent라고주장하지않는다. 자식materialID로실제분할되는cut은T10의별도entity/lineage기록을따르며T58same-IDboundary로가짜rename하지않는다.

coil output dimensions는실제최종mesh의core/outer径/폭과고정arc length4m/두께를보존한다. 코일의void를filled cylinder volume으로계산하지않고`L*W*t`를계산한다. winding/unwinding경로전체같은값이어야한다. source geometry는한connectedsheet이며wrapper나duplicatecoilmesh로가려서는안된다. 새outputversion의grade/product/cause/처리상태도route와일치하고GR/NGO를COIL색으로만구분하지않는다.

cold-reduction의boundedview수학은nip원통반경R, exitthicknessTout, inletTin에대해upstream gap(x)=Tout+2*(R-sqrt(R²-x²)), thickness(x)=min(Tin,gap(x))이고downstream는Tout이다. 소재의Lagrangian 길이좌표를각구간단면적에따라배분해W∫t(x)dx=Win*Tin*Lin을보존한다. exit tangential feed=R*θ일때input feed=R*θ*Tout/Tin; 따라서위4m/4→2mm full-strip예의최종각도는8/R이다. 실제nip/입출측guides가이형상과맞는지triangle clearance로확인한다. partialreduction상태에서원version의businessdimensions를덮지않으며completion에만새version으로동일실제mesh를넘긴다. 유효한signedclearance를증명하지못하면범위/두께/길이를줄여통과시키지말고구조를수정한다.

### 현재 base function 단위/범위 근거

**현재 base function 단위/범위에 대한 실제 답**: (a)mandrel rotation 0..9.037865009051153rad/axis[0,0,-1], (b)GO07 treatment_feed translation −2..0m/axis[1,0,0]는둘다기존`BindingFunction.mechanics`의finite ordered range/normalized axis/id==node 검사와`motion_admission.validate_binding`의moving-vs-state검사를통과했다. canonicalworld의실제CS-CR-09/CS-GO-07 owner로직접실행한`base-function-probes.json`이근거다. MotionRecipe의moving은rotation/translation중하나를전역고정하지않고실제typedmechanic과채널이일치해야한다. manifest movingPart 역시rotation(rad)/translation(m)를허용하고실제clip/node/pivot가선택과일치해야한다. 따라서이둘은새base-unit override 규칙이필요없다. GO07에는internal_feed를선언하지않으며T62의rotation-only규칙은그대로다. 새bell_lift는S1extension에만추가하고T20heat_treatment는기존rotationtreatment_feed를그대로쓴다. 위probe는metadata admission이지새GLB동작/완성bell extra함수PASS가아니다.
