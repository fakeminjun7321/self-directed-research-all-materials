"""
교수님 'Simulation Summary' 슬라이드 형식 (제목 + 불릿 + 좌·우 RDF 그래프).
"""

from __future__ import annotations
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "03_Analysis_Results" / "RDF_CN" / "raw_xvg"
OUT = ROOT / "04_Figures_For_Report" / "RDF_CN" / "presentation_slide_simulation_summary.png"

SYSTEMS = ["L1P2", "L2P2", "L3P2"]
COLORS = {"L1P2": "#2ca02c", "L2P2": "#d62728", "L3P2": "#1f77b4"}


def read_xvg(p: Path) -> np.ndarray:
    rows = []
    for line in p.read_text(errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith(("#", "@")):
            continue
        rows.append([float(v) for v in s.split()])
    return np.array(rows, dtype=float)


def main() -> None:
    obt = {s: read_xvg(RAW / f"{s}_rdf_li_obt.xvg") for s in SYSTEMS}
    nbt = {s: read_xvg(RAW / f"{s}_rdf_li_nbt.xvg") for s in SYSTEMS}
    obt_max = max(d[:, 1].max() for d in obt.values()) * 1.06
    nbt_max = max(d[:, 1].max() for d in nbt.values()) * 1.06

    fig = plt.figure(figsize=(13, 7.6))
    # 본문(그래프)은 화면의 아래쪽 70%
    ax0 = fig.add_axes([0.07, 0.10, 0.41, 0.55])
    ax1 = fig.add_axes([0.55, 0.10, 0.41, 0.55])

    for s in SYSTEMS:
        d = obt[s]
        ax0.plot(d[:, 0], d[:, 1], color=COLORS[s], linewidth=1.9, label=s)
    ax0.set_xlim(0, 1.0)
    ax0.set_ylim(0, obt_max)
    ax0.set_xlabel("r (nm)", fontsize=12)
    ax0.set_ylabel(r"$g_{\rm Li-O(FSI)}(r)$", fontsize=12)
    ax0.legend(frameon=True, loc="upper right", fontsize=11)
    ax0.grid(True, color="#dddddd", linewidth=0.6)
    ax0.tick_params(labelsize=10)

    for s in SYSTEMS:
        d = nbt[s]
        ax1.plot(d[:, 0], d[:, 1], color=COLORS[s], linewidth=1.9, label=s)
    ax1.set_xlim(0, 0.9)
    ax1.set_ylim(0, nbt_max)
    ax1.set_xlabel("r (nm)", fontsize=12)
    ax1.set_ylabel(r"$g_{\rm Li-N(FSI)}(r)$", fontsize=12)
    ax1.legend(frameon=True, loc="upper right", fontsize=11)
    ax1.grid(True, color="#dddddd", linewidth=0.6)
    ax1.tick_params(labelsize=10)

    # 제목 + 불릿 (figure 좌표계)
    fig.text(0.07, 0.93, "Simulation Summary",
             fontsize=22, weight="bold", color="#1f2c4d")
    fig.add_artist(plt.Line2D([0.07, 0.97], [0.905, 0.905],
                              color="#1f2c4d", linewidth=1.0))
    fig.text(0.07, 0.85,
             "*  We are studying solvation structure of three configurations: L1P2, L2P2, L3P2",
             fontsize=12.5)
    fig.text(0.07, 0.80,
             "*  We computed the RDF and coordination number between Li and O(FSI), N(FSI)",
             fontsize=12.5)
    fig.text(0.07, 0.75,
             "*  Trajectory: 50 ps NVT (298 K), OPLS-style force field, GROMACS 2026.1",
             fontsize=11.5, color="#555555")

    fig.savefig(OUT, dpi=240)
    plt.close(fig)
    print(f"saved: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
