# MD 정식 프로토콜(EM → NVT → NPT → Production)과 평형화 결과

## 표준 프로토콜

```
1. Energy Minimization (EM, steep)           — 최대 50000 step, emtol = 500
2. NVT equilibration  100 ps  — V-rescale 항온, gen-vel = yes (Maxwell 분포 298 K)
3. NPT equilibration  500 ps  — Parrinello-Rahman 항압 1 bar, V-rescale 항온 298 K
4. Production NPT     1 ns    — 같은 P/T 제어, RDF/MSD 계산용 trajectory
```

`02_Processed_Data/MD_Protocols/Rigorous_1ns/mdp/` 에 MDP 파일이 있다.

## 단계별 그림

- `04_Figures_For_Report/Comprehensive/em_convergence.png` — 5개 시스템 EM 수렴
- `04_Figures_For_Report/Comprehensive/equilibration_nvt_npt_{L1P1,L1P2,L2P1}.png` — NVT/NPT 6-panel
- `04_Figures_For_Report/Comprehensive/full_protocol_timeline_{L1P1,L1P2,L2P1}.png` — 4단계 풀 타임라인

## 핵심 관찰

### 1. EM 수렴
모든 시스템에서 potential energy가 수십~수백 step 이내에 매끄럽게 수렴 (steep descent).
시스템 크기에 비례해 step 수 증가 (L2P1처럼 큰 시스템 약 800 step).

### 2. NVT 100 ps
- 초기 Maxwell 분포로 인한 T spike (~400 K, ~첫 2 ps)
- ~20 ps 안에 298 K 부근으로 안정화
- Total energy 가 양의 큰 값에서 평형값으로 지수적 감쇠 → V-rescale 동작 정상

### 3. NPT 500 ps — 부족
**중요한 발견**: Packmol 초기 박스 밀도가 너무 헐거워서 (≈ 140 kg/m³) NPT 500 ps로는
실제 ionic liquid 평형 밀도(≈ 1300–1500 kg/m³)까지 압축이 끝나지 않는다.

| 시스템 | 초기 box (Å) | NPT 끝 box (nm) | 초기 ρ | NPT 끝 ρ (kg/m³) |
|---|---:|---:|---:|---:|
| L1P1 | 52.877 | 5.10 | ~135 | 155 |
| L1P2 | 64.114 | 6.14 | ~131 | ~145 |
| L2P1 | 56.460 | 5.51 | ~140 | 170 |

→ 500 ps 동안 ~10–20% 정도만 압축됨. 평형 밀도 도달까지 갈 길이 한참 멀다.

### 4. Production 1 ns — 불안정성 발생
Parrinello-Rahman 압력 제어가 sparse한 시스템에서 불안정해, **prod 1 ns 도중 박스가
폭발적으로 변동**하는 경우가 생긴다.

| 시스템 | Prod 평균 ρ | Prod 끝 box | 상태 |
|---|---:|---:|---|
| L1P1 | 24 kg/m³ (!) | 299.2 nm³ | **실패** — 박스 폭발, MD divergent |
| L1P2 | 1256 kg/m³ | 2.91 nm | **성공** — 약 620 ps에서 폭압축 후 안정화 |
| L2P1 | 진행 중 | – | 진행 중 (압력 시계열 음의 값 –600 bar 보임, 불안정 우려) |
| L3P1 | 미실행 | – | 백그라운드 대기 |
| L1P3 | 미실행 | – | 백그라운드 대기 |

## 원인 진단

1. Packmol 패킹 밀도 0.00778 atoms/Å³ → 실제 IL 대비 약 1/10 (헐거움)
2. 압력 제어가 큰 압축을 짧은 시간에 안정적으로 수행 못함
3. 작은 시스템(L1P1, 1150 atoms)일수록 PR barostat의 통계 떨림이 커서 발산 위험 ↑

## 권장 수정

다음 중 하나 (또는 조합)으로 protocol 개선 필요:

1. **Packmol 박스를 작게**: density 0.078 atoms/Å³ 목표 (현재의 10배). 박스 길이는
   각 시스템마다 약 (현재 길이 × 10⁻¹/³) = 약 47% 짧게.
2. **Berendsen 단계 추가**: NPT 시작을 Berendsen barostat 200–500 ps 로 부드럽게
   압축한 뒤 Parrinello-Rahman 으로 전환.
3. **NPT 500 ps → 2–5 ns 로 늘림**: 가장 안전. 작은 시스템 안정화에 효과적.
4. **tau-p 늘림** (5 → 10): 압력 제어 부드러워져 발산 위험 감소.

## 50 ps Practice와의 차이

`50ps_Practice` (이전에 돌린 빠른 RDF/CN/diffusion 분석) 는 **EM → 50 ps NVT만**
실행했고 NPT 단계가 없다. 따라서 *전 시스템이 packmol 초기 박스의 헐거운 밀도
상태에서 trajectory를 수집*했다. 이 때문에:

- g(r) peak이 크게 부풀려진다 (예: g_Li-O peak 약 145, 교수님 슬라이드는 ~23).
- CN 자체(첫 shell 적분)는 robust하므로 트렌드는 유지.
- 확산/전도도는 절대값 신뢰 어려움 → 1 ns 데이터로 재계산 권장.

L1P2의 properly equilibrated 1ns trajectory에 같은 분석 스크립트를 돌리면
g(r) peak이 적절한 값으로 나올 것 (다음 단계).
