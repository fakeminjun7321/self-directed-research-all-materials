# CILE MD 팀원 전달 패키지

이 ZIP은 팀원이 macOS 또는 Windows WSL2에서 연구 환경을 설치하고, 공식 5개 조성의 입력 파일을 정적으로 검사하고, GROMACS 전처리 및 짧은 기술 smoke를 수행할 수 있도록 만든 전달본이다.

## 앞 문서에서 말한 ZIP의 뜻

설치 안내서에서 말한 ZIP은 기존의 특정 파일 하나를 뜻한 것이 아니라, 현재 프로젝트가 Git 커밋 없이 로컬에만 있으므로 필요한 파일을 압축해서 전달하자는 의미였다.

프로젝트에는 별도로 `CILE_MD_Handoff_v0_DRAFT.zip`이라는 교수 전달용 초안도 존재한다. 그 파일은 공식 5개 시스템의 입력과 검증 스크립트를 담은 작은 기술 인계본이다. 이번 팀원 전달 ZIP은 그 인계본에 운영체제별 설치 문서, 환경 명세, fftool과 VMD 예시 자료를 추가한 패키지다.

## 포함된 내용

- `00_START_HERE/TEAM_SETUP_MACOS_KOR.md`: macOS 설치 안내
- `00_START_HERE/TEAM_SETUP_WINDOWS_WSL2_KOR.md`: Windows WSL2 설치 안내
- `Brewfile`: macOS용 GROMACS, Packmol, Pandoc 설치 명세
- `environment.yml`: Python 3.13 분석 환경
- `07_Handoff/CILE_MD_Handoff_v0_DRAFT/`: 공식 5개 조성의 좌표, topology, MDP 및 검증·실행 스크립트
- `90_Reproduce_Scripts/tools/fftool/`: 프로젝트에서 사용한 fftool 소스와 라이선스
- `03_Analysis_Results/VMD_View/`: 50 ps 예비 구조를 보는 VMD용 PDB·Tcl 파일
- `00_START_HERE/OPEN_VMD_*.command`: macOS용 VMD 실행 파일
- `environment_reference/`: 기존 Mac의 기록된 환경 정보
- `MANIFEST.tsv`, `SHA256SUMS`: 전달 파일 목록과 무결성 검사값

## 포함하지 않은 내용

- 전체 1.1 GB 작업 폴더
- 장시간 trajectory, checkpoint, energy, TPR 및 모든 중간 실행 결과
- 개인 Obsidian 설정, Drive 폴더 정보, 로컬 백업
- 보고서 작업본과 개인 메모
- Git 내부 데이터와 fftool의 중첩 `.git` 폴더

따라서 이 ZIP은 환경 설정과 기술 입력 검증용이지, 전체 연구 이력의 완전한 백업은 아니다.

## 압축 해제 후 먼저 할 일

1. 사용하는 운영체제에 맞는 문서를 연다.
   - Mac: `00_START_HERE/TEAM_SETUP_MACOS_KOR.md`
   - Windows: `00_START_HERE/TEAM_SETUP_WINDOWS_WSL2_KOR.md`
2. GROMACS, Packmol, Conda/Python과 필요한 시각화 도구를 설치한다.
3. 아래 무결성 검사를 수행한다.
4. `validate_inputs.sh`를 먼저 실행한다.
5. 그다음 `validate_grompp.sh`를 실행한다.
6. 실제 20-step smoke는 담당자와 확인한 뒤 실행한다.

## ZIP 무결성 확인

macOS:

```bash
cd CILE_MD_TEAM_PACKAGE_20260901
shasum -a 256 -c SHA256SUMS
```

Windows WSL2/Ubuntu:

```bash
cd CILE_MD_TEAM_PACKAGE_20260901
sha256sum -c SHA256SUMS
```

모든 항목이 `OK`여야 한다. 실패한 항목이 있으면 계산을 시작하지 말고 ZIP을 다시 전달받는다.

## 입력 정적 검사

```bash
cd 07_Handoff/CILE_MD_Handoff_v0_DRAFT
bash validate_inputs.sh
```

성공 문구:

```text
Static validation PASSED
```

## GROMACS 전처리 검사

```bash
bash validate_grompp.sh
```

성공 문구:

```text
grompp validation PASSED for all five systems.
```

이 단계는 TPR 생성과 입력 호환성만 확인하며 MD trajectory를 만들지 않는다.

## 기술 smoke

담당자와 확인한 뒤 다음을 실행한다.

```bash
THREADS=2 bash run_smoke_all.sh
```

이 명령은 각 시스템의 EM, NVT, NPT, production 설정을 각각 20 step만 연결한다. 성공하더라도 밀도, 평형, box 안정성, diffusion, conductivity 또는 production 타당성을 증명하지 않는다.

## 검증 수준

- **Implemented:** 운영체제별 설치 문서, 환경 명세, 공식 5개 입력, 검증 스크립트, fftool과 VMD 예시 파일이 패키지에 포함되어 있다.
- **Unit-verified:** 패키지 생성 전 원본 handoff의 내부 SHA-256 검사와 정적 입력 검사가 통과했다.
- **Physical-device-verified:** 기존 개인 Mac에서 과거의 기술 경로만 부분 확인되었다.
- **Not verified / 미검증:** 이 새 ZIP을 다른 Mac 또는 Windows WSL2에서 압축 해제하여 신규 설치, `grompp`, smoke와 결과 생성을 완료하는 경로는 아직 확인되지 않았다.
- **Not verified / 미검증:** full-length 시뮬레이션과 과학적 평형·물성 타당성은 이 패키지로 확인되지 않았다.

