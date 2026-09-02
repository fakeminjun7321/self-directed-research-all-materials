#!/usr/bin/env python3
"""Fail-closed comparison of three independent 1 ns replica screens."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import sys
from typing import Any


PROJECT = Path(__file__).resolve().parents[2]
NEXT = PROJECT / "08_Next_Research"
RULES_PATH = NEXT / "02_Protocol" / "REPLICA_1NS_COMPARISON_RULES.md"
EXPECTED_RULES_SHA256 = (
    "c9d3608be93162bb0eea9ef03b061c3734a09d8c3758c4b0559d164724eec627"
)
SCHEMA = "replica-1ns-comparison-v1"
INPUT_AUDIT_PATH = NEXT / "05_QC" / "replica_input_audit_v3.json"
EXPECTED_INPUT_AUDIT_SHA256 = (
    "72b18746ffb250dedc26b15864d4780b4420fca6efbd75da8910c55c9c469a5b"
)
MASS_U = 24771.4
DALTON_KG = 1.66053906660e-27
EXPECTED_COMPOSITION = {"Li+": 50, "c3c1pyrr+": 50, "fsi-": 100}
PLAN = {
    240101: {"replica_id": "R1", "velocity_seed": 110101},
    240102: {"replica_id": "R2", "velocity_seed": 110102},
    240103: {"replica_id": "R3", "velocity_seed": 110103},
}
EXPECTED_THREADS = 6
SHA256_RE = re.compile(r"[0-9a-f]{64}")
NVT_SEED_RE = re.compile(
    r"^(\s*gen[-_]seed\s*=\s*)([+-]?\d+)(\s*(?:;.*)?)$",
    re.MULTILINE | re.IGNORECASE,
)


class ComparisonError(RuntimeError):
    """Input evidence is malformed or cannot support the requested comparison."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def file_evidence(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ComparisonError(f"required evidence is missing: {path}")
    return {"sha256": sha256(path), "size_bytes": path.stat().st_size}


def rules_evidence() -> dict[str, Any]:
    evidence = file_evidence(RULES_PATH)
    if evidence["sha256"] != EXPECTED_RULES_SHA256:
        raise ComparisonError(
            "pre-registered comparison rules SHA-256 differs from the fixed value"
        )
    return {
        "path": "08_Next_Research/02_Protocol/REPLICA_1NS_COMPARISON_RULES.md",
        **evidence,
    }


def input_audit() -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    evidence = file_evidence(INPUT_AUDIT_PATH)
    if evidence["sha256"] != EXPECTED_INPUT_AUDIT_SHA256:
        raise ComparisonError("replica input audit SHA-256 differs from the fixed value")
    payload = read_json(INPUT_AUDIT_PATH)
    expected_header = {
        "schema_version": "replica-input-audit-v3",
        "technical_status": "PASS_PACKMOL_ARTIFACTS",
        "md_execution_status": "NOT_EXECUTED",
        "physics_status": "NOT_EVALUATED",
        "replica_count": 3,
        "packmol_seeds_unique": True,
        "initial_coordinate_hashes_unique": True,
        "direct_packmol_output_hashes_unique": True,
        "topology_hashes_identical": True,
        "em_mdp_hashes_identical": True,
    }
    for key, expected in expected_header.items():
        if payload.get(key) != expected:
            raise ComparisonError(f"replica input audit header differs for {key}")
    chains = payload.get("chains")
    if not isinstance(chains, list) or len(chains) != 3:
        raise ComparisonError("replica input audit must contain exactly three chains")
    by_seed: dict[int, dict[str, Any]] = {}
    for chain in chains:
        if not isinstance(chain, dict):
            raise ComparisonError("replica input audit chain must be an object")
        seed = integer(chain.get("packmol_seed"), "audited Packmol seed")
        if seed in by_seed:
            raise ComparisonError("replica input audit contains a duplicate seed")
        if chain.get("atom_count") != 2300:
            raise ComparisonError("replica input audit atom count differs")
        require_close(
            chain.get("requested_density_kg_m3"), 1400.0, "audited requested density"
        )
        checks = require_dict(
            chain.get("scientific_input_checks"), "audited scientific input checks"
        )
        if not checks or any(value is not True for value in checks.values()):
            raise ComparisonError("replica input audit scientific checks did not all pass")
        initial = require_dict(chain.get("initial_gro"), "audited initial GRO evidence")
        require_sha(initial.get("sha256"), "audited initial GRO hash")
        if integer(initial.get("size_bytes"), "audited initial GRO size") <= 0:
            raise ComparisonError("audited initial GRO size must be positive")
        finite(chain.get("initial_density_kg_m3"), "audited initial density")
        by_seed[seed] = chain
    if set(by_seed) != set(PLAN):
        raise ComparisonError("replica input audit seed set differs from the fixed plan")
    return by_seed, {
        "path": "08_Next_Research/05_QC/replica_input_audit_v3.json",
        **evidence,
    }


def reject_json_constant(value: str) -> None:
    raise ComparisonError(f"non-finite JSON constant: {value}")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(), parse_constant=reject_json_constant)
    except (OSError, json.JSONDecodeError) as exc:
        raise ComparisonError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ComparisonError(f"expected JSON object: {path}")
    return value


def finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ComparisonError(f"{label} must be a JSON number")
    number = float(value)
    if not math.isfinite(number):
        raise ComparisonError(f"{label} must be finite")
    return number


def integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ComparisonError(f"{label} must be an integer")
    return value


def require_close(value: Any, expected: float, label: str) -> float:
    number = finite(value, label)
    if not math.isclose(number, expected, rel_tol=0.0, abs_tol=1.0e-9):
        raise ComparisonError(f"{label} is {number}, expected {expected}")
    return number


def require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ComparisonError(f"{label} is not a SHA-256 digest")
    return value


def require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ComparisonError(f"{label} must be an object")
    return value


def initial_density_from_gro(path: Path) -> float:
    lines = path.read_text().splitlines()
    if not lines:
        raise ComparisonError(f"initial GRO is empty: {path}")
    try:
        box = [float(value) for value in lines[-1].split()]
    except ValueError as exc:
        raise ComparisonError(f"initial GRO box is invalid: {path}") from exc
    if len(box) != 3 or not all(math.isfinite(value) and value > 0 for value in box):
        raise ComparisonError(f"initial GRO must have three positive box lengths: {path}")
    volume_m3 = box[0] * box[1] * box[2] * 1.0e-27
    return MASS_U * DALTON_KG / volume_m3


def topology_composition(path: Path) -> dict[str, int]:
    in_molecules = False
    counts: dict[str, int] = {}
    for raw in path.read_text().splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        section = re.fullmatch(r"\[\s*([^]]+)\s*\]", line)
        if section:
            in_molecules = section.group(1).strip().lower() == "molecules"
            continue
        if not in_molecules:
            continue
        fields = line.split()
        if len(fields) != 2:
            raise ComparisonError(f"malformed [ molecules ] row in {path}: {raw}")
        name, raw_count = fields
        try:
            count = int(raw_count)
        except ValueError as exc:
            raise ComparisonError(f"invalid molecule count in {path}: {raw}") from exc
        if name in counts or count <= 0:
            raise ComparisonError(f"duplicate/non-positive molecule row in {path}: {raw}")
        counts[name] = count
    if counts != EXPECTED_COMPOSITION:
        raise ComparisonError(f"L1P1x2 composition differs in {path}: {counts}")
    return counts


def resolve_work_file(work: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ComparisonError(f"{label} must be a non-empty relative path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ComparisonError(f"{label} is not a safe relative path")
    resolved = (work / relative).resolve()
    try:
        resolved.relative_to(work.resolve())
    except ValueError as exc:
        raise ComparisonError(f"{label} escapes the equilibration directory") from exc
    return resolved


def parse_packmol_seed(path: Path, observed: bool) -> int:
    text = path.read_text(errors="strict")
    pattern = (
        r"Seed for random number generator:\s*([+-]?\d+)"
        if observed
        else r"^\s*seed\s+([+-]?\d+)\s*$"
    )
    flags = 0 if observed else re.MULTILINE | re.IGNORECASE
    matches = re.findall(pattern, text, flags)
    if len(matches) != 1:
        raise ComparisonError(f"expected exactly one Packmol seed in {path}")
    return int(matches[0])


def normalized_nvt_mdp(path: Path) -> tuple[int, dict[str, Any]]:
    text = path.read_text()
    matches = list(NVT_SEED_RE.finditer(text))
    if len(matches) != 1:
        raise ComparisonError(f"expected exactly one gen-seed assignment in {path}")
    seed = int(matches[0].group(2))
    normalized = NVT_SEED_RE.sub("gen-seed = <NORMALIZED>", text)
    encoded = normalized.encode()
    return seed, {
        "sha256": sha256_bytes(encoded),
        "size_bytes": len(encoded),
        "normalization": "exact file with the single gen-seed assignment replaced",
    }


def manifest_velocity_seed(
    manifest: dict[str, Any], chain_id: str
) -> tuple[int, str]:
    """Resolve explicit or narrowly allowed legacy manifest seed evidence."""
    has_velocity = "velocity_seed" in manifest
    has_semantics = "seed_semantics" in manifest
    if has_velocity != has_semantics:
        raise ComparisonError(
            f"{chain_id}: partially populated manifest velocity-seed evidence"
        )
    alias = integer(manifest.get("seed"), f"{chain_id} manifest seed")
    if not has_velocity:
        return alias, "LEGACY_MANIFEST_SEED_FALLBACK"
    velocity = integer(
        manifest.get("velocity_seed"), f"{chain_id} manifest velocity seed"
    )
    if manifest.get("seed_semantics") != "gromacs_nvt_gen_seed":
        raise ComparisonError(f"{chain_id}: manifest seed semantics differ")
    if alias != velocity:
        raise ComparisonError(f"{chain_id}: manifest seed alias differs")
    return velocity, "EXPLICIT_MANIFEST_VELOCITY_SEED"


def verify_parent_provenance(
    run_dir: Path,
    parent_metrics: dict[str, Any],
    manifest: dict[str, Any],
    eq_metrics: dict[str, Any],
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    requested = integer(
        parent_metrics.get("packmol_seed_requested"),
        f"{run_dir.name} requested Packmol seed",
    )
    observed = integer(
        parent_metrics.get("packmol_seed_observed"),
        f"{run_dir.name} observed Packmol seed",
    )
    if requested != observed:
        raise ComparisonError(f"{run_dir.name}: requested/observed Packmol seeds differ")

    pack_input = run_dir / "input" / "pack.inp"
    pack_log = run_dir / "commands.log"
    initial = run_dir / "input" / "initial.gro"
    if parse_packmol_seed(pack_input, False) != requested:
        raise ComparisonError(f"{run_dir.name}: pack.inp seed differs from metrics")
    if parse_packmol_seed(pack_log, True) != requested:
        raise ComparisonError(f"{run_dir.name}: Packmol log seed differs from metrics")
    expected = {
        "packmol_seed": requested,
        "packmol_input_sha256": sha256(pack_input),
        "packmol_log_sha256": sha256(pack_log),
        "packmol_initial_gro_sha256": sha256(initial),
    }
    if manifest.get("parent_packmol_provenance") != expected:
        raise ComparisonError(
            f"{run_dir.name}: chain manifest parent Packmol provenance differs"
        )
    metrics_provenance = eq_metrics.get("parent_packmol_provenance")
    if eq_metrics.get("technical_status") == "PASS_COMPLETE":
        if metrics_provenance != expected:
            raise ComparisonError(
                f"{run_dir.name}: equilibration metrics parent Packmol provenance differs"
            )
    elif metrics_provenance is not None and metrics_provenance != expected:
        raise ComparisonError(
            f"{run_dir.name}: failed metrics carry contradictory Packmol provenance"
        )
    return requested, expected, {
        "pack.inp": file_evidence(pack_input),
        "commands.log": file_evidence(pack_log),
        "input/initial.gro": file_evidence(initial),
    }


def verify_mdrun_threads(path: Path, stage: str, expected_threads: int) -> None:
    text = path.read_text(errors="replace")
    commands = re.findall(r"^.*\$\s+gmx\s+mdrun\b[^\n]*$", text, re.MULTILINE)
    if not commands:
        raise ComparisonError(f"{stage}: no logged gmx mdrun command in {path}")
    observed: list[int] = []
    for command in commands:
        matches = re.findall(r"(?:^|\s)-ntomp\s+(\d+)(?:\s|$)", command)
        if len(matches) != 1:
            raise ComparisonError(f"{stage}: ambiguous -ntomp evidence in {path}")
        observed.append(int(matches[0]))
    if any(value != expected_threads for value in observed):
        raise ComparisonError(f"{stage}: logged OpenMP threads differ from request")


def parse_energy_range(text: str, label: str) -> tuple[float, float]:
    first = re.search(
        r"frame:\s*0\s+\(index\s+0\),\s*t:\s*([-+0-9.eE]+)", text
    )
    if first is None:
        first = re.search(r"Reading energy frame\s+0\s+time\s+([-+0-9.eE]+)", text)
    last = re.search(r"Last energy frame read\s+\d+\s+time\s+([-+0-9.eE]+)", text)
    if first is None or last is None:
        raise ComparisonError(f"{label}: energy time range is missing")
    values = (float(first.group(1)), float(last.group(1)))
    if not all(math.isfinite(value) for value in values):
        raise ComparisonError(f"{label}: energy time range is non-finite")
    return values


def verify_attempt_snapshot(
    work: Path,
    metrics_path: Path,
    metrics: dict[str, Any],
    attempt_path: Path,
    attempt: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    chain_id = str(metrics.get("chain_id"))
    number = integer(attempt.get("attempt"), f"{chain_id} attempt number")
    tag = f"attempt_{number:03d}"
    expected_started = work / "attempts" / f"{tag}_started.json"
    if attempt_path != expected_started.resolve():
        raise ComparisonError(f"{chain_id}: attempt started path is not canonical")
    snapshot = work / "attempts" / f"{tag}_metrics.json"
    final_path = work / "attempts" / f"{tag}_final.json"
    final = read_json(final_path)
    snapshot_evidence = file_evidence(snapshot)
    if metrics_path.read_bytes() != snapshot.read_bytes():
        raise ComparisonError(f"{chain_id}: central metrics differ from immutable snapshot")
    if final.get("schema_version") != "eq-attempt-v1":
        raise ComparisonError(f"{chain_id}: attempt final schema differs")
    if final.get("attempt") != number or final.get("chain_id") != chain_id:
        raise ComparisonError(f"{chain_id}: attempt final identity differs")
    if final.get("technical_status") != metrics.get("technical_status"):
        raise ComparisonError(f"{chain_id}: attempt final technical status differs")
    if final.get("physics_status") != metrics.get("physics_status"):
        raise ComparisonError(f"{chain_id}: attempt final physics status differs")
    if final.get("ended_at") != metrics.get("end"):
        raise ComparisonError(f"{chain_id}: attempt final end time differs")
    expected_snapshot = f"attempts/{tag}_metrics.json"
    if final.get("metrics_snapshot") != expected_snapshot:
        raise ComparisonError(f"{chain_id}: attempt final snapshot path differs")
    if final.get("metrics_evidence") != snapshot_evidence:
        raise ComparisonError(f"{chain_id}: attempt final snapshot evidence differs")
    return {
        "equilibration/attempt_started.json": file_evidence(attempt_path),
        "equilibration/attempt_metrics_snapshot.json": snapshot_evidence,
        "equilibration/attempt_final.json": file_evidence(final_path),
    }


def verify_stage_artifacts(
    work: Path,
    stage: str,
    target_ps: float,
    stage_metrics: dict[str, Any],
    threads: int,
) -> dict[str, dict[str, Any]]:
    label = f"{work.parent.name}:{stage}"
    native_log = work / f"{stage}.log"
    console_log = work / f"{stage}_mdrun_console.log"
    native_text = native_log.read_text(errors="replace")
    console_text = console_log.read_text(errors="replace")
    verify_mdrun_threads(console_log, label, threads)
    if "Finished mdrun" not in native_text:
        raise ComparisonError(f"{label}: native log lacks Finished mdrun")
    thread_matches = re.findall(r"Using\s+(\d+)\s+OpenMP threads", native_text)
    if not thread_matches or any(int(value) != threads for value in thread_matches):
        raise ComparisonError(f"{label}: native OpenMP thread evidence differs")
    combined = native_text + "\n" + console_text
    forbidden = {
        "fatal": len(re.findall(r"fatal error", combined, re.IGNORECASE)),
        "nan": len(re.findall(r"\bnan\b", combined, re.IGNORECASE)),
        "lincs": len(re.findall(r"lincs warning", combined, re.IGNORECASE)),
        "segfault": len(re.findall(r"segmentation fault", combined, re.IGNORECASE)),
    }
    if any(forbidden.values()):
        raise ComparisonError(f"{label}: native logs contain forbidden markers {forbidden}")

    check_path = work / f"{stage}_edr_check.txt"
    first, last = parse_energy_range(check_path.read_text(errors="replace"), label)
    expected_first = 0.0
    if not math.isclose(first, expected_first, rel_tol=0.0, abs_tol=1.0e-6):
        raise ComparisonError(f"{label}: EDR first time is not 0 ps")
    if not math.isclose(last, target_ps, rel_tol=0.0, abs_tol=1.0e-6):
        raise ComparisonError(f"{label}: EDR last time differs from target")
    recorded_first = finite(stage_metrics.get("first_time_ps"), f"{label} first time")
    recorded_last = finite(stage_metrics.get("last_time_ps"), f"{label} last time")
    recorded_duration = finite(stage_metrics.get("duration_ps"), f"{label} duration")
    if not (
        math.isclose(recorded_first, first, rel_tol=0.0, abs_tol=1.0e-6)
        and math.isclose(recorded_last, last, rel_tol=0.0, abs_tol=1.0e-6)
        and math.isclose(recorded_duration, last - first, rel_tol=0.0, abs_tol=1.0e-6)
    ):
        raise ComparisonError(f"{label}: metrics/EDR time range differs")

    artifacts: dict[str, dict[str, Any]] = {}
    for suffix in ("edr", "log", "tpr", "cpt", "xtc", "gro"):
        path = work / f"{stage}.{suffix}"
        artifacts[f"equilibration/{stage}.{suffix}"] = file_evidence(path)
    artifacts[f"equilibration/{stage}_edr_check.txt"] = file_evidence(check_path)
    artifacts[f"equilibration/{stage}_mdrun_console.log"] = file_evidence(console_log)
    return artifacts


def validate_analysis(chain_id: str, analysis: dict[str, Any]) -> dict[str, Any]:
    if analysis.get("equilibrium_validated") is not False:
        raise ComparisonError(f"{chain_id}: analysis claims equilibrium validation")
    if analysis.get("production_ready") is not False:
        raise ComparisonError(f"{chain_id}: analysis claims production readiness")
    if analysis.get("physics_status") != "EXPLORATORY_ONLY":
        raise ComparisonError(f"{chain_id}: unexpected analysis physics status")

    nvt_stats = require_dict(
        require_dict(analysis.get("nvt_last_50ps"), f"{chain_id} NVT stats").get(
            "Temperature"
        ),
        f"{chain_id} NVT temperature stats",
    )
    npt_stats = require_dict(
        analysis.get("npt_last_500ps"), f"{chain_id} NPT tail stats"
    )
    density_stats = require_dict(
        npt_stats.get("Density"), f"{chain_id} density stats"
    )
    npt_temp_stats = require_dict(
        npt_stats.get("Temperature"), f"{chain_id} NPT temperature stats"
    )

    density = finite(density_stats.get("mean"), f"{chain_id} last-500-ps density")
    if density <= 0:
        raise ComparisonError(f"{chain_id}: density mean must be positive")
    values = {
        "density_slope_percent_per_ns": finite(
            analysis.get("density_slope_percent_per_ns"),
            f"{chain_id} density slope",
        ),
        "density_last_two_block_diff_percent": finite(
            analysis.get("density_last_two_block_diff_percent"),
            f"{chain_id} density last-two-block difference",
        ),
        "density_max_adjacent_block_diff_percent": finite(
            analysis.get("density_max_adjacent_block_diff_percent"),
            f"{chain_id} density adjacent-block difference",
        ),
        "nvt_temperature_slope_K_per_ns": finite(
            nvt_stats.get("slope_per_ns"), f"{chain_id} NVT temperature slope"
        ),
        "nvt_last_two_temperature_block_diff_K": finite(
            require_dict(
                analysis.get("nvt_last_50ps"), f"{chain_id} NVT stats"
            ).get("last_two_temperature_block_diff_K"),
            f"{chain_id} NVT last-two-block temperature difference",
        ),
        "npt_temperature_slope_K_per_ns": finite(
            npt_temp_stats.get("slope_per_ns"), f"{chain_id} NPT temperature slope"
        ),
        "nvt_min_box_over_2rlist": finite(
            analysis.get("nvt_min_box_over_2rlist"), f"{chain_id} NVT cutoff margin"
        ),
        "npt_min_box_over_2rlist": finite(
            analysis.get("npt_min_box_over_2rlist"), f"{chain_id} NPT cutoff margin"
        ),
        "max_adjacent_volume_jump_percent": finite(
            analysis.get("max_adjacent_volume_jump_percent"),
            f"{chain_id} maximum adjacent volume jump",
        ),
        "nvt_temperature_mean_K": finite(
            nvt_stats.get("mean"), f"{chain_id} NVT temperature mean"
        ),
        "npt_temperature_mean_K": finite(
            npt_temp_stats.get("mean"), f"{chain_id} NPT temperature mean"
        ),
    }
    nonnegative = (
        "density_slope_percent_per_ns",
        "density_last_two_block_diff_percent",
        "density_max_adjacent_block_diff_percent",
        "nvt_last_two_temperature_block_diff_K",
        "nvt_min_box_over_2rlist",
        "npt_min_box_over_2rlist",
        "max_adjacent_volume_jump_percent",
    )
    if any(values[key] < 0 for key in nonnegative):
        raise ComparisonError(f"{chain_id}: a non-negative QC metric is negative")

    expected_hard: list[str] = []
    if (
        values["nvt_min_box_over_2rlist"] <= 1.0
        or values["npt_min_box_over_2rlist"] <= 1.0
    ):
        expected_hard.append("minimum_image_cutoff_violation")
    if not 293.0 <= values["nvt_temperature_mean_K"] <= 303.0:
        expected_hard.append("nvt_temperature_mean_outside_293_303_K")
    if not 293.0 <= values["npt_temperature_mean_K"] <= 303.0:
        expected_hard.append("npt_temperature_mean_outside_293_303_K")
    if values["max_adjacent_volume_jump_percent"] > 5.0:
        expected_hard.append("adjacent_volume_jump_above_5_percent")
    actual_hard = analysis.get("hard_fail_reasons")
    if actual_hard != expected_hard:
        raise ComparisonError(f"{chain_id}: hard-fail reasons do not match fixed rules")

    stationarity = (
        not expected_hard
        and values["nvt_min_box_over_2rlist"] >= 1.10
        and values["npt_min_box_over_2rlist"] >= 1.10
        and values["density_slope_percent_per_ns"] <= 1.0
        and values["density_last_two_block_diff_percent"] <= 1.0
        and values["density_max_adjacent_block_diff_percent"] <= 2.0
        and abs(values["nvt_temperature_slope_K_per_ns"]) <= 2.0
        and values["nvt_last_two_temperature_block_diff_K"] <= 3.0
        and abs(values["npt_temperature_slope_K_per_ns"]) <= 2.0
    )
    expected_verdict = (
        "SCREEN_FAIL"
        if expected_hard
        else ("SCREEN_STATIONARITY_PASS" if stationarity else "SCREEN_EXTEND")
    )
    if analysis.get("exploratory_verdict") != expected_verdict:
        raise ComparisonError(f"{chain_id}: SCREEN verdict differs from fixed rules")
    return {
        "last500_density_mean_kg_m3": density,
        "exploratory_verdict": expected_verdict,
        "hard_fail_reasons": expected_hard,
        **values,
    }


def load_chain(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    work = run_dir / "equilibration"
    parent_metrics_path = run_dir / "metrics.json"
    validation_path = run_dir / "validation.json"
    metrics_path = work / "equilibration_metrics.json"
    manifest_path = work / "chain_manifest.json"
    input_hash_path = work / "INPUT_SHA256.json"
    parent_metrics = read_json(parent_metrics_path)
    validation = read_json(validation_path)
    metrics = read_json(metrics_path)
    manifest = read_json(manifest_path)
    recorded_hashes = read_json(input_hash_path)

    if metrics.get("chain_id") != run_dir.name:
        raise ComparisonError(f"{run_dir.name}: equilibration metrics chain_id mismatch")
    if parent_metrics.get("run_id") != run_dir.name:
        raise ComparisonError(f"{run_dir.name}: parent run_id mismatch")
    if validation.get("all_passed") is not True:
        raise ComparisonError(f"{run_dir.name}: parent validation did not pass")
    if parent_metrics.get("technical_status") != "PASS_EM_TECHNICAL":
        raise ComparisonError(f"{run_dir.name}: parent EM technical gate did not pass")
    if parent_metrics.get("grompp_warning_count") != 0:
        raise ComparisonError(f"{run_dir.name}: parent EM grompp warnings are nonzero")
    em_summary = require_dict(
        parent_metrics.get("em_summary"), f"{run_dir.name} parent EM summary"
    )
    if em_summary.get("converged") is not True:
        raise ComparisonError(f"{run_dir.name}: parent EM did not converge")
    if parent_metrics.get("atom_count") != 2300:
        raise ComparisonError(f"{run_dir.name}: atom count is not 2300")
    require_close(
        parent_metrics.get("charge_scaling_retained"),
        0.75,
        f"{run_dir.name} charge scale",
    )
    requested_density = finite(
        parent_metrics.get("requested_density_kg_m3"),
        f"{run_dir.name} requested density",
    )
    if requested_density <= 0:
        raise ComparisonError(f"{run_dir.name}: requested density must be positive")
    canonical_topology_sha256 = require_sha(
        parent_metrics.get("canonical_topology_sha256"),
        f"{run_dir.name} canonical topology hash",
    )
    charge_sums = require_dict(
        parent_metrics.get("molecule_charge_sums"),
        f"{run_dir.name} molecule charge sums",
    )
    for molecule, expected_charge in {
        "Li+": 0.75,
        "c3c1pyrr+": 0.75,
        "fsi-": -0.75,
    }.items():
        require_close(
            charge_sums.get(molecule),
            expected_charge,
            f"{run_dir.name} {molecule} charge",
        )

    technical_status = metrics.get("technical_status")
    if technical_status not in {"PASS_COMPLETE", "FAILED"}:
        raise ComparisonError(f"{run_dir.name}: unrecognized terminal technical status")
    packmol_seed, parent_packmol_provenance, packmol_evidence = verify_parent_provenance(
        run_dir, parent_metrics, manifest, metrics
    )
    velocity_seed, manifest_seed_mode = manifest_velocity_seed(
        manifest, run_dir.name
    )
    if technical_status == "PASS_COMPLETE":
        if integer(
            metrics.get("velocity_seed"), f"{run_dir.name} metrics velocity seed"
        ) != velocity_seed:
            raise ComparisonError(f"{run_dir.name}: metrics velocity seed differs")
        if metrics.get("seed_semantics") != "gromacs_nvt_gen_seed":
            raise ComparisonError(f"{run_dir.name}: metrics seed semantics differ")
        if integer(metrics.get("seed"), f"{run_dir.name} metrics seed") != velocity_seed:
            raise ComparisonError(f"{run_dir.name}: metrics seed alias differs")
        require_close(
            metrics.get("npt_target_ps"),
            1000.0,
            f"{run_dir.name} metrics NPT target",
        )
    else:
        optional_seed_fields = {
            "seed": velocity_seed,
            "velocity_seed": velocity_seed,
            "seed_semantics": "gromacs_nvt_gen_seed",
            "npt_target_ps": 1000.0,
        }
        for key, expected in optional_seed_fields.items():
            if key in metrics and metrics[key] != expected:
                raise ComparisonError(
                    f"{run_dir.name}: failed metrics carry contradictory {key}"
                )

    nvt_mdp = work / "nvt_100ps.mdp"
    npt_mdp = work / "npt_1000ps.mdp"
    mdp_seed, normalized_nvt = normalized_nvt_mdp(nvt_mdp)
    if mdp_seed != velocity_seed:
        raise ComparisonError(f"{run_dir.name}: NVT MDP gen-seed differs")
    require_close(manifest.get("npt_ps"), 1000.0, f"{run_dir.name} NPT ps")
    if integer(manifest.get("npt_steps"), f"{run_dir.name} NPT steps") != 1_000_000:
        raise ComparisonError(f"{run_dir.name}: NPT step count differs")
    require_close(manifest.get("dt_ps"), 0.001, f"{run_dir.name} dt")
    if manifest.get("protocol_version") != "eq-screen-v2":
        raise ComparisonError(f"{run_dir.name}: equilibration protocol version differs")

    input_hashes = require_dict(manifest.get("input_sha256"), f"{run_dir.name} input hashes")
    expected_input_hashes = {
        "start_em.gro": sha256(work / "start_em.gro"),
        "topol.top": sha256(work / "topol.top"),
        "nvt_100ps.mdp": sha256(nvt_mdp),
        "npt_1000ps.mdp": sha256(npt_mdp),
    }
    if input_hashes != expected_input_hashes or recorded_hashes != expected_input_hashes:
        raise ComparisonError(f"{run_dir.name}: immutable equilibration input hashes differ")
    if metrics.get("input_sha256") != expected_input_hashes:
        if technical_status == "PASS_COMPLETE" or metrics.get("input_sha256") is not None:
            raise ComparisonError(f"{run_dir.name}: metrics input hashes differ")

    initial = run_dir / "input" / "initial.gro"
    em_gro = run_dir / "em.gro"
    nvt_gro = work / "nvt.gro"
    topology = run_dir / "input" / "topol.top"
    reported_initial_density = finite(
        parent_metrics.get("initial_density_kg_m3"),
        f"{run_dir.name} reported initial density",
    )
    calculated_initial_density = initial_density_from_gro(initial)
    if not math.isclose(
        reported_initial_density,
        calculated_initial_density,
        rel_tol=0.0,
        abs_tol=1.0e-6,
    ):
        raise ComparisonError(f"{run_dir.name}: reported/calculated initial density differs")
    composition = topology_composition(topology)
    if sha256(work / "start_em.gro") != sha256(em_gro):
        raise ComparisonError(f"{run_dir.name}: copied EM coordinates differ")
    if require_sha(
        manifest.get("parent_em_sha256"), f"{run_dir.name} parent EM hash"
    ) != sha256(em_gro):
        raise ComparisonError(f"{run_dir.name}: parent EM hash differs")
    topology_hash = sha256(topology)
    if sha256(work / "topol.top") != topology_hash:
        raise ComparisonError(f"{run_dir.name}: copied topology differs")
    if require_sha(
        manifest.get("parent_topology_sha256"), f"{run_dir.name} parent topology hash"
    ) != topology_hash:
        raise ComparisonError(f"{run_dir.name}: parent topology hash differs")

    attempt_path = resolve_work_file(
        work, metrics.get("attempt_started_record"), f"{run_dir.name} attempt record"
    )
    attempt = read_json(attempt_path)
    if attempt.get("schema_version") != "eq-attempt-v1":
        raise ComparisonError(f"{run_dir.name}: attempt record schema differs")
    if attempt.get("chain_id") != run_dir.name:
        raise ComparisonError(f"{run_dir.name}: attempt record chain differs")
    if attempt.get("attempt") != metrics.get("attempt"):
        raise ComparisonError(f"{run_dir.name}: attempt number differs")
    threads = integer(attempt.get("requested_threads"), f"{run_dir.name} threads")
    if attempt.get("requested_velocity_seed") != velocity_seed:
        raise ComparisonError(f"{run_dir.name}: attempt velocity seed differs")
    if attempt.get("requested_seed") != velocity_seed:
        raise ComparisonError(f"{run_dir.name}: attempt seed alias differs")
    if attempt.get("seed_semantics") != "gromacs_nvt_gen_seed":
        raise ComparisonError(f"{run_dir.name}: attempt seed semantics differ")
    if attempt.get("inherited_packmol_seed") != packmol_seed:
        raise ComparisonError(f"{run_dir.name}: attempt Packmol seed differs")
    require_close(
        attempt.get("requested_npt_ps"), 1000.0, f"{run_dir.name} attempt NPT ps"
    )
    attempt_evidence = verify_attempt_snapshot(
        work, metrics_path, metrics, attempt_path, attempt
    )

    technical_failures: list[str] = []
    stage_metrics_by_name = {
        stage: require_dict(metrics.get(stage), f"{run_dir.name} {stage} metrics")
        for stage in ("nvt", "npt")
    }
    if technical_status != "PASS_COMPLETE":
        technical_failures.append("equilibration_technical_status_failed")
        analysis_summary = None
    else:
        if metrics.get("physics_status") != "EXPLORATORY_ONLY":
            raise ComparisonError(f"{run_dir.name}: metrics physics status differs")
        warnings = require_dict(metrics.get("grompp_warnings"), f"{run_dir.name} warnings")
        if warnings != {"nvt": 0, "npt": 0}:
            technical_failures.append("grompp_warnings_nonzero")
        markers = require_dict(metrics.get("bad_markers"), f"{run_dir.name} bad markers")
        if any(value != 0 for value in markers.values()):
            technical_failures.append("bad_runtime_markers_present")
        for stage, target in (("nvt", 100.0), ("npt", 1000.0)):
            stage_metrics = stage_metrics_by_name[stage]
            duration = finite(
                stage_metrics.get("duration_ps"), f"{run_dir.name} {stage} duration"
            )
            if duration + 1.0e-6 < target:
                technical_failures.append(f"{stage}_duration_incomplete")
        analysis_summary = validate_analysis(
            run_dir.name,
            require_dict(metrics.get("analysis"), f"{run_dir.name} analysis"),
        )
        if metrics.get("equilibrium_validated") not in (None, False):
            raise ComparisonError(f"{run_dir.name}: metrics claim equilibrium")
        if metrics.get("production_ready") not in (None, False):
            raise ComparisonError(f"{run_dir.name}: metrics claim production readiness")

    stage_evidence: dict[str, dict[str, Any]] = {}
    for stage, target in (("nvt", 100.0), ("npt", 1000.0)):
        stage_evidence.update(
            verify_stage_artifacts(
                work, stage, target, stage_metrics_by_name[stage], threads
            )
        )

    force_field_names = ("Li.zmat", "c3c1pyrr.zmat", "fsi.zmat", "il.ff")
    source_files = {
        name: file_evidence(run_dir / "input" / name) for name in force_field_names
    }
    source_evidence = {
        "metrics.json": file_evidence(parent_metrics_path),
        "validation.json": file_evidence(validation_path),
        "equilibration/equilibration_metrics.json": file_evidence(metrics_path),
        "equilibration/chain_manifest.json": file_evidence(manifest_path),
        "equilibration/INPUT_SHA256.json": file_evidence(input_hash_path),
        "input/initial.gro": file_evidence(initial),
        "em.gro": file_evidence(em_gro),
        "equilibration/nvt.gro": file_evidence(nvt_gro),
        "input/topol.top": file_evidence(topology),
        "input/em.mdp": file_evidence(run_dir / "input" / "em.mdp"),
        "equilibration/nvt_100ps.mdp": file_evidence(nvt_mdp),
        "equilibration/npt_1000ps.mdp": file_evidence(npt_mdp),
        **attempt_evidence,
        **stage_evidence,
        **{f"input/{name}": evidence for name, evidence in source_files.items()},
        **packmol_evidence,
    }
    return {
        "chain_id": run_dir.name,
        "packmol_seed": packmol_seed,
        "velocity_seed": velocity_seed,
        "seed_cross_validation": {
            "passed": True,
            "manifest_mode": manifest_seed_mode,
            "manifest_seed": velocity_seed,
            "nvt_mdp_gen_seed": mdp_seed,
            "attempt_requested_seed": attempt["requested_seed"],
            "attempt_requested_velocity_seed": attempt["requested_velocity_seed"],
            "attempt_seed_semantics": attempt["seed_semantics"],
            "completed_metrics_seed": metrics.get("seed"),
            "completed_metrics_velocity_seed": metrics.get("velocity_seed"),
            "completed_metrics_seed_semantics": metrics.get("seed_semantics"),
        },
        "parent_packmol_provenance": parent_packmol_provenance,
        "requested_density_kg_m3": requested_density,
        "initial_density_kg_m3": calculated_initial_density,
        "composition": composition,
        "technical_status": technical_status,
        "technical_failures": technical_failures,
        "analysis": analysis_summary,
        "protocol": {
            "protocol_version": manifest["protocol_version"],
            "topology_sha256": topology_hash,
            "em_mdp_sha256": sha256(run_dir / "input" / "em.mdp"),
            "normalized_nvt_mdp": normalized_nvt,
            "npt_mdp_sha256": sha256(npt_mdp),
            "gromacs_version": manifest.get("gromacs_version"),
            "openmp_threads": threads,
            "canonical_topology_sha256": canonical_topology_sha256,
            "force_field_source_sha256": {
                name: evidence["sha256"] for name, evidence in source_files.items()
            },
        },
        "coordinate_sha256": {
            "packmol_initial_gro": sha256(initial),
            "em_gro": sha256(em_gro),
            "nvt_gro": sha256(nvt_gro),
        },
        "source_evidence": source_evidence,
    }


def all_equal(records: list[dict[str, Any]], getter) -> bool:
    return len({json.dumps(getter(record), sort_keys=True) for record in records}) == 1


def density_statistics(records: list[dict[str, Any]]) -> dict[str, Any]:
    values = [record["analysis"]["last500_density_mean_kg_m3"] for record in records]
    mean = statistics.mean(values)
    if mean <= 0:
        raise ComparisonError("replica density mean must be positive")
    sample_std = statistics.stdev(values)
    pairwise = []
    for index, left in enumerate(records):
        for right in records[index + 1 :]:
            a = left["analysis"]["last500_density_mean_kg_m3"]
            b = right["analysis"]["last500_density_mean_kg_m3"]
            denominator = (abs(a) + abs(b)) / 2.0
            difference = abs(a - b) / denominator * 100.0 if denominator else 0.0
            pairwise.append(
                {
                    "replicas": [left["replica_id"], right["replica_id"]],
                    "symmetric_difference_percent": difference,
                }
            )
    return {
        "observations": [
            {
                "replica_id": record["replica_id"],
                "last500_density_mean_kg_m3": record["analysis"][
                    "last500_density_mean_kg_m3"
                ],
            }
            for record in records
        ],
        "replica_mean_kg_m3": mean,
        "sample_standard_deviation_kg_m3": sample_std,
        "technical_cv_percent": sample_std / abs(mean) * 100.0,
        "minimum_kg_m3": min(values),
        "maximum_kg_m3": max(values),
        "spread_percent": (max(values) - min(values)) / mean * 100.0,
        "pairwise": pairwise,
        "maximum_pairwise_symmetric_difference_percent": max(
            item["symmetric_difference_percent"] for item in pairwise
        ),
        "sem_not_calculated": True,
    }


def completion_snapshot(run_dirs: list[Path]) -> tuple[bool, list[dict[str, Any]]]:
    rows = []
    pending = False
    for run_dir in run_dirs:
        path = run_dir.resolve() / "equilibration" / "equilibration_metrics.json"
        if not path.is_file():
            pending = True
            rows.append({"chain_id": run_dir.name, "state": "MISSING"})
            continue
        payload = read_json(path)
        status = payload.get("technical_status")
        if status not in {"PASS_COMPLETE", "FAILED"}:
            pending = True
        rows.append(
            {
                "chain_id": run_dir.name,
                "state": status if isinstance(status, str) else "INCOMPLETE",
                "source_evidence": file_evidence(path),
            }
        )
    return pending, rows


def pending_payload(run_dirs: list[Path], completion: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "comparison_technical_status": "PENDING_INPUTS",
        "replica_set_technical_status": "PENDING",
        "physics_status": "NOT_EVALUATED",
        "one_ns_replica_verdict": "ONE_NS_REPLICA_COMPARISON_PENDING",
        "replica_count_expected": 3,
        "completion": completion,
        "planned_seed_mapping": [
            {
                "replica_id": plan["replica_id"],
                "packmol_seed": packmol_seed,
                "velocity_seed": plan["velocity_seed"],
            }
            for packmol_seed, plan in PLAN.items()
        ],
        "representative_replica": None,
        "equilibrium_validated": False,
        "production_ready": False,
        "source_evidence": {"comparison_rules": rules_evidence()},
        "not_verified": [
            "three completed independent 1 ns replica screens",
            "thermodynamic equilibrium",
            "production readiness",
            "structural and transport-property convergence",
            "laboratory-server reproduction",
        ],
    }


def compare_runs(run_dirs: list[Path]) -> dict[str, Any]:
    if len(run_dirs) != 3 or len({path.resolve() for path in run_dirs}) != 3:
        raise ComparisonError("exactly three unique replica run directories are required")
    rules = rules_evidence()
    pending, completion = completion_snapshot(run_dirs)
    if pending:
        return pending_payload(run_dirs, completion)

    audited_by_seed, input_audit_evidence = input_audit()
    records = [load_chain(path) for path in run_dirs]
    records.sort(key=lambda record: record["packmol_seed"])
    comparability_failures: list[str] = []
    actual_packmol = [record["packmol_seed"] for record in records]
    if actual_packmol != sorted(PLAN):
        comparability_failures.append("planned_packmol_seed_mapping_mismatch")
    for record in records:
        plan = PLAN.get(record["packmol_seed"])
        record["replica_id"] = plan["replica_id"] if plan else "UNPLANNED"
        if plan is None or record["velocity_seed"] != plan["velocity_seed"]:
            comparability_failures.append(
                f"{record['chain_id']}:planned_velocity_seed_mapping_mismatch"
            )
        audited = audited_by_seed.get(record["packmol_seed"])
        if audited is None:
            comparability_failures.append(
                f"{record['chain_id']}:missing_fixed_input_audit_binding"
            )
            record["input_audit_binding"] = None
        else:
            audited_initial = require_dict(
                audited.get("initial_gro"), "audited initial GRO evidence"
            )
            actual_initial = record["source_evidence"]["input/initial.gro"]
            if audited_initial != actual_initial:
                raise ComparisonError(
                    f"{record['chain_id']}: initial GRO differs from fixed input audit"
                )
            audited_density = finite(
                audited.get("initial_density_kg_m3"), "audited initial density"
            )
            if not math.isclose(
                audited_density,
                record["initial_density_kg_m3"],
                rel_tol=0.0,
                abs_tol=1.0e-6,
            ):
                raise ComparisonError(
                    f"{record['chain_id']}: initial density differs from fixed input audit"
                )
            record["input_audit_binding"] = {
                "audited_chain_id": audited.get("chain_id"),
                "packmol_seed": record["packmol_seed"],
                "initial_gro": audited_initial,
                "initial_density_kg_m3": audited_density,
            }

    for coordinate_name in ("packmol_initial_gro", "em_gro", "nvt_gro"):
        hashes = [record["coordinate_sha256"][coordinate_name] for record in records]
        if len(set(hashes)) != 3:
            comparability_failures.append(f"{coordinate_name}_hashes_not_unique")

    comparable_fields = {
        "requested_density": lambda record: record["requested_density_kg_m3"],
        "initial_density": lambda record: record["initial_density_kg_m3"],
        "composition": lambda record: record["composition"],
        "protocol_version": lambda record: record["protocol"]["protocol_version"],
        "topology": lambda record: record["protocol"]["topology_sha256"],
        "canonical_topology": lambda record: record["protocol"][
            "canonical_topology_sha256"
        ],
        "em_mdp": lambda record: record["protocol"]["em_mdp_sha256"],
        "normalized_nvt_mdp": lambda record: record["protocol"][
            "normalized_nvt_mdp"
        ]["sha256"],
        "npt_mdp": lambda record: record["protocol"]["npt_mdp_sha256"],
        "gromacs_version": lambda record: record["protocol"]["gromacs_version"],
        "openmp_threads": lambda record: record["protocol"]["openmp_threads"],
        "force_field_sources": lambda record: record["protocol"][
            "force_field_source_sha256"
        ],
    }
    for name, getter in comparable_fields.items():
        if not all_equal(records, getter):
            comparability_failures.append(f"{name}_differs")
    if any(record["protocol"]["openmp_threads"] != EXPECTED_THREADS for record in records):
        comparability_failures.append("openmp_threads_not_fixed_at_6")
    if any(
        not isinstance(record["protocol"]["gromacs_version"], str)
        or not record["protocol"]["gromacs_version"].strip()
        or "unknown" in record["protocol"]["gromacs_version"].lower()
        for record in records
    ):
        comparability_failures.append("gromacs_version_missing_or_unknown")
    comparability_failures = list(dict.fromkeys(comparability_failures))

    technical_failures = [
        f"{record['replica_id']}:{failure}"
        for record in records
        for failure in record["technical_failures"]
    ]
    screen_failures = [
        record["replica_id"]
        for record in records
        if record["analysis"] is not None
        and (
            record["analysis"]["exploratory_verdict"] == "SCREEN_FAIL"
            or record["analysis"]["hard_fail_reasons"]
        )
    ]
    stats: dict[str, Any] | None = None
    if comparability_failures:
        verdict = "ONE_NS_REPLICA_NOT_COMPARABLE"
    elif technical_failures or screen_failures:
        verdict = "ONE_NS_REPLICA_SET_FAIL"
    else:
        stats = density_statistics(records)
        minimum_margin = min(
            min(
                record["analysis"]["nvt_min_box_over_2rlist"],
                record["analysis"]["npt_min_box_over_2rlist"],
            )
            for record in records
        )
        spread = stats["spread_percent"]
        pairwise = stats["maximum_pairwise_symmetric_difference_percent"]
        if 1.0 < minimum_margin < 1.10:
            verdict = "ONE_NS_REPLICA_SIZE_REVIEW_REQUIRED"
        elif spread > 5.0 or pairwise > 5.0:
            verdict = "ONE_NS_REPLICA_DISPERSION_OR_INCOMPLETE"
        elif (
            any(
                record["analysis"]["exploratory_verdict"] == "SCREEN_EXTEND"
                for record in records
            )
            or spread > 2.0
            or pairwise > 2.0
        ):
            verdict = "ONE_NS_REPLICA_UNIFORM_EXTENSION_REQUIRED"
        elif all(
            record["analysis"]["exploratory_verdict"]
            == "SCREEN_STATIONARITY_PASS"
            for record in records
        ):
            verdict = "ONE_NS_REPLICA_EARLY_AGREEMENT_CANDIDATE"
        else:
            raise ComparisonError("fixed verdict priority did not produce a decision")

    output_records = []
    chain_sources = {}
    for record in records:
        analysis = record["analysis"]
        output_records.append(
            {
                "replica_id": record["replica_id"],
                "chain_id": record["chain_id"],
                "packmol_seed": record["packmol_seed"],
                "velocity_seed": record["velocity_seed"],
                "seed_cross_validation": record["seed_cross_validation"],
                "parent_packmol_provenance": record[
                    "parent_packmol_provenance"
                ],
                "input_audit_binding": record["input_audit_binding"],
                "requested_density_kg_m3": record["requested_density_kg_m3"],
                "initial_density_kg_m3": record["initial_density_kg_m3"],
                "composition": record["composition"],
                "technical_status": record["technical_status"],
                "technical_failures": record["technical_failures"],
                "exploratory_verdict": (
                    analysis["exploratory_verdict"] if analysis is not None else None
                ),
                "hard_fail_reasons": (
                    analysis["hard_fail_reasons"] if analysis is not None else []
                ),
                "last500_density_mean_kg_m3": (
                    analysis["last500_density_mean_kg_m3"]
                    if analysis is not None
                    else None
                ),
                "cutoff_margins": (
                    {
                        "nvt_min_box_over_2rlist": analysis[
                            "nvt_min_box_over_2rlist"
                        ],
                        "npt_min_box_over_2rlist": analysis[
                            "npt_min_box_over_2rlist"
                        ],
                    }
                    if analysis is not None
                    else None
                ),
                "coordinate_sha256": record["coordinate_sha256"],
                "protocol_evidence": record["protocol"],
            }
        )
        chain_sources[record["replica_id"]] = record["source_evidence"]

    return {
        "schema_version": SCHEMA,
        "comparison_technical_status": "PASS_COMPLETE",
        "replica_set_technical_status": (
            "NOT_COMPARABLE"
            if verdict == "ONE_NS_REPLICA_NOT_COMPARABLE"
            else (
                "FAIL"
                if verdict == "ONE_NS_REPLICA_SET_FAIL"
                else "PASS_COMPLETE"
            )
        ),
        "physics_status": (
            "NOT_EVALUATED"
            if verdict
            in {"ONE_NS_REPLICA_NOT_COMPARABLE", "ONE_NS_REPLICA_SET_FAIL"}
            else "EXPLORATORY_ONLY_NOT_EQUILIBRIUM"
        ),
        "one_ns_replica_verdict": verdict,
        "replica_count": 3,
        "planned_seed_mapping": [
            {
                "replica_id": plan["replica_id"],
                "packmol_seed": seed,
                "velocity_seed": plan["velocity_seed"],
            }
            for seed, plan in PLAN.items()
        ],
        "comparability": {
            "passed": not comparability_failures,
            "failures": comparability_failures,
            "seed_cross_validation_passed": all(
                record["seed_cross_validation"]["passed"] for record in records
            ),
            "packmol_coordinate_hashes_unique": "packmol_initial_gro_hashes_not_unique"
            not in comparability_failures,
            "em_coordinate_hashes_unique": "em_gro_hashes_not_unique"
            not in comparability_failures,
            "nvt_output_hashes_unique": "nvt_gro_hashes_not_unique"
            not in comparability_failures,
            "topology_protocol_gromacs_threads_compared": True,
            "nvt_protocol_fingerprint_excludes_only_gen_seed": True,
            "topology_hashes_identical": "topology_differs"
            not in comparability_failures,
            "em_protocol_hashes_identical": "em_mdp_differs"
            not in comparability_failures,
            "normalized_nvt_protocol_hashes_identical": "normalized_nvt_mdp_differs"
            not in comparability_failures,
            "npt_protocol_hashes_identical": "npt_mdp_differs"
            not in comparability_failures,
            "gromacs_versions_identical": "gromacs_version_differs"
            not in comparability_failures,
            "openmp_threads_identical": "openmp_threads_differs"
            not in comparability_failures,
            "force_field_source_hashes_identical": "force_field_sources_differs"
            not in comparability_failures,
        },
        "technical_failures": technical_failures,
        "screen_failures": screen_failures,
        "replicas": output_records,
        "density_statistics": stats,
        "representative_replica": None,
        "equilibrium_validated": False,
        "production_ready": False,
        "source_evidence": {
            "comparison_rules": rules,
            "replica_input_audit_v3": input_audit_evidence,
            "chains": chain_sources,
        },
        "not_verified": [
            "thermodynamic equilibrium",
            "production readiness",
            "structural and transport-property convergence",
            "force-field physical accuracy",
            "laboratory-server reproduction",
        ],
    }


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    try:
        return (
            json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        ).encode()
    except (TypeError, ValueError) as exc:
        raise ComparisonError(f"comparison output is not finite JSON: {exc}") from exc


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
                    f"comparison was concurrently created with different content: {path}"
                )
    finally:
        temporary.unlink(missing_ok=True)


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dirs", nargs=3, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        run_dirs = [path.resolve() for path in args.run_dirs]
        output = args.output.resolve()
        if any(is_within(output, run_dir) for run_dir in run_dirs):
            raise ComparisonError("comparison output must not be inside a run directory")
        if is_within(output, (PROJECT / "07_Handoff").resolve()):
            raise ComparisonError("comparison output must not modify 07_Handoff")
        payload = compare_runs(run_dirs)
        if (
            payload.get("one_ns_replica_verdict")
            == "ONE_NS_REPLICA_COMPARISON_PENDING"
        ):
            print(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False))
            raise SystemExit(2)
        write_json_once(output, payload)
        print(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False))
    except (ComparisonError, OSError, KeyError, TypeError, ValueError) as exc:
        print(
            f"replica 1 ns comparison failed safely: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
