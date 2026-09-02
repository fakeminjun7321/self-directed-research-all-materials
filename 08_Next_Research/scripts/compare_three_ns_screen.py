#!/usr/bin/env python3
"""Compare three immutable exploratory 3 ns NPT extension analyses.

The comparison is intentionally limited to cross-start exploratory evidence.
The three same-seed chains are not independent replicas, and no result from
this script validates equilibrium or production readiness.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any


EXTENSION_ID = "npt_ext001"
ANALYSIS_SCHEMA = "npt-extension-analysis-v1"
COMPARISON_SCHEMA = "three-ns-screen-comparison-v1"
ALLOWED_CHAIN_VERDICTS = {
    "THREE_NS_STATIONARITY_CANDIDATE",
    "THREE_NS_EXTEND_OR_REVIEW",
    "THREE_NS_FAIL",
}
EXPECTED_INITIAL_DENSITIES = (1000.0, 1200.0, 1400.0)
INITIAL_DENSITY_TOLERANCE = 2.0
TIME_TOLERANCE_PS = 1.0e-3


class ComparisonError(RuntimeError):
    """The three chains cannot be compared without weakening provenance."""


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_evidence(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ComparisonError(f"required immutable source is missing: {path}")
    return {"sha256": sha256(path), "size_bytes": path.stat().st_size}


def reject_json_constant(value: str) -> None:
    raise ComparisonError(f"non-finite JSON constant: {value}")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(), parse_constant=reject_json_constant)
    except (OSError, json.JSONDecodeError) as exc:
        raise ComparisonError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ComparisonError(f"expected a JSON object: {path}")
    return payload


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    try:
        return (
            json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        ).encode()
    except (TypeError, ValueError) as exc:
        raise ComparisonError(f"comparison is not finite canonical JSON: {exc}") from exc


def write_json_once(path: Path, payload: dict[str, Any]) -> None:
    content = canonical_json_bytes(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise ComparisonError(f"immutable comparison differs: {path}")
        return
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != content:
                raise ComparisonError(
                    f"immutable comparison was concurrently created with different content: {path}"
                )
    finally:
        if temporary.exists():
            temporary.unlink()


def finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise ComparisonError(f"invalid numeric {label}: {value!r}")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ComparisonError(f"invalid numeric {label}: {value!r}") from exc
    if not math.isfinite(number):
        raise ComparisonError(f"non-finite {label}: {number}")
    return number


def require_close(value: Any, expected: float, label: str) -> float:
    number = finite_number(value, label)
    if not math.isclose(
        number,
        expected,
        rel_tol=0.0,
        abs_tol=TIME_TOLERANCE_PS,
    ):
        raise ComparisonError(f"{label} mismatch: {number} != {expected}")
    return number


def require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ComparisonError(f"{label} is not a JSON object")
    return value


def require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ComparisonError(f"{label} is not a JSON list")
    return value


def single_npt_mdp_hash(chain_manifest: dict[str, Any]) -> str:
    input_hashes = require_dict(chain_manifest.get("input_sha256"), "input_sha256")
    matches = [
        value
        for name, value in input_hashes.items()
        if name.startswith("npt_") and name.endswith("ps.mdp")
    ]
    if len(matches) != 1 or not isinstance(matches[0], str):
        raise ComparisonError("expected exactly one NPT MDP hash")
    return matches[0]


def nvt_mdp_hash(chain_manifest: dict[str, Any]) -> str:
    input_hashes = require_dict(chain_manifest.get("input_sha256"), "input_sha256")
    value = input_hashes.get("nvt_100ps.mdp")
    if not isinstance(value, str):
        raise ComparisonError("nvt_100ps.mdp hash is missing")
    return value


def validate_analysis_shape(
    analysis: dict[str, Any],
    manifest: dict[str, Any],
    metrics: dict[str, Any],
    chain_id: str,
) -> None:
    if analysis.get("schema_version") != ANALYSIS_SCHEMA:
        raise ComparisonError(f"{chain_id}: unsupported extension analysis schema")
    for key, expected in (
        ("extension_id", EXTENSION_ID),
        ("chain_id", chain_id),
        ("record_id", manifest.get("record_id")),
        ("parent_record_id", manifest.get("parent_record_id")),
        ("technical_status", "PASS_COMPLETE"),
        ("analysis_status", "PASS_COMPLETE"),
        ("physics_status", "EXPLORATORY_ONLY"),
    ):
        if analysis.get(key) != expected:
            raise ComparisonError(
                f"{chain_id}: extension analysis {key} mismatch: "
                f"{analysis.get(key)!r} != {expected!r}"
            )
    if analysis.get("equilibrium_validated") is not False:
        raise ComparisonError(f"{chain_id}: extension analysis claims equilibrium")
    if analysis.get("production_ready") is not False:
        raise ComparisonError(f"{chain_id}: extension analysis claims production readiness")

    window = require_dict(analysis.get("analysis_window_ps"), f"{chain_id} analysis window")
    require_close(window.get("start"), 2000.0, f"{chain_id} analysis-window start")
    require_close(window.get("end"), 3000.0, f"{chain_id} analysis-window end")
    edr_range = require_dict(analysis.get("edr_range_ps"), f"{chain_id} EDR range")
    require_close(edr_range.get("first"), 0.0, f"{chain_id} EDR first")
    require_close(edr_range.get("last"), 3000.0, f"{chain_id} EDR last")
    require_close(edr_range.get("duration"), 3000.0, f"{chain_id} EDR duration")
    block = require_dict(analysis.get("block_definition"), f"{chain_id} block definition")
    if block.get("count") != 5:
        raise ComparisonError(f"{chain_id}: expected five final-window blocks")
    require_close(block.get("width_ps"), 200.0, f"{chain_id} block width")
    require_close(block.get("window_start_ps"), 2000.0, f"{chain_id} block start")
    require_close(block.get("window_end_ps"), 3000.0, f"{chain_id} block end")
    blocks = require_list(analysis.get("blocks_200ps"), f"{chain_id} 200 ps blocks")
    if len(blocks) != 5:
        raise ComparisonError(f"{chain_id}: blocks_200ps does not contain five blocks")

    verdict = analysis.get("exploratory_verdict")
    if verdict not in ALLOWED_CHAIN_VERDICTS:
        raise ComparisonError(f"{chain_id}: invalid exploratory verdict: {verdict!r}")
    hard = require_list(analysis.get("hard_fail_reasons"), f"{chain_id} hard-fail reasons")
    review = require_list(analysis.get("review_reasons"), f"{chain_id} review reasons")
    if not all(isinstance(reason, str) and reason for reason in hard + review):
        raise ComparisonError(f"{chain_id}: QC reasons must be non-empty strings")
    if verdict == "THREE_NS_STATIONARITY_CANDIDATE" and (hard or review):
        raise ComparisonError(f"{chain_id}: stationarity candidate has fail/review reasons")
    if verdict == "THREE_NS_EXTEND_OR_REVIEW" and (hard or not review):
        raise ComparisonError(f"{chain_id}: review verdict has inconsistent reasons")
    if verdict == "THREE_NS_FAIL" and not hard:
        raise ComparisonError(f"{chain_id}: fail verdict has no hard-fail reason")

    if metrics.get("technical_status") != "PASS_COMPLETE":
        raise ComparisonError(f"{chain_id}: extension metrics are not PASS_COMPLETE")
    if metrics.get("analysis_status") != "PENDING_EXTENSION_REANALYSIS":
        raise ComparisonError(f"{chain_id}: unexpected immutable extension analysis status")


def validate_analysis_provenance(
    work: Path,
    extension_dir: Path,
    analysis: dict[str, Any],
    manifest: dict[str, Any],
    metrics: dict[str, Any],
    chain_manifest_path: Path,
    chain_id: str,
) -> dict[str, Any]:
    manifest_path = extension_dir / "extension_manifest.json"
    metrics_path = extension_dir / "extension_metrics.json"
    analysis_path = extension_dir / "extension_analysis.json"
    if metrics.get("extension_manifest_sha256") != sha256(manifest_path):
        raise ComparisonError(f"{chain_id}: metrics reference a different extension manifest")
    if manifest.get("chain_manifest_sha256") != sha256(chain_manifest_path):
        raise ComparisonError(f"{chain_id}: extension manifest references a different chain manifest")

    tpr_name = manifest.get("extended_tpr_path")
    if not isinstance(tpr_name, str) or not tpr_name or Path(tpr_name).name != tpr_name:
        raise ComparisonError(f"{chain_id}: unsafe extended_tpr_path: {tpr_name!r}")
    tpr_path = extension_dir / tpr_name
    actual_sources = {
        "extension_manifest.json": file_evidence(manifest_path),
        "extension_metrics.json": file_evidence(metrics_path),
        "npt.edr": file_evidence(work / "npt.edr"),
        tpr_name: file_evidence(tpr_path),
    }
    recorded_sources = require_dict(
        analysis.get("source_evidence"), f"{chain_id} analysis source evidence"
    )
    if recorded_sources != actual_sources:
        raise ComparisonError(f"{chain_id}: analysis source hash/provenance mismatch")

    post_extension = require_dict(
        metrics.get("post_extension_sha256"), f"{chain_id} post-extension evidence"
    )
    for name in ("npt.edr", tpr_name):
        if post_extension.get(name) != actual_sources[name]:
            raise ComparisonError(f"{chain_id}: extension output evidence mismatch for {name}")
    if manifest.get("extended_tpr_sha256") != actual_sources[tpr_name]["sha256"]:
        raise ComparisonError(f"{chain_id}: extended TPR hash mismatch")

    return {
        "chain_manifest.json": file_evidence(chain_manifest_path),
        "extension_manifest.json": actual_sources["extension_manifest.json"],
        "extension_metrics.json": actual_sources["extension_metrics.json"],
        "extension_analysis.json": file_evidence(analysis_path),
        "npt.edr": actual_sources["npt.edr"],
        tpr_name: actual_sources[tpr_name],
    }


def load_chain(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    work = run_dir / "equilibration"
    extension_dir = work / "extensions" / EXTENSION_ID
    chain_manifest_path = work / "chain_manifest.json"
    manifest_path = extension_dir / "extension_manifest.json"
    metrics_path = extension_dir / "extension_metrics.json"
    analysis_path = extension_dir / "extension_analysis.json"

    chain_manifest = read_json(chain_manifest_path)
    manifest = read_json(manifest_path)
    metrics = read_json(metrics_path)
    analysis = read_json(analysis_path)
    run_metrics_path = run_dir / "metrics.json"
    run_metrics = read_json(run_metrics_path)
    chain_id = run_dir.name

    for payload_name, payload in (
        ("extension manifest", manifest),
        ("extension metrics", metrics),
        ("extension analysis", analysis),
    ):
        if payload.get("extension_id") != EXTENSION_ID:
            raise ComparisonError(f"{chain_id}: {payload_name} extension_id mismatch")
        if payload.get("chain_id") != chain_id:
            raise ComparisonError(f"{chain_id}: {payload_name} chain_id mismatch")
    if metrics.get("record_id") != manifest.get("record_id"):
        raise ComparisonError(f"{chain_id}: extension record_id mismatch")
    if metrics.get("parent_record_id") != manifest.get("parent_record_id"):
        raise ComparisonError(f"{chain_id}: extension parent_record_id mismatch")
    validate_analysis_shape(analysis, manifest, metrics, chain_id)
    source_evidence = validate_analysis_provenance(
        work,
        extension_dir,
        analysis,
        manifest,
        metrics,
        chain_manifest_path,
        chain_id,
    )

    last_1ns = require_dict(analysis.get("last_1ns"), f"{chain_id} last_1ns")
    density_stats = require_dict(last_1ns.get("Density"), f"{chain_id} density stats")
    density_qc = require_dict(analysis.get("density_qc"), f"{chain_id} density QC")
    temperature_qc = require_dict(
        analysis.get("temperature_qc"), f"{chain_id} temperature QC"
    )
    volume_qc = require_dict(analysis.get("volume_qc"), f"{chain_id} volume QC")
    box_qc = require_dict(analysis.get("box_qc"), f"{chain_id} box QC")
    metric_values = {
        "last1ns_density_mean_kg_m3": finite_number(
            density_stats.get("mean"), f"{chain_id} final density mean"
        ),
        "density_slope_percent_per_ns": finite_number(
            density_qc.get("slope_percent_per_ns"), f"{chain_id} density slope"
        ),
        "density_last_two_block_diff_percent": finite_number(
            density_qc.get("last_two_block_diff_percent"),
            f"{chain_id} last-two density difference",
        ),
        "density_max_adjacent_block_diff_percent": finite_number(
            density_qc.get("max_adjacent_block_diff_percent"),
            f"{chain_id} adjacent density difference",
        ),
        "density_first_vs_second_500ps_diff_percent": finite_number(
            density_qc.get("first_vs_second_500ps_diff_percent"),
            f"{chain_id} half-window density difference",
        ),
        "density_1_2ns_vs_2_3ns_diff_percent": finite_number(
            density_qc.get("one_to_two_vs_two_to_three_ns_diff_percent"),
            f"{chain_id} cross-window density difference",
        ),
        "temperature_mean_K": finite_number(
            temperature_qc.get("mean_K"), f"{chain_id} temperature mean"
        ),
        "temperature_slope_K_per_ns": finite_number(
            temperature_qc.get("slope_K_per_ns"), f"{chain_id} temperature slope"
        ),
        "max_adjacent_volume_jump_percent": finite_number(
            volume_qc.get("max_adjacent_frame_jump_percent_0_3ns"),
            f"{chain_id} volume jump",
        ),
        "min_box_over_2rlist": finite_number(
            box_qc.get("min_box_over_2rlist"), f"{chain_id} box margin"
        ),
    }
    if metric_values["last1ns_density_mean_kg_m3"] <= 0:
        raise ComparisonError(f"{chain_id}: final density mean must be positive")
    for key in (
        "density_slope_percent_per_ns",
        "density_last_two_block_diff_percent",
        "density_max_adjacent_block_diff_percent",
        "density_first_vs_second_500ps_diff_percent",
        "density_1_2ns_vs_2_3ns_diff_percent",
        "max_adjacent_volume_jump_percent",
    ):
        if metric_values[key] < 0:
            raise ComparisonError(f"{chain_id}: {key} must be non-negative")
    if metric_values["min_box_over_2rlist"] <= 0:
        raise ComparisonError(f"{chain_id}: box margin must be positive")

    initial_density = finite_number(
        run_metrics.get("initial_density_kg_m3"), f"{chain_id} initial density"
    )
    hard_reasons = require_list(
        analysis.get("hard_fail_reasons"), f"{chain_id} hard-fail reasons"
    )
    review_reasons = require_list(
        analysis.get("review_reasons"), f"{chain_id} review reasons"
    )
    expected_hard: list[str] = []
    if metric_values["min_box_over_2rlist"] <= 1.0:
        expected_hard.append("minimum_image_cutoff_violation")
    if not 293.0 <= metric_values["temperature_mean_K"] <= 303.0:
        expected_hard.append("temperature_mean_outside_293_303_K")
    if metric_values["max_adjacent_volume_jump_percent"] > 5.0:
        expected_hard.append("adjacent_volume_jump_above_5_percent")
    expected_review: list[str] = []
    if 1.0 < metric_values["min_box_over_2rlist"] < 1.10:
        expected_review.append("cutoff_margin_below_1_10_time_extension_prohibited")
    if abs(metric_values["temperature_slope_K_per_ns"]) > 1.0:
        expected_review.append("temperature_slope_above_1_K_per_ns")
    if metric_values["density_slope_percent_per_ns"] > 0.5:
        expected_review.append("density_slope_above_0_5_percent_per_ns")
    if metric_values["density_last_two_block_diff_percent"] > 0.5:
        expected_review.append("density_last_two_block_diff_above_0_5_percent")
    if metric_values["density_max_adjacent_block_diff_percent"] > 1.0:
        expected_review.append("density_adjacent_block_diff_above_1_percent")
    if metric_values["density_first_vs_second_500ps_diff_percent"] > 1.0:
        expected_review.append("density_first_vs_second_500ps_diff_above_1_percent")
    if metric_values["density_1_2ns_vs_2_3ns_diff_percent"] > 2.0:
        expected_review.append("density_1_2ns_vs_2_3ns_diff_above_2_percent")
    if hard_reasons != expected_hard or review_reasons != expected_review:
        raise ComparisonError(
            f"{chain_id}: THREE_NS reasons do not match the recorded stationarity indicators"
        )
    expected_verdict = (
        "THREE_NS_FAIL"
        if expected_hard
        else "THREE_NS_EXTEND_OR_REVIEW"
        if expected_review
        else "THREE_NS_STATIONARITY_CANDIDATE"
    )
    if analysis["exploratory_verdict"] != expected_verdict:
        raise ComparisonError(
            f"{chain_id}: THREE_NS verdict does not match the stationarity indicators"
        )
    source_evidence["metrics.json"] = file_evidence(run_metrics_path)
    return {
        "run_dir": str(run_dir),
        "chain_id": chain_id,
        "initial_density_kg_m3": initial_density,
        **metric_values,
        "exploratory_verdict": analysis["exploratory_verdict"],
        "hard_fail_reasons": hard_reasons,
        "review_reasons": review_reasons,
        "chain_manifest": chain_manifest,
        "extension_manifest": manifest,
        "source_evidence": source_evidence,
    }


def comparable_protocol(record: dict[str, Any]) -> dict[str, Any]:
    chain = record["chain_manifest"]
    extension = record["extension_manifest"]
    input_hashes = require_dict(chain.get("input_sha256"), "input_sha256")
    return {
        "base_protocol_version": chain.get("protocol_version"),
        "seed": chain.get("seed"),
        "base_npt_ps": chain.get("npt_ps"),
        "base_npt_steps": chain.get("npt_steps"),
        "dt_ps": chain.get("dt_ps"),
        "parent_topology_sha256": chain.get("parent_topology_sha256"),
        "topology_input_sha256": input_hashes.get("topol.top"),
        "nvt_mdp_sha256": nvt_mdp_hash(chain),
        "npt_mdp_sha256": single_npt_mdp_hash(chain),
        "gromacs_version": chain.get("gromacs_version"),
        "extension_schema_version": extension.get("schema_version"),
        "extension_stage": extension.get("stage"),
        "extension_segment_no": extension.get("segment_no"),
        "extension_mode": extension.get("mode"),
        "extension_start_step": extension.get("start_step"),
        "extension_steps": extension.get("extension_steps"),
        "target_total_steps": extension.get("target_total_steps"),
        "extension_dt_ps": extension.get("dt_ps"),
        "base_duration_ps": extension.get("base_duration_ps"),
        "extension_duration_ps": extension.get("extension_duration_ps"),
        "target_total_duration_ps": extension.get("target_total_duration_ps"),
        "extension_gromacs_version": extension.get("gromacs_version"),
        "base_tpr_shape": extension.get("base_tpr_shape"),
        "extended_tpr_shape": extension.get("extended_tpr_shape"),
    }


def ensure_comparable(records: list[dict[str, Any]]) -> dict[str, Any]:
    if len(records) != 3:
        raise ComparisonError(f"expected exactly three chains, got {len(records)}")
    chain_ids = [record["chain_id"] for record in records]
    if len(set(chain_ids)) != 3:
        raise ComparisonError(f"chain IDs are not unique: {chain_ids}")
    actual_densities = sorted(record["initial_density_kg_m3"] for record in records)
    if any(
        abs(actual - expected) > INITIAL_DENSITY_TOLERANCE
        for actual, expected in zip(actual_densities, EXPECTED_INITIAL_DENSITIES)
    ):
        raise ComparisonError(
            f"expected initial densities near {EXPECTED_INITIAL_DENSITIES}, got {actual_densities}"
        )
    if len({round(value, 6) for value in actual_densities}) != 3:
        raise ComparisonError("initial densities are not unique")

    protocols = [comparable_protocol(record) for record in records]
    reference = protocols[0]
    mismatches: dict[str, list[Any]] = {}
    for key in reference:
        values = [protocol[key] for protocol in protocols]
        canonical_values = {
            json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
            for value in values
        }
        if len(canonical_values) != 1:
            mismatches[key] = values
    if mismatches:
        raise ComparisonError(f"chains are not directly comparable: {mismatches}")
    if reference["seed"] is None:
        raise ComparisonError("shared velocity seed is missing")
    if reference["base_protocol_version"] is None:
        raise ComparisonError("base protocol version is missing")
    expected_protocol = {
        "base_npt_ps": 1000.0,
        "base_npt_steps": 1_000_000,
        "dt_ps": 0.001,
        "extension_schema_version": "npt-extension-v1",
        "extension_stage": "npt",
        "extension_segment_no": 2,
        "extension_mode": "EXTEND",
        "extension_start_step": 1_000_000,
        "extension_steps": 2_000_000,
        "target_total_steps": 3_000_000,
        "extension_dt_ps": 0.001,
        "base_duration_ps": 1000.0,
        "extension_duration_ps": 2000.0,
        "target_total_duration_ps": 3000.0,
    }
    for key, expected in expected_protocol.items():
        if reference[key] != expected:
            raise ComparisonError(
                f"unsupported three-ns protocol value for {key}: "
                f"{reference[key]!r} != {expected!r}"
            )
    for key in (
        "base_protocol_version",
        "parent_topology_sha256",
        "topology_input_sha256",
        "nvt_mdp_sha256",
        "npt_mdp_sha256",
        "gromacs_version",
        "extension_gromacs_version",
    ):
        if not isinstance(reference[key], str) or not reference[key]:
            raise ComparisonError(f"required protocol field is missing: {key}")
    if reference["parent_topology_sha256"] != reference["topology_input_sha256"]:
        raise ComparisonError("parent topology hash differs from topol.top input hash")
    if reference["gromacs_version"] != reference["extension_gromacs_version"]:
        raise ComparisonError("base and extension GROMACS versions differ")
    if isinstance(reference["seed"], bool) or not isinstance(reference["seed"], int):
        raise ComparisonError(f"shared seed is not an integer: {reference['seed']!r}")
    if not isinstance(reference["base_tpr_shape"], dict) or not isinstance(
        reference["extended_tpr_shape"], dict
    ):
        raise ComparisonError("base/extended TPR shapes are missing")
    return reference


def symmetric_spread_percent(values: list[float]) -> float:
    average = sum(values) / len(values)
    if average <= 0:
        raise ComparisonError("cannot calculate density spread from a non-positive mean")
    return (max(values) - min(values)) / average * 100.0


def compare_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    protocol = ensure_comparable(records)
    densities = [record["last1ns_density_mean_kg_m3"] for record in records]
    spread = symmetric_spread_percent(densities)
    any_hard_fail = any(record["hard_fail_reasons"] for record in records)
    all_stationarity = all(
        record["exploratory_verdict"] == "THREE_NS_STATIONARITY_CANDIDATE"
        for record in records
    )
    if any_hard_fail:
        assessment = "THREE_NS_CROSS_START_INCOMPLETE"
    elif spread > 5.0:
        assessment = "THREE_NS_NOT_CONVERGED"
    elif all_stationarity and spread <= 2.0:
        assessment = "THREE_NS_SAME_BASIN_CANDIDATE"
    else:
        assessment = "THREE_NS_INITIAL_CONDITION_DEPENDENCE_OR_INCOMPLETE"

    representative: str | None = None
    if assessment == "THREE_NS_SAME_BASIN_CANDIDATE":
        representative = min(
            records,
            key=lambda record: (
                abs(record["density_slope_percent_per_ns"]),
                record["density_last_two_block_diff_percent"],
                record["density_max_adjacent_block_diff_percent"],
                -record["min_box_over_2rlist"],
                abs(record["initial_density_kg_m3"] - 1200.0),
                record["chain_id"],
            ),
        )["chain_id"]

    protocol_bytes = json.dumps(
        protocol,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode()
    public_records = [
        {key: value for key, value in record.items() if key not in {"chain_manifest", "extension_manifest", "source_evidence"}}
        for record in records
    ]
    return {
        "schema_version": COMPARISON_SCHEMA,
        "technical_status": "PASS_COMPLETE",
        "analysis_status": "PASS_COMPLETE",
        "chains": public_records,
        "comparison_source_evidence": {
            record["chain_id"]: record["source_evidence"] for record in records
        },
        "comparability": {
            "same_protocol": True,
            "same_seed": True,
            "shared_seed": protocol["seed"],
            "same_seed_chains_are_independent_replicas": False,
            "protocol_fingerprint_sha256": hashlib.sha256(protocol_bytes).hexdigest(),
            "protocol_fields": protocol,
        },
        "last1ns_density_spread_percent": spread,
        "cross_start_assessment": assessment,
        "provisional_replica_design_chain": representative,
        "physics_status": "EXPLORATORY_ONLY",
        "equilibrium_validated": False,
        "production_ready": False,
        "not_verified": [
            "thermodynamic equilibrium",
            "independent Packmol and velocity-seed replicas",
            "production readiness",
            "structural and transport-property convergence",
            "laboratory-server reproduction",
        ],
    }


def compare_runs(run_dirs: list[Path]) -> dict[str, Any]:
    records = [load_chain(run_dir) for run_dir in run_dirs]
    records.sort(key=lambda record: record["initial_density_kg_m3"])
    return compare_records(records)


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_existing_output(existing: dict[str, Any], current: dict[str, Any]) -> None:
    if existing.get("schema_version") != COMPARISON_SCHEMA:
        raise ComparisonError("existing comparison schema is invalid")
    if existing.get("comparison_source_evidence") != current["comparison_source_evidence"]:
        raise ComparisonError("existing comparison references changed immutable inputs")
    if existing.get("comparability") != current["comparability"]:
        raise ComparisonError("existing comparison protocol fingerprint differs")
    if existing.get("cross_start_assessment") != current["cross_start_assessment"]:
        raise ComparisonError("existing comparison assessment differs from current inputs")
    if existing.get("equilibrium_validated") is not False:
        raise ComparisonError("existing comparison claims equilibrium")
    if existing.get("production_ready") is not False:
        raise ComparisonError("existing comparison claims production readiness")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dirs", nargs=3, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    try:
        run_dirs = [path.resolve() for path in args.run_dirs]
        output = args.output.resolve()
        if any(is_within(output, run_dir) for run_dir in run_dirs):
            raise ComparisonError("comparison output must not modify a run directory")
        current = compare_runs(run_dirs)
        if output.exists():
            existing = read_json(output)
            validate_existing_output(existing, current)
            print(json.dumps(existing, indent=2, ensure_ascii=False, allow_nan=False))
            return
        current["generated_at"] = now()
        # Reassert these claims immediately before the immutable write.
        current["equilibrium_validated"] = False
        current["production_ready"] = False
        write_json_once(output, current)
        print(json.dumps(current, indent=2, ensure_ascii=False, allow_nan=False))
    except (ComparisonError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"three-ns comparison failed safely: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
