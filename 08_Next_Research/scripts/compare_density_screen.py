#!/usr/bin/env python3
"""Compare completed exploratory equilibration chains from different initial densities."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re


SHA256_RE = re.compile(r"[0-9a-f]{64}")
TIME_TOLERANCE_PS = 1.0e-6


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_evidence(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise ValueError(f"required resume provenance file is missing: {path}")
    return {"sha256": sha256(path), "size_bytes": path.stat().st_size}


def reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def resolve_work_relative(work: Path, value: object, context: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context} path is missing")
    relative = Path(value)
    if relative.is_absolute():
        raise ValueError(f"{context} path must be relative to equilibration: {value}")
    work_resolved = work.resolve()
    resolved = (work / relative).resolve()
    try:
        resolved.relative_to(work_resolved)
    except ValueError as exc:
        raise ValueError(f"{context} path escapes equilibration: {value}") from exc
    if resolved == work_resolved:
        raise ValueError(f"{context} path does not identify a file")
    return resolved


def read_resume_record(path: Path, context: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(), parse_constant=reject_json_constant)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{context} record cannot be read: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{context} record must be a JSON object")
    return payload


def finite_number(value: object, context: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{context} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context} must be numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"{context} must be finite")
    return number


def validate_stage_resume_provenance(
    stage_metrics: object,
    stage: str,
    work: Path,
    chain_id: str,
) -> dict[str, object]:
    """Require immutable checkpoint evidence only when a stage was resumed."""
    context = f"{chain_id}:{stage}"
    if not isinstance(stage_metrics, dict):
        raise ValueError(f"{context} stage metrics are missing")
    resumed = stage_metrics.get("resumed")
    if not isinstance(resumed, bool):
        raise ValueError(f"{context} resumed must be boolean")
    checkpoint_hash = stage_metrics.get("checkpoint_in_sha256", "")
    evidence_file = stage_metrics.get("resume_evidence_file", "")
    checkpoint_file = stage_metrics.get("resume_checkpoint_file", "")
    if not resumed:
        if checkpoint_hash or evidence_file or checkpoint_file:
            raise ValueError(f"{context} non-resumed stage carries resume evidence")
        return {"resumed": False}

    if not isinstance(checkpoint_hash, str) or SHA256_RE.fullmatch(checkpoint_hash) is None:
        raise ValueError(
            f"{context} resumed stage lacks immutable checkpoint_in_sha256"
        )
    evidence_match = re.fullmatch(
        rf"resume_evidence/({re.escape(stage)}_resume_\d{{3}})\.json",
        str(evidence_file),
    )
    if evidence_match is None:
        raise ValueError(f"{context} resume_evidence_file is not a write-once record path")
    expected_checkpoint_file = (
        f"resume_evidence/{evidence_match.group(1)}_checkpoint.cpt"
    )
    if checkpoint_file != expected_checkpoint_file:
        raise ValueError(f"{context} resume_checkpoint_file is not the paired snapshot path")
    evidence_path = resolve_work_relative(
        work, evidence_file, f"{context} resume_evidence_file"
    )
    snapshot_path = resolve_work_relative(
        work, checkpoint_file, f"{context} resume_checkpoint_file"
    )
    if evidence_path == snapshot_path:
        raise ValueError(f"{context} resume record and checkpoint snapshot are the same file")
    record = read_resume_record(evidence_path, context)
    if record.get("schema_version") != "eq-resume-evidence-v1":
        raise ValueError(f"{context} resume evidence schema mismatch")
    if record.get("stage") != stage:
        raise ValueError(f"{context} resume evidence stage mismatch")
    if record.get("checkpoint_snapshot") != checkpoint_file:
        raise ValueError(f"{context} checkpoint snapshot path mismatch")
    if record.get("checkpoint_source_name") != f"{stage}.cpt":
        raise ValueError(f"{context} checkpoint source name mismatch")

    snapshot_evidence = file_evidence(snapshot_path)
    recorded_checkpoint = record.get("checkpoint_in")
    if not isinstance(recorded_checkpoint, dict):
        raise ValueError(f"{context} checkpoint_in record is missing")
    if recorded_checkpoint != snapshot_evidence:
        raise ValueError(f"{context} resume checkpoint snapshot/record SHA mismatch")
    if recorded_checkpoint.get("sha256") != checkpoint_hash:
        raise ValueError(f"{context} checkpoint_in_sha256 mismatch")

    resume_time = finite_number(
        stage_metrics.get("resume_from_time_ps"), f"{context} resume_from_time_ps"
    )
    pre_range = record.get("pre_resume_edr_range_ps")
    if not isinstance(pre_range, dict):
        raise ValueError(f"{context} pre-resume EDR range is missing")
    recorded_last = finite_number(pre_range.get("last"), f"{context} pre-resume last time")
    if not math.isclose(
        recorded_last,
        resume_time,
        rel_tol=0.0,
        abs_tol=TIME_TOLERANCE_PS,
    ):
        raise ValueError(f"{context} resume time differs from immutable evidence")
    return {
        "resumed": True,
        "checkpoint_in_sha256": checkpoint_hash,
        "resume_evidence_file": evidence_file,
        "resume_evidence_sha256": sha256(evidence_path),
        "resume_checkpoint_file": checkpoint_file,
        "resume_checkpoint_sha256": snapshot_evidence["sha256"],
        "resume_from_time_ps": resume_time,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dirs", nargs=3, type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.force:
        raise SystemExit(f"refusing to overwrite existing output without --force: {args.output}")
    records = []
    manifests = []
    for run_dir in args.run_dirs:
        work = run_dir / "equilibration"
        metrics_path = work / "equilibration_metrics.json"
        payload = json.loads(metrics_path.read_text())
        if payload.get("technical_status") != "PASS_COMPLETE":
            raise SystemExit(f"incomplete chain: {run_dir}")
        try:
            resume_provenance = {
                stage: validate_stage_resume_provenance(
                    payload.get(stage), stage, work, run_dir.name
                )
                for stage in ("nvt", "npt")
            }
        except ValueError as exc:
            raise SystemExit(f"invalid resume provenance: {exc}") from exc
        em = json.loads((run_dir / "metrics.json").read_text())
        manifest = json.loads((work / "chain_manifest.json").read_text())
        manifests.append(manifest)
        analysis = payload["analysis"]
        density_mean = analysis["npt_last_500ps"]["Density"]["mean"]
        if not math.isfinite(density_mean):
            raise SystemExit(f"non-finite density mean: {run_dir}")
        records.append(
            {
                "chain_id": run_dir.name,
                "initial_density_kg_m3": em["initial_density_kg_m3"],
                "last500_density_mean": density_mean,
                "density_slope_percent_per_ns": analysis["density_slope_percent_per_ns"],
                "last_two_block_diff_percent": analysis["density_last_two_block_diff_percent"],
                "min_box_over_2rlist": analysis["npt_min_box_over_2rlist"],
                "exploratory_verdict": analysis["exploratory_verdict"],
                "hard_fail_reasons": analysis["hard_fail_reasons"],
                "resume_provenance": resume_provenance,
            }
        )
    expected_densities = [1000.0, 1200.0, 1400.0]
    actual_densities = sorted(record["initial_density_kg_m3"] for record in records)
    if any(abs(actual - expected) > 2.0 for actual, expected in zip(actual_densities, expected_densities)):
        raise SystemExit(f"expected unique initial densities near {expected_densities}, got {actual_densities}")
    if len({round(value, 3) for value in actual_densities}) != 3:
        raise SystemExit("initial densities are not unique")
    comparable_fields = {
        "seed": {manifest["seed"] for manifest in manifests},
        "npt_ps": {manifest["npt_ps"] for manifest in manifests},
        "parent_topology_sha256": {manifest["parent_topology_sha256"] for manifest in manifests},
        "nvt_mdp_sha256": {
            manifest["input_sha256"]["nvt_100ps.mdp"] for manifest in manifests
        },
    }
    npt_mdp_hashes = {
        next(value for name, value in manifest["input_sha256"].items() if name.startswith("npt_"))
        for manifest in manifests
    }
    comparable_fields["npt_mdp_sha256"] = npt_mdp_hashes
    mismatches = {name: sorted(values) for name, values in comparable_fields.items() if len(values) != 1}
    if mismatches:
        raise SystemExit(f"chains are not directly comparable: {mismatches}")
    means = [record["last500_density_mean"] for record in records]
    pooled = sum(means) / len(means)
    spread = (max(means) - min(means)) / pooled * 100.0
    any_screen_fail = any(record["hard_fail_reasons"] for record in records)
    if any_screen_fail:
        convergence = "SCREEN_FAIL_PRESENT"
    elif spread <= 2.0:
        convergence = "SAME_BASIN_CANDIDATE"
    elif spread <= 5.0:
        convergence = "INITIAL_CONDITION_DEPENDENCE_OR_INCOMPLETE"
    else:
        convergence = "NOT_CONVERGED"
    eligible = [record for record in records if not record["hard_fail_reasons"]]
    recommended = (
        min(
            eligible,
            key=lambda item: (
                item["exploratory_verdict"] != "SCREEN_STATIONARITY_PASS",
                item["density_slope_percent_per_ns"] + item["last_two_block_diff_percent"],
                -item["min_box_over_2rlist"],
            ),
        )
        if eligible
        else None
    )
    report = {
        "chains": records,
        "plateau_spread_percent": spread,
        "cross_start_assessment": convergence,
        "best_exploratory_chain": recommended["chain_id"] if recommended else None,
        "physics_status": "EXPLORATORY_ONLY",
        "not_verified": [
            "approved target density",
            "force-field charge scaling",
            "long-time equilibrium",
            "independent replicas",
            "production and transport properties",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    temporary = args.output.with_name(f".{args.output.name}.{os.getpid()}.tmp")
    temporary.write_text(content)
    os.replace(temporary, args.output)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
