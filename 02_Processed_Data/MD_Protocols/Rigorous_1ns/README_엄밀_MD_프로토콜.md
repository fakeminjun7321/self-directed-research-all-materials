# 엄밀 MD 프로토콜

## 목적

기존 50 ps 계산은 Packmol 초기 구조가 GROMACS에서 정상적으로 돌아가는지 확인하고 RDF/coordination number를 연습 분석하기 위한 예비 계산이다.  
교수님께 더 엄밀한 절차를 보여주려면 아래처럼 평형화 단계를 추가하는 편이 좋다.

```text
Packmol 정육면체 초기 구조
→ 기존 energy minimization 결과 확인
→ 더 엄격한 re-minimization
→ NVT equilibration
→ NPT equilibration
→ Production MD
→ RDF / coordination number analysis
```

## 이 폴더에 들어 있는 파일

- `mdp/01_em_strict.mdp`: 에너지 최소화. 기존보다 수렴 기준을 더 엄격하게 설정했다.
- `mdp/02_nvt_100ps.mdp`: 298 K에서 100 ps NVT 온도 평형화.
- `mdp/03_npt_500ps.mdp`: 298 K, 1 bar에서 500 ps NPT 밀도/박스 평형화.
- `mdp/04_prod_1ns.mdp`: 1 ns production MD. RDF와 coordination number 분석에 사용할 수 있는 본 계산 단계.
- `scripts/RUN_ONE_SYSTEM.command`: 조성 하나만 선택해서 실행.
- `scripts/RUN_ALL_SYSTEMS.command`: 다섯 조성 전체 실행.

## 교수님께 설명할 핵심

Packmol로 만든 초기 구조는 정육면체 박스 안에 분자를 무작위 배치한 구조이다. 그러나 Packmol 구조만으로는 실제 액체 밀도와 박스 크기가 충분히 평형화되었다고 보기 어렵다. 따라서 GROMACS에서 에너지 최소화를 수행한 뒤, NVT 평형화로 온도를 안정화하고, NPT 평형화로 박스 크기와 밀도를 안정화한 다음 production MD를 수행하는 절차가 더 엄밀하다. 이 실행 스크립트는 기존 50 ps 예비 계산 폴더에 저장된 `em.gro`를 출발점으로 다시 더 엄격한 에너지 최소화를 수행한다.

## 보고서용 문장

본 연구에서는 Packmol을 이용하여 각 조성의 Li+, Pyr13+, FSI-를 정육면체 simulation box에 배치하였다. 이후 GROMACS에서 steepest descent 방법으로 에너지 최소화를 수행하여 초기 구조의 원자 간 겹침과 큰 힘을 완화하였다. 보다 엄밀한 분석을 위해 최소화된 구조를 다시 더 낮은 force tolerance 조건에서 재최소화하고, 298 K에서 100 ps NVT 평형화를 수행하여 온도를 안정화하였다. 이어 298 K, 1 bar 조건에서 500 ps NPT 평형화를 수행하여 밀도와 simulation box 크기를 안정화하였다. 최종적으로 평형화된 구조를 이용해 1 ns production MD를 수행하고, 이 trajectory로부터 radial distribution function과 coordination number를 계산하도록 설계하였다.

## 실행 방법

GROMACS가 설치된 Mac에서 실행한다.

1. 조성 하나만 시험 실행하려면 `scripts/RUN_ONE_SYSTEM.command`를 더블클릭한다.
2. 다섯 조성을 모두 실행하려면 `scripts/RUN_ALL_SYSTEMS.command`를 더블클릭한다.
3. 전체 실행은 시간이 오래 걸릴 수 있으므로 먼저 `RUN_ONE_SYSTEM.command`로 L1P1 하나를 테스트하는 것을 권장한다.

결과는 `02_Processed_Data/MD_Runs/Rigorous_1ns` 아래에 생성된다.

## 주의

이 폴더는 더 엄밀한 계산을 하기 위한 입력 파일 세트이다. 파일을 만든 것만으로 새 결과가 생기는 것은 아니며, 스크립트를 실행해야 실제 `nvt`, `npt`, `prod_1ns` 결과가 생성된다.

1 ns production도 학교 연구/예비 연구 수준에서는 훨씬 나아진 조건이지만, 논문 수준으로 엄밀하게 하려면 더 긴 production MD와 반복 계산이 필요하다.
