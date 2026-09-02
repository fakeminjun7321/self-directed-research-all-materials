# Colab Pro Linux 교차검증

이 폴더는 교수님 서버 실행을 대신하지 않습니다. Colab의 깨끗한 Ubuntu 환경에서
압축 해제, checksum, 상대경로, 정적 입력, GROMACS `grompp` 호환성만 교차검증합니다.

## 사용 순서

1. 최종 전달 ZIP과 `CILE_Linux_Validation.ipynb`를 Colab에 업로드합니다.
2. 노트북 셀을 위에서 아래로 실행합니다.
3. `colab_validation_artifacts.zip`을 내려받아 패키지의 `validation/colab/`에 보관합니다.

## 판정 범위

- `validate_inputs.sh` 통과: 파일 수준 정적 검사
- 5개 조성 EM `grompp` 통과: Ubuntu/GROMACS 입력 생성 호환성
- 실제 `mdrun`: 이 노트북의 기본 범위에 포함되지 않음
- 물리적 평형화와 교수님 서버: `Not verified / 미검증`

Colab 런타임과 GPU는 고정되지 않으므로 환경 정보와 실제 명령을 로그에 남깁니다.
