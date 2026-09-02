# LiFSI/Pyr13FSI 이온성 액체 전해질의 분자동역학 탐색 연구

## 초록

본 연구에서는 LiFSI/Pyr13FSI 계열 이온성 액체 전해질의 분자동역학 시뮬레이션 환경을 구축하고, 초기 밀도 및 독립 초기화 조건에 대한 탐색적 평형화 거동을 조사하였다. 현재 결과는 기술적 실행과 초기 반복 간 일치 여부를 검증한 단계이며, 열역학적 평형이나 수송 물성을 확정하지 않는다.

> TODO: 최종 제출 분량에 맞춰 연구 목적, 핵심 수치, 결론을 5–7문장으로 정리한다.

## 1. 연구 동기와 목적

> TODO: 연구 질문과 교육적·과학적 동기를 작성한다.

## 2. 이론적 배경

> TODO: MD, ensemble, RDF, MSD 및 전하 스케일링을 참고문헌과 함께 설명한다.

## 3. 연구 방법

상세 실행 조건과 재현 근거는 `METHODS.md`를 기준으로 작성한다.

## 4. 결과

검증된 수치는 `RESULTS_TABLE.csv`를 기준으로 옮긴다.

### 4.1 초기 밀도 민감도 탐색

L1P1x2 후보의 서로 다른 초기 밀도 세 체인은 총 NPT 3 ns 탐색에서 마지막 1 ns 평균 밀도 spread 1.2557%를 보였다. 이 결과는 `THREE_NS_SAME_BASIN_CANDIDATE`로 판정됐으나, 세 체인이 같은 속도 seed를 사용했으므로 독립 replica 결과가 아니다.

### 4.2 독립 replica 1 ns 탐색

서로 다른 Packmol seed와 NVT velocity seed를 사용한 세 replica의 마지막 500 ps 평균 밀도는 1513.96, 1515.56, 1516.76 kg/m³였다. replica 간 spread는 0.1846%였지만 세 체인 모두 사전 stationarity 문턱에서 `SCREEN_EXTEND`로 판정됐다. 따라서 집합 판정은 `ONE_NS_REPLICA_UNIFORM_EXTENSION_REQUIRED`다.

## 5. 논의

밀도 평균의 근접성은 초기 반복 간 유사한 밀도 영역을 탐색했다는 증거이지만, 짧은 분석 구간의 온도 slope와 아직 수행하지 않은 장시간 구조·수송 분석 때문에 평형을 선언할 수 없다.

## 6. 결론과 후속 계획

본 연구는 재현 가능한 입력 생성, 안전한 로컬 실행, 자동 QC, checksum 기반 provenance와 독립 replica 설계를 구현했다. 다음 단계는 세 replica의 동일 총 3 ns 연장, 독립 replica 전용 비교기 적용, 연구실 서버 재현이다.

## 검증 한계

`LIMITATIONS.md`의 내용을 최종 본문 분량에 맞춰 요약한다.

## 참고문헌

> TODO: `references.bib`의 검증된 항목만 렌더링한다.
