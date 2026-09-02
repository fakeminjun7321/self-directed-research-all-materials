#!/usr/bin/env python3
"""Focused tests for report evidence and upload-safe backup artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import unittest
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_RESULTS = PROJECT_ROOT / "05_Report/2026_Final/RESULTS_TABLE.csv"
QC_ROOT = PROJECT_ROOT / "08_Next_Research/05_QC"
BACKUP_ROOT = PROJECT_ROOT / "09_Research_Environment/backups"


class EnvironmentArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with REPORT_RESULTS.open(newline="", encoding="utf-8") as handle:
            cls.rows = {row["result_id"]: row for row in csv.DictReader(handle)}
        cls.three_ns = json.loads((QC_ROOT / "three_ns_screen.json").read_text())
        cls.replica = json.loads(
            (QC_ROOT / "replica_1ns_comparison.json").read_text()
        )

    def test_report_values_are_bound_to_qc_json(self) -> None:
        three_ns_values = {
            "R001": self.three_ns["chains"][0]["last1ns_density_mean_kg_m3"],
            "R002": self.three_ns["chains"][1]["last1ns_density_mean_kg_m3"],
            "R003": self.three_ns["chains"][2]["last1ns_density_mean_kg_m3"],
            "R004": self.three_ns["last1ns_density_spread_percent"],
        }
        replica_values = {
            "R101": self.replica["replicas"][0]["last500_density_mean_kg_m3"],
            "R102": self.replica["replicas"][1]["last500_density_mean_kg_m3"],
            "R103": self.replica["replicas"][2]["last500_density_mean_kg_m3"],
            "R104": self.replica["density_statistics"]["spread_percent"],
            "R105": self.replica["density_statistics"]["replica_mean_kg_m3"],
        }
        for result_id, expected in {**three_ns_values, **replica_values}.items():
            rendered = self.rows[result_id]["value"]
            decimal_places = len(rendered.partition(".")[2])
            rounding_tolerance = 0.5 * 10 ** (-decimal_places)
            self.assertLessEqual(abs(float(rendered) - expected), rounding_tolerance)

    def test_report_does_not_claim_equilibrium(self) -> None:
        self.assertFalse(self.three_ns["equilibrium_validated"])
        self.assertFalse(self.replica["equilibrium_validated"])
        self.assertEqual(
            self.rows["R105"]["verdict"], "EXPLORATORY_ONLY_NOT_EQUILIBRIUM"
        )

    def test_latest_backup_archives_are_upload_safe(self) -> None:
        dated = sorted(path for path in BACKUP_ROOT.glob("20*") if path.is_dir())
        if not dated:
            self.skipTest("backup packages have not been built yet")
        forbidden_suffixes = {".xtc", ".trr", ".edr", ".cpt", ".tpr"}
        for archive in dated[-1].glob("*.zip"):
            with zipfile.ZipFile(archive) as bundle:
                for name in bundle.namelist():
                    self.assertNotIn(Path(name).suffix.lower(), forbidden_suffixes)
                    lowered = Path(name).name.lower()
                    self.assertFalse(lowered.endswith((".pem", ".key")))
                    self.assertFalse(lowered == ".env" or lowered.startswith(".env."))

    def test_backup_checksums_match(self) -> None:
        dated = sorted(path for path in BACKUP_ROOT.glob("20*") if path.is_dir())
        if not dated:
            self.skipTest("backup packages have not been built yet")
        directory = dated[-1]
        for line in (directory / "SHA256SUMS").read_text().splitlines():
            expected, filename = line.split(maxsplit=1)
            actual = hashlib.sha256((directory / filename).read_bytes()).hexdigest()
            self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
