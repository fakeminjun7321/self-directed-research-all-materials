# 과학 검토 및 교수님 결정 필요 항목

> **STOP-SHIP / DRAFT**  
> 아래 항목이 결정되고 실제 사용자 경로와 물리 결과가 검증되기 전에는 이 패키지를 production-ready로 표현하면 안 된다.

## 1. 교수님께 받아야 할 정확한 결정

| ID | 결정할 항목 | 현재 파일의 가정 | 교수님께 확인할 질문 | 결정 전 처리 |
|---|---|---|---|---|
| D1 | 조성 범위 | 공식 5개=L1P1, L1P2, L2P1, L3P1, L1P3 | 위 5개를 모두 전달하면 되는가? L2P2·L3P2는 제외가 맞는가? | 현재 범위를 draft로만 표시 |
| D2 | 분자 수·라벨 정의 | 기준 수는 `SCOPE_AND_ASSUMPTIONS.md` 표와 같음 | 각 라벨의 Li⁺/Pyr13⁺/FSI⁻ 수가 의도한 조성과 일치하는가? TTE 등 용매는 없는 계가 맞는가? | 분자 수를 임의 변경하지 않음 |
| D3 | Force field 모델 | `il.ff` 2021/01/29, CL&P 계열 fixed-charge 매개변수 | 이 force field와 해당 문헌 계보를 본 연구에 사용해도 되는가? 지정한 다른 force field가 있는가? | 기존 topology를 과학적 확정본으로 간주하지 않음 |
| D4 | 0.75 전하 스케일링 | Li⁺/Pyr13⁺/FSI⁻ 모두 정수 전하의 0.75배 | 0.75 스케일링을 그대로 사용할지, 전체 전하(±1 e)나 다른 계수를 사용할지? 근거로 사용할 문헌은 무엇인가? | 승인 전에 전하를 임의 변경하지 않음 |
| D5 | Topology 재생성법 | 스케일된 `topol.top`은 있으나 정확한 변환 명령은 없음 | 승인된 전하 값으로 pinned `fftool` 명령·스크립트를 다시 만들지, 기존 topology를 원본으로 보존할지? 안 쓰는 PF6⁻·TTE 정의는 제거할지? | 재현성 결락으로 표시 |
| D6 | 초기 밀도·박스 | 현재 초기 밀도 약 131–140 kg/m³ | 조성별 목표 밀도와 출처는? Packmol 박스를 목표 밀도에 가깝게 재생성할지, 점진 압축할지? | 기존 저밀도 구조를 검증본으로 사용하지 않음 |
| D7 | 평형화 압력 결합 | 실제 NPT MDP=C-rescale 500 ps; 문서=NPT Parrinello–Rahman | 초기 압축에 C-rescale/Berendsen 중 무엇을 얼마나 사용하고, 언제 Parrinello–Rahman으로 전환할지? `tau-p`와 압축 시간은? | 문서와 MDP를 일치한다고 주장하지 않음 |
| D8 | 평형화·production 길이 | NVT 100 ps, NPT 500 ps, production 1 ns, 단일 seed | 각 단계의 최소 길이, production ensemble, replica 수, seed, trajectory 출력 간격을 어떻게 할지? | 1 ns를 논문용 충분조건으로 설명하지 않음 |
| D9 | 물리 합격 기준 | 명목 298 K, 1 bar; 밀도 기준값·허용차 미정 | 조성별 실험/문헌 밀도, 허용 오차, 평형 구간 판정법, replica 재현성 기준은? | 밀도가 “그럴듯하다”는 이유만으로 합격 처리하지 않음 |
| D10 | 연구실 실행 환경 | 일반 GROMACS 입력만 알려짐 | GROMACS 버전, `gmx`/`gmx_mpi`, CPU/GPU, Slurm, 노드당 코어·GPU, 표준 job script는? | 서버 실행 검증을 주장하지 않음 |

### 교수님께 보낼 최소 확인문

> 시스템 파일을 정리하며 물리 검증 기준을 맞추기 위해 몇 가지 확인 부탁드립니다.  
> (1) 전달 대상은 L1P1, L1P2, L2P1, L3P1, L1P3 5개가 맞는지,  
> (2) CL&P 계열 force field의 모든 이온 전하에 0.75 스케일링을 적용하는 것이 맞는지,  
> (3) 298 K에서 조성별 목표 밀도와 평형화 길이·barostat 순서,  
> (4) production 길이와 replica 수,  
> (5) 연구실 서버의 GROMACS/Slurm 환경을 알려주시면 그 기준에 맞춰 검증하겠습니다.

## 2. 언어적으로 분리해야 할 두 가지 합격

### A. 기술적 실행 성공

다음은 “GROMACS가 입력을 읽고 예정된 시간까지 실행했다”는 뜻이다.

- clean extraction한 폴더에서 상대경로로 실행됨
- topology–좌표의 분자 수·원자 수가 일치함
- 전체 전하가 0 e임
- `grompp`가 임의 `-maxwarn`없이 통과함
- `mdrun`이 Fatal error·NaN·LINCS warning 없이 예정된 끝 step까지 도달함
- 예상한 checkpoint, log, energy, trajectory, 최종 구조 파일이 생성됨

### B. 물리적 타당성

다음은 “생성된 trajectory가 의도한 온도·압력·조성의 평형 액체를 나타낸다”는 뜻이다.

기술적 실행 성공은 물리적 타당성을 증명하지 않는다. L1P1은 `Finished mdrun`이 있지만 최종 박스 한 변이 299.15686 nm로 폭발한 직접적인 반례다.

## 3. 향후 실제 검증에 사용할 합격 기준

아래의 수치는 교수님 승인 전의 **임시 최소안**이다. 특히 밀도·평형 기울기·replica 허용차는 반드시 실험값과 연구 목표를 기준으로 사전 확정해야 한다.

### 3.1 정적·기술 게이트

| 게이트 | 합격 기준 | 증거로 보존할 것 |
|---|---|---|
| 패키지 무결성 | 전달 checksum과 clean extraction 후 checksum 일치 | `SHA256SUMS`, 확인 log |
| 조성 | 5개 각각의 분자 수·원자 수가 승인표와 일치 | topology 파싱 결과, 좌표 원자 수 |
| 전하 | 분자당 +0.75/+0.75/-0.75 e, 시스템 총합 `|Q| < 1e-6 e` — D4에서 0.75를 승인한 경우 | 분자당·시스템별 전하 계산표 |
| 입력 생성 | `grompp` Fatal error=0, 설명 없는 warning=0, `-maxwarn` 사용=0 | 단계별 `grompp` log |
| EM | 정상 수렴, `Fmax < 500 kJ mol⁻¹ nm⁻¹`(현재 `emtol` 유지 시), NaN·LINCS warning=0 | EM log, potential/Fmax 요약 |
| 단계 완주 | NVT 100 ps, 승인된 NPT 길이, 승인된 production 길이의 최종 step에 도달 | 단계별 log·checkpoint·최종 구조 |
| 재시작 | checkpoint에서 재시작해도 step·시간·trajectory가 연속적 | 재시작 smoke log |
| 환경 | 개인 Mac clean folder와 연구실과 동일한 Linux/GROMACS 환경에서 각각 짧은 실제 user path 통과 | 환경 버전, 명령, 종료코드, 생성 파일 |

### 3.2 물리 게이트

| 관측량 | 임시 합격 기준 | 불합격 예 |
|---|---|---|
| 온도 | NVT/NPT/production의 합의된 평형 구간 평균이 298 ± 5 K, 시간 드리프가 통계적으로 없음 | 초기 spike가 계속되거나 일방향 드리프 |
| 밀도 | production 시작 전에 평탄구간에 도달. 마지막 20% 구간 평균이 교수님이 승인한 조성별 참조값의 임시 ±5% 이내이고, 기울기 기준도 사전 충족 | L1P1처럼 거의 0으로 감소, 또는 500 ps 끝에도 150 kg/m³ 근처 |
| 박스 | 모든 변이 유한하고 평탄구간에서 드리프 없음. 최소 박스 길이는 1.2 nm cutoff의 두 배보다 크게 유지 | 299 nm로 폭발, 급격한 압축·팽창, cutoff 조건 위반 |
| 압력 | 순간 변동이 큰 소규모 액체임을 감안하되, 합의된 block average가 1 bar와 양립하고 지속적 드리프가 없음. 허용 CI/block 길이는 D9에서 사전 확정 | 순간 값 하나만 1 bar에 가깝다고 합격, 장기 음/양 드리프 |
| 에너지 | 평형 구간에서 potential/total energy가 정상적 변동범위와 정상성을 보이고 NaN·불연속 점프가 없음 | 박스 변형과 함께 에너지 발산 |
| 구조 | 분자 무결성, PBC, 겹침, 비정상 결합이 없음을 수치와 깨끗한 trajectory 시각 점검으로 확인 | 렌더링 스크린샷만 보고 백엔드 수치를 확인하지 않음 |
| production 구간 | 밀도·에너지·박스가 평형에 도달한 후의 구간만 분석. 압축 전이나 급격한 압축 전환구간은 폐기 | L1P2의 약 620 ps 급압축 전·전환 구간을 평형 production으로 포함 |
| replica | D8에서 승인된 독립 seed 수만큼 실행하고, 밀도·구조 통계·이동성의 replica 편차가 사전 허용범위 이내 | 단일 seed 하나로 재현성을 주장 |

밀도 ±5%와 온도 ±5 K는 현재 위험한 구조를 걸러내기 위한 임시 문턱이다. 문헌·실험 불확도와 연구 목적에 따라 D9에서 바꿔야 하며, 결과를 본 뒤 기준을 느슨하게 바꾸면 안 된다.

## 4. 시스템별 향후 판정에 필요한 최소 산출물

각 시스템에 대해 다음을 하나의 검증 묶음으로 남겨야 한다.

1. 실행 환경과 정확한 명령
2. topology–좌표–전하 검사표
3. EM 수렴 요약
4. NVT/NPT/production의 온도·압력·밀도·부피·에너지 전체 시계열
5. 평형 구간과 폐기 구간을 명시한 분석 메타데이터
6. 비정상 박스·NaN·LINCS·fatal 검사 결과
7. 승인된 경우 replica 간 비교

이 묶음을 보고서 및 원시 로그로 동시에 확인하지 못한 시스템은 **Not verified / 미검증**로 남긴다.

## 5. 현재 판정

- **Implemented**: 검토할 입력 구조와 현재 MDP는 존재한다.
- **Unit-verified**: 정적 입력 검사와 공식 5개 EM-stage `grompp`를 개인 Mac의 GROMACS 2026.3에서 통과했다. 이는 입력 생성 범위만 증명한다.
- **Simulator-verified**: 해당 없음.
- **Physical-device-verified**: **기술 경로만 부분 검증** — 개인 Mac에서 공식 5개 모두 20-step EM→NVT→NPT→production 연쇄 smoke를 완료했다. 원래 길이와 물리적 평형은 검증하지 않았다.
- 연구실 서버 실행: **Not verified / 미검증**.
- 물리 타당성: **Blocked / 차단됨** — D3–D9의 과학 조건과 합격 기준이 승인되지 않았고, 승인된 조건으로 새 MD 경로를 실행·판정하지 않았다.

실행 증거와 정확한 범위는 `validation/local_current/SMOKE_SUMMARY.md` 및 `validation/verification_matrix.csv`를 따른다.
