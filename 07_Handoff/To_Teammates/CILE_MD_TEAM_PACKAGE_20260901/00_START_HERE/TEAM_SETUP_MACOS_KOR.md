# 팀원용 macOS 연구 환경 설정

이 문서는 2026 자율연구의 LiFSI/Pyr13FSI 분자동역학 파일을 macOS에서 열고, 입력을 점검하고, 같은 도구로 분석하기 위한 설치 안내서다.

기준 환경은 다음과 같다.

| 항목 | 기준 |
|---|---|
| 운영체제 | macOS, Apple Silicon 권장 |
| GROMACS | 2026.3 |
| Packmol | 21.2.3 |
| Python | 3.13 |
| Python 환경 이름 | `cile-md-report` |
| 프로젝트 크기 | 현재 약 1.1 GB, 계산 결과가 추가되면 더 커짐 |

> 설치가 끝났다는 것만으로 연구 결과가 재현된 것은 아니다. 마지막의 정적 검사, `grompp`, 기술 smoke를 단계별로 구분해서 확인한다.

## 1. 컴퓨터 정보 확인

터미널을 열고 다음을 실행한 뒤 결과를 팀에 남긴다.

```bash
uname -m
sw_vers
system_profiler SPHardwareDataType | sed -n '1,20p'
df -h .
```

- `uname -m`이 `arm64`이면 Apple Silicon이다.
- Intel Mac이면 `x86_64`가 나온다. VMD와 Conda 설치 파일도 Intel용을 선택해야 한다.
- 프로젝트 자체 외에 trajectory와 checkpoint가 생성되므로 충분한 여유 공간을 확보한다.

## 2. 프로젝트 폴더 받기

프로젝트 전체 폴더를 전달받아 로컬 디스크에 둔다. 경로에 공백이나 한글이 있어도 대부분의 새 스크립트는 동작하지만, 팀원용 경로는 다음처럼 단순하게 두는 편이 안전하다.

```text
~/Research/cile-md
```

아직 이 프로젝트는 Git 커밋이 없는 로컬 저장소이므로 현재 상태에서는 `git clone`만으로 전체 프로젝트를 받을 수 없다. ZIP, 외장 저장장치 또는 합의한 공유 저장소로 전달받아야 한다.

## 3. Xcode Command Line Tools 설치

```bash
xcode-select --install
```

설치 확인:

```bash
git --version
```

## 4. Homebrew 설치

[Homebrew 공식 사이트](https://brew.sh/)의 설치 명령을 사용한다. 설치 후 새 터미널을 열고 다음을 확인한다.

```bash
brew --version
```

Apple Silicon에서 일반적인 Homebrew 경로는 `/opt/homebrew/bin/brew`이다. Intel Mac에서는 경로가 다를 수 있으므로 스크립트에 `/opt/homebrew`를 직접 입력하지 않는다.

## 5. GROMACS, Packmol, Pandoc 설치

프로젝트 루트로 이동해서 저장된 `Brewfile`을 사용한다.

```bash
cd "$HOME/Research/cile-md"
brew bundle --file Brewfile
```

이 명령으로 설치되는 핵심 도구:

- GROMACS
- Packmol
- Pandoc

설치 확인:

```bash
command -v gmx
gmx --version
command -v packmol
brew list --versions gromacs packmol pandoc
```

기준 버전은 GROMACS `2026.3`, Packmol `21.2.3`이다. Homebrew가 더 새 버전을 설치했다면 바로 장시간 계산을 시작하지 말고 팀에 버전 차이를 기록한다.

## 6. Conda와 Python 분석 환경 설치

Anaconda 또는 Miniforge 중 하나를 설치한다. 새 팀원에게는 가벼운 [Miniforge](https://github.com/conda-forge/miniforge)를 권장한다.

- Apple Silicon: macOS `arm64` 설치 파일
- Intel Mac: macOS `x86_64` 설치 파일

설치 후 새 터미널에서 프로젝트 루트로 이동한다.

```bash
cd "$HOME/Research/cile-md"
conda env create -f environment.yml
conda activate cile-md-report
```

이미 같은 이름의 환경이 있다면 새로 덮어쓰지 말고 먼저 팀에 알린다. 설치 확인:

```bash
python --version
python -c "import numpy, pandas, scipy, matplotlib, seaborn, yaml; print('PYTHON_PACKAGES_OK')"
```

## 7. fftool 확인

`fftool` 소스는 프로젝트에 포함되어 있으므로 별도 다운로드가 필요하지 않다.

```bash
conda activate cile-md-report
python 90_Reproduce_Scripts/tools/fftool/fftool -h
```

반드시 Conda 환경을 활성화한 뒤 실행한다. `env: python: No such file or directory`가 나오면 Conda 환경이 활성화되어 있는지 확인한다.

## 8. VMD 설치

[VMD 공식 사이트](https://www.ks.uiuc.edu/Research/vmd/)에서 Mac 종류에 맞는 빌드를 받아 `/Applications`에 설치한다.

- Apple Silicon Mac: ARM64 빌드
- Intel Mac: x86_64 빌드

설치 후 프로젝트의 다음 파일을 더블클릭해서 확인할 수 있다.

```text
00_START_HERE/OPEN_VMD_50ps_animation.command
00_START_HERE/OPEN_VMD_P2_series.command
```

이 실행 파일들은 `/Applications`와 `~/Applications`의 `VMD*.app`을 찾는다. 표시되는 50 ps 구조는 시각화·workflow 점검용이며 평형이나 최종 물성을 증명하지 않는다.

## 9. 선택 프로그램

영상과 추가 시각화가 필요한 팀원만 설치한다.

```bash
brew install ffmpeg pymol
```

PDF 보고서를 직접 빌드해야 한다면 MacTeX 또는 다른 LaTeX 배포판을 설치하고 확인한다.

```bash
latexmk --version
pandoc --version
ffmpeg -version
pymol --version
```

## 10. 계산 전에 실행할 검사

### 10.1 정적 입력 검사: MD를 실행하지 않음

```bash
cd "$HOME/Research/cile-md/07_Handoff/CILE_MD_Handoff_v0_DRAFT"
bash validate_inputs.sh
```

성공 기준:

```text
Static validation PASSED
```

### 10.2 GROMACS 전처리 검사: `mdrun`을 실행하지 않음

```bash
bash validate_grompp.sh
```

성공 기준:

```text
grompp validation PASSED for all five systems.
```

이 단계는 TPR 생성과 입력 호환성만 확인한다.

### 10.3 기술 smoke: 승인 후 실행

다음 명령은 5개 시스템에서 각 단계 20 step을 실제 실행하고 `validation/smoke` 아래에 결과를 생성한다.

```bash
THREADS=2 bash run_smoke_all.sh
```

이 결과는 명령 연결과 파일 형식만 확인한다. 밀도, 평형, box 안정성, production 타당성은 확인하지 않는다.

## 11. 팀에 제출할 설치 확인 기록

다음 출력을 복사해서 담당자에게 보낸다.

```bash
uname -m
sw_vers -productVersion
gmx --version | sed -n '1,20p'
brew list --versions packmol
python --version
conda env list
command -v gmx packmol python
```

## 검증 수준

- **Implemented:** 프로젝트에 `Brewfile`, `environment.yml`, fftool, macOS용 VMD 실행 파일과 검증 스크립트가 있다.
- **Physical-device-verified:** 기존 Apple Silicon Mac에서 일부 기술 실행 경로가 확인되었다.
- **Not verified / 미검증:** 이 문서를 받은 새 Mac에서 설치, `grompp`, smoke 및 실제 출력은 각 컴퓨터에서 별도로 확인해야 한다.

