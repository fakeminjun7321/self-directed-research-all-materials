# 연구·보고서·백업 환경

이 폴더는 시뮬레이션 실행 환경, 최종 보고서 작성 환경, Google Drive 선별 백업 정책을 한곳에서 관리한다.

## 핵심 원칙

1. `07_Handoff` 교수 전달본은 불변으로 보존한다.
2. 스크립트·프로토콜·QC·보고서·그림은 Google Drive에 선별 백업한다.
3. XTC/TRR/EDR/CPT/TPR 및 대형 PDB trajectory는 기본 Drive 백업에서 제외한다.
4. 제외한 대용량 파일도 `workspace_manifest.csv`의 SHA-256으로 추적한다.
5. 대용량 원본은 Mac 외에 외장 SSD 또는 연구실 서버에 한 벌 더 보관한다.
6. Drive 업로드가 성공했다는 말은 업로드 후 metadata를 다시 읽어 이름·크기·폴더를 확인했을 때만 사용한다.

## 현재 Google Drive 구조

- 루트: `2026_자율연구_CILE_MD`
- `00_README`: 정책·manifest
- `01_Professor_Handoff`: 교수 전달용 불변 ZIP
- `02_Report_Working`: HWPX/PDF/그림을 묶은 보고서 작업본
- `03_Reproducibility`: 코드·프로토콜·환경·QC 재현 패키지
- `04_Selected_Results`: 핵심 비교 JSON·CSV·보고서
- `90_Backup_Archives`: 날짜별 선별 백업 아카이브

Drive 폴더 ID와 URL은 `drive_folder_map.json`에 기록한다. 폴더 ID는 비밀키가 아니지만 공유 권한은 기본 비공개로 유지한다.

Mac 저장공간 절감용 오프로드는 `91_Mac_Storage_Offload/날짜`에 따로 보관한다. 활성 run과 재시작 파일은 오프로드하지 않는다. 100 MB를 넘는 ZIP은 `.part-aa`, `.part-ab`로 나뉘며 `OFFLOAD_MANIFEST_YYYYMMDD.json`의 `cat` 명령으로 원본 ZIP을 복구한다.

## 로컬 실행

```bash
bash 09_Research_Environment/scripts/capture_environment.sh
/opt/anaconda3/bin/python 09_Research_Environment/scripts/preflight_environment.py
bash 09_Research_Environment/scripts/build_drive_packages.sh
/opt/anaconda3/bin/python -m unittest -v \
  09_Research_Environment/tests/test_environment_artifacts.py
```

백업 생성기는 기존 파일을 삭제하지 않는다. 같은 날짜의 패키지가 이미 있으면 덮어쓰지 않고 중단한다.

## 보고서 작성

최종 보고서 원본은 `05_Report/2026_Final`에서 관리한다. 분석 결과는 사람이 숫자를 옮겨 적지 않고 검증된 JSON/CSV에서 가져온다. 기존 50 ps 그림은 workflow 설명용 예비 자료이며 최종 물성 결과로 사용하지 않는다.

## 검증 수준

- **Implemented**: 환경 명세, 보고서 폴더, 백업 정책·스크립트와 Drive 폴더 구조.
- **Not verified / 미검증**: 다른 Mac/Linux 서버에서 `environment.yml`로 새 환경을 실제 재생성하는 경로, 외장 SSD 이중 백업.
