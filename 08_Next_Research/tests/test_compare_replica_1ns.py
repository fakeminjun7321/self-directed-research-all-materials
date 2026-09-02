#!/usr/bin/env python3
"""Synthetic tests for the pre-registered independent-replica comparison."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


PROJECT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT / "08_Next_Research" / "scripts" / "compare_replica_1ns.py"
SPEC = importlib.util.spec_from_file_location("compare_replica_1ns_under_test", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not import compare_replica_1ns.py")
comparison = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(comparison)


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


class SyntheticReplicaComparisonTests(unittest.TestCase):
    def setUp(self):
        self.production_audit_path = comparison.INPUT_AUDIT_PATH
        self.production_audit_sha256 = comparison.EXPECTED_INPUT_AUDIT_SHA256

    def tearDown(self):
        comparison.INPUT_AUDIT_PATH = self.production_audit_path
        comparison.EXPECTED_INPUT_AUDIT_SHA256 = self.production_audit_sha256

    def write_chain(
        self,
        root: Path,
        replica_id: str,
        packmol_seed: int,
        velocity_seed: int,
        density: float,
    ) -> Path:
        run_dir = root / f"replica_{replica_id}"
        input_dir = run_dir / "input"
        work = run_dir / "equilibration"
        attempts = work / "attempts"
        input_dir.mkdir(parents=True)
        attempts.mkdir(parents=True)

        files = {
            input_dir / "initial.gro": (
                f"synthetic initial coordinates {replica_id}\n"
                "0\n"
                "3.08570 3.08570 3.08570\n"
            ),
            run_dir / "em.gro": f"em coordinates {replica_id}\n",
            input_dir / "topol.top": (
                "identical scaled topology\n"
                "[ molecules ]\n"
                "Li+ 50\n"
                "c3c1pyrr+ 50\n"
                "fsi- 100\n"
            ),
            input_dir / "em.mdp": "identical em protocol\n",
            input_dir / "Li.zmat": "identical Li source\n",
            input_dir / "c3c1pyrr.zmat": "identical cation source\n",
            input_dir / "fsi.zmat": "identical anion source\n",
            input_dir / "il.ff": "identical force field\n",
            input_dir / "pack.inp": f"seed {packmol_seed}\n",
            run_dir / "commands.log": (
                "Packmol Version 21.2.3\n"
                f"Seed for random number generator: {packmol_seed}\n"
                "Success!\n"
            ),
            work / "nvt_100ps.mdp": (
                "integrator = md\n"
                "nsteps = 100000\n"
                f"gen-seed = {velocity_seed}\n"
                "tcoupl = V-rescale\n"
            ),
            work / "npt_1000ps.mdp": (
                "integrator = md\n"
                "nsteps = 1000000\n"
                "pcoupl = C-rescale\n"
            ),
            work / "nvt.gro": f"nvt coordinates {replica_id}\n",
            work / "nvt_mdrun_console.log": (
                "[synthetic] $ gmx mdrun -deffnm nvt -ntmpi 1 -ntomp 6 -pin on\n"
            ),
            work / "npt_mdrun_console.log": (
                "[synthetic] $ gmx mdrun -deffnm npt -ntmpi 1 -ntomp 6 -pin on\n"
            ),
        }
        for path, content in files.items():
            path.write_text(content)
        for stage, target in (("nvt", 100.0), ("npt", 1000.0)):
            for suffix in ("edr", "tpr", "cpt", "xtc", "gro"):
                (work / f"{stage}.{suffix}").write_bytes(
                    f"{stage}-{suffix}-{replica_id}\n".encode()
                )
            (work / f"{stage}.log").write_text(
                "Using 6 OpenMP threads\nFinished mdrun\n"
            )
            (work / f"{stage}_edr_check.txt").write_text(
                "frame:      0 (index      0), t:      0.000\n"
                f"Last energy frame read 1000 time  {target:.3f}\n"
            )
        (work / "start_em.gro").write_bytes((run_dir / "em.gro").read_bytes())
        (work / "topol.top").write_bytes((input_dir / "topol.top").read_bytes())

        parent_metrics = {
            "run_id": run_dir.name,
            "atom_count": 2300,
            "requested_density_kg_m3": 1400.0,
            "initial_density_kg_m3": comparison.initial_density_from_gro(
                input_dir / "initial.gro"
            ),
            "packmol_seed_requested": packmol_seed,
            "packmol_seed_observed": packmol_seed,
            "canonical_topology_sha256": "a" * 64,
            "charge_scaling_retained": 0.75,
            "molecule_charge_sums": {
                "Li+": 0.75,
                "c3c1pyrr+": 0.75,
                "fsi-": -0.75,
            },
            "technical_status": "PASS_EM_TECHNICAL",
            "grompp_warning_count": 0,
            "em_summary": {"converged": True},
        }
        write_json(run_dir / "metrics.json", parent_metrics)
        write_json(run_dir / "validation.json", {"all_passed": True})

        provenance = {
            "packmol_seed": packmol_seed,
            "packmol_input_sha256": comparison.sha256(input_dir / "pack.inp"),
            "packmol_log_sha256": comparison.sha256(run_dir / "commands.log"),
            "packmol_initial_gro_sha256": comparison.sha256(
                input_dir / "initial.gro"
            ),
        }
        input_hashes = {
            "start_em.gro": comparison.sha256(work / "start_em.gro"),
            "topol.top": comparison.sha256(work / "topol.top"),
            "nvt_100ps.mdp": comparison.sha256(work / "nvt_100ps.mdp"),
            "npt_1000ps.mdp": comparison.sha256(work / "npt_1000ps.mdp"),
        }
        manifest = {
            "protocol_version": "eq-screen-v2",
            "seed": velocity_seed,
            "velocity_seed": velocity_seed,
            "seed_semantics": "gromacs_nvt_gen_seed",
            "npt_ps": 1000.0,
            "npt_steps": 1_000_000,
            "dt_ps": 0.001,
            "input_sha256": input_hashes,
            "parent_em_sha256": comparison.sha256(run_dir / "em.gro"),
            "parent_topology_sha256": comparison.sha256(input_dir / "topol.top"),
            "gromacs_version": "GROMACS version: 2026.2-synthetic",
            "parent_packmol_provenance": provenance,
        }
        write_json(work / "chain_manifest.json", manifest)
        write_json(work / "INPUT_SHA256.json", input_hashes)

        attempt = {
            "schema_version": "eq-attempt-v1",
            "attempt": 1,
            "chain_id": run_dir.name,
            "requested_seed": velocity_seed,
            "requested_velocity_seed": velocity_seed,
            "seed_semantics": "gromacs_nvt_gen_seed",
            "inherited_packmol_seed": packmol_seed,
            "requested_npt_ps": 1000.0,
            "requested_threads": 6,
        }
        write_json(attempts / "attempt_001_started.json", attempt)

        analysis = {
            "nvt_last_50ps": {
                "Temperature": {"mean": 298.0, "slope_per_ns": 0.1},
                "last_two_temperature_block_diff_K": 0.2,
            },
            "npt_last_500ps": {
                "Density": {"mean": density},
                "Temperature": {"mean": 298.0, "slope_per_ns": 0.1},
            },
            "density_slope_percent_per_ns": 0.1,
            "density_last_two_block_diff_percent": 0.2,
            "density_max_adjacent_block_diff_percent": 0.3,
            "max_adjacent_volume_jump_percent": 0.1,
            "nvt_min_box_over_2rlist": 1.20,
            "npt_min_box_over_2rlist": 1.20,
            "hard_fail_reasons": [],
            "exploratory_verdict": "SCREEN_STATIONARITY_PASS",
            "physics_status": "EXPLORATORY_ONLY",
            "equilibrium_validated": False,
            "production_ready": False,
        }
        eq_metrics = {
            "chain_id": run_dir.name,
            "attempt": 1,
            "attempt_started_record": "attempts/attempt_001_started.json",
            "end": "2026-08-07T12:00:00+09:00",
            "technical_status": "PASS_COMPLETE",
            "physics_status": "EXPLORATORY_ONLY",
            "seed": velocity_seed,
            "velocity_seed": velocity_seed,
            "seed_semantics": "gromacs_nvt_gen_seed",
            "parent_packmol_provenance": provenance,
            "npt_target_ps": 1000.0,
            "nvt": {
                "first_time_ps": 0.0,
                "last_time_ps": 100.0,
                "duration_ps": 100.0,
            },
            "npt": {
                "first_time_ps": 0.0,
                "last_time_ps": 1000.0,
                "duration_ps": 1000.0,
            },
            "bad_markers": {"Fatal error": 0, "nan": 0},
            "grompp_warnings": {"nvt": 0, "npt": 0},
            "analysis": analysis,
            "input_sha256": input_hashes,
            "equilibrium_validated": False,
            "production_ready": False,
        }
        write_json(work / "equilibration_metrics.json", eq_metrics)
        self.sync_attempt_snapshot(run_dir)
        return run_dir

    def make_three(self, root: Path, densities=(1200.0, 1205.0, 1210.0)):
        runs = [
            self.write_chain(root, replica, packmol, velocity, density)
            for replica, packmol, velocity, density in zip(
                ("R1", "R2", "R3"),
                (240101, 240102, 240103),
                (110101, 110102, 110103),
                densities,
            )
        ]
        self.write_input_audit(root, runs)
        return runs

    def write_input_audit(self, root: Path, runs: list[Path]) -> None:
        chains = []
        for run in runs:
            metrics = json.loads((run / "metrics.json").read_text())
            initial = run / "input" / "initial.gro"
            chains.append(
                {
                    "chain_id": run.name.replace("replica_", "audited_"),
                    "packmol_seed": metrics["packmol_seed_requested"],
                    "requested_density_kg_m3": 1400.0,
                    "initial_density_kg_m3": metrics["initial_density_kg_m3"],
                    "atom_count": 2300,
                    "scientific_input_checks": {"synthetic_all_passed": True},
                    "initial_gro": comparison.file_evidence(initial),
                }
            )
        audit = {
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
            "chains": chains,
        }
        path = root / "synthetic_replica_input_audit_v3.json"
        write_json(path, audit)
        comparison.INPUT_AUDIT_PATH = path
        comparison.EXPECTED_INPUT_AUDIT_SHA256 = comparison.sha256(path)

    def sync_attempt_snapshot(self, run_dir: Path) -> None:
        work = run_dir / "equilibration"
        metrics_path = work / "equilibration_metrics.json"
        metrics = json.loads(metrics_path.read_text())
        snapshot = work / "attempts" / "attempt_001_metrics.json"
        snapshot.write_bytes(metrics_path.read_bytes())
        final = {
            "schema_version": "eq-attempt-v1",
            "attempt": 1,
            "chain_id": run_dir.name,
            "ended_at": metrics["end"],
            "technical_status": metrics["technical_status"],
            "physics_status": metrics["physics_status"],
            "metrics_snapshot": "attempts/attempt_001_metrics.json",
            "metrics_evidence": comparison.file_evidence(snapshot),
        }
        write_json(work / "attempts" / "attempt_001_final.json", final)

    def rewrite_metrics(self, run_dir: Path, mutate, *, sync: bool = True) -> None:
        path = run_dir / "equilibration" / "equilibration_metrics.json"
        value = json.loads(path.read_text())
        mutate(value)
        write_json(path, value)
        if sync:
            self.sync_attempt_snapshot(run_dir)

    def test_early_agreement_verifies_fixed_rules_and_independent_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs = self.make_three(Path(temporary))
            payload = comparison.compare_runs(runs)
        self.assertEqual(
            payload["one_ns_replica_verdict"],
            "ONE_NS_REPLICA_EARLY_AGREEMENT_CANDIDATE",
        )
        self.assertTrue(payload["comparability"]["passed"])
        self.assertTrue(payload["comparability"]["nvt_output_hashes_unique"])
        self.assertEqual(
            len(
                {
                    replica["protocol_evidence"]["normalized_nvt_mdp"]["sha256"]
                    for replica in payload["replicas"]
                }
            ),
            1,
        )
        self.assertEqual(payload["representative_replica"], None)
        self.assertFalse(payload["equilibrium_validated"])
        self.assertFalse(payload["production_ready"])
        self.assertEqual(payload["replica_set_technical_status"], "PASS_COMPLETE")
        self.assertEqual(payload["physics_status"], "EXPLORATORY_ONLY_NOT_EQUILIBRIUM")
        self.assertEqual(
            payload["replicas"][0]["composition"], comparison.EXPECTED_COMPOSITION
        )
        self.assertAlmostEqual(
            payload["replicas"][0]["initial_density_kg_m3"], 1400.0338886017998
        )
        self.assertIn("replica_input_audit_v3", payload["source_evidence"])
        self.assertEqual(
            payload["source_evidence"]["comparison_rules"]["sha256"],
            comparison.EXPECTED_RULES_SHA256,
        )
        self.assertAlmostEqual(
            payload["density_statistics"]["replica_mean_kg_m3"], 1205.0
        )
        self.assertEqual(len(payload["density_statistics"]["pairwise"]), 3)
        self.assertTrue(payload["density_statistics"]["sem_not_calculated"])

    def test_pending_has_highest_priority(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs = self.make_three(Path(temporary))
            (runs[2] / "equilibration" / "equilibration_metrics.json").unlink()
            payload = comparison.compare_runs(runs)
        self.assertEqual(
            payload["one_ns_replica_verdict"],
            "ONE_NS_REPLICA_COMPARISON_PENDING",
        )
        self.assertIsNone(payload["representative_replica"])

    def test_pending_cli_exits_nonzero_without_creating_immutable_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runs = self.make_three(root / "runs")
            (runs[2] / "equilibration" / "equilibration_metrics.json").unlink()
            output = root / "pending-must-not-exist.json"
            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    *(str(path) for path in runs),
                    "--output",
                    str(output),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=environment,
                check=False,
            )
            output_existed = output.exists()
        self.assertEqual(completed.returncode, 2)
        self.assertFalse(output_existed)
        self.assertEqual(
            json.loads(completed.stdout)["one_ns_replica_verdict"],
            "ONE_NS_REPLICA_COMPARISON_PENDING",
        )
        self.assertEqual(completed.stderr, "")

    def test_actual_r1_legacy_manifest_shape_is_cross_validated(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs = self.make_three(Path(temporary))
            manifest_path = runs[0] / "equilibration" / "chain_manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest.pop("velocity_seed")
            manifest.pop("seed_semantics")
            write_json(manifest_path, manifest)
            payload = comparison.compare_runs(runs)
        r1 = next(item for item in payload["replicas"] if item["replica_id"] == "R1")
        self.assertTrue(payload["comparability"]["seed_cross_validation_passed"])
        self.assertEqual(
            r1["seed_cross_validation"]["manifest_mode"],
            "LEGACY_MANIFEST_SEED_FALLBACK",
        )
        self.assertEqual(r1["seed_cross_validation"]["nvt_mdp_gen_seed"], 110101)
        self.assertEqual(r1["seed_cross_validation"]["completed_metrics_seed"], 110101)

    def test_partial_or_conflicting_manifest_seed_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for field in ("velocity_seed", "seed_semantics"):
                with self.subTest(missing=field):
                    runs = self.make_three(root / field)
                    manifest_path = runs[0] / "equilibration" / "chain_manifest.json"
                    manifest = json.loads(manifest_path.read_text())
                    manifest.pop(field)
                    write_json(manifest_path, manifest)
                    with self.assertRaisesRegex(
                        comparison.ComparisonError, "partially populated"
                    ):
                        comparison.compare_runs(runs)

    def test_normalized_nvt_passes_but_npt_mismatch_is_not_comparable(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs = self.make_three(Path(temporary))
            work = runs[2] / "equilibration"
            npt = work / "npt_1000ps.mdp"
            npt.write_text(npt.read_text() + "tau-p = 7.0\n")
            digest = comparison.sha256(npt)
            for filename in ("chain_manifest.json", "INPUT_SHA256.json"):
                path = work / filename
                value = json.loads(path.read_text())
                target = value["input_sha256"] if filename.startswith("chain") else value
                target["npt_1000ps.mdp"] = digest
                write_json(path, value)
            metrics_path = work / "equilibration_metrics.json"
            metrics = json.loads(metrics_path.read_text())
            metrics["input_sha256"]["npt_1000ps.mdp"] = digest
            write_json(metrics_path, metrics)
            self.sync_attempt_snapshot(runs[2])
            payload = comparison.compare_runs(runs)
        self.assertEqual(
            payload["one_ns_replica_verdict"], "ONE_NS_REPLICA_NOT_COMPARABLE"
        )
        self.assertIn("npt_mdp_differs", payload["comparability"]["failures"])
        self.assertNotIn(
            "normalized_nvt_mdp_differs", payload["comparability"]["failures"]
        )

    def test_duplicate_nvt_output_is_not_comparable(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs = self.make_three(Path(temporary))
            target = runs[1] / "equilibration" / "nvt.gro"
            target.write_bytes((runs[0] / "equilibration" / "nvt.gro").read_bytes())
            payload = comparison.compare_runs(runs)
        self.assertEqual(
            payload["one_ns_replica_verdict"], "ONE_NS_REPLICA_NOT_COMPARABLE"
        )
        self.assertFalse(payload["comparability"]["nvt_output_hashes_unique"])

    def test_planned_velocity_seed_mapping_is_enforced(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runs = [
                self.write_chain(root, "R1", 240101, 110101, 1200.0),
                self.write_chain(root, "R2", 240102, 110102, 1200.0),
                self.write_chain(root, "R3", 240103, 119999, 1200.0),
            ]
            self.write_input_audit(root, runs)
            payload = comparison.compare_runs(runs)
        self.assertEqual(
            payload["one_ns_replica_verdict"], "ONE_NS_REPLICA_NOT_COMPARABLE"
        )
        self.assertTrue(
            any(
                failure.endswith("planned_velocity_seed_mapping_mismatch")
                for failure in payload["comparability"]["failures"]
            )
        )

    def test_stored_screen_verdict_cannot_disagree_with_fixed_thresholds(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs = self.make_three(Path(temporary))

            def contradictory(value):
                value["analysis"]["density_slope_percent_per_ns"] = 1.1

            self.rewrite_metrics(runs[1], contradictory)
            with self.assertRaisesRegex(
                comparison.ComparisonError, "SCREEN verdict differs"
            ):
                comparison.compare_runs(runs)

    def test_screen_fail_precedes_density_statistics(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs = self.make_three(Path(temporary))

            def fail(value):
                analysis = value["analysis"]
                analysis["npt_last_500ps"]["Temperature"]["mean"] = 310.0
                analysis["hard_fail_reasons"] = [
                    "npt_temperature_mean_outside_293_303_K"
                ]
                analysis["exploratory_verdict"] = "SCREEN_FAIL"

            self.rewrite_metrics(runs[1], fail)
            payload = comparison.compare_runs(runs)
        self.assertEqual(
            payload["one_ns_replica_verdict"], "ONE_NS_REPLICA_SET_FAIL"
        )
        self.assertEqual(payload["screen_failures"], ["R2"])
        self.assertIsNone(payload["density_statistics"])

    def test_terminal_technical_failure_produces_set_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs = self.make_three(Path(temporary))

            def technical_failure(value):
                value["technical_status"] = "FAILED"
                value.pop("analysis")
                value.pop("parent_packmol_provenance")
                value.pop("input_sha256")

            self.rewrite_metrics(runs[0], technical_failure)
            payload = comparison.compare_runs(runs)
        self.assertEqual(
            payload["one_ns_replica_verdict"], "ONE_NS_REPLICA_SET_FAIL"
        )
        self.assertIn(
            "R1:equilibration_technical_status_failed",
            payload["technical_failures"],
        )

    def test_thread_difference_is_not_comparable_even_when_internally_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs = self.make_three(Path(temporary))
            work = runs[2] / "equilibration"
            attempt_path = work / "attempts" / "attempt_001_started.json"
            attempt = json.loads(attempt_path.read_text())
            attempt["requested_threads"] = 5
            write_json(attempt_path, attempt)
            for stage in ("nvt", "npt"):
                console = work / f"{stage}_mdrun_console.log"
                console.write_text(console.read_text().replace("-ntomp 6", "-ntomp 5"))
                native = work / f"{stage}.log"
                native.write_text(native.read_text().replace("Using 6", "Using 5"))
            payload = comparison.compare_runs(runs)
        self.assertEqual(
            payload["one_ns_replica_verdict"], "ONE_NS_REPLICA_NOT_COMPARABLE"
        )
        self.assertIn("openmp_threads_differs", payload["comparability"]["failures"])
        self.assertIn(
            "openmp_threads_not_fixed_at_6", payload["comparability"]["failures"]
        )

    def test_size_review_precedes_uniform_extension(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs = self.make_three(Path(temporary))

            def size_review(value):
                value["analysis"]["nvt_min_box_over_2rlist"] = 1.05
                value["analysis"]["exploratory_verdict"] = "SCREEN_EXTEND"

            self.rewrite_metrics(runs[0], size_review)
            payload = comparison.compare_runs(runs)
        self.assertEqual(
            payload["one_ns_replica_verdict"],
            "ONE_NS_REPLICA_SIZE_REVIEW_REQUIRED",
        )

    def test_dispersion_and_extension_thresholds_are_pre_registered(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dispersed = self.make_three(root / "dispersed", (1200.0, 1200.0, 1280.0))
            dispersion_payload = comparison.compare_runs(dispersed)
            extension = self.make_three(root / "extension", (1200.0, 1200.0, 1200.0))

            def extend(value):
                value["analysis"]["density_slope_percent_per_ns"] = 1.1
                value["analysis"]["exploratory_verdict"] = "SCREEN_EXTEND"

            self.rewrite_metrics(extension[2], extend)
            extension_payload = comparison.compare_runs(extension)
        self.assertEqual(
            dispersion_payload["one_ns_replica_verdict"],
            "ONE_NS_REPLICA_DISPERSION_OR_INCOMPLETE",
        )
        self.assertEqual(
            extension_payload["one_ns_replica_verdict"],
            "ONE_NS_REPLICA_UNIFORM_EXTENSION_REQUIRED",
        )

    def test_rules_hash_and_write_once_are_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runs = self.make_three(root / "runs")
            payload = comparison.compare_runs(runs)
            output = root / "comparison.json"
            comparison.write_json_once(output, payload)
            comparison.write_json_once(output, payload)
            with self.assertRaisesRegex(comparison.ComparisonError, "immutable"):
                comparison.write_json_once(output, {**payload, "replica_count": 99})
            with mock.patch.object(
                comparison, "EXPECTED_RULES_SHA256", "0" * 64
            ), self.assertRaisesRegex(comparison.ComparisonError, "SHA-256"):
                comparison.compare_runs(runs)

    def test_central_metrics_tamper_breaks_immutable_attempt_binding(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs = self.make_three(Path(temporary))

            def tamper(value):
                value["analysis"]["npt_last_500ps"]["Density"]["mean"] = 9999.0

            self.rewrite_metrics(runs[0], tamper, sync=False)
            with self.assertRaisesRegex(
                comparison.ComparisonError, "central metrics differ"
            ):
                comparison.compare_runs(runs)

    def test_missing_core_stage_artifact_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs = self.make_three(Path(temporary))
            (runs[1] / "equilibration" / "npt.xtc").unlink()
            with self.assertRaisesRegex(comparison.ComparisonError, "required evidence"):
                comparison.compare_runs(runs)

    def test_native_log_marker_and_edr_range_tamper_are_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker_runs = self.make_three(root / "marker")
            nvt_log = marker_runs[2] / "equilibration" / "nvt.log"
            nvt_log.write_text(nvt_log.read_text() + "Fatal error synthetic\n")
            with self.assertRaisesRegex(comparison.ComparisonError, "forbidden markers"):
                comparison.compare_runs(marker_runs)

            range_runs = self.make_three(root / "range")
            check = range_runs[2] / "equilibration" / "npt_edr_check.txt"
            check.write_text(check.read_text().replace("1000.000", "999.000"))
            with self.assertRaisesRegex(comparison.ComparisonError, "last time differs"):
                comparison.compare_runs(range_runs)

    def test_initial_density_and_composition_are_recomputed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            density_runs = self.make_three(root / "density")
            metrics_path = density_runs[0] / "metrics.json"
            metrics = json.loads(metrics_path.read_text())
            metrics["initial_density_kg_m3"] += 1.0
            write_json(metrics_path, metrics)
            with self.assertRaisesRegex(
                comparison.ComparisonError, "reported/calculated initial density"
            ):
                comparison.compare_runs(density_runs)

            composition_runs = self.make_three(root / "composition")
            topology = composition_runs[0] / "input" / "topol.top"
            topology.write_text(topology.read_text().replace("fsi- 100", "fsi- 99"))
            with self.assertRaisesRegex(comparison.ComparisonError, "composition differs"):
                comparison.compare_runs(composition_runs)

    def test_fixed_input_audit_and_initial_gro_binding_reject_tamper(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            audit_runs = self.make_three(root / "audit")
            comparison.INPUT_AUDIT_PATH.write_text(
                comparison.INPUT_AUDIT_PATH.read_text() + " \n"
            )
            with self.assertRaisesRegex(comparison.ComparisonError, "audit SHA-256"):
                comparison.compare_runs(audit_runs)

            initial_runs = self.make_three(root / "initial")
            run = initial_runs[0]
            initial = run / "input" / "initial.gro"
            initial.write_text(initial.read_text().replace("synthetic", "tampered"))
            new_hash = comparison.sha256(initial)
            manifest_path = run / "equilibration" / "chain_manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["parent_packmol_provenance"][
                "packmol_initial_gro_sha256"
            ] = new_hash
            write_json(manifest_path, manifest)

            def update_provenance(value):
                value["parent_packmol_provenance"][
                    "packmol_initial_gro_sha256"
                ] = new_hash

            self.rewrite_metrics(run, update_provenance)
            with self.assertRaisesRegex(
                comparison.ComparisonError, "initial GRO differs from fixed input audit"
            ):
                comparison.compare_runs(initial_runs)


if __name__ == "__main__":
    unittest.main()
