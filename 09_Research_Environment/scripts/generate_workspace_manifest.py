#!/usr/bin/env python3
"""Create an upload-safe inventory of the CILE workspace.

Secret-like files are counted but omitted from the uploadable manifest. Large
MD outputs remain listed by size and SHA-256 so an external/server copy can be
verified without placing the trajectory itself in Google Drive.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "09_Research_Environment" / "manifests" / "workspace_manifest.csv"
)
HEAVY_EXTENSIONS = {".xtc", ".trr", ".edr", ".cpt", ".tpr"}
SECRET_PATTERNS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*credentials*.json",
    "*service-account*.json",
)
SKIP_PREFIXES = (
    ".git/",
    "09_Research_Environment/backups/",
    "09_Research_Environment/manifests/",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_secret(relative: str) -> bool:
    name = Path(relative).name
    return any(fnmatch.fnmatch(name, pattern) for pattern in SECRET_PATTERNS)


def classify(relative: str, path: Path) -> str:
    lower = relative.lower()
    if relative == "07_Handoff/To_Professor/CILE_MD_Systems_20260806.zip":
        return "DRIVE_PROFESSOR_HANDOFF"
    if path.suffix.lower() in HEAVY_EXTENSIONS:
        return "EXTERNAL_OR_SERVER_ONLY"
    if path.suffix.lower() == ".pdb" and (
        "animation" in path.name.lower() or "sampled" in path.name.lower()
    ):
        return "EXTERNAL_OR_SERVER_ONLY"
    if lower.startswith("99_old_backup/"):
        return "LOCAL_ARCHIVE_ONLY"
    if path.suffix.lower() == ".zip":
        return "LOCAL_ARCHIVE_ONLY"
    selected_prefixes = (
        "04_Figures_For_Report/",
        "05_Report/",
        "08_Next_Research/02_Protocol/",
        "08_Next_Research/03_Environments/",
        "08_Next_Research/05_QC/",
        "08_Next_Research/06_Reproducibility/",
        "08_Next_Research/scripts/",
        "08_Next_Research/tests/",
        "09_Research_Environment/",
    )
    if relative.startswith(selected_prefixes):
        return "DRIVE_SELECTED_PACKAGE"
    if path.suffix.lower() in {".md", ".py", ".csv", ".json", ".yml", ".yaml"}:
        return "VERSION_CONTROL_REVIEW"
    return "LOCAL_REVIEW"


def iter_files(root: Path):
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if relative.startswith(SKIP_PREFIXES):
            continue
        yield relative, path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    secret_omitted = 0
    for relative, path in iter_files(root):
        if is_secret(relative):
            secret_omitted += 1
            continue
        stat = path.stat()
        rows.append(
            {
                "relative_path": relative,
                "size_bytes": stat.st_size,
                "modified_utc": dt.datetime.fromtimestamp(
                    stat.st_mtime, tz=dt.timezone.utc
                ).isoformat(timespec="seconds"),
                "sha256": sha256(path),
                "storage_class": classify(relative, path),
            }
        )

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=(
                    "relative_path",
                    "size_bytes",
                    "modified_utc",
                    "sha256",
                    "storage_class",
                ),
            )
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, output)
    finally:
        Path(temporary_name).unlink(missing_ok=True)

    counts: dict[str, int] = {}
    bytes_by_class: dict[str, int] = {}
    for row in rows:
        key = row["storage_class"]
        counts[key] = counts.get(key, 0) + 1
        bytes_by_class[key] = bytes_by_class.get(key, 0) + int(row["size_bytes"])
    summary = {
        "schema_version": "cile-workspace-manifest-summary-v1",
        "generated_at": dt.datetime.now(tz=dt.timezone.utc).isoformat(timespec="seconds"),
        "root_name": root.name,
        "file_count": len(rows),
        "total_size_bytes": sum(int(row["size_bytes"]) for row in rows),
        "secret_like_files_omitted_count": secret_omitted,
        "counts_by_storage_class": counts,
        "bytes_by_storage_class": bytes_by_class,
        "manifest_sha256": sha256(output),
    }
    summary_path = output.with_name("workspace_manifest_summary.json")
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
