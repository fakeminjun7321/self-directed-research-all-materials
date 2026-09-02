# MDP 설정 파일 설명

## 무엇을 설명하면 되는가

교수님이 `.mdp` 파일을 풀라고 하신 것은 GROMACS 분자동역학 계산에서 사용한 실행 조건을 설명하라는 의미로 보면 된다.  
본 연구에서는 L1P1, L1P2, L2P1, L3P1, L1P3 조성에 대해 동일한 MD 조건을 적용했고, 조성 차이는 초기 구조와 분자 수 비율에서만 달라진다.

## 제출하거나 설명할 핵심 파일

1. `01_energy_minimization_em.mdp`
   - 에너지 최소화 조건이다.
   - 초기 구조에서 원자 간 겹침이나 너무 큰 힘을 줄이기 위해 사용했다.

2. `03_production_50ps.mdp`
   - 실제 50 ps MD 생산 계산 조건이다.
   - RDF와 coordination number 분석에는 이 50 ps trajectory를 사용했다.

3. `02_short_practice_10ps.mdp`
   - 10 ps 연습 계산 조건이다.
   - 본 분석의 핵심 파일은 아니고, 실행 가능성 확인 및 연습용으로 사용했다.

## 보고서에 쓰면 좋은 요약 문장

본 연구에서는 GROMACS를 이용하여 각 조성별 전해질 구조에 대해 먼저 steepest descent 방법으로 에너지 최소화를 수행하였다. 이후 298 K에서 V-rescale thermostat을 적용한 NVT 조건의 분자동역학 계산을 수행하였다. 시간 간격은 1 fs로 설정하였고, 50 ps 생산 계산에서는 총 50,000 step을 계산하였다. 장거리 정전기 상호작용은 PME 방법으로 처리하였으며, Lennard-Jones 및 Coulomb cutoff는 1.2 nm로 설정하였다. 수소 결합은 LINCS 알고리즘으로 constraint 처리하였다.

## 주요 파라미터 해석

- `integrator = steep`: 에너지 최소화에서 steepest descent 알고리즘을 사용한다.
- `integrator = md`: 실제 분자동역학 계산을 수행한다.
- `dt = 0.001`: 시간 간격은 0.001 ps, 즉 1 fs이다.
- `nsteps = 50000`: 50 ps 계산이다. 0.001 ps x 50000 = 50 ps.
- `tcoupl = V-rescale`: 온도 조절을 위해 V-rescale thermostat을 사용한다.
- `ref-t = 298.0`: 기준 온도는 298 K이다.
- `pcoupl = no`: 압력 조절은 사용하지 않았으므로 NVT 조건에 해당한다.
- `coulombtype = PME`: 장거리 정전기 상호작용을 PME 방식으로 계산한다.
- `rcoulomb = 1.2`, `rvdw = 1.2`: Coulomb 및 van der Waals cutoff는 1.2 nm이다.
- `pbc = xyz`: x, y, z 모든 방향에 주기적 경계 조건을 적용한다.
- `constraints = h-bonds`: 수소가 포함된 결합을 constraint 처리한다.
- `constraint-algorithm = LINCS`: constraint 계산에 LINCS 알고리즘을 사용한다.

## 설명하지 않아도 되는 파일

- `mdout.mdp`: GROMACS가 `grompp` 실행 후 자동으로 생성한 출력 설정 파일이다. 직접 작성한 입력 조건 파일이 아니므로 핵심 설명 대상은 아니다.
- `run0.mdp`, `run1.mdp`, `run2.mdp`, `run3.mdp`, `run.mdp`: 원본 강의자료 또는 이전 정리 전 파일로 보이며, 현재 정리된 최종 분석 조건 설명에는 필수적이지 않다.
