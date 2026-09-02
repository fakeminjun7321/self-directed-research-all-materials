#!/usr/bin/env python3
"""Render a three-chain 3 ns exploratory comparison as Korean Markdown."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any


PROJECT = Path(__file__).resolve().parents[2]
NEXT = PROJECT / "08_Next_Research"
PROTECTED_OUTPUT_ROOTS = (NEXT / "04_Runs", PROJECT / "07_Handoff")
EXPECTED_SCHEMA = "three-ns-screen-comparison-v1"
CHAIN_VERDICTS = {
    "THREE_NS_STATIONARITY_CANDIDATE",
    "THREE_NS_EXTEND_OR_REVIEW",
    "THREE_NS_FAIL",
}
CROSS_START_ASSESSMENTS = {
    "THREE_NS_SAME_BASIN_CANDIDATE",
    "THREE_NS_INITIAL_CONDITION_DEPENDENCE_OR_INCOMPLETE",
    "THREE_NS_NOT_CONVERGED",
    "THREE_NS_CROSS_START_INCOMPLETE",
}

ASSESSMENT_KO = {
    "THREE_NS_SAME_BASIN_CANDIDATE": (
        "세 체인이 잠정 stationarity 문턱을 통과했고 마지막 1 ns 평균 밀도 spread가 "
        "2% 이하인 상태다. 독립 replica 설계를 위한 임시 후보일 뿐이다."
    ),
    "THREE_NS_INITIAL_CONDITION_DEPENDENCE_OR_INCOMPLETE": (
        "stationarity 문턱 미충족 또는 2–5% 밀도 spread가 있어 초기조건 의존성 판단이 "
        "끝나지 않았다."
    ),
    "THREE_NS_NOT_CONVERGED": (
        "마지막 1 ns 평균 밀도 spread가 5%를 초과하여 세 시작조건의 수렴 근거가 없다."
    ),
    "THREE_NS_CROSS_START_INCOMPLETE": (
        "하나 이상의 chain에 hard fail이 있어 세 시작조건 비교가 완결되지 않았다."
    ),
}

NOT_VERIFIED_KO = {
    "thermodynamic equilibrium": "열역학적 평형",
    "independent Packmol and velocity-seed replicas": (
        "독립 Packmol 배치와 독립 속도 seed를 사용한 replica 재현성"
    ),
    "production readiness": "production 조건 및 준비 상태",
    "structural and transport-property convergence": "구조·수송 물성의 수렴",
    "laboratory-server reproduction": "연구실 서버 재현",
}


class RendererError(RuntimeError):
    """The comparison JSON is unsafe or incomplete for rendering."""


def reject_json_constant(value: str) -> None:
    raise RendererError(f"non-finite JSON constant: {value}")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(), parse_constant=reject_json_constant)
    except (OSError, json.JSONDecodeError) as exc:
        raise RendererError(f"cannot read comparison JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RendererError("comparison JSON root must be an object")
    return payload


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise RendererError(f"{label} must be numeric, got {value!r}")
    try:
        converted = float(value)
    except (TypeError, ValueError) as exc:
        raise RendererError(f"{label} must be numeric, got {value!r}") from exc
    if not math.isfinite(converted):
        raise RendererError(f"{label} is non-finite")
    return converted


def number(value: Any, digits: int, label: str) -> str:
    return f"{finite_number(value, label):.{digits}f}"


def require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise RendererError(f"{label} must be a list")
    return value


def require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RendererError(f"{label} must be an object")
    return value


def markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def reason_cell(hard: list[Any], review: list[Any]) -> str:
    for reason in hard + review:
        if not isinstance(reason, str) or not reason:
            raise RendererError("hard/review reasons must be non-empty strings")
    parts = [f"hard: `{markdown_cell(reason)}`" for reason in hard]
    parts += [f"review: `{markdown_cell(reason)}`" for reason in review]
    return "<br>".join(parts) if parts else "없음"


def validate_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("schema_version") != EXPECTED_SCHEMA:
        raise RendererError(f"unsupported comparison schema: {payload.get('schema_version')!r}")
    for key, expected in (
        ("technical_status", "PASS_COMPLETE"),
        ("analysis_status", "PASS_COMPLETE"),
        ("physics_status", "EXPLORATORY_ONLY"),
    ):
        if payload.get(key) != expected:
            raise RendererError(f"comparison {key} mismatch: {payload.get(key)!r}")
    if payload.get("equilibrium_validated") is not False:
        raise RendererError("comparison JSON claims equilibrium validation")
    if payload.get("production_ready") is not False:
        raise RendererError("comparison JSON claims production readiness")

    assessment = payload.get("cross_start_assessment")
    if assessment not in CROSS_START_ASSESSMENTS:
        raise RendererError(f"unsupported cross-start assessment: {assessment!r}")
    spread = finite_number(
        payload.get("last1ns_density_spread_percent"), "last-1-ns density spread"
    )
    if spread < 0:
        raise RendererError("last-1-ns density spread must be non-negative")

    comparability = require_dict(payload.get("comparability"), "comparability")
    if comparability.get("same_protocol") is not True:
        raise RendererError("chains are not recorded as the same protocol")
    if comparability.get("same_seed") is not True:
        raise RendererError("chains are not recorded as the same seed")
    if comparability.get("same_seed_chains_are_independent_replicas") is not False:
        raise RendererError("same-seed chains are incorrectly marked as independent replicas")
    shared_seed = comparability.get("shared_seed")
    if isinstance(shared_seed, bool) or not isinstance(shared_seed, int):
        raise RendererError("shared seed must be an integer")

    chains_raw = require_list(payload.get("chains"), "chains")
    if len(chains_raw) != 3 or not all(isinstance(chain, dict) for chain in chains_raw):
        raise RendererError("comparison must contain exactly three chain objects")
    chains = sorted(chains_raw, key=lambda chain: finite_number(chain.get("initial_density_kg_m3"), "initial density"))
    chain_ids: list[str] = []
    numeric_keys = (
        "initial_density_kg_m3",
        "last1ns_density_mean_kg_m3",
        "density_slope_percent_per_ns",
        "density_last_two_block_diff_percent",
        "density_max_adjacent_block_diff_percent",
        "density_first_vs_second_500ps_diff_percent",
        "density_1_2ns_vs_2_3ns_diff_percent",
        "min_box_over_2rlist",
    )
    for chain in chains:
        chain_id = chain.get("chain_id")
        if not isinstance(chain_id, str) or not chain_id:
            raise RendererError("every chain must have a non-empty chain_id")
        chain_ids.append(chain_id)
        for key in numeric_keys:
            finite_number(chain.get(key), f"{chain_id} {key}")
        if chain.get("exploratory_verdict") not in CHAIN_VERDICTS:
            raise RendererError(f"{chain_id}: unsupported THREE_NS verdict")
        require_list(chain.get("hard_fail_reasons"), f"{chain_id} hard-fail reasons")
        require_list(chain.get("review_reasons"), f"{chain_id} review reasons")
    if len(set(chain_ids)) != 3:
        raise RendererError("chain IDs must be unique")

    representative = payload.get("provisional_replica_design_chain")
    if representative is not None and representative not in chain_ids:
        raise RendererError("provisional representative is not one of the three chains")
    if assessment == "THREE_NS_SAME_BASIN_CANDIDATE" and representative is None:
        raise RendererError("same-basin candidate is missing a provisional representative")
    if assessment != "THREE_NS_SAME_BASIN_CANDIDATE" and representative is not None:
        raise RendererError("a provisional representative exists without same-basin status")

    not_verified = require_list(payload.get("not_verified"), "not_verified")
    if not not_verified or not all(isinstance(item, str) and item for item in not_verified):
        raise RendererError("not_verified must contain non-empty strings")
    return chains


def render_report(payload: dict[str, Any], source_name: str, source_sha256: str) -> str:
    chains = validate_payload(payload)
    representative = payload.get("provisional_replica_design_chain")
    rows: list[str] = []
    for chain in chains:
        chain_id = chain["chain_id"]
        rows.append(
            "| {chain} | {initial} | {final} | {slope} | {last_two} | {adjacent} | "
            "{cross_window} | {margin} | `{verdict}` | {reasons} | {representative} |".format(
                chain=markdown_cell(chain_id),
                initial=number(chain["initial_density_kg_m3"], 1, "initial density"),
                final=number(
                    chain["last1ns_density_mean_kg_m3"], 2, "last-1-ns density"
                ),
                slope=number(
                    chain["density_slope_percent_per_ns"], 3, "density slope"
                ),
                last_two=number(
                    chain["density_last_two_block_diff_percent"],
                    3,
                    "last-two-block difference",
                ),
                adjacent=number(
                    chain["density_max_adjacent_block_diff_percent"],
                    3,
                    "max-adjacent-block difference",
                ),
                cross_window=number(
                    chain["density_1_2ns_vs_2_3ns_diff_percent"],
                    3,
                    "cross-window difference",
                ),
                margin=number(chain["min_box_over_2rlist"], 4, "cutoff margin"),
                verdict=markdown_cell(chain["exploratory_verdict"]),
                reasons=reason_cell(
                    chain["hard_fail_reasons"], chain["review_reasons"]
                ),
                representative="예 (replica 설계용 임시 후보)"
                if chain_id == representative
                else "아니오",
            )
        )

    assessment = payload["cross_start_assessment"]
    representative_text = (
        f"`{markdown_cell(representative)}` — 독립 replica 설계용 임시 후보"
        if representative is not None
        else "없음 — 현재 비교만으로는 선정하지 않음"
    )
    comparability = payload["comparability"]
    not_verified_lines = "\n".join(
        f"- {markdown_cell(NOT_VERIFIED_KO.get(item, item))}"
        for item in payload["not_verified"]
    )
    return f"""# L1P1x2 총 3 ns 초기조건 비교 보고서

> **PROVISIONAL / EXPLORATORY ONLY**  
> 이 보고서는 2–3 ns 구간의 잠정 stationarity 및 세 시작 밀도의 민감도 비교다. 평형·독립 replica·production 조건을 검증한 결과가 아니다.

## 핵심 판정

- 교차 시작조건 판정: `{assessment}`
- 판정 의미: {ASSESSMENT_KO[assessment]}
- 2–3 ns 평균 밀도의 chain 간 spread: {number(payload['last1ns_density_spread_percent'], 3, 'density spread')}%
- 임시 대표 chain: {representative_text}
- 공통 seed: `{comparability['shared_seed']}`
- protocol 동일성: 확인됨
- 독립 replica 여부: **아님** — 세 chain은 같은 seed를 사용한 시작 밀도 민감도 비교다.

## Chain별 마지막 1 ns QC

주 분석 구간은 2–3 ns이며, block 지표는 200 ps × 5개로 계산된 값이다.

| chain | 초기 밀도 (kg/m³) | 2–3 ns 평균 밀도 (kg/m³) | 밀도 slope (%/ns) | 마지막 두 block 차이 (%) | 인접 block 최대 차이 (%) | 1–2 vs 2–3 ns 차이 (%) | min box/(2rlist) | THREE_NS 판정 | fail/review 사유 | 임시 대표 |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
{chr(10).join(rows)}

`THREE_NS_STATIONARITY_CANDIDATE`는 마지막 1 ns의 잠정 문턱을 통과했다는 뜻뿐이며, 열역학적 평형 판정이 아니다. 임시 대표 chain도 후속 독립 replica 설계를 위한 계산상 후보일 뿐 물리적으로 참인 밀도나 우수한 chain을 뜻하지 않는다.

## 검증 상태

- 입력 비교 technical status: `PASS_COMPLETE`
- 입력 비교 analysis status: `PASS_COMPLETE`
- 물리 상태: `EXPLORATORY_ONLY`
- 평형 검증: **Not verified / 미검증** (`equilibrium_validated=false`)
- production 준비 상태: **Not verified / 미검증** (`production_ready=false`)

### 추가 미검증 항목

{not_verified_lines}

## 출처

- 비교 JSON: `{markdown_cell(source_name)}`
- 비교 JSON SHA-256: `{source_sha256}`

이 Markdown은 비교 JSON을 사람이 읽기 쉽게 옮긴 파생 보고서이며 새로운 물리 판정을 추가하지 않는다.
"""


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_output_path(path: Path) -> None:
    resolved = path.resolve()
    for protected in PROTECTED_OUTPUT_ROOTS:
        if is_within(resolved, protected.resolve()):
            raise RendererError(f"refusing to write renderer output under {protected}")


def atomic_write_text(path: Path, content: str, *, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        raise RendererError(f"refusing to overwrite existing output without --force: {path}")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("comparison", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    try:
        comparison_path = args.comparison.resolve()
        output_path = args.output.resolve()
        validate_output_path(output_path)
        payload = read_json(comparison_path)
        content = render_report(payload, comparison_path.name, sha256(comparison_path))
        atomic_write_text(output_path, content, force=args.force)
    except (RendererError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"three-ns report rendering failed safely: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
