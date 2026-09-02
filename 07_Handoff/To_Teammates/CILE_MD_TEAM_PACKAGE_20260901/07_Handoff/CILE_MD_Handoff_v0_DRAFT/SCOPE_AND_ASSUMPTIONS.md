# CILE MD 시스템 범위·가정 및 현재 과학 상태

> **DRAFT / NOT FOR PRODUCTION**  
> 이 문서는 2026-08-06에 기존 파일을 읽어 작성한 과학 감사 메모이다. 감사 뒤 별도 기술 검증에서 20-step smoke를 실행했지만 MDP·topology·초기 구조는 변경하지 않았다. 따라서 교수님 서버로 전달할 수 있는 물리 검증본이 아니다.

## 1. 이 인계본의 범위

- 계: LiFSI/Pyr13FSI 고정 전하(fixed-charge) 고전 MD 입력
- 엔진: GROMACS
- 공식 대상: `L1P1`, `L1P2`, `L2P1`, `L3P1`, `L1P3` 5개
- 구성 요소: Li⁺, N-propyl-N-methylpyrrolidinium(Pyr13⁺, topology 이름 `c3c1pyrr+`), FSI⁻
- 설계된 단계: EM → 100 ps NVT → 500 ps NPT → 1 ns NPT production
- 온도·압력 명목값: 298 K, 1 bar

`L2P2`, `L3P2`는 추가 비교용 시스템으로 현재 공식 5개의 범위에 포함하지 않는다. 이 범위는 원본 `00_START_HERE/README_2026-05-27_full_analysis.md`의 기록을 따른 것이며, 최종 범위는 교수님의 명시적 확인이 필요하다.

## 2. 공식 5개 시스템과 분자 수

| 라벨 | Li⁺ | Pyr13⁺ | FSI⁻ | 총 원자 수 | 초기 정육면체 한 변 (Å) | 전하 중성 관계 |
|---|---:|---:|---:|---:|---:|---|
| L1P1 | 25 | 25 | 50 | 1,150 | 52.877 | 25 + 25 = 50 |
| L1P2 | 25 | 50 | 75 | 2,050 | 64.114 | 25 + 50 = 75 |
| L2P1 | 50 | 25 | 75 | 1,400 | 56.460 | 50 + 25 = 75 |
| L3P1 | 75 | 25 | 100 | 1,650 | 59.639 | 75 + 25 = 100 |
| L1P3 | 25 | 75 | 100 | 2,950 | 72.384 | 25 + 75 = 100 |

정적 대조 결과, 위 수치는 다음 세 곳에서 일치한다.

1. `01_Raw_Data/Initial_Structures_Packmol/summary.csv`
2. 각 시스템의 `*.pack.inp`
3. 각 `topol.top`의 `[ molecules ]` 섹션

PDB의 `ATOM`/`HETATM` 행 수도 표의 총 원자 수와 일치한다. 다만 라벨 `LxPy`가 지정하는 정확한 몰비를 외부 스펙으로 확인하지 못했으므로, 이 표의 분자 수를 교수님이 승인해야 한다.

## 3. Force field와 topology 출처

파일에서 확인된 계보는 다음과 같다.

1. Li⁺, Pyr13⁺, FSI⁻의 분자 정의는 `01_Raw_Data/Original_MD_Sources/MD_files/{Li,c3c1pyrr,fsi}.zmat`에 있다.
2. 모든 사용 분자의 z-matrix는 `il.ff`를 참조한다.
3. `il.ff`는 자신을 `version 2021/01/29`, “Molecular force field for ionic liquids”, Agilio Padua·J. N. Canongia Lopes 계열로 기록한다. 파일 내부에는 lithium cation=Aqvist, ammonium/pyrrolidinium=JPCB 108 (2004) 16893, FSI=PCCP 43 (2017) 29617로 출처가 적혀 있다.
4. GROMACS topology는 첫 행에 `created by fftool`로 기록되어 있다. 작업 공간에 보관된 `fftool` Git 원격은 `https://github.com/paduagroup/fftool.git`, 현재 커밋은 `39d980be16d0123a72ba698a437476f2e535407a`이다.

이는 파일 내부 기록에 대한 계보 확인이지, 문헌 적합성과 현재 조성에 대한 매개변수의 과학적 승인을 의미하지 않는다. 또한 현재 topology에는 `[ molecules ]`에서 사용하지 않는 PF6⁻·TTE 정의도 남아 있다. 실제 시스템 분자는 Li⁺/Pyr13⁺/FSI⁻뿐이지만, 최종 인계본은 안 쓰는 정의를 제거하거나 그 존재를 명시해야 한다.

## 4. 0.75 전하 스케일링

현재 `topol.top`의 사용 분자당 전하합은 다음과 같다.

| 분자 | topology 전하합 (e) | 원래 정수 전하 대비 |
|---|---:|---:|
| Li⁺ | +0.750000 | 0.75 × (+1) |
| Pyr13⁺ | +0.750000 | 0.75 × (+1) |
| FSI⁻ | -0.750000 | 0.75 × (-1) |

Li의 +1.00→+0.75, N4의 +0.12→+0.09, C1의 -0.17→-0.1275, FSI 구성 원자의 대응 전하를 표본 대조하면 `il.ff` 전하가 전체적으로 0.75배 된 topology임을 확인할 수 있다. 모든 공식 조성에서 FSI⁻ 수 = Li⁺ 수 + Pyr13⁺ 수이므로 전체 전하는 0 e이다.

그러나 보관된 `fftool` 버전에는 전하 스케일링 인자를 받는 명령행 옵션이 보이지 않고, 원본에서 스케일된 topology를 만든 **정확한 변환 명령·스크립트·근거문헌은 현재 범위에서 발견하지 못했다**. 따라서 0.75는 파일에서 확인된 사실이지만 아직 승인된 과학적 가정이 아니다.

## 5. 초기 밀도 문제

기존 평형화 분석은 Packmol 초기 밀도를 약 131–140 kg/m³로 기록했다. 해당 문서가 비교값으로 제시한 ionic liquid 밀도 1,300–1,500 kg/m³의 약 1/10이다. 500 ps NPT 끝에서도 기록된 밀도는 L1P1 155, L1P2 144, L2P1 170 kg/m³ 정도로, 현재 500 ps NPT는 압축·밀도 평형화를 완료하지 못했다.

근거: `03_Analysis_Results/Equilibration_Stages/README_equilibration_findings.md` 및 해당 `*_npt_TEPV.xvg`.

초기 박스를 작게 재생성할지, 점진적 압축 단계를 자세히 둘지, 조성별 실험 밀도를 목표로 삼을지는 아직 결정되지 않았다. 이 결정 없이 기존 박스를 그대로 production에 넘기는 것은 수용할 수 없다.

## 6. 기존 실행 파일의 정적 상태

아래는 **과거 실행 파일에 대한 정적 감사**이며, 현재 인계본의 새 실행 검증이 아니다.

| 시스템 | 파일상 기술적 상태 | 물리 판정 | 근거·주의 |
|---|---|---|---|
| L1P1 | EM·NVT·NPT·1 ns log에 `Finished mdrun` 존재 | **실패** | production 끝 박스 한 변 299.15686 nm, 끝 밀도 0.000768 kg/m³. 박스 폭발이므로 사용 불가. |
| L1P2 | EM·NVT·NPT·1 ns log에 `Finished mdrun` 존재 | **미검증** | 기존 분석에서 약 620 ps에 급격히 압축된 뒤 끝 박스 2.91125 nm, 끝 밀도 1,352 kg/m³. 단일 run과 짧은 압축 후 구간만으로 평형을 확정할 수 없음. |
| L2P1 | EM·NVT·NPT·1 ns log에 `Finished mdrun` 존재 | **미검증** | 최종 `prod_1ns.gro`는 있지만 보관된 `L2P1_prod_TEPV.xvg`는 30 ps까지만 포함한 이전 스냅샷. 전체 1 ns를 재추출·판정해야 함. |
| L3P1 | EM·NVT 완료, NPT log는 103 ps 부근에서 종료 | **미검증 / 미완료** | `npt.gro`와 production 파일이 없음. 500 ps NPT user path 미실행. |
| L1P3 | 50 ps 예비 계산 파일만 존재 | **미검증 / 미실행** | `Rigorous_1ns/L1P3` 폴더가 없음. |

50 ps practice는 298 K NVT 예비 trajectory이며 NPT가 없다. 따라서 저밀도 Packmol 박스에서 얻은 RDF·MSD·확산·전도도 결과는 보고서용 물리 검증값으로 사용하면 안 된다.

## 7. 문서–MDP 불일치

현재 설계 파일의 압력 결합은 다음과 같다.

- `03_npt_500ps.mdp`: `pcoupl = C-rescale`
- `04_prod_1ns.mdp`: `pcoupl = Parrinello-Rahman`

그러나 `02_Processed_Data/MD_Protocols/Rigorous_1ns/README_엄밀_MD_프로토콜.md`와 `03_Analysis_Results/Equilibration_Stages/README_equilibration_findings.md`의 “표준 프로토콜”은 500 ps NPT를 Parrinello–Rahman으로 설명한다. 즉, **NPT 평형화 문서와 실제 MDP가 다르다**. Production이 Parrinello–Rahman인 것은 일치한다.

또한 2026-05-27 분석 문서는 L2P1을 “진행 중”으로 기록했지만, 현재 디스크에는 이후 종료된 1 ns log와 최종 구조가 남아 있다. 이는 분석 문서와 실행 파일의 시점이 다르기 때문이며, 최종 패키지에서 전체 상태를 다시 추출해야 한다.

## 8. 현재 검증 레벨

- **Implemented**: 원본 작업 공간에 공식 5개의 초기 구조, topology, 4단계 MDP가 존재한다.
- **Unit-verified**: 분자 수·원자 수·전하의 정적 대조와 공식 5개 EM-stage `grompp`를 통과했다.
- **Simulator-verified**: 해당 없음.
- **Physical-device-verified**: **기술 경로만 부분 검증** — 개인 Mac에서 공식 5개 모두 20-step EM→NVT→NPT→production 연쇄 smoke를 완료했다. 원래 길이와 물리적 평형은 검증하지 않았다.
- 연구실 서버: **Not verified / 미검증**.
- 물리적 타당성: **Not verified / 미검증**. L1P1 과거 production은 명백한 실패다.

실행 증거는 `validation/local_current/SMOKE_SUMMARY.md`에, 교수님의 결정과 향후 검증 게이트는 `SCIENTIFIC_REVIEW_REQUIRED.md`에 분리했다.
