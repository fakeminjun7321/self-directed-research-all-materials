# 팀원용 Windows 연구 환경 설정

이 문서는 2026 자율연구의 LiFSI/Pyr13FSI 분자동역학 파일을 Windows에서 다루기 위한 안내서다. 계산은 `WSL2 + Ubuntu`, 시각화는 Windows용 VMD·PyMOL을 사용하는 구성을 기준으로 한다.

Windows 네이티브 GROMACS를 직접 빌드할 수도 있지만 MSVC, CMake, FFT 설정까지 팀원별로 달라질 수 있다. 팀의 계산 환경을 맞추기 위해 WSL2를 기본 경로로 사용한다.

| 항목 | 기준 |
|---|---|
| Windows | Windows 11 또는 WSL을 지원하는 Windows 10 |
| 계산 환경 | WSL2 Ubuntu |
| GROMACS | 2026.3, WSL 내부 설치 |
| Packmol | 21.2.3, WSL 내부 설치 |
| Python | 3.13, WSL 내부 Conda 환경 |
| Python 환경 이름 | `cile-md-report` |
| 시각화 | Windows용 VMD·PyMOL |
| 프로젝트 크기 | Git 게시 파일 약 79 MiB, 전체 로컬 자료와 추가 계산 결과는 별도 |

> Windows PowerShell 명령과 Ubuntu 명령을 섞어 입력하지 않는다. 각 코드 블록 위의 실행 위치를 확인한다.

## 1. Windows 정보 확인

PowerShell에서 다음을 실행하고 결과를 팀에 남긴다.

```powershell
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, OsArchitecture, CsTotalPhysicalMemory
Get-PSDrive C
```

작업 관리자에서 CPU 가상화가 활성화되어 있는지도 확인한다.

## 2. WSL2와 Ubuntu 설치

관리자 권한으로 PowerShell을 열고 실행한다.

```powershell
wsl --install -d Ubuntu
```

설치가 끝나면 Windows를 재부팅하고 Ubuntu를 한 번 실행한다. Linux 사용자 이름과 비밀번호를 새로 만든다.

PowerShell에서 WSL 버전을 확인한다.

```powershell
wsl --list --verbose
```

Ubuntu의 `VERSION` 열이 `2`여야 한다. WSL 설치 안내는 [Microsoft 공식 문서](https://learn.microsoft.com/windows/wsl/install)를 참고한다.

## 3. Ubuntu 기본 도구 설치

여기부터는 **Ubuntu/WSL 터미널**에서 실행한다.

```bash
sudo apt update
sudo apt install -y git curl wget build-essential ca-certificates
```

확인:

```bash
uname -m
git --version
```

일반적인 Intel·AMD Windows PC에서는 `uname -m`이 `x86_64`로 나온다. ARM Windows라면 Miniforge도 Linux `aarch64` 설치 파일을 선택해야 한다.

## 4. WSL 내부에 Miniforge 설치

[Miniforge 공식 배포 페이지](https://github.com/conda-forge/miniforge/releases)에서 WSL 아키텍처에 맞는 Linux 설치 파일을 사용한다.

- Intel·AMD Windows: `Miniforge3-Linux-x86_64.sh`
- ARM Windows: `Miniforge3-Linux-aarch64.sh`

설치가 끝난 뒤 Ubuntu 터미널을 닫았다가 다시 열고 확인한다.

```bash
conda --version
```

Windows에 이미 Anaconda가 설치되어 있어도 WSL에서는 보통 사용할 수 없다. 계산용 Conda는 WSL 내부에 별도로 설치한다.

## 5. 프로젝트 폴더를 WSL 홈으로 받기

권장 위치:

```text
/home/리눅스사용자이름/cile-md
```

Windows 탐색기 주소창에서 다음 경로로 WSL 파일에 접근할 수 있다.

```text
\\wsl$\Ubuntu\home\리눅스사용자이름
```

프로젝트를 `C:\` 아래에 두고 `/mnt/c/...`에서 직접 장시간 계산하지 않는다. WSL 홈에 복사해야 파일 입출력 성능과 Linux 권한 처리가 안정적이다.

GitHub 프로젝트 [자율연구](https://github.com/users/fakeminjun7321/projects/2)에 연결된 공개 저장소 [자율연구 전체 자료](https://github.com/fakeminjun7321/self-directed-research-all-materials)에서 파일을 받는다. 다운로드에는 GitHub 로그인이나 접근 권한 신청이 필요하지 않다. **Ubuntu/WSL 터미널**에서 다음 명령을 실행한다. 대상 폴더가 이미 있다면 다른 빈 경로를 사용한다.

```bash
git clone --recurse-submodules https://github.com/fakeminjun7321/self-directed-research-all-materials.git "$HOME/cile-md"
```

GitHub CLI를 사용하는 clone 방법은 루트 `README.md`의 "파일 받기"를 참고한다. `--recurse-submodules`는 fftool을 함께 받기 위해 필요하다. GitHub Download ZIP에는 fftool의 실제 파일이 포함되지 않는다.

trajectory·checkpoint·XVG·실행 로그·대형 애니메이션 PDB·백업 ZIP은 Git에 포함하지 않는다. 기존 결과의 재분석이나 VMD 애니메이션에 필요한 원자료는 별도로 전달받거나 생성해야 한다. clone만으로 과거 계산 결과 전체를 복원할 수는 없다.

## 6. Python 분석 환경 생성

Ubuntu/WSL 터미널에서 프로젝트 루트로 이동한다.

```bash
cd "$HOME/cile-md"
conda env create -f environment.yml
conda activate cile-md-report
```

설치 확인:

```bash
python --version
python -c "import numpy, pandas, scipy, matplotlib, seaborn, yaml; print('PYTHON_PACKAGES_OK')"
```

## 7. GROMACS와 Packmol 설치

Windows 네이티브가 아니라 활성화된 WSL Conda 환경에 설치한다.

```bash
conda activate cile-md-report
conda install -c conda-forge gromacs=2026.3
python -m pip install packmol==21.2.3
```

확인:

```bash
command -v gmx
gmx --version
command -v packmol
python --version
```

기준은 GROMACS `2026.3`, Packmol `21.2.3`, Python `3.13.x`이다. 먼저 CPU 경로를 검증하고, NVIDIA GPU/CUDA 가속은 팀에서 별도로 합의하기 전에는 추가하지 않는다. 기존 기준 Mac도 CPU-only GROMACS로 기록되어 있다.

## 8. fftool 확인

`fftool`은 프로젝트에 포함되어 있으므로 별도 다운로드하지 않는다.

```bash
cd "$HOME/cile-md"
conda activate cile-md-report
python 90_Reproduce_Scripts/tools/fftool/fftool -h
```

## 9. Windows용 VMD 설치

[VMD 공식 사이트](https://www.ks.uiuc.edu/Research/vmd/)에서 Windows 64비트 빌드를 받아 Windows에 설치한다.

현재 프로젝트의 다음 파일은 macOS 전용이므로 Windows에서 더블클릭해 실행할 수 없다.

```text
00_START_HERE/OPEN_VMD_50ps_animation.command
00_START_HERE/OPEN_VMD_P2_series.command
```

Windows VMD에서 다음 파일을 직접 연다.

```text
03_Analysis_Results/VMD_View/01_all_five_50ps_animation.pdb
```

필요하면 VMD의 Tk Console에서 다음 Tcl 파일을 불러온다.

```text
03_Analysis_Results/VMD_View/VMD_01_open_50ps_animation.tcl
```

50 ps 구조는 시각화·workflow 확인용이며 평형이나 최종 물성을 증명하지 않는다.

## 10. 선택 프로그램

Windows에 직접 설치:

- PyMOL: 추가 구조 시각화와 PNG frame 생성
- FFmpeg: PNG frame을 MP4로 변환할 때 필요
- Windows Terminal: WSL 터미널 사용 편의
- VS Code: 스크립트 편집용
- Obsidian: 연구 노트 열람용

WSL에서 보고서 빌드까지 해야 한다면 다음을 추가할 수 있다.

```bash
sudo apt install -y pandoc latexmk texlive-latex-base
```

## 11. 계산 전에 실행할 검사

아래 명령은 **Ubuntu/WSL 터미널**에서 실행한다.

### 11.1 정적 입력 검사: MD를 실행하지 않음

```bash
cd "$HOME/cile-md/07_Handoff/CILE_MD_Handoff_v0_DRAFT"
bash validate_inputs.sh
```

성공 기준:

```text
Static validation PASSED
```

### 11.2 GROMACS 전처리 검사: `mdrun`을 실행하지 않음

```bash
bash validate_grompp.sh
```

성공 기준:

```text
grompp validation PASSED for all five systems.
```

이 단계는 TPR 생성과 입력 호환성만 확인한다.

### 11.3 기술 smoke: 승인 후 실행

다음 명령은 5개 시스템에서 각 단계 20 step을 실제 실행하고 `validation/smoke` 아래에 결과를 생성한다.

```bash
THREADS=2 bash run_smoke_all.sh
```

이 결과는 WSL에서 명령 연결과 파일 형식이 동작한다는 것만 확인한다. 밀도, 평형, box 안정성, production 타당성은 확인하지 않는다.

## 12. 팀에 제출할 설치 확인 기록

Ubuntu/WSL 터미널에서 다음 출력을 복사해 담당자에게 보낸다.

```bash
uname -a
cat /etc/os-release
gmx --version | sed -n '1,20p'
python --version
conda env list
command -v gmx packmol python
```

PowerShell에서는 다음 결과도 함께 보낸다.

```powershell
wsl --list --verbose
```

## 검증 수준

- **Implemented:** WSL2 기준 설치 절차와 프로젝트의 Linux/bash 검증 스크립트가 있다.
- **Unit-verified:** 기존 인계 패키지의 정적 검사와 macOS GROMACS 전처리 검사는 과거에 통과한 기록이 있다.
- **Physical-device-verified:** 기존 개인 Mac의 기술 경로만 부분 확인되었다.
- **Not verified / 미검증:** 새 Windows PC의 WSL2에서 Conda 환경 생성, GROMACS·Packmol 설치, `grompp`, smoke 및 실제 출력은 아직 확인되지 않았다.
