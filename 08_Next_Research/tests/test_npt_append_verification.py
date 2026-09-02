#!/usr/bin/env python3
"""Focused tests for format-aware GROMACS append verification."""

from __future__ import annotations

import importlib.util
from pathlib import Path
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


extend_npt = load_script(
    "extend_npt_append_verification_under_test",
    "08_Next_Research/scripts/extend_npt.py",
)


def comparison_output(*, longer: bool, mismatch: str = "") -> str:
    ending = (
        "End of file on base.edr but not on live.edr"
        if longer
        else "Files read successfully"
    )
    return (
        "There are 45 terms in the energy files\n"
        "There are 45 terms to compare in the energy files\n"
        f"{mismatch}\n{ending}\n"
    )


class XtcPrefixTests(unittest.TestCase):
    def test_requires_the_complete_snapshot_xtc_prefix(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work, snapshot = root / "work", root / "snapshot"
            work.mkdir()
            snapshot.mkdir()
            (snapshot / "npt.xtc").write_bytes(b"complete-base-xtc")
            (work / "npt.xtc").write_bytes(b"complete-base-xtc-and-extension")

            report = extend_npt.verify_xtc_full_prefix(work, snapshot)

            self.assertEqual(report["mode"], "full_byte_prefix")
            self.assertEqual(report["base_size_bytes"], len(b"complete-base-xtc"))

    def test_rejects_a_shorter_checkpoint_only_xtc_prefix(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work, snapshot = root / "work", root / "snapshot"
            work.mkdir()
            snapshot.mkdir()
            (snapshot / "npt.xtc").write_bytes(b"base-finalized")
            (work / "npt.xtc").write_bytes(b"base-rewritten-and-extension")

            with self.assertRaisesRegex(extend_npt.ExtensionError, "full byte prefix"):
                extend_npt.verify_xtc_full_prefix(work, snapshot)


class EdrComparisonTests(unittest.TestCase):
    def test_rejects_value_mismatch_even_when_gmx_check_text_looks_complete(self):
        text = comparison_output(
            longer=True,
            mismatch="Pressure step 1000000: 1.0, step 1000000: 2.0",
        )
        with self.assertRaisesRegex(extend_npt.ExtensionError, "value mismatch"):
            extend_npt.verify_gmx_energy_comparison(
                text,
                "inclusive comparison",
                expect_longer_second_file=True,
            )

    def test_rejects_a_missing_frame_on_the_extracted_time_axis(self):
        rows = [(0.0, 300.0), (1.0, 301.0), (3.0, 302.0)]
        with self.assertRaisesRegex(extend_npt.ExtensionError, "frame count|gap"):
            extend_npt.uniform_time_axis(rows, 0.0, 3.0, 1.0, "live EDR")

    def test_semantic_validator_combines_exact_history_boundary_and_continuity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work, snapshot = root / "work", root / "snapshot"
            work.mkdir()
            snapshot.mkdir()
            (work / "npt.edr").write_bytes(b"live")
            (snapshot / "npt.edr").write_bytes(b"base")
            base_rows = [(0.0, 300.0), (500.0, 301.0), (1000.0, 302.0)]
            live_rows = [
                (0.0, 300.0),
                (500.0, 301.0),
                (1000.0, 302.1),
                (1500.0, 303.0),
                (2000.0, 304.0),
                (2500.0, 305.0),
                (3000.0, 306.0),
            ]

            def fake_run_with_input(command, _cwd, _input_text):
                if "eneconv" in command:
                    output = Path(command[command.index("-o") + 1])
                    output.write_bytes(b"canonical-all-terms-pre-boundary")
                return ""

            with mock.patch.object(
                extend_npt,
                "extract_energy_series",
                side_effect=[base_rows, live_rows],
            ), mock.patch.object(
                extend_npt,
                "run_capture_with_input",
                side_effect=fake_run_with_input,
            ), mock.patch.object(
                extend_npt,
                "run_capture",
                side_effect=[
                    comparison_output(longer=False),
                    comparison_output(longer=True),
                ],
            ):
                report = extend_npt.verify_edr_base_semantics(
                    "gmx", work, snapshot, 3000.0
                )

            self.assertEqual(report["energy_terms_compared"], 45)
            self.assertEqual(report["live_frames"], 7)
            self.assertEqual(report["exact_pre_boundary_last_ps"], 500.0)
            self.assertEqual(
                report["boundary_comparison"],
                "gmx_check_native_default_tolerance_no_mismatch_lines",
            )


class LogSemanticsTests(unittest.TestCase):
    def make_logs(self, live_text: str):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        work, snapshot = root / "work", root / "snapshot"
        work.mkdir()
        snapshot.mkdir()
        (snapshot / "npt.log").write_text("base body\nFinished mdrun\n")
        (work / "npt.log").write_text(live_text)
        return temporary, work, snapshot

    def test_accepts_one_final_marker_after_checkpoint_restart(self):
        temporary, work, snapshot = self.make_logs(
            "old body\n"
            "Reading checkpoint file npt.cpt\n"
            "Restarting from checkpoint, appending to previous log file.\n"
            "Started mdrun on rank 0\n"
            "Finished mdrun\n"
        )
        with temporary:
            report = extend_npt.verify_live_log_semantics(work, snapshot)

        self.assertEqual(report["base_snapshot_finished_mdrun_markers"], 1)
        self.assertEqual(report["live_finished_mdrun_markers"], 1)

    def test_rejects_finished_marker_without_checkpoint_continuation(self):
        temporary, work, snapshot = self.make_logs("Started mdrun\nFinished mdrun\n")
        with temporary, self.assertRaisesRegex(
            extend_npt.ExtensionError, "checkpoint append restart"
        ):
            extend_npt.verify_live_log_semantics(work, snapshot)

    def test_rejects_bad_markers_in_the_live_log(self):
        temporary, work, snapshot = self.make_logs(
            "Reading checkpoint file npt.cpt\n"
            "Restarting from checkpoint, appending to previous log file.\n"
            "Started mdrun on rank 0\n"
            "LINCS WARNING\n"
            "Finished mdrun\n"
        )
        with temporary, self.assertRaisesRegex(extend_npt.ExtensionError, "bad live"):
            extend_npt.verify_live_log_semantics(work, snapshot)


if __name__ == "__main__":
    unittest.main()
