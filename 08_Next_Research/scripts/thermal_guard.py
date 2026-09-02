#!/usr/bin/env python3
"""Pause a local simulation at a thermal threshold and resume after cooling."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def command_output(command: list[str], timeout_seconds: float = 5.0) -> str:
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=True,
        timeout=timeout_seconds,
    ).stdout.strip()


def sensor_temperature_c(key: str) -> float:
    raw = float(
        command_output(
            [
                "sh",
                "-c",
                f"ioreg -r -c AppleSmartBattery -a | plutil -extract 0.{key} raw -",
            ]
        )
    )
    if key == "Temperature":
        value = raw / 10.0 - 273.15
    elif key == "VirtualTemperature":
        value = raw / 100.0
    else:
        raise ValueError(f"unsupported sensor key: {key}")
    if not math.isfinite(value):
        raise ValueError(f"non-finite sensor value for {key}: {value}")
    return value


def thermal_state() -> dict[str, object]:
    sensor_errors: list[str] = []
    temperatures: dict[str, float] = {}
    for key in ("Temperature", "VirtualTemperature"):
        try:
            temperatures[key] = sensor_temperature_c(key)
        except Exception as exc:  # the macOS key can be absent on some hardware
            sensor_errors.append(f"{key}: {type(exc).__name__}: {exc}")
    try:
        pmset = command_output(["pmset", "-g", "therm"])
        pmset_available = True
    except Exception as exc:
        pmset = ""
        pmset_available = False
        sensor_errors.append(f"pmset: {type(exc).__name__}: {exc}")
    thermal_warning = pmset_available and "No thermal warning level has been recorded" not in pmset
    performance_warning = (
        pmset_available and "No performance warning level has been recorded" not in pmset
    )
    return {
        "temperatures_c": temperatures,
        "max_temperature_c": max(temperatures.values()) if temperatures else None,
        "sensor_errors": sensor_errors,
        "thermal_warning": thermal_warning,
        "performance_warning": performance_warning,
        "monitor_available": bool(temperatures) or pmset_available,
        "pmset_summary": [line.strip() for line in pmset.splitlines() if line.strip()],
    }


def append_event(path: Path, event: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
        handle.flush()


def process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def process_group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def signal_process_group(pgid: int, sig: signal.Signals) -> bool:
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        return False
    return True


def terminate_process_group(
    child: subprocess.Popen[str], pgid: int, grace_seconds: float
) -> int:
    """Resume a stopped owned group, request termination, then bound the wait."""
    signal_process_group(pgid, signal.SIGCONT)
    signal_process_group(pgid, signal.SIGTERM)
    deadline = time.monotonic() + grace_seconds
    while process_group_exists(pgid) and time.monotonic() < deadline:
        child.poll()
        time.sleep(0.1)
    if process_group_exists(pgid):
        signal_process_group(pgid, signal.SIGKILL)
    try:
        return child.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        signal_process_group(pgid, signal.SIGKILL)
        return child.wait(timeout=5.0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attach-pid", type=int)
    parser.add_argument("--high-c", type=float, default=60.0)
    parser.add_argument("--resume-c", type=float, default=50.0)
    parser.add_argument("--poll-seconds", type=float, default=15.0)
    parser.add_argument("--terminate-grace-seconds", type=float, default=30.0)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not all(
        math.isfinite(value)
        for value in (args.high_c, args.resume_c, args.poll_seconds, args.terminate_grace_seconds)
    ):
        raise SystemExit("thermal thresholds and intervals must be finite")
    if args.resume_c >= args.high_c:
        raise SystemExit("--resume-c must be lower than --high-c")
    if args.poll_seconds < 5.0 or args.poll_seconds > 60.0:
        raise SystemExit("--poll-seconds must be between 5 and 60")
    if args.terminate_grace_seconds < 5.0 or args.terminate_grace_seconds > 120.0:
        raise SystemExit("--terminate-grace-seconds must be between 5 and 120")
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if (args.attach_pid is None) == (not command):
        raise SystemExit("provide exactly one of --attach-pid or a command after --")

    requested_signal: int | None = None
    guard_error: Exception | None = None

    def request_stop(signum: int, _frame: object) -> None:
        nonlocal requested_signal
        if requested_signal is None:
            requested_signal = signum

    handled_signals = [signal.SIGTERM, signal.SIGINT]
    for optional_name in ("SIGHUP", "SIGQUIT"):
        optional_signal = getattr(signal, optional_name, None)
        if optional_signal is not None:
            handled_signals.append(optional_signal)
    for handled_signal in handled_signals:
        signal.signal(handled_signal, request_stop)

    append_event(args.log, {"at": now(), "event": "GUARD_INITIALIZING"})
    if requested_signal is not None:
        append_event(
            args.log,
            {"at": now(), "event": "GUARD_SIGNAL_BEFORE_CHILD", "signal": requested_signal},
        )
        raise SystemExit(128 + requested_signal)
    child: subprocess.Popen[str] | None = None
    if args.attach_pid is not None:
        target_pid = args.attach_pid
        if target_pid <= 1 or target_pid == os.getpid() or not process_exists(target_pid):
            raise SystemExit(f"invalid or absent --attach-pid: {target_pid}")
        target_pgid: int | None = None
    else:
        child = subprocess.Popen(command, start_new_session=True, text=True)
        target_pid = child.pid
        target_pgid = os.getpgid(child.pid)

    paused = False

    def signal_target(sig: signal.Signals) -> None:
        try:
            if target_pgid is not None:
                signal_process_group(target_pgid, sig)
            else:
                os.kill(target_pid, sig)
        except ProcessLookupError:
            return

    def target_running() -> bool:
        if child is not None:
            child.poll()
            return process_group_exists(target_pgid)
        return process_exists(target_pid)

    return_code = 0
    try:
        append_event(
            args.log,
            {
                "at": now(),
                "event": "GUARD_STARTED",
                "target_pid": target_pid,
                "target_pgid": target_pgid,
                "high_c": args.high_c,
                "resume_c": args.resume_c,
                "poll_seconds": args.poll_seconds,
                "sensor_scope": "battery_and_virtual_thermal_sensors_not_CPU_die",
            },
        )
        while target_running() and requested_signal is None:
            state = thermal_state()
            event = {"at": now(), "event": "SAMPLE", "paused": paused, **state}
            append_event(args.log, event)
            maximum = state["max_temperature_c"]
            warning = bool(state["thermal_warning"] or state["performance_warning"])
            monitor_available = bool(state["monitor_available"])
            should_pause = (
                not monitor_available
                or warning
                or (isinstance(maximum, float) and maximum >= args.high_c)
            )
            should_resume = (
                paused
                and monitor_available
                and not warning
                and (maximum is None or (isinstance(maximum, float) and maximum <= args.resume_c))
            )
            if not paused and should_pause:
                signal_target(signal.SIGSTOP)
                paused = True
                append_event(
                    args.log,
                    {"at": now(), "event": "PAUSED", "reason": "temperature_or_pmset_warning", **state},
                )
            elif should_resume:
                signal_target(signal.SIGCONT)
                paused = False
                append_event(args.log, {"at": now(), "event": "RESUMED", **state})
            time.sleep(args.poll_seconds)
    except Exception as exc:
        guard_error = exc
    finally:
        if requested_signal is not None:
            try:
                append_event(
                    args.log,
                    {"at": now(), "event": "GUARD_SIGNAL", "signal": requested_signal},
                )
            except Exception:
                pass
        if guard_error is not None:
            try:
                append_event(
                    args.log,
                    {
                        "at": now(),
                        "event": "GUARD_ERROR",
                        "detail": f"{type(guard_error).__name__}: {guard_error}",
                    },
                )
            except Exception:
                pass
        if paused and target_running():
            try:
                if child is not None:
                    signal_target(signal.SIGCONT)
                    append_event(args.log, {"at": now(), "event": "RESUMED_ON_GUARD_EXIT"})
                else:
                    append_event(
                        args.log,
                        {
                            "at": now(),
                            "event": "ATTACHED_TARGET_LEFT_PAUSED_ON_GUARD_EXIT",
                            "manual_resume_command": f"kill -CONT {target_pid}",
                        },
                    )
            except Exception:
                pass
        if child is not None:
            if (requested_signal is not None or guard_error is not None) and target_running():
                return_code = terminate_process_group(
                    child,
                    target_pgid,
                    args.terminate_grace_seconds,
                )
            else:
                return_code = child.wait()
        if requested_signal is not None:
            return_code = 128 + requested_signal
        elif guard_error is not None:
            return_code = 70
        try:
            append_event(
                args.log,
                {"at": now(), "event": "GUARD_FINISHED", "target_return_code": return_code},
            )
        except Exception:
            pass
    raise SystemExit(return_code)


if __name__ == "__main__":
    main()
