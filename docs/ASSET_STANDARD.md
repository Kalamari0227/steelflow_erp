# SteelFlow 운영 자산 제작·라이선스 표준

기준일: 2026-10-25. **T4는 자산 메타데이터와 제작 계약을 정의한다. 이 문서는 실제 모델 제작, Blender 설치, GLB 검사 또는 시각 품질 통과 보고가 아니다.** 계약 예제는 배포 자산이 아니다. 실제 source/export 파일이 없는 상태에서 해시나 검증 완료를 만들어 넣지 않는다.

기준 계약은 [자산 스키마](../shared/asset-manifest.schema.json), [기구 요구 정책](../shared/asset-requirements.json), [출처·커버리지 등록부](../shared/coverage-registry.json), [공정 출처 설명](FACTORY_PROCESS_REFERENCES.md), [승인 계획의 T4/T12/T19–29](../.omo/ulw-execute/steelflow-uniform-fidelity-factory/approved-plan.md)이다. 기존 40 kind·158 semantic variant·158 설비 배치는 시작 분모이며 새 장비와 배치를 면제하지 않는다. 등록부의 `pending_delivery`/QA `pending`을 본 문서 때문에 완료로 바꾸지 않는다.

## 제작 순서와 동일 품질 기준

1. 등록부에서 requirement, source, semantic variant, placement, QA ID를 먼저 선정한다. 기존 구현 목록만 보고 제조 요구를 역생성하지 않는다. 새 kind/variant는 독립 요구·검증 행과 정책 검토를 추가한 후 제작한다.
2. 실루엣, 고정 지지구조, 실제 기능부, 소재 entry/work/exit 및 load/grip/support 접점, 충돌 여유를 도면화한다. 치수·속도·기구 세부는 검증된 공개 근거가 없는 한 합성 설계라고 기록한다.
3. 같은 asset root 아래 고정 프레임·작업부·소켓·collision·절개 그룹을 제작한다. 움직이는 축과 피벗을 분리하고 rest pose를 고정한다. 소재는 별도 업무 entity이며 기계에 영구 복제하지 않는다.
4. LOD0 완성 후 원거리 LOD를 만든다. silhouette·작업부의 의미·소켓·업무 선택 ID를 유지한다. 모든 kind에 같은 polygon 수를 강제하지 않지만 상세 원본이 없는 저정밀 최종품은 허용하지 않는다.
5. 모든 모델·재질·텍스처의 provenance와 권한을 기록하고 계약 검사를 통과시킨다. T12에서 원본부터 재생성하여 실제 바이트/노드/축/피벗/텍스처/semantic hash를 검증한다.
6. 가족별 작업에서 3각도·근접·idle/running/blocked·pause/resume·full-cycle 영상과 실제 API/노드/소켓/픽셀 증거를 제출한다. geometry 공유도 variant별 의미와 배치별 접점 검사를 생략할 수 없다.

[시안 A](../design/mockups/2026-10-25/a-miniature-overview.png), [B](../design/mockups/2026-10-25/b-operations-map.png), [C](../design/mockups/2026-10-25/c-material-follow.png)와 [프롬프트](../design/mockups/2026-10-25/prompts.md)는 직접 확인한 미술 방향이다. 밝은 바닥, 청회색 긴 shed, 주황/황색 크레인, 설비별 다른 실루엣, 넓은 곡선 도로와 대기 공간, 용선 철도와 출하 철도의 분리, 원료·제품 부두 구별을 따른다. C의 절개는 동일 공장의 내부를 노출한다. 이미지 속 UI 수치·날짜·기구 치수는 제품 데이터나 공학 근거가 아니다. 화면 전체를 배경 이미지로 쓰거나 정적인 운영 장비를 덧붙여 시안을 복제하지 않는다. 선택 소재 한 개는 현재 custody 위치 한 곳에만 존재한다.

## 좌표·루트·노드·소켓

프로젝트 좌표는 meter, right-handed, Y-up, +X forward, radian이다. 소재 업무 치수 mm는 기하를 만들 때 정확히 m로 변환한다. 위치별 임의 배율 보정이나 음수 scale로 축 오류를 숨기지 않는다. root는 지면/기초 또는 명시한 적재 기준면에 두고 rest transform과 기준면을 기록한다.

**glTF의 전방은 +Z이며 프로젝트의 +X와 다르다.** glTF는 Y-up/right-handed/m/rad를 사용한다. 이름은 고유하지 않고 노드는 단일 부모의 비순환 계층이며 회전은 XYZW 단위 quaternion이다. 이 형식 사실과 아래 프로젝트 변환 정책을 구별한다. [Khronos glTF 2.0 고정 커밋, 좌표·이름·계층·변환](https://github.com/KhronosGroup/glTF/blob/7cee0fcddd5730e90d488bfb5aa2e52171483dde/specification/2.0/Specification.adoc#coordinate-system-and-units)

이 스키마의 제작 경로는 **Blender Z-up/+X forward → 프로젝트용 GLB Y-up/+X forward**다. `export.authoring_axes`는 `up="+Z", forward="+X"`, `export.conversion_rotation_xyzw`는 X축 −π/2 회전 `[-√0.5,0,0,√0.5]`(전체 부호 반전은 같은 회전)이다. `(x,y,z) → (x,z,-y)`로 +X 전방을 보존한다. 이것은 glTF 기본 front +Z와 다른 프로젝트용 기하 방향을 의도적으로 기록한 것이다. 일반 +Z-front glTF를 편입할 경우 Y축 +π/2인 `(x,y,z) → (z,y,-x)`로 프로젝트 방향에 맞춰 source에서 정규화해야 하며 이 경로를 별도 recipe에 남긴다. 프로젝트용 export에 importer가 같은 yaw를 다시 적용하면 실패다. T12는 원점, 전방/위/옆 축 marker, 비대칭 형상, 1m 기준선으로 실제 결과를 검사한다. Blender exporter 옵션만 켰다고 +X 전방 검증을 통과하지 않는다. 실제 exporter API·옵션의 확정과 검증은 T12 책임이다.

노드 표시 이름은 사람이 읽기 위한 힌트다. 참조는 안정적인 semantic node ID와 고유한 `locator` 계층 경로를 사용한다. T4는 LOD 사이 locator가 같은지 확인하며, T12가 이 경로를 각 GLB의 실제 node index/semantic ID와 대조한다. 재export로 index가 바뀌면 실파일 매핑을 다시 검사한다. 이름 검색 첫 결과에 부착하지 않는다. 부모 누락·순환·중복 ID·알 수 없는 node/part/socket 참조는 T4 실패다. 실제 clip/procedure의 존재와 대상 node 연결은 T12/T6의 후속 검사다.

내부 부품과 소켓의 local pose는 3D 위치와 정규화 quaternion을 사용한다. 회전축은 단위 벡터, 피벗은 해당 부모 좌표의 m, 범위는 회전 rad/직선 m, rest는 범위 안이다. 경사진 hook, ladle, drum을 world yaw 하나로 축약하지 않는다. T3 [worldContract.ts](../src/operations/scene/worldContract.ts)의 월드 배치는 position+yaw이며 이를 변경하지 않는다. 월드 접점은 `T_world_owner × T_root × T_parent… × T_local_socket` 전체 변환으로 계산한다. 평면 socket을 T3에 연결할 때만 yaw 표현 가능성을 확인하고, 경사 자세는 전체 quaternion/normal 비교로 별도 검사한다. 전달 순간 지지 접점의 거리와 custody 불연속 허용치는 **0.01m 이하**다. 중심점 일치만으로 통과하지 않는다.

support는 받침면, load는 차량/화차/선창의 적재 기준, grip은 hook/집게/포크의 인계 접점, entry/work/exit는 공정 경로 기준이다. 각 소켓은 node, local frame, 표면 normal, 허용 form과 kg 하중을 갖는다. 포크 간격, 코일 cradle, slab 받침, 선창 바닥은 형상별로 구분한다. 소켓은 mesh 중심의 별칭이 아니다. 고정 설비·정적 창고도 실제 지지와 충돌 proxy가 필요하다.

## 기구 동작·충돌·LOD·절개

모든 operational moving part에는 기능, 대상 node, local axis/pivot, 최소·최대·rest, clip 또는 procedural binding 하나를 둔다. binding은 서버 phase/progress를 입력으로 사용한다. wall-clock 반복, 카메라 진입, 로딩 완료, frame rate가 공정을 진행시켜서는 안 된다. 정지·장애 시 마지막 승인 pose와 적재물을 유지하고 재개는 같은 서버 상태에서 이어진다. 대기 중 이유 없이 blade/hoist/vessel이 반복 작동하지 않는다. 바퀴는 이동 거리, 조향은 경로, 작업부는 작업 phase에 연결한다. 기계 고정 본체는 움직이지 않아도 되지만 작업부를 generic roller로 바꿀 수 없다.

clip binding은 part의 대상 node와 서버 phase에 연결하고 실제 GLB 채널을 T12에서 대조한다. T4의 `clip_id`/`procedure_id`는 식별자 계약이며 구현 존재나 phase window 자체를 검사하지 않는다. T6/T12에서 실제 recipe와 채널/함수를 해석하고 검증해야 한다. 별도 자유 JavaScript나 metadata 문자열을 실행하지 않는다. 증기·물결·먼지 같은 decorative 효과는 따로 표시하며 제조·적재·이동 기능 충족으로 세지 않는다. 실제로 정적인 기초·랙·받침에는 고정 이유와 `binding:null`을 명시한다. 반면 `gas_tuyere`, `air_knife`, `thermal_chamber`, `electrode_bank`, `spray_header`, `acid_tank`처럼 물리적으로 고정된 작업 기능은 정책의 `state_bound_fixed_functions`에 따라 `fixed_parts[].binding.type="operational_state"`로 서버 phase/progress·pause/fault를 연결한다. 고정 상태 기능을 억지 geometric motion으로 대신하거나 operational part를 decor/fixed로 바꾸어 요구를 우회하지 않는다.


고정 부품은 실제 비퇴화 triangle 메시와 독립 동작이 없음을 검증한다. `binding:null`은 정책이 상태를 요구하지 않는 LF `ladle_support` 등에 허용하며 임의 state를 생성하지 않는다. 선택 필드 `fixed_to_part_id`가 없으면 기존 자산 root 기준 정지 의미를 유지한다. 현재 이 필드는 trusted AOD 정책의 `gas_tuyere → vessel_tilt` 한 관계에만 허용한다. gas_tuyere는 canonical rotation/clip vessel_tilt의 직접 자식이고 자기·자손의 animation/이동 부품·업무 socket·중복 의미 소유자가 없어야 한다. parent의 조상은 정지이며 LOD마다 동일 parent/locator/rest를 유지한다. 운영 상태 binding은 계속 필수이고 새 서버 채널이나 attachment 실행기는 만들지 않는다. 이 branch의 보고서는 `local_physical_motion:false`와 `inherited_from_part_id`를 분리한다. 정지 공급 manifold를 vessel 장착 tuyere 대신 제출하지 않는다. schema_version은 1을 유지하는 선택적 확장이며, 필드가 없는 기존 바이트의 의미는 그대로다. 구버전 parser는 새 필드를 거절하며 신규 AOD 원본·GLB·manifest는 새 content hash로 등록한다. 과거 export/fixture/archive 바이트를 다시 쓰지 않는다.

고정 위치에서 도는 여러 roll에는 좁은 `mechanical_follower` binding을 사용할 수 있다. 필드는 `type`, `driver_part_id`, finite/nonzero `ratio` 세 개뿐이다. driver는 같은 asset의 정책 필수 operational canonical `id=node_id=function`, rotation/rad, clip binding이다. follower는 driver와 같은 function을 가지며 독립 node/pivot/axis/mesh/sweep을 선언한다. 서로 조상이 될 수 없고 공통 정지 parent 아래에 두며, follower 자손에 업무 소켓을 붙이지 않는다. follower chain·translation/state driver·독립 phase/clock/자유 수식은 허용하지 않는다. 각 endpoint에서 `follower.rest + ratio × (driver_value − driver.rest)`가 follower range에 있어야 한다. `driver_value`는 기존 `MotionPose.channels[].value` scalar이며 2π/4π를 modulo하거나 quaternion에서 역산하지 않는다. adapter의 서버 함수 집합에는 follower를 넣지 않고 모든 canonical/follower pose 검증 후 한 번에 적용한다. pause/blocked/LOD 재진입도 같은 승인 scalar에서 다시 계산한다.

실제 rotation clip은 `d=min+(max−min)×t/T`, `q=Q(axis,value−rest)×q_rest`의 parent-frame PREmultiply 절대 local quaternion을 모든 sample에서 따른다. follower는 같은 driver clip과 정확히 같은 timeline을 사용하고 위 scalar 식을 따른다. 정적 node는 manifest의 rest transform을 유지하며 pivot은 node의 parent-frame 원점이다. finite/increasing time은 0에서 T>0까지, quaternion은 단위 길이·부호 동등성을 검사한다. driver와 각 follower의 인접 scalar 변화가 각각 **π 미만**이어야 하므로 0/2π/4π 세 identity key만으로 다회전을 입증할 수 없다. 미선언 target/다른 clip/animated scale·node.matrix·비단위/음수 scale은 거절한다. 기존 translation clip의 삼각형 왕복 규칙은 유지하며 runtime은 clip을 임의 재생하지 않는다.

EAF의 canonical moving 기능은 `electrode_lift`, `vessel_tilt`, `roof_swing`이다. 두 STS EAF recipe에만 `roof_swing`을 work window로 추가한다. roof carrier의 실제 Y축 pivot·별도 roof_shell·독립 electrode lift를 제작하고 장입 경로에서 실제로 회피시킨다. 절개는 roof_shell만 숨긴다. [ArcelorMittal 공정 설명](https://constructalia.arcelormittal.com/en/sica-steel-academy/properties-of-steel/manufacturing-and-forming-processes)과 [Tata Steel EAF 설명](https://www.tatasteeluk.com/eshot/how-will-our-consteel-eaf-work)은 전통 bucket 장입의 roof/전극 회피 기능 근거이며 실측 치수·현장 SOP·안전 인증은 아니다. family recipe의 `mechanical_basis`와 신규 source/hash 기록에 이 제한을 보존한다. 지원 archive는 저장된 domain/schema/reader/world 네 bytes를 읽으므로 현행 EAF 정책으로 소급 재검사하지 않는다. 과거 archive/fixture/T12 bytes를 수정해 현재 admission을 통과시키지 않는다.

AOD의 tuyere와 기울임 기능은 [Primetals AOD 설명](https://www.primetals.com/en/portfolio/solutions/steelmaking/aod-converter/), Air Knife의 가스 jet wiping은 [ISIJ International 원논문, 2020, §1](https://www.jstage.jst.go.jp/article/isijinternational/60/5/60_ISIJINT-2019-548/_html/-char/ja)에서 기능 개념을 확인했다. 따라서 고정 nozzle의 작동 상태를 요구하되 임의의 왕복 운동을 의무화하지 않는다. 논문의 실험 수치나 공급사의 특정 설계를 이 합성 공장의 검증된 치수로 옮기지 않는다.

collision proxy는 본체·작업부의 실제 외곽을 보수적으로 감싸고 node와 local pose에 연결한다. 회전/이동 부품은 전체 동작 범위 swept volume을 가진다. 소재와의 의도된 접촉 제외는 해당 socket에 한정하며 전체 설비 충돌 검사를 끄지 않는다. 초기 배치, 소재/차량 load envelope, 이동 경로 여유는 공간/스케줄러 작업에서 별도로 검증한다. T4 proxy 숫자 적합성이 실제 관통 없음의 증거는 아니다.

LOD0는 필수다. LOD 변경은 asset/entity/variant, node/part/socket/material semantic ID, hierarchy·locator·rest frame, binding과 custody를 보존한다. 작은 bolt나 비작동 외장 geometry만 줄이고 선언된 node는 유지한다. 롤의 접촉축·blade·hoist·coupler·적재 지지면을 제거하지 않는다. LOD별 실제 GLB index는 달라도 선언된 locator와 소켓 pose는 같아야 한다. roof/cutaway는 외피 node 집합을 숨기거나 fade하며 같은 interior를 유지한다. roof 숨김으로 기계·소재·collision·선택 ID·업무 상태를 교체하지 않는다. 건물 내부를 별도 전시 scene으로 재생성하지 않는다.

## 기존 40 kind 제작표

아래 표는 제작해야 할 최소 기능의 구체적 지침이다. 정확한 기계 판독 function/role 이름과 허용 family는 요구 정책을 따른다. 표의 축·치수는 실측 사양이 아니며 각 variant가 자신의 실제 local 축/범위/접점을 기록한다. 공개 source ID의 원문/제한은 [공정 출처 설명](FACTORY_PROCESS_REFERENCES.md)에 있다. `scope:approved-plan`은 합성 운영 범위다.

| kind | 실루엣·주요 작업부와 상태 연결 | 접점·variant별 필수 구별 | 제작 책임 / 근거 |
| --- | --- | --- | --- |
| `charge` | hopper·계량 gate·투입 chute; charge phase의 gate/feed | raw lot 수량·투입 support, 일반 roller 대체 금지 | T19 / 승인 범위 |
| `blast_furnace` | 고로·열풍로·출선층·출선 기구; tap phase | 용선 수용/래들 handoff; 전체 본체 회전 금지 | T19 / 승인 범위·P4 개념 |
| `bof` | converter shell·trunnion·lance; 장입/정련/출강 | vessel tilt와 ladle grip/load 분리 | T19 / 승인 범위 |
| `ladle_furnace` | 래들 지지대·전극 승강·덮개 | 래들 지지/인계, 정련과 운반 구별 | T19 / 승인 범위 |
| `eaf` | 전기로·전극·roof swing/tilt | scrap 장입과 출강 접점; STS variant | T19/T26 / M15·P1 |
| `aod` | 정련 vessel·tilt·출강부 | STS 정련/래들 인계, EAF 전극 동작 대체 금지 | T19/T26 / M15 |
| `caster` | ladle/tundish·mold·strand roller·cutting | slab/bloom/billet mold·출력 form·절단 위치 | T19/T26 / P4·M15 |
| `furnace` | 긴 가열 chamber·door·장입/추출 기구 | slab/bloom/billet/plate별 entry/work/exit | T20/T26/T27 / M0z·M10·M11·M15·M16 |
| `roughing` | 큰 stand·상하 roll·guide | 거친 압연 전후 단면/받침; 왕복 variant 명시 | T20/T26/T27 / M0z·M10·M15·M16 |
| `finishing_mill` | 연속 stand·work roll·guide | strip/plate별 경로; stand 간 지지 연속 | T20/T26/T27 / M0z·M10·M15·M16 |
| `bloom_mill` | bloom stand·roll·guide/transfer | bloom→billet, 형상·출측 지지 | T20 / M11 |
| `wire_mill` | 소형 다단 stand·wire guide | rod 경로·속도 phase, strip roller와 구별 | T20 / M11 |
| `cooling` | 냉각 header·roller table | 소재 이동과 냉각 구간; GI/GA/HGI/EG 순서 구별 | T20/T21 / M0z·M13 |
| `cooling_bed` | 긴 bed·이송 rack/roller | plate/billet/wire별 지지와 이송 방식 | T20/T26 / M10·M11·M15 |
| `coiler` | mandrel·wrapper·coil saddle | 회전축·직경 변화·coil 인계; 소재 중복 금지 | T20/T21/T26/T27 / M0z·M12·M15·M16 |
| `laying_head` | 회전 head·ring guide·냉각 conveyor | wire ring 형성/출력 support, coiler와 구별 | T20 / M11 |
| `shear` | blade/가스 절단 head·clamp·table | 기계 횡절단·가스절단·황삭가위 각각 variant | T20/T21/T26/T27 / M10·M11·M12·M15·M16 |
| `heat_treatment` | chamber·door·charging support | plate/STs 후판의 가열·배출, 열 효과는 decor | T20/T26 / M10·M15 |
| `leveler` | staggered leveling rolls·frame | plate/TLL 교정, strip/plate support 구별 | T20/T26/T27 / M10·M15·M16 |
| `uncoiler` | mandrel·coil cradle·pinch rolls | coil→strip 접점과 공급 phase | T21/T26/T27 / M12·M15·M16 |
| `pickling` | bath·guide roll·hood·rinse | CR/STS/Ti 경로·재료 구별; bath 장식으로 대체 금지 | T21/T26/T27 / M12·M15·M16 |
| `cold_mill` | cold stand·work/back-up rolls | strip 두께 변화와 entry/exit, Ti·STS variant | T21/T26/T27 / M12·M14·M15·M16 |
| `electrocleaning` | 전해 cell·strip guide·electrodes | 세정 기능/침지 경로, 도금과 구별 | T21 / M12 |
| `annealing` | furnace·transport roll/door | continuous/batch·CAF/CAPL·GO/NGO 처리 구별 | T21/T26/T27 / M12·M14·M15·M16 |
| `temper` | skin-pass stand·roll·guide | 조질과 본압연 기능·압하 구별 | T21/T26 / M12·M13·M15 |
| `oiling` | applicator·nip/transport roll | 후처리 위치·strip 지지, spray decor만으로 실패 | T21 / M12·M13 |
| `galvanizing` | zinc bath·sink roll·Air Knife | GI/GA/HGI 기재와 냉각; EG cell과 구별 | T21 / M13·P1 |
| `alloying` | GA 합금화 furnace·strip transport | 도금 뒤/냉각 전, GI에 강제하지 않음 | T21 / M13 |
| `electroplating` | electrode cell·strip guide·transport | EG 전해 경로, 용융욕 대체 금지 | T21 / M13 |
| `coating` | coating rolls/head·dryer·transport | GO base coat/최종 절연·NGO 절연 별도 | T21 / M14 |
| `decarburizing` | 탈탄 furnace·strip transport | GO 탈탄 단계와 입출구; 일반 소둔과 의미 구별 | T21 / M14·P2 |
| `forging` | press/hammer·anvil·manipulator | Ti ingot→slab; stroke·clamp·받침, 허구 상류 금지 | T27 / M16·P3 |
| `vacuum_annealing` | 밀폐 chamber·door·coil support | Ti VAF의 loading/treatment/unloading | T27 / M16·P3 |
| `slitter` | rotary blade pair·guide·recoiler | STL 길이방향 분리; SHL 횡절단과 구별 | T26/T27 / M15·M16 |
| `inspection` | 검사 table·probe/scanner·이송부 | 품질 hold/retest, 후판 초음파는 별도 제조 요구 | T29 / 승인 범위·M10 |
| `packaging` | saddle/table·strap/wrap 기구 | 제품 형상별 결박/포장·내부 후공정 포장 생략 조건 | T29 / 승인 범위 |
| `stock` | rack·coil cradle·slab dunnage | 정적 support 허용, 실제 stock slot·허용 form 필수 | T29 / 승인 범위 |
| `delivery` | dispatch bay·gate·계량/상차 접점 | 도로/철도/해상 leg 선택, 운영 차량은 별도 entity | T29 / 승인 범위·P5 |
| `port` | quay·berth·bollard·하역 접점 | 원료/제품 분리; 크레인은 transport ID 참조 | T29 / 승인 범위·P5–P7 |
| `ship` | 선체·deck/hold·hatch·선창 support | 기존 campus 장면과 실제 transport 선박 identity 중복 금지 | T28/T29 / 승인 범위·P5–P7 |

기존 kind 40개를 구현해도 원문 기능 전부를 충족한 것은 아니다. T2의 추가 요구인 Scale Breaker·용접기·Looper·Shot Blasting·Air Knife·EG Oven and Cooler·GO 자구 미세화·베이스 도포·후판 마킹/초음파·황삭가위·구간별 출측 절단도 각 source requirement와 의미 부품/variant/QA로 연결한다. STL로 출측 횡절단을 대신하거나 GO 자구 처리를 일반 검사로 흡수하지 않는다. Ti TLL 뒤 냉연코일/STL-Skelp/SHL-Sheet 분기는 원문대로 구별한다. HGI 전용 도식 미확인은 명시적 adaptation으로 유지한다.

## 신규 운송·물류·건축 자산

새 운송 kind는 운영 개체의 일부다. 작업이 없어도 존재하며 empty/loaded/return/blocked/fault 상태를 같은 identity로 표시한다. 고정 crane, unloader, stacker, conveyor의 root는 고정 가능하지만 작업부·소재는 서버 상태에 반응해야 한다. 다음은 승인 범위의 제작 설계이며 실제 사업장 SOP/장비 치수 증거가 아니다.

| kind / 범위 | 제작할 기구·소켓·검증 경계 |
| --- | --- |
| `truck` | dump와 flatbed variant; wheels/steering, dump hinge 또는 적재 deck·결박. slab/coil 적재 support와 턴/하역 sweep. |
| `slab-carrier` | 낮은 운반 chassis·다축 wheel/steering·들어올리는 받침; slab load socket과 lift phase. |
| `coil-carrier` | coil saddle/cradle·wheel/steering·lift; 코일 축과 받침 normal, 낙하 없는 handoff. |
| `forklift` | mast·carriage·fork·wheel/steering; fork lift/tilt, grip와 load 중심/허용 kg. |
| `torpedo` | 용선 vessel·trunnion·bogie·coupler; 철도 이동과 vessel tilt 별도, 용선 인계. |
| `ladle-car` | ladle support·bogie·coupler; ladle/hook grip와 차체 load, 용선차 형상과 구별. |
| `locomotive` | body·bogie/wheel·front/rear coupler; consist 순서·역주행·곡선과 coupler 간격. |
| `railcar` | bogie/wheel·coupler·deck/cradle; coil/slab/bulk variant, 적재와 하역 접점. |
| `ship` | bulk/product variant; hold/deck·hatch/도어와 load sockets; berth→loading→sea→unloading 상태. propeller/wake만으로 하역 기능 충족 불가. |
| `crane` | overhead/yard/port variant; bridge·trolley·hoist 또는 slew/boom, hook/grab. grip과 load의 1cm 인계, 본체/부품 sweep. |
| `unloader` | quay gantry·boom/trolley·hoist/grab 또는 연속 하역 head; ship hold→hopper 접점. |
| `stacker` | rail/chassis·slew/luff boom·belt/분배부; 실제 raw lot 공급/적층, 입자는 decor. |
| `reclaimer` | bucket wheel/grab·slew/luff·belt; 야드 lot 회수와 downstream 접점. |
| `conveyor` | belt/drive·idler·chute·지지대; bulk 이동·전달, 고정 root와 작동 belt 구별. |
| `hall` | 기존 31 hall + 신규 receiving/rail/port/customer 동: 구조 frame·roof·door·내부 통로·cutaway. roof와 retained interior ID를 고정한다. |
| receiving / weighing | 검수·계량대·하역 bay·원료/스크랩/구입 반제품·코일/Ti ingot 보관; 도착→검수→계량→하역→stock 접점. |
| inspection / quarantine / retest | 검사 장비와 격리 rack/slot, hold 상태 물리 보존, 재검 동선. 제조 초음파/자구 처리와 업무 품질 경계 구별. |
| packaging / warehouse | 형상별 포장·결박·rack·coil cradle·slab 받침과 적재 여유; stock custody·상차 연결. |
| dispatch / rail / quay / customer | gate·대기열·turning apron·rail block/coupler 여유·berth·고객 하역/보관. 캠퍼스는 실제 transport/공정 ID를 참조하고 정적 복제품을 넣지 않는다. |

receiving/warehouse/customer 등의 설명을 새 kind 문자열로 임의 제출하지 않는다. 현재 정책에 있는 kind/variant와 requirement에 명시 매핑하거나 검토된 정책 추가를 먼저 한다. 도로·rail·berth·slot 배치는 T8, 물류 로직 T9/T11/T15–17/T22–25, 운송 자산 T28, 건물·구역 자산 T29, 실제 동작 연결 T31/T32 책임이다. 시각 reference만으로 이 작업들의 완료를 주장하지 않는다.

## 재질·텍스처와 권리 추적

기본 모델과 procedural texture는 직접 제작하며 **기본 외부 자산 수는 0**이다. 직접 제작은 CC0 선언이나 외부 공개 허가를 의미하지 않는다. creator, 제작 recipe와 원본 경로/해시, 사용한 외부 input, 프로젝트 배포 권한을 기록한다. procedural texture도 생성 recipe·seed·출력 파일과 색 공간·해시가 필요하다. 외부 input을 사용한 결과를 순수 self-created로 표시하지 않는다.

PBR 재질은 안정적인 material ID와 base color/metallic/roughness 및 texture slot을 가진다. base-color/emissive의 sRGB와 normal/metallic/roughness/occlusion의 linear 의미를 구별한다. 각 texture는 로컬 resource와 provenance를 갖고 GLB에 포함된 이미지도 누락 없이 대조한다. 텍스처 없는 재질은 명시적으로 빈 목록이며 존재하지 않는 가짜 texture를 넣지 않는다. 최종 번들에 원격 texture URL 의존을 남기지 않는다. 원문 스크린샷·로고를 재질로 복사하는 것은 공정 참고와 다른 권리 사용이다.

외부 모델·텍스처는 명시적으로 확인된 `CC0-1.0` 또는 `CC-BY-4.0`만 허용한다. 검색 결과의 “free”, 다운로드 성공, 출처의 일반 푸터만으로 통과하지 않는다. 실제 개별 자산 페이지/파일 URL, 제목, 저작자, 원본 해시, license URL, 확인 날짜, 자산과 license를 연결하는 보존 증거/해시, 변경 내역, attribution을 모두 기록한다. NC/ND/unknown·라이선스 누락·텍스처 출처 누락은 실패한다. CC0에도 프로젝트 provenance 기록은 필수다. CC0의 권리 포기 범위에는 상표·특허 및 타인 권리의 보장이 포함되지 않는다. [CC0 법문 §4](https://creativecommons.org/publicdomain/zero/1.0/legalcode.en)

CC BY 4.0 배포에는 제공된 저작자/지정 attribution, 저작권·license·면책 고지, 가능한 원문 URI, 변경 표시와 이전 변경 이력, license 링크/본문을 보존한다. bundle attribution 파일과 해시를 해당 resource에 연결한다. 이 admission 정책은 개별 자산의 권리 관계를 자동 보증하지 않는다. [CC BY 4.0 법문 §3](https://creativecommons.org/licenses/by/4.0/legalcode.en#s3)

## 메타데이터 필드 계약

최상위 필드는 `schema_version:1`, `purpose:"contract_example"|"production"`, `assets`다. 허용되지 않은 필드는 실패한다. 다음 필드는 `assets[]` 기준이며 정확한 타입·필수 여부는 스키마, 상호 참조와 kind별 최소 기능은 별도 정책/런타임 검증기의 책임이다.

| 필드 | 작성 계약 |
| --- | --- |
| `id`, `family`, `category`, `kind`, `variant` | category는 equipment/fleet/campus. family는 steelmaking/hot-rolling/finishing/stainless/titanium/transport/campus. 임의 family-kind 조합 불가. |
| `requirement_ids`, `qa_row_ids`, `placement_ids` | T2 요구·QA 대상·variant 배치를 함께 대조한다. ID가 존재한다는 사실만으로 다른 설비의 QA를 빌릴 수 없다. |
| `source_refs[].id`, `uri`, `note` | source ID 또는 연결한 requirement ID, 실제 근거 URI, 제한/합성 해석. 등록된 source면 URI도 일치해야 한다. |
| `coordinate_system.length`, `up`, `forward`, `handedness`, `angle` | 각각 m/+Y/+X/right/rad 고정. |
| `root_node_id`, `nodes[].id`, `parent_id`, `locator`, `transform` | 단일 root. root transform은 위치 [0,0,0], 회전 [0,0,0,1]로 정규화; 배치는 T3에서 적용. 모든 transform은 `position_m[3]`, `rotation_xyzw[4]`. |
| `sockets[].id`, `node_id`, `role`, `transform`, `normal`, `forms`, `max_load_kg` | role은 support/load/grip/entry/work/exit/coupler. normal은 단위 벡터, forms는 스키마의 허용 소재형, 하중은 양의 안전 정수 kg. |
| `moving_parts[].id`, `node_id`, `function`, `role`, `motion`, `axis`, `pivot_m`, `range`, `binding` | role operational/decorative, motion rotation/translation. `range.min/max/rest/unit`에서 max>min·rest 범위 내·rad/m 일치. |
| `moving_parts[].binding` | `procedural`/`clip`은 selector 하나와 공통 server_sim phase/progress/hold/rest 필드를 사용한다. `mechanical_follower`는 `type`, canonical `driver_part_id`, finite/nonzero `ratio`만 가지며 위 회전 전용 제한을 따른다. |
| `fixed_parts[].id`, `node_id`, `function`, `reason`, `binding`, optional `fixed_to_part_id` | binding null 또는 `type=operational_state`, `clock=server_sim`, `phase`, `progress_source=server_phase_progress`, `pause=hold`, `fault=hold`, `rest=inactive`, `state_id`. 정책의 고정 상태 기능은 null 불가. |
| `cutaway.roof_node_ids`, `interior_node_ids`, `retained_socket_ids` | roof-required 정책이면 roof/interior 비어 있으면 실패. roof의 자손으로 interior/기구/socket을 숨기면 실패. roof가 없으면 나머지도 빈 목록. |
| `materials[].id`, `model`, `base_color`, `metallic`, `roughness`, `textures`, `provenance` | model metallic-roughness. 색 RGBA·metallic·roughness 0..1. `textures[].slot/texture_id`는 선언된 texture에 연결. |
| `textures[].id`, `artifact`, `color_space`, `provenance` | srgb/linear는 slot 의미에 일치. 사용하지 않는 orphan texture, 중복 slot, 미등록 texture를 거절. |
| `collision_proxies[].id`, `node_id`, `shape`, `transform`, `size_m`, `purpose`, `part_id`, `contact_socket_ids` | shape box, 양의 xyz 크기. body는 part_id=null, moving_sweep는 실제 moving part ID. body 1개 이상과 모든 moving part의 sweep 필요. |
| `lods[].level`, `artifact`, `semantic_geometry_sha256`, `nodes`, `socket_ids`, `part_ids`, `material_ids` | level 0..3, LOD0 필수, 서로 다른 .glb 경로. 선언된 전체 node 구조·locator·transform과 모든 semantic ID 유지. built이면 semantic hash 필요, unbuilt이면 null. |
| `source.artifact`, `source.provenance` | 편집 가능한 .blend source와 권리/recipe. provenance는 재질·텍스처에도 각각 필수. |
| `export.tool`, `version`, `tool_artifact`, `recipe`, `settings`, `authoring_axes`, `conversion_rotation_xyzw`, `world_boundary` | Blender/4.5.15 고정. settings는 format=GLB/y_up=true/apply_transforms=true/animations=true. authoring axes +Z/+X, conversion은 위 Rx(-π/2), world_boundary=yaw_root_full_quaternion_internal. 설정은 선언이며 실제 exporter 작동 증거 아님. |

공통 artifact는 `{status:"unbuilt",path}` 또는 `{status:"built",path,sha256}`다. path는 프로젝트 상대 경로이며 traversal/절대 경로 금지, SHA256은 소문자 64자리 hex다. `self_created` provenance 필드는 `origin`, `creator`, `title`, `license="project-owned"`, `distribution_permission="project-local"|"redistribution-authorized"`, `recipe`, `third_party_inputs`다. 외부 input ID는 추적 가능한 external resource여야 한다. `external` provenance 필드는 `origin`, `creator`, `title`, `license`, `source_url`, `download_url`, `license_url`, `evidence`, `original`, `verified_at`, `modification_note`, `attribution`이다. evidence/original/attribution은 built artifact다. 실제 바이트 검증은 T12의 책임이다.

정책의 `required_functions`/`fixed_functions` 각각에 canonical `part.id = part.node_id = function`이 필요하고, `required_socket_roles`마다 `socket.id = role`가 필요하다. 추가 detail ID는 허용해도 이 최소 anchor를 대체할 수 없다. 동일 category/kind의 variant 사이 기존 부품·소켓 의미 ID를 유지한다. follower 개수는 variant별 명시 집합에 따라 다를 수 있으나 각 follower 전체의 node/driver/axis/pivot/range/ratio와 모든 LOD의 part ID를 검증하며 기존 non-follower 부품 비교를 생략하지 않는다. `planned_bindings`는 14 fleet와 8 campus의 현재 계약 예제 연결이며 실제 새 placement 완료 등록이 아니다. 8 campus kind는 `hall`, `receiving-inspection`, `weighbridge`, `gate`, `raw-yard`, `warehouse`, `berth`, `customer-dock`이다. receiving-inspection은 inspection_scan, gate는 barrier_lift가 필요하며 나머지 고정 지지는 각각 정책의 structural_support/weigh_platform/stockpile_support/rack_support/berth_support/customer_support를 따른다. hall/warehouse는 roof 절개가 필수다.

`policies[].id`와 binding의 `policy_group_id`는 검토된 기구 정책을 연결한다. kind 수준 `families`는 상위 허용 범위일 뿐이다. 기존 158 variant/placement의 실제 family는 `existing_bindings[].allowed_families`로 더 좁게 고정한다. `stage_family_policy` 24행과 `placement_family_overrides`의 명시적 SHIP→transport 행이 근거이며 `shared_mesh_exceptions=[]`로 공유 mesh 예외는 없다. 예를 들어 carbon CUT-SLAB의 kind가 shear라는 이유로 titanium family를 제출하면 실패해야 한다. `scope:carbon-upstream`·stage ID는 과거 요구/공간 identity로 유지되지만 asset family는 `steelmaking`이다. 신규 실제 배치와 variant도 이 독립 연결 정책을 검토해 추가해야 한다.

계약 예제 [asset-manifest-valid.json](../shared/fixtures/asset-manifest-valid.json)은 source/export hash를 허구로 넣지 않은 작성 예시다. [manifest.ts](../src/operations/scene/assets/manifest.ts)의 `parseAssetManifest(raw)`/`parseAssetManifestValue(value)`는 메타데이터를 검증해 deep immutable 결과를 반환한다. `parseProductionAssetManifest(raw)`는 production purpose와 built artifact/LOD semantic hash를 추가로 요구하지만 파일을 읽지 않는다.

| 실패 입력 | 현재 T4 검사 위치·관측 | 후속 실제 검증 |
| --- | --- | --- |
| 중복 key/escaped 동일 key, 미지원 version/추가 field | raw parser의 duplicate key 오류, schema 실패 | GLB 내부 JSON과 byte inventory는 T12 |
| kind/family/variant/placement/QA 위조, canonical ID 변경 | `identity`의 requirements/reference/identity 오류 | 실제 instance↔entity 연결은 가족 QA |
| moving binding 누락·decor/generic loop 대체, 고정 상태 binding 누락 | schema 또는 `identity`의 requirements 오류 | 서버 phase와 실제 화면 동작은 T6/T12/가족 QA |
| 비단위 quaternion/axis/normal, 틀린 conversion/root, 범위/단위 오류, NaN/Infinity/unsafe 값 | schema 또는 `hierarchy`의 numeric 오류 | 실제 GLB 변환·피벗·1m 기준선은 T12 |
| cycle/unknown node/socket/part | `hierarchy`의 reference 오류 | 실제 clip/procedure 존재·채널 대상은 T12/T6 |
| missing body/sweep·unknown contact socket, roof가 내부 삭제 | collision/reference/requirements 오류; contact_socket_ids는 선언된 socket만 | 실제 sweep/관통·과도한 접촉 제외 여부는 T12/공간 QA |
| LOD0 누락·node/locator/pose/socket/part/material drift | `lods`의 lod/identity/artifact 오류 | 실제 GLB geometry/LOD 전환 접점은 T12/가족 QA |
| NC/ND/unknown·출처/texture 누락·색 공간·외부 input 세탁 | schema 또는 `resources`의 license/reference/requirements 오류 | 외부 권리 증거 진위·실제 embedded image 전수는 T12 |
| contract_example를 production으로 사용·unbuilt/hash 누락 | production admission의 artifact 오류 | 파일/hash/semantic 재현 비교는 T12; JSON 통과를 built proof로 사용 금지 |

이 표는 실제 parser 구현을 읽어 정리한 검사 책임이며 본 문서 작업이 parser test 통과를 대신 주장하지 않는다. T4 실행 담당은 `npm test -- src/operations/scene/assets/manifest.test.ts -t valid`, `-t license_or_binding_missing`, 전체 파일 검증과 raw parser의 성공/실패 입력·정확한 오류를 evidence에 기록한다.

## 검증 단계와 완료 경계

T4 fixture는 계약 예제이며 실제 source/GLB가 없는 항목은 unbuilt다. `built` 및 hash 문자열의 JSON 적합성은 파일을 읽었다는 증거가 아니다. production manifest에 placeholder를 넣지 않는다. production 허용은 실제 존재하는 source/recipe/toolchain/texture/GLB 바이트와 T12 receipt를 대조한 뒤 판단한다.

| 단계 | 실제 확인할 것 | 증거와 한계 |
| --- | --- | --- |
| T4 metadata | version, 타입/필수 필드, 중복-safe JSON, 참조/정책, 단위/범위, provenance, LOD 일관성 | parser 입력·오류·exit·immutable 출력. 모델/렌더링/라이선스 페이지 진위 검증의 대체 아님. |
| T12 pipeline | 공식 Blender 4.5 LTS Apple Silicon 4.5.15 및 checksum 고정, source→blend→LOD GLB/texture 재생성, 같은 T4 validator 호출 | toolchain·recipe·source·output byte hash, 실제 nodes/clips/material/image 목록, 축/scale/pivot/socket/sweep 검사. 아직 구현되지 않은 경로를 완료로 표시하지 않음. |
| T12 reproducibility | timestamp 제외 geometry/mesh/name/animation semantic hash, resource inventory, 축/피벗/texture/scale/node 손상 거절 | 독립 재빌드 2회의 명령/exit/semantic 비교, 실패 원본. binary GLB byte hash와 semantic hash를 혼동하지 않음. |
| T19–21/T26–29 family | 모든 kind/variant, placement, 정상/대기/장애/정지/재개, 실제 소재 지지·인계·선택 | 3각도·근접·full-cycle 연속영상 + API revision + 실제 bound node + 화면 픽셀 + 독립 검토. JSON-only 통과로 fidelity 완료 불가. |
| T40/T43–45 전수 | 신규 포함 모든 요구·경로·leg·variant·placement와 실제 업무/시각 증거 연결 | 40 모델 또는 158 기존 배치만으로 전체 완료를 선언하지 않음. |

T12 예정 경로는 `assets/toolchain.json`, `scripts/assets/build.py`, `scripts/assets/verify.mjs`, `assets/source/<family>/`, `public/assets/steelworks/<family>/`, `src/operations/scene/assets/pipeline.test.ts`다. 아직 없는 파일은 향후 deliverable이며 본 문서의 링크 검증 대상이나 실행 성공 증거가 아니다. 승인 계획과 스키마 family는 steelmaking/hot-rolling/finishing/stainless/titanium/transport/campus다. EAF/AOD 등은 정책상 stainless family이며 T19의 공용 제작 recipe 재사용과 실제 variant family admission을 혼동하지 않는다. T12의 `reproducible`, `reject_corrupt`, 가족별 `full-cycle`, `bad-pivot-or-binding` 시나리오는 해당 작업에서 실제 실행하고 evidence를 남겨야 한다.

공개 공정 도식은 기능과 순서의 근거다. myPOSCO 8개 URL은 2026-10-24 캡처·2026-10-25 재조사 제한이 기록되어 있고, 현행 페이지 전체 재확인이나 실측 기계 도면으로 취급하지 않는다. HGI 전용 도식 부재·Ti 분기 adaptation·역사 자료의 현재 설비 미확인·치수/속도/현장 SOP 미확인은 유지한다. 본 문서는 기존 등록부를 읽어 출처 범위를 승계하며 새 현장 조사로 날짜를 바꾸지 않는다.
