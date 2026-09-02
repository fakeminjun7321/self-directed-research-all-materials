# 로컬 Mac 열 감시 기록

## 적용 조건

- 감시 간격: 15초
- 최초 체인 기준은 70/60 °C였으나, 2026-08-07 00:39 KST 사용자가 Mac 안전 우선을 요청해 이후 기준을 10 °C 낮췄다.
- 현재 일시정지: 사용 가능한 열 센서의 최댓값이 60 °C 이상이거나 `pmset -g therm`에 열·성능 경고가 나타날 때
- 현재 재개: 센서 최댓값이 50 °C 이하이고 열·성능 경고가 모두 사라졌을 때
- 현재 계산 자원: 한 번에 한 체인, 6 OpenMP threads
- 동작: 계산 프로세스에 `SIGSTOP`을 보내 일시정지하고, 냉각 뒤 `SIGCONT`로 동일 프로세스를 재개한다.
- 실행 중 Mac 수면 방지: 별도 `caffeinate -dimsu` assertion을 유지한다.

## 센서 범위와 한계

비관리자 권한에서 이 Mac이 노출하는 `AppleSmartBattery.Temperature`와 `VirtualTemperature`를 기록한다. 전자는 0.1 K 단위 값을 °C로 변환하고, 후자는 0.01 °C 단위로 해석한다. 이 값들은 CPU die 온도가 아니다.

CPU die 온도를 직접 읽는 `powermetrics --samplers smc`는 관리자 권한을 요구해 이번 무인 실행에서는 사용할 수 없다. 60 °C 기준은 위의 battery/virtual 센서 최댓값에만 적용되며 CPU die는 guard 입력이 아니다. 따라서 CPU die가 60 °C 미만이었다고 확인할 수 없고, 이 공백은 macOS의 열·성능 경고를 별도 중단 조건으로 사용해 보완한다.

## 3 ns 연장 실행 기록

| 실행 | 표본 수 | 가용 센서 최댓값 (°C) | pause / resume | 열·성능 경고 | 대상 rc |
|---|---:|---:|---:|---:|---:|
| rho1000 본 연장 | 150 | 40.75 | 0 / 0 | 0 | 1 |
| rho1000 완료 산출물 재검증 | 1 | 40.65 | 0 / 0 | 0 | 0 |
| rho1200 clean 연장 | 149 | 41.05 | 0 / 0 | 0 | 0 |
| rho1400 연장 | 153 | 40.85 | 0 / 0 | 0 | 0 |

rho1000 본 연장의 rc=1은 GROMACS 실행 실패가 아니라, 구 검증기가 append 로그에 `Finished mdrun` 2개를 요구한 잘못된 가정 때문이다. 누적 3 ns 산출물은 mdrun 재실행 없이 형식 인지 검증기로 재검증해 rc=0을 확인했다.

## 검증 수준

- **Implemented**: `scripts/thermal_guard.py`에 설정 가능한 hysteresis와 macOS 경고 기반 pause/resume가 구현되어 있으며 현재 실행은 60/50 °C를 사용한다.
- **Unit-verified**: 센서 오류 보고, 프로세스 그룹 일시정지·종료·에스컬레이션, 6-thread 정책을 포함한 현재 전체 104개 테스트와 Python 문법 검사가 통과했다.
- **Physical-device-verified**: 세 GROMACS 연장을 60/50 °C, 15초 표본, 한 체인·OpenMP 스레드 6개 조건으로 실행하고 JSONL 기록과 종료 코드를 확인했다. 관측된 가용 센서 최댓값은 41.05 °C였다.
- **Not verified / 미검증**: 실제 60 °C 도달에 의한 `SIGSTOP`과 냉각 후 `SIGCONT` 경로, CPU die 직접 온도.

각 체인의 실제 표본과 pause/resume event는 `thermal_guard_*.jsonl`에 보존한다.
