# LiFSI/Pyr13FSI MD systems

LiFSI/Pyr13FSI 조성별 GROMACS 입력 파일을 정리한 폴더입니다.

## 시스템 구성

| 폴더 | Li+ | Pyr13+ | FSI- | 원자 수 |
|---|---:|---:|---:|---:|
| L1P1 | 25 | 25 | 50 | 1,150 |
| L1P2 | 25 | 50 | 75 | 2,050 |
| L2P1 | 50 | 25 | 75 | 1,400 |
| L3P1 | 75 | 25 | 100 | 1,650 |
| L1P3 | 25 | 75 | 100 | 2,950 |

각 시스템 폴더에는 `initial.gro`와 `topol.top`이 들어 있습니다. 공통 MDP는 `mdp` 폴더에 모았습니다.

- energy minimization: 최대 50,000 steps
- NVT: 298 K, 100 ps
- NPT: 298 K, 1 bar, 500 ps, C-rescale
- production: 298 K, 1 bar, 1 ns, Parrinello-Rahman

## 개인 PC 확인 내용

macOS와 GROMACS 2026.3 환경에서 입력 파일 검사, 다섯 시스템의 `grompp`, 20-step EM–NVT–NPT–production 연결 테스트를 진행했습니다. 짧은 테스트 범위에서는 모두 오류 없이 종료됐습니다.

전체 100 ps–500 ps–1 ns 계산은 새 패키지에서 다시 실행하지 않았습니다. 또 기존 계산 기록을 확인했을 때 초기 구조의 밀도가 약 130–140 kg/m3로 낮았고, topology의 Li+, Pyr13+, FSI- 전하는 모두 원래 전하의 0.75배로 적용돼 있습니다. 초기 밀도와 전하 스케일링 조건이 의도한 설정인지 확인이 필요합니다.

## 실행 방법

먼저 파일을 확인합니다.

```bash
bash validate_inputs.sh
bash validate_grompp.sh
```

시스템 하나를 실행하는 예시는 다음과 같습니다.

```bash
THREADS=8 bash run_one.sh L1P1
```

다섯 시스템을 순서대로 실행하려면 다음 명령을 사용합니다.

```bash
THREADS=8 MAX_PARALLEL=1 bash run_local.sh
```

연구실 서버에서는 `run_slurm_template.sh`의 partition, account, module 설정을 서버 환경에 맞게 수정해야 합니다.

체크섬은 아래 명령으로 확인할 수 있습니다.

```bash
sha256sum -c SHA256SUMS
```

macOS에서는 `shasum -a 256 -c SHA256SUMS`를 사용하면 됩니다.
