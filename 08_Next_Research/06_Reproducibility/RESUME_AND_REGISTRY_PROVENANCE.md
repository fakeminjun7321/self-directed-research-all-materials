# Resume 및 중앙 registry provenance

## 기록 원칙

`equilibration_metrics.json`은 최종 요약이지 단독 실행 이력이 아니다. 새 실행은
`equilibration/attempts/`에 시작 기록과 종료 시점 metrics 스냅샷을 write-once로
보존한다. 체크포인트 재개 직전에는 다음 파일을 추가로 보존한다.

- `resume_evidence/<stage>_resume_NNN_checkpoint.cpt`: 실제 `-cpi` 입력의 byte snapshot
- `resume_evidence/<stage>_resume_NNN.json`: snapshot SHA-256, 크기, 재개 직전 EDR 범위

중앙 registry의 `mode=RESUME` 행은 이 증거가 존재하고 실제 파일 hash와 일치할
때만 `checkpoint_in_sha256`을 기록한다. 최종 `stage.cpt`나
`stage_prev.cpt`의 사후 hash를 재개 입력 hash로 대체해서는 안 된다.

## 현재 알려진 제한

기존 `screen_L1P1x2_rho1200_20260807` NPT는 로그상 139.1 ps 지점에서 재개됐다.
그러나 당시 runner는 `-cpi` 입력 checkpoint의 불변 snapshot을 만들지 않았다.
따라서 현재 남은 최종 checkpoint로 과거 입력 SHA-256을 복원할 수 없다.

이 체인은 시뮬레이션 완료 여부와 별개로 **registry provenance 미충족** 상태다.
통합기는 빈 hash를 채우거나 현재 checkpoint hash를 대신 쓰지 않고 중앙 registry
재생성을 거부한다. 이 제한은 기록상 `Not verified / 미검증`으로 유지한다.

## 검증 가능한 quarantine

복구 불가능한 과거 체인 하나가 모든 후속 registry rebuild를 영구 차단하지 않도록
`registry_quarantine.json`을 사용할 수 있다. 이는 임의 skip 목록이 아니다.

- 제외 대상의 `chain_manifest.json`, `equilibration_metrics.json`, 관련 safety
  record SHA-256을 모두 정확히 고정한다.
- 사유 코드는 resume-input checkpoint provenance 손실만 허용한다.
- 정확한 replacement chain ID를 요구한다.
- replacement가 `PASS_COMPLETE`이고 기존 scientific QC와 registry 검증을 전부
  통과해야 한다.
- protocol, seed, NPT 길이, topology·MDP hash, GROMACS version, system ID와 초기
  밀도가 원 체인과 일치해야 한다. 새 clean packing/EM의 좌표 hash만 달라질 수 있다.
- SHA 불일치, replacement 미완료, wildcard·숨은 제외 필드는 전체 rebuild를
  중단한다.

활성화된 제외는 `--dry-run`의 `QUARANTINE_ACTIVE` 행과 별도
`registry_quarantine_audit.json`에 기록된다. audit에는 quarantine config SHA,
원 체인 증거 SHA, replacement manifest·metrics SHA 및 실제 생성된 replacement
record ID가 포함된다. replacement가 미완료인 동안에는 audit를 활성 상태로 만들지
않고 registry 갱신도 허용하지 않는다.

## extension 연결

- `npt:001`: extension 생성 전 `base_snapshot`의 log, metrics, artifact
- `npt:002`: `extension_manifest.json`, `extension_metrics.json`,
  `extension_analysis.json`을 모두 검증한 별도 `EXTEND` segment
- `npt:002.parent_record_id`: 반드시 같은 chain의 `npt:001`
- extension checkpoint hash: 반드시 `base_snapshot/npt.cpt`와 일치

분석 파일이 없거나 source evidence가 바뀌면 중앙 CSV를 갱신하지 않는다. 1 ns의
`SCREEN_*` 판정을 3 ns 결과로 재사용하지 않는다.

## 외부 공유 전 개인정보 및 hash 주의

원시 GROMACS/fftool log와 생성된 MDP 주석에는 사용자 홈 경로, 작업 폴더와 로컬
실행 파일 경로가 포함될 수 있다. 중앙 CSV는 상대 artifact 경로만 기록하지만,
`04_Runs` 전체를 그대로 외부 전송하면 로컬 사용자명과 디렉터리 구조가 노출될 수
있다. 공유본은 별도 staging 폴더에서 경로를 검토·redact하고 원본 run은 수정하지
않는다.

SHA-256은 무결성 식별자이지 암호화나 익명화 수단이 아니다. 입력 파일 hash는
내용 자체를 공개하지 않지만, 알려진 파일과의 동일성 비교에는 사용될 수 있다.
API key, token, password, private key는 manifest·log·registry에 넣지 않는다.

## 검증 수준

- **Implemented**: 향후 attempt 및 resume-checkpoint write-once 기록
- **Unit-verified**: snapshot 변조, hash 누락, metrics 변조, extension·quarantine 연결 오류 거부를 포함한 현재 전체 104개 테스트와 registry self-test 통과
- **Physical-device-verified**: 세 초기 밀도 체인의 3 ns 기록과 독립 R1·R2·R3의 NVT/NPT 기록을 연결해 중앙 registry를 15행·QC 192행으로 재생성했다. 완료되지 않은 chain은 0개였고, 예전 rho1200의 provenance 손실은 SHA-256으로 고정된 quarantine과 clean replacement로 명시적으로 남겼다. 최신 chain/QC registry SHA-256은 각각 `64cdc8f0624a47e545daaae2e220bbfd95eeaf21f6aca26aded79ddd7d076c40`, `8f545e5ed04bb2dcf6350dd6ac9d5b28605cd656d623607c9a6b42da8a895f05`다. 온도 slope QC는 signed source를 유지한 채 중앙 CSV에 `absolute_temperature_slope_per_ns`/`absolute_slope`로 명시한다.
- **Not verified / 미검증**: 실제 새 checkpoint resume에서 생성된 provenance 파일
