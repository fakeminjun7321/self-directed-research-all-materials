#!/usr/bin/env python3
"""Deterministically rebuild exploratory equilibration CSV registries.

Completed worker outputs are the source of truth.  This script never edits a
run directory and never appends to a central CSV.  It validates every completed
chain, renders both CSVs in memory, validates cross-references and duplicates,
then writes temporary files and replaces the registries while holding one lock.

When ``npt_ext001`` exists, the frozen base snapshot remains ``npt:001`` and a
fully analyzed extension becomes ``npt:002``.  Partial or unanalyzed extensions
abort the entire rebuild before either central registry can be replaced.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import fcntl
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Iterable


SCRIPT_NAME = "consolidate_equilibration_registry.py"
QUARANTINE_SCHEMA = "registry-quarantine-v1"
QUARANTINE_REASON = "UNRECOVERABLE_RESUME_INPUT_CHECKPOINT_PROVENANCE"
QUARANTINE_EVIDENCE_FILES = {
    "equilibration/chain_manifest.json",
    "equilibration/equilibration_metrics.json",
    "equilibration/safety_thread_reduction_record.json",
}
QUARANTINE_CONFIG_RELATIVE = Path("06_Reproducibility/registry_quarantine.json")
QUARANTINE_AUDIT_RELATIVE = Path("06_Reproducibility/registry_quarantine_audit.json")
CHAIN_FIELDS = [
    "record_id",
    "chain_id",
    "system_id",
    "protocol_version",
    "stage",
    "segment_no",
    "mode",
    "parent_record_id",
    "input_sha256",
    "checkpoint_in_sha256",
    "environment_id",
    "start_at",
    "end_at",
    "start_step",
    "target_step",
    "last_step",
    "exit_code",
    "termination_reason",
    "tech_status",
    "physics_status",
    "artifact_path",
]
QC_FIELDS = [
    "chain_id",
    "record_id",
    "stage",
    "domain",
    "metric",
    "window_start_ps",
    "window_end_ps",
    "aggregation",
    "value",
    "unit",
    "criterion_id",
    "criterion_status",
    "verdict",
    "evidence_file",
    "reviewer",
]
STAGE_ORDER = {"nvt": 0, "npt": 1}
EXTENSION_ID = "npt_ext001"
EXTENSION_SCHEMA = "npt-extension-v1"
EXTENSION_ANALYSIS_FILE = "extension_analysis.json"
BASE_NPT_STEPS = 1_000_000
EXTENSION_NPT_STEPS = 2_000_000
TARGET_TOTAL_NPT_STEPS = 3_000_000
BASE_NPT_DURATION_PS = 1_000.0
EXTENSION_NPT_DURATION_PS = 2_000.0
TARGET_TOTAL_NPT_DURATION_PS = 3_000.0
TIME_TOLERANCE_PS = 1.0e-3
BASE_SNAPSHOT_FILES = {
    "npt.tpr",
    "npt.cpt",
    "npt.edr",
    "npt.xtc",
    "npt.log",
    "npt.gro",
    "equilibration_metrics.json",
}
POST_EXTENSION_FILES = {
    "npt.cpt",
    "npt.edr",
    "npt.xtc",
    "npt.log",
    "npt.gro",
    f"{EXTENSION_ID}.tpr",
}
SCREEN_VERDICTS = {
    "SCREEN_STATIONARITY_PASS",
    "SCREEN_EXTEND",
    "SCREEN_FAIL",
}
ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:+-]+$")
LOG_TIME_FORMAT = "%a %b %d %H:%M:%S %Y"


class RegistryError(RuntimeError):
    """A completed run is internally inconsistent or unsafe to consolidate."""


def reject_json_constant(value: str) -> None:
    raise RegistryError(f"non-finite JSON constant: {value}")


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RegistryError(f"required file is missing: {path}")
    try:
        value = json.loads(path.read_text(), parse_constant=reject_json_constant)
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RegistryError(f"expected a JSON object: {path}")
    return value


def require_mapping(mapping: dict[str, Any], key: str, context: str) -> dict[str, Any]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise RegistryError(f"{context}: {key} must be an object")
    return value


def require_number(mapping: dict[str, Any], key: str, context: str) -> float:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RegistryError(f"{context}: {key} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise RegistryError(f"{context}: {key} must be finite")
    return number


def require_text(mapping: dict[str, Any], key: str, context: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RegistryError(f"{context}: {key} must be non-empty text")
    return value.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_evidence(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RegistryError(f"required artifact is missing: {path}")
    return {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}


def require_integer(mapping: dict[str, Any], key: str, context: str) -> int:
    value = require_number(mapping, key, context)
    integer = int(value)
    if value != integer:
        raise RegistryError(f"{context}: {key} must be an integer")
    return integer


def require_exact(mapping: dict[str, Any], expected: dict[str, Any], context: str) -> None:
    for key, wanted in expected.items():
        actual = mapping.get(key)
        if actual != wanted:
            raise RegistryError(
                f"{context}: {key} mismatch: expected {wanted!r}, got {actual!r}"
            )


def validate_evidence_map(
    root: Path,
    evidence: dict[str, Any],
    expected_names: set[str],
    context: str,
) -> None:
    if set(evidence) != expected_names:
        raise RegistryError(
            f"{context}: artifact set mismatch: expected {sorted(expected_names)}, "
            f"got {sorted(evidence)}"
        )
    for name in sorted(expected_names):
        item = evidence.get(name)
        if not isinstance(item, dict):
            raise RegistryError(f"{context}: evidence for {name} must be an object")
        expected_hash = require_text(item, "sha256", f"{context}:{name}")
        expected_size = require_integer(item, "size_bytes", f"{context}:{name}")
        actual = file_evidence(root / name)
        if expected_hash != actual["sha256"] or expected_size != actual["size_bytes"]:
            raise RegistryError(
                f"{context}: artifact evidence mismatch for {root / name}"
            )


def validate_byte_prefix(base_path: Path, current_path: Path, context: str) -> None:
    if not base_path.is_file() or not current_path.is_file():
        raise RegistryError(f"{context}: append-prefix artifact is missing")
    if current_path.stat().st_size < base_path.stat().st_size:
        raise RegistryError(f"{context}: current artifact is shorter than base snapshot")
    with base_path.open("rb") as base, current_path.open("rb") as current:
        while True:
            expected = base.read(1024 * 1024)
            if not expected:
                break
            if current.read(len(expected)) != expected:
                raise RegistryError(f"{context}: base snapshot is not a byte prefix")


def sha256_prefix(path: Path, size_bytes: int, context: str) -> str:
    if size_bytes <= 0:
        raise RegistryError(f"{context}: prefix size must be positive")
    digest = hashlib.sha256()
    remaining = size_bytes
    with path.open("rb") as handle:
        while remaining:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                raise RegistryError(f"{context}: artifact is shorter than the evidenced prefix")
            digest.update(chunk)
            remaining -= len(chunk)
    return digest.hexdigest()


def require_exact_keys(mapping: dict[str, Any], expected: set[str], context: str) -> None:
    if set(mapping) != expected:
        raise RegistryError(
            f"{context}: field set mismatch: expected {sorted(expected)}, "
            f"got {sorted(mapping)}"
        )


def require_sha256(mapping: dict[str, Any], key: str, context: str) -> str:
    value = require_text(mapping, key, context)
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise RegistryError(f"{context}: {key} must be a lowercase SHA-256")
    return value


def canonical_bundle_sha256(hashes: dict[str, Any]) -> str:
    normalized: dict[str, str] = {}
    for name, value in hashes.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise RegistryError("input hash manifest must map filenames to SHA-256 strings")
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise RegistryError(f"invalid SHA-256 for {name}: {value}")
        normalized[name] = value
    encoded = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_actual_input_hashes(work: Path, hashes: dict[str, Any]) -> None:
    for relative_name, expected in sorted(hashes.items()):
        if not isinstance(relative_name, str) or Path(relative_name).name != relative_name:
            raise RegistryError(f"unsafe or nested input hash key: {relative_name!r}")
        path = work / relative_name
        if not path.is_file():
            raise RegistryError(f"hashed input is missing: {path}")
        actual = sha256_file(path)
        if actual != expected:
            raise RegistryError(
                f"input SHA-256 mismatch for {path}: expected {expected}, got {actual}"
            )


def resolve_work_relative(work: Path, value: Any, context: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise RegistryError(f"{context}: evidence path must be non-empty and relative")
    candidate = (work / value).resolve()
    try:
        candidate.relative_to(work.resolve())
    except ValueError as exc:
        raise RegistryError(f"{context}: evidence path escapes equilibration directory") from exc
    return candidate


def validate_attempt_provenance(
    metrics: dict[str, Any], work: Path, context: str
) -> dict[str, Any] | None:
    attempt_value = metrics.get("attempt")
    if attempt_value is None:
        return
    if isinstance(attempt_value, bool) or not isinstance(attempt_value, int) or attempt_value <= 0:
        raise RegistryError(f"{context}: attempt must be a positive integer")
    expected_started = f"attempts/attempt_{attempt_value:03d}_started.json"
    if metrics.get("attempt_started_record") != expected_started:
        raise RegistryError(f"{context}: attempt_started_record is inconsistent")
    started_path = resolve_work_relative(work, expected_started, context)
    started = read_json(started_path)
    require_exact(
        started,
        {
            "schema_version": "eq-attempt-v1",
            "attempt": attempt_value,
            "chain_id": require_text(metrics, "chain_id", context),
            "resume_requested": metrics.get("resume_requested"),
        },
        f"{context}:attempt start",
    )
    if "seed" in metrics and started.get("requested_seed") != metrics.get("seed"):
        raise RegistryError(f"{context}: attempt seed differs from final metrics")
    if "velocity_seed" in metrics:
        if metrics.get("velocity_seed") != metrics.get("seed"):
            raise RegistryError(f"{context}: velocity seed differs from legacy seed field")
        if started.get("requested_velocity_seed") != metrics.get("velocity_seed"):
            raise RegistryError(f"{context}: attempt velocity seed differs from final metrics")
        if started.get("seed_semantics") != "gromacs_nvt_gen_seed":
            raise RegistryError(f"{context}: attempt seed semantics are invalid")
    if "npt_target_ps" in metrics and started.get("requested_npt_ps") != metrics.get(
        "npt_target_ps"
    ):
        raise RegistryError(f"{context}: attempt NPT target differs from final metrics")
    previous_snapshot = started.get("previous_metrics_snapshot", "")
    previous_evidence = started.get("previous_metrics_evidence")
    if previous_snapshot:
        previous_path = resolve_work_relative(work, previous_snapshot, context)
        if not isinstance(previous_evidence, dict) or previous_evidence != file_evidence(
            previous_path
        ):
            raise RegistryError(f"{context}: previous metrics snapshot evidence mismatch")
    elif previous_evidence is not None:
        raise RegistryError(f"{context}: previous metrics evidence has no snapshot")
    final_path = work / "attempts" / f"attempt_{attempt_value:03d}_final.json"
    final = read_json(final_path)
    require_exact(
        final,
        {
            "schema_version": "eq-attempt-v1",
            "attempt": attempt_value,
            "chain_id": require_text(metrics, "chain_id", context),
            "technical_status": require_text(metrics, "technical_status", context),
            "physics_status": require_text(metrics, "physics_status", context),
            "metrics_snapshot": f"attempts/attempt_{attempt_value:03d}_metrics.json",
        },
        f"{context}:attempt final",
    )
    immutable_metrics = resolve_work_relative(work, final["metrics_snapshot"], context)
    evidence = require_mapping(final, "metrics_evidence", context)
    if evidence != file_evidence(immutable_metrics):
        raise RegistryError(f"{context}: immutable attempt metrics evidence mismatch")
    if immutable_metrics.read_bytes() != (work / "equilibration_metrics.json").read_bytes():
        raise RegistryError(f"{context}: live metrics differ from immutable final attempt metrics")
    return started


def validate_stage_resume_provenance(
    run: dict[str, Any],
    stage: str,
    work: Path,
    context: str,
) -> str:
    resumed = run.get("resumed")
    if not isinstance(resumed, bool):
        raise RegistryError(f"{context}:{stage}: resumed must be boolean")
    checkpoint_hash = run.get("checkpoint_in_sha256", "")
    evidence_file = run.get("resume_evidence_file", "")
    checkpoint_file = run.get("resume_checkpoint_file", "")
    if not resumed:
        if checkpoint_hash or evidence_file or checkpoint_file:
            raise RegistryError(f"{context}:{stage}: START stage carries resume evidence")
        return ""
    if not isinstance(checkpoint_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", checkpoint_hash):
        raise RegistryError(
            f"{context}:{stage}: resumed stage lacks immutable checkpoint_in_sha256; "
            "refusing non-reproducible registry update"
        )
    evidence_path = resolve_work_relative(work, evidence_file, f"{context}:{stage}")
    evidence = read_json(evidence_path)
    require_exact(
        evidence,
        {"schema_version": "eq-resume-evidence-v1", "stage": stage},
        f"{context}:{stage}:resume evidence",
    )
    if evidence.get("checkpoint_snapshot") != checkpoint_file:
        raise RegistryError(f"{context}:{stage}: checkpoint snapshot path mismatch")
    snapshot_path = resolve_work_relative(work, checkpoint_file, f"{context}:{stage}")
    recorded = require_mapping(evidence, "checkpoint_in", f"{context}:{stage}")
    if recorded != file_evidence(snapshot_path):
        raise RegistryError(f"{context}:{stage}: resume checkpoint snapshot changed")
    if require_text(recorded, "sha256", f"{context}:{stage}") != checkpoint_hash:
        raise RegistryError(f"{context}:{stage}: resume checkpoint SHA-256 mismatch")
    resume_time = require_number(run, "resume_from_time_ps", f"{context}:{stage}")
    pre_range = require_mapping(evidence, "pre_resume_edr_range_ps", f"{context}:{stage}")
    if not math.isclose(
        require_number(pre_range, "last", f"{context}:{stage}"),
        resume_time,
        rel_tol=0.0,
        abs_tol=TIME_TOLERANCE_PS,
    ):
        raise RegistryError(f"{context}:{stage}: resume time differs from immutable evidence")
    return checkpoint_hash


def parse_iso(value: str, context: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise RegistryError(f"{context}: invalid ISO timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        raise RegistryError(f"{context}: timestamp must include timezone: {value!r}")
    return parsed


def parse_stage_times_text(
    text: str,
    timezone: dt.tzinfo,
    context: str,
) -> tuple[str, str]:
    starts = re.findall(r"Started mdrun on rank\s+\d+\s+(.+)$", text, re.MULTILINE)
    finishes = re.findall(r"Finished mdrun on rank\s+\d+\s+(.+)$", text, re.MULTILINE)
    if not starts or not finishes:
        raise RegistryError(f"Started/Finished mdrun markers are incomplete: {context}")
    try:
        start_values = [dt.datetime.strptime(value.strip(), LOG_TIME_FORMAT) for value in starts]
        end_values = [dt.datetime.strptime(value.strip(), LOG_TIME_FORMAT) for value in finishes]
    except ValueError as exc:
        raise RegistryError(f"cannot parse mdrun timestamp in {context}: {exc}") from exc
    start = min(start_values).replace(tzinfo=timezone)
    end = max(end_values).replace(tzinfo=timezone)
    if end < start:
        raise RegistryError(f"stage end precedes start: {context}")
    return start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")


def parse_stage_times(log_path: Path, timezone: dt.tzinfo) -> tuple[str, str]:
    if not log_path.is_file():
        raise RegistryError(f"stage log is missing: {log_path}")
    return parse_stage_times_text(log_path.read_text(errors="replace"), timezone, str(log_path))


def count_bad_markers(paths: Iterable[Path]) -> dict[str, int]:
    text = "\n".join(path.read_text(errors="replace") for path in paths if path.is_file())
    return {
        "fatal": len(re.findall(r"fatal error", text, re.IGNORECASE)),
        "nan": len(re.findall(r"\bnan\b", text, re.IGNORECASE)),
        "lincs": len(re.findall(r"lincs warning", text, re.IGNORECASE)),
        "segfault": len(re.findall(r"segmentation fault", text, re.IGNORECASE)),
    }


def warning_count(path: Path) -> int:
    if not path.is_file():
        raise RegistryError(f"grompp log is missing: {path}")
    return len(re.findall(r"\bWARNING\b", path.read_text(errors="replace")))


def parse_system_id(run_dir: Path) -> str:
    record = run_dir / "RUN_RECORD.md"
    if record.is_file():
        match = re.search(r"^- System:\s*([A-Za-z0-9_.:+-]+)", record.read_text(), re.MULTILINE)
        if match:
            return match.group(1)
    match = re.search(r"(?:^|_)(L\d+P\d+(?:x\d+)?)(?:_|$)", run_dir.name)
    if match:
        return match.group(1)
    raise RegistryError(f"cannot determine system_id for {run_dir}")


def read_environment_map(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise RegistryError(f"environment registry is missing: {path}")
    result: dict[str, str] = {}
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "environment_id" not in reader.fieldnames or "gromacs_version" not in reader.fieldnames:
            raise RegistryError(f"environment registry has an unexpected header: {path}")
        for row in reader:
            environment_id = (row.get("environment_id") or "").strip()
            version = (row.get("gromacs_version") or "").strip()
            if environment_id and version and version != "TBD":
                if version in result:
                    raise RegistryError(f"duplicate GROMACS version in environment registry: {version}")
                result[version] = environment_id
    return result


def match_environment(version_line: str, environments: dict[str, str]) -> str:
    matches = [environment_id for version, environment_id in environments.items() if version in version_line]
    if len(matches) != 1:
        raise RegistryError(
            f"expected one environment for {version_line!r}, found {len(matches)}"
        )
    return matches[0]


def relative_artifact(path: Path, next_root: Path) -> str:
    try:
        relative = path.resolve().relative_to(next_root.resolve())
    except ValueError as exc:
        raise RegistryError(f"artifact is outside 08_Next_Research: {path}") from exc
    return relative.as_posix()


def format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RegistryError(f"non-finite QC value: {value}")
        return format(value, ".12g")
    if isinstance(value, str):
        return value
    raise RegistryError(f"unsupported QC value type: {type(value).__name__}")


def metric_verdict(value: float, *, lower: float | None = None, upper: float | None = None) -> str:
    if lower is not None and value < lower:
        return "FAIL"
    if upper is not None and value > upper:
        return "FAIL"
    return "PASS"


def render_csv(fields: list[str], rows: list[dict[str, Any]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        missing = set(fields) - set(row)
        extra = set(row) - set(fields)
        if missing or extra:
            raise RegistryError(f"CSV row schema mismatch; missing={missing}, extra={extra}")
        writer.writerow(row)
    return output.getvalue()


def make_qc_row(
    *,
    chain_id: str,
    record_id: str,
    stage: str,
    domain: str,
    metric: str,
    window_start: Any,
    window_end: Any,
    aggregation: str,
    value: Any,
    unit: str,
    criterion_id: str,
    criterion_status: str,
    verdict: str,
    evidence: str,
) -> dict[str, str]:
    return {
        "chain_id": chain_id,
        "record_id": record_id,
        "stage": stage,
        "domain": domain,
        "metric": metric,
        "window_start_ps": format_value(window_start) if window_start != "" else "",
        "window_end_ps": format_value(window_end) if window_end != "" else "",
        "aggregation": aggregation,
        "value": format_value(value),
        "unit": unit,
        "criterion_id": criterion_id,
        "criterion_status": criterion_status,
        "verdict": verdict,
        "evidence_file": evidence,
        "reviewer": SCRIPT_NAME,
    }


def require_close(actual: float, expected: float, context: str) -> None:
    if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=TIME_TOLERANCE_PS):
        raise RegistryError(f"{context}: expected {expected}, got {actual}")


def validate_time_range(
    value: dict[str, Any],
    expected_first: float,
    expected_last: float,
    context: str,
) -> None:
    first = require_number(value, "first", context)
    last = require_number(value, "last", context)
    duration = require_number(value, "duration", context)
    require_close(first, expected_first, f"{context}:first")
    require_close(last, expected_last, f"{context}:last")
    require_close(duration, expected_last - expected_first, f"{context}:duration")
    require_close(last - first, duration, f"{context}:range continuity")


def validate_extension_append_evidence(
    metrics: dict[str, Any],
    manifest: dict[str, Any],
    snapshot: Path,
    work: Path,
    timezone: dt.tzinfo,
    context: str,
) -> tuple[dict[str, int], str, str]:
    """Validate immutable, format-aware evidence for a completed GROMACS append.

    A completed EDR and log are not required to retain the finalized base file
    byte-for-byte.  GROMACS truncates them to the checkpoint-safe boundary and
    rewrites the boundary frame/final log suffix.  The XTC produced by this
    protocol does retain the complete finalized base prefix, while the EDR and
    log require their native semantic evidence to be checked instead.
    """
    append = require_mapping(metrics, "append_validation", context)
    require_exact_keys(append, {"xtc", "edr", "log"}, f"{context}:append validation")

    xtc = require_mapping(append, "xtc", context)
    require_exact_keys(
        xtc,
        {"mode", "base_size_bytes", "base_sha256"},
        f"{context}:XTC append evidence",
    )
    require_exact(
        xtc,
        {"mode": "full_byte_prefix"},
        f"{context}:XTC append evidence",
    )
    snapshot_xtc = file_evidence(snapshot / "npt.xtc")
    if require_integer(xtc, "base_size_bytes", context) != snapshot_xtc["size_bytes"]:
        raise RegistryError(f"{context}: XTC base prefix size evidence mismatch")
    if require_sha256(xtc, "base_sha256", context) != snapshot_xtc["sha256"]:
        raise RegistryError(f"{context}: XTC base prefix SHA-256 evidence mismatch")
    validate_byte_prefix(snapshot / "npt.xtc", work / "npt.xtc", f"{context}:npt.xtc")

    edr = require_mapping(append, "edr", context)
    require_exact_keys(
        edr,
        {
            "mode",
            "energy_terms_compared",
            "base_frames",
            "live_frames",
            "frame_cadence_ps",
            "exact_pre_boundary_last_ps",
            "canonical_pre_boundary_sha256",
            "canonical_pre_boundary_size_bytes",
            "boundary_ps",
            "boundary_comparison",
        },
        f"{context}:EDR append evidence",
    )
    require_exact(
        edr,
        {
            "mode": "exact_pre_boundary_plus_gromacs_boundary_comparison",
            "energy_terms_compared": 45,
            "base_frames": 1001,
            "live_frames": 3001,
            "boundary_comparison": (
                "gmx_check_native_default_tolerance_no_mismatch_lines"
            ),
        },
        f"{context}:EDR append evidence",
    )
    if require_integer(edr, "energy_terms_compared", context) != 45:
        raise RegistryError(f"{context}: EDR energy-term count mismatch")
    cadence = require_number(edr, "frame_cadence_ps", context)
    require_close(cadence, 1.0, f"{context}:EDR frame cadence")
    require_close(
        require_number(edr, "exact_pre_boundary_last_ps", context),
        BASE_NPT_DURATION_PS - cadence,
        f"{context}:EDR exact pre-boundary last time",
    )
    require_close(
        require_number(edr, "boundary_ps", context),
        BASE_NPT_DURATION_PS,
        f"{context}:EDR checkpoint boundary",
    )
    expected_base_frames = int(round(BASE_NPT_DURATION_PS / cadence)) + 1
    expected_live_frames = int(round(TARGET_TOTAL_NPT_DURATION_PS / cadence)) + 1
    if require_integer(edr, "base_frames", context) != expected_base_frames:
        raise RegistryError(f"{context}: EDR base frame count/cadence mismatch")
    if require_integer(edr, "live_frames", context) != expected_live_frames:
        raise RegistryError(f"{context}: EDR live frame count/cadence mismatch")

    canonical_size = require_integer(edr, "canonical_pre_boundary_size_bytes", context)
    canonical_hash = require_sha256(edr, "canonical_pre_boundary_sha256", context)
    base_edr = snapshot / "npt.edr"
    live_edr = work / "npt.edr"
    if canonical_size >= base_edr.stat().st_size:
        raise RegistryError(
            f"{context}: canonical EDR pre-boundary evidence includes the rewritten boundary"
        )
    if sha256_prefix(base_edr, canonical_size, f"{context}:base EDR") != canonical_hash:
        raise RegistryError(f"{context}: canonical base EDR evidence mismatch")
    if sha256_prefix(live_edr, canonical_size, f"{context}:live EDR") != canonical_hash:
        raise RegistryError(f"{context}: canonical live EDR history mismatch")

    log = require_mapping(append, "log", context)
    require_exact_keys(
        log,
        {
            "mode",
            "base_snapshot_finished_mdrun_markers",
            "live_finished_mdrun_markers",
            "restart_append_markers",
            "bad_markers",
        },
        f"{context}:log append evidence",
    )
    require_exact(
        log,
        {"mode": "checkpoint_restart_append_sequence"},
        f"{context}:log append evidence",
    )
    base_text = (snapshot / "npt.log").read_text(errors="replace")
    live_text = (work / "npt.log").read_text(errors="replace")
    base_finished = base_text.count("Finished mdrun")
    live_finished = live_text.count("Finished mdrun")
    manifest_base_finished = require_integer(
        manifest, "base_finished_mdrun_markers", context
    )
    if base_finished != manifest_base_finished or base_finished != 1:
        raise RegistryError(f"{context}: immutable base Finished marker evidence mismatch")
    if require_integer(log, "base_snapshot_finished_mdrun_markers", context) != base_finished:
        raise RegistryError(f"{context}: stored base Finished marker evidence mismatch")
    if live_finished != 1:
        raise RegistryError(f"{context}: live append must contain one final Finished marker")
    if require_integer(log, "live_finished_mdrun_markers", context) != live_finished:
        raise RegistryError(f"{context}: stored live Finished marker evidence mismatch")
    if require_integer(metrics, "finished_mdrun_markers", context) != live_finished:
        raise RegistryError(f"{context}: final Finished marker count mismatch")

    restart_matches = list(
        re.finditer(
            r"Restarting from checkpoint,\s*appending to previous log file\.",
            live_text,
            re.IGNORECASE,
        )
    )
    stored_restarts = require_integer(log, "restart_append_markers", context)
    if not restart_matches or stored_restarts != len(restart_matches):
        raise RegistryError(f"{context}: checkpoint append restart evidence mismatch")
    last_restart = restart_matches[-1]
    checkpoint_offset = live_text.rfind(
        "Reading checkpoint file", 0, last_restart.start()
    )
    started_offset = live_text.find("Started mdrun", last_restart.end())
    finished_offset = live_text.find("Finished mdrun", started_offset)
    if checkpoint_offset < 0 or started_offset < 0 or finished_offset < 0:
        raise RegistryError(
            f"{context}: live log lacks checkpoint -> restart -> start -> Finished sequence"
        )

    stored_bad = require_mapping(log, "bad_markers", context)
    require_exact_keys(
        stored_bad,
        {"fatal", "nan", "lincs", "segfault"},
        f"{context}:log bad-marker evidence",
    )
    actual_bad = count_bad_markers([work / "npt.log"])
    for key in sorted(actual_bad):
        if require_integer(stored_bad, key, context) != actual_bad[key]:
            raise RegistryError(f"{context}: stored log bad-marker evidence mismatch for {key}")
    if any(actual_bad.values()):
        raise RegistryError(f"{context}: bad markers in live NPT log: {actual_bad}")

    extension_log = live_text[checkpoint_offset:]
    started, ended = parse_stage_times_text(
        extension_log, timezone, f"{context}:checkpoint append npt.log"
    )
    return actual_bad, started, ended


def discover_extension(
    work: Path,
    chain_id: str,
    chain_manifest: dict[str, Any],
    timezone: dt.tzinfo,
) -> dict[str, Any] | None:
    extension_dir = work / "extensions" / EXTENSION_ID
    if not extension_dir.exists():
        return None
    if not extension_dir.is_dir():
        raise RegistryError(f"{chain_id}: extension path is not a directory: {extension_dir}")

    manifest_path = extension_dir / "extension_manifest.json"
    metrics_path = extension_dir / "extension_metrics.json"
    analysis_path = extension_dir / EXTENSION_ANALYSIS_FILE
    missing = [
        path.name
        for path in (manifest_path, metrics_path, analysis_path)
        if not path.is_file()
    ]
    if missing:
        if EXTENSION_ANALYSIS_FILE in missing:
            raise RegistryError(
                f"{chain_id}: extension analysis is missing; refusing central registry update "
                f"until {analysis_path} exists"
            )
        raise RegistryError(
            f"{chain_id}: incomplete extension artifacts {missing}; refusing central registry update"
        )

    context = f"{chain_id}:{EXTENSION_ID}"
    manifest = read_json(manifest_path)
    metrics = read_json(metrics_path)
    analysis_document = read_json(analysis_path)
    base_record_id = f"{chain_id}:npt:001"
    extension_record_id = f"{chain_id}:npt:002"
    require_exact(
        manifest,
        {
            "schema_version": EXTENSION_SCHEMA,
            "extension_id": EXTENSION_ID,
            "chain_id": chain_id,
            "record_id": extension_record_id,
            "parent_record_id": base_record_id,
            "stage": "npt",
            "segment_no": 2,
            "mode": "EXTEND",
            "start_step": BASE_NPT_STEPS,
            "target_step": EXTENSION_NPT_STEPS,
            "base_steps": BASE_NPT_STEPS,
            "extension_steps": EXTENSION_NPT_STEPS,
            "target_total_steps": TARGET_TOTAL_NPT_STEPS,
            "dt_ps": 0.001,
            "base_duration_ps": BASE_NPT_DURATION_PS,
            "extension_duration_ps": EXTENSION_NPT_DURATION_PS,
            "target_total_duration_ps": TARGET_TOTAL_NPT_DURATION_PS,
            "base_snapshot_path": "base_snapshot",
            "output_prefix": "npt",
            "extended_tpr_path": f"{EXTENSION_ID}.tpr",
            "gromacs_version": require_text(chain_manifest, "gromacs_version", context),
        },
        f"{context}:manifest",
    )
    if manifest.get("target_step_semantics") != (
        "extension segment length; cumulative target is target_total_steps"
    ):
        raise RegistryError(f"{context}: manifest target-step semantics are ambiguous")
    if BASE_NPT_STEPS + EXTENSION_NPT_STEPS != TARGET_TOTAL_NPT_STEPS:
        raise RegistryError(f"{context}: internal step-continuity invariant failed")
    if require_integer(manifest, "start_step", context) != require_integer(
        chain_manifest, "npt_steps", context
    ):
        raise RegistryError(f"{context}: extension start_step does not continue npt:001")
    if require_integer(manifest, "target_total_steps", context) != (
        require_integer(manifest, "start_step", context)
        + require_integer(manifest, "extension_steps", context)
    ):
        raise RegistryError(f"{context}: cumulative step continuity is broken")
    require_close(
        require_number(manifest, "extension_duration_ps", context),
        require_integer(manifest, "extension_steps", context)
        * require_number(manifest, "dt_ps", context),
        f"{context}:extension step/time continuity",
    )
    require_close(
        require_number(manifest, "target_total_duration_ps", context),
        require_integer(manifest, "target_total_steps", context)
        * require_number(manifest, "dt_ps", context),
        f"{context}:total step/time continuity",
    )
    chain_manifest_path = work / "chain_manifest.json"
    if require_text(manifest, "chain_manifest_sha256", context) != sha256_file(
        chain_manifest_path
    ):
        raise RegistryError(f"{context}: chain_manifest SHA-256 mismatch")

    snapshot = extension_dir / "base_snapshot"
    snapshot_evidence = require_mapping(manifest, "base_snapshot", context)
    validate_evidence_map(snapshot, snapshot_evidence, BASE_SNAPSHOT_FILES, f"{context}:snapshot")
    base_metrics_path = snapshot / "equilibration_metrics.json"
    base_metrics_hash = require_text(manifest, "base_metrics_sha256", context)
    if base_metrics_hash != sha256_file(base_metrics_path):
        raise RegistryError(f"{context}: base metrics SHA-256 mismatch")
    if file_evidence(work / "equilibration_metrics.json") != snapshot_evidence[
        "equilibration_metrics.json"
    ]:
        raise RegistryError(f"{context}: live base metrics changed after immutable snapshot")
    checkpoint_hash = require_text(manifest, "checkpoint_in_sha256", context)
    if checkpoint_hash != require_text(
        require_mapping(snapshot_evidence, "npt.cpt", context), "sha256", context
    ):
        raise RegistryError(f"{context}: checkpoint does not identify snapshot npt.cpt")
    base_range = require_mapping(manifest, "base_edr_range_ps", context)
    validate_time_range(base_range, 0.0, BASE_NPT_DURATION_PS, f"{context}:base EDR")
    require_close(
        require_number(manifest, "expected_final_edr_last_ps", context),
        TARGET_TOTAL_NPT_DURATION_PS,
        f"{context}:expected final EDR last",
    )

    require_exact(
        metrics,
        {
            "schema_version": EXTENSION_SCHEMA,
            "extension_id": EXTENSION_ID,
            "chain_id": chain_id,
            "record_id": extension_record_id,
            "parent_record_id": base_record_id,
            "stage": "npt",
            "segment_no": 2,
            "mode": "EXTEND",
            "start_step": BASE_NPT_STEPS,
            "target_step": EXTENSION_NPT_STEPS,
            "base_steps": BASE_NPT_STEPS,
            "extension_steps": EXTENSION_NPT_STEPS,
            "target_total_steps": TARGET_TOTAL_NPT_STEPS,
            "technical_status": "PASS_COMPLETE",
            "physics_status": "NOT_EVALUATED_AFTER_EXTENSION",
            "analysis_status": "PENDING_EXTENSION_REANALYSIS",
            "checkpoint_in_sha256": checkpoint_hash,
        },
        f"{context}:metrics",
    )
    if require_text(metrics, "extension_manifest_sha256", context) != sha256_file(
        manifest_path
    ):
        raise RegistryError(f"{context}: extension metrics reference a different manifest")
    metrics_range = require_mapping(metrics, "edr_range_ps", context)
    validate_time_range(
        metrics_range, 0.0, TARGET_TOTAL_NPT_DURATION_PS, f"{context}:completed EDR"
    )
    for key, expected in (
        ("base_duration", BASE_NPT_DURATION_PS),
        ("extension_duration", EXTENSION_NPT_DURATION_PS),
        ("target_total_duration", TARGET_TOTAL_NPT_DURATION_PS),
    ):
        require_close(require_number(metrics_range, key, context), expected, f"{context}:{key}")
    post_evidence = require_mapping(metrics, "post_extension_sha256", context)
    if set(post_evidence) != POST_EXTENSION_FILES:
        raise RegistryError(f"{context}: post-extension artifact set is invalid")
    for name in sorted(POST_EXTENSION_FILES):
        root = extension_dir if name == f"{EXTENSION_ID}.tpr" else work
        item = post_evidence.get(name)
        if not isinstance(item, dict) or file_evidence(root / name) != item:
            raise RegistryError(f"{context}: post-extension evidence mismatch for {name}")
    if require_text(manifest, "extended_tpr_sha256", context) != require_text(
        require_mapping(post_evidence, f"{EXTENSION_ID}.tpr", context), "sha256", context
    ):
        raise RegistryError(f"{context}: extended TPR SHA-256 mismatch")
    appended_markers, log_started, log_ended = validate_extension_append_evidence(
        metrics,
        manifest,
        snapshot,
        work,
        timezone,
        context,
    )

    attempt_number = metrics.get("completion_attempt")
    if attempt_number is not None:
        if isinstance(attempt_number, bool) or not isinstance(attempt_number, int) or attempt_number <= 0:
            raise RegistryError(f"{context}: completion_attempt must be a positive integer or null")
        attempt_path = extension_dir / "attempts" / f"attempt_{attempt_number:03d}_metrics.json"
        attempt = read_json(attempt_path)
        require_exact(
            attempt,
            {"attempt": attempt_number, "technical_status": "PASS_COMPLETE", "exit_code": 0},
            f"{context}:attempt",
        )
        validate_time_range(
            require_mapping(attempt, "edr_range_ps", context),
            0.0,
            TARGET_TOTAL_NPT_DURATION_PS,
            f"{context}:attempt EDR",
        )
        attempt_markers = require_mapping(attempt, "bad_markers", context)
        if any(require_integer(attempt_markers, key, context) != 0 for key in appended_markers):
            raise RegistryError(f"{context}: extension attempt has bad runtime markers")
        started = require_text(attempt, "started_at", context)
        ended = require_text(attempt, "ended_at", context)
        if parse_iso(ended, context) < parse_iso(started, context):
            raise RegistryError(f"{context}: extension attempt end precedes start")
    else:
        started, ended = log_started, log_ended

    if require_text(analysis_document, "schema_version", context) != (
        "npt-extension-analysis-v1"
    ):
        raise RegistryError(f"{context}: unsupported extension analysis schema")
    require_exact(
        analysis_document,
        {
            "extension_id": EXTENSION_ID,
            "chain_id": chain_id,
            "record_id": extension_record_id,
            "technical_status": "PASS_COMPLETE",
            "analysis_status": "PASS_COMPLETE",
            "physics_status": "EXPLORATORY_ONLY",
            "equilibrium_validated": False,
            "production_ready": False,
        },
        f"{context}:analysis",
    )
    source_evidence = require_mapping(analysis_document, "source_evidence", context)
    expected_source_paths = {
        "extension_manifest.json": manifest_path,
        "extension_metrics.json": metrics_path,
        "npt.edr": work / "npt.edr",
        f"{EXTENSION_ID}.tpr": extension_dir / f"{EXTENSION_ID}.tpr",
    }
    if set(source_evidence) != set(expected_source_paths):
        raise RegistryError(f"{context}: extension analysis source-evidence set is invalid")
    for name, path in expected_source_paths.items():
        if source_evidence.get(name) != file_evidence(path):
            raise RegistryError(f"{context}: extension analysis source changed: {name}")
    validate_time_range(
        require_mapping(analysis_document, "edr_range_ps", context),
        0.0,
        TARGET_TOTAL_NPT_DURATION_PS,
        f"{context}:analysis EDR",
    )
    analysis_window = require_mapping(analysis_document, "analysis_window_ps", context)
    require_close(
        require_number(analysis_window, "start", context), 2000.0, f"{context}:analysis window start"
    )
    require_close(
        require_number(analysis_window, "end", context), 3000.0, f"{context}:analysis window end"
    )
    block_definition = require_mapping(analysis_document, "block_definition", context)
    require_exact(
        block_definition,
        {"count": 5, "width_ps": 200.0, "window_start_ps": 2000.0, "window_end_ps": 3000.0},
        f"{context}:analysis blocks",
    )
    verdict = require_text(analysis_document, "exploratory_verdict", context)
    if verdict not in {
        "THREE_NS_STATIONARITY_CANDIDATE",
        "THREE_NS_EXTEND_OR_REVIEW",
        "THREE_NS_FAIL",
    }:
        raise RegistryError(f"{context}: unknown 3 ns exploratory verdict {verdict!r}")
    for key in ("hard_fail_reasons", "review_reasons"):
        reasons = analysis_document.get(key)
        if not isinstance(reasons, list) or not all(isinstance(item, str) for item in reasons):
            raise RegistryError(f"{context}: {key} must be a string list")

    return {
        "dir": extension_dir,
        "manifest_path": manifest_path,
        "metrics_path": metrics_path,
        "analysis_path": analysis_path,
        "base_metrics_path": base_metrics_path,
        "manifest": manifest,
        "metrics": metrics,
        "analysis_document": analysis_document,
        "checkpoint_hash": checkpoint_hash,
        "record_id": extension_record_id,
        "started": started,
        "ended": ended,
        "appended_markers": appended_markers,
    }


def append_extension_record(
    extension: dict[str, Any],
    chain_rows: list[dict[str, Any]],
    qc_rows: list[dict[str, str]],
    next_root: Path,
    system_id: str,
    environment_id: str,
) -> None:
    manifest = extension["manifest"]
    analysis = extension["analysis_document"]
    chain_id = require_text(manifest, "chain_id", EXTENSION_ID)
    context = f"{chain_id}:{EXTENSION_ID}"
    parent_record_id = require_text(manifest, "parent_record_id", context)
    parent = next(
        (row for row in chain_rows if row["record_id"] == parent_record_id),
        None,
    )
    if parent is None:
        raise RegistryError(f"{context}: npt:002 parent npt:001 was not built")
    if parent["stage"] != "npt" or int(parent["segment_no"]) != 1:
        raise RegistryError(f"{context}: parent is not the immutable npt:001 record")
    start_step = require_integer(manifest, "start_step", context)
    segment_steps = require_integer(manifest, "extension_steps", context)
    if start_step != int(parent["last_step"]):
        raise RegistryError(
            f"{context}: step continuity broken: npt:001 last_step={parent['last_step']} "
            f"but npt:002 start_step={start_step}"
        )
    if require_integer(manifest, "target_step", context) != segment_steps:
        raise RegistryError(f"{context}: segment target_step differs from extension_steps")

    record_id = require_text(manifest, "record_id", context)
    extension_artifact = relative_artifact(extension["dir"], next_root)
    chain_rows.append(
        {
            "record_id": record_id,
            "chain_id": chain_id,
            "system_id": system_id,
            "protocol_version": EXTENSION_SCHEMA,
            "stage": "npt",
            "segment_no": 2,
            "mode": "EXTEND",
            "parent_record_id": parent_record_id,
            "input_sha256": require_text(manifest, "extended_tpr_sha256", context),
            "checkpoint_in_sha256": extension["checkpoint_hash"],
            "environment_id": environment_id,
            "start_at": extension["started"],
            "end_at": extension["ended"],
            "start_step": start_step,
            "target_step": segment_steps,
            "last_step": segment_steps,
            "exit_code": 0,
            "termination_reason": "COMPLETED",
            "tech_status": "PASS_COMPLETE",
            "physics_status": "EXPLORATORY_ONLY",
            "artifact_path": extension_artifact,
        }
    )

    technical_evidence = relative_artifact(extension["metrics_path"], next_root)
    physical_evidence = relative_artifact(extension["analysis_path"], next_root)
    qc_rows.append(
        make_qc_row(
            chain_id=chain_id,
            record_id=record_id,
            stage="npt",
            domain="technical",
            metric="stage_duration",
            window_start=BASE_NPT_DURATION_PS,
            window_end=TARGET_TOTAL_NPT_DURATION_PS,
            aggregation="range",
            value=EXTENSION_NPT_DURATION_PS,
            unit="ps",
            criterion_id="TECH006",
            criterion_status="PROVISIONAL_EXPLORATORY",
            verdict="PASS",
            evidence=technical_evidence,
        )
    )
    for metric, key, criterion in (
        ("fatal_error", "fatal", "TECH002"),
        ("nan_count", "nan", "TECH003"),
        ("lincs_warning", "lincs", "TECH004"),
        ("segmentation_fault", "segfault", "TECH005"),
    ):
        value = int(extension["appended_markers"][key])
        qc_rows.append(
            make_qc_row(
                chain_id=chain_id,
                record_id=record_id,
                stage="npt",
                domain="technical",
                metric=metric,
                window_start=BASE_NPT_DURATION_PS,
                window_end=TARGET_TOTAL_NPT_DURATION_PS,
                aggregation="count",
                value=value,
                unit="count",
                criterion_id=criterion,
                criterion_status="PROVISIONAL_EXPLORATORY",
                verdict=metric_verdict(value, lower=0, upper=0),
                evidence=technical_evidence,
            )
        )

    final_window = require_mapping(analysis, "analysis_window_ps", context)
    window = (
        require_number(final_window, "start", context),
        require_number(final_window, "end", context),
    )
    last_1ns = require_mapping(analysis, "last_1ns", context)
    density_stats = require_mapping(last_1ns, "Density", context)
    density_qc = require_mapping(analysis, "density_qc", context)
    temperature_qc = require_mapping(analysis, "temperature_qc", context)
    volume_qc = require_mapping(analysis, "volume_qc", context)
    box_qc = require_mapping(analysis, "box_qc", context)
    thresholds = require_mapping(analysis, "thresholds", context)
    threshold_contract = {
        "min_box_over_2rlist_candidate_min": 1.10,
        "min_box_over_2rlist_hard_fail_max": 1.0,
        "temperature_abs_slope_K_per_ns_max": 1.0,
        "density_abs_slope_percent_per_ns_max": 0.5,
        "density_last_two_block_diff_percent_max": 0.5,
        "density_max_adjacent_block_diff_percent_max": 1.0,
        "density_first_vs_second_500ps_diff_percent_max": 1.0,
        "density_1_2ns_vs_2_3ns_diff_percent_max": 2.0,
        "max_adjacent_volume_jump_percent_max": 5.0,
    }
    for key, expected in threshold_contract.items():
        require_close(require_number(thresholds, key, context), expected, f"{context}:{key}")
    temperature_range = thresholds.get("temperature_mean_K_inclusive")
    if temperature_range != [293.0, 303.0]:
        raise RegistryError(f"{context}: temperature threshold contract changed")

    physical_specs = [
        (
            "density_mean",
            "mean",
            require_number(density_stats, "mean", context),
            "kg_m3",
            "OBS3NS001",
            None,
            None,
            window,
        ),
        (
            "density_slope_percent_per_ns",
            "slope",
            require_number(density_qc, "slope_percent_per_ns", context),
            "percent_per_ns",
            "EXT3NS004",
            0.0,
            0.5,
            window,
        ),
        (
            "density_last_two_block_diff_percent",
            "symmetric_difference",
            require_number(density_qc, "last_two_block_diff_percent", context),
            "percent",
            "EXT3NS005",
            0.0,
            0.5,
            window,
        ),
        (
            "density_max_adjacent_block_diff_percent",
            "max_symmetric_difference",
            require_number(density_qc, "max_adjacent_block_diff_percent", context),
            "percent",
            "EXT3NS006",
            0.0,
            1.0,
            window,
        ),
        (
            "density_first_vs_second_500ps_diff_percent",
            "symmetric_difference",
            require_number(density_qc, "first_vs_second_500ps_diff_percent", context),
            "percent",
            "EXT3NS007",
            0.0,
            1.0,
            window,
        ),
        (
            "density_1_2ns_vs_2_3ns_diff_percent",
            "symmetric_difference",
            require_number(
                density_qc, "one_to_two_vs_two_to_three_ns_diff_percent", context
            ),
            "percent",
            "EXT3NS008",
            0.0,
            2.0,
            (1000.0, 3000.0),
        ),
        (
            "temperature_mean",
            "mean",
            require_number(temperature_qc, "mean_K", context),
            "K",
            "EXT3NS002",
            293.0,
            303.0,
            window,
        ),
        (
            "absolute_temperature_slope_per_ns",
            "absolute_slope",
            abs(require_number(temperature_qc, "slope_K_per_ns", context)),
            "K_per_ns",
            "EXT3NS003",
            0.0,
            1.0,
            window,
        ),
        (
            "npt_min_box_over_2rlist",
            "min",
            require_number(box_qc, "min_box_over_2rlist", context),
            "ratio",
            "EXT3NS001",
            1.10,
            None,
            (0.0, 3000.0),
        ),
        (
            "max_adjacent_volume_jump_percent",
            "max_relative_jump",
            require_number(volume_qc, "max_adjacent_frame_jump_percent_0_3ns", context),
            "percent",
            "EXT3NS009",
            0.0,
            5.0,
            (0.0, 3000.0),
        ),
    ]
    for metric, aggregation, value, unit, criterion, lower, upper, metric_window in physical_specs:
        verdict = (
            "NOT_EVALUATED"
            if lower is None and upper is None
            else metric_verdict(value, lower=lower, upper=upper)
        )
        qc_rows.append(
            make_qc_row(
                chain_id=chain_id,
                record_id=record_id,
                stage="npt",
                domain="physical",
                metric=metric,
                window_start=metric_window[0],
                window_end=metric_window[1],
                aggregation=aggregation,
                value=value,
                unit=unit,
                criterion_id=criterion,
                criterion_status="PROVISIONAL_3NS_EXPLORATORY",
                verdict=verdict,
                evidence=physical_evidence,
            )
        )

    hard_fail_reasons = analysis["hard_fail_reasons"]
    review_reasons = analysis["review_reasons"]
    three_ns_verdict = require_text(analysis, "exploratory_verdict", context)
    expected_verdict = (
        "THREE_NS_FAIL"
        if hard_fail_reasons
        else "THREE_NS_EXTEND_OR_REVIEW"
        if review_reasons
        else "THREE_NS_STATIONARITY_CANDIDATE"
    )
    if three_ns_verdict != expected_verdict:
        raise RegistryError(f"{context}: 3 ns verdict conflicts with its reason lists")
    for metric, value, criterion in (
        ("three_ns_hard_fail_reason_count", len(hard_fail_reasons), "DEC3NS001"),
        ("three_ns_review_reason_count", len(review_reasons), "DEC3NS002"),
    ):
        qc_rows.append(
            make_qc_row(
                chain_id=chain_id,
                record_id=record_id,
                stage="npt",
                domain="physical",
                metric=metric,
                window_start=0.0,
                window_end=3000.0,
                aggregation="count",
                value=value,
                unit="count",
                criterion_id=criterion,
                criterion_status="PROVISIONAL_3NS_EXPLORATORY",
                verdict=metric_verdict(value, lower=0, upper=0),
                evidence=physical_evidence,
            )
        )
    qc_rows.append(
        make_qc_row(
            chain_id=chain_id,
            record_id=record_id,
            stage="npt",
            domain="physical",
            metric="three_ns_exploratory_verdict",
            window_start=0.0,
            window_end=3000.0,
            aggregation="decision",
            value=three_ns_verdict,
            unit="status",
            criterion_id="DEC3NS003",
            criterion_status="PROVISIONAL_3NS_EXPLORATORY",
            verdict=three_ns_verdict,
            evidence=physical_evidence,
        )
    )


def consolidate_one(
    metrics_path: Path,
    next_root: Path,
    environments: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    work = metrics_path.parent
    run_dir = work.parent
    context = run_dir.name
    live_metrics = read_json(metrics_path)
    live_chain_id = require_text(live_metrics, "chain_id", context)
    if live_chain_id != run_dir.name or not ID_PATTERN.fullmatch(live_chain_id):
        raise RegistryError(f"{context}: unsafe or mismatched chain_id {live_chain_id!r}")
    live_chain_start = parse_iso(require_text(live_metrics, "start", context), context)
    manifest = read_json(work / "chain_manifest.json")
    timezone = live_chain_start.tzinfo
    if timezone is None:
        raise RegistryError(f"{context}: timezone unexpectedly missing")
    extension = discover_extension(work, live_chain_id, manifest, timezone)
    if extension is not None:
        metrics_path = extension["base_metrics_path"]
    metrics = read_json(metrics_path)
    if require_text(metrics, "technical_status", context) != "PASS_COMPLETE":
        raise RegistryError(
            f"{context}: finalized metrics are not PASS_COMPLETE; refusing to hide a failed chain"
        )
    chain_id = require_text(metrics, "chain_id", context)
    if chain_id != run_dir.name or not ID_PATTERN.fullmatch(chain_id):
        raise RegistryError(f"{context}: unsafe or mismatched chain_id {chain_id!r}")
    started = validate_attempt_provenance(metrics, work, context)
    chain_start = parse_iso(require_text(metrics, "start", context), context)
    chain_end = parse_iso(require_text(metrics, "end", context), context)
    if chain_end < chain_start:
        raise RegistryError(f"{context}: chain end precedes start")

    hashes = read_json(work / "INPUT_SHA256.json")
    metrics_hashes = require_mapping(metrics, "input_sha256", context)
    manifest_hashes = require_mapping(manifest, "input_sha256", context)
    if hashes != metrics_hashes or hashes != manifest_hashes:
        raise RegistryError(f"{context}: manifest/metrics/INPUT_SHA256 disagree")
    validate_actual_input_hashes(work, hashes)
    if sha256_file(run_dir / "em.gro") != require_text(manifest, "parent_em_sha256", context):
        raise RegistryError(f"{context}: parent EM SHA-256 mismatch")
    if sha256_file(run_dir / "input" / "topol.top") != require_text(
        manifest, "parent_topology_sha256", context
    ):
        raise RegistryError(f"{context}: parent topology SHA-256 mismatch")
    packmol = manifest.get("parent_packmol_provenance")
    if packmol is not None:
        if not isinstance(packmol, dict):
            raise RegistryError(f"{context}: parent Packmol provenance must be an object")
        if metrics.get("parent_packmol_provenance") != packmol:
            raise RegistryError(f"{context}: parent Packmol provenance differs in metrics")
        seed = require_integer(packmol, "packmol_seed", context)
        if not 1 <= seed <= 2_147_483_647:
            raise RegistryError(f"{context}: parent Packmol seed is outside valid range")
        if manifest.get("velocity_seed") != manifest.get("seed"):
            raise RegistryError(f"{context}: manifest velocity seed mismatch")
        if manifest.get("seed_semantics") != "gromacs_nvt_gen_seed":
            raise RegistryError(f"{context}: manifest seed semantics are invalid")
        packmol_paths = {
            "packmol_input_sha256": run_dir / "input" / "pack.inp",
            "packmol_log_sha256": run_dir / "commands.log",
            "packmol_initial_gro_sha256": run_dir / "input" / "initial.gro",
        }
        for key, path in packmol_paths.items():
            if sha256_file(path) != require_text(packmol, key, context):
                raise RegistryError(f"{context}: parent Packmol evidence mismatch for {key}")
        if started is None:
            raise RegistryError(f"{context}: parent Packmol provenance requires attempt evidence")
        if started.get("inherited_packmol_seed") != seed:
            raise RegistryError(f"{context}: attempt inherited Packmol seed mismatch")

    protocol = require_text(manifest, "protocol_version", context)
    dt_ps = require_number(manifest, "dt_ps", context)
    npt_steps = int(require_number(manifest, "npt_steps", context))
    npt_target_ps = require_number(manifest, "npt_ps", context)
    if npt_steps <= 0 or dt_ps <= 0 or not math.isclose(npt_steps * dt_ps, npt_target_ps, abs_tol=1e-6):
        raise RegistryError(f"{context}: NPT manifest duration is inconsistent")
    environment_id = match_environment(
        require_text(manifest, "gromacs_version", context), environments
    )
    system_id = parse_system_id(run_dir)
    if not ID_PATTERN.fullmatch(system_id):
        raise RegistryError(f"{context}: unsafe system_id {system_id!r}")
    bundle_hash = canonical_bundle_sha256(hashes)

    nvt_run = require_mapping(metrics, "nvt", context)
    npt_run = require_mapping(metrics, "npt", context)
    analysis = require_mapping(metrics, "analysis", context)
    bad_markers = require_mapping(metrics, "bad_markers", context)
    grompp_warnings = require_mapping(metrics, "grompp_warnings", context)
    screen_verdict = require_text(analysis, "exploratory_verdict", context)
    if screen_verdict not in SCREEN_VERDICTS:
        raise RegistryError(f"{context}: unknown SCREEN verdict {screen_verdict!r}")
    if metrics.get("physics_status") != "EXPLORATORY_ONLY":
        raise RegistryError(f"{context}: top-level physics_status must remain EXPLORATORY_ONLY")
    if analysis.get("physics_status") != "EXPLORATORY_ONLY":
        raise RegistryError(f"{context}: physics_status must remain EXPLORATORY_ONLY")
    if analysis.get("equilibrium_validated") is not False or analysis.get("production_ready") is not False:
        raise RegistryError(f"{context}: exploratory screen must not claim physical validation")

    base_npt_log = (
        extension["dir"] / "base_snapshot" / "npt.log"
        if extension is not None
        else work / "npt.log"
    )
    native_logs = [work / "nvt.log", base_npt_log]
    console_logs = [work / "nvt_mdrun_console.log", work / "npt_mdrun_console.log"]
    scanned_markers = count_bad_markers([*native_logs, *console_logs])
    for key in ("fatal", "nan", "lincs", "segfault"):
        expected = int(require_number(bad_markers, key, context))
        if expected != 0 or scanned_markers[key] != expected:
            raise RegistryError(
                f"{context}: bad-marker mismatch for {key}: metrics={expected}, scan={scanned_markers[key]}"
            )
    for stage in ("nvt", "npt"):
        expected_warnings = int(require_number(grompp_warnings, stage, context))
        scanned_warnings = warning_count(work / f"grompp_{stage}.log")
        if expected_warnings != 0 or scanned_warnings != expected_warnings:
            raise RegistryError(
                f"{context}: {stage} grompp warning mismatch: metrics={expected_warnings}, scan={scanned_warnings}"
            )

    nvt_started, nvt_ended = parse_stage_times(work / "nvt.log", timezone)
    npt_started, npt_ended = parse_stage_times(base_npt_log, timezone)
    if parse_iso(npt_started, context) < parse_iso(nvt_ended, context):
        raise RegistryError(f"{context}: NPT starts before NVT finishes")

    nvt_artifact = relative_artifact(work, next_root)
    npt_artifact = relative_artifact(
        extension["dir"] / "base_snapshot" if extension is not None else work,
        next_root,
    )
    evidence = relative_artifact(metrics_path, next_root)
    stage_specs = [
        ("nvt", nvt_run, 100000, 100.0, nvt_started, nvt_ended, "EXPLORATORY_ONLY", nvt_artifact),
        ("npt", npt_run, npt_steps, npt_target_ps, npt_started, npt_ended, "EXPLORATORY_ONLY", npt_artifact),
    ]
    chain_rows: list[dict[str, Any]] = []
    record_ids: dict[str, str] = {}
    for stage, run, target_steps, target_ps, started, ended, physics, artifact in stage_specs:
        first_time = require_number(run, "first_time_ps", f"{context}:{stage}")
        last_time = require_number(run, "last_time_ps", f"{context}:{stage}")
        duration = require_number(run, "duration_ps", f"{context}:{stage}")
        if not math.isclose(last_time - first_time, duration, abs_tol=1e-6):
            raise RegistryError(f"{context}:{stage}: time range and duration disagree")
        if duration + 1e-6 < target_ps:
            raise RegistryError(f"{context}:{stage}: duration is shorter than target")
        last_step = int(round(duration / dt_ps))
        if last_step < target_steps:
            raise RegistryError(f"{context}:{stage}: last step is shorter than target")
        record_id = f"{chain_id}:{stage}:001"
        record_ids[stage] = record_id
        resumed = run.get("resumed")
        checkpoint_in_sha256 = validate_stage_resume_provenance(
            run, stage, work, context
        )
        chain_rows.append(
            {
                "record_id": record_id,
                "chain_id": chain_id,
                "system_id": system_id,
                "protocol_version": protocol,
                "stage": stage,
                "segment_no": 1,
                "mode": "RESUME" if resumed else "START",
                "parent_record_id": "" if stage == "nvt" else record_ids["nvt"],
                "input_sha256": bundle_hash,
                "checkpoint_in_sha256": checkpoint_in_sha256,
                "environment_id": environment_id,
                "start_at": started,
                "end_at": ended,
                "start_step": 0,
                "target_step": target_steps,
                "last_step": last_step,
                "exit_code": 0,
                "termination_reason": "COMPLETED",
                "tech_status": "PASS_COMPLETE",
                "physics_status": physics,
                "artifact_path": artifact,
            }
        )

    qc_rows: list[dict[str, str]] = []
    for stage in ("nvt", "npt"):
        record_id = record_ids[stage]
        warnings = int(require_number(grompp_warnings, stage, context))
        qc_rows.append(
            make_qc_row(
                chain_id=chain_id,
                record_id=record_id,
                stage=stage,
                domain="technical",
                metric="grompp_warnings",
                window_start="",
                window_end="",
                aggregation="count",
                value=warnings,
                unit="count",
                criterion_id="TECH001",
                criterion_status="PROVISIONAL_EXPLORATORY",
                verdict=metric_verdict(warnings, lower=0, upper=0),
                evidence=relative_artifact(work / f"grompp_{stage}.log", next_root),
            )
        )
        run = nvt_run if stage == "nvt" else npt_run
        target_ps = 100.0 if stage == "nvt" else npt_target_ps
        duration = require_number(run, "duration_ps", f"{context}:{stage}")
        qc_rows.append(
            make_qc_row(
                chain_id=chain_id,
                record_id=record_ids[stage],
                stage=stage,
                domain="technical",
                metric="stage_duration",
                window_start=require_number(run, "first_time_ps", f"{context}:{stage}"),
                window_end=require_number(run, "last_time_ps", f"{context}:{stage}"),
                aggregation="range",
                value=duration,
                unit="ps",
                criterion_id="TECH006",
                criterion_status="PROVISIONAL_EXPLORATORY",
                verdict=metric_verdict(duration, lower=target_ps),
                evidence=evidence,
            )
        )
    marker_specs = [
        ("fatal_error", "fatal", "TECH002"),
        ("nan_count", "nan", "TECH003"),
        ("lincs_warning", "lincs", "TECH004"),
        ("segmentation_fault", "segfault", "TECH005"),
    ]
    for metric, key, criterion in marker_specs:
        value = int(require_number(bad_markers, key, context))
        qc_rows.append(
            make_qc_row(
                chain_id=chain_id,
                record_id=record_ids["npt"],
                stage="all",
                domain="technical",
                metric=metric,
                window_start="",
                window_end="",
                aggregation="count",
                value=value,
                unit="count",
                criterion_id=criterion,
                criterion_status="PROVISIONAL_EXPLORATORY",
                verdict=metric_verdict(value, lower=0, upper=0),
                evidence=evidence,
            )
        )

    nvt_summary = require_mapping(analysis, "nvt_last_50ps", context)
    nvt_temp = require_mapping(nvt_summary, "Temperature", context)
    npt_summary = require_mapping(analysis, "npt_last_500ps", context)
    npt_temp = require_mapping(npt_summary, "Temperature", context)
    npt_density = require_mapping(npt_summary, "Density", context)
    nvt_last = require_number(nvt_run, "last_time_ps", context)
    npt_last = require_number(npt_run, "last_time_ps", context)
    nvt_window = (max(require_number(nvt_run, "first_time_ps", context), nvt_last - 50.0), nvt_last)
    npt_window = (max(require_number(npt_run, "first_time_ps", context), npt_last - 500.0), npt_last)

    physical_specs = [
        ("nvt", "nvt_min_box_over_2rlist", "min", require_number(analysis, "nvt_min_box_over_2rlist", context), "ratio", "SCR001", "PROVISIONAL_EXPLORATORY", 1.10, None, (require_number(nvt_run, "first_time_ps", context), nvt_last)),
        ("npt", "npt_min_box_over_2rlist", "min", require_number(analysis, "npt_min_box_over_2rlist", context), "ratio", "SCR002", "PROVISIONAL_EXPLORATORY", 1.10, None, (require_number(npt_run, "first_time_ps", context), npt_last)),
        ("nvt", "temperature_mean", "mean", require_number(nvt_temp, "mean", context), "K", "SCR003", "PROVISIONAL_EXPLORATORY", 293.0, 303.0, nvt_window),
        ("nvt", "absolute_temperature_slope_per_ns", "absolute_slope", abs(require_number(nvt_temp, "slope_per_ns", context)), "K_per_ns", "SCR009", "PROVISIONAL_EXPLORATORY", 0.0, 2.0, nvt_window),
        ("nvt", "temperature_last_two_block_diff", "absolute_difference", require_number(nvt_summary, "last_two_temperature_block_diff_K", context), "K", "SCR010", "PROVISIONAL_EXPLORATORY", 0.0, 3.0, nvt_window),
        ("npt", "density_mean", "mean", require_number(npt_density, "mean", context), "kg_m3", "OBS005", "PROVISIONAL_EXPLORATORY", None, None, npt_window),
        ("npt", "density_slope_percent_per_ns", "slope", require_number(analysis, "density_slope_percent_per_ns", context), "percent_per_ns", "SCR006", "PROVISIONAL_EXPLORATORY", 0.0, 1.0, npt_window),
        ("npt", "density_last_two_block_diff_percent", "symmetric_difference", require_number(analysis, "density_last_two_block_diff_percent", context), "percent", "SCR007", "PROVISIONAL_EXPLORATORY", 0.0, 1.0, npt_window),
        ("npt", "density_max_adjacent_block_diff_percent", "max_symmetric_difference", require_number(analysis, "density_max_adjacent_block_diff_percent", context), "percent", "SCR008", "PROVISIONAL_EXPLORATORY", 0.0, 2.0, npt_window),
        ("npt", "density_first_vs_second_250ps_diff_percent", "symmetric_difference", require_number(analysis, "density_first_vs_second_250ps_diff_percent", context), "percent", "OBS001", "PROVISIONAL_EXPLORATORY", None, None, npt_window),
        ("npt", "max_adjacent_volume_jump_percent", "max_relative_jump", require_number(analysis, "max_adjacent_volume_jump_percent", context), "percent", "SCR005", "PROVISIONAL_EXPLORATORY", 0.0, 5.0, (require_number(npt_run, "first_time_ps", context), npt_last)),
        ("npt", "temperature_mean", "mean", require_number(npt_temp, "mean", context), "K", "SCR004", "PROVISIONAL_EXPLORATORY", 293.0, 303.0, npt_window),
        ("npt", "absolute_temperature_slope_per_ns", "absolute_slope", abs(require_number(npt_temp, "slope_per_ns", context)), "K_per_ns", "SCR011", "PROVISIONAL_EXPLORATORY", 0.0, 2.0, npt_window),
    ]
    for stage, metric, aggregation, value, unit, criterion, criterion_status, lower, upper, metric_window in physical_specs:
        if lower is None and upper is None:
            verdict = "NOT_EVALUATED"
        else:
            passed = metric_verdict(value, lower=lower, upper=upper) == "PASS"
            if passed:
                verdict = "PASS"
            elif criterion in {"SCR001", "SCR002"}:
                verdict = "SCREEN_FAIL" if value <= 1.0 else "SCREEN_EXTEND"
            elif criterion in {"SCR003", "SCR004", "SCR005"}:
                verdict = "SCREEN_FAIL"
            else:
                verdict = "SCREEN_EXTEND"
        qc_rows.append(
            make_qc_row(
                chain_id=chain_id,
                record_id=record_ids[stage],
                stage=stage,
                domain="physical",
                metric=metric,
                window_start=metric_window[0],
                window_end=metric_window[1],
                aggregation=aggregation,
                value=value,
                unit=unit,
                criterion_id=criterion,
                criterion_status=criterion_status,
                verdict=verdict,
                evidence=evidence,
            )
        )
    hard_fail_reasons = analysis.get("hard_fail_reasons")
    if not isinstance(hard_fail_reasons, list) or not all(isinstance(value, str) for value in hard_fail_reasons):
        raise RegistryError(f"{context}: hard_fail_reasons must be a string list")
    qc_rows.append(
        make_qc_row(
            chain_id=chain_id,
            record_id=record_ids["npt"],
            stage="npt",
            domain="physical",
            metric="screen_hard_fail_reason_count",
            window_start=npt_window[0],
            window_end=npt_window[1],
            aggregation="count",
            value=len(hard_fail_reasons),
            unit="count",
            criterion_id="DEC001",
            criterion_status="PROVISIONAL_EXPLORATORY",
            verdict=metric_verdict(len(hard_fail_reasons), lower=0, upper=0),
            evidence=evidence,
        )
    )
    qc_rows.append(
        make_qc_row(
            chain_id=chain_id,
            record_id=record_ids["npt"],
            stage="npt",
            domain="physical",
            metric="screen_verdict",
            window_start=npt_window[0],
            window_end=npt_window[1],
            aggregation="decision",
            value=screen_verdict,
            unit="status",
            criterion_id="DEC002",
            criterion_status="PROVISIONAL_EXPLORATORY",
            verdict=screen_verdict,
            evidence=evidence,
        )
    )
    if extension is not None:
        append_extension_record(
            extension,
            chain_rows,
            qc_rows,
            next_root,
            system_id,
            environment_id,
        )
    return chain_rows, qc_rows


def validate_rows(chain_rows: list[dict[str, Any]], qc_rows: list[dict[str, str]]) -> None:
    record_ids: set[str] = set()
    chain_stage_keys: set[tuple[str, str, int]] = set()
    for row in chain_rows:
        record_id = str(row["record_id"])
        if record_id in record_ids:
            raise RegistryError(f"duplicate record_id: {record_id}")
        record_ids.add(record_id)
        key = (str(row["chain_id"]), str(row["stage"]), int(row["segment_no"]))
        if key in chain_stage_keys:
            raise RegistryError(f"duplicate chain/stage/segment: {key}")
        chain_stage_keys.add(key)
    for row in chain_rows:
        parent = str(row["parent_record_id"])
        if parent and parent not in record_ids:
            raise RegistryError(f"missing parent_record_id: {parent}")
        if parent:
            parent_row = next(candidate for candidate in chain_rows if candidate["record_id"] == parent)
            if parent_row["chain_id"] != row["chain_id"]:
                raise RegistryError(f"cross-chain parent reference: {row['record_id']} -> {parent}")
            if row["mode"] == "EXTEND":
                if row["stage"] != parent_row["stage"]:
                    raise RegistryError(
                        f"extension stage differs from parent: {row['record_id']} -> {parent}"
                    )
                if int(row["segment_no"]) != int(parent_row["segment_no"]) + 1:
                    raise RegistryError(f"extension segment sequence is broken: {row['record_id']}")
                if int(row["start_step"]) != int(parent_row["last_step"]):
                    raise RegistryError(f"extension step continuity is broken: {row['record_id']}")
                if not str(row["checkpoint_in_sha256"]):
                    raise RegistryError(f"extension checkpoint evidence is missing: {row['record_id']}")
                if int(row["last_step"]) != int(row["target_step"]):
                    raise RegistryError(f"completed extension did not reach its segment target: {row['record_id']}")
    qc_keys: set[tuple[str, str, str, str, str]] = set()
    for row in qc_rows:
        if row["record_id"] not in record_ids:
            raise RegistryError(f"QC row references missing record_id: {row['record_id']}")
        key = (
            row["record_id"],
            row["metric"],
            row["window_start_ps"],
            row["window_end_ps"],
            row["aggregation"],
        )
        if key in qc_keys:
            raise RegistryError(f"duplicate QC key: {key}")
        qc_keys.add(key)


def check_existing_header(path: Path, expected: list[str]) -> None:
    if not path.exists():
        return
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
    if header != expected:
        raise RegistryError(f"refusing to replace registry with unexpected header: {path}")


def atomic_replace_pair(
    chain_path: Path,
    chain_content: str,
    qc_path: Path,
    qc_content: str,
    lock_path: Path,
    audit_path: Path | None = None,
    audit_content: str | None = None,
) -> None:
    if (audit_path is None) != (audit_content is None):
        raise RegistryError("audit_path and audit_content must be provided together")
    chain_path.parent.mkdir(parents=True, exist_ok=True)
    qc_path.parent.mkdir(parents=True, exist_ok=True)
    if audit_path is not None:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        check_existing_header(chain_path, CHAIN_FIELDS)
        check_existing_header(qc_path, QC_FIELDS)
        if audit_path is not None and audit_path.exists():
            existing_audit = read_json(audit_path)
            if existing_audit.get("schema_version") != "registry-quarantine-audit-v1":
                raise RegistryError(f"refusing to replace unexpected audit file: {audit_path}")
        destinations = [(chain_path, chain_content), (qc_path, qc_content)]
        if audit_path is not None and audit_content is not None:
            destinations.append((audit_path, audit_content))
        temporary_paths: list[Path] = []
        try:
            for destination, content in destinations:
                descriptor, temporary_name = tempfile.mkstemp(
                    prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
                )
                temporary = Path(temporary_name)
                temporary_paths.append(temporary)
                with os.fdopen(descriptor, "w", newline="") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
            for temporary, (destination, _) in zip(temporary_paths, destinations):
                os.replace(temporary, destination)
            temporary_paths.clear()
        finally:
            for temporary in temporary_paths:
                temporary.unlink(missing_ok=True)


def read_quarantine_entries(next_root: Path) -> tuple[list[dict[str, Any]], str]:
    config_path = next_root / QUARANTINE_CONFIG_RELATIVE
    if not config_path.exists():
        return [], ""
    document = read_json(config_path)
    if set(document) != {"schema_version", "entries"}:
        raise RegistryError("quarantine config has unexpected top-level fields")
    if document.get("schema_version") != QUARANTINE_SCHEMA:
        raise RegistryError("quarantine config schema_version is invalid")
    raw_entries = document.get("entries")
    if not isinstance(raw_entries, list):
        raise RegistryError("quarantine entries must be a list")
    entries: list[dict[str, Any]] = []
    quarantined_ids: set[str] = set()
    replacement_ids: set[str] = set()
    expected_fields = {
        "chain_id",
        "reason_code",
        "reason",
        "replacement_chain_id",
        "evidence_sha256",
    }
    runs_root = next_root / "04_Runs"
    for index, raw in enumerate(raw_entries):
        context = f"quarantine entry {index + 1}"
        if not isinstance(raw, dict) or set(raw) != expected_fields:
            raise RegistryError(f"{context}: fields must be exactly {sorted(expected_fields)}")
        chain_id = require_text(raw, "chain_id", context)
        replacement_id = require_text(raw, "replacement_chain_id", context)
        if not ID_PATTERN.fullmatch(chain_id) or not ID_PATTERN.fullmatch(replacement_id):
            raise RegistryError(f"{context}: chain IDs contain unsafe characters")
        if chain_id == replacement_id:
            raise RegistryError(f"{context}: replacement must be a different chain")
        if chain_id in quarantined_ids:
            raise RegistryError(f"{context}: duplicate quarantined chain {chain_id}")
        if replacement_id in replacement_ids:
            raise RegistryError(f"{context}: replacement chain is reused {replacement_id}")
        if raw.get("reason_code") != QUARANTINE_REASON:
            raise RegistryError(f"{context}: unsupported quarantine reason_code")
        reason = require_text(raw, "reason", context)
        normalized_reason = reason.lower().replace("-", "")
        if "checkpoint" not in normalized_reason or "sha256" not in normalized_reason:
            raise RegistryError(f"{context}: reason must state the checkpoint SHA-256 defect")
        evidence = require_mapping(raw, "evidence_sha256", context)
        if set(evidence) != QUARANTINE_EVIDENCE_FILES:
            raise RegistryError(f"{context}: evidence file set is incomplete or expanded")
        run_dir = runs_root / chain_id
        if not run_dir.is_dir():
            raise RegistryError(f"{context}: quarantined run directory is missing")
        for relative_name in sorted(QUARANTINE_EVIDENCE_FILES):
            expected_hash = evidence.get(relative_name)
            if not isinstance(expected_hash, str) or not re.fullmatch(
                r"[0-9a-f]{64}", expected_hash
            ):
                raise RegistryError(f"{context}: invalid SHA-256 for {relative_name}")
            actual_hash = sha256_file(run_dir / relative_name)
            if actual_hash != expected_hash:
                raise RegistryError(
                    f"{context}: evidence SHA-256 mismatch for {chain_id}/{relative_name}"
                )
        metrics = read_json(run_dir / "equilibration" / "equilibration_metrics.json")
        npt = require_mapping(metrics, "npt", context)
        if metrics.get("chain_id") != chain_id or npt.get("resumed") is not True:
            raise RegistryError(f"{context}: chain is not the identified resumed NPT record")
        if npt.get("checkpoint_in_sha256"):
            raise RegistryError(
                f"{context}: chain now has checkpoint provenance; quarantine reason is stale"
            )
        safety = read_json(
            run_dir / "equilibration" / "safety_thread_reduction_record.json"
        )
        require_exact(
            safety,
            {
                "chain_id": chain_id,
                "technical_status": "INTERRUPTED_BY_SAFETY_POLICY_CHANGE",
                "resume_command_mode": "gmx mdrun -cpi npt.cpt -append",
            },
            f"{context}:safety record",
        )
        quarantined_ids.add(chain_id)
        replacement_ids.add(replacement_id)
        entries.append(dict(raw))
    if quarantined_ids & replacement_ids:
        raise RegistryError("a replacement chain cannot itself be quarantined")
    return entries, sha256_file(config_path)


def validate_replacement_equivalence(
    next_root: Path,
    entry: dict[str, Any],
    chain_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    runs_root = next_root / "04_Runs"
    chain_id = str(entry["chain_id"])
    replacement_id = str(entry["replacement_chain_id"])
    original_dir = runs_root / chain_id
    replacement_dir = runs_root / replacement_id
    replacement_metrics_path = replacement_dir / "equilibration" / "equilibration_metrics.json"
    if not replacement_metrics_path.is_file():
        raise RegistryError(
            f"quarantine replacement incomplete: {replacement_id} has no finalized "
            "equilibration_metrics.json"
        )
    replacement_records = [
        str(row["record_id"]) for row in chain_rows if row["chain_id"] == replacement_id
    ]
    if not replacement_records:
        raise RegistryError(
            f"quarantine replacement was not fully consolidated: {replacement_id}"
        )
    original_manifest_path = original_dir / "equilibration" / "chain_manifest.json"
    replacement_manifest_path = replacement_dir / "equilibration" / "chain_manifest.json"
    original_manifest = read_json(original_manifest_path)
    replacement_manifest = read_json(replacement_manifest_path)
    for key in (
        "protocol_version",
        "seed",
        "npt_ps",
        "npt_steps",
        "dt_ps",
        "parent_topology_sha256",
        "gromacs_version",
    ):
        if original_manifest.get(key) != replacement_manifest.get(key):
            raise RegistryError(
                f"quarantine replacement protocol mismatch for {key}: {replacement_id}"
            )
    original_inputs = require_mapping(original_manifest, "input_sha256", chain_id)
    replacement_inputs = require_mapping(replacement_manifest, "input_sha256", replacement_id)
    comparable_original = {
        name: value for name, value in original_inputs.items() if name != "start_em.gro"
    }
    comparable_replacement = {
        name: value for name, value in replacement_inputs.items() if name != "start_em.gro"
    }
    if comparable_original != comparable_replacement:
        raise RegistryError(f"quarantine replacement input protocol hashes differ: {replacement_id}")
    if parse_system_id(original_dir) != parse_system_id(replacement_dir):
        raise RegistryError(f"quarantine replacement system_id differs: {replacement_id}")
    original_parent = read_json(original_dir / "metrics.json")
    replacement_parent = read_json(replacement_dir / "metrics.json")
    original_density = require_number(original_parent, "initial_density_kg_m3", chain_id)
    replacement_density = require_number(
        replacement_parent, "initial_density_kg_m3", replacement_id
    )
    if not math.isclose(original_density, replacement_density, rel_tol=0.0, abs_tol=1e-9):
        raise RegistryError(f"quarantine replacement initial density differs: {replacement_id}")
    replacement_metrics = read_json(replacement_metrics_path)
    if replacement_metrics.get("chain_id") != replacement_id:
        raise RegistryError(f"quarantine replacement metrics chain_id differs: {replacement_id}")
    return {
        "chain_id": chain_id,
        "reason_code": entry["reason_code"],
        "reason": entry["reason"],
        "status": "ACTIVE_REPLACED",
        "evidence_sha256": entry["evidence_sha256"],
        "replacement_chain_id": replacement_id,
        "replacement_chain_manifest_sha256": sha256_file(replacement_manifest_path),
        "replacement_metrics_sha256": sha256_file(replacement_metrics_path),
        "replacement_record_ids": sorted(replacement_records),
    }


def render_quarantine_audit(config_sha256: str, entries: list[dict[str, Any]]) -> str:
    payload = {
        "schema_version": "registry-quarantine-audit-v1",
        "generated_by": SCRIPT_NAME,
        "quarantine_config_sha256": config_sha256,
        "active_exclusions": sorted(entries, key=lambda item: item["chain_id"]),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def build_registries(
    next_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[str], str]:
    runs_root = next_root / "04_Runs"
    environments = read_environment_map(next_root / "03_Environments" / "environment_registry.csv")
    quarantine_entries, quarantine_config_sha = read_quarantine_entries(next_root)
    quarantined_ids = {str(entry["chain_id"]) for entry in quarantine_entries}
    chain_rows: list[dict[str, Any]] = []
    qc_rows: list[dict[str, str]] = []
    metrics_paths = sorted(runs_root.glob("*/equilibration/equilibration_metrics.json"))
    incomplete = sorted(
        path.parent.name
        for path in runs_root.glob("*/equilibration")
        if not (path / "equilibration_metrics.json").is_file()
    )
    if not metrics_paths:
        raise RegistryError("no finalized equilibration_metrics.json files were found")
    for metrics_path in metrics_paths:
        if metrics_path.parent.parent.name in quarantined_ids:
            continue
        new_chain_rows, new_qc_rows = consolidate_one(metrics_path, next_root, environments)
        chain_rows.extend(new_chain_rows)
        qc_rows.extend(new_qc_rows)
    chain_rows.sort(
        key=lambda row: (
            row["chain_id"],
            STAGE_ORDER.get(str(row["stage"]), 99),
            int(row["segment_no"]),
            row["record_id"],
        )
    )
    qc_rows.sort(
        key=lambda row: (
            row["chain_id"],
            STAGE_ORDER.get(row["stage"], 99),
            row["record_id"],
            row["metric"],
            row["window_start_ps"],
            row["aggregation"],
        )
    )
    validate_rows(chain_rows, qc_rows)
    discovered_ids = {path.parent.parent.name for path in metrics_paths}
    hidden = quarantined_ids - discovered_ids
    if hidden:
        raise RegistryError(f"quarantine references undiscovered metrics chains: {sorted(hidden)}")
    active_quarantine = [
        validate_replacement_equivalence(next_root, entry, chain_rows)
        for entry in quarantine_entries
    ]
    audit = render_quarantine_audit(quarantine_config_sha, active_quarantine)
    return chain_rows, qc_rows, incomplete, audit


def create_self_test_fixture(root: Path) -> Path:
    next_root = root / "08_Next_Research"
    run_dir = next_root / "04_Runs" / "screen_L1P1x2_rho1000_TEST"
    work = run_dir / "equilibration"
    (run_dir / "input").mkdir(parents=True)
    work.mkdir(parents=True)
    (next_root / "03_Environments").mkdir(parents=True)
    (next_root / "03_Environments" / "environment_registry.csv").write_text(
        "environment_id,host_class,os,gromacs_version,precision,mpi,gpu,scheduler,command_profile,verification_level\n"
        "test_env,test,test,2026.3-Test,mixed,thread_mpi,disabled,none,gmx,test\n"
    )
    (run_dir / "RUN_RECORD.md").write_text("- System: L1P1x2 = test\n")
    (run_dir / "metrics.json").write_text(
        json.dumps({"initial_density_kg_m3": 1000.0}) + "\n"
    )
    (run_dir / "em.gro").write_text("em\n")
    (run_dir / "input" / "topol.top").write_text("topology\n")
    inputs = {
        "start_em.gro": "em\n",
        "topol.top": "topology\n",
        "nvt_100ps.mdp": "nsteps = 100000\n",
        "npt_1000ps.mdp": "nsteps = 1000000\n",
    }
    for name, content in inputs.items():
        (work / name).write_text(content)
    hashes = {name: sha256_file(work / name) for name in inputs}
    (work / "INPUT_SHA256.json").write_text(json.dumps(hashes, indent=2) + "\n")
    manifest = {
        "protocol_version": "eq-screen-v2",
        "seed": 1,
        "npt_ps": 1000.0,
        "npt_steps": 1000000,
        "dt_ps": 0.001,
        "input_sha256": hashes,
        "parent_em_sha256": sha256_file(run_dir / "em.gro"),
        "parent_topology_sha256": sha256_file(run_dir / "input" / "topol.top"),
        "gromacs_version": "GROMACS version: 2026.3-Test",
    }
    (work / "chain_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for stage, started, finished in (
        ("nvt", "Fri Aug  7 00:00:00 2026", "Fri Aug  7 00:01:00 2026"),
        ("npt", "Fri Aug  7 00:01:01 2026", "Fri Aug  7 00:11:00 2026"),
    ):
        (work / f"{stage}.log").write_text(
            f"Started mdrun on rank 0 {started}\nFinished mdrun on rank 0 {finished}\n"
        )
        (work / f"{stage}_mdrun_console.log").write_text("completed\n")
        (work / f"grompp_{stage}.log").write_text("There were 0 notes\n")
    analysis = {
        "nvt_last_50ps": {
            "Temperature": {"mean": 298.1, "slope_per_ns": 0.2},
            "last_two_temperature_block_diff_K": 0.5,
        },
        "npt_last_500ps": {
            "Density": {"mean": 1395.0},
            "Temperature": {"mean": 298.2, "slope_per_ns": -0.1},
        },
        "density_slope_percent_per_ns": 0.4,
        "density_last_two_block_diff_percent": 0.3,
        "density_max_adjacent_block_diff_percent": 0.8,
        "density_first_vs_second_250ps_diff_percent": 0.6,
        "max_adjacent_volume_jump_percent": 0.4,
        "nvt_min_box_over_2rlist": 1.20,
        "npt_min_box_over_2rlist": 1.15,
        "hard_fail_reasons": [],
        "exploratory_verdict": "SCREEN_STATIONARITY_PASS",
        "physics_status": "EXPLORATORY_ONLY",
        "equilibrium_validated": False,
        "production_ready": False,
    }
    metrics = {
        "chain_id": run_dir.name,
        "start": "2026-08-07T00:00:00+09:00",
        "end": "2026-08-07T00:11:01+09:00",
        "technical_status": "PASS_COMPLETE",
        "physics_status": "EXPLORATORY_ONLY",
        "detail": "self-test",
        "nvt": {"resumed": False, "first_time_ps": 0.0, "last_time_ps": 100.0, "duration_ps": 100.0},
        "npt": {"resumed": False, "first_time_ps": 0.0, "last_time_ps": 1000.0, "duration_ps": 1000.0},
        "bad_markers": {"fatal": 0, "nan": 0, "lincs": 0, "segfault": 0},
        "grompp_warnings": {"nvt": 0, "npt": 0},
        "analysis": analysis,
        "input_sha256": hashes,
    }
    (work / "equilibration_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    create_self_test_extension(work)
    create_self_test_quarantine(next_root, run_dir)
    return next_root


def write_test_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def create_self_test_extension(work: Path) -> None:
    chain_id = work.parent.name
    extension_dir = work / "extensions" / EXTENSION_ID
    snapshot = extension_dir / "base_snapshot"
    snapshot.mkdir(parents=True)
    canonical_base_edr = b"base-edr-0-999\n"
    base_log_prefix = (
        "Started mdrun on rank 0 Fri Aug  7 00:01:01 2026\n"
        "Writing checkpoint, step 1000000 at Fri Aug  7 00:10:59 2026\n\n"
    )
    base_artifacts = {
        "npt.tpr": b"base-tpr\n",
        "npt.cpt": b"base-checkpoint\n",
        "npt.edr": canonical_base_edr + b"base-boundary-frame-1000\n",
        "npt.xtc": b"base-xtc-0-1000\n",
        "npt.gro": b"base-gro\n",
    }
    for name, content in base_artifacts.items():
        (work / name).write_bytes(content)
    (work / "npt.log").write_text(
        base_log_prefix
        + "Energy conservation and performance summary\n"
        + "Finished mdrun on rank 0 Fri Aug  7 00:11:00 2026\n"
    )
    for name in BASE_SNAPSHOT_FILES:
        (snapshot / name).write_bytes((work / name).read_bytes())

    (work / "npt.edr").write_bytes(
        canonical_base_edr
        + b"restart-boundary-frame-1000\n"
        + b"extension-edr-1001-3000\n"
    )
    (work / "npt.xtc").write_bytes((snapshot / "npt.xtc").read_bytes() + b"extension-xtc-1000-3000\n")
    (work / "npt.log").write_text(
        base_log_prefix
        + (
            "Reading checkpoint file npt.cpt\n"
            "Restarting from checkpoint, appending to previous log file.\n"
            "Started mdrun on rank 0 Fri Aug  7 00:12:00 2026\n"
            "Finished mdrun on rank 0 Fri Aug  7 00:32:00 2026\n"
        )
    )
    (work / "npt.cpt").write_bytes(b"extended-checkpoint\n")
    (work / "npt.gro").write_bytes(b"extended-gro\n")
    extended_tpr = extension_dir / f"{EXTENSION_ID}.tpr"
    extended_tpr.write_bytes(b"extended-tpr-3000000\n")

    snapshot_evidence = {
        name: file_evidence(snapshot / name) for name in sorted(BASE_SNAPSHOT_FILES)
    }
    chain_manifest = read_json(work / "chain_manifest.json")
    manifest = {
        "schema_version": EXTENSION_SCHEMA,
        "extension_id": EXTENSION_ID,
        "chain_id": chain_id,
        "record_id": f"{chain_id}:npt:002",
        "record_label": "npt:002",
        "parent_record_id": f"{chain_id}:npt:001",
        "parent_record_label": "npt:001",
        "stage": "npt",
        "segment_no": 2,
        "mode": "EXTEND",
        "created_at": "2026-08-07T00:11:30+09:00",
        "start_step": BASE_NPT_STEPS,
        "target_step": EXTENSION_NPT_STEPS,
        "target_step_semantics": "extension segment length; cumulative target is target_total_steps",
        "base_steps": BASE_NPT_STEPS,
        "extension_steps": EXTENSION_NPT_STEPS,
        "target_total_steps": TARGET_TOTAL_NPT_STEPS,
        "dt_ps": 0.001,
        "base_duration_ps": BASE_NPT_DURATION_PS,
        "extension_duration_ps": EXTENSION_NPT_DURATION_PS,
        "target_total_duration_ps": TARGET_TOTAL_NPT_DURATION_PS,
        "base_edr_range_ps": {"first": 0.0, "last": 1000.0, "duration": 1000.0},
        "expected_final_edr_last_ps": 3000.0,
        "base_finished_mdrun_markers": 1,
        "base_tpr_shape": {"nsteps": 1000000, "dt_ps": 0.001, "init_step": 0, "tinit_ps": 0.0},
        "extended_tpr_shape": {"nsteps": 3000000, "dt_ps": 0.001, "init_step": 0, "tinit_ps": 0.0},
        "extended_tpr_path": f"{EXTENSION_ID}.tpr",
        "extended_tpr_sha256": sha256_file(extended_tpr),
        "output_prefix": "npt",
        "checkpoint_in_sha256": snapshot_evidence["npt.cpt"]["sha256"],
        "base_snapshot": snapshot_evidence,
        "base_snapshot_path": "base_snapshot",
        "base_metrics_sha256": snapshot_evidence["equilibration_metrics.json"]["sha256"],
        "chain_manifest_sha256": sha256_file(work / "chain_manifest.json"),
        "gmx_bin": "/test/gmx",
        "gromacs_version": chain_manifest["gromacs_version"],
        "allowed_threads": [6, 7, 8],
    }
    manifest_path = extension_dir / "extension_manifest.json"
    write_test_json(manifest_path, manifest)

    post_evidence = {
        name: file_evidence(extension_dir / name if name == f"{EXTENSION_ID}.tpr" else work / name)
        for name in sorted(POST_EXTENSION_FILES)
    }
    extension_metrics = {
        "schema_version": EXTENSION_SCHEMA,
        "extension_id": EXTENSION_ID,
        "chain_id": chain_id,
        "record_id": f"{chain_id}:npt:002",
        "parent_record_id": f"{chain_id}:npt:001",
        "stage": "npt",
        "segment_no": 2,
        "mode": "EXTEND",
        "start_step": BASE_NPT_STEPS,
        "target_step": EXTENSION_NPT_STEPS,
        "base_steps": BASE_NPT_STEPS,
        "extension_steps": EXTENSION_NPT_STEPS,
        "target_total_steps": TARGET_TOTAL_NPT_STEPS,
        "technical_status": "PASS_COMPLETE",
        "physics_status": "NOT_EVALUATED_AFTER_EXTENSION",
        "analysis_status": "PENDING_EXTENSION_REANALYSIS",
        "completion_mode": "RESUME_OBSERVED_COMPLETE",
        "completion_attempt": None,
        "completed_at": "2026-08-07T00:32:01+09:00",
        "edr_range_ps": {
            "first": 0.0,
            "last": 3000.0,
            "duration": 3000.0,
            "base_duration": 1000.0,
            "extension_duration": 2000.0,
            "target_total_duration": 3000.0,
        },
        "finished_mdrun_markers": 1,
        "append_validation": {
            "xtc": {
                "mode": "full_byte_prefix",
                "base_size_bytes": snapshot_evidence["npt.xtc"]["size_bytes"],
                "base_sha256": snapshot_evidence["npt.xtc"]["sha256"],
            },
            "edr": {
                "mode": "exact_pre_boundary_plus_gromacs_boundary_comparison",
                "energy_terms_compared": 45,
                "base_frames": 1001,
                "live_frames": 3001,
                "frame_cadence_ps": 1.0,
                "exact_pre_boundary_last_ps": 999.0,
                "canonical_pre_boundary_sha256": hashlib.sha256(
                    canonical_base_edr
                ).hexdigest(),
                "canonical_pre_boundary_size_bytes": len(canonical_base_edr),
                "boundary_ps": 1000.0,
                "boundary_comparison": (
                    "gmx_check_native_default_tolerance_no_mismatch_lines"
                ),
            },
            "log": {
                "mode": "checkpoint_restart_append_sequence",
                "base_snapshot_finished_mdrun_markers": 1,
                "live_finished_mdrun_markers": 1,
                "restart_append_markers": 1,
                "bad_markers": {"fatal": 0, "nan": 0, "lincs": 0, "segfault": 0},
            },
        },
        "checkpoint_in_sha256": manifest["checkpoint_in_sha256"],
        "extension_manifest_sha256": sha256_file(manifest_path),
        "post_extension_sha256": post_evidence,
        "base_analysis_preserved_at": "base_snapshot/equilibration_metrics.json",
        "not_verified": ["stationarity after extension"],
    }
    metrics_path = extension_dir / "extension_metrics.json"
    write_test_json(metrics_path, extension_metrics)

    source_evidence = {
        "extension_manifest.json": file_evidence(manifest_path),
        "extension_metrics.json": file_evidence(metrics_path),
        "npt.edr": file_evidence(work / "npt.edr"),
        f"{EXTENSION_ID}.tpr": file_evidence(extended_tpr),
    }
    extension_analysis = {
        "schema_version": "npt-extension-analysis-v1",
        "extension_id": EXTENSION_ID,
        "chain_id": chain_id,
        "record_id": f"{chain_id}:npt:002",
        "generated_at": "2026-08-07T00:33:00+09:00",
        "technical_status": "PASS_COMPLETE",
        "analysis_status": "PASS_COMPLETE",
        "source_evidence": source_evidence,
        "gromacs": {"executable": "/test/gmx", "version": chain_manifest["gromacs_version"]},
        "edr_range_ps": {"first": 0.0, "last": 3000.0, "duration": 3000.0, "rows": 3001},
        "analysis_window_ps": {"start": 2000.0, "end": 3000.0},
        "comparison_windows_ps": {
            "earlier": {"start": 1000.0, "end_exclusive": 2000.0},
            "final": {"start": 2000.0, "end_inclusive": 3000.0},
        },
        "block_definition": {
            "count": 5,
            "width_ps": 200.0,
            "window_start_ps": 2000.0,
            "window_end_ps": 3000.0,
        },
        "last_1ns": {
            "Density": {"n": 1001, "mean": 1395.0, "std": 1.0, "min": 1392.0, "max": 1398.0, "slope_per_ns": 0.1},
            "Temperature": {"n": 1001, "mean": 298.2, "std": 0.5, "min": 296.0, "max": 300.0, "slope_per_ns": 0.1},
        },
        "blocks_200ps": [],
        "density_qc": {
            "slope_percent_per_ns": 0.2,
            "slope_kg_m3_per_ns": 2.79,
            "last_two_block_diff_percent": 0.2,
            "max_adjacent_block_diff_percent": 0.4,
            "first_vs_second_500ps_diff_percent": 0.3,
            "one_to_two_ns_mean_kg_m3": 1390.0,
            "two_to_three_ns_mean_kg_m3": 1395.0,
            "one_to_two_vs_two_to_three_ns_diff_percent": 0.36,
        },
        "temperature_qc": {"mean_K": 298.2, "slope_K_per_ns": 0.1},
        "volume_qc": {"max_adjacent_frame_jump_percent_0_3ns": 0.2, "last_1ns": {}},
        "box_qc": {
            "rlist_nm": 1.2,
            "min_box_nm_0_3ns": 3.0,
            "min_box_over_2rlist": 1.25,
            "time_extension_allowed_by_margin": True,
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
        "hard_fail_reasons": [],
        "review_reasons": [],
        "exploratory_verdict": "THREE_NS_STATIONARITY_CANDIDATE",
        "physics_status": "EXPLORATORY_ONLY",
        "equilibrium_validated": False,
        "production_ready": False,
        "not_verified": ["equilibrium"],
    }
    write_test_json(extension_dir / EXTENSION_ANALYSIS_FILE, extension_analysis)


def create_self_test_quarantine(next_root: Path, replacement_dir: Path) -> None:
    chain_id = "screen_L1P1x2_rho1000_QUARANTINED"
    run_dir = next_root / "04_Runs" / chain_id
    work = run_dir / "equilibration"
    work.mkdir(parents=True)
    (run_dir / "RUN_RECORD.md").write_text("- System: L1P1x2 = test\n")
    (run_dir / "metrics.json").write_text(
        json.dumps({"initial_density_kg_m3": 1000.0}) + "\n"
    )
    replacement_manifest = read_json(
        replacement_dir / "equilibration" / "chain_manifest.json"
    )
    write_test_json(work / "chain_manifest.json", replacement_manifest)
    write_test_json(
        work / "equilibration_metrics.json",
        {
            "chain_id": chain_id,
            "technical_status": "PASS_COMPLETE",
            "physics_status": "EXPLORATORY_ONLY",
            "npt": {
                "resumed": True,
                "first_time_ps": 0.0,
                "last_time_ps": 1000.0,
                "duration_ps": 1000.0,
            },
        },
    )
    write_test_json(
        work / "safety_thread_reduction_record.json",
        {
            "chain_id": chain_id,
            "technical_status": "INTERRUPTED_BY_SAFETY_POLICY_CHANGE",
            "resume_command_mode": "gmx mdrun -cpi npt.cpt -append",
        },
    )
    evidence = {
        relative_name: sha256_file(run_dir / relative_name)
        for relative_name in sorted(QUARANTINE_EVIDENCE_FILES)
    }
    config_path = next_root / QUARANTINE_CONFIG_RELATIVE
    config_path.parent.mkdir(parents=True, exist_ok=True)
    write_test_json(
        config_path,
        {
            "schema_version": QUARANTINE_SCHEMA,
            "entries": [
                {
                    "chain_id": chain_id,
                    "reason_code": QUARANTINE_REASON,
                    "reason": (
                        "The resume input checkpoint SHA256 is unrecoverable because "
                        "the checkpoint bytes were not snapshotted."
                    ),
                    "replacement_chain_id": replacement_dir.name,
                    "evidence_sha256": evidence,
                }
            ],
        },
    )


def parse_args() -> argparse.Namespace:
    default_next = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--next-root", type=Path, default=default_next)
    parser.add_argument("--dry-run", action="store_true", help="validate and render without replacing CSVs")
    parser.add_argument("--self-test", action="store_true", help="run a deterministic synthetic dry-run")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.self_test:
        with tempfile.TemporaryDirectory(prefix="cile_registry_selftest_") as temporary:
            next_root = create_self_test_fixture(Path(temporary))
            chain_rows, qc_rows, incomplete, first_audit = build_registries(next_root)
            first_chain = render_csv(CHAIN_FIELDS, chain_rows)
            first_qc = render_csv(QC_FIELDS, qc_rows)
            second_chain_rows, second_qc_rows, _, second_audit = build_registries(next_root)
            second_chain = render_csv(CHAIN_FIELDS, second_chain_rows)
            second_qc = render_csv(QC_FIELDS, second_qc_rows)
            if (
                first_chain != second_chain
                or first_qc != second_qc
                or first_audit != second_audit
                or incomplete
            ):
                raise RegistryError("self-test output is not deterministic")
            audit_document = json.loads(first_audit)
            if (
                len(audit_document.get("active_exclusions", [])) != 1
                or audit_document["active_exclusions"][0]["status"]
                != "ACTIVE_REPLACED"
                or audit_document["active_exclusions"][0]["replacement_chain_id"]
                != "screen_L1P1x2_rho1000_TEST"
            ):
                raise RegistryError("self-test quarantine audit is incomplete")
            if (
                len(chain_rows) != 3
                or not any(row["metric"] == "nvt_min_box_over_2rlist" for row in qc_rows)
                or sum(row["metric"] == "npt_min_box_over_2rlist" for row in qc_rows) != 2
                or not any(row["verdict"] == "SCREEN_STATIONARITY_PASS" for row in qc_rows)
                or not any(
                    row["verdict"] == "THREE_NS_STATIONARITY_CANDIDATE"
                    for row in qc_rows
                )
                or not any(
                    row["record_id"].endswith(":npt:002")
                    and row["artifact_path"].endswith("extensions/npt_ext001")
                    and row["start_step"] == BASE_NPT_STEPS
                    and row["target_step"] == EXTENSION_NPT_STEPS
                    and row["last_step"] == EXTENSION_NPT_STEPS
                    for row in chain_rows
                )
                or not any(
                    row["record_id"].endswith(":npt:001")
                    and row["artifact_path"].endswith(
                        "extensions/npt_ext001/base_snapshot"
                    )
                    and row["end_at"].endswith("00:11:00+09:00")
                    for row in chain_rows
                )
                or not any(
                    row["record_id"].endswith(":npt:001")
                    and row["metric"] == "stage_duration"
                    and row["evidence_file"].endswith(
                        "extensions/npt_ext001/base_snapshot/equilibration_metrics.json"
                    )
                    for row in qc_rows
                )
                or not any(
                    row["record_id"].endswith(":npt:002")
                    and row["domain"] == "technical"
                    and row["evidence_file"].endswith(
                        "extensions/npt_ext001/extension_metrics.json"
                    )
                    for row in qc_rows
                )
                or not any(
                    row["record_id"].endswith(":npt:002")
                    and row["domain"] == "physical"
                    and row["evidence_file"].endswith(
                        "extensions/npt_ext001/extension_analysis.json"
                    )
                    for row in qc_rows
                )
            ):
                raise RegistryError("self-test did not preserve required metrics/verdict")
            try:
                validate_rows([*chain_rows, dict(chain_rows[0])], qc_rows)
            except RegistryError as exc:
                if "duplicate record_id" not in str(exc):
                    raise
            else:
                raise RegistryError("self-test duplicate record was not rejected")
            broken_parent_rows = [dict(row) for row in chain_rows]
            broken_parent_rows[1]["parent_record_id"] = "missing:record:001"
            try:
                validate_rows(broken_parent_rows, qc_rows)
            except RegistryError as exc:
                if "missing parent_record_id" not in str(exc):
                    raise
            else:
                raise RegistryError("self-test missing parent was not rejected")
            broken_qc_rows = [dict(row) for row in qc_rows]
            broken_qc_rows[0]["record_id"] = "missing:record:001"
            try:
                validate_rows(chain_rows, broken_qc_rows)
            except RegistryError as exc:
                if "QC row references missing record_id" not in str(exc):
                    raise
            else:
                raise RegistryError("self-test missing QC reference was not rejected")
            chain_path = next_root / "04_Runs" / "chain_registry.csv"
            qc_path = next_root / "05_QC" / "equilibration_qc_results.csv"
            audit_path = next_root / QUARANTINE_AUDIT_RELATIVE
            atomic_replace_pair(
                chain_path,
                first_chain,
                qc_path,
                first_qc,
                next_root / ".equilibration_registry.lock",
                audit_path,
                first_audit,
            )
            if (
                chain_path.read_text() != first_chain
                or qc_path.read_text() != first_qc
                or audit_path.read_text() != first_audit
            ):
                raise RegistryError("self-test atomic replacement changed rendered content")

            fixture_work = next_root / "04_Runs" / "screen_L1P1x2_rho1000_TEST" / "equilibration"
            fixture_extension = fixture_work / "extensions" / EXTENSION_ID
            protected_chain = chain_path.read_bytes()
            protected_qc = qc_path.read_bytes()
            protected_audit = audit_path.read_bytes()

            def expect_rebuild_rejection(
                path: Path,
                expected_message: str,
                mutate: Any,
            ) -> None:
                original = path.read_bytes()
                try:
                    mutate(path)
                    try:
                        build_registries(next_root)
                    except RegistryError as exc:
                        if expected_message not in str(exc):
                            raise RegistryError(
                                f"self-test expected {expected_message!r}, got {exc!r}"
                            ) from exc
                    else:
                        raise RegistryError(
                            f"self-test corruption was not rejected: {expected_message}"
                        )
                    if (
                        chain_path.read_bytes() != protected_chain
                        or qc_path.read_bytes() != protected_qc
                        or audit_path.read_bytes() != protected_audit
                    ):
                        raise RegistryError(
                            "self-test failed: rejected extension changed central registries"
                        )
                finally:
                    path.write_bytes(original)

            expect_rebuild_rejection(
                fixture_extension / "base_snapshot" / "npt.log",
                "artifact evidence mismatch",
                lambda path: path.write_bytes(path.read_bytes() + b"tampered\n"),
            )

            def mutate_json_field(path: Path, key: str, value: Any) -> None:
                payload = read_json(path)
                payload[key] = value
                write_test_json(path, payload)

            def mutate_nested_json_field(
                path: Path, keys: tuple[str, ...], value: Any
            ) -> None:
                payload = read_json(path)
                target: dict[str, Any] = payload
                for key in keys[:-1]:
                    target = require_mapping(target, key, "self-test mutation")
                target[keys[-1]] = value
                write_test_json(path, payload)

            manifest_path = fixture_extension / "extension_manifest.json"
            expect_rebuild_rejection(
                manifest_path,
                "parent_record_id mismatch",
                lambda path: mutate_json_field(path, "parent_record_id", "missing:npt:001"),
            )
            expect_rebuild_rejection(
                manifest_path,
                "checkpoint does not identify snapshot npt.cpt",
                lambda path: mutate_json_field(path, "checkpoint_in_sha256", "0" * 64),
            )
            expect_rebuild_rejection(
                manifest_path,
                "start_step mismatch",
                lambda path: mutate_json_field(path, "start_step", BASE_NPT_STEPS + 1),
            )

            metrics_path = fixture_extension / "extension_metrics.json"
            expect_rebuild_rejection(
                metrics_path,
                "energy_terms_compared mismatch",
                lambda path: mutate_nested_json_field(
                    path, ("append_validation", "edr", "energy_terms_compared"), 44
                ),
            )
            expect_rebuild_rejection(
                metrics_path,
                "live_frames mismatch",
                lambda path: mutate_nested_json_field(
                    path, ("append_validation", "edr", "live_frames"), 3000
                ),
            )
            expect_rebuild_rejection(
                metrics_path,
                "canonical base EDR evidence mismatch",
                lambda path: mutate_nested_json_field(
                    path,
                    ("append_validation", "edr", "canonical_pre_boundary_sha256"),
                    "0" * 64,
                ),
            )
            expect_rebuild_rejection(
                metrics_path,
                "XTC base prefix SHA-256 evidence mismatch",
                lambda path: mutate_nested_json_field(
                    path, ("append_validation", "xtc", "base_sha256"), "0" * 64
                ),
            )
            expect_rebuild_rejection(
                metrics_path,
                "stored live Finished marker evidence mismatch",
                lambda path: mutate_nested_json_field(
                    path,
                    ("append_validation", "log", "live_finished_mdrun_markers"),
                    2,
                ),
            )
            expect_rebuild_rejection(
                metrics_path,
                "stored log bad-marker evidence mismatch for lincs",
                lambda path: mutate_nested_json_field(
                    path, ("append_validation", "log", "bad_markers", "lincs"), 1
                ),
            )
            expect_rebuild_rejection(
                metrics_path,
                "post-extension evidence mismatch for npt.edr",
                lambda path: mutate_nested_json_field(
                    path, ("post_extension_sha256", "npt.edr", "sha256"), "0" * 64
                ),
            )

            analysis_path = fixture_extension / EXTENSION_ANALYSIS_FILE
            expect_rebuild_rejection(
                analysis_path,
                "extension analysis source changed: extension_metrics.json",
                lambda path: mutate_nested_json_field(
                    path,
                    ("source_evidence", "extension_metrics.json", "sha256"),
                    "0" * 64,
                ),
            )
            analysis_bytes = analysis_path.read_bytes()
            try:
                analysis_path.unlink()
                try:
                    build_registries(next_root)
                except RegistryError as exc:
                    if "extension analysis is missing" not in str(exc):
                        raise
                else:
                    raise RegistryError("self-test missing extension analysis was not rejected")
                if (
                    chain_path.read_bytes() != protected_chain
                    or qc_path.read_bytes() != protected_qc
                    or audit_path.read_bytes() != protected_audit
                ):
                    raise RegistryError(
                        "self-test failed: missing analysis changed central registries"
                    )
            finally:
                analysis_path.write_bytes(analysis_bytes)

            restored_rows, restored_qc, _, restored_audit = build_registries(next_root)
            if (
                render_csv(CHAIN_FIELDS, restored_rows) != first_chain
                or render_csv(QC_FIELDS, restored_qc) != first_qc
                or restored_audit != first_audit
            ):
                raise RegistryError("self-test fixture did not restore after rejection tests")
            atomic_replace_pair(
                chain_path,
                second_chain,
                qc_path,
                second_qc,
                next_root / ".equilibration_registry.lock",
                audit_path,
                second_audit,
            )
            if (
                chain_path.read_text() != first_chain
                or qc_path.read_text() != first_qc
                or audit_path.read_text() != first_audit
            ):
                raise RegistryError("self-test repeat replacement is not idempotent")
            print(
                f"SELF_TEST_DRY_RUN_OK chain_rows={len(chain_rows)} qc_rows={len(qc_rows)} "
                "atomic_replace=OK "
                f"chain_sha256={hashlib.sha256(first_chain.encode()).hexdigest()} "
                f"qc_sha256={hashlib.sha256(first_qc.encode()).hexdigest()}"
            )
            return

    next_root = args.next_root.resolve()
    chain_rows, qc_rows, incomplete, quarantine_audit = build_registries(next_root)
    chain_content = render_csv(CHAIN_FIELDS, chain_rows)
    qc_content = render_csv(QC_FIELDS, qc_rows)
    if args.dry_run:
        print(
            f"DRY_RUN_OK chain_rows={len(chain_rows)} qc_rows={len(qc_rows)} "
            f"incomplete_chains={len(incomplete)} "
            f"chain_sha256={hashlib.sha256(chain_content.encode()).hexdigest()} "
            f"qc_sha256={hashlib.sha256(qc_content.encode()).hexdigest()} "
            f"quarantine_audit_sha256={hashlib.sha256(quarantine_audit.encode()).hexdigest()}"
        )
        audit_document = json.loads(quarantine_audit)
        for item in audit_document["active_exclusions"]:
            print(
                "QUARANTINE_ACTIVE "
                f"excluded={item['chain_id']} "
                f"replacement={item['replacement_chain_id']} "
                f"reason={item['reason_code']}"
            )
        for chain_id in incomplete:
            print(f"INCOMPLETE_SKIPPED {chain_id}")
        return

    chain_path = next_root / "04_Runs" / "chain_registry.csv"
    qc_path = next_root / "05_QC" / "equilibration_qc_results.csv"
    atomic_replace_pair(
        chain_path,
        chain_content,
        qc_path,
        qc_content,
        next_root / ".equilibration_registry.lock",
        next_root / QUARANTINE_AUDIT_RELATIVE,
        quarantine_audit,
    )
    print(
        f"REGISTRIES_REBUILT chain_rows={len(chain_rows)} qc_rows={len(qc_rows)} "
        f"incomplete_chains={len(incomplete)}"
    )
    for chain_id in incomplete:
        print(f"INCOMPLETE_SKIPPED {chain_id}")


if __name__ == "__main__":
    try:
        main()
    except RegistryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
