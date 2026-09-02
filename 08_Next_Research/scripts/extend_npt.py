#!/usr/bin/env python3
"""Safely extend a completed 1 ns exploratory NPT screen by 2 ns.

The base segment remains the immutable ``npt:001`` record.  Before any
continuation is attempted, every append-sensitive base artifact is copied
byte-for-byte into ``extensions/npt_ext001/base_snapshot``.  The continuation
uses a separate TPR but deliberately keeps the ``npt`` output prefix so that
GROMACS can enforce checkpoint output checksums while appending.

This script performs technical continuation checks only.  It does not carry
the base stationarity verdict forward and does not update central registries.
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
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any


EXTENSION_ID = "npt_ext001"
SCHEMA_VERSION = "npt-extension-v1"
BASE_STEPS = 1_000_000
EXTENSION_STEPS = 2_000_000
TARGET_TOTAL_STEPS = 3_000_000
DT_PS = 0.001
BASE_DURATION_PS = 1_000.0
EXTENSION_DURATION_PS = 2_000.0
TARGET_TOTAL_DURATION_PS = 3_000.0
TIME_TOLERANCE_PS = 1.0e-3
CHILD_SIGNAL_GRACE_SECONDS = 30.0
BASE_SNAPSHOT_FILES = (
    "npt.tpr",
    "npt.cpt",
    "npt.edr",
    "npt.xtc",
    "npt.log",
    "npt.gro",
    "equilibration_metrics.json",
)
MUTABLE_NPT_OUTPUTS = ("npt.cpt", "npt.edr", "npt.xtc", "npt.log", "npt.gro")
CONTINUITY_ENERGY_TERM = "Temperature"


class ExtensionError(RuntimeError):
    """The extension cannot proceed without weakening provenance or safety."""


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
        raise ExtensionError(f"required file is missing: {path}")
    return {"sha256": sha256(path), "size_bytes": path.stat().st_size}


def reject_json_constant(value: str) -> None:
    raise ExtensionError(f"non-finite JSON constant: {value}")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(), parse_constant=reject_json_constant)
    except (OSError, json.JSONDecodeError) as exc:
        raise ExtensionError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ExtensionError(f"expected a JSON object: {path}")
    return value


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def write_bytes_once(path: Path, content: bytes) -> None:
    """Atomically create a file, accepting an already-identical file only."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise ExtensionError(f"immutable file differs: {path}")
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
                raise ExtensionError(f"immutable file was created with different content: {path}")
    finally:
        if temporary.exists():
            temporary.unlink()


def write_json_once(path: Path, value: dict[str, Any]) -> None:
    write_bytes_once(path, canonical_json_bytes(value))


def copy_snapshot_once(source: Path, destination: Path) -> None:
    """Create a byte-identical snapshot without replacing an existing copy."""
    if not source.is_file():
        raise ExtensionError(f"base snapshot source is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if file_evidence(destination) != file_evidence(source):
            raise ExtensionError(f"existing base snapshot differs from source: {destination}")
        return
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.copy")
    try:
        with source.open("rb") as src, temporary.open("xb") as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
            dst.flush()
            os.fsync(dst.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if file_evidence(destination) != file_evidence(source):
                raise ExtensionError(f"base snapshot race produced different bytes: {destination}")
    finally:
        if temporary.exists():
            temporary.unlink()


def run_capture(command: list[str], cwd: Path) -> str:
    env = os.environ.copy()
    env["GMX_MAXBACKUP"] = "-1"
    result = subprocess.run(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=True,
        env=env,
    )
    return result.stdout


def run_capture_with_input(command: list[str], cwd: Path, input_text: str) -> str:
    env = os.environ.copy()
    env["GMX_MAXBACKUP"] = "-1"
    result = subprocess.run(
        command,
        cwd=cwd,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=True,
        env=env,
    )
    return result.stdout


def run_to_new_log(command: list[str], cwd: Path, log_path: Path) -> int:
    """Run in the caller's process group and forward direct termination signals.

    Sharing the group is intentional: thermal_guard pauses and resumes the
    Python driver and GROMACS together.  Forwarding additionally covers a
    signal sent only to this Python PID.
    """
    env = os.environ.copy()
    env["GMX_MAXBACKUP"] = "-1"
    forwarded_signal: int | None = None
    forwarded_at: float | None = None
    forwarded_signals = [signal.SIGTERM, signal.SIGINT]
    for optional_name in ("SIGHUP", "SIGQUIT"):
        optional_signal = getattr(signal, optional_name, None)
        if optional_signal is not None:
            forwarded_signals.append(optional_signal)
    previous_handlers: dict[signal.Signals, Any] = {}
    previous_mask: set[signal.Signals] | None = None
    if hasattr(signal, "pthread_sigmask"):
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, set(forwarded_signals))
    try:
        with log_path.open("x") as output:
            output.write(f"[{now()}] $ {shlex.join(command)}\n")
            output.flush()
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdout=output,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )

            def forward_signal(signum: int, _frame: object) -> None:
                nonlocal forwarded_signal, forwarded_at
                if forwarded_signal is None:
                    forwarded_signal = signum
                    forwarded_at = time.monotonic()
                try:
                    os.kill(process.pid, signum)
                except ProcessLookupError:
                    pass

            for forwarded in forwarded_signals:
                previous_handlers[forwarded] = signal.getsignal(forwarded)
                signal.signal(forwarded, forward_signal)
            if previous_mask is not None:
                signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
                previous_mask = None
            while True:
                try:
                    return_code = process.wait(timeout=0.5)
                    break
                except subprocess.TimeoutExpired:
                    if (
                        forwarded_at is not None
                        and time.monotonic() - forwarded_at >= CHILD_SIGNAL_GRACE_SECONDS
                    ):
                        process.kill()
                        return_code = process.wait(timeout=5.0)
                        break
            if forwarded_signal is not None:
                output.write(f"[{now()}] forwarded signal {forwarded_signal} to child process\n")
                output.flush()
                if return_code == 0:
                    return 128 + forwarded_signal
    finally:
        if previous_mask is not None:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        for forwarded, previous in previous_handlers.items():
            signal.signal(forwarded, previous)
    return return_code


def parse_last_energy_time(text: str) -> float:
    match = re.search(r"Last energy frame read\s+\d+\s+time\s+([-+0-9.eE]+)", text)
    if match:
        return float(match.group(1))
    matches = re.findall(r"time\s+([-+0-9.eE]+)", text)
    if not matches:
        raise ExtensionError("last energy time not found in gmx check output")
    return float(matches[-1])


def parse_energy_range(text: str) -> tuple[float, float]:
    first = re.search(r"frame:\s*0\s+\(index\s+0\),\s*t:\s*([-+0-9.eE]+)", text)
    if first is None:
        first = re.search(r"Reading energy frame\s+0\s+time\s+([-+0-9.eE]+)", text)
    if first is None:
        raise ExtensionError("first energy time not found in gmx check output")
    return float(first.group(1)), parse_last_energy_time(text)


def check_edr(gmx_bin: str, work: Path) -> tuple[float, float, str]:
    text = run_capture([gmx_bin, "check", "-e", "npt.edr"], work)
    first, last = parse_energy_range(text)
    if not (math.isfinite(first) and math.isfinite(last) and last >= first):
        raise ExtensionError(f"invalid EDR time range: {first} to {last} ps")
    return first, last, text


def parse_xvg_series(path: Path, term: str) -> list[tuple[float, float]]:
    rows: list[tuple[float, float]] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "@")):
            continue
        fields = stripped.split()
        if len(fields) < 2:
            raise ExtensionError(
                f"malformed {term} XVG row at {path}:{line_number}: {line!r}"
            )
        try:
            time_ps, value = float(fields[0]), float(fields[1])
        except ValueError as exc:
            raise ExtensionError(
                f"non-numeric {term} XVG row at {path}:{line_number}: {line!r}"
            ) from exc
        if not (math.isfinite(time_ps) and math.isfinite(value)):
            raise ExtensionError(
                f"non-finite {term} XVG row at {path}:{line_number}: {line!r}"
            )
        rows.append((time_ps, value))
    if not rows:
        raise ExtensionError(f"gmx energy produced no {term} rows: {path}")
    return rows


def extract_energy_series(
    gmx_bin: str,
    edr: Path,
    cwd: Path,
    output: Path,
    term: str = CONTINUITY_ENERGY_TERM,
) -> list[tuple[float, float]]:
    run_capture_with_input(
        [
            gmx_bin,
            "energy",
            "-f",
            str(edr.resolve()),
            "-o",
            str(output),
            "-xvg",
            "none",
            "-dp",
        ],
        cwd,
        f"{term}\n0\n",
    )
    return parse_xvg_series(output, term)


def uniform_time_axis(
    rows: list[tuple[float, float]],
    expected_first: float,
    expected_last: float,
    expected_cadence: float | None,
    context: str,
) -> float:
    if len(rows) < 2:
        raise ExtensionError(f"{context} needs at least two energy frames")
    times = [row[0] for row in rows]
    if not math.isclose(
        times[0], expected_first, rel_tol=0.0, abs_tol=TIME_TOLERANCE_PS
    ):
        raise ExtensionError(f"{context} first frame changed: {times[0]} != {expected_first}")
    if not math.isclose(
        times[-1], expected_last, rel_tol=0.0, abs_tol=TIME_TOLERANCE_PS
    ):
        raise ExtensionError(f"{context} last frame changed: {times[-1]} != {expected_last}")
    cadence = times[1] - times[0]
    if not math.isfinite(cadence) or cadence <= 0.0:
        raise ExtensionError(f"{context} has a non-positive frame cadence: {cadence}")
    if expected_cadence is not None and not math.isclose(
        cadence, expected_cadence, rel_tol=0.0, abs_tol=TIME_TOLERANCE_PS
    ):
        raise ExtensionError(
            f"{context} cadence changed: {cadence} != {expected_cadence} ps"
        )
    expected_frames = int(round((expected_last - expected_first) / cadence)) + 1
    if len(times) != expected_frames:
        raise ExtensionError(
            f"{context} frame count is not continuous: {len(times)} != {expected_frames}"
        )
    for index, time_ps in enumerate(times):
        expected_time = expected_first + index * cadence
        if not math.isclose(
            time_ps, expected_time, rel_tol=0.0, abs_tol=TIME_TOLERANCE_PS
        ):
            raise ExtensionError(
                f"{context} time-axis gap at frame {index}: {time_ps} != {expected_time} ps"
            )
    return cadence


def verify_gmx_energy_comparison(
    text: str,
    context: str,
    expect_longer_second_file: bool,
) -> int:
    normalized = text.replace("\r", "\n")
    term_match = re.search(
        r"There are\s+(\d+)\s+terms to compare in the energy files", normalized
    )
    if term_match is None or int(term_match.group(1)) <= 0:
        raise ExtensionError(f"{context} did not compare any EDR energy terms")
    mismatch = re.search(
        r"(?m)^\s*.+?\s+step\s+\d+\s*:.*?\s+step\s+\d+\s*:", normalized
    )
    if mismatch is not None:
        raise ExtensionError(
            f"{context} found an EDR value mismatch: {mismatch.group(0).strip()}"
        )
    lowered = normalized.lower()
    forbidden = (
        "different number of energy terms",
        "files have different time",
        "inconsistent time",
        "invalid energy",
    )
    if any(marker in lowered for marker in forbidden):
        raise ExtensionError(f"{context} reported an incompatible EDR comparison")
    if expect_longer_second_file:
        if not re.search(r"End of file on .+ but not on .+", normalized):
            raise ExtensionError(
                f"{context} did not prove that only the second EDR continues past the base"
            )
    elif "Files read successfully" not in normalized:
        raise ExtensionError(f"{context} did not report equal-length EDR success")
    return int(term_match.group(1))


def parse_tpr_number(dump: str, key: str) -> float:
    match = re.search(rf"^\s*{re.escape(key)}\s*=\s*([-+0-9.eE]+)\s*$", dump, re.MULTILINE)
    if match is None:
        raise ExtensionError(f"{key} not found in TPR dump")
    return float(match.group(1))


def tpr_shape(gmx_bin: str, work: Path, tpr: Path) -> dict[str, Any]:
    dump = run_capture([gmx_bin, "dump", "-s", str(tpr)], work)
    return {
        "nsteps": int(parse_tpr_number(dump, "nsteps")),
        "dt_ps": parse_tpr_number(dump, "dt"),
        "init_step": int(parse_tpr_number(dump, "init-step")),
        "tinit_ps": parse_tpr_number(dump, "tinit"),
    }


def require_tpr_shape(shape: dict[str, Any], expected_steps: int, context: str) -> None:
    if shape["nsteps"] != expected_steps:
        raise ExtensionError(
            f"{context} nsteps mismatch: {shape['nsteps']} != {expected_steps}"
        )
    if not math.isclose(shape["dt_ps"], DT_PS, rel_tol=0.0, abs_tol=1.0e-12):
        raise ExtensionError(f"{context} dt mismatch: {shape['dt_ps']} != {DT_PS}")


def finished_marker_count(path: Path) -> int:
    return path.read_text(errors="replace").count("Finished mdrun")


def bad_marker_counts(text: str) -> dict[str, int]:
    return {
        "fatal": len(re.findall(r"fatal error", text, re.IGNORECASE)),
        "nan": len(re.findall(r"\bnan\b", text, re.IGNORECASE)),
        "lincs": len(re.findall(r"lincs warning", text, re.IGNORECASE)),
        "segfault": len(re.findall(r"segmentation fault", text, re.IGNORECASE)),
    }


def validate_base_metrics(metrics: dict[str, Any]) -> None:
    if metrics.get("technical_status") != "PASS_COMPLETE":
        raise ExtensionError("base equilibration technical_status is not PASS_COMPLETE")
    analysis = metrics.get("analysis")
    if not isinstance(analysis, dict):
        raise ExtensionError("base analysis is missing")
    reasons = analysis.get("hard_fail_reasons")
    if reasons != []:
        raise ExtensionError(f"base analysis has hard-fail reasons: {reasons}")
    if analysis.get("exploratory_verdict") not in {
        "SCREEN_EXTEND",
        "SCREEN_STATIONARITY_PASS",
    }:
        raise ExtensionError(
            "extension requires SCREEN_EXTEND or SCREEN_STATIONARITY_PASS"
        )
    if not math.isclose(
        float(metrics.get("npt_target_ps", math.nan)),
        BASE_DURATION_PS,
        rel_tol=0.0,
        abs_tol=TIME_TOLERANCE_PS,
    ):
        raise ExtensionError("base npt_target_ps is not 1000 ps")
    npt_run = metrics.get("npt")
    if not isinstance(npt_run, dict):
        raise ExtensionError("base NPT run metrics are missing")
    if not math.isclose(
        float(npt_run.get("duration_ps", math.nan)),
        BASE_DURATION_PS,
        rel_tol=0.0,
        abs_tol=TIME_TOLERANCE_PS,
    ):
        raise ExtensionError("base NPT EDR duration metric is not 1000 ps")
    bad_markers = metrics.get("bad_markers")
    if not isinstance(bad_markers, dict) or any(int(value) != 0 for value in bad_markers.values()):
        raise ExtensionError(f"base runtime markers are not clean: {bad_markers}")
    warnings = metrics.get("grompp_warnings")
    if not isinstance(warnings, dict) or int(warnings.get("npt", -1)) != 0:
        raise ExtensionError(f"base NPT grompp warnings are not zero: {warnings}")


def verify_time_range(
    first: float,
    last: float,
    expected_first: float,
    expected_duration: float,
    context: str,
) -> None:
    duration = last - first
    if not math.isclose(first, expected_first, rel_tol=0.0, abs_tol=TIME_TOLERANCE_PS):
        raise ExtensionError(f"{context} first EDR time changed: {first} != {expected_first}")
    if not math.isclose(duration, expected_duration, rel_tol=0.0, abs_tol=TIME_TOLERANCE_PS):
        raise ExtensionError(
            f"{context} EDR duration mismatch: {duration} != {expected_duration} ps"
        )


def snapshot_evidence(snapshot: Path) -> dict[str, dict[str, Any]]:
    return {name: file_evidence(snapshot / name) for name in BASE_SNAPSHOT_FILES}


def verify_snapshot(snapshot: Path, expected: dict[str, Any]) -> None:
    if set(expected) != set(BASE_SNAPSHOT_FILES):
        raise ExtensionError("manifest base_snapshot file set is invalid")
    for name in BASE_SNAPSHOT_FILES:
        actual = file_evidence(snapshot / name)
        if actual != expected[name]:
            raise ExtensionError(
                f"immutable base snapshot evidence mismatch for {name}: {actual} != {expected[name]}"
            )


def verify_xtc_full_prefix(work: Path, snapshot: Path) -> dict[str, Any]:
    base = (snapshot / "npt.xtc").read_bytes()
    current = work / "npt.xtc"
    with current.open("rb") as handle:
        prefix = handle.read(len(base))
    if prefix != base:
        raise ExtensionError("extension did not preserve the full byte prefix of npt.xtc")
    return {
        "mode": "full_byte_prefix",
        "base_size_bytes": len(base),
        "base_sha256": sha256(snapshot / "npt.xtc"),
    }


def verify_edr_base_semantics(
    gmx_bin: str,
    work: Path,
    snapshot: Path,
    live_last_ps: float,
) -> dict[str, Any]:
    """Prove preserved history without assuming a completed EDR is a byte prefix.

    GROMACS rewrites the checkpoint-boundary frame when an append begins.  The
    pre-boundary segment must therefore be exactly identical, while the single
    1000 ps boundary frame is accepted only if GROMACS compares every energy
    term successfully at its native semantic tolerance.
    """
    base_edr = snapshot / "npt.edr"
    live_edr = work / "npt.edr"
    with tempfile.TemporaryDirectory(prefix="npt-edr-verify-") as temporary:
        temporary_path = Path(temporary)
        base_xvg = temporary_path / "base_temperature.xvg"
        live_xvg = temporary_path / "live_temperature.xvg"
        base_rows = extract_energy_series(gmx_bin, base_edr, work, base_xvg)
        live_rows = extract_energy_series(gmx_bin, live_edr, work, live_xvg)
        base_first = base_rows[0][0]
        base_last = base_rows[-1][0]
        cadence = uniform_time_axis(
            base_rows,
            base_first,
            base_last,
            None,
            "base EDR",
        )
        if not math.isclose(
            base_last - base_first,
            BASE_DURATION_PS,
            rel_tol=0.0,
            abs_tol=TIME_TOLERANCE_PS,
        ):
            raise ExtensionError(
                f"base EDR extracted duration changed: {base_last - base_first} ps"
            )
        uniform_time_axis(
            live_rows,
            base_first,
            live_last_ps,
            cadence,
            "live EDR",
        )
        if len(live_rows) < len(base_rows):
            raise ExtensionError("live EDR contains fewer frames than the base snapshot")
        for index, (base_row, live_row) in enumerate(zip(base_rows, live_rows)):
            if not math.isclose(
                base_row[0], live_row[0], rel_tol=0.0, abs_tol=TIME_TOLERANCE_PS
            ):
                raise ExtensionError(
                    f"live EDR base time changed at frame {index}: "
                    f"{live_row[0]} != {base_row[0]} ps"
                )

        # Exclude the checkpoint boundary itself.  This canonical segment
        # contains every stored EDR term through the last unmodified frame.
        exact_end = base_last - cadence / 2.0
        canonical_base = temporary_path / "base_pre_boundary.edr"
        canonical_live = temporary_path / "live_pre_boundary.edr"
        for source, destination in (
            (base_edr, canonical_base),
            (live_edr, canonical_live),
        ):
            run_capture_with_input(
                [
                    gmx_bin,
                    "eneconv",
                    "-f",
                    str(source.resolve()),
                    "-o",
                    str(destination),
                    "-e",
                    format(exact_end, ".12g"),
                ],
                work,
                "",
            )
        canonical_base_evidence = file_evidence(canonical_base)
        canonical_live_evidence = file_evidence(canonical_live)
        if canonical_live_evidence != canonical_base_evidence:
            raise ExtensionError(
                "canonical EDR history before the checkpoint boundary is not byte-identical"
            )
        strict_text = run_capture(
            [
                gmx_bin,
                "check",
                "-e",
                str(canonical_base),
                "-e2",
                str(canonical_live),
                "-tol",
                "0",
                "-abstol",
                "0",
            ],
            work,
        )
        strict_terms = verify_gmx_energy_comparison(
            strict_text,
            "strict pre-boundary EDR comparison",
            expect_longer_second_file=False,
        )
        inclusive_text = run_capture(
            [
                gmx_bin,
                "check",
                "-e",
                str(base_edr.resolve()),
                "-e2",
                str(live_edr.resolve()),
            ],
            work,
        )
        inclusive_terms = verify_gmx_energy_comparison(
            inclusive_text,
            "inclusive base EDR comparison",
            expect_longer_second_file=live_last_ps > base_last + TIME_TOLERANCE_PS,
        )
        if inclusive_terms != strict_terms:
            raise ExtensionError(
                f"EDR term count changed at the checkpoint boundary: "
                f"{inclusive_terms} != {strict_terms}"
            )
        return {
            "mode": "exact_pre_boundary_plus_gromacs_boundary_comparison",
            "energy_terms_compared": inclusive_terms,
            "base_frames": len(base_rows),
            "live_frames": len(live_rows),
            "frame_cadence_ps": cadence,
            "exact_pre_boundary_last_ps": base_last - cadence,
            "canonical_pre_boundary_sha256": canonical_base_evidence["sha256"],
            "canonical_pre_boundary_size_bytes": canonical_base_evidence["size_bytes"],
            "boundary_ps": base_last,
            "boundary_comparison": "gmx_check_native_default_tolerance_no_mismatch_lines",
        }


def verify_live_log_semantics(work: Path, snapshot: Path) -> dict[str, Any]:
    base_finished = finished_marker_count(snapshot / "npt.log")
    if base_finished < 1:
        raise ExtensionError("immutable base log has no Finished mdrun marker")
    text = (work / "npt.log").read_text(errors="replace")
    restart_matches = list(
        re.finditer(
            r"Restarting from checkpoint,\s*appending to previous log file\.",
            text,
            re.IGNORECASE,
        )
    )
    if not restart_matches:
        raise ExtensionError("live npt.log has no checkpoint append restart marker")
    restart = restart_matches[-1]
    checkpoint_offset = text.rfind("Reading checkpoint file", 0, restart.start())
    started_offset = text.find("Started mdrun", restart.end())
    finished_offset = text.find("Finished mdrun", started_offset)
    if checkpoint_offset < 0 or started_offset < 0 or finished_offset < 0:
        raise ExtensionError(
            "live npt.log does not contain checkpoint -> restart -> start -> Finished semantics"
        )
    marker_counts = bad_marker_counts(text)
    if any(marker_counts.values()):
        raise ExtensionError(f"bad live NPT runtime markers: {marker_counts}")
    live_finished = finished_marker_count(work / "npt.log")
    if live_finished < 1:
        raise ExtensionError("live npt.log has no final Finished mdrun marker")
    return {
        "mode": "checkpoint_restart_append_sequence",
        "base_snapshot_finished_mdrun_markers": base_finished,
        "live_finished_mdrun_markers": live_finished,
        "restart_append_markers": len(restart_matches),
        "bad_markers": marker_counts,
    }


def verify_completed_append(
    gmx_bin: str,
    work: Path,
    snapshot: Path,
    first: float,
    last: float,
    expected_first: float,
) -> dict[str, Any]:
    verify_time_range(
        first,
        last,
        expected_first,
        TARGET_TOTAL_DURATION_PS,
        "completed extension",
    )
    return {
        "xtc": verify_xtc_full_prefix(work, snapshot),
        "edr": verify_edr_base_semantics(gmx_bin, work, snapshot, last),
        "log": verify_live_log_semantics(work, snapshot),
    }


def next_attempt_number(attempt_dir: Path) -> int:
    numbers: list[int] = []
    if attempt_dir.exists():
        for path in attempt_dir.iterdir():
            match = re.search(r"attempt_(\d{3})", path.name)
            if match:
                numbers.append(int(match.group(1)))
    return max(numbers, default=0) + 1


def gromacs_identity(gmx_bin: str, work: Path) -> tuple[str, str]:
    resolved = shutil.which(gmx_bin)
    if resolved is None:
        raise ExtensionError(f"GROMACS executable not found: {gmx_bin}")
    output = run_capture([resolved, "--version"], work)
    version = next(
        (line.strip() for line in output.splitlines() if "GROMACS version:" in line),
        None,
    )
    if version is None:
        raise ExtensionError("GROMACS version line not found")
    return str(Path(resolved).resolve()), version


def prepare_extended_tpr(
    gmx_bin: str,
    work: Path,
    extension_dir: Path,
    source_tpr: Path,
) -> tuple[Path, dict[str, Any], str]:
    prepared = extension_dir / f".{EXTENSION_ID}.{os.getpid()}.prepare.tpr"
    if prepared.exists():
        prepared.unlink()
    command = [
        gmx_bin,
        "convert-tpr",
        "-s",
        str(source_tpr),
        "-extend",
        format(EXTENSION_DURATION_PS, ".12g"),
        "-o",
        str(prepared),
    ]
    log_path = extension_dir / f"prepare_convert_tpr_{os.getpid()}.log"
    try:
        exit_code = run_to_new_log(command, work, log_path)
        if exit_code != 0:
            raise ExtensionError(f"gmx convert-tpr failed with exit code {exit_code}: {log_path}")
        shape = tpr_shape(gmx_bin, work, prepared)
        require_tpr_shape(shape, TARGET_TOTAL_STEPS, "extended TPR")
        return prepared, shape, sha256(prepared)
    except Exception:
        if prepared.exists():
            prepared.unlink()
        raise


def promote_tpr_once(prepared: Path, destination: Path, expected_sha256: str) -> None:
    if destination.exists():
        if sha256(destination) != expected_sha256:
            raise ExtensionError(f"existing extended TPR hash mismatch: {destination}")
        if prepared.exists():
            prepared.unlink()
        return
    if sha256(prepared) != expected_sha256:
        raise ExtensionError("prepared extended TPR changed before promotion")
    try:
        os.link(prepared, destination)
    except FileExistsError:
        if sha256(destination) != expected_sha256:
            raise ExtensionError(f"extended TPR race produced a different file: {destination}")
    finally:
        if prepared.exists():
            prepared.unlink()


def validate_manifest(
    manifest: dict[str, Any],
    chain_id: str,
    gmx_bin: str,
    gmx_version: str,
    chain_manifest_path: Path,
    snapshot: Path,
) -> None:
    exact = {
        "schema_version": SCHEMA_VERSION,
        "extension_id": EXTENSION_ID,
        "chain_id": chain_id,
        "record_id": f"{chain_id}:npt:002",
        "parent_record_id": f"{chain_id}:npt:001",
        "stage": "npt",
        "segment_no": 2,
        "mode": "EXTEND",
        "start_step": BASE_STEPS,
        "target_step": EXTENSION_STEPS,
        "base_steps": BASE_STEPS,
        "extension_steps": EXTENSION_STEPS,
        "target_total_steps": TARGET_TOTAL_STEPS,
        "dt_ps": DT_PS,
        "base_duration_ps": BASE_DURATION_PS,
        "extension_duration_ps": EXTENSION_DURATION_PS,
        "target_total_duration_ps": TARGET_TOTAL_DURATION_PS,
        "allowed_threads": [6],
        "gmx_bin": gmx_bin,
        "gromacs_version": gmx_version,
    }
    for key, expected in exact.items():
        if manifest.get(key) != expected:
            raise ExtensionError(
                f"immutable extension manifest mismatch for {key}: {manifest.get(key)!r} != {expected!r}"
            )
    if manifest.get("chain_manifest_sha256") != sha256(chain_manifest_path):
        raise ExtensionError("base chain_manifest.json changed after extension preparation")
    verify_snapshot(snapshot, manifest.get("base_snapshot", {}))
    if manifest.get("checkpoint_in_sha256") != manifest["base_snapshot"]["npt.cpt"]["sha256"]:
        raise ExtensionError("checkpoint_in_sha256 does not identify the base snapshot checkpoint")


def final_output_evidence(work: Path, extended_tpr: Path) -> dict[str, dict[str, Any]]:
    evidence = {name: file_evidence(work / name) for name in MUTABLE_NPT_OUTPUTS}
    evidence[extended_tpr.name] = file_evidence(extended_tpr)
    return evidence


def verify_final_metrics(
    metrics: dict[str, Any],
    manifest_path: Path,
    work: Path,
    extended_tpr: Path,
    first: float,
    last: float,
    append_validation: dict[str, Any],
) -> None:
    if metrics.get("technical_status") != "PASS_COMPLETE":
        raise ExtensionError("immutable extension metrics are not PASS_COMPLETE")
    if metrics.get("extension_manifest_sha256") != sha256(manifest_path):
        raise ExtensionError("extension metrics reference a different manifest")
    if metrics.get("post_extension_sha256") != final_output_evidence(work, extended_tpr):
        raise ExtensionError("post-extension artifacts changed after immutable metrics were written")
    if metrics.get("append_validation") != append_validation:
        raise ExtensionError("stored append validation no longer matches the completed outputs")
    verify_time_range(
        first,
        last,
        float(metrics["edr_range_ps"]["first"]),
        TARGET_TOTAL_DURATION_PS,
        "completed extension",
    )


def build_final_metrics(
    manifest: dict[str, Any],
    manifest_path: Path,
    work: Path,
    extended_tpr: Path,
    first: float,
    last: float,
    finished_markers: int,
    append_validation: dict[str, Any],
    completion_mode: str,
    attempt_number: int | None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "extension_id": EXTENSION_ID,
        "chain_id": manifest["chain_id"],
        "record_id": manifest["record_id"],
        "parent_record_id": manifest["parent_record_id"],
        "stage": "npt",
        "segment_no": 2,
        "mode": "EXTEND",
        "start_step": BASE_STEPS,
        "target_step": EXTENSION_STEPS,
        "base_steps": BASE_STEPS,
        "extension_steps": EXTENSION_STEPS,
        "target_total_steps": TARGET_TOTAL_STEPS,
        "technical_status": "PASS_COMPLETE",
        "physics_status": "NOT_EVALUATED_AFTER_EXTENSION",
        "analysis_status": "PENDING_EXTENSION_REANALYSIS",
        "completion_mode": completion_mode,
        "completion_attempt": attempt_number,
        "completed_at": now(),
        "edr_range_ps": {
            "first": first,
            "last": last,
            "duration": last - first,
            "base_duration": BASE_DURATION_PS,
            "extension_duration": EXTENSION_DURATION_PS,
            "target_total_duration": TARGET_TOTAL_DURATION_PS,
        },
        "finished_mdrun_markers": finished_markers,
        "append_validation": append_validation,
        "checkpoint_in_sha256": manifest["checkpoint_in_sha256"],
        "extension_manifest_sha256": sha256(manifest_path),
        "post_extension_sha256": final_output_evidence(work, extended_tpr),
        "base_analysis_preserved_at": "base_snapshot/equilibration_metrics.json",
        "not_verified": [
            "stationarity after the 2 ns extension",
            "equilibrium density",
            "independent replicas",
            "production readiness",
            "transport properties",
            "central registry linkage for npt:002",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--extend-ps", type=float, default=EXTENSION_DURATION_PS)
    parser.add_argument("--threads", type=int, default=6)
    parser.add_argument("--gmx-bin", default="gmx")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if not math.isclose(
        args.extend_ps,
        EXTENSION_DURATION_PS,
        rel_tol=0.0,
        abs_tol=TIME_TOLERANCE_PS,
    ):
        raise SystemExit(
            f"this protocol fixes --extend-ps at {EXTENSION_DURATION_PS:g} ps "
            f"({EXTENSION_STEPS} extension steps)"
        )
    if args.threads != 6:
        raise SystemExit("this Mac safety protocol requires exactly 6 OpenMP threads")

    run_dir = args.run_dir.resolve()
    work = run_dir / "equilibration"
    if not work.is_dir():
        raise SystemExit(f"equilibration directory is missing: {work}")
    extension_dir = work / "extensions" / EXTENSION_ID
    extension_preexisted = extension_dir.exists()
    if extension_preexisted and not args.resume:
        raise SystemExit(f"extension directory exists; use --resume: {extension_dir}")
    if args.resume and not extension_preexisted:
        raise SystemExit(f"extension directory does not exist; omit --resume: {extension_dir}")

    lock_path = work / ".chain.lock"
    with lock_path.open("a+") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SystemExit(f"another process holds the chain lock: {work}") from exc

        snapshot = extension_dir / "base_snapshot"
        manifest_path = extension_dir / "extension_manifest.json"
        metrics_path = extension_dir / "extension_metrics.json"
        extended_tpr = extension_dir / f"{EXTENSION_ID}.tpr"
        chain_manifest_path = work / "chain_manifest.json"
        base_metrics_path = work / "equilibration_metrics.json"

        try:
            gmx_bin, gmx_version = gromacs_identity(args.gmx_bin, work)

            if manifest_path.exists():
                manifest = read_json(manifest_path)
                validate_manifest(
                    manifest,
                    run_dir.name,
                    gmx_bin,
                    gmx_version,
                    chain_manifest_path,
                    snapshot,
                )
                if sha256(work / "npt.tpr") != manifest["base_snapshot"]["npt.tpr"]["sha256"]:
                    raise ExtensionError("base npt.tpr changed after snapshot")
                if sha256(base_metrics_path) != manifest["base_snapshot"]["equilibration_metrics.json"]["sha256"]:
                    raise ExtensionError("base equilibration_metrics.json was overwritten after snapshot")
                if not extended_tpr.exists():
                    current_first, current_last, _ = check_edr(gmx_bin, work)
                    verify_time_range(
                        current_first,
                        current_last,
                        float(manifest["base_edr_range_ps"]["first"]),
                        BASE_DURATION_PS,
                        "TPR recovery",
                    )
                    prepared, shape, prepared_hash = prepare_extended_tpr(
                        gmx_bin,
                        work,
                        extension_dir,
                        snapshot / "npt.tpr",
                    )
                    if shape != manifest["extended_tpr_shape"]:
                        raise ExtensionError("recovered extended TPR shape differs from manifest")
                    if prepared_hash != manifest["extended_tpr_sha256"]:
                        raise ExtensionError("recovered extended TPR hash differs from manifest")
                    promote_tpr_once(prepared, extended_tpr, prepared_hash)
                elif sha256(extended_tpr) != manifest["extended_tpr_sha256"]:
                    raise ExtensionError("extended TPR hash differs from immutable manifest")
            else:
                base_metrics = read_json(base_metrics_path)
                validate_base_metrics(base_metrics)
                chain_manifest = read_json(chain_manifest_path)
                if chain_manifest.get("npt_steps") != BASE_STEPS:
                    raise ExtensionError("base chain manifest does not describe 1,000,000 NPT steps")
                if not math.isclose(
                    float(chain_manifest.get("dt_ps", math.nan)),
                    DT_PS,
                    rel_tol=0.0,
                    abs_tol=1.0e-12,
                ):
                    raise ExtensionError("base chain manifest dt is not 0.001 ps")
                if chain_manifest.get("gromacs_version") != gmx_version:
                    raise ExtensionError(
                        "extension GROMACS version differs from the immutable base chain version"
                    )
                base_shape = tpr_shape(gmx_bin, work, work / "npt.tpr")
                require_tpr_shape(base_shape, BASE_STEPS, "base TPR")
                base_first, base_last, _ = check_edr(gmx_bin, work)
                verify_time_range(
                    base_first,
                    base_last,
                    float(base_metrics["npt"]["first_time_ps"]),
                    BASE_DURATION_PS,
                    "base",
                )
                if finished_marker_count(work / "npt.log") < 1:
                    raise ExtensionError("base npt.log has no Finished mdrun marker")
                extension_dir.mkdir(parents=True, exist_ok=True)
                snapshot.mkdir(parents=True, exist_ok=True)
                for name in BASE_SNAPSHOT_FILES:
                    copy_snapshot_once(work / name, snapshot / name)
                base_evidence = snapshot_evidence(snapshot)
                prepared, extended_shape, extended_hash = prepare_extended_tpr(
                    gmx_bin,
                    work,
                    extension_dir,
                    snapshot / "npt.tpr",
                )
                manifest = {
                    "schema_version": SCHEMA_VERSION,
                    "extension_id": EXTENSION_ID,
                    "chain_id": run_dir.name,
                    "record_id": f"{run_dir.name}:npt:002",
                    "record_label": "npt:002",
                    "parent_record_id": f"{run_dir.name}:npt:001",
                    "parent_record_label": "npt:001",
                    "stage": "npt",
                    "segment_no": 2,
                    "mode": "EXTEND",
                    "created_at": now(),
                    "start_step": BASE_STEPS,
                    "target_step": EXTENSION_STEPS,
                    "target_step_semantics": "extension segment length; cumulative target is target_total_steps",
                    "base_steps": BASE_STEPS,
                    "extension_steps": EXTENSION_STEPS,
                    "target_total_steps": TARGET_TOTAL_STEPS,
                    "dt_ps": DT_PS,
                    "base_duration_ps": BASE_DURATION_PS,
                    "extension_duration_ps": EXTENSION_DURATION_PS,
                    "target_total_duration_ps": TARGET_TOTAL_DURATION_PS,
                    "base_edr_range_ps": {
                        "first": base_first,
                        "last": base_last,
                        "duration": base_last - base_first,
                    },
                    "expected_final_edr_last_ps": base_first + TARGET_TOTAL_DURATION_PS,
                    "base_finished_mdrun_markers": finished_marker_count(snapshot / "npt.log"),
                    "base_tpr_shape": base_shape,
                    "extended_tpr_shape": extended_shape,
                    "extended_tpr_path": extended_tpr.name,
                    "extended_tpr_sha256": extended_hash,
                    "output_prefix": "npt",
                    "checkpoint_in_sha256": base_evidence["npt.cpt"]["sha256"],
                    "base_snapshot": base_evidence,
                    "base_snapshot_path": "base_snapshot",
                    "base_metrics_sha256": base_evidence["equilibration_metrics.json"]["sha256"],
                    "chain_manifest_sha256": sha256(chain_manifest_path),
                    "gmx_bin": gmx_bin,
                    "gromacs_version": gmx_version,
                    "allowed_threads": [6],
                }
                write_json_once(manifest_path, manifest)
                promote_tpr_once(prepared, extended_tpr, extended_hash)

            validate_manifest(
                manifest,
                run_dir.name,
                gmx_bin,
                gmx_version,
                chain_manifest_path,
                snapshot,
            )
            extended_shape = tpr_shape(gmx_bin, work, extended_tpr)
            require_tpr_shape(extended_shape, TARGET_TOTAL_STEPS, "extended TPR")
            if extended_shape != manifest["extended_tpr_shape"]:
                raise ExtensionError("extended TPR dump differs from immutable manifest")

            first, last, _ = check_edr(gmx_bin, work)
            base_first = float(manifest["base_edr_range_ps"]["first"])
            duration = last - first
            if not math.isclose(first, base_first, rel_tol=0.0, abs_tol=TIME_TOLERANCE_PS):
                raise ExtensionError(f"current EDR first time changed: {first} != {base_first}")
            if duration < BASE_DURATION_PS - TIME_TOLERANCE_PS:
                raise ExtensionError(f"current EDR is shorter than the base snapshot: {duration} ps")
            if duration > TARGET_TOTAL_DURATION_PS + TIME_TOLERANCE_PS:
                raise ExtensionError(
                    f"current EDR exceeds the immutable extension target: {duration} ps"
                )

            current_marker_count = finished_marker_count(work / "npt.log")
            duration_complete = math.isclose(
                duration,
                TARGET_TOTAL_DURATION_PS,
                rel_tol=0.0,
                abs_tol=TIME_TOLERANCE_PS,
            )
            # A normal GROMACS append removes the old completed-log suffix and
            # writes one new final marker.  It does not retain base+1 markers.
            marker_complete = current_marker_count >= 1

            if metrics_path.exists():
                if not (duration_complete and marker_complete):
                    raise ExtensionError("immutable PASS metrics exist but outputs are incomplete")
                verify_snapshot(snapshot, manifest["base_snapshot"])
                append_validation = verify_completed_append(
                    gmx_bin,
                    work,
                    snapshot,
                    first,
                    last,
                    base_first,
                )
                metrics = read_json(metrics_path)
                verify_final_metrics(
                    metrics,
                    manifest_path,
                    work,
                    extended_tpr,
                    first,
                    last,
                    append_validation,
                )
                print(json.dumps(metrics, indent=2, ensure_ascii=False))
                return

            attempt_number: int | None = None
            completion_mode = "RESUME_OBSERVED_COMPLETE"
            if not (duration_complete and marker_complete):
                if not (work / "npt.cpt").is_file():
                    raise ExtensionError("npt.cpt is required for checksum-protected append")
                verify_snapshot(snapshot, manifest["base_snapshot"])
                verify_xtc_full_prefix(work, snapshot)
                verify_edr_base_semantics(gmx_bin, work, snapshot, last)

                attempt_dir = extension_dir / "attempts"
                attempt_dir.mkdir(parents=True, exist_ok=True)
                attempt_number = next_attempt_number(attempt_dir)
                attempt_tag = f"attempt_{attempt_number:03d}"
                console_log = attempt_dir / f"{attempt_tag}_mdrun_console.log"
                attempt_metrics_path = attempt_dir / f"{attempt_tag}_metrics.json"
                command = [
                    gmx_bin,
                    "mdrun",
                    "-s",
                    str(extended_tpr),
                    "-deffnm",
                    "npt",
                    "-cpi",
                    "npt.cpt",
                    "-append",
                    "-ntmpi",
                    "1",
                    "-ntomp",
                    str(args.threads),
                    "-pin",
                    "auto",
                    "-cpt",
                    "5",
                ]
                attempt_started = now()
                wall_start = time.monotonic()
                exit_code: int | None = None
                try:
                    exit_code = run_to_new_log(command, work, console_log)
                    if exit_code != 0:
                        raise ExtensionError(
                            f"mdrun extension attempt exited with code {exit_code}: {console_log}"
                        )
                    first, last, check_text = check_edr(gmx_bin, work)
                    write_bytes_once(
                        attempt_dir / f"{attempt_tag}_edr_check.txt",
                        check_text.encode(),
                    )
                    verify_time_range(
                        first,
                        last,
                        base_first,
                        TARGET_TOTAL_DURATION_PS,
                        "post-extension",
                    )
                    current_marker_count = finished_marker_count(work / "npt.log")
                    if current_marker_count < 1:
                        raise ExtensionError("extension Finished mdrun marker is missing")
                    verify_snapshot(snapshot, manifest["base_snapshot"])
                    append_validation = verify_completed_append(
                        gmx_bin,
                        work,
                        snapshot,
                        first,
                        last,
                        base_first,
                    )
                    marker_counts = append_validation["log"]["bad_markers"]
                    attempt_payload = {
                        "attempt": attempt_number,
                        "started_at": attempt_started,
                        "ended_at": now(),
                        "wall_seconds": time.monotonic() - wall_start,
                        "exit_code": 0,
                        "technical_status": "PASS_COMPLETE",
                        "threads": args.threads,
                        "command": command,
                        "edr_range_ps": {
                            "first": first,
                            "last": last,
                            "duration": last - first,
                        },
                        "bad_markers": marker_counts,
                        "append_validation": append_validation,
                        "console_log": console_log.name,
                    }
                    write_json_once(attempt_metrics_path, attempt_payload)
                except Exception as exc:
                    failure_payload = {
                        "attempt": attempt_number,
                        "started_at": attempt_started,
                        "ended_at": now(),
                        "wall_seconds": time.monotonic() - wall_start,
                        "exit_code": exit_code,
                        "technical_status": "FAILED",
                        "threads": args.threads,
                        "command": command,
                        "detail": f"{type(exc).__name__}: {exc}",
                        "console_log": console_log.name,
                    }
                    write_json_once(attempt_metrics_path, failure_payload)
                    raise
                completion_mode = "MDRUN_APPEND"

            verify_time_range(
                first,
                last,
                base_first,
                TARGET_TOTAL_DURATION_PS,
                "final extension",
            )
            verify_snapshot(snapshot, manifest["base_snapshot"])
            append_validation = verify_completed_append(
                gmx_bin,
                work,
                snapshot,
                first,
                last,
                base_first,
            )
            final_metrics = build_final_metrics(
                manifest,
                manifest_path,
                work,
                extended_tpr,
                first,
                last,
                finished_marker_count(work / "npt.log"),
                append_validation,
                completion_mode,
                attempt_number,
            )
            write_json_once(metrics_path, final_metrics)
            print(json.dumps(final_metrics, indent=2, ensure_ascii=False))
        except (ExtensionError, subprocess.CalledProcessError, OSError, KeyError, ValueError) as exc:
            print(f"extension failed safely: {type(exc).__name__}: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
