#!/usr/bin/env python3
"""Read-only preflight for simulation, reporting, and selected backup."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_HANDOFF_SHA256 = (
    "9da4e4eb5ea33089520a2362cbcb84bf996ccee3093eed20f45b1e0d586eba88"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command_version(command: str, args: list[str]) -> dict[str, object]:
    path = shutil.which(command)
    if path is None:
        return {"status": "MISSING", "path": None, "version_line": None}
    completed = subprocess.run(
        [path, *args], capture_output=True, text=True, timeout=20, check=False
    )
    output = (completed.stdout + completed.stderr).splitlines()
    first = next((line.strip() for line in output if line.strip()), "")
    return {
        "status": "PASS" if completed.returncode == 0 else "AVAILABLE_NONZERO_VERSION",
        "path": path,
        "version_line": first,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    checks = {}
    warnings = []
    failures = []

    commands = {
        "gmx": ["--version"],
        "packmol": [],
        "pandoc": ["--version"],
        "latexmk": ["--version"],
        "git": ["--version"],
        "zip": ["-v"],
    }
    for command, version_args in commands.items():
        result = command_version(command, version_args)
        checks[f"command:{command}"] = result
        if result["status"] == "MISSING":
            failures.append(f"missing command: {command}")

    packages = (
        "numpy",
        "pandas",
        "scipy",
        "matplotlib",
        "seaborn",
        "jupyter",
        "notebook",
        "jupyterlab",
        "openpyxl",
    )
    for package in packages:
        try:
            version = importlib.metadata.version(package)
            checks[f"python:{package}"] = {"status": "PASS", "version": version}
        except importlib.metadata.PackageNotFoundError:
            checks[f"python:{package}"] = {"status": "MISSING"}
            failures.append(f"missing Python package: {package}")

    required_paths = (
        "environment.yml",
        "Brewfile",
        ".gitignore",
        "05_Report/2026_Final/report_source.md",
        "05_Report/2026_Final/RESULTS_TABLE.csv",
        "05_Report/2026_Final/FIGURE_MANIFEST.csv",
        "09_Research_Environment/backup_policy.json",
        "09_Research_Environment/drive_folder_map.json",
    )
    for relative in required_paths:
        exists = (PROJECT_ROOT / relative).is_file()
        checks[f"file:{relative}"] = {"status": "PASS" if exists else "MISSING"}
        if not exists:
            failures.append(f"missing required file: {relative}")

    handoff = (
        PROJECT_ROOT
        / "07_Handoff"
        / "To_Professor"
        / "CILE_MD_Systems_20260806.zip"
    )
    handoff_hash = sha256(handoff) if handoff.is_file() else None
    checks["professor_handoff"] = {
        "status": "PASS" if handoff_hash == EXPECTED_HANDOFF_SHA256 else "FAIL",
        "sha256": handoff_hash,
    }
    if handoff_hash != EXPECTED_HANDOFF_SHA256:
        failures.append("professor handoff ZIP missing or SHA-256 mismatch")

    disk = shutil.disk_usage(PROJECT_ROOT)
    free_gib = disk.free / (1024**3)
    checks["disk_free"] = {"status": "PASS" if free_gib >= 80 else "WARN", "gib": free_gib}
    if free_gib < 80:
        warnings.append(f"free disk is {free_gib:.1f} GiB; 80 GiB or more is recommended")

    git_dir = PROJECT_ROOT / ".git"
    checks["git_repository"] = {"status": "PASS" if git_dir.is_dir() else "WARN"}
    if not git_dir.is_dir():
        warnings.append("Git repository is not initialized")

    drive_desktop = Path("/Applications/Google Drive.app").is_dir()
    checks["google_drive_desktop"] = {
        "status": "PASS" if drive_desktop else "OPTIONAL_MISSING"
    }
    if not drive_desktop:
        warnings.append("Google Drive desktop is not installed; connector uploads are used")

    payload = {
        "schema_version": "cile-environment-preflight-v1",
        "status": "FAIL" if failures else ("READY_WITH_WARNINGS" if warnings else "READY"),
        "checks": checks,
        "warnings": warnings,
        "failures": failures,
        "verification_scope": {
            "implemented": "local configuration and read-only preflight",
            "not_verified": [
                "fresh conda environment recreation",
                "laboratory Linux server recreation",
                "external SSD backup",
            ],
        },
    }
    rendered = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.output:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
        temporary.write_text(rendered, encoding="utf-8")
        os.replace(temporary, output)
    print(rendered, end="")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
