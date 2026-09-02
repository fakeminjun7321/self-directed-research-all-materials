# L1P1x2 오버나잇 탐색 요약

> **PROVISIONAL / EXPLORATORY ONLY**  
> 이 요약은 로컬 Mac에서 수행한 초기 밀도 민감도 탐색이다. 평형, force field, production, 구조·수송 물성을 검증한 결과가 아니다.

## 핵심 결과

L1P1x2의 세 초기 밀도 체인을 동일 protocol·동일 속도 seed로 NVT 100 ps, NPT 총 3 ns까지 실행했다. 세 체인 모두 기술적 완료, append provenance, 마지막 1 ns의 잠정 stationarity 문턱을 통과했다.

| 초기 밀도 (kg/m³) | 2–3 ns 평균 밀도 (kg/m³) | 밀도 slope (%/ns) | 1–2 vs 2–3 ns 차이 (%) | 잠정 판정 |
|---:|---:|---:|---:|---|
| 1,000 | 1505.35 | 0.269 | 0.178 | `THREE_NS_STATIONARITY_CANDIDATE` |
| 1,200 clean | 1524.39 | 0.373 | 0.221 | `THREE_NS_STATIONARITY_CANDIDATE` |
| 1,400 | 1518.93 | 0.061 | 0.006 | `THREE_NS_STATIONARITY_CANDIDATE` |

- 마지막 1 ns 평균 밀도의 chain 간 spread: **1.256%**
- cross-start 판정: **`THREE_NS_SAME_BASIN_CANDIDATE`**
- 독립 replica 설계용 임시 후보: **`pilot_L1P1x2_rho1400_v6`**

위 판정은 세 초기 밀도의 짧은 window 밀도가 2% 이내로 모였다는 뜻이다. 세 체인이 같은 seed를 써서 독립 replica가 아니며, 이 결과로 평형을 선언할 수 없다.

## 재현성과 예외 처리

- 각 chain의 1 ns 원본을 `base_snapshot` 해시로 고정하고, 연장 산출물을 별도 `npt:002` record로 연결했다.
- 세 체인 모두 0–3000 ps, 3001 frame, 1 ps 간격을 확인했다. XTC full prefix, EDR 0–999 ps canonical exact 일치, 1000 ps GROMACS 경계 비교, restart log 순서를 모두 통과했다.
- 예전 `screen_L1P1x2_rho1200_20260807`은 139.1 ps 재개 입력 checkpoint의 불변 snapshot이 없어 비교에서 제외했다. 정확한 해시로 quarantine하고 새로 시작한 `screen_L1P1x2_rho1200_clean_20260807`로 대체했다.
- rho1000의 첫 guard rc=1은 GROMACS 실패가 아니라 구 append 검증기의 `Finished mdrun` marker 가정 오류였다. 완료 산출물을 mdrun 재실행 없이 신규 형식 인지 검증기로 재검증해 rc=0을 확인했다.
- 독립 replica까지 포함한 최신 중앙 registry는 chain 15행, QC 192행, incomplete chain 0개로 재생성했다.

## Mac 안전 조건

- 감시 기준: 60 °C 일시정지 / 50 °C 재개, 15초 간격
- 2 ns 연장 자원 제한: 한 번에 한 체인, OpenMP 스레드 6개
- 초기 밀도 3 ns 연장의 battery/virtual 센서 최댓값: **41.05 °C**
- 독립 replica Packmol→EM→1 ns 실행의 battery/virtual 센서 최댓값: **41.25 °C**
- pause/resume, macOS 열·성능 경고: **0건**
- CPU die 온도: **Not verified / 미검증** — 관리자 권한 없이 직접 센서를 읽지 못했다.

## 검증 수준

- **Implemented**: 불변 chain·extension manifest, 60/50 °C thermal guard, 3 ns analyzer, cross-start comparator, fail-closed registry가 존재한다.
- **Unit-verified**: 전체 104개 테스트와 Python 문법 검사, registry self-test가 통과했다.
- **Physical-device-verified**: 로컬 Mac에서 세 초기 밀도 체인의 3 ns 탐색을 실제로 수행했다. 이어 서로 다른 Packmol·속도 seed를 사용한 R1·R2·R3의 strict EM → NVT 100 ps → NPT 1 ns도 순차 실행하고 실제 산출물 provenance와 비교 가능성을 검증했다.
- **Not verified / 미검증**: 열역학적 평형, 0.75 전하 스케일 force field 정확도, 총 3 ns 독립 replica 결과, production 조건, RDF·확산·전도도 수렴, 연구실 서버 재현.

## 다음 의사결정

1. 교수님과 함께 현재 조성·0.75 전하 스케일·C-rescale/Parrinello-Rahman protocol을 후속 연장에 사용할지 확인한다.
2. 승인을 받으면 hard fail이 없는 R1·R2·R3를 모두 동일하게 총 NPT 3 ns로 연장한다. 특정 replica만 선택하지 않는다.
3. 총 3 ns의 동일 window를 다시 비교하기 전에는 평형 또는 production으로 전환하지 않는다.

Packmol seed `240101`, `240102`, `240103`과 velocity seed `110101`, `110102`, `110103`을 사용한 R1·R2·R3를 각각 1 ns까지 실행했다. 세 기술 상태는 `PASS_COMPLETE`, 마지막 500 ps 평균 밀도 spread는 0.185%지만 세 단일 체인 판정이 모두 `SCREEN_EXTEND`라 집합 판정은 `ONE_NS_REPLICA_UNIFORM_EXTENSION_REQUIRED`다. 세부 기록은 `05_QC/REPLICA_1NS_REPORT.md`, 불변 비교 자료는 `05_QC/replica_1ns_comparison.json`, 현재 입력 감사는 `05_QC/replica_input_audit_v3.json`에 있다.

초기 밀도 탐색 수치와 해시는 `05_QC/three_ns_screen.json`, 독립 replica 수치와 해시는 `05_QC/replica_1ns_comparison.json`에 있다.
