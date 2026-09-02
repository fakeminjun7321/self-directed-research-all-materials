#!/usr/bin/env python3
"""Synthetic tests for the cumulative 3 ns extension analysis."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


PROJECT = Path(__file__).resolve().parents[2]


def load_script(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, PROJECT / relative_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {relative_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


extension_analysis = load_script(
    "analyze_npt_extension_under_test",
    "08_Next_Research/scripts/analyze_npt_extension.py",
)


def synthetic_rows(
    *,
    box_nm: float = 3.0,
    final_temperature_K: float = 298.0,
    density_drift_kg_m3_per_ns: float = 0.0,
):
    rows = []
    for time_ps in range(0, 3001, 10):
        final_elapsed_ns = max(0.0, time_ps - 2000.0) / 1000.0
        density = 1200.0 + density_drift_kg_m3_per_ns * final_elapsed_ns
        temperature = final_temperature_K if time_ps >= 2000 else 298.0
        rows.append(
            {
                "time_ps": float(time_ps),
                "Temperature": temperature,
                "Pressure": 1.0,
                "Potential": -1000.0,
                "Density": density,
                "Volume": box_nm**3,
                "Box-X": box_nm,
                "Box-Y": box_nm,
                "Box-Z": box_nm,
            }
        )
    return rows


class ExtensionAnalysisMathTests(unittest.TestCase):
    def test_constant_three_ns_is_only_a_stationarity_candidate(self):
        result = extension_analysis.analyze_rows(synthetic_rows(), rlist_nm=1.2)

        self.assertEqual(
            result["exploratory_verdict"],
            "THREE_NS_STATIONARITY_CANDIDATE",
        )
        self.assertEqual(len(result["blocks_200ps"]), 5)
        self.assertEqual(
            [block["start_ps"] for block in result["blocks_200ps"]],
            [2000.0, 2200.0, 2400.0, 2600.0, 2800.0],
        )
        self.assertAlmostEqual(
            result["density_qc"]["one_to_two_vs_two_to_three_ns_diff_percent"],
            0.0,
        )
        self.assertFalse(result["equilibrium_validated"])
        self.assertFalse(result["production_ready"])

    def test_density_drift_requires_extension_or_review(self):
        result = extension_analysis.analyze_rows(
            synthetic_rows(density_drift_kg_m3_per_ns=18.0),
            rlist_nm=1.2,
        )

        self.assertEqual(result["exploratory_verdict"], "THREE_NS_EXTEND_OR_REVIEW")
        self.assertIn(
            "density_slope_above_0_5_percent_per_ns",
            result["review_reasons"],
        )

    def test_temperature_and_minimum_image_violation_are_hard_failures(self):
        result = extension_analysis.analyze_rows(
            synthetic_rows(box_nm=2.3, final_temperature_K=310.0),
            rlist_nm=1.2,
        )

        self.assertEqual(result["exploratory_verdict"], "THREE_NS_FAIL")
        self.assertIn("minimum_image_cutoff_violation", result["hard_fail_reasons"])
        self.assertIn(
            "temperature_mean_outside_293_303_K",
            result["hard_fail_reasons"],
        )

    def test_adjacent_volume_jump_above_five_percent_is_a_hard_failure(self):
        rows = synthetic_rows()
        rows[150]["Volume"] *= 1.06

        result = extension_analysis.analyze_rows(rows, rlist_nm=1.2)

        self.assertEqual(result["exploratory_verdict"], "THREE_NS_FAIL")
        self.assertIn(
            "adjacent_volume_jump_above_5_percent",
            result["hard_fail_reasons"],
        )
        self.assertGreater(
            result["volume_qc"]["max_adjacent_frame_jump_percent_0_3ns"],
            5.0,
        )

    def test_cutoff_margin_between_one_and_one_point_one_forbids_time_extension(self):
        result = extension_analysis.analyze_rows(
            synthetic_rows(box_nm=2.5),
            rlist_nm=1.2,
        )

        self.assertEqual(result["exploratory_verdict"], "THREE_NS_EXTEND_OR_REVIEW")
        self.assertFalse(result["box_qc"]["time_extension_allowed_by_margin"])
        self.assertIn(
            "cutoff_margin_below_1_10_time_extension_prohibited",
            result["review_reasons"],
        )


class SafeExtractionTests(unittest.TestCase):
    def fake_extractor(self, mismatched_term=None):
        def fake(gmx_bin, edr, term, output, cwd):
            del gmx_bin, edr, cwd
            end = 2999.0 if term == mismatched_term else 3000.0
            output.write_text(f"0 1\n{end:g} 2\n")

        return fake

    def test_extracts_each_named_term_independently(self):
        with tempfile.TemporaryDirectory() as temporary:
            cwd = Path(temporary)
            edr = cwd / "npt.edr"
            edr.write_bytes(b"synthetic")
            with mock.patch.object(
                extension_analysis,
                "run_energy_term",
                side_effect=self.fake_extractor(),
            ) as runner:
                rows = extension_analysis.extract_energy("gmx", edr, cwd)

        self.assertEqual(len(rows), 2)
        self.assertEqual(runner.call_count, len(extension_analysis.ENERGY_TERMS))
        self.assertEqual(
            [call.args[2] for call in runner.call_args_list],
            list(extension_analysis.ENERGY_TERMS),
        )

    def test_rejects_mismatched_term_time_axis(self):
        with tempfile.TemporaryDirectory() as temporary:
            cwd = Path(temporary)
            edr = cwd / "npt.edr"
            edr.write_bytes(b"synthetic")
            with mock.patch.object(
                extension_analysis,
                "run_energy_term",
                side_effect=self.fake_extractor("Pressure"),
            ):
                with self.assertRaisesRegex(
                    extension_analysis.AnalysisError,
                    "energy time mismatch for Pressure",
                ):
                    extension_analysis.extract_energy("gmx", edr, cwd)


class WriteOnceAndMainTests(unittest.TestCase):
    def test_write_json_once_accepts_identical_and_rejects_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "analysis.json"
            extension_analysis.write_json_once(path, {"value": 1})
            extension_analysis.write_json_once(path, {"value": 1})
            with self.assertRaisesRegex(
                extension_analysis.AnalysisError,
                "immutable analysis differs",
            ):
                extension_analysis.write_json_once(path, {"value": 2})

    def make_completed_extension(self, root: Path):
        run_dir = root / "screen_chain"
        work = run_dir / "equilibration"
        extension_dir = work / "extensions" / "npt_ext001"
        extension_dir.mkdir(parents=True)
        edr = work / "npt.edr"
        tpr = extension_dir / "npt_ext001.tpr"
        edr.write_bytes(b"immutable cumulative edr")
        tpr.write_bytes(b"immutable extended tpr")
        manifest = {
            "extension_id": "npt_ext001",
            "chain_id": "screen_chain",
            "record_id": "screen_chain:npt:002",
            "parent_record_id": "screen_chain:npt:001",
            "target_total_duration_ps": 3000.0,
            "extended_tpr_path": "npt_ext001.tpr",
            "extended_tpr_sha256": extension_analysis.sha256(tpr),
            "gromacs_version": "GROMACS version: synthetic",
        }
        manifest_path = extension_dir / "extension_manifest.json"
        manifest_path.write_text(json.dumps(manifest) + "\n")
        metrics = {
            "extension_id": "npt_ext001",
            "chain_id": "screen_chain",
            "record_id": "screen_chain:npt:002",
            "parent_record_id": "screen_chain:npt:001",
            "technical_status": "PASS_COMPLETE",
            "analysis_status": "PENDING_EXTENSION_REANALYSIS",
            "extension_manifest_sha256": extension_analysis.sha256(manifest_path),
            "edr_range_ps": {"first": 0.0, "last": 3000.0, "duration": 3000.0},
            "post_extension_sha256": {
                "npt.edr": extension_analysis.file_evidence(edr),
                "npt_ext001.tpr": extension_analysis.file_evidence(tpr),
            },
        }
        (extension_dir / "extension_metrics.json").write_text(json.dumps(metrics) + "\n")
        return run_dir, edr, extension_dir / "extension_analysis.json"

    def invoke_main(self, run_dir: Path):
        with mock.patch.object(
            sys,
            "argv",
            ["analyze_npt_extension.py", str(run_dir)],
        ), mock.patch("builtins.print"):
            extension_analysis.main()

    def test_main_writes_expected_path_once_and_detects_source_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir, edr, output = self.make_completed_extension(Path(temporary))
            with mock.patch.object(
                extension_analysis,
                "gromacs_identity",
                return_value=("/fake/gmx", "GROMACS version: synthetic"),
            ), mock.patch.object(
                extension_analysis,
                "dump_tpr",
                return_value="   rlist = 1.2\n",
            ), mock.patch.object(
                extension_analysis,
                "extract_energy",
                return_value=synthetic_rows(),
            ):
                self.invoke_main(run_dir)

            payload = json.loads(output.read_text())
            self.assertEqual(payload["schema_version"], "npt-extension-analysis-v1")
            self.assertEqual(payload["technical_status"], "PASS_COMPLETE")
            self.assertEqual(payload["analysis_status"], "PASS_COMPLETE")
            self.assertEqual(
                payload["exploratory_verdict"],
                "THREE_NS_STATIONARITY_CANDIDATE",
            )
            original_bytes = output.read_bytes()

            # Existing analysis is idempotently returned without re-extraction.
            with mock.patch.object(
                extension_analysis,
                "gromacs_identity",
                side_effect=AssertionError("must not run for immutable existing analysis"),
            ):
                self.invoke_main(run_dir)
            self.assertEqual(output.read_bytes(), original_bytes)

            # A changed cumulative EDR invalidates provenance and cannot replace
            # the immutable analysis.
            edr.write_bytes(b"changed cumulative edr")
            with self.assertRaises(SystemExit):
                self.invoke_main(run_dir)
            self.assertEqual(output.read_bytes(), original_bytes)


if __name__ == "__main__":
    unittest.main()
