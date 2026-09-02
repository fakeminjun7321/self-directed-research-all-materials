#!/usr/bin/env python3
"""Render the exploratory three-density comparison JSON as a Korean Markdown report."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path


def number(value: object, digits: int = 3) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"expected numeric value, got {value!r}")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"non-finite value: {value!r}")
    return f"{converted:.{digits}f}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("comparison", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.force:
        raise SystemExit(f"refusing to overwrite without --force: {args.output}")
    payload = json.loads(args.comparison.read_text())
    chains = payload.get("chains")
    if not isinstance(chains, list) or len(chains) != 3:
        raise SystemExit("comparison must contain exactly three chains")
    rows = []
    for chain in sorted(chains, key=lambda item: item["initial_density_kg_m3"]):
        failures = chain.get("hard_fail_reasons")
        if not isinstance(failures, list):
            raise SystemExit("hard_fail_reasons must be a list")
        rows.append(
            "| {chain} | {initial} | {density} | {slope} | {block} | {margin} | {verdict} | {failures} |".format(
                chain=chain["chain_id"],
                initial=number(chain["initial_density_kg_m3"], 1),
                density=number(chain["last500_density_mean"], 2),
                slope=number(chain["density_slope_percent_per_ns"], 3),
                block=number(chain["last_two_block_diff_percent"], 3),
                margin=number(chain["min_box_over_2rlist"], 4),
                verdict=chain["exploratory_verdict"],
                failures=", ".join(failures) if failures else "없음",
            )
        )
    best = payload.get("best_exploratory_chain") or "없음"
    content = f"""# L1P1x2 초기 밀도 민감도 탐색 보고서

## 결과 요약

- 교차 초기조건 판정: `{payload['cross_start_assessment']}`
- 마지막 500 ps 평균 밀도의 체인 간 spread: {number(payload['plateau_spread_percent'], 3)}%
- 후속 검토 우선 체인: `{best}`
- 물리 상태: `{payload['physics_status']}`

| chain | 초기 밀도 (kg/m³) | 마지막 500 ps 밀도 (kg/m³) | 밀도 slope (%/ns) | 마지막 두 block 차이 (%) | min box/(2rlist) | screen verdict | hard fail |
|---|---:|---:|---:|---:|---:|---|---|
{chr(10).join(rows)}

## 검증 수준

- **Implemented**: 동일 조성의 세 초기 밀도 후보, 고정 seed NVT 100 ps, C-rescale NPT 1 ns, 자동 QC와 교차 비교가 기록되었다.
- **Unit-verified**: 열 매핑·시간축·TPR 길이·비교 가능성·screen 수식의 집중 테스트를 통과했다.
- **Physical-device-verified**: 각 표에 포함된 체인은 이 Mac에서 실제 GROMACS 경로가 끝나고 EDR 시간 범위·로그·에너지 열을 확인한 경우에만 포함된다.
- **Not verified / 미검증**: 연구실 서버 재현, 교수님 승인 프로토콜, 장시간 평형, 독립 packing/seed replica, force-field 및 0.75 전하 스케일의 물리 타당성, production·RDF·확산·전도도.

`SCREEN_STATIONARITY_PASS`와 `SAME_BASIN_CANDIDATE`는 1 ns 탐색 window의 임시 기준일 뿐 평형 또는 production 준비를 뜻하지 않는다. `best_exploratory_chain`도 연구 결과의 우수성을 뜻하지 않고 다음 연장·반복 검토의 우선순위다.
"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(f".{args.output.name}.{os.getpid()}.tmp")
    temporary.write_text(content)
    os.replace(temporary, args.output)


if __name__ == "__main__":
    main()
