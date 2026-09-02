#!/usr/bin/env python3
"""Focused synthetic tests for three-chain 3 ns comparison."""

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


comparison = load_script(
    "compare_three_ns_screen_under_test",
    "08_Next_Research/scripts/compare_three_ns_screen.py",
)


class SyntheticThreeNsComparisonTests(unittest.TestCase):
    def write_chain(
        self,
        root: Path,
        initial_density: float,
        final_density: float,
        *,
        seed: int = 110001,
        verdict: str = "THREE_NS_STATIONARITY_CANDIDATE",
    ) -> Path:
        chain_id = f"rho{int(initial_density)}"
        run_dir = root / chain_id
        work = run_dir / "equilibration"
        extension_dir = work / "extensions" / "npt_ext001"
        extension_dir.mkdir(parents=True)
        (run_dir / "metrics.json").write_text(
            json.dumps({"initial_density_kg_m3": initial_density}) + "\n"
        )

        chain_manifest = {
            "protocol_version": "eq-screen-v2",
            "seed": seed,
            "npt_ps": 1000.0,
            "npt_steps": 1_000_000,
            "dt_ps": 0.001,
            "input_sha256": {
                "start_em.gro": f"chain-specific-{chain_id}",
                "topol.top": "same-topology",
                "nvt_100ps.mdp": "same-nvt-mdp",
                "npt_1000ps.mdp": "same-npt-mdp",
            },
            "parent_em_sha256": f"chain-specific-{chain_id}",
            "parent_topology_sha256": "same-topology",
            "gromacs_version": "GROMACS version: synthetic",
        }
        chain_manifest_path = work / "chain_manifest.json"
        chain_manifest_path.write_text(json.dumps(chain_manifest) + "\n")

        edr = work / "npt.edr"
        tpr = extension_dir / "npt_ext001.tpr"
        edr.write_bytes(f"cumulative-edr-{chain_id}".encode())
        tpr.write_bytes(f"extended-tpr-{chain_id}".encode())
        manifest = {
            "schema_version": "npt-extension-v1",
            "extension_id": "npt_ext001",
            "chain_id": chain_id,
            "record_id": f"{chain_id}:npt:002",
            "parent_record_id": f"{chain_id}:npt:001",
            "stage": "npt",
            "segment_no": 2,
            "mode": "EXTEND",
            "start_step": 1_000_000,
            "extension_steps": 2_000_000,
            "target_total_steps": 3_000_000,
            "dt_ps": 0.001,
            "base_duration_ps": 1000.0,
            "extension_duration_ps": 2000.0,
            "target_total_duration_ps": 3000.0,
            "extended_tpr_path": "npt_ext001.tpr",
            "extended_tpr_sha256": comparison.sha256(tpr),
            "chain_manifest_sha256": comparison.sha256(chain_manifest_path),
            "gromacs_version": "GROMACS version: synthetic",
            "base_tpr_shape": {
                "nsteps": 1_000_000,
                "dt_ps": 0.001,
                "init_step": 0,
                "tinit_ps": 0.0,
            },
            "extended_tpr_shape": {
                "nsteps": 3_000_000,
                "dt_ps": 0.001,
                "init_step": 0,
                "tinit_ps": 0.0,
            },
        }
        manifest_path = extension_dir / "extension_manifest.json"
        manifest_path.write_text(json.dumps(manifest) + "\n")
        metrics = {
            "extension_id": "npt_ext001",
            "chain_id": chain_id,
            "record_id": f"{chain_id}:npt:002",
            "parent_record_id": f"{chain_id}:npt:001",
            "technical_status": "PASS_COMPLETE",
            "analysis_status": "PENDING_EXTENSION_REANALYSIS",
            "extension_manifest_sha256": comparison.sha256(manifest_path),
            "post_extension_sha256": {
                "npt.edr": comparison.file_evidence(edr),
                "npt_ext001.tpr": comparison.file_evidence(tpr),
            },
        }
        metrics_path = extension_dir / "extension_metrics.json"
        metrics_path.write_text(json.dumps(metrics) + "\n")

        hard_reasons = ["temperature_mean_outside_293_303_K"] if verdict == "THREE_NS_FAIL" else []
        review_reasons = (
            ["density_slope_above_0_5_percent_per_ns"]
            if verdict == "THREE_NS_EXTEND_OR_REVIEW"
            else []
        )
        source_evidence = {
            "extension_manifest.json": comparison.file_evidence(manifest_path),
            "extension_metrics.json": comparison.file_evidence(metrics_path),
            "npt.edr": comparison.file_evidence(edr),
            "npt_ext001.tpr": comparison.file_evidence(tpr),
        }
        analysis = {
            "schema_version": "npt-extension-analysis-v1",
            "extension_id": "npt_ext001",
            "chain_id": chain_id,
            "record_id": f"{chain_id}:npt:002",
            "parent_record_id": f"{chain_id}:npt:001",
            "technical_status": "PASS_COMPLETE",
            "analysis_status": "PASS_COMPLETE",
            "source_evidence": source_evidence,
            "edr_range_ps": {
                "first": 0.0,
                "last": 3000.0,
                "duration": 3000.0,
                "rows": 301,
            },
            "analysis_window_ps": {"start": 2000.0, "end": 3000.0},
            "block_definition": {
                "count": 5,
                "width_ps": 200.0,
                "window_start_ps": 2000.0,
                "window_end_ps": 3000.0,
            },
            "blocks_200ps": [
                {
                    "index": index + 1,
                    "start_ps": 2000.0 + index * 200.0,
                    "end_ps": 2200.0 + index * 200.0,
                    "Density_mean": final_density,
                }
                for index in range(5)
            ],
            "last_1ns": {"Density": {"n": 101, "mean": final_density}},
            "density_qc": {
                "slope_percent_per_ns": 0.8 if review_reasons else 0.1,
                "last_two_block_diff_percent": 0.1,
                "max_adjacent_block_diff_percent": 0.1,
                "first_vs_second_500ps_diff_percent": 0.1,
                "one_to_two_vs_two_to_three_ns_diff_percent": 0.2,
            },
            "temperature_qc": {"mean_K": 310.0 if hard_reasons else 298.0, "slope_K_per_ns": 0.1},
            "volume_qc": {"max_adjacent_frame_jump_percent_0_3ns": 0.2},
            "box_qc": {"min_box_over_2rlist": 1.2},
            "hard_fail_reasons": hard_reasons,
            "review_reasons": review_reasons,
            "exploratory_verdict": verdict,
            "physics_status": "EXPLORATORY_ONLY",
            "equilibrium_validated": False,
            "production_ready": False,
        }
        (extension_dir / "extension_analysis.json").write_text(json.dumps(analysis) + "\n")
        return run_dir

    def make_three(
        self,
        root: Path,
        final_densities=(1200.0, 1205.0, 1198.0),
        verdicts=(
            "THREE_NS_STATIONARITY_CANDIDATE",
            "THREE_NS_STATIONARITY_CANDIDATE",
            "THREE_NS_STATIONARITY_CANDIDATE",
        ),
        seeds=(110001, 110001, 110001),
    ):
        return [
            self.write_chain(
                root,
                initial_density,
                final_density,
                seed=seed,
                verdict=verdict,
            )
            for initial_density, final_density, verdict, seed in zip(
                (1000.0, 1200.0, 1400.0),
                final_densities,
                verdicts,
                seeds,
            )
        ]

    def test_three_stationarity_candidates_within_two_percent_are_same_basin_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs = self.make_three(Path(temporary))
            report = comparison.compare_runs(runs)

        self.assertEqual(
            report["cross_start_assessment"],
            "THREE_NS_SAME_BASIN_CANDIDATE",
        )
        self.assertTrue(report["comparability"]["same_protocol"])
        self.assertTrue(report["comparability"]["same_seed"])
        self.assertFalse(
            report["comparability"]["same_seed_chains_are_independent_replicas"]
        )
        self.assertIsNotNone(report["provisional_replica_design_chain"])
        self.assertFalse(report["equilibrium_validated"])
        self.assertFalse(report["production_ready"])

    def test_review_chain_makes_cross_start_incomplete_even_with_tight_spread(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs = self.make_three(
                Path(temporary),
                verdicts=(
                    "THREE_NS_STATIONARITY_CANDIDATE",
                    "THREE_NS_EXTEND_OR_REVIEW",
                    "THREE_NS_STATIONARITY_CANDIDATE",
                ),
            )
            report = comparison.compare_runs(runs)

        self.assertEqual(
            report["cross_start_assessment"],
            "THREE_NS_INITIAL_CONDITION_DEPENDENCE_OR_INCOMPLETE",
        )
        self.assertIsNone(report["provisional_replica_design_chain"])

    def test_density_spread_above_five_percent_is_not_converged(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs = self.make_three(
                Path(temporary),
                final_densities=(1100.0, 1200.0, 1300.0),
            )
            report = comparison.compare_runs(runs)

        self.assertEqual(report["cross_start_assessment"], "THREE_NS_NOT_CONVERGED")

    def test_hard_fail_makes_cross_start_incomplete(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs = self.make_three(
                Path(temporary),
                verdicts=(
                    "THREE_NS_STATIONARITY_CANDIDATE",
                    "THREE_NS_FAIL",
                    "THREE_NS_STATIONARITY_CANDIDATE",
                ),
            )
            report = comparison.compare_runs(runs)

        self.assertEqual(
            report["cross_start_assessment"],
            "THREE_NS_CROSS_START_INCOMPLETE",
        )

    def test_mismatched_seed_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs = self.make_three(Path(temporary), seeds=(110001, 99, 110001))
            with self.assertRaisesRegex(comparison.ComparisonError, "not directly comparable"):
                comparison.compare_runs(runs)

    def test_changed_cumulative_edr_breaks_analysis_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs = self.make_three(Path(temporary))
            (runs[0] / "equilibration" / "npt.edr").write_bytes(b"tampered")
            with self.assertRaisesRegex(
                comparison.ComparisonError,
                "source hash/provenance mismatch",
            ):
                comparison.compare_runs(runs)

    def test_candidate_verdict_with_inconsistent_stationarity_metric_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs = self.make_three(Path(temporary))
            analysis_path = (
                runs[0]
                / "equilibration"
                / "extensions"
                / "npt_ext001"
                / "extension_analysis.json"
            )
            payload = json.loads(analysis_path.read_text())
            payload["density_qc"]["slope_percent_per_ns"] = 9.0
            analysis_path.write_text(json.dumps(payload) + "\n")
            with self.assertRaisesRegex(
                comparison.ComparisonError,
                "reasons do not match",
            ):
                comparison.compare_runs(runs)

    def invoke_main(self, runs, output):
        with mock.patch.object(
            sys,
            "argv",
            [
                "compare_three_ns_screen.py",
                *(str(run) for run in runs),
                "--output",
                str(output),
            ],
        ), mock.patch("builtins.print"):
            comparison.main()

    def test_main_writes_outside_runs_once_and_reuses_identical_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runs = self.make_three(root)
            output = root / "three_ns_comparison.json"
            self.invoke_main(runs, output)
            original = output.read_bytes()
            payload = json.loads(original)
            self.assertEqual(payload["schema_version"], "three-ns-screen-comparison-v1")
            self.assertFalse(payload["equilibrium_validated"])
            self.assertFalse(payload["production_ready"])

            self.invoke_main(runs, output)
            self.assertEqual(output.read_bytes(), original)

    def test_output_inside_run_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs = self.make_three(Path(temporary))
            output = runs[0] / "comparison.json"
            with self.assertRaises(SystemExit):
                self.invoke_main(runs, output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
