# 실제 Blender 자산 파이프라인

T12는 무료 Blender 4.5.15 ARM64로 직접 제작한 절단기와 도금 설비를 재생성·검사한다. 실제 편집 원본, 3단계 LOD GLB, 절차적 PNG, production manifest를 포함한다. 외부 모델·텍스처·유료/AI 서비스 입력은 0개다. 치수는 합성 설계이며 실제 사업장 설비 사양이 아니다.

## 고정 도구와 입력

[toolchain.json](../assets/toolchain.json)은 공식 DMG URL/SHA256, 실제 실행 파일 경로/SHA256, ARM64 아키텍처, `--version` 원문과 도구 라이선스 파일 SHA256을 구별해 기록한다. 설치 위치는 `~/Library/Application Support/SteelFlow/tools/blender/4.5.15-macos-arm64/Blender.app`다. 기존 앱을 덮어쓰거나 quarantine·보안 설정을 변경하지 않았다. 공식 DMG SHA256은 `bfbc0bda099d1ab7aef0992a584f872f58bed9bb491210ad45f9ca071aa2e688`, 실제 실행 파일 SHA256은 `d85bac46c9cc9ae7e64ecdc5a647db28af60959eb7df65e030657ff9e0ed8299`다. 버전·실행 파일 해시가 다르면 빌드가 중단된다.

[recipe.json](../assets/source/recipe.json)에 seed, 대상 variant, 기존 T4 계약 입력, LOD segment 수, 실제 축 marker 좌표와 제한을 둔다. [build.py](../scripts/assets/build.py)가 원본 geometry·UV·PBR·25샘플 clip을 생성한다. [inventory.json](../assets/source/inventory.json)은 실제 원본·입력·텍스처·라이선스 해시를 기록하고, 각 GLB 해시는 [production manifest](../public/assets/steelworks/manifest.json)의 LOD에 기록한다. 외부 자산을 쓰지 않았다는 사실과 별도 GPL 도구 사용을 구별한다. 원본의 권한은 [LICENSE.txt](../assets/source/LICENSE.txt)의 project-local이며 임의 공개 재배포 권한을 주장하지 않는다.

현재 검증 환경은 Node 24.18.0, 저장소에 이미 설치된 npm 패키지다. 새 패키지나 의존성 업그레이드가 없다. 기존 TypeScript production admission parser는 설치된 esbuild로 **메모리 안에서** 묶어 호출한다. 전역 module hook, 임시 JS 번들, 원격 module import를 만들지 않는다.

## 실행

프로젝트 루트에서 실행한다. 출력은 신규 또는 빈 디렉터리만 허용한다. 실행 전에 해당 출력과 `runtime` 디렉터리를 자신의 자원 기록에 등록한다. 아래 `RUN`은 매번 새 이름으로 지정한다. 다른 작업자의 출력·기존 `dist`·DB·서비스 포트를 사용하지 않는다.

```sh
RUN="$PWD/.omo/evidence/asset-pipeline-manual-001"
mkdir -p "$RUN/runtime/tmp"
export TMPDIR="$RUN/runtime/tmp"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX="$RUN/runtime/pycache"
export BLENDER_USER_RESOURCES="$RUN/runtime/blender"
export XDG_CACHE_HOME="$RUN/runtime/cache"
export NODE_COMPILE_CACHE="$RUN/runtime/node"
export BUN_RUNTIME_TRANSPILER_CACHE_PATH="$RUN/runtime/bun"
export npm_config_cache="$RUN/runtime/npm"

"/Users/ethanlee/Library/Application Support/SteelFlow/tools/blender/4.5.15-macos-arm64/Blender.app/Contents/MacOS/Blender" \
  --background --factory-startup --python-exit-code 1 \
  --python scripts/assets/build.py -- --out "$RUN/build-a" --render
node scripts/assets/verify.mjs --root "$RUN/build-a"

"/Users/ethanlee/Library/Application Support/SteelFlow/tools/blender/4.5.15-macos-arm64/Blender.app/Contents/MacOS/Blender" \
  --background --factory-startup --disable-autoexec --python-exit-code 1 \
  --python scripts/assets/render.py -- --root "$RUN/build-a" --out "$RUN/render"
```

`build.py`는 source `.blend`와 PNG를 생성하고 실제 Blender exporter로 GLB를 쓴다. `stamp.mjs`는 새 manifest에만 실제 semantic hash를 채운 뒤 전체 검증을 실행한다. 이미 hash가 있는 manifest를 재서명하지 않는다. 검증 성공 뒤에만 `STEELFLOW_BUILD_COMPLETE`를 출력한다. 실패한 출력은 삭제/덮어쓰기하지 않고 다음 새 디렉터리로 수정된 원본을 빌드한다. 외부 runner는 Blender를 180초 안에 종료하도록 제한한다. 내부 Node 검증 subprocess도 60초로 제한된다.

`render.py`는 각 `.blend`를 실제로 다시 열고 semantic node와 packed texture를 확인한다. 이후 GLB를 새 장면에 import하여 front/side/rear의 동일 clip frame 0과 quarter/midpoint/three-quarter frame 6/12/18을 렌더한다. 반 바퀴에서 원통이 대칭으로 보이는 경우에도 quarter의 실제 roll index 이동을 확인한다. 모든 캡처에서 Air Knife 행렬이 고정인지 검사한다. 원본/GLB/이미지 SHA256, 카메라, 프로젝트 좌표의 실제 노드 행렬을 `render-receipt.json`에 쓴다. 임의 벽시계 애니메이션이나 T6 서버 동작으로 해석하지 않는다.

시험은 명시 Node 환경과 각 120초 timeout을 사용한다. 자식 Blender는 실제 pinned executable로 실행하고 exit/signal/stdout/stderr를 보존한다.

```sh
ASSET_PIPELINE_EVIDENCE_ROOT="$PWD/.omo/evidence/asset-pipeline-test-001" \
  npm test -- src/operations/scene/assets/pipeline.test.ts \
  --config scripts/assets/vitest.config.mts --configLoader runner
```

`-t reproducible` 또는 `-t reject_corrupt`로 한 시나리오를 선택할 수 있다. 테스트는 자체 신규 출력/캐시를 등록한다. npm 프로세스 자체의 cache도 실행자 소유 경로로 설정한다. 검증 후 실행자의 `runtime`만 정리하고 로그·실패 원본·산출물은 증거로 보존한다. 설치 앱은 계속 사용하는 도구이므로 유지한다.

## 실제 바이트 검사

[verify.mjs](../scripts/assets/verify.mjs)는 기존 `parseProductionAssetManifest`를 먼저 호출한다. 다음 항목은 별도 [GLB 검사기](../scripts/assets/glb.mjs)가 실제 바이트를 읽어 판정한다.

- artifact 경로의 traversal/URL/루트 밖 symlink 거절, source/license/recipe/texture/GLB 해시와 pinned 도구 해시 대조.
- GLB header·chunk·embedded buffer·accessor bounds·유한값·삼각형 index·normal·UV·PBR·PNG 압축 pixel·image 참조 검사. 외부 URI를 로드하지 않는다.
- 실제 semantic ID의 유일성, locator·부모·루트·rest pose·unit scale을 LOD별 계약과 대조한다. 비대칭 arrow mesh와 origin/front/up/side의 실제 world 좌표를 통해 1m 기준선, Y-up, +X 전방을 확인한다. export 옵션만 보고 판정하지 않는다.
- 실제 clip/channel/target node와 25개 샘플을 검사한다. shear는 0→0.48m→0 stroke, sink roll은 0→2π 회전이다. 피벗은 node의 부모 좌표 원점과 대조한다. 고정 Air Knife와 조상에 물리 animation이 있으면 거절한다.
- 소켓과 모든 부모의 full quaternion 행렬을 곱하여 실제 mesh triangle까지 거리≤0.01m, 표면 normal 정렬을 검사한다. 두 축으로 기울어진 service pad를 포함한다. mesh 중심을 접점으로 대신하지 않는다.
- 실제 mesh vertices와 모든 clip 샘플의 움직이는 자손을 collision body/swept box가 감싸는지 검사한다. scene 배치 사이 충돌·운송 경로 여유는 T8/T13 이후의 별도 책임이다.
- LOD0/1/2는 node/part/socket/재질 의미를 보존하고 실제 삼각형 수가 감소한다. 작은 bevel과 cylinder segment만 줄이며 작업부를 지우지 않는다.

Semantic digest는 `SHA256(canonical_sorted_GLTF_JSON + NUL + complete_BIN_chunk)`다. **기하·topology·UV·normal·이름·행렬·animation·재질·PNG를 제외하거나 반올림하지 않는다. generator를 포함하여 GLB 내용에서 제외하는 필드는 없다.** JSON key 순서와 공백만 canonicalize한다. 서로 다른 `.blend` 저장의 경로/파일 내부 timestamp는 GLB semantic digest에 들어가지 않지만 각 원본의 실제 파일 해시는 별도로 검증한다. LOD0과 LOD1의 hash가 같아야 하는 것은 아니다. 같은 입력으로 독립 Blender 프로세스가 생성한 같은 LOD의 hash가 정확히 같아야 한다.

초기 실제 시험에서 Blender bevel의 UV 보간에 process별 float32 차이가 발견됐다. hash를 느슨하게 만들지 않고 bevel 적용 뒤 최종 vertex에서 UV를 다시 투영해 수정했다. 최초 실패 증거도 보존했다. 손상 시험은 GLB 내부를 직접 바꾸고 파일 checksum까지 갱신하여 단순 checksum 거절을 우회한 뒤 axis/pivot/texture/scale/missing-node/semantic 검사를 각각 확인한다.

## 대표 자산과 후속 연결

| 자산 | 실제 작업부 | 작업 소켓(프로젝트 m) | 남은 연결 |
| --- | --- | --- | --- |
| `steelflow:shear:CUT-SLAB` | 분리 blade/carriage/rod, 두 column, 절단 clearance가 있는 앞뒤 table, stroke clip | entry(-1.4,1.05,0), work(0.3,1.05,0), exit(1.4,1.05,0) | T6 phase→clip sample, T13 loader, T8 외부 gantry adapter |
| `steelflow:galvanizing:CS-GI-05` | zinc bath 형상, 실제 sink roll/shaft/index, 양쪽 고정 nozzle/slot, support pads | entry(-1.4,1.76,0), work(0,1.76,0), exit(1.4,1.76,0) | Air Knife `galvanizing.gas_wiping` 상태는 T4 선언이며 T6/T13 구현 연결 대기 |

내부 기울어진 service support는 전체 quaternion/normal 검증용 실제 받침 형상이며 생산 소재를 별도로 복제하지 않는다. 루트는 지면 원점, physicalScale=1이다. T8의 넓은 예약 envelope와 외부 작업/하역 socket을 실제 기계 socket으로 잘못 해석하거나 자산을 확대해 맞추지 않는다.

이번 결과는 **파이프라인과 이 두 대표 원본**에 대한 증거다. 전체 40 kind/158 variant·placement, T6 runtime, T13 브라우저 loader·LOD 전환, 서버 pause/fault/custody, 전체 공장 시각 승인·성능을 완료했다고 주장하지 않는다. 표준의 공개 공정 근거는 기능 개념만 제공하며 세부 기구 치수는 직접 합성 제작이다.

## 승인된 미니어처 방향과 검수 경계

기준은 [A 미니어처 조감도](../design/mockups/2026-10-25/a-miniature-overview.png), [B 운영 지도](../design/mockups/2026-10-25/b-operations-map.png), [C 소재 추적](../design/mockups/2026-10-25/c-material-follow.png)와 [공통 시각 표준](FACTORY_VISUAL_STANDARD.md)이다. 실제 모델의 청회색 도장·따뜻한 안전색·노출 금속 구분, 작은 bevel, 같은 조명 아래의 부드러운 접촉 그림자와 정사영 검수는 이 방향을 유지한다. 미니어처 인상은 물리 크기를 축소해서 만들지 않는다. 실제 m/Y-up/+X 전방·루트 scale 1·접촉 소켓·분리 작업부·LOD 의미는 바이트 검사 대상이다.

색·기구의 가독성과 깊이감은 실제 GLB PNG를 열어 수동 판정한다. 현재 proof의 중성 스튜디오 배경은 자산 검사 환경이며, 최종 장면의 따뜻한 흰 gallery 배경·얇은 부지·hall/도로/야드/부두의 밀도와 구도는 T8 및 후속 가족별 제작·통합 검수에서 같은 기준으로 확인해야 한다. 이 두 기준물로 참고 이미지 전체의 세부 밀도나 전체 가족의 시각 품질을 승인하지 않는다. 참고 PNG를 배경 plane으로 사용하지 않는다.

현재 재개 실행 증거는 `.omo/evidence/uniform-fidelity/uf-20261026-resume01/task-12/producer/`에 둔다. `DoneClaim.json`은 현재 원본·검사기·도구·실제 명령·이미지를 해시로 묶은 구현자 제출이며, 독립 Astra High 검증과 최종 채택은 별도 게이트가 담당한다. 이전 `.omo/evidence/uniform-fidelity/uf-20261025-exec01/task-12/lane-a/`의 설치 영수증·실패·수정 과정은 그대로 보존한다. 이전 후보 로그를 최종 결과로 승격하지 않는다.
