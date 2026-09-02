# 자율연구 전체 자료

LiFSI/Pyr13FSI 이온성 액체 전해질의 분자동역학 연구 작업 공간입니다. GROMACS 입력, Packmol 초기 구조, 분석 코드, 결과 표·그림, 보고서 초안과 팀원용 설치 안내를 관리합니다.

- GitHub 프로젝트: [자율연구](https://github.com/users/fakeminjun7321/projects/2)
- 연결 저장소: [자율연구 전체 자료](https://github.com/fakeminjun7321/self-directed-research-all-materials)
- 공개 범위: 프로젝트와 저장소 모두 **공개**입니다. 로그인 없이 열람하고 clone할 수 있습니다.

> **진행 중인 연구입니다.** 기존 50 ps 계산은 연습·탐색 자료이며 최종 물성값으로 해석하지 않습니다. 현재 보관된 후속 연구 판정은 `ONE_NS_REPLICA_UNIFORM_EXTENSION_REQUIRED`이고, `equilibrium_validated=false`, `production_ready=false`입니다. GitHub 게시나 파일 다운로드 성공은 물리적 타당성 또는 다른 컴퓨터에서의 재현성을 검증하지 않습니다.

## 처음 보는 분께

1. [현재 연구 상태와 다음 단계](08_Next_Research/README_FIRST_KOR.md)를 확인합니다.
2. [macOS 설치 안내](00_START_HERE/TEAM_SETUP_MACOS_KOR.md) 또는 [Windows·WSL2 설치 안내](00_START_HERE/TEAM_SETUP_WINDOWS_WSL2_KOR.md)를 따릅니다.
3. [입력·기술 검증 범위](07_Handoff/CILE_MD_Handoff_v0_DRAFT/README_FIRST_KOR.md)와 [과학적 검토가 필요한 항목](07_Handoff/CILE_MD_Handoff_v0_DRAFT/SCIENTIFIC_REVIEW_REQUIRED.md)을 읽습니다.
4. 보고서 작성에는 [보고서 원본 안내](05_Report/2026_Final/README.md)와 [한계](05_Report/2026_Final/LIMITATIONS.md)를 함께 사용합니다.

과거 문서의 실행 상태와 검증 기록은 해당 문서의 날짜를 기준으로 한 기록입니다. 이 저장소를 내려받은 환경에서 새로 검증한 결과가 아닙니다.

## 파일 받기

Git이 설치된 터미널에서 다음 명령으로 받습니다. 공개 저장소이므로 다운로드에 GitHub 로그인이나 접근 권한 신청은 필요하지 않습니다.

```bash
git clone --recurse-submodules https://github.com/fakeminjun7321/self-directed-research-all-materials.git cile-md
cd cile-md
```

GitHub CLI를 이미 사용하고 있다면 다음 명령도 사용할 수 있습니다.

```bash
gh repo clone fakeminjun7321/self-directed-research-all-materials cile-md -- --recurse-submodules
```

clone 대상 경로에는 기존 연구 폴더를 지정하지 않습니다. 원자료 제외 범위는 아래를 확인합니다.

## 폴더 구성

| 폴더 | 내용 |
|---|---|
| `00_START_HERE/` | 시작 안내, macOS·Windows 설정, VMD 실행 파일 |
| `01_Raw_Data/` | 원본 자료, 분자 정의와 초기 구조 |
| `02_Processed_Data/` | MDP·topology, 프로토콜과 보관된 구조 파일 |
| `03_Analysis_Results/` | 분석 표, 요약과 그림 |
| `04_Figures_For_Report/` | 보고서용 그림 |
| `05_Report/` | 보고서 원본·초안·참고문헌 목록 |
| `06_Presentation/` | 발표용 시각화 |
| `07_Handoff/` | 전달 패키지의 소스와 검증 기록 |
| `08_Next_Research/` | 후속 연구 설계, QC, 재현 코드와 테스트 |
| `09_Research_Environment/` | 환경·백업 관리 문서와 스크립트 |
| `90_Reproduce_Scripts/` | 분석·그림 생성 스크립트와 fftool 연결 |

## 저장소에 포함되지 않는 파일

Git 저장소는 전체 작업 폴더의 백업이 아닙니다. `.gitignore`에 따라 trajectory·실행 산출물(`.xtc`, `.trr`, `.edr`, `.cpt`, `.tpr`, `.xvg`, `.log`), 대형 애니메이션·샘플링 PDB, ZIP과 분할 백업, Drive 복원 사본, 개인 편집기 설정·인증 정보·임시 파일은 제외합니다. 해당 파일은 로컬에 그대로 보존합니다.

기존 trajectory를 이용하는 분석과 VMD 애니메이션은 필요한 원자료를 별도로 전달받거나 생성해야 합니다. 저장소만 내려받으면 모든 과거 분석·영상이 즉시 재생성되는 것은 아닙니다. 백업 관리 문서: [환경 안내](09_Research_Environment/README_FIRST_KOR.md).

## fftool

`90_Reproduce_Scripts/tools/fftool`은 [paduagroup/fftool](https://github.com/paduagroup/fftool)의 Git submodule입니다. 고정 버전은 `39d980be16d0123a72ba698a437476f2e535407a`입니다. 저장소를 clone할 때 `--recurse-submodules`를 사용하거나, clone한 폴더에서 아래 명령을 실행합니다.

```bash
git submodule update --init --recursive
python 90_Reproduce_Scripts/tools/fftool/fftool -h
```

GitHub의 Download ZIP에는 submodule의 실제 파일이 들어가지 않으므로 fftool은 별도로 받아야 합니다. fftool의 원저작자 표시와 MIT 라이선스는 해당 submodule의 `LICENSE`를 따릅니다. 강의자료·외부 원자료를 포함한 다른 파일에 이 라이선스가 일괄 적용되는 것은 아닙니다.

## 검증 범위

- **Implemented**: 연구 입력, 분석 코드, 환경 파일과 문서가 존재합니다.
- **Unit-verified**: 과거 테스트 기록은 각 연구·전달 문서에 있으며, 새 환경에서의 실행 결과는 별도로 남겨야 합니다.
- **Simulator-verified**: 이번 GitHub 게시 준비에서는 수행하지 않았습니다.
- **Physical-device-verified**: 이번 게시 준비에서 MD 계산이나 다른 컴퓨터 재현은 수행하지 않았습니다.
- **Not verified / 미검증**: 열역학적 평형, force field 정확도, 최종 수송 물성, 팀원 PC·연구실 서버에서의 재현성.
