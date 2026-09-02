# L1P1x2 독립 replica 사전 계획 및 1 ns 실행 결과

> **1 ns EXPLORATORY SCREENS EXECUTED / NOT EQUILIBRIUM**  
> 3 ns 초기 밀도 민감도 탐색에서 `pilot_L1P1x2_rho1400_v6`가 임시 후보로 선정됐다. 사전 고정한 두 종류 seed로 세 replica를 strict EM, NVT 100 ps, NPT 1 ns까지 실제 실행했다.

## 독립성 정의

각 replica는 다음 두 종류의 seed를 모두 다르게 사용하도록 고정했다.

1. **Packmol seed**: 초기 분자 배치를 변경한다.
2. **GROMACS velocity seed**: NVT 시작 속도를 변경한다.

둘 중 하나만 바꾸면 이 계획에서는 완전한 독립 replica로 카운트하지 않는다. 단, 세 replica가 같은 topology·조성·초기 밀도·MDP·GROMACS 버전을 사용해야 한다.

## 사전 고정값

| replica | 예정 run ID | Packmol seed | velocity seed |
|---|---|---:|---:|
| R1 | `replica_L1P1x2_rho1400_R1` | 240101 | 110101 |
| R2 | `replica_L1P1x2_rho1400_R2` | 240102 | 110102 |
| R3 | `replica_L1P1x2_rho1400_R3` | 240103 | 110103 |

실제 Packmol 입력 생성 결과:

| replica | 요청/Packmol 관측 seed | `initial.gro` SHA-256 | 원본 입력 폴더 | 별도 `_exec_20260807` 폴더 |
|---|---:|---|---|---|
| R1 | 240101 / 240101 | `dc84a241d4e7f371466f8ec6d18fd0b9ee6feaeb0e12a36dc41f1dc4f47a7d6a` | `BUILT_NOT_EXECUTED` | `PASS_COMPLETE` (NPT 1 ns) |
| R2 | 240102 / 240102 | `46604333933c8b3dcb5289eae8eac21a979f814d52fd2f7f8b8f53d385a56508` | `BUILT_NOT_EXECUTED` | `PASS_COMPLETE` (NPT 1 ns) |
| R3 | 240103 / 240103 | `bfbc32352cc4689703680a8ea9aca3750ed5dbcf0405bdcfaf0bb9c90e68f57e` | `BUILT_NOT_EXECUTED` | `PASS_COMPLETE` (NPT 1 ns) |

세 topology SHA-256은 모두 `e411d910eabfcd4598f6a090bae23f4cbb6c95f4e0aad8726d603e1cf76bd4c8`로 같고, 세 초기 좌표 hash는 모두 다르다.

- 초기 밀도: 1,400 kg/m³
- 조성: Li 50 / Pyr13 50 / FSI 100
- 전하 스케일: 0.75 (임의 변경 금지)
- 기본 경로: Packmol → strict `grompp` → EM → NVT 100 ps → NPT 1 ns → 사전 QC
- 1 ns 통과 후에도 세 replica 전부를 같은 길이로만 연장한다. 가장 좋아 보이는 하나만 선택하지 않는다.

## 안전 및 중단 조건

- 가용 battery/virtual 센서: 60 °C 일시정지 / 50 °C 재개, 15초 간격. CPU die는 직접 측정하지 못한다.
- 동시 실행: 한 번에 한 replica
- GROMACS: OpenMP 스레드 6개
- strict `grompp` warning, Fatal, NaN/Inf, LINCS warning, segfault: 1건이라도 있으면 즉시 중단
- `min(box)/(2×rlist) < 1.10`이면 시간 연장 금지
- 다른 replica와 다른 protocol·hash·버전이 감지되면 비교 금지

## 예정 명령

```bash
/opt/anaconda3/bin/python scripts/build_l1p1x2_candidate.py \
  --density 1400 --tolerance 2.0 --threads 6 \
  --packmol-seed 240101 --run-id replica_L1P1x2_rho1400_R1 --execute-em

/opt/anaconda3/bin/python scripts/run_equilibration.py \
  04_Runs/replica_L1P1x2_rho1400_R1 --seed 110101 --npt-ps 1000 --threads 6
```

실제 실행은 원래 입력 폴더를 보존하고 `_exec_20260807` 별도 run ID로 수행했다. 각 실행의 `initial.gro`는 사전 입력과 바이트 단위로 일치한다.

## 검증 수준

- **Implemented**: builder가 명시적 `--packmol-seed`를 입력에 추가하고, 실행 로그에서 Packmol이 실제 사용한 seed를 재확인하도록 작성됐다.
- **Unit-verified**: seed·좌표·topology·MD provenance, replica 비교, 실행 안전을 포함한 전체 104개 테스트가 통과했다.
- **Physical-device-verified**: 로컬 Mac에서 세 입력을 각각 별도 폴더로 바이트 일치 재생성하고 strict EM → NVT 100 ps → NPT 1 ns를 순차 실행했다. 세 기술 상태는 `PASS_COMPLETE`, strict warning·hard fail은 0건이다. 두 종류 seed, 세 단계 좌표 고유성, 동일 protocol·GROMACS·실제 6스레드, EDR 시간 범위와 핵심 파일 hash가 모두 교차검증됐다. 전체 실행 guard의 가용 센서 최고값은 41.25 °C, 경고·pause는 0건이었다.
- **Not verified / 미검증**: 총 3 ns 독립 replica 결과, 평형, production, 구조·수송 물성, 연구실 서버 재현성.

현재 입력 감사 결과는 `05_QC/replica_input_audit_v3.json`, 실행 비교 결과는 `05_QC/replica_1ns_comparison.json`, 사람이 읽는 요약은 `05_QC/REPLICA_1NS_REPORT.md`에 있다. 사전 규칙에 따른 판정은 `ONE_NS_REPLICA_UNIFORM_EXTENSION_REQUIRED`이며 대표 replica는 선정하지 않았다. 기존 v1·v2 감사 파일은 이력으로 보존한다.
