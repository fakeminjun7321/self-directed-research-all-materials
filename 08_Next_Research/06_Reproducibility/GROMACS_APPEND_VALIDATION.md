# GROMACS checkpoint append 검증 기준

> **PROVISIONAL / EXPLORATORY ONLY**  
> 이 문서는 GROMACS 2026.3에서 1 ns NPT checkpoint를 이어 총 3 ns로 연장할 때의 파일 연속성 검증 규칙을 기록한다. 이 검증은 trajectory provenance를 점검할 뿐 평형이나 production 타당성을 입증하지 않는다.

## 1. 실제 append에서 관찰한 파일 동작

`screen_L1P1x2_rho1000_20260807` 1 ns checkpoint에서 `gmx mdrun -cpi npt.cpt -append`를 시작한 실제 Mac 경로에서 다음을 확인했다.

- `base_snapshot/`에 원본 TPR, CPT, EDR, XTC, LOG, GRO, metrics를 SHA-256과 함께 불변 보존했다.
- extended TPR은 `dt = 0.001 ps`, `nsteps = 3,000,000`이다.
- GROMACS console은 `continuing from step 1000000, 1000.0 ps`를 기록했다.
- checkpoint가 기록한 append 유효 offset은 LOG 624,164 byte, EDR 612,704 byte, XTC 9,054,764 byte이다. 세 파일은 해당 offset까지 원본과 누적 파일이 byte-exact로 같았다.
- XTC는 동결된 base 파일 전체가 누적 XTC의 접두사로 그대로 보존됐다.
- EDR과 LOG는 checkpoint 이후의 기존 종료 suffix를 재작성했다. 이는 누적 파일 전체가 base 파일의 literal byte-prefix여야 한다는 가정이 잘못되었음을 뜻한다.
- base/live EDR에서 `gmx eneconv -b 0 -e 999`로 추출한 0–999 ps 구간은 SHA-256과 byte가 완전히 같았고, `gmx check -e/-e2 -tol 0 -abstol 0`에서 45개 에너지 항목이 일치했다.
- 1000 ps checkpoint 경계 frame에서만 restart 재계산에 따른 미세한 파생값 차이가 나타났다. Temperature, Density, Volume, Box-X/Y/Z는 같았고, Pressure와 Potential 차이는 각각 약 0.00745 bar, 0.00391 kJ/mol이었다.

## 2. 완료 trajectory에 적용할 fail-closed 검증

`scripts/extend_npt.py`는 완료 후 다음을 모두 요구한다.

1. manifest의 base snapshot SHA-256과 실제 동결 파일이 모두 일치해야 한다.
2. XTC는 동결 base XTC 전체를 byte-prefix로 보존해야 한다.
3. base/live EDR의 checkpoint 직전 0–999 ps 구간은 canonical EDR SHA-256과 45개 항목 zero-tolerance 비교가 모두 같아야 한다.
4. 1000 ps 경계를 포함한 base/live EDR 비교는 GROMACS native 의미 비교를 사용하되, 출력에 mismatch 행이 있으면 거부한다. `gmx check`는 mismatch에도 exit code 0을 반환할 수 있으므로 반환 코드만 신뢰하지 않는다.
5. live EDR은 0–3000 ps, 1 ps cadence, 3001 frame의 단조·연속 시간축을 가져야 한다.
6. live log에 `Reading checkpoint` → `Restarting ... appending` → `Started mdrun` → 최종 `Finished mdrun`의 순서가 있어야 한다.
7. Fatal error, NaN, LINCS warning, segmentation fault는 0개여야 한다.

GROMACS append는 기존 종료 summary를 잘라내므로 live log에는 최종 `Finished mdrun` 1개를 예상한다. `base Finished + extension Finished = 2`를 누적 log에 요구하지 않는다. base의 종료 marker는 동결 `base_snapshot/npt.log`에 따로 보존된다.

## 3. 검증 레벨

- **Implemented**: 형식 인지 append 검증이 `scripts/extend_npt.py`에 구현됐다.
- **Unit-verified**: XTC prefix, EDR exact/canonical 구간, mismatch 출력, 시간축 gap, LOG restart/Finished 순서, bad marker 거부를 포함한 현재 전체 104개 테스트가 통과했다.
- **Physical-device-verified**: 실제 Mac에서 세 chain의 0–3000 ps 누적 파일을 신규 검증기로 검사했다. `rho1000`은 GROMACS 완료 후 구 검증기의 Finished marker=2 가정 때문에 첫 guard가 rc=1이었고, mdrun을 재실행하지 않은 `--resume` 재검증으로 rc=0과 `PASS_COMPLETE`를 확인했다. `rho1200_clean`과 `rho1400`은 첫 `MDRUN_APPEND`에서 rc=0과 `PASS_COMPLETE`를 확인했다. 세 체인 모두 0–3000 ps, 3001 frame, 1 ps 간격, EDR 45항목, XTC full prefix, LOG restart/Finished 순서를 통과했다.
- **Not verified / 미검증**: 이 append provenance는 평형, production, force field 정확도, 독립 replica, 연구실 서버 재현을 입증하지 않는다.
