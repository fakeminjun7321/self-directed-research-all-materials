#!/usr/bin/env python3
"""Focused regression tests for exploratory equilibration analysis."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import shutil
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


equilibration = load_script(
    "run_equilibration_under_test",
    "08_Next_Research/scripts/run_equilibration.py",
)
comparison = load_script(
    "compare_density_screen_under_test",
    "08_Next_Research/scripts/compare_density_screen.py",
)
consolidator = load_script(
    "consolidate_equilibration_registry_under_test",
    "08_Next_Research/scripts/consolidate_equilibration_registry.py",
)


class EnergyExtractionTests(unittest.TestCase):
    def fake_run_logged(self, values_by_column, times_by_column=None):
        def fake(command, cwd, log_path, input_text=None):
            del log_path
            column = input_text.splitlines()[0]
            times = (times_by_column or {}).get(column, [0.0, 1.0])
            output_name = command[command.index("-o") + 1]
            rows = zip(times, values_by_column[column])
            (cwd / output_name).write_text(
                "\n".join(f"{time_ps} {value}" for time_ps, value in rows) + "\n"
            )

        return fake

    def test_extract_energy_maps_each_named_series(self):
        values = {
            "Temperature": [298.0, 299.0],
            "Pressure": [1.0, 2.0],
            "Potential": [-1000.0, -1001.0],
            "Density": [1100.0, 1101.0],
            "Volume": [20.0, 20.1],
            "Box-X": [3.0, 3.1],
            "Box-Y": [3.2, 3.3],
            "Box-Z": [3.4, 3.5],
        }
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            with mock.patch.object(
                equilibration,
                "run_logged",
                side_effect=self.fake_run_logged(values),
            ):
                rows = equilibration.extract_energy("npt", work, work / "chain.log")

            self.assertEqual(len(rows), 2)
            for column in equilibration.ENERGY_COLUMNS_BY_STAGE["npt"]:
                self.assertEqual(rows[0][column], values[column][0])
                self.assertEqual(rows[1][column], values[column][1])
            header = (work / "npt_thermo.xvg").read_text().splitlines()[0]
            self.assertEqual(
                header,
                "# time_ps " + " ".join(equilibration.ENERGY_COLUMNS_BY_STAGE["npt"]),
            )

    def test_extract_energy_rejects_mismatched_time_axis(self):
        columns = equilibration.ENERGY_COLUMNS_BY_STAGE["npt"]
        values = {column: [1.0, 2.0] for column in columns}
        times = {column: [0.0, 1.0] for column in columns}
        times["Pressure"] = [0.0, 2.0]
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            with mock.patch.object(
                equilibration,
                "run_logged",
                side_effect=self.fake_run_logged(values, times),
            ):
                with self.assertRaisesRegex(ValueError, "energy time mismatch"):
                    equilibration.extract_energy("npt", work, work / "chain.log")

    def test_extract_energy_rejects_non_increasing_reference_times(self):
        columns = equilibration.ENERGY_COLUMNS_BY_STAGE["npt"]
        values = {column: [1.0, 2.0] for column in columns}
        times = {column: [1.0, 1.0] for column in columns}
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            with mock.patch.object(
                equilibration,
                "run_logged",
                side_effect=self.fake_run_logged(values, times),
            ):
                with self.assertRaisesRegex(ValueError, "non-increasing energy times"):
                    equilibration.extract_energy("npt", work, work / "chain.log")

    def test_nvt_requests_only_terms_present_in_constant_volume_edr(self):
        expected = ["Temperature", "Pressure", "Potential"]
        self.assertEqual(equilibration.ENERGY_COLUMNS_BY_STAGE["nvt"], expected)


class AnalysisMathTests(unittest.TestCase):
    def test_symmetric_percent_difference_is_order_independent(self):
        forward = equilibration.symmetric_percent_difference(90.0, 110.0)
        reverse = equilibration.symmetric_percent_difference(110.0, 90.0)
        self.assertAlmostEqual(forward, 20.0)
        self.assertAlmostEqual(reverse, forward)

    def test_symmetric_percent_difference_handles_zero(self):
        self.assertEqual(equilibration.symmetric_percent_difference(0.0, 0.0), 0.0)
        self.assertAlmostEqual(
            equilibration.symmetric_percent_difference(0.0, 10.0),
            200.0,
        )

    def make_nvt_rows(self):
        return [
            {
                "time_ps": float(time_ps),
                "Temperature": 298.0,
                "Pressure": 1.0,
                "Potential": -1000.0,
            }
            for time_ps in range(101)
        ]

    def make_npt_rows(self, box_nm: float = 3.0):
        return [
            {
                "time_ps": float(time_ps),
                "Temperature": 298.0,
                "Pressure": 1.0,
                "Potential": -1100.0,
                "Density": 1300.0,
                "Volume": box_nm**3,
                "Box-X": box_nm,
                "Box-Y": box_nm,
                "Box-Z": box_nm,
            }
            for time_ps in range(1001)
        ]

    def test_constant_screen_reaches_stationarity_pass_without_validation_claim(self):
        analysis = equilibration.analyze(
            self.make_nvt_rows(),
            self.make_npt_rows(),
            3.0,
            1.2,
            1.2,
        )
        self.assertEqual(analysis["exploratory_verdict"], "SCREEN_STATIONARITY_PASS")
        self.assertEqual(analysis["hard_fail_reasons"], [])
        self.assertFalse(analysis["equilibrium_validated"])
        self.assertFalse(analysis["production_ready"])

    def test_minimum_image_violation_is_screen_fail(self):
        analysis = equilibration.analyze(
            self.make_nvt_rows(),
            self.make_npt_rows(box_nm=2.3),
            3.0,
            1.2,
            1.2,
        )
        self.assertEqual(analysis["exploratory_verdict"], "SCREEN_FAIL")
        self.assertIn("minimum_image_cutoff_violation", analysis["hard_fail_reasons"])

    def test_energy_range_and_tpr_duration_parsers(self):
        check_output = (
            "frame:      0 (index      0), t:    100.000\n"
            "Last energy frame read 1000 time  1100.000\n"
        )
        self.assertEqual(equilibration.parse_energy_range(check_output), (100.0, 1100.0))
        tpr_dump = "   dt = 0.001\n   nsteps = 1000000\n"
        equilibration.verify_tpr_duration(tpr_dump, 1000000, 0.001)
        with self.assertRaisesRegex(RuntimeError, "TPR duration mismatch"):
            equilibration.verify_tpr_duration(tpr_dump, 2000000, 0.001)


class ComparisonGuardTests(unittest.TestCase):
    def write_chain(self, root: Path, name: str, density: float, seed: int = 20260807) -> Path:
        run_dir = root / name
        eq_dir = run_dir / "equilibration"
        eq_dir.mkdir(parents=True)
        (run_dir / "metrics.json").write_text(
            json.dumps({"initial_density_kg_m3": density}) + "\n"
        )
        analysis = {
            "npt_last_500ps": {"Density": {"mean": 1200.0}},
            "density_slope_percent_per_ns": 0.2,
            "density_last_two_block_diff_percent": 0.3,
            "npt_min_box_over_2rlist": 1.2,
            "exploratory_verdict": "SCREEN_STATIONARITY_PASS",
            "hard_fail_reasons": [],
        }
        (eq_dir / "equilibration_metrics.json").write_text(
            json.dumps(
                {
                    "technical_status": "PASS_COMPLETE",
                    "nvt": {"resumed": False},
                    "npt": {"resumed": False},
                    "analysis": analysis,
                }
            )
            + "\n"
        )
        manifest = {
            "seed": seed,
            "npt_ps": 1000.0,
            "parent_topology_sha256": "topology-hash",
            "input_sha256": {
                "nvt_100ps.mdp": "nvt-hash",
                "npt_1000ps.mdp": "npt-hash",
            },
        }
        (eq_dir / "chain_manifest.json").write_text(json.dumps(manifest) + "\n")
        return run_dir

    def mark_stage_resumed(self, run_dir: Path, stage: str, resume_time_ps: float = 139.1):
        work = run_dir / "equilibration"
        checkpoint = work / f"{stage}.cpt"
        checkpoint.write_bytes(f"{stage}-checkpoint-at-{resume_time_ps}-ps\n".encode())
        resume = equilibration.snapshot_resume_checkpoint(
            stage,
            work,
            checkpoint,
            0.0,
            resume_time_ps,
        )
        metrics_path = work / "equilibration_metrics.json"
        metrics = json.loads(metrics_path.read_text())
        metrics[stage] = {"resumed": True, **resume}
        metrics_path.write_text(json.dumps(metrics) + "\n")
        return resume

    def invoke_comparison(self, run_dirs, output: Path):
        argv = [
            "compare_density_screen.py",
            *(str(path) for path in run_dirs),
            "--output",
            str(output),
        ]
        with mock.patch.object(sys, "argv", argv), mock.patch("builtins.print"):
            comparison.main()

    def test_compare_rejects_mismatched_seed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runs = [
                self.write_chain(root, "rho1000", 1000.0),
                self.write_chain(root, "rho1200", 1200.0, seed=99),
                self.write_chain(root, "rho1400", 1400.0),
            ]
            with self.assertRaisesRegex(SystemExit, "not directly comparable"):
                self.invoke_comparison(runs, root / "comparison.json")

    def test_compare_rejects_duplicate_initial_density(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runs = [
                self.write_chain(root, "rho1000a", 1000.0),
                self.write_chain(root, "rho1000b", 1000.0),
                self.write_chain(root, "rho1400", 1400.0),
            ]
            with self.assertRaisesRegex(SystemExit, "expected unique initial densities"):
                self.invoke_comparison(runs, root / "comparison.json")

    def test_non_resumed_stages_need_no_checkpoint_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runs = [
                self.write_chain(root, "rho1000", 1000.0),
                self.write_chain(root, "rho1200", 1200.0),
                self.write_chain(root, "rho1400", 1400.0),
            ]
            output = root / "comparison.json"
            self.invoke_comparison(runs, output)
            payload = json.loads(output.read_text())
            for chain in payload["chains"]:
                self.assertEqual(chain["resume_provenance"]["nvt"], {"resumed": False})
                self.assertEqual(chain["resume_provenance"]["npt"], {"resumed": False})

    def test_resumed_nvt_and_npt_with_immutable_evidence_are_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runs = [
                self.write_chain(root, "rho1000", 1000.0),
                self.write_chain(root, "rho1200", 1200.0),
                self.write_chain(root, "rho1400", 1400.0),
            ]
            nvt_resume = self.mark_stage_resumed(runs[0], "nvt", 41.0)
            npt_resume = self.mark_stage_resumed(runs[1], "npt", 139.1)
            output = root / "comparison.json"
            self.invoke_comparison(runs, output)
            payload = json.loads(output.read_text())
            by_chain = {chain["chain_id"]: chain for chain in payload["chains"]}
            self.assertEqual(
                by_chain["rho1000"]["resume_provenance"]["nvt"][
                    "checkpoint_in_sha256"
                ],
                nvt_resume["checkpoint_in_sha256"],
            )
            self.assertEqual(
                by_chain["rho1200"]["resume_provenance"]["npt"][
                    "checkpoint_in_sha256"
                ],
                npt_resume["checkpoint_in_sha256"],
            )

    def test_resumed_stage_without_provenance_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runs = [
                self.write_chain(root, "rho1000", 1000.0),
                self.write_chain(root, "rho1200", 1200.0),
                self.write_chain(root, "rho1400", 1400.0),
            ]
            metrics_path = runs[1] / "equilibration" / "equilibration_metrics.json"
            metrics = json.loads(metrics_path.read_text())
            metrics["npt"] = {"resumed": True}
            metrics_path.write_text(json.dumps(metrics) + "\n")
            with self.assertRaisesRegex(
                SystemExit,
                "resumed stage lacks immutable checkpoint_in_sha256",
            ):
                self.invoke_comparison(runs, root / "comparison.json")

    def test_tampered_resume_checkpoint_snapshot_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runs = [
                self.write_chain(root, "rho1000", 1000.0),
                self.write_chain(root, "rho1200", 1200.0),
                self.write_chain(root, "rho1400", 1400.0),
            ]
            resume = self.mark_stage_resumed(runs[1], "npt")
            snapshot = runs[1] / "equilibration" / resume["resume_checkpoint_file"]
            snapshot.write_bytes(b"tampered checkpoint snapshot\n")
            with self.assertRaisesRegex(
                SystemExit,
                "snapshot/record SHA mismatch",
            ):
                self.invoke_comparison(runs, root / "comparison.json")

    def test_tampered_resume_record_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runs = [
                self.write_chain(root, "rho1000", 1000.0),
                self.write_chain(root, "rho1200", 1200.0),
                self.write_chain(root, "rho1400", 1400.0),
            ]
            resume = self.mark_stage_resumed(runs[1], "npt")
            record_path = runs[1] / "equilibration" / resume["resume_evidence_file"]
            record = json.loads(record_path.read_text())
            record["checkpoint_in"]["sha256"] = "0" * 64
            record_path.write_text(json.dumps(record) + "\n")
            with self.assertRaisesRegex(
                SystemExit,
                "snapshot/record SHA mismatch",
            ):
                self.invoke_comparison(runs, root / "comparison.json")


class ResumeProvenanceTests(unittest.TestCase):
    def test_base_runner_refuses_to_reopen_chain_after_extension_preparation(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "screen_TEST"
            (run_dir / "equilibration" / "extensions").mkdir(parents=True)
            argv = [
                "run_equilibration.py",
                str(run_dir),
                "--seed",
                "1",
                "--resume",
            ]
            with mock.patch.object(sys, "argv", argv):
                with self.assertRaisesRegex(
                    SystemExit, "base equilibration is frozen"
                ):
                    equilibration.main()

    def test_resume_checkpoint_is_snapshotted_and_registry_validates_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            checkpoint = work / "npt.cpt"
            checkpoint.write_bytes(b"checkpoint-at-139.1-ps\n")
            resume = equilibration.snapshot_resume_checkpoint(
                "npt", work, checkpoint, 0.0, 139.1
            )
            run = {
                "resumed": True,
                **resume,
            }
            validated = consolidator.validate_stage_resume_provenance(
                run, "npt", work, "synthetic"
            )
            self.assertEqual(validated, equilibration.sha256(checkpoint))
            snapshot = work / str(resume["resume_checkpoint_file"])
            self.assertEqual(snapshot.read_bytes(), checkpoint.read_bytes())

            snapshot.write_bytes(b"tampered\n")
            with self.assertRaisesRegex(
                consolidator.RegistryError, "resume checkpoint snapshot changed"
            ):
                consolidator.validate_stage_resume_provenance(
                    run, "npt", work, "synthetic"
                )

    def test_resumed_stage_without_checkpoint_provenance_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                consolidator.RegistryError,
                "lacks immutable checkpoint_in_sha256",
            ):
                consolidator.validate_stage_resume_provenance(
                    {"resumed": True},
                    "npt",
                    Path(temporary),
                    "synthetic",
                )

    def test_attempt_records_bind_live_metrics_to_immutable_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            attempts = work / "attempts"
            attempts.mkdir()
            metrics = {
                "chain_id": "screen_TEST",
                "technical_status": "PASS_COMPLETE",
                "physics_status": "EXPLORATORY_ONLY",
                "attempt": 1,
                "attempt_started_record": "attempts/attempt_001_started.json",
                "resume_requested": True,
            }
            live = work / "equilibration_metrics.json"
            live.write_text(json.dumps(metrics, indent=2) + "\n")
            immutable = attempts / "attempt_001_metrics.json"
            immutable.write_bytes(live.read_bytes())
            (attempts / "attempt_001_started.json").write_text(
                json.dumps(
                    {
                        "schema_version": "eq-attempt-v1",
                        "attempt": 1,
                        "chain_id": "screen_TEST",
                        "resume_requested": True,
                    }
                )
                + "\n"
            )
            (attempts / "attempt_001_final.json").write_text(
                json.dumps(
                    {
                        "schema_version": "eq-attempt-v1",
                        "attempt": 1,
                        "chain_id": "screen_TEST",
                        "technical_status": "PASS_COMPLETE",
                        "physics_status": "EXPLORATORY_ONLY",
                        "metrics_snapshot": "attempts/attempt_001_metrics.json",
                        "metrics_evidence": consolidator.file_evidence(immutable),
                    }
                )
                + "\n"
            )
            started = consolidator.validate_attempt_provenance(
                metrics, work, "synthetic"
            )
            self.assertIsNotNone(started)
            self.assertEqual(started["chain_id"], "screen_TEST")
            live.write_text(json.dumps({**metrics, "physics_status": "CHANGED"}) + "\n")
            with self.assertRaisesRegex(
                consolidator.RegistryError, "live metrics differ"
            ):
                consolidator.validate_attempt_provenance(metrics, work, "synthetic")

    def test_missing_attempt_returns_a_defined_none(self):
        self.assertIsNone(
            consolidator.validate_attempt_provenance(
                {"chain_id": "screen_TEST"}, Path("/not/read"), "synthetic"
            )
        )

    def test_packmol_registry_path_uses_validated_started_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            next_root = consolidator.create_self_test_fixture(Path(temporary))
            run_dir = (
                next_root / "04_Runs" / "screen_L1P1x2_rho1000_TEST"
            )
            work = run_dir / "equilibration"
            shutil.rmtree(work / "extensions")
            (work / "npt.log").write_text(
                "Started mdrun on rank 0 Fri Aug  7 00:01:01 2026\n"
                "Finished mdrun on rank 0 Fri Aug  7 00:11:00 2026\n"
            )

            packmol_seed = 240101
            velocity_seed = 110101
            (run_dir / "input" / "pack.inp").write_text(
                f"seed {packmol_seed}\n"
            )
            (run_dir / "commands.log").write_text(
                f"Seed for random number generator: {packmol_seed}\n"
            )
            (run_dir / "input" / "initial.gro").write_text("initial\n")
            provenance = {
                "packmol_seed": packmol_seed,
                "packmol_input_sha256": consolidator.sha256_file(
                    run_dir / "input" / "pack.inp"
                ),
                "packmol_log_sha256": consolidator.sha256_file(
                    run_dir / "commands.log"
                ),
                "packmol_initial_gro_sha256": consolidator.sha256_file(
                    run_dir / "input" / "initial.gro"
                ),
            }

            manifest_path = work / "chain_manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest.update(
                {
                    "seed": velocity_seed,
                    "velocity_seed": velocity_seed,
                    "seed_semantics": "gromacs_nvt_gen_seed",
                    "parent_packmol_provenance": provenance,
                }
            )
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

            metrics_path = work / "equilibration_metrics.json"
            metrics = json.loads(metrics_path.read_text())
            metrics.update(
                {
                    "seed": velocity_seed,
                    "velocity_seed": velocity_seed,
                    "seed_semantics": "gromacs_nvt_gen_seed",
                    "parent_packmol_provenance": provenance,
                    "npt_target_ps": 1000.0,
                    "attempt": 1,
                    "attempt_started_record": "attempts/attempt_001_started.json",
                    "resume_requested": False,
                }
            )
            metrics_path.write_text(json.dumps(metrics, indent=2) + "\n")
            attempts = work / "attempts"
            attempts.mkdir()
            started_path = attempts / "attempt_001_started.json"
            started = {
                "schema_version": "eq-attempt-v1",
                "attempt": 1,
                "chain_id": run_dir.name,
                "resume_requested": False,
                "requested_seed": velocity_seed,
                "requested_velocity_seed": velocity_seed,
                "seed_semantics": "gromacs_nvt_gen_seed",
                "inherited_packmol_seed": packmol_seed,
                "requested_npt_ps": 1000.0,
            }
            started_path.write_text(json.dumps(started, indent=2) + "\n")
            immutable = attempts / "attempt_001_metrics.json"
            immutable.write_bytes(metrics_path.read_bytes())
            (attempts / "attempt_001_final.json").write_text(
                json.dumps(
                    {
                        "schema_version": "eq-attempt-v1",
                        "attempt": 1,
                        "chain_id": run_dir.name,
                        "technical_status": "PASS_COMPLETE",
                        "physics_status": "EXPLORATORY_ONLY",
                        "metrics_snapshot": "attempts/attempt_001_metrics.json",
                        "metrics_evidence": consolidator.file_evidence(immutable),
                    },
                    indent=2,
                )
                + "\n"
            )

            environments = consolidator.read_environment_map(
                next_root / "03_Environments" / "environment_registry.csv"
            )
            chain_rows, qc_rows = consolidator.consolidate_one(
                metrics_path, next_root, environments
            )
            self.assertEqual(len(chain_rows), 2)
            self.assertTrue(qc_rows)
            slope_rows = {
                row["criterion_id"]: row
                for row in qc_rows
                if row["criterion_id"] in {"SCR009", "SCR011"}
            }
            self.assertEqual(set(slope_rows), {"SCR009", "SCR011"})
            for criterion, expected in (("SCR009", 0.2), ("SCR011", 0.1)):
                self.assertEqual(
                    slope_rows[criterion]["metric"],
                    "absolute_temperature_slope_per_ns",
                )
                self.assertEqual(
                    slope_rows[criterion]["aggregation"], "absolute_slope"
                )
                self.assertAlmostEqual(float(slope_rows[criterion]["value"]), expected)

            started["inherited_packmol_seed"] = packmol_seed + 1
            started_path.write_text(json.dumps(started, indent=2) + "\n")
            with self.assertRaisesRegex(
                consolidator.RegistryError, "attempt inherited Packmol seed mismatch"
            ):
                consolidator.consolidate_one(metrics_path, next_root, environments)


class RegistryQuarantineTests(unittest.TestCase):
    def make_fixture(self, root: Path) -> Path:
        return consolidator.create_self_test_fixture(root)

    def test_exact_quarantine_is_visible_and_replacement_is_consolidated(self):
        with tempfile.TemporaryDirectory() as temporary:
            next_root = self.make_fixture(Path(temporary))
            chain_rows, qc_rows, _, audit_text = consolidator.build_registries(next_root)
            audit = json.loads(audit_text)
            excluded = "screen_L1P1x2_rho1000_QUARANTINED"
            replacement = "screen_L1P1x2_rho1000_TEST"
            self.assertFalse(any(row["chain_id"] == excluded for row in chain_rows))
            self.assertTrue(any(row["chain_id"] == replacement for row in chain_rows))
            self.assertEqual(audit["active_exclusions"][0]["chain_id"], excluded)
            self.assertEqual(
                audit["active_exclusions"][0]["replacement_chain_id"], replacement
            )
            extension_slope = next(
                row for row in qc_rows if row["criterion_id"] == "EXT3NS003"
            )
            self.assertEqual(
                extension_slope["metric"], "absolute_temperature_slope_per_ns"
            )
            self.assertEqual(extension_slope["aggregation"], "absolute_slope")

    def test_dry_run_prints_the_exact_active_exclusion(self):
        with tempfile.TemporaryDirectory() as temporary:
            next_root = self.make_fixture(Path(temporary))
            argv = [
                "consolidate_equilibration_registry.py",
                "--next-root",
                str(next_root),
                "--dry-run",
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch(
                "sys.stdout", new_callable=io.StringIO
            ) as stdout:
                consolidator.main()
            output = stdout.getvalue()
            self.assertIn(
                "QUARANTINE_ACTIVE "
                "excluded=screen_L1P1x2_rho1000_QUARANTINED "
                "replacement=screen_L1P1x2_rho1000_TEST "
                f"reason={consolidator.QUARANTINE_REASON}",
                output,
            )

    def test_quarantine_evidence_sha_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            next_root = self.make_fixture(Path(temporary))
            safety = (
                next_root
                / "04_Runs"
                / "screen_L1P1x2_rho1000_QUARANTINED"
                / "equilibration"
                / "safety_thread_reduction_record.json"
            )
            safety.write_bytes(safety.read_bytes() + b"tampered\n")
            with self.assertRaisesRegex(
                consolidator.RegistryError, "evidence SHA-256 mismatch"
            ):
                consolidator.build_registries(next_root)

    def test_incomplete_replacement_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            next_root = self.make_fixture(Path(temporary))
            replacement_metrics = (
                next_root
                / "04_Runs"
                / "screen_L1P1x2_rho1000_TEST"
                / "equilibration"
                / "equilibration_metrics.json"
            )
            replacement_metrics.unlink()
            with self.assertRaisesRegex(
                consolidator.RegistryError, "quarantine replacement incomplete"
            ):
                consolidator.build_registries(next_root)

    def test_hidden_exclusion_field_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            next_root = self.make_fixture(Path(temporary))
            config_path = next_root / consolidator.QUARANTINE_CONFIG_RELATIVE
            config = json.loads(config_path.read_text())
            config["exclude_patterns"] = ["screen_*"]
            config_path.write_text(json.dumps(config) + "\n")
            with self.assertRaisesRegex(
                consolidator.RegistryError, "unexpected top-level fields"
            ):
                consolidator.build_registries(next_root)

if __name__ == "__main__":
    unittest.main()
