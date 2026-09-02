# CILE MD 시스템 인계 패키지 v0

> **DRAFT / NOT FOR PRODUCTION**  
> **Implemented:** 기존 입력 자료에서 공식 5개 조성의 좌표·topology와 공통 MDP를 모았습니다.  
> **Physical-device-verified (기술 경로만):** 2026-08-06 개인 Mac에서 공식 5개 모두 EM-stage `grompp`와 20-step EM→NVT→NPT→production 연쇄 실행을 완료했고, ZIP 후보를 새 임시 폴더에 풀은 clean-extract 경로에서도 같은 기술 검사를 통과했습니다.  
> **Not verified / 미검증:** 원래 길이의 full protocol, 물리적 평형·안정성, Colab/Linux 교차검증, M4 Pro 재검증, 연구실 서버 호환성은 검증되지 않았습니다.

## 용도와 현재 제한

이 폴더는 LiFSI/Pyr13FSI 조성별 GROMACS 입력을 독립적으로 점검하기 위한 인계 초안입니다. 기존 소스를 수정하지 않고 필요한 입력만 복사했습니다. trajectory, checkpoint, energy, log, TPR, 분석 결과와 예전 backup은 포함하지 않았습니다.

현재 입력의 초기 박스는 너무 헐거운 저밀도 상태입니다. 따라서 이 초안으로 장시간 시뮬레이션을 시작하거나 데이터를 생성하면 안 됩니다.

## 포함된 시스템

| 라벨 | Li+ | Pyr13+ (`c3c1pyrr+`) | FSI- | 원자 수 | 초기 box (nm) |
|---|---:|---:|---:|---:|---:|
| L1P1 | 25 | 25 | 50 | 1,150 | 5.28770 |
| L1P2 | 25 | 50 | 75 | 2,050 | 6.41140 |
| L2P1 | 50 | 25 | 75 | 1,400 | 5.64600 |
| L3P1 | 75 | 25 | 100 | 1,650 | 5.96390 |
| L1P3 | 25 | 75 | 100 | 2,950 | 7.23840 |

각 시스템의 `initial.gro`는 기존 10 ps 예비 실행 폴더의 `em.gro`를 이름만 바꿔 복사한 좌표입니다. `topol.top`도 같은 예비 실행 폴더에서 복사했습니다. 네 시스템에서 10 ps, 50 ps, rigorous 폴더의 topology checksum은 서로 같았고, rigorous 폴더가 없는 L1P3는 10 ps와 50 ps topology checksum이 같았습니다.

## 공통 MDP

`mdp/` 폴더의 네 파일은 기존 rigorous 프로토콜에서 복사한 공통 입력입니다.

1. `01_em_strict.mdp`: steepest-descent EM, 최대 50,000 steps
2. `02_nvt_100ps.mdp`: 298 K NVT, 100 ps
3. `03_npt_500ps.mdp`: 298 K, 1 bar NPT, C-rescale, 500 ps
4. `04_prod_1ns.mdp`: 298 K, 1 bar production NPT, Parrinello-Rahman, 1 ns

MDP 네 개는 기존 rigorous 실행 폴더 `L1P1`, `L1P2`, `L2P1`, `L3P1`에서 각각 checksum이 모두 같음을 확인했습니다. 다만 이는 파일 동일성만 확인한 것이며 조건의 과학적 타당성을 증명하지 않습니다.

## 반드시 해결해야 할 알려진 문제

1. **초기 저밀도:** 기존 분석 기록에서 Packmol 초기 밀도는 약 130–140 kg/m³로 추정되었습니다. 기록에서 비교한 ionic liquid 목표 밀도 약 1,300–1,500 kg/m³보다 크게 낮습니다.
2. **500 ps NPT의 한계:** 기존 기록상 500 ps 동안 증가한 밀도는 평형 범위에 도달하지 못했습니다. 초기 box 크기와 밀도 평형화 절차를 재설계해야 합니다.
3. **L1P1 발산 이력:** 기존 1 ns production 실행에서 L1P1 박스가 비정상적으로 팽창하고 밀도가 붕괴한 기록이 있습니다. 현재 production MDP는 Parrinello-Rahman barostat을 사용합니다.
4. **기록과 실제 MDP의 표현 차이:** 기존 평형화 문서 일부는 NPT 500 ps를 Parrinello-Rahman으로 설명하지만, 이 패키지의 `03_npt_500ps.mdp`에 적힌 실제 값은 `pcoupl = C-rescale`입니다. production MDP만 `Parrinello-Rahman`입니다.

위 문제를 해결하기 전에는 기존 50 ps/1 ns 결과를 정상 production 데이터로 간주하지 마십시오. 특히 명령이 종료됐다는 사실만으로 시스템의 물리적 타당성을 판단하면 안 됩니다.

## 패키지 구조

```text
CILE_MD_Handoff_v0_DRAFT/
├── DRAFT_NOT_FOR_PRODUCTION.txt
├── README_FIRST_KOR.md
├── MANIFEST.tsv
├── SHA256SUMS
├── colab/
├── operator_prompts/
├── mdp/
│   ├── 01_em_strict.mdp
│   ├── 02_nvt_100ps.mdp
│   ├── 03_npt_500ps.mdp
│   └── 04_prod_1ns.mdp
├── systems/
│   ├── L1P1/
│   ├── L1P2/
│   ├── L2P1/
│   ├── L3P1/
│   └── L1P3/
│       └── 각 폴더에 initial.gro, topol.top
├── validation/
├── run_one.sh, run_local.sh, run_smoke_all.sh
├── run_slurm_template.sh
└── validate_inputs.sh, validate_grompp.sh
```

## 검증 상태

- **Implemented:** 공식 5개 조성의 `initial.gro`, `topol.top`, 공통 rigorous MDP 4개, manifest, SHA-256 checksum을 포함합니다.
- **Unit-verified:** 파일 인벤토리, 원본과의 byte-level 동일성, GRO 원자 수와 topology에서 계산한 원자 수의 일치, 절대경로/외부 include 부재, 금지 확장자 및 macOS 메타데이터 부재를 정적 검사로 확인했습니다. GROMACS 2026.3-Homebrew에서 공식 5개 모두 EM-stage `grompp`를 `-maxwarn` 없이 통과했습니다.
- **Simulator-verified:** 해당 없음.
- **Physical-device-verified:** **기술 실행 경로만 부분 검증.** 개인 Mac(Apple M5, 24 GB, CPU-only GROMACS)에서 공식 5개 모두 20-step EM→NVT→NPT→production 체인을 종료하고 단계별 최종 GRO/CPT/EDR/LOG와 읽을 수 있는 trajectory를 확인했습니다. ZIP 후보 clean extraction에서도 SHA 52/52, 정적 검사, 5-system `grompp`, 20-step 4단계 체인, production XTC `gmx check`가 통과했습니다. 짧게 제한한 EM은 5개 모두 `Fmax < 500`에 수렴하지 않았으므로 물리 합격 근거가 아닙니다.
- **Physical validity:** **Not verified / 미검증.** 원래 MDP 길이, 목표 밀도, 박스 안정성, 에너지·온도·압력 plateau를 검증하지 않았습니다.
- **Live-service/server verification:** **Not verified / 미검증.** 연구실 GROMACS/Slurm 환경에서 실행하지 않았습니다.

## 완료한 clean-extract 기술 검증

2026-08-06에 ZIP 후보를 새 임시 폴더에 풀어 checksum 52/52, 정적 검사, 5-system `grompp`, 5-system 20-step 기술 smoke, production XTC 형식 확인을 통과했습니다. 세부 결과와 제한은 `validation/local_current/FINAL_ZIP_CLEAN_EXTRACT.md`에 있습니다.

## 다음 검증에서 필수로 확인할 것

1. 위 clean-extract 결과를 기록한 문서와 새 `SHA256SUMS`를 포함해 재생성한 최종 ZIP에서 동일 검증을 한 번 더 반복
2. Colab의 깨끗한 Ubuntu/GROMACS 환경에서 checksum·정적 검사·5개 `grompp`를 교차검증
3. 별도 M4 Pro에서 같은 기술 경로를 독립 재검증
4. 교수님 승인 조건으로 초기 밀도와 평형화 경로를 재설계하고 full-length 밀도, box, 온도, 압력, 에너지를 판정
5. 교수님이 사용할 연구실 서버의 GROMACS 버전, `gmx`/`gmx_mpi`, Slurm 설정에서 같은 경로 재현

세부 로컬 증거는 `validation/local_current/`에, 조성별 상태는 `validation/verification_matrix.csv`에 있습니다.

## 무결성 확인

패키지 루트에서 다음과 같이 SHA-256를 확인할 수 있습니다.

```bash
shasum -a 256 -c SHA256SUMS
```

Linux에서 `sha256sum`만 있는 경우 `SHA256SUMS`의 형식을 그대로 사용해 `sha256sum -c SHA256SUMS`로 확인할 수 있습니다.
