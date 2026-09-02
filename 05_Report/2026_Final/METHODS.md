# 연구 방법 재현 기록

## 시스템

- 후보: L1P1x2
- 조성: Li 50 / Pyr13 50 / FSI 100
- 원자 수: 2,300
- 초기 요청 밀도: 1,400 kg/m³
- 실제 초기 밀도: 1,400.0339 kg/m³
- 활성 전하 스케일: 0.75
- topology SHA-256: `e411d910eabfcd4598f6a090bae23f4cbb6c95f4e0aad8726d603e1cf76bd4c8`

0.75 전하 스케일은 기존 연구 조건을 보존한 후보값이며 물리적으로 최적화·승인된 값이 아니다.

## 독립 replica

| Replica | Packmol seed | NVT velocity seed |
|---|---:|---:|
| R1 | 240101 | 110101 |
| R2 | 240102 | 110102 |
| R3 | 240103 | 110103 |

두 종류 seed가 모두 다르고 topology·조성·MD protocol은 동일하다.

## 실행 단계

1. Packmol 21.2.3으로 초기 좌표 생성
2. `grompp` warning 0 조건의 strict energy minimization
3. NVT 100 ps
4. NPT 1 ns 탐색
5. 자동 QC 및 독립 replica 비교

- GROMACS: 2026.3 Homebrew CPU build
- OpenMP: 동시에 한 체인, 스레드 6개
- thermal guard: 가용 battery/virtual 센서 60°C 관측 시 최대 15초 내 pause, 50°C 이하 및 macOS 경고 없음에서 resume
- CPU die 온도: 직접 측정하지 못함

## 판정

- 단일 체인: `SCREEN_FAIL`, `SCREEN_EXTEND`, `SCREEN_STATIONARITY_PASS`
- 세 replica 1 ns: `ONE_NS_REPLICA_UNIFORM_EXTENSION_REQUIRED`
- equilibrium validated: false
- production ready: false

## 핵심 source artifact

- `08_Next_Research/02_Protocol/REPLICA_1NS_COMPARISON_RULES.md`
- `08_Next_Research/05_QC/replica_input_audit_v3.json`
- `08_Next_Research/05_QC/replica_1ns_comparison.json`
- `08_Next_Research/05_QC/REPLICA_1NS_REPORT.md`
- `08_Next_Research/04_Runs/chain_registry.csv`
- `08_Next_Research/05_QC/equilibration_qc_results.csv`
