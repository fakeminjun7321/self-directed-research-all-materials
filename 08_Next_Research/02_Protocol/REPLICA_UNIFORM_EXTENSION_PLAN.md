# R1·R2·R3 동일 3 ns 연장 계획

> **PLANNED / NOT EXECUTED**  
> 1 ns 독립 replica 판정 `ONE_NS_REPLICA_UNIFORM_EXTENSION_REQUIRED`에 따른 다음 실행 계획이다. 세 체인 중 하나만 먼저 선택해 과학적 결론을 내리지 않는다.

## 지금 시작하지 않은 이유

기존 2 ns 연장 실측은 체인당 약 37분이었으므로 세 체인을 순차 실행하면 계산만 약 2시간이고 분석·감사 시간이 추가로 필요하다. 보류를 결정한 2026-08-07 05:12 KST에는 현재 약 6시간 작업 창이 1시간보다 적게 남아 있어 세 체인을 같은 길이로 끝낼 수 없었다. 일부 replica만 연장하면 비교 window가 달라지므로, 새 작업 창에서 세 체인을 모두 마칠 수 있을 때 시작한다.

## 실행 순서

R1 → R2 → R3를 한 번에 하나씩 실행한다. 각 체인마다 아래 순서를 완료한 뒤 다음 체인으로 넘어간다.

1. 현재 1 ns base metrics, EDR 0–1000 ps, checkpoint, TPR, log 완료 marker와 source hash를 확인한다.
2. `extend_npt.py`로 base snapshot을 고정하고 NPT를 2 ns 추가해 누적 3 ns로 만든다.
3. thermal guard rc, 최고 가용 센서, pause/resume 및 macOS 열·성능 경고를 확인한다.
4. `analyze_npt_extension.py`로 누적 0–3000 ps와 마지막 1 ns를 분석한다.
5. 세 체인이 모두 기술 완료된 뒤에만 별도 독립-replica 3 ns comparator를 실행한다. 이 comparator는 현재 **Not implemented / 미구현**이므로 다음 연장 전에 구현·합성 테스트를 먼저 완료한다. 초기 밀도 cross-start용 `compare_three_ns_screen.py`를 대신 사용하지 않는다.
6. 중앙 registry는 모든 분석을 통과한 뒤 dry-run → 실제 rebuild → 재 dry-run 순서로 갱신한다.

## 안전 고정값

- 가용 battery/virtual 센서가 60 °C 이상으로 관측되면 최대 한 감시 주기(15초) 안에 일시정지
- 50 °C 이하이고 macOS 열·성능 경고가 없을 때만 재개
- 15초 감시 간격
- 동시에 한 체인만 실행
- OpenMP 스레드 정확히 6개
- CPU die 온도는 직접 읽지 못하므로 **Not verified / 미검증**

## 예정 명령 형태

각 `<R#>`에 R1, R2, R3를 순서대로 대입한다.

작업 시작 전에 별도 터미널에서 이 작업 전용 sleep 방지를 실행하고 PID를 기록한다. 전체 작업이 끝나면 기록한 이 PID만 종료하며, 기존의 다른 `caffeinate` 프로세스는 건드리지 않는다.

```bash
caffeinate -dimsu &
extension_caffeinate_pid=$!
echo "$extension_caffeinate_pid"
```

```bash
/opt/anaconda3/bin/python scripts/thermal_guard.py \
  --high-c 60 --resume-c 50 --poll-seconds 15 \
  --log "06_Reproducibility/thermal_guard_replica_<R#>_extend2ns_strict60.jsonl" -- \
  /opt/anaconda3/bin/python scripts/extend_npt.py \
  "04_Runs/replica_L1P1x2_rho1400_<R#>_exec_20260807" \
  --extend-ps 2000 --threads 6

/opt/anaconda3/bin/python scripts/analyze_npt_extension.py \
  "04_Runs/replica_L1P1x2_rho1400_<R#>_exec_20260807"
```

중단 뒤 재개는 해당 `extensions/npt_ext001` directory가 존재할 때 thermal guard 내부 `extend_npt.py` 명령에 `--resume`을 추가한다. directory가 없으면 `--resume`을 쓰지 않는다. directory는 있으나 manifest 생성 전에 중단된 경우에도 `--resume`을 사용하며, 스크립트가 남은 snapshot·manifest 상태를 fail-closed로 검사해 복구하거나 거부한다.

모든 실행·분석·registry 재검증이 끝난 뒤, 시작할 때 기록한 작업 전용 PID가 여전히 `caffeinate -dimsu`인지 확인하고 그 PID만 종료한다.

## 3 ns 후 판정 원칙

- 세 체인 모두 동일한 마지막 1 ns window를 사용한다.
- hard fail 또는 provenance 불일치가 하나라도 있으면 3-replica 결과를 만들지 않는다.
- 개별 체인의 3 ns stationarity 판정과 replica 간 밀도 spread/pairwise 차이를 분리해 보고한다.
- 대표 trajectory는 결과가 좋아 보이는 체인으로 사후 선택하지 않는다.
- 3 ns 결과도 평형·production·구조·수송 물성의 자동 승인이 아니다.

## 검증 수준

- **Implemented**: `extend_npt.py`, `analyze_npt_extension.py`, thermal guard와 1 ns base provenance가 존재한다.
- **Unit-verified**: 현재 전체 104개 테스트가 통과했다.
- **Physical-device-verified**: 같은 연장 경로는 초기 밀도 탐색 3개 체인에서 실제 사용·검증됐다.
- **Not implemented / 미구현**: 독립 replica 전용 3 ns comparator와 합성 테스트.
- **Not verified / 미검증**: 독립 R1·R2·R3의 2 ns 추가 연장과 총 3 ns 비교. 이 문서 작성 시점에는 시작하지 않았다.
