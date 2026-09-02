#!/usr/bin/env python3
"""Analyze the immutable cumulative 0--3 ns NPT extension artifact.

This is a deliberately separate post-processing step for ``npt_ext001``.  It
does not alter the original 1 ns record, the cumulative NPT artifacts, or any
registry.  Each GROMACS energy term is extracted independently so column
identity never depends on the interactive menu order.

The resulting verdict is an exploratory stationarity screen only.  It never
validates equilibrium or production readiness.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from typing import Any


EXTENSION_ID = "npt_ext001"
SCHEMA_VERSION = "npt-extension-analysis-v1"
TARGET_START_PS = 0.0
TARGET_END_PS = 3000.0
TARGET_DURATION_PS = 3000.0
TIME_TOLERANCE_PS = 1.0e-3
TIME_AXIS_TOLERANCE_PS = 1.0e-7
FINAL_WINDOW_START_PS = 2000.0
COMPARISON_WINDOW_START_PS = 1000.0
BLOCK_WIDTH_PS = 200.0
BLOCK_COUNT = 5
ENERGY_TERMS = (
    "Temperature",
    "Pressure",
    "Potential",
    "Density",
    "Volume",
    "Box-X",
    "Box-Y",
    "Box-Z",
)


class AnalysisError(RuntimeError):
    """Analysis cannot continue without weakening provenance or QC."""


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
        raise AnalysisError(f"required file is missing: {path}")
    return {"sha256": sha256(path), "size_bytes": path.stat().st_size}


def reject_json_constant(value: str) -> None:
    raise AnalysisError(f"non-finite JSON constant: {value}")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(), parse_constant=reject_json_constant)
    except (OSError, json.JSONDecodeError) as exc:
        raise AnalysisError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AnalysisError(f"expected a JSON object: {path}")
    return value


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    try:
        text = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    except (TypeError, ValueError) as exc:
        raise AnalysisError(f"analysis is not finite canonical JSON: {exc}") from exc
    return text.encode()


def write_json_once(path: Path, value: dict[str, Any]) -> None:
    """Atomically create ``path`` without ever replacing existing bytes."""
    content = canonical_json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise AnalysisError(f"immutable analysis differs: {path}")
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
                raise AnalysisError(
                    f"immutable analysis was concurrently created with different content: {path}"
                )
    finally:
        if temporary.exists():
            temporary.unlink()


def gromacs_identity(gmx_bin: str, cwd: Path) -> tuple[str, str]:
    resolved = shutil.which(gmx_bin)
    if resolved is None:
        raise AnalysisError(f"GROMACS executable not found: {gmx_bin}")
    result = subprocess.run(
        [resolved, "--version"],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=True,
    )
    version = next(
        (line.strip() for line in result.stdout.splitlines() if "GROMACS version:" in line),
        None,
    )
    if version is None:
        raise AnalysisError("GROMACS version line not found")
    return str(Path(resolved).resolve()), version


def parse_tpr_number(dump: str, key: str) -> float:
    match = re.search(
        rf"^\s*{re.escape(key)}\s*=\s*([-+0-9.eE]+)\s*$",
        dump,
        re.MULTILINE,
    )
    if match is None:
        raise AnalysisError(f"{key} not found in TPR dump")
    value = float(match.group(1))
    if not math.isfinite(value):
        raise AnalysisError(f"non-finite {key} in TPR dump")
    return value


def dump_tpr(gmx_bin: str, tpr: Path, cwd: Path) -> str:
    result = subprocess.run(
        [gmx_bin, "dump", "-s", str(tpr)],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=True,
    )
    return result.stdout


def run_energy_term(
    gmx_bin: str,
    edr: Path,
    term: str,
    output: Path,
    cwd: Path,
) -> None:
    env = os.environ.copy()
    env["GMX_MAXBACKUP"] = "-1"
    subprocess.run(
        [
            gmx_bin,
            "energy",
            "-f",
            str(edr),
            "-o",
            str(output),
            "-xvg",
            "none",
            "-b",
            format(TARGET_START_PS, ".12g"),
            "-e",
            format(TARGET_END_PS, ".12g"),
        ],
        cwd=cwd,
        input=f"{term}\n0\n",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=True,
        env=env,
    )


def parse_xvg(path: Path, term: str) -> list[tuple[float, float]]:
    values: list[tuple[float, float]] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "@")):
            continue
        fields = stripped.split()
        if len(fields) != 2:
            raise AnalysisError(
                f"unexpected {term} column count at {path}:{line_number}; expected 2"
            )
        try:
            time_ps, value = (float(field) for field in fields)
        except ValueError as exc:
            raise AnalysisError(f"non-numeric {term} row at {path}:{line_number}") from exc
        if not (math.isfinite(time_ps) and math.isfinite(value)):
            raise AnalysisError(f"non-finite {term} row at {path}:{line_number}")
        values.append((time_ps, value))
    if not values:
        raise AnalysisError(f"no energy rows extracted for {term}")
    times = [time_ps for time_ps, _ in values]
    if any(current <= previous for previous, current in zip(times, times[1:])):
        raise AnalysisError(f"non-increasing energy times for {term}")
    return values


def extract_energy(gmx_bin: str, edr: Path, cwd: Path) -> list[dict[str, float]]:
    """Extract each named term independently and verify a common time axis."""
    series: dict[str, list[tuple[float, float]]] = {}
    with tempfile.TemporaryDirectory(prefix="npt-extension-analysis-", dir=cwd) as temporary:
        scratch = Path(temporary)
        for term in ENERGY_TERMS:
            output = scratch / f"{term.lower().replace('-', '_')}.xvg"
            run_energy_term(gmx_bin, edr, term, output, cwd)
            series[term] = parse_xvg(output, term)

    reference_times = [time_ps for time_ps, _ in series[ENERGY_TERMS[0]]]
    rows: list[dict[str, float]] = []
    for term in ENERGY_TERMS:
        if len(series[term]) != len(reference_times):
            raise AnalysisError(
                f"energy row-count mismatch for {term}: "
                f"{len(series[term])} != {len(reference_times)}"
            )
    for index, time_ps in enumerate(reference_times):
        row = {"time_ps": time_ps}
        for term in ENERGY_TERMS:
            term_time, value = series[term][index]
            if not math.isclose(
                term_time,
                time_ps,
                rel_tol=0.0,
                abs_tol=TIME_AXIS_TOLERANCE_PS,
            ):
                raise AnalysisError(
                    f"energy time mismatch for {term}: {term_time} != {time_ps} ps"
                )
            row[term] = value
        rows.append(row)
    validate_rows(rows)
    return rows


def validate_rows(rows: list[dict[str, float]]) -> None:
    if len(rows) < 2:
        raise AnalysisError("fewer than two cumulative NPT energy rows")
    expected = {"time_ps", *ENERGY_TERMS}
    for index, row in enumerate(rows):
        if set(row) != expected:
            raise AnalysisError(f"energy row {index} has unexpected columns")
        if not all(math.isfinite(float(value)) for value in row.values()):
            raise AnalysisError(f"energy row {index} has a non-finite value")
        for key in ("Density", "Volume", "Box-X", "Box-Y", "Box-Z"):
            if row[key] <= 0:
                raise AnalysisError(f"energy row {index} has non-positive {key}")
    times = [float(row["time_ps"]) for row in rows]
    if any(current <= previous for previous, current in zip(times, times[1:])):
        raise AnalysisError("cumulative NPT energy times are not strictly increasing")
    if not math.isclose(
        times[0], TARGET_START_PS, rel_tol=0.0, abs_tol=TIME_TOLERANCE_PS
    ):
        raise AnalysisError(f"cumulative NPT extraction does not start at 0 ps: {times[0]}")
    if not math.isclose(
        times[-1], TARGET_END_PS, rel_tol=0.0, abs_tol=TIME_TOLERANCE_PS
    ):
        raise AnalysisError(f"cumulative NPT extraction does not end at 3000 ps: {times[-1]}")


def mean(values: list[float]) -> float:
    if not values:
        raise AnalysisError("cannot calculate a mean from an empty series")
    return sum(values) / len(values)


def slope_per_ns(rows: list[dict[str, float]], key: str) -> float:
    if len(rows) < 2:
        raise AnalysisError(f"insufficient rows for {key} slope")
    x = [row["time_ps"] for row in rows]
    y = [row[key] for row in rows]
    xbar = mean(x)
    ybar = mean(y)
    denominator = sum((value - xbar) ** 2 for value in x)
    if denominator == 0:
        raise AnalysisError(f"zero time variance for {key} slope")
    per_ps = sum((a - xbar) * (b - ybar) for a, b in zip(x, y)) / denominator
    return per_ps * 1000.0


def symmetric_percent_difference(a: float, b: float) -> float:
    denominator = (abs(a) + abs(b)) / 2.0
    return abs(a - b) / denominator * 100.0 if denominator else 0.0


def stats(rows: list[dict[str, float]], key: str) -> dict[str, Any]:
    values = [row[key] for row in rows]
    return {
        "n": len(values),
        "mean": mean(values),
        "std": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
        "slope_per_ns": slope_per_ns(rows, key),
    }


def interval(
    rows: list[dict[str, float]],
    start_ps: float,
    end_ps: float,
    *,
    include_end: bool,
) -> list[dict[str, float]]:
    selected = [
        row
        for row in rows
        if row["time_ps"] >= start_ps - TIME_AXIS_TOLERANCE_PS
        and (
            row["time_ps"] <= end_ps + TIME_AXIS_TOLERANCE_PS
            if include_end
            else row["time_ps"] < end_ps - TIME_AXIS_TOLERANCE_PS
        )
    ]
    if len(selected) < 2:
        raise AnalysisError(f"insufficient energy rows in {start_ps}--{end_ps} ps")
    return selected


def final_blocks(rows: list[dict[str, float]]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for index in range(BLOCK_COUNT):
        start_ps = FINAL_WINDOW_START_PS + index * BLOCK_WIDTH_PS
        end_ps = start_ps + BLOCK_WIDTH_PS
        block_rows = interval(
            rows,
            start_ps,
            end_ps,
            include_end=index == BLOCK_COUNT - 1,
        )
        blocks.append(
            {
                "index": index + 1,
                "start_ps": start_ps,
                "end_ps": end_ps,
                "n": len(block_rows),
                "Density_mean": mean([row["Density"] for row in block_rows]),
                "Volume_mean": mean([row["Volume"] for row in block_rows]),
                "Temperature_mean": mean([row["Temperature"] for row in block_rows]),
                "Pressure_mean": mean([row["Pressure"] for row in block_rows]),
                "Potential_mean": mean([row["Potential"] for row in block_rows]),
            }
        )
    return blocks


def max_relative_adjacent_jump(rows: list[dict[str, float]], key: str) -> float:
    jumps: list[float] = []
    for previous, current in zip(rows, rows[1:]):
        base = abs(previous[key])
        if base == 0:
            if current[key] != 0:
                return math.inf
            continue
        jumps.append(abs(current[key] - previous[key]) / base * 100.0)
    return max(jumps, default=0.0)


def analyze_rows(rows: list[dict[str, float]], rlist_nm: float) -> dict[str, Any]:
    validate_rows(rows)
    if not math.isfinite(rlist_nm) or rlist_nm <= 0:
        raise AnalysisError(f"invalid rlist: {rlist_nm}")

    one_to_two = interval(
        rows,
        COMPARISON_WINDOW_START_PS,
        FINAL_WINDOW_START_PS,
        include_end=False,
    )
    final = interval(rows, FINAL_WINDOW_START_PS, TARGET_END_PS, include_end=True)
    first_half = interval(rows, FINAL_WINDOW_START_PS, 2500.0, include_end=False)
    second_half = interval(rows, 2500.0, TARGET_END_PS, include_end=True)
    blocks = final_blocks(rows)
    density_blocks = [float(block["Density_mean"]) for block in blocks]
    density_block_rows = [
        {
            "time_ps": FINAL_WINDOW_START_PS + (index + 0.5) * BLOCK_WIDTH_PS,
            "Density": density,
        }
        for index, density in enumerate(density_blocks)
    ]

    final_density_mean = mean([row["Density"] for row in final])
    density_slope = slope_per_ns(density_block_rows, "Density")
    density_slope_percent = (
        abs(density_slope) / abs(final_density_mean) * 100.0
        if final_density_mean
        else math.inf
    )
    last_two_diff = symmetric_percent_difference(density_blocks[-2], density_blocks[-1])
    max_adjacent_diff = max(
        symmetric_percent_difference(a, b)
        for a, b in zip(density_blocks, density_blocks[1:])
    )
    half_diff = symmetric_percent_difference(
        mean([row["Density"] for row in first_half]),
        mean([row["Density"] for row in second_half]),
    )
    cross_window_diff = symmetric_percent_difference(
        mean([row["Density"] for row in one_to_two]),
        final_density_mean,
    )

    min_box_nm = min(
        min(row["Box-X"], row["Box-Y"], row["Box-Z"]) for row in rows
    )
    min_box_over_2rlist = min_box_nm / (2.0 * rlist_nm)
    max_volume_jump = max_relative_adjacent_jump(rows, "Volume")
    temperature = stats(final, "Temperature")

    hard_fail_reasons: list[str] = []
    if min_box_over_2rlist <= 1.0:
        hard_fail_reasons.append("minimum_image_cutoff_violation")
    if not 293.0 <= float(temperature["mean"]) <= 303.0:
        hard_fail_reasons.append("temperature_mean_outside_293_303_K")
    if max_volume_jump > 5.0:
        hard_fail_reasons.append("adjacent_volume_jump_above_5_percent")

    review_reasons: list[str] = []
    if 1.0 < min_box_over_2rlist < 1.10:
        review_reasons.append("cutoff_margin_below_1_10_time_extension_prohibited")
    if abs(float(temperature["slope_per_ns"])) > 1.0:
        review_reasons.append("temperature_slope_above_1_K_per_ns")
    if density_slope_percent > 0.5:
        review_reasons.append("density_slope_above_0_5_percent_per_ns")
    if last_two_diff > 0.5:
        review_reasons.append("density_last_two_block_diff_above_0_5_percent")
    if max_adjacent_diff > 1.0:
        review_reasons.append("density_adjacent_block_diff_above_1_percent")
    if half_diff > 1.0:
        review_reasons.append("density_first_vs_second_500ps_diff_above_1_percent")
    if cross_window_diff > 2.0:
        review_reasons.append("density_1_2ns_vs_2_3ns_diff_above_2_percent")

    if hard_fail_reasons:
        verdict = "THREE_NS_FAIL"
    elif review_reasons:
        verdict = "THREE_NS_EXTEND_OR_REVIEW"
    else:
        verdict = "THREE_NS_STATIONARITY_CANDIDATE"

    return {
        "edr_range_ps": {
            "first": rows[0]["time_ps"],
            "last": rows[-1]["time_ps"],
            "duration": rows[-1]["time_ps"] - rows[0]["time_ps"],
            "rows": len(rows),
        },
        "analysis_window_ps": {"start": 2000.0, "end": 3000.0},
        "comparison_windows_ps": {
            "earlier": {"start": 1000.0, "end_exclusive": 2000.0},
            "final": {"start": 2000.0, "end_inclusive": 3000.0},
        },
        "block_definition": {
            "count": BLOCK_COUNT,
            "width_ps": BLOCK_WIDTH_PS,
            "window_start_ps": FINAL_WINDOW_START_PS,
            "window_end_ps": TARGET_END_PS,
        },
        "last_1ns": {
            term: stats(final, term)
            for term in ("Temperature", "Pressure", "Potential", "Density", "Volume")
        },
        "blocks_200ps": blocks,
        "density_qc": {
            "slope_percent_per_ns": density_slope_percent,
            "slope_kg_m3_per_ns": density_slope,
            "last_two_block_diff_percent": last_two_diff,
            "max_adjacent_block_diff_percent": max_adjacent_diff,
            "first_vs_second_500ps_diff_percent": half_diff,
            "one_to_two_ns_mean_kg_m3": mean([row["Density"] for row in one_to_two]),
            "two_to_three_ns_mean_kg_m3": final_density_mean,
            "one_to_two_vs_two_to_three_ns_diff_percent": cross_window_diff,
        },
        "temperature_qc": {
            "mean_K": temperature["mean"],
            "slope_K_per_ns": temperature["slope_per_ns"],
        },
        "volume_qc": {
            "max_adjacent_frame_jump_percent_0_3ns": max_volume_jump,
            "last_1ns": stats(final, "Volume"),
        },
        "box_qc": {
            "rlist_nm": rlist_nm,
            "min_box_nm_0_3ns": min_box_nm,
            "min_box_over_2rlist": min_box_over_2rlist,
            "time_extension_allowed_by_margin": min_box_over_2rlist >= 1.10,
        },
        "thresholds": {
            "min_box_over_2rlist_candidate_min": 1.10,
            "min_box_over_2rlist_hard_fail_max": 1.0,
            "temperature_mean_K_inclusive": [293.0, 303.0],
            "temperature_abs_slope_K_per_ns_max": 1.0,
            "density_abs_slope_percent_per_ns_max": 0.5,
            "density_last_two_block_diff_percent_max": 0.5,
            "density_max_adjacent_block_diff_percent_max": 1.0,
            "density_first_vs_second_500ps_diff_percent_max": 1.0,
            "density_1_2ns_vs_2_3ns_diff_percent_max": 2.0,
            "max_adjacent_volume_jump_percent_max": 5.0,
        },
        "hard_fail_reasons": hard_fail_reasons,
        "review_reasons": review_reasons,
        "exploratory_verdict": verdict,
        "physics_status": "EXPLORATORY_ONLY",
        "equilibrium_validated": False,
        "production_ready": False,
    }


def require_close(actual: Any, expected: float, label: str) -> float:
    try:
        value = float(actual)
    except (TypeError, ValueError) as exc:
        raise AnalysisError(f"invalid {label}: {actual!r}") from exc
    if not math.isfinite(value) or not math.isclose(
        value, expected, rel_tol=0.0, abs_tol=TIME_TOLERANCE_PS
    ):
        raise AnalysisError(f"{label} mismatch: {value} != {expected}")
    return value


def validate_extension_inputs(
    work: Path,
    extension_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any], Path, dict[str, Any]]:
    manifest_path = extension_dir / "extension_manifest.json"
    metrics_path = extension_dir / "extension_metrics.json"
    manifest = read_json(manifest_path)
    metrics = read_json(metrics_path)
    if manifest.get("extension_id") != EXTENSION_ID:
        raise AnalysisError("extension manifest has the wrong extension_id")
    if metrics.get("extension_id") != EXTENSION_ID:
        raise AnalysisError("extension metrics have the wrong extension_id")
    if metrics.get("technical_status") != "PASS_COMPLETE":
        raise AnalysisError("extension technical_status is not PASS_COMPLETE")
    if metrics.get("analysis_status") != "PENDING_EXTENSION_REANALYSIS":
        raise AnalysisError("extension is not pending the required reanalysis")
    if metrics.get("extension_manifest_sha256") != sha256(manifest_path):
        raise AnalysisError("extension metrics reference a different manifest")
    if metrics.get("chain_id") != manifest.get("chain_id"):
        raise AnalysisError("extension chain_id differs between manifest and metrics")
    if metrics.get("record_id") != manifest.get("record_id"):
        raise AnalysisError("extension record_id differs between manifest and metrics")
    if metrics.get("parent_record_id") != manifest.get("parent_record_id"):
        raise AnalysisError("extension parent_record_id differs between manifest and metrics")

    edr_range = metrics.get("edr_range_ps")
    if not isinstance(edr_range, dict):
        raise AnalysisError("extension EDR range is missing")
    require_close(edr_range.get("first"), TARGET_START_PS, "EDR first time")
    require_close(edr_range.get("last"), TARGET_END_PS, "EDR last time")
    require_close(edr_range.get("duration"), TARGET_DURATION_PS, "EDR duration")
    require_close(
        manifest.get("target_total_duration_ps"),
        TARGET_DURATION_PS,
        "manifest target duration",
    )

    tpr_name = manifest.get("extended_tpr_path")
    if not isinstance(tpr_name, str) or not tpr_name or Path(tpr_name).name != tpr_name:
        raise AnalysisError(f"unsafe extended_tpr_path: {tpr_name!r}")
    tpr_path = extension_dir / tpr_name
    edr_path = work / "npt.edr"
    current_outputs = {
        "npt.edr": file_evidence(edr_path),
        tpr_name: file_evidence(tpr_path),
    }
    recorded_outputs = metrics.get("post_extension_sha256")
    if not isinstance(recorded_outputs, dict):
        raise AnalysisError("post-extension output evidence is missing")
    for name, evidence in current_outputs.items():
        if recorded_outputs.get(name) != evidence:
            raise AnalysisError(f"post-extension artifact changed: {name}")
    if manifest.get("extended_tpr_sha256") != current_outputs[tpr_name]["sha256"]:
        raise AnalysisError("extended TPR differs from the immutable manifest")

    evidence = {
        "extension_manifest.json": file_evidence(manifest_path),
        "extension_metrics.json": file_evidence(metrics_path),
        "npt.edr": current_outputs["npt.edr"],
        tpr_name: current_outputs[tpr_name],
    }
    return manifest, metrics, tpr_path, evidence


def validate_existing_analysis(
    analysis: dict[str, Any],
    manifest: dict[str, Any],
    source_evidence: dict[str, Any],
) -> None:
    if analysis.get("schema_version") != SCHEMA_VERSION:
        raise AnalysisError("existing analysis schema_version is invalid")
    if analysis.get("extension_id") != EXTENSION_ID:
        raise AnalysisError("existing analysis extension_id is invalid")
    if analysis.get("chain_id") != manifest.get("chain_id"):
        raise AnalysisError("existing analysis chain_id is invalid")
    if analysis.get("record_id") != manifest.get("record_id"):
        raise AnalysisError("existing analysis record_id is invalid")
    if analysis.get("parent_record_id") != manifest.get("parent_record_id"):
        raise AnalysisError("existing analysis parent_record_id is invalid")
    if analysis.get("technical_status") != "PASS_COMPLETE":
        raise AnalysisError("existing analysis technical_status is invalid")
    if analysis.get("analysis_status") != "PASS_COMPLETE":
        raise AnalysisError("existing analysis analysis_status is invalid")
    if analysis.get("source_evidence") != source_evidence:
        raise AnalysisError("existing immutable analysis references changed inputs")
    if analysis.get("equilibrium_validated") is not False:
        raise AnalysisError("existing analysis makes an equilibrium claim")
    if analysis.get("production_ready") is not False:
        raise AnalysisError("existing analysis makes a production-readiness claim")
    verdict = analysis.get("exploratory_verdict")
    if verdict not in {
        "THREE_NS_STATIONARITY_CANDIDATE",
        "THREE_NS_EXTEND_OR_REVIEW",
        "THREE_NS_FAIL",
    }:
        raise AnalysisError(f"existing analysis verdict is invalid: {verdict!r}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--gmx-bin", default="gmx")
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    work = run_dir / "equilibration"
    extension_dir = work / "extensions" / EXTENSION_ID
    if not extension_dir.is_dir():
        raise SystemExit(f"completed extension directory is missing: {extension_dir}")

    lock_path = work / ".chain.lock"
    try:
        with lock_path.open("a+") as lock_handle:
            try:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise AnalysisError(f"another process holds the chain lock: {work}") from exc

            manifest, metrics, tpr_path, source_evidence = validate_extension_inputs(
                work, extension_dir
            )
            output_path = extension_dir / "extension_analysis.json"
            if output_path.exists():
                existing = read_json(output_path)
                validate_existing_analysis(existing, manifest, source_evidence)
                print(json.dumps(existing, indent=2, ensure_ascii=False, allow_nan=False))
                return

            gmx_bin, gmx_version = gromacs_identity(args.gmx_bin, work)
            if gmx_version != manifest.get("gromacs_version"):
                raise AnalysisError(
                    "analysis GROMACS version differs from the extension manifest: "
                    f"{gmx_version!r} != {manifest.get('gromacs_version')!r}"
                )
            tpr_dump = dump_tpr(gmx_bin, tpr_path, work)
            rlist_nm = parse_tpr_number(tpr_dump, "rlist")
            rows = extract_energy(gmx_bin, work / "npt.edr", extension_dir)
            calculated = analyze_rows(rows, rlist_nm)
            analysis = {
                "schema_version": SCHEMA_VERSION,
                "extension_id": EXTENSION_ID,
                "chain_id": manifest["chain_id"],
                "record_id": manifest["record_id"],
                "parent_record_id": manifest["parent_record_id"],
                "generated_at": now(),
                "technical_status": "PASS_COMPLETE",
                "analysis_status": "PASS_COMPLETE",
                "source_evidence": source_evidence,
                "gromacs": {"executable": gmx_bin, "version": gmx_version},
                "extraction": {
                    "source": "equilibration/npt.edr",
                    "method": "one_named_energy_term_per_gmx_energy_call",
                    "terms": list(ENERGY_TERMS),
                    "requested_range_ps": [TARGET_START_PS, TARGET_END_PS],
                },
                **calculated,
                "not_verified": [
                    "thermodynamic equilibrium",
                    "independent Packmol and velocity-seed replicas",
                    "production readiness",
                    "structural and transport-property convergence",
                    "cross-start same-basin convergence",
                    "laboratory-server reproduction",
                ],
            }
            # Reassert the two non-negotiable claims immediately before the
            # immutable write, even if the analysis payload is later refactored.
            analysis["equilibrium_validated"] = False
            analysis["production_ready"] = False
            write_json_once(output_path, analysis)
            print(json.dumps(analysis, indent=2, ensure_ascii=False, allow_nan=False))
    except (
        AnalysisError,
        subprocess.CalledProcessError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"extension analysis failed safely: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
