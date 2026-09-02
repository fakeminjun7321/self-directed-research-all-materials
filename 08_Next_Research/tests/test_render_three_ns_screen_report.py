#!/usr/bin/env python3
"""Focused tests for the Korean three-nanosecond comparison renderer."""

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


renderer = load_script(
    "render_three_ns_screen_report_under_test",
    "08_Next_Research/scripts/render_three_ns_screen_report.py",
)


def chain(chain_id: str, initial: float, final: float, slope: float):
    return {
        "run_dir": f"/synthetic/{chain_id}",
        "chain_id": chain_id,
        "initial_density_kg_m3": initial,
        "last1ns_density_mean_kg_m3": final,
        "density_slope_percent_per_ns": slope,
        "density_last_two_block_diff_percent": 0.20,
        "density_max_adjacent_block_diff_percent": 0.30,
        "density_first_vs_second_500ps_diff_percent": 0.25,
        "density_1_2ns_vs_2_3ns_diff_percent": 0.40,
        "temperature_mean_K": 298.0,
        "temperature_slope_K_per_ns": 0.10,
        "max_adjacent_volume_jump_percent": 0.20,
        "min_box_over_2rlist": 1.24,
        "exploratory_verdict": "THREE_NS_STATIONARITY_CANDIDATE",
        "hard_fail_reasons": [],
        "review_reasons": [],
    }


def comparison_payload():
    return {
        "schema_version": "three-ns-screen-comparison-v1",
        "technical_status": "PASS_COMPLETE",
        "analysis_status": "PASS_COMPLETE",
        "chains": [
            chain("rho1400", 1400.0, 1202.0, 0.30),
            chain("rho1000", 1000.0, 1198.0, 0.20),
            chain("rho1200", 1200.0, 1200.0, 0.10),
        ],
        "comparability": {
            "same_protocol": True,
            "same_seed": True,
            "shared_seed": 110001,
            "same_seed_chains_are_independent_replicas": False,
            "protocol_fingerprint_sha256": "synthetic-fingerprint",
        },
        "last1ns_density_spread_percent": 0.3333333333,
        "cross_start_assessment": "THREE_NS_SAME_BASIN_CANDIDATE",
        "provisional_replica_design_chain": "rho1200",
        "physics_status": "EXPLORATORY_ONLY",
        "equilibrium_validated": False,
        "production_ready": False,
        "not_verified": [
            "thermodynamic equilibrium",
            "independent Packmol and velocity-seed replicas",
            "production readiness",
            "structural and transport-property convergence",
            "laboratory-server reproduction",
        ],
    }


class ReportContentTests(unittest.TestCase):
    def test_renders_three_chains_assessment_representative_and_limits(self):
        report = renderer.render_report(
            comparison_payload(),
            "three_ns_comparison.json",
            "a" * 64,
        )

        self.assertIn("PROVISIONAL / EXPLORATORY ONLY", report)
        self.assertIn("`THREE_NS_SAME_BASIN_CANDIDATE`", report)
        self.assertIn("2–3 ns 평균 밀도의 chain 간 spread: 0.333%", report)
        self.assertIn("`rho1200` — 독립 replica 설계용 임시 후보", report)
        self.assertIn("| rho1000 | 1000.0 | 1198.00 | 0.200 |", report)
        self.assertIn("| rho1200 | 1200.0 | 1200.00 | 0.100 |", report)
        self.assertIn("| rho1400 | 1400.0 | 1202.00 | 0.300 |", report)
        self.assertEqual(report.count("THREE_NS_STATIONARITY_CANDIDATE` |"), 3)
        self.assertIn("min box/(2rlist)", report)
        self.assertIn("평형 검증: **Not verified / 미검증**", report)
        self.assertIn("production 준비 상태: **Not verified / 미검증**", report)
        self.assertIn("독립 Packmol 배치와 독립 속도 seed", report)
        self.assertIn("연구실 서버 재현", report)
        self.assertIn("`equilibrium_validated=false`", report)
        self.assertIn("`production_ready=false`", report)
        self.assertNotIn("평형 완료", report)
        self.assertNotIn("production-ready", report)
        self.assertNotIn("production 준비 완료", report)

    def test_rejects_any_input_that_claims_equilibrium_or_production(self):
        for key in ("equilibrium_validated", "production_ready"):
            payload = comparison_payload()
            payload[key] = True
            with self.subTest(key=key), self.assertRaises(renderer.RendererError):
                renderer.render_report(payload, "comparison.json", "b" * 64)

    def test_representative_requires_same_basin_assessment(self):
        payload = comparison_payload()
        payload["cross_start_assessment"] = (
            "THREE_NS_INITIAL_CONDITION_DEPENDENCE_OR_INCOMPLETE"
        )
        with self.assertRaisesRegex(renderer.RendererError, "representative"):
            renderer.render_report(payload, "comparison.json", "c" * 64)

    def test_markdown_table_cells_escape_pipe_and_newline(self):
        self.assertEqual(renderer.markdown_cell("a|b\nc"), "a\\|b c")


class RendererMainTests(unittest.TestCase):
    def invoke_main(self, source: Path, output: Path, *, force: bool = False):
        argv = [
            "render_three_ns_screen_report.py",
            str(source),
            "--output",
            str(output),
        ]
        if force:
            argv.append("--force")
        with mock.patch.object(sys, "argv", argv):
            renderer.main()

    def test_main_writes_report_and_refuses_unforced_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "comparison.json"
            output = root / "report.md"
            source.write_text(json.dumps(comparison_payload()) + "\n")

            self.invoke_main(source, output)
            first = output.read_text()
            self.assertIn(renderer.sha256(source), first)
            with self.assertRaises(SystemExit):
                self.invoke_main(source, output)
            self.assertEqual(output.read_text(), first)

    def test_force_replaces_only_the_derived_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "comparison.json"
            output = root / "report.md"
            source.write_text(json.dumps(comparison_payload()) + "\n")
            output.write_text("old derived report\n")

            self.invoke_main(source, output, force=True)
            self.assertIn("총 3 ns 초기조건 비교", output.read_text())
            self.assertEqual(
                json.loads(source.read_text())["cross_start_assessment"],
                "THREE_NS_SAME_BASIN_CANDIDATE",
            )

    def test_protected_run_and_handoff_output_roots_are_rejected(self):
        for protected in renderer.PROTECTED_OUTPUT_ROOTS:
            with self.subTest(protected=protected), self.assertRaises(renderer.RendererError):
                renderer.validate_output_path(protected / "must_not_write.md")

    def test_nonfinite_json_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.json"
            path.write_text('{"value": NaN}\n')
            with self.assertRaisesRegex(renderer.RendererError, "non-finite JSON"):
                renderer.read_json(path)


if __name__ == "__main__":
    unittest.main()
