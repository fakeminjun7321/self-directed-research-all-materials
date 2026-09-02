#!/usr/bin/env python3
"""Focused process and signal safety tests for guarded NPT extension."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import signal
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


thermal_guard = load_script(
    "thermal_guard_under_test",
    "08_Next_Research/scripts/thermal_guard.py",
)
extend_npt = load_script(
    "extend_npt_process_under_test",
    "08_Next_Research/scripts/extend_npt.py",
)
run_equilibration = load_script(
    "run_equilibration_process_under_test",
    "08_Next_Research/scripts/run_equilibration.py",
)


class FakeChild:
    def __init__(self, return_code=0, signal_to_invoke=None):
        self.pid = 4242
        self.return_code = return_code
        self.signal_to_invoke = signal_to_invoke
        self.poll_calls = 0
        self.kill_calls = 0

    def poll(self):
        self.poll_calls += 1
        return None

    def wait(self, timeout=None):
        del timeout
        if self.signal_to_invoke is not None:
            handler = signal.getsignal(self.signal_to_invoke)
            signum = self.signal_to_invoke
            self.signal_to_invoke = None
            handler(signum, None)
        return self.return_code

    def kill(self):
        self.kill_calls += 1


class HungChild(FakeChild):
    def wait(self, timeout=None):
        if self.kill_calls:
            return -signal.SIGKILL
        if self.signal_to_invoke is not None:
            handler = signal.getsignal(self.signal_to_invoke)
            signum = self.signal_to_invoke
            self.signal_to_invoke = None
            handler(signum, None)
        raise extend_npt.subprocess.TimeoutExpired(["gmx", "mdrun"], timeout)


class ThermalGuardUnitTests(unittest.TestCase):
    def test_graceful_cleanup_resumes_then_terminates_owned_group(self):
        child = FakeChild(return_code=-signal.SIGTERM)
        with mock.patch.object(
            thermal_guard,
            "signal_process_group",
            return_value=True,
        ) as sender, mock.patch.object(
            thermal_guard,
            "process_group_exists",
            side_effect=[True, False, False],
        ), mock.patch.object(thermal_guard.time, "sleep"):
            result = thermal_guard.terminate_process_group(child, 777, 30.0)

        self.assertEqual(result, -signal.SIGTERM)
        self.assertEqual(
            sender.call_args_list[:2],
            [mock.call(777, signal.SIGCONT), mock.call(777, signal.SIGTERM)],
        )
        self.assertNotIn(mock.call(777, signal.SIGKILL), sender.call_args_list)

    def test_cleanup_escalates_after_bounded_grace(self):
        child = FakeChild(return_code=-signal.SIGKILL)
        with mock.patch.object(
            thermal_guard,
            "signal_process_group",
            return_value=True,
        ) as sender, mock.patch.object(
            thermal_guard,
            "process_group_exists",
            return_value=True,
        ), mock.patch.object(
            thermal_guard.time,
            "monotonic",
            side_effect=[0.0, 1.0],
        ):
            result = thermal_guard.terminate_process_group(child, 888, 0.0)

        self.assertEqual(result, -signal.SIGKILL)
        self.assertIn(mock.call(888, signal.SIGKILL), sender.call_args_list)

    def test_sensor_failures_are_reported_without_fake_temperature(self):
        with mock.patch.object(
            thermal_guard,
            "sensor_temperature_c",
            side_effect=RuntimeError("sensor absent"),
        ), mock.patch.object(
            thermal_guard,
            "command_output",
            side_effect=RuntimeError("pmset absent"),
        ):
            state = thermal_guard.thermal_state()

        self.assertFalse(state["monitor_available"])
        self.assertIsNone(state["max_temperature_c"])
        self.assertEqual(len(state["sensor_errors"]), 3)


class ExtensionChildSignalTests(unittest.TestCase):
    def run_with_fake_child(self, child: FakeChild):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "command.log"
            with mock.patch.object(
                extend_npt.subprocess,
                "Popen",
                return_value=child,
            ) as popen, mock.patch.object(
                extend_npt.signal,
                "pthread_sigmask",
                return_value=set(),
            ), mock.patch.object(extend_npt.os, "kill") as kill:
                result = extend_npt.run_to_new_log(["gmx", "mdrun"], Path(temporary), log)
            return result, popen, kill, log.read_text()

    def test_direct_term_is_forwarded_and_not_reported_as_success(self):
        result, popen, kill, log_text = self.run_with_fake_child(
            FakeChild(return_code=0, signal_to_invoke=signal.SIGTERM)
        )

        self.assertEqual(result, 128 + signal.SIGTERM)
        kill.assert_called_once_with(4242, signal.SIGTERM)
        self.assertIn("forwarded signal", log_text)
        self.assertNotIn("start_new_session", popen.call_args.kwargs)

    def test_normal_child_exit_is_preserved(self):
        result, _popen, kill, _log_text = self.run_with_fake_child(FakeChild(return_code=0))

        self.assertEqual(result, 0)
        kill.assert_not_called()

    def test_direct_term_escalates_if_child_ignores_grace(self):
        child = HungChild(signal_to_invoke=signal.SIGTERM)
        with mock.patch.object(
            extend_npt.time,
            "monotonic",
            side_effect=[0.0, extend_npt.CHILD_SIGNAL_GRACE_SECONDS + 1.0],
        ):
            result, _popen, kill, _log_text = self.run_with_fake_child(child)

        self.assertEqual(result, -signal.SIGKILL)
        self.assertEqual(child.kill_calls, 1)
        kill.assert_called_once_with(4242, signal.SIGTERM)

    def test_signal_mask_is_restored_if_exclusive_log_open_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "existing.log"
            log.write_text("do not replace\n")
            with mock.patch.object(
                extend_npt.signal,
                "pthread_sigmask",
                side_effect=[{signal.SIGUSR1}, set()],
            ) as mask:
                with self.assertRaises(FileExistsError):
                    extend_npt.run_to_new_log(["gmx", "mdrun"], Path(temporary), log)

        self.assertEqual(mask.call_count, 2)
        self.assertEqual(mask.call_args_list[0].args[0], signal.SIG_BLOCK)
        self.assertEqual(mask.call_args_list[1], mock.call(signal.SIG_SETMASK, {signal.SIGUSR1}))

    def test_extension_requires_exactly_six_threads(self):
        for threads in (5, 7, 8, 9):
            with self.subTest(threads=threads), mock.patch.object(
                sys,
                "argv",
                ["extend_npt.py", "/not/used", "--threads", str(threads)],
            ):
                with self.assertRaisesRegex(SystemExit, "exactly 6"):
                    extend_npt.main()


class BaseRunnerThreadPolicyTests(unittest.TestCase):
    def test_base_runner_accepts_exactly_six_threads(self):
        self.assertEqual(run_equilibration.MAC_SAFE_THREADS, 6)
        run_equilibration.require_mac_safe_threads(6)

    def test_base_runner_rejects_every_other_thread_count(self):
        for threads in (0, 1, 5, 7, 8, 12):
            with self.subTest(threads=threads):
                with self.assertRaisesRegex(ValueError, "exactly 6"):
                    run_equilibration.require_mac_safe_threads(threads)

    def test_ensure_mdrun_enforces_policy_before_touching_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            with self.assertRaisesRegex(ValueError, "exactly 6"):
                run_equilibration.ensure_mdrun(
                    "npt",
                    work,
                    8,
                    1000.0,
                    work / "chain.log",
                )

            self.assertEqual(list(work.iterdir()), [])


class ParentPackmolProvenanceTests(unittest.TestCase):
    def test_explicit_parent_seed_is_bound_to_input_log_and_coordinates(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            (run_dir / "input").mkdir()
            (run_dir / "input" / "pack.inp").write_text("seed 240101\n")
            (run_dir / "commands.log").write_text(
                "Seed for random number generator: 240101\n"
            )
            (run_dir / "input" / "initial.gro").write_text("coordinates\n")
            provenance = run_equilibration.parent_packmol_provenance(
                run_dir,
                {
                    "packmol_seed_requested": 240101,
                    "packmol_seed_observed": 240101,
                },
            )
            self.assertEqual(provenance["packmol_seed"], 240101)
            self.assertEqual(
                provenance["packmol_initial_gro_sha256"],
                run_equilibration.sha256(run_dir / "input" / "initial.gro"),
            )

    def test_ambiguous_or_mismatched_parent_seed_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            (run_dir / "input").mkdir()
            (run_dir / "input" / "pack.inp").write_text("seed 1\nseed 1\n")
            (run_dir / "commands.log").write_text(
                "Seed for random number generator: 1\n"
            )
            (run_dir / "input" / "initial.gro").write_text("coordinates\n")
            with self.assertRaisesRegex(RuntimeError, "missing or ambiguous"):
                run_equilibration.parent_packmol_provenance(
                    run_dir,
                    {"packmol_seed_requested": 1, "packmol_seed_observed": 1},
                )
            with self.assertRaisesRegex(RuntimeError, "requested/observed"):
                run_equilibration.parent_packmol_provenance(
                    run_dir,
                    {"packmol_seed_requested": 1, "packmol_seed_observed": 2},
                )


if __name__ == "__main__":
    unittest.main()
