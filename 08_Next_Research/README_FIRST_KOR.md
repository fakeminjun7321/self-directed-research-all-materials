# 후속 자율연구 작업 공간

이 폴더는 교수님께 이미 전달할 수 있도록 정리한 `07_Handoff`와 분리된 후속 연구 공간이다. 기존 전달 ZIP은 수정하지 않는다.

## 지금 확인된 핵심

- 기존 5개 시스템의 초기 밀도는 약 122–170 kg/m³로, 문헌에서 확인한 이온성 액체 전해질 밀도보다 약 한 자릿수 낮다.
- 현재 비결합 cutoff는 1.2 nm이다. 단일 L1P1을 1,500 kg/m³ 부근으로 압축하면 박스 한 변이 약 2.394 nm가 되어 `2 × cutoff`보다 작아진다.
- 따라서 L1P1은 조성을 유지하면서 분자 수만 2배로 늘린 `L1P1x2` 후보를 먼저 기술 시험한다.
- 현재 topology의 전하는 모든 이온에 대해 0.75배로 축소되어 있다. 이 값은 임의로 바꾸지 않으며 교수님 확인 전까지 후보 조건으로만 유지한다.
- L2P1과 L3P1은 기존 실험 문헌에서 직접 확인한 0–3.2 mol/kg 범위를 넘는다. 298 K에서의 상 상태와 목표 밀도는 미확정이다.

## 초기 기술 점검 범위

1. 조성·질량·밀도·박스 크기를 재현 가능하게 계산한다.
2. `L1P1x2` 초기 구조를 별도로 만든다.
3. `grompp`에서 `-maxwarn` 없이 통과하는지 확인한다.
4. 에너지 최소화까지만 실행해 기술적 입력 건전성을 확인한다.
5. NVT/NPT는 탐색용 QC 증거로만 분리하고, production과 물성 결과로 사용하지 않는다.

## 추가 탐색 현황 (2026-08-07)

- L1P1x2의 초기 밀도 1,000·1,200·1,400 kg/m³ 세 체인에 대해 실제 NVT 100 ps 및 NPT 총 3 ns를 로컬 Mac에서 실행했다.
- 세 체인 모두 0–3000 ps, 3001 frame, 1 ps 간격의 append·hash provenance와 마지막 1 ns 잠정 stationarity 문턱을 통과했다.
- 2–3 ns 평균 밀도는 1505.35, 1524.39, 1518.93 kg/m³였고, chain 간 spread는 1.256%였다.
- 탐색 판정은 `THREE_NS_SAME_BASIN_CANDIDATE`이며, `pilot_L1P1x2_rho1400_v6`는 독립 replica 설계용 임시 후보다. 평형 밀도나 물리적 정답으로 판정한 것이 아니다.
- 세부 결과: `05_QC/THREE_NS_SCREEN_REPORT.md`
- 오버나잇 요약: `OVERNIGHT_RESEARCH_SUMMARY_20260807.md`
- 독립 replica 사전 계획과 입력 현황: `02_Protocol/INDEPENDENT_REPLICA_PLAN.md`
- 3 ns 연장 단계의 열 보호: 60 °C 일시정지 / 50 °C 재개, 한 번에 한 체인, OpenMP 스레드 6개. 가용 battery/virtual 센서 최댓값은 41.05 °C였고 CPU die 온도는 직접 측정하지 못했다.

임시 후보 조건에서 Packmol seed가 다른 R1·R2·R3 입력을 생성했다. 세 좌표·`simbox.xyz` hash는 모두 다르고 topology hash는 같다. 원본 세 입력 폴더는 불변 입력 증거로 `BUILT_NOT_EXECUTED` 상태를 유지하고, 실제 EM·MD는 별도 `_exec_20260807` 폴더에서 수행했다.

이후 세 입력을 별도 실행 폴더로 바이트 일치 재생성해 각각 strict EM → NVT 100 ps → NPT 1 ns를 실제 실행했다. 세 체인 모두 `PASS_COMPLETE`이고 hard fail은 없었지만 단일 체인 판정은 모두 `SCREEN_EXTEND`였다. 마지막 500 ps 평균 밀도는 1513.96, 1515.56, 1516.76 kg/m³, replica 간 spread는 0.185%다. 사전 고정 규칙에 따른 집합 판정은 `ONE_NS_REPLICA_UNIFORM_EXTENSION_REQUIRED`이며, 세 체인을 동일하게 총 3 ns로 연장하기 전에는 평형으로 해석하지 않는다. 자세한 결과는 `05_QC/REPLICA_1NS_REPORT.md`, 불변 데이터는 `05_QC/replica_1ns_comparison.json`에 있다. 현재 입력 감사는 v3다.

다음 동일 연장은 일부 replica만 시작하지 않도록 별도 작업 창으로 분리했다. 실행 순서와 안전·중단 규칙은 `02_Protocol/REPLICA_UNIFORM_EXTENSION_PLAN.md`에 고정했다.

## 재현 명령

```bash
/opt/anaconda3/bin/python scripts/calculate_compositions.py
/opt/anaconda3/bin/python scripts/build_l1p1x2_candidate.py \
  --density 1400 --tolerance 2.0 --threads 6 --packmol-seed 1234567 --execute-em
/opt/anaconda3/bin/python scripts/validate_candidate.py \
  04_Runs/pilot_L1P1x2_rho1400_v6
```

## 초기 EM 기술 점검 기록

- Run ID: `pilot_L1P1x2_rho1400_v6`
- Packmol/EM 초기·최종 box: 3.0857 nm 정육면체
- 계산 밀도: 1,400.03 kg/m³
- 실제 EM TPR의 `rlist`: 1.26 nm
- `min(box)/(2 × rlist)`: 1.2245
- strict `grompp` warning: 0
- EM: 874 step에서 `Fmax < 500` 수렴
- Fatal / NaN / LINCS warning: 0 / 0 / 0
- 기존 L2P2와 활성 topology 파라미터 동등성 및 좌표 순서 검사: 12/12 통과

위 항목은 에너지 최소화 단계의 기술 성공만 뜻한다. 298 K 평형, 압력 결합, 밀도 plateau와 물성은 검증하지 않았다.

## 검증 수준

- **Implemented**: 후속 연구 구조, 계산·후보 생성 스크립트, Packmol seed·replica artifact 감사
- **Unit-verified**: 계산·topology·원자 순서·seed provenance·실행 안전과 독립 replica 비교를 포함한 전체 104개 테스트 통과
- **Simulator-verified**: 해당 없음
- **Physical-device-verified**: 로컬 Mac에서 세 초기 밀도 체인의 3 ns 탐색을 실행했다. 별도로 Packmol 배치·속도 seed가 모두 다른 R1·R2·R3의 strict EM → NVT 100 ps → NPT 1 ns를 순차 실행하고, provenance·독립성·동일 protocol 및 replica 밀도 통계를 실제 산출물로 검증했다.
- **Not verified / 미검증**: 열역학적 평형, force field 정확도, 총 3 ns 독립 replica 결과, production, 구조·수송 특성 수렴, 연구실 서버 재현성
