# 최종 보고서 목차 및 완료 조건

## 1. 연구 동기와 질문

- LiFSI/Pyr13FSI 계열 이온성 액체 전해질을 선택한 이유
- 조성 변화가 국소 구조와 이동 특성에 미치는 영향이라는 장기 질문
- 이번 제출에서 실제로 답할 수 있는 범위와 아직 답할 수 없는 범위

## 2. 이론적 배경

- 분자동역학의 기본 개념
- NVT·NPT ensemble과 평형화
- RDF, coordination number, MSD, diffusion의 의미와 요구 trajectory 길이
- 비분극 force field의 전하 스케일링과 한계

## 3. 연구 방법

- 조성·분자 수·초기 밀도
- Packmol 초기화와 두 종류의 seed
- force field와 0.75 전하 스케일
- strict EM, NVT 100 ps, NPT 1 ns 및 3 ns 탐색
- thermal guard와 OpenMP 스레드 제한
- 불변 manifest·checksum·자동 QC

완료 조건: `METHODS.md`의 모든 값에 source 경로 또는 manifest가 연결돼야 한다.

## 4. 결과

### 4.1 기존 50 ps workflow

분석 파이프라인을 구현했다는 증거로만 사용한다. 물성의 정량 비교 결론으로 사용하지 않는다.

### 4.2 초기 밀도 민감도 탐색

- 1,000/1,200/1,400 kg/m³ 시작점
- 총 NPT 3 ns
- 마지막 1 ns 평균과 cross-start spread

### 4.3 독립 replica 1 ns 탐색

- 서로 다른 Packmol·velocity seed
- 마지막 500 ps 밀도 평균과 replica spread
- 세 체인의 `SCREEN_EXTEND`
- `ONE_NS_REPLICA_UNIFORM_EXTENSION_REQUIRED`

완료 조건: 모든 표 숫자가 `RESULTS_TABLE.csv`와 일치해야 한다.

## 5. 논의

- 서로 다른 초기 조건에서 밀도가 가까워진 의미
- 짧은 NVT 온도 slope가 stationarity 판정을 막은 이유
- 0.75 전하 스케일과 목표 밀도 미승인의 영향
- 짧은 trajectory에서 RDF·diffusion 결론을 유보하는 이유

## 6. 결론

- 기술적으로 재현 가능한 MD 탐색 시스템을 구축했다.
- 1 ns replica 밀도는 가깝지만 평형은 검증하지 못했다.
- 다음 단계는 동일 3 ns 연장과 연구실 서버 재현이다.

## 7. 참고문헌

검증된 BibTeX metadata만 사용한다. URL만 확인한 문헌은 `REFERENCE_INBOX.csv`에서 `METADATA_PENDING`으로 유지한다.

## 8. 부록

- software version
- seed와 checksum
- QC 기준표
- Google Drive/외장 백업 정책
- 실행 명령과 미검증 항목
