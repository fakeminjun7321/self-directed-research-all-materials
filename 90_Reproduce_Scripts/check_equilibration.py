"""
5개 시스템 50 ps run의 에너지/온도/압력 안정성 점검.
- gmx energy로 .edr에서 Total-Energy, Temperature, Pressure 시계열 추출
- 5x3 시계열 그림 + 마지막 요약 표
"""

from __future__ import annotations

from pathlib import Path
import os
import subprocess
import numpy as np
import matplotlib.pyplot as plt
import csv

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "02_Processed_Data" / "MD_Runs" / "50ps_Practice"
OUT = ROOT / "03_Analysis_Results" / "Equilibration_Check"
FIG = ROOT / "04_Figures_For_Report" / "Comprehensive"
OUT.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

SYSTEMS = ["L1P1", "L1P2", "L2P1", "L3P1", "L1P3"]
COLORS5 = {"L1P1": "#000000", "L1P2": "#2ca02c", "L2P1": "#d62728",
           "L3P1": "#9467bd", "L1P3": "#1f77b4"}


def run_gmx_energy(work: Path, out_xvg: Path) -> None:
    if out_xvg.exists():
        return
    env = os.environ.copy()
    env["GMX_MAXBACKUP"] = "-1"
    # Total Energy, Temperature, Pressure
    sel = "Total-Energy\nTemperature\nPressure\n0\n"
    subprocess.run(
        ["gmx", "energy", "-f", "md_50ps.edr", "-o", str(out_xvg)],
        cwd=work, input=sel, text=True, env=env, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )


def read_xvg(path: Path) -> np.ndarray:
    rows = []
    for line in path.read_text(errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith(("#", "@")):
            continue
        rows.append([float(v) for v in s.split()])
    return np.array(rows, dtype=float)


def main() -> None:
    summary = []
    fig, axes = plt.subplots(3, 5, figsize=(17, 8), constrained_layout=True, sharex=True)

    for col, sys in enumerate(SYSTEMS):
        work = RUNS / sys
        out_xvg = OUT / f"{sys}_energy_temp_press.xvg"
        run_gmx_energy(work, out_xvg)
        data = read_xvg(out_xvg)
        t = data[:, 0]; e = data[:, 1]; T = data[:, 2]; P = data[:, 3]

        # 시계열
        c = COLORS5[sys]
        for row, (vals, ylab) in enumerate(zip([e, T, P],
                                                ["Total energy (kJ/mol)",
                                                 "Temperature (K)",
                                                 "Pressure (bar)"])):
            ax = axes[row, col]
            ax.plot(t, vals, color=c, lw=0.7)
            mean = vals.mean(); std = vals.std()
            ax.axhline(mean, color="grey", lw=0.6, ls="--", alpha=0.6)
            ax.set_xlim(0, t.max())
            if row == 0:
                ax.set_title(sys, fontsize=12)
            if col == 0:
                ax.set_ylabel(ylab, fontsize=10)
            if row == 2:
                ax.set_xlabel("t (ps)", fontsize=10)
            ax.grid(True, color="#eeeeee", lw=0.4)
            ax.text(0.98, 0.95, f"μ={mean:.1f}\nσ={std:.1f}",
                    transform=ax.transAxes, ha="right", va="top",
                    fontsize=8, bbox=dict(facecolor="white", edgecolor="none", alpha=0.7))

        summary.append({
            "system": sys, "frames": len(t),
            "E_mean": e.mean(), "E_std": e.std(),
            "T_mean": T.mean(), "T_std": T.std(),
            "P_mean": P.mean(), "P_std": P.std(),
        })

    fig.suptitle("Equilibration check — 50 ps NVT (E, T, P time series)", fontsize=13)
    out_fig = FIG / "equilibration_check.png"
    fig.savefig(out_fig, dpi=200, bbox_inches="tight")
    plt.close(fig)

    out_csv = OUT / "equilibration_summary.csv"
    with out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        for row in summary:
            w.writerow({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()})

    print(f"saved: {out_fig.relative_to(ROOT)}")
    print(f"saved: {out_csv.relative_to(ROOT)}")
    for s in summary:
        print(f"  {s['system']}: T = {s['T_mean']:.1f}±{s['T_std']:.1f} K, "
              f"P = {s['P_mean']:.1f}±{s['P_std']:.1f} bar")


if __name__ == "__main__":
    main()
