#!/usr/bin/env python3
"""Run and analyze exploratory NVT 100 ps -> C-rescale NPT for one EM candidate."""

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
import statistics
import subprocess
import sys
import time

PROJECT = Path(__file__).resolve().parents[2]
NEXT = PROJECT / "08_Next_Research"
MDP_DIR = NEXT / "02_Protocol" / "mdp"
BASE_NVT = MDP_DIR / "nvt_100ps_exploratory.mdp"
BASE_NPT = MDP_DIR / "npt_1ns_exploratory.mdp"
MASS_U = 24771.4
DALTON_KG = 1.66053906660e-27
MAC_SAFE_THREADS = 6


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parent_packmol_provenance(
    run_dir: Path, parent_metrics: dict[str, object]
) -> dict[str, object] | None:
    """Validate optional explicit Packmol seed evidence from a new parent build."""
    requested = parent_metrics.get("packmol_seed_requested")
    observed = parent_metrics.get("packmol_seed_observed")
    if requested is None and observed is None:
        return None
    if (
        isinstance(requested, bool)
        or not isinstance(requested, int)
        or isinstance(observed, bool)
        or not isinstance(observed, int)
        or observed != requested
        or not 1 <= requested <= 2_147_483_647
    ):
        raise RuntimeError("parent Packmol requested/observed seed evidence is invalid")
    packmol_input = run_dir / "input" / "pack.inp"
    commands_log = run_dir / "commands.log"
    initial_gro = run_dir / "input" / "initial.gro"
    for path in (packmol_input, commands_log, initial_gro):
        if not path.is_file():
            raise RuntimeError(f"parent Packmol evidence is missing: {path}")
    input_matches = re.findall(
        r"^\s*seed\s+([+-]?\d+)\s*$",
        packmol_input.read_text(),
        re.MULTILINE | re.IGNORECASE,
    )
    log_matches = re.findall(
        r"Seed for random number generator:\s*([+-]?\d+)",
        commands_log.read_text(errors="replace"),
    )
    if len(input_matches) != 1 or len(log_matches) != 1:
        raise RuntimeError("parent Packmol seed evidence is missing or ambiguous")
    if int(input_matches[0]) != requested or int(log_matches[0]) != requested:
        raise RuntimeError("parent Packmol seed evidence disagrees across files")
    return {
        "packmol_seed": requested,
        "packmol_input_sha256": sha256(packmol_input),
        "packmol_log_sha256": sha256(commands_log),
        "packmol_initial_gro_sha256": sha256(initial_gro),
    }


def atomic_write_text(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(content)
    os.replace(temporary, path)


def canonical_json_bytes(value: dict[str, object]) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def write_bytes_once(path: Path, content: bytes) -> None:
    """Create immutable evidence, accepting an already byte-identical file only."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise RuntimeError(f"immutable evidence differs: {path}")
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
                raise RuntimeError(f"immutable evidence race differs: {path}")
    finally:
        temporary.unlink(missing_ok=True)


def write_json_once(path: Path, value: dict[str, object]) -> None:
    write_bytes_once(path, canonical_json_bytes(value))


def file_evidence(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise RuntimeError(f"required evidence file is missing: {path}")
    return {"sha256": sha256(path), "size_bytes": path.stat().st_size}


def copy_file_once(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise RuntimeError(f"immutable evidence source is missing: {source}")
    write_bytes_once(destination, source.read_bytes())


def next_evidence_number(directory: Path, pattern: re.Pattern[str]) -> int:
    numbers: list[int] = []
    if directory.exists():
        for path in directory.iterdir():
            match = pattern.fullmatch(path.name)
            if match:
                numbers.append(int(match.group(1)))
    return max(numbers, default=0) + 1


def snapshot_resume_checkpoint(
    stage: str,
    work: Path,
    checkpoint: Path,
    first_time_ps: float | None,
    last_time_ps: float | None,
) -> dict[str, object]:
    evidence_dir = work / "resume_evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    number = next_evidence_number(
        evidence_dir,
        re.compile(rf"{re.escape(stage)}_resume_(\d{{3}})\.json"),
    )
    stem = f"{stage}_resume_{number:03d}"
    snapshot = evidence_dir / f"{stem}_checkpoint.cpt"
    copy_file_once(checkpoint, snapshot)
    record = {
        "schema_version": "eq-resume-evidence-v1",
        "stage": stage,
        "recorded_at": now(),
        "checkpoint_source_name": checkpoint.name,
        "checkpoint_snapshot": snapshot.relative_to(work).as_posix(),
        "checkpoint_in": file_evidence(snapshot),
        "pre_resume_edr_range_ps": {
            "first": first_time_ps,
            "last": last_time_ps,
            "duration": (
                last_time_ps - first_time_ps
                if first_time_ps is not None and last_time_ps is not None
                else None
            ),
        },
    }
    record_path = evidence_dir / f"{stem}.json"
    write_json_once(record_path, record)
    return {
        "checkpoint_in_sha256": record["checkpoint_in"]["sha256"],
        "resume_evidence_file": record_path.relative_to(work).as_posix(),
        "resume_checkpoint_file": snapshot.relative_to(work).as_posix(),
        "resume_from_time_ps": last_time_ps,
    }


def set_assignment(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^(\s*{re.escape(key)}\s*=\s*).*$", re.MULTILINE)
    replaced, count = pattern.subn(rf"\g<1>{value}", text)
    if count != 1:
        raise ValueError(f"expected exactly one {key} assignment, found {count}")
    return replaced


def require_mac_safe_threads(threads: int) -> None:
    if threads != MAC_SAFE_THREADS:
        raise ValueError(
            f"this Mac safety protocol requires exactly {MAC_SAFE_THREADS} OpenMP threads"
        )


def run_logged(
    command: list[str], cwd: Path, log_path: Path, input_text: str | None = None
) -> None:
    env = os.environ.copy()
    env["GMX_MAXBACKUP"] = "-1"
    with log_path.open("a") as output:
        output.write(f"\n[{now()}] $ {shlex.join(command)}\n")
        output.flush()
        subprocess.run(
            command,
            cwd=cwd,
            input=input_text,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
            check=True,
            env=env,
        )


def capture_logged(command: list[str], cwd: Path, log_path: Path, artifact: Path) -> str:
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
    artifact.write_text(result.stdout)
    with log_path.open("a") as output:
        output.write(f"\n[{now()}] $ {shlex.join(command)}\n")
        output.write(f"output: {artifact.name}\n")
    return result.stdout


def stage_finished(log_path: Path) -> bool:
    return log_path.exists() and "Finished mdrun" in log_path.read_text(errors="replace")


def warning_count(path: Path) -> int:
    if not path.exists():
        return 999
    return len(re.findall(r"\bWARNING\b", path.read_text(errors="replace")))


def bad_markers(paths: list[Path]) -> dict[str, int]:
    text = "\n".join(path.read_text(errors="replace") for path in paths if path.exists())
    return {
        "fatal": len(re.findall(r"fatal error", text, re.IGNORECASE)),
        "nan": len(re.findall(r"\bnan\b", text, re.IGNORECASE)),
        "lincs": len(re.findall(r"lincs warning", text, re.IGNORECASE)),
        "segfault": len(re.findall(r"segmentation fault", text, re.IGNORECASE)),
    }


def parse_rlist(dump: str) -> float:
    match = re.search(r"\brlist\s*=\s*([-+0-9.eE]+)", dump)
    if match is None:
        raise ValueError("rlist not found in TPR dump")
    return float(match.group(1))


def parse_tpr_number(dump: str, key: str) -> float:
    match = re.search(rf"^\s*{re.escape(key)}\s*=\s*([-+0-9.eE]+)\s*$", dump, re.MULTILINE)
    if match is None:
        raise ValueError(f"{key} not found in TPR dump")
    return float(match.group(1))


def verify_tpr_duration(dump: str, expected_steps: int, expected_dt_ps: float) -> None:
    actual_steps = int(parse_tpr_number(dump, "nsteps"))
    actual_dt = parse_tpr_number(dump, "dt")
    if actual_steps != expected_steps or not math.isclose(actual_dt, expected_dt_ps, abs_tol=1e-12):
        raise RuntimeError(
            f"TPR duration mismatch: nsteps={actual_steps}, dt={actual_dt}; "
            f"expected nsteps={expected_steps}, dt={expected_dt_ps}"
        )


def parse_last_energy_time(text: str) -> float:
    match = re.search(r"Last energy frame read\s+\d+\s+time\s+([-+0-9.eE]+)", text)
    if match:
        return float(match.group(1))
    matches = re.findall(r"time\s+([-+0-9.eE]+)", text)
    if not matches:
        raise ValueError("last energy time not found")
    return float(matches[-1])


def parse_energy_range(text: str) -> tuple[float, float]:
    first = re.search(r"frame:\s*0\s+\(index\s+0\),\s*t:\s*([-+0-9.eE]+)", text)
    if first is None:
        first = re.search(r"Reading energy frame\s+0\s+time\s+([-+0-9.eE]+)", text)
    if first is None:
        raise ValueError("first energy time not found")
    return float(first.group(1)), parse_last_energy_time(text)


ENERGY_COLUMNS_BY_STAGE = {
    "nvt": ["Temperature", "Pressure", "Potential"],
    "npt": [
        "Temperature",
        "Pressure",
        "Potential",
        "Density",
        "Volume",
        "Box-X",
        "Box-Y",
        "Box-Z",
    ],
}


def extract_energy(stage: str, work: Path, chain_log: Path) -> list[dict[str, float]]:
    # gmx energy writes multiple selected terms in its internal menu order, not
    # necessarily in the order supplied on stdin.  Extract one term at a time
    # so that column identity never depends on that undocumented ordering.
    if stage not in ENERGY_COLUMNS_BY_STAGE:
        raise ValueError(f"unsupported energy stage: {stage}")
    columns = ENERGY_COLUMNS_BY_STAGE[stage]
    series: dict[str, list[tuple[float, float]]] = {}
    for column in columns:
        safe_name = column.lower().replace("-", "_")
        xvg = work / f"{stage}_{safe_name}.xvg"
        run_logged(
            [
                "gmx",
                "energy",
                "-f",
                f"{stage}.edr",
                "-o",
                xvg.name,
                "-xvg",
                "none",
            ],
            work,
            work / f"{stage}_energy_extract.log",
            f"{column}\n0\n",
        )
        values_for_column: list[tuple[float, float]] = []
        for line in xvg.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "@")):
                continue
            values = [float(value) for value in stripped.split()]
            if len(values) != 2:
                raise ValueError(
                    f"unexpected {stage} {column} column count {len(values)}; expected 2"
                )
            values_for_column.append((values[0], values[1]))
        if not values_for_column:
            raise ValueError(f"no energy rows extracted for {stage} {column}")
        series[column] = values_for_column

    reference_times = [pair[0] for pair in series[columns[0]]]
    for column in columns:
        if len(series[column]) != len(reference_times):
            raise ValueError(
                f"energy row-count mismatch for {stage} {column}: "
                f"{len(series[column])} vs {len(reference_times)}"
            )
    rows: list[dict[str, float]] = []
    for index, time_ps in enumerate(reference_times):
        row: dict[str, float] = {"time_ps": time_ps}
        for column in columns:
            column_time, value = series[column][index]
            if abs(column_time - time_ps) > 1e-9:
                raise ValueError(
                    f"energy time mismatch for {stage} {column}: {column_time} vs {time_ps}"
                )
            row[column] = value
        if not all(math.isfinite(value) for value in row.values()):
            raise ValueError(f"non-finite energy value in {stage} at {time_ps} ps")
        rows.append(row)
    if any(current <= previous for previous, current in zip(reference_times, reference_times[1:])):
        raise ValueError(f"non-increasing energy times in {stage}")
    combined = work / f"{stage}_thermo.xvg"
    combined.write_text(
        "# time_ps " + " ".join(columns) + "\n"
        + "\n".join(
            " ".join([f"{row['time_ps']:.9g}"] + [f"{row[column]:.12g}" for column in columns])
            for row in rows
        )
        + "\n"
    )
    if not rows:
        raise ValueError(f"no energy rows extracted for {stage}")
    with chain_log.open("a") as log:
        log.write(f"[{now()}] extracted {len(rows)} {stage} energy rows\n")
    return rows


def minimum_gro_box_vector(path: Path) -> float:
    values = [float(value) for value in path.read_text().splitlines()[-1].split()]
    if len(values) == 3:
        lengths = values
    elif len(values) == 9:
        ax, by, cz, ay, az, bx, bz, cx, cy = values
        lengths = [
            math.sqrt(ax * ax + ay * ay + az * az),
            math.sqrt(bx * bx + by * by + bz * bz),
            math.sqrt(cx * cx + cy * cy + cz * cz),
        ]
    else:
        raise ValueError(f"unexpected GRO box field count {len(values)} in {path}")
    if not all(math.isfinite(value) and value > 0 for value in lengths):
        raise ValueError(f"invalid GRO box vectors in {path}: {lengths}")
    return min(lengths)


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def slope_per_ns(rows: list[dict[str, float]], key: str) -> float:
    x = [row["time_ps"] for row in rows]
    y = [row[key] for row in rows]
    xbar = mean(x)
    ybar = mean(y)
    denominator = sum((value - xbar) ** 2 for value in x)
    if denominator == 0:
        return 0.0
    per_ps = sum((a - xbar) * (b - ybar) for a, b in zip(x, y)) / denominator
    return per_ps * 1000.0


def window(rows: list[dict[str, float]], start_ps: float) -> list[dict[str, float]]:
    selected = [row for row in rows if row["time_ps"] >= start_ps - 1e-9]
    if len(selected) < 2:
        raise ValueError(f"insufficient rows from {start_ps} ps")
    return selected


def stats(rows: list[dict[str, float]], key: str) -> dict[str, float]:
    values = [row[key] for row in rows]
    return {
        "n": float(len(values)),
        "mean": mean(values),
        "std": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
        "slope_per_ns": slope_per_ns(rows, key),
    }


def equal_time_blocks(
    rows: list[dict[str, float]], start_ps: float, end_ps: float, count: int
) -> list[list[dict[str, float]]]:
    width = (end_ps - start_ps) / count
    blocks: list[list[dict[str, float]]] = []
    for index in range(count):
        lo = start_ps + index * width
        hi = start_ps + (index + 1) * width
        block = [
            row
            for row in rows
            if row["time_ps"] >= lo - 1e-9
            and (row["time_ps"] < hi - 1e-9 or (index == count - 1 and row["time_ps"] <= hi + 1e-9))
        ]
        if not block:
            raise ValueError(f"empty analysis block {index}: {lo}-{hi} ps")
        blocks.append(block)
    return blocks


def max_relative_adjacent_jump(rows: list[dict[str, float]], key: str) -> float:
    jumps = []
    for previous, current in zip(rows, rows[1:]):
        base = abs(previous[key])
        if base > 0:
            jumps.append(abs(current[key] - previous[key]) / base * 100.0)
    return max(jumps, default=0.0)


def symmetric_percent_difference(a: float, b: float) -> float:
    denominator = (abs(a) + abs(b)) / 2.0
    return abs(a - b) / denominator * 100.0 if denominator else 0.0


def analyze(
    nvt: list[dict[str, float]],
    npt: list[dict[str, float]],
    nvt_min_box: float,
    nvt_rlist: float,
    npt_rlist: float,
) -> dict[str, object]:
    nvt_tail = window(nvt, max(50.0, nvt[-1]["time_ps"] - 50.0))
    nvt_start = nvt_tail[0]["time_ps"]
    nvt_end = nvt_tail[-1]["time_ps"]
    nvt_blocks = equal_time_blocks(nvt_tail, nvt_start, nvt_end, 5)
    nvt_temp_blocks = [mean([row["Temperature"] for row in block]) for block in nvt_blocks]
    npt_end = npt[-1]["time_ps"]
    npt_start = max(0.0, npt_end - 500.0)
    npt_tail = window(npt, npt_start)
    blocks = equal_time_blocks(npt, npt_start, npt_end, 5)
    density_blocks = [mean([row["Density"] for row in block]) for block in blocks]
    volume_blocks = [mean([row["Volume"] for row in block]) for block in blocks]
    temp_blocks = [mean([row["Temperature"] for row in block]) for block in blocks]
    pressure_blocks = [mean([row["Pressure"] for row in block]) for block in blocks]
    density_mean = mean([row["Density"] for row in npt_tail])
    block_midpoints = [mean([row["time_ps"] for row in block]) for block in blocks]
    density_block_rows = [
        {"time_ps": time_ps, "Density": density}
        for time_ps, density in zip(block_midpoints, density_blocks)
    ]
    density_slope = slope_per_ns(density_block_rows, "Density")
    density_slope_percent = abs(density_slope) / abs(density_mean) * 100.0
    last_two_diff = symmetric_percent_difference(density_blocks[-1], density_blocks[-2])
    adjacent_diff = max(symmetric_percent_difference(a, b) for a, b in zip(density_blocks, density_blocks[1:]))
    first_half_density = mean([row["Density"] for row in npt_tail if row["time_ps"] < npt_start + 250.0])
    second_half_density = mean([row["Density"] for row in npt_tail if row["time_ps"] >= npt_start + 250.0])
    half_diff = symmetric_percent_difference(first_half_density, second_half_density)
    npt_min_box = min(min(row["Box-X"], row["Box-Y"], row["Box-Z"]) for row in npt)
    nvt_margin = nvt_min_box / (2.0 * nvt_rlist)
    npt_margin = npt_min_box / (2.0 * npt_rlist)
    nvt_temp = stats(nvt_tail, "Temperature")
    npt_temp = stats(npt_tail, "Temperature")
    nvt_last_two_temp_diff = abs(nvt_temp_blocks[-1] - nvt_temp_blocks[-2])
    max_volume_jump = max_relative_adjacent_jump(npt, "Volume")
    hard_fail_reasons: list[str] = []
    if nvt_margin <= 1.0 or npt_margin <= 1.0:
        hard_fail_reasons.append("minimum_image_cutoff_violation")
    if not (293.0 <= nvt_temp["mean"] <= 303.0):
        hard_fail_reasons.append("nvt_temperature_mean_outside_293_303_K")
    if not (293.0 <= npt_temp["mean"] <= 303.0):
        hard_fail_reasons.append("npt_temperature_mean_outside_293_303_K")
    if max_volume_jump > 5.0:
        hard_fail_reasons.append("adjacent_volume_jump_above_5_percent")
    hard_fail = bool(hard_fail_reasons)
    green = (
        not hard_fail
        and nvt_margin >= 1.10
        and npt_margin >= 1.10
        and density_slope_percent <= 1.0
        and last_two_diff <= 1.0
        and adjacent_diff <= 2.0
        and abs(nvt_temp["slope_per_ns"]) <= 2.0
        and nvt_last_two_temp_diff <= 3.0
        and abs(npt_temp["slope_per_ns"]) <= 2.0
    )
    verdict = "SCREEN_STATIONARITY_PASS" if green else ("SCREEN_FAIL" if hard_fail else "SCREEN_EXTEND")
    return {
        "nvt_last_50ps": {
            "Temperature": nvt_temp,
            "temperature_10ps_blocks_K": nvt_temp_blocks,
            "last_two_temperature_block_diff_K": nvt_last_two_temp_diff,
        },
        "npt_last_500ps": {
            "Density": stats(npt_tail, "Density"),
            "Volume": stats(npt_tail, "Volume"),
            "Temperature": npt_temp,
            "Pressure": stats(npt_tail, "Pressure"),
            "Potential": stats(npt_tail, "Potential"),
        },
        "npt_100ps_blocks": {
            "Density": density_blocks,
            "Volume": volume_blocks,
            "Temperature": temp_blocks,
            "Pressure": pressure_blocks,
        },
        "density_slope_percent_per_ns": density_slope_percent,
        "density_last_two_block_diff_percent": last_two_diff,
        "density_max_adjacent_block_diff_percent": adjacent_diff,
        "density_first_vs_second_250ps_diff_percent": half_diff,
        "max_adjacent_volume_jump_percent": max_volume_jump,
        "nvt_min_box_nm": nvt_min_box,
        "npt_min_box_nm": npt_min_box,
        "nvt_rlist_nm": nvt_rlist,
        "npt_rlist_nm": npt_rlist,
        "nvt_min_box_over_2rlist": nvt_margin,
        "npt_min_box_over_2rlist": npt_margin,
        "hard_fail_reasons": hard_fail_reasons,
        "exploratory_verdict": verdict,
        "physics_status": "EXPLORATORY_ONLY",
        "equilibrium_validated": False,
        "production_ready": False,
    }


def ensure_mdrun(stage: str, work: Path, threads: int, target_ps: float, chain_log: Path) -> dict[str, object]:
    require_mac_safe_threads(threads)
    native_log = work / f"{stage}.log"
    resumed = False
    resume_evidence: dict[str, object] = {
        "checkpoint_in_sha256": "",
        "resume_evidence_file": "",
        "resume_checkpoint_file": "",
        "resume_from_time_ps": None,
    }
    first_time: float | None = None
    last_time: float | None = None
    edr = work / f"{stage}.edr"
    if edr.exists():
        precheck = capture_logged(
            ["gmx", "check", "-e", edr.name],
            work,
            chain_log,
            work / f"{stage}_edr_precheck.txt",
        )
        first_time, last_time = parse_energy_range(precheck)
    duration_complete = (
        first_time is not None
        and last_time is not None
        and last_time - first_time + 1e-6 >= target_ps
    )
    if not (stage_finished(native_log) and duration_complete):
        command = [
            "gmx",
            "mdrun",
            "-deffnm",
            stage,
            "-ntmpi",
            "1",
            "-ntomp",
            str(threads),
            "-pin",
            "on",
            "-cpt",
            "5",
        ]
        checkpoint = work / f"{stage}.cpt"
        partial_artifacts = any((work / f"{stage}{suffix}").exists() for suffix in (".edr", ".xtc", ".log"))
        if checkpoint.exists():
            resume_evidence = snapshot_resume_checkpoint(
                stage,
                work,
                checkpoint,
                first_time,
                last_time,
            )
            command += ["-cpi", checkpoint.name, "-append"]
            resumed = True
        elif partial_artifacts:
            raise RuntimeError(f"{stage}: partial artifacts exist without checkpoint")
        run_logged(command, work, work / f"{stage}_mdrun_console.log")
    if not stage_finished(native_log):
        raise RuntimeError(f"{stage}: Finished mdrun marker missing")
    check = capture_logged(
        ["gmx", "check", "-e", f"{stage}.edr"],
        work,
        chain_log,
        work / f"{stage}_edr_check.txt",
    )
    first_time, last_time = parse_energy_range(check)
    duration = last_time - first_time
    if duration + 1e-6 < target_ps:
        raise RuntimeError(
            f"{stage}: energy duration {duration} ps ({first_time} to {last_time}) "
            f"< target {target_ps} ps"
        )
    if (work / f"{stage}.xtc").exists():
        capture_logged(
            ["gmx", "check", "-f", f"{stage}.xtc"],
            work,
            chain_log,
            work / f"{stage}_xtc_check.txt",
        )
    return {
        "resumed": resumed,
        "first_time_ps": first_time,
        "last_time_ps": last_time,
        "duration_ps": duration,
        **resume_evidence,
    }


def write_record(path: Path, payload: dict[str, object]) -> None:
    status = payload.get("technical_status", "FAILED")
    physics = payload.get("physics_status", "NOT_EVALUATED")
    path.write_text(
        f"""# Exploratory equilibration record

- Chain: {payload.get('chain_id')}
- Start: {payload.get('start')}
- End: {payload.get('end')}
- Technical status: {status}
- Physics status: {physics}
- Detail: {payload.get('detail')}

This chain is an initial-density sensitivity pilot. It does not validate the force field, equilibrium density, production trajectory, or transport properties.
"""
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--npt-ps", type=float, default=1000.0)
    parser.add_argument("--threads", type=int, default=MAC_SAFE_THREADS)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.npt_ps < 1000.0:
        raise SystemExit("exploratory screen requires --npt-ps >= 1000")
    try:
        require_mac_safe_threads(args.threads)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    run_dir = args.run_dir.resolve()
    parent_metrics_preview: dict[str, object] = {}
    parent_metrics_path = run_dir / "metrics.json"
    if parent_metrics_path.is_file():
        loaded_parent = json.loads(parent_metrics_path.read_text())
        if not isinstance(loaded_parent, dict):
            raise SystemExit("parent metrics must be a JSON object")
        parent_metrics_preview = loaded_parent
    try:
        inherited_packmol = parent_packmol_provenance(run_dir, parent_metrics_preview)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    work = run_dir / "equilibration"
    if work.exists() and not args.resume:
        raise SystemExit(f"equilibration directory exists; use --resume: {work}")
    if (work / "extensions").exists():
        raise SystemExit(
            "base equilibration is frozen after extension preparation; "
            "use extend_npt.py/analyze_npt_extension.py and do not rerun the base worker"
        )
    work.mkdir(parents=True, exist_ok=True)
    lock_handle = (work / ".chain.lock").open("a+")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise SystemExit(f"another process holds the chain lock: {work}") from exc
    chain_log = work / "chain.log"
    attempts_dir = work / "attempts"
    attempts_dir.mkdir(parents=True, exist_ok=True)
    attempt_number = next_evidence_number(
        attempts_dir,
        re.compile(r"attempt_(\d{3})_started\.json"),
    )
    attempt_tag = f"attempt_{attempt_number:03d}"
    previous_metrics_path = work / "equilibration_metrics.json"
    previous_metrics_snapshot = ""
    previous_metrics_evidence: dict[str, object] | None = None
    if previous_metrics_path.is_file():
        previous_snapshot_path = attempts_dir / f"{attempt_tag}_previous_metrics.json"
        copy_file_once(previous_metrics_path, previous_snapshot_path)
        previous_metrics_snapshot = previous_snapshot_path.relative_to(work).as_posix()
        previous_metrics_evidence = file_evidence(previous_snapshot_path)
    attempt_started_path = attempts_dir / f"{attempt_tag}_started.json"
    write_json_once(
        attempt_started_path,
        {
            "schema_version": "eq-attempt-v1",
            "attempt": attempt_number,
            "chain_id": run_dir.name,
            "started_at": now(),
            "resume_requested": args.resume,
            "requested_seed": args.seed,
            "requested_velocity_seed": args.seed,
            "seed_semantics": "gromacs_nvt_gen_seed",
            "inherited_packmol_seed": (
                inherited_packmol["packmol_seed"] if inherited_packmol else None
            ),
            "requested_npt_ps": args.npt_ps,
            "requested_threads": args.threads,
            "previous_metrics_snapshot": previous_metrics_snapshot,
            "previous_metrics_evidence": previous_metrics_evidence,
        },
    )
    start = now()
    wall_start = time.monotonic()
    payload: dict[str, object] = {
        "chain_id": run_dir.name,
        "start": start,
        "technical_status": "FAILED",
        "physics_status": "NOT_EVALUATED",
        "detail": "chain did not finish",
        "attempt": attempt_number,
        "attempt_started_record": attempt_started_path.relative_to(work).as_posix(),
        "resume_requested": args.resume,
    }

    try:
        validation = json.loads((run_dir / "validation.json").read_text())
        if not validation.get("all_passed"):
            raise RuntimeError("candidate validation did not pass")
        parent_metrics = json.loads((run_dir / "metrics.json").read_text())
        if parent_metrics != parent_metrics_preview:
            raise RuntimeError("parent metrics changed after preflight provenance check")
        if parent_metrics.get("grompp_warning_count") != 0 or not parent_metrics.get("em_summary", {}).get("converged"):
            raise RuntimeError("parent EM technical gate did not pass")
        for source, target in (
            (run_dir / "em.gro", work / "start_em.gro"),
            (run_dir / "input" / "topol.top", work / "topol.top"),
        ):
            if not target.exists():
                shutil.copy2(source, target)

        nvt_text = set_assignment(BASE_NVT.read_text(), "gen-seed", str(args.seed)).rstrip("\n") + "\n\n"
        npt_steps = int(round(args.npt_ps / 0.001))
        npt_text = set_assignment(BASE_NPT.read_text(), "nsteps", str(npt_steps)).rstrip("\n") + "\n\n"
        nvt_mdp = work / "nvt_100ps.mdp"
        npt_mdp = work / f"npt_{args.npt_ps:g}ps.mdp"
        if not nvt_mdp.exists():
            nvt_mdp.write_text(nvt_text)
        elif nvt_mdp.read_text() != nvt_text:
            raise RuntimeError("existing NVT MDP differs from requested fixed-seed MDP")
        if not npt_mdp.exists():
            npt_mdp.write_text(npt_text)
        elif npt_mdp.read_text() != npt_text:
            raise RuntimeError("existing NPT MDP differs from requested duration")

        input_hashes = {
            path.name: sha256(path)
            for path in (work / "start_em.gro", work / "topol.top", nvt_mdp, npt_mdp)
        }
        input_hash_path = work / "INPUT_SHA256.json"
        if input_hash_path.exists():
            if json.loads(input_hash_path.read_text()) != input_hashes:
                raise RuntimeError("resume input hashes differ from write-once INPUT_SHA256.json")
        else:
            atomic_write_text(input_hash_path, json.dumps(input_hashes, indent=2) + "\n")
        gmx_version = subprocess.run(
            ["gmx", "--version"],
            cwd=work,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=True,
        ).stdout
        version_line = next(
            (line.strip() for line in gmx_version.splitlines() if "GROMACS version:" in line),
            "GROMACS version: unknown",
        )
        requested_manifest = {
            "protocol_version": "eq-screen-v2",
            "seed": args.seed,
            "npt_ps": args.npt_ps,
            "npt_steps": npt_steps,
            "dt_ps": 0.001,
            "input_sha256": input_hashes,
            "parent_em_sha256": sha256(run_dir / "em.gro"),
            "parent_topology_sha256": sha256(run_dir / "input" / "topol.top"),
            "gromacs_version": version_line,
        }
        if inherited_packmol is not None:
            requested_manifest["velocity_seed"] = args.seed
            requested_manifest["seed_semantics"] = "gromacs_nvt_gen_seed"
            requested_manifest["parent_packmol_provenance"] = inherited_packmol
        manifest_path = work / "chain_manifest.json"
        if manifest_path.exists():
            if json.loads(manifest_path.read_text()) != requested_manifest:
                raise RuntimeError("resume request differs from immutable chain_manifest.json")
        else:
            atomic_write_text(
                manifest_path,
                json.dumps(requested_manifest, indent=2, ensure_ascii=False) + "\n",
            )

        if not (work / "nvt.tpr").exists():
            run_logged(
                [
                    "gmx",
                    "grompp",
                    "-f",
                    nvt_mdp.name,
                    "-c",
                    "start_em.gro",
                    "-p",
                    "topol.top",
                    "-o",
                    "nvt.tpr",
                    "-po",
                    "nvt_out.mdp",
                ],
                work,
                work / "grompp_nvt.log",
            )
        if warning_count(work / "grompp_nvt.log") != 0:
            raise RuntimeError("NVT grompp warnings detected")
        nvt_dump = capture_logged(
            ["gmx", "dump", "-s", "nvt.tpr"],
            work,
            chain_log,
            work / "nvt_tpr_dump.txt",
        )
        verify_tpr_duration(nvt_dump, 100000, 0.001)
        nvt_run = ensure_mdrun("nvt", work, args.threads, 100.0, chain_log)

        if not (work / "npt.tpr").exists():
            run_logged(
                [
                    "gmx",
                    "grompp",
                    "-f",
                    npt_mdp.name,
                    "-c",
                    "nvt.gro",
                    "-t",
                    "nvt.cpt",
                    "-p",
                    "topol.top",
                    "-o",
                    "npt.tpr",
                    "-po",
                    "npt_out.mdp",
                ],
                work,
                work / "grompp_npt.log",
            )
        if warning_count(work / "grompp_npt.log") != 0:
            raise RuntimeError("NPT grompp warnings detected")
        npt_dump = capture_logged(
            ["gmx", "dump", "-s", "npt.tpr"],
            work,
            chain_log,
            work / "npt_tpr_dump.txt",
        )
        verify_tpr_duration(npt_dump, npt_steps, 0.001)
        npt_run = ensure_mdrun("npt", work, args.threads, args.npt_ps, chain_log)

        marker_counts = bad_markers(
            [
                work / "nvt.log",
                work / "npt.log",
                work / "nvt_mdrun_console.log",
                work / "npt_mdrun_console.log",
            ]
        )
        if any(marker_counts.values()):
            raise RuntimeError(f"bad runtime markers: {marker_counts}")
        nvt_rows = extract_energy("nvt", work, chain_log)
        npt_rows = extract_energy("npt", work, chain_log)
        analysis = analyze(
            nvt_rows,
            npt_rows,
            minimum_gro_box_vector(work / "nvt.gro"),
            parse_rlist(nvt_dump),
            parse_rlist(npt_dump),
        )
        payload.update(
            {
                "technical_status": "PASS_COMPLETE",
                "physics_status": analysis["physics_status"],
                "detail": "configured exploratory NVT 100 ps and C-rescale NPT completed and analyzed",
                "seed": args.seed,
                "npt_target_ps": args.npt_ps,
                "nvt": nvt_run,
                "npt": npt_run,
                "nvt_rlist_nm": parse_rlist(nvt_dump),
                "npt_rlist_nm": parse_rlist(npt_dump),
                "bad_markers": marker_counts,
                "grompp_warnings": {
                    "nvt": warning_count(work / "grompp_nvt.log"),
                    "npt": warning_count(work / "grompp_npt.log"),
                },
                "analysis": analysis,
                "input_sha256": input_hashes,
            }
        )
        if inherited_packmol is not None:
            payload["velocity_seed"] = args.seed
            payload["seed_semantics"] = "gromacs_nvt_gen_seed"
            payload["parent_packmol_provenance"] = inherited_packmol
    except Exception as exc:
        payload["detail"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        payload["end"] = now()
        payload["wall_seconds"] = time.monotonic() - wall_start
        metrics_path = work / "equilibration_metrics.json"
        metrics_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        )
        write_record(work / "EQUILIBRATION_RECORD.md", payload)
        immutable_metrics_path = attempts_dir / f"{attempt_tag}_metrics.json"
        copy_file_once(metrics_path, immutable_metrics_path)
        write_json_once(
            attempts_dir / f"{attempt_tag}_final.json",
            {
                "schema_version": "eq-attempt-v1",
                "attempt": attempt_number,
                "chain_id": run_dir.name,
                "ended_at": payload["end"],
                "technical_status": payload["technical_status"],
                "physics_status": payload["physics_status"],
                "metrics_snapshot": immutable_metrics_path.relative_to(work).as_posix(),
                "metrics_evidence": file_evidence(immutable_metrics_path),
            },
        )


if __name__ == "__main__":
    main()
