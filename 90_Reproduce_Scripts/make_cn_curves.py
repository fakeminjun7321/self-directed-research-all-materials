"""
누적 coordination number N(r) 곡선 비교.

각 시스템의 cumulative coordination number를 r에 대해 그려서
- 5개 오버레이 (Li-O / Li-N)
- L=1 라인, P=1 라인 분리
- RDF와 함께 더블 y축
모두 만든다.
"""

from __future__ import annotations
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "03_Analysis_Results" / "RDF_CN" / "raw_xvg"
OUT = ROOT / "04_Figures_For_Report" / "Comprehensive"
OUT.mkdir(parents=True, exist_ok=True)

SYSTEMS = ["L1P1", "L1P2", "L2P1", "L3P1", "L1P3"]
P_SERIES = ["L1P1", "L2P1", "L3P1"]
L_SERIES = ["L1P1", "L1P2", "L1P3"]
COLORS5 = {"L1P1": "#000000", "L1P2": "#2ca02c", "L2P1": "#d62728",
           "L3P1": "#9467bd", "L1P3": "#1f77b4"}


def read_xvg(p: Path) -> np.ndarray:
    rows = []
    for line in p.read_text(errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith(("#", "@")):
            continue
        rows.append([float(v) for v in s.split()])
    return np.array(rows, dtype=float)


def plot_overlay_5() -> Path:
    """5개 시스템 N(r) 오버레이 (Li-O, Li-N 2-panel)."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2), constrained_layout=True)
    for ax, key, title, ylim in zip(
        axes,
        ["li_obt", "li_nbt"],
        [r"Li-O(FSI):  $N_{Li-O}(r)$", r"Li-N(FSI):  $N_{Li-N}(r)$"],
        [(0, 14), (0, 8)],
    ):
        for sys in SYSTEMS:
            cn = read_xvg(RAW / f"{sys}_coordination_{key}.xvg")
            ax.plot(cn[:, 0], cn[:, 1], color=COLORS5[sys], lw=1.8, label=sys)
        ax.set_xlim(0, 0.8)
        ax.set_ylim(*ylim)
        ax.set_xlabel("r (nm)", fontsize=12)
        ax.set_ylabel("Cumulative coordination number  N(r)", fontsize=12)
        ax.set_title(title, fontsize=12)
        ax.grid(True, color="#eeeeee", lw=0.5)
        ax.legend(frameon=True, fontsize=11, loc="upper left")
    fig.suptitle("Cumulative coordination number N(r) — five systems", fontsize=13)
    out = OUT / "cn_curves_overlay.png"
    fig.savefig(out, dpi=240)
    plt.close(fig)
    return out


def plot_series() -> Path:
    """L=1 라인과 P=1 라인 별로 N(r) 비교."""
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.5), constrained_layout=True)
    rows_specs = [
        ("L=1 fixed, P 1->2->3", L_SERIES),
        ("P=1 fixed, L 1->2->3", P_SERIES),
    ]
    col_specs = [
        ("li_obt", r"$N_{Li-O(FSI)}(r)$", 14),
        ("li_nbt", r"$N_{Li-N(FSI)}(r)$", 8),
    ]
    for row, (title, series) in enumerate(rows_specs):
        for col, (key, ylab, ymax) in enumerate(col_specs):
            ax = axes[row, col]
            for sys in series:
                cn = read_xvg(RAW / f"{sys}_coordination_{key}.xvg")
                ax.plot(cn[:, 0], cn[:, 1], color=COLORS5[sys], lw=1.9, label=sys)
            ax.set_xlim(0, 0.8); ax.set_ylim(0, ymax)
            ax.set_xlabel("r (nm)", fontsize=11)
            ax.set_ylabel(ylab, fontsize=11)
            ax.legend(frameon=True, fontsize=11, loc="upper left")
            ax.grid(True, color="#eeeeee", lw=0.5)
            if col == 0:
                ax.text(-0.13, 0.5, title, transform=ax.transAxes, rotation=90,
                        va="center", ha="center", fontsize=12, weight="bold")
    fig.suptitle("Composition-series cumulative coordination number N(r)", fontsize=13)
    out = OUT / "cn_curves_by_series.png"
    fig.savefig(out, dpi=220)
    plt.close(fig)
    return out


def plot_rdf_with_cn_overlay() -> Path:
    """5개 시스템 RDF + N(r) (이중 y축) Li-O / Li-N 2-panel."""
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.4), constrained_layout=True)
    for ax, key, ylab_rdf, ylab_cn, cn_ymax in zip(
        axes, ["li_obt", "li_nbt"],
        [r"$g_{Li-O(FSI)}(r)$", r"$g_{Li-N(FSI)}(r)$"],
        [r"$N_{Li-O}(r)$", r"$N_{Li-N}(r)$"],
        [14, 8],
    ):
        ax2 = ax.twinx()
        rdf_ymax = 0
        for sys in SYSTEMS:
            rdf = read_xvg(RAW / f"{sys}_rdf_{key}.xvg")
            cn = read_xvg(RAW / f"{sys}_coordination_{key}.xvg")
            ax.plot(rdf[:, 0], rdf[:, 1], color=COLORS5[sys], lw=1.5, label=sys)
            ax2.plot(cn[:, 0], cn[:, 1], color=COLORS5[sys], lw=1.0, ls=":", alpha=0.85)
            rdf_ymax = max(rdf_ymax, rdf[rdf[:, 0] > 0.15, 1].max())
        ax.set_xlim(0, 0.8); ax.set_ylim(0, rdf_ymax * 1.08)
        ax.set_xlabel("r (nm)", fontsize=12)
        ax.set_ylabel(ylab_rdf, fontsize=12)
        ax.grid(True, color="#eeeeee", lw=0.5)
        ax.legend(frameon=True, fontsize=10, loc="upper right", ncol=2)
        ax2.set_ylim(0, cn_ymax)
        ax2.set_ylabel(ylab_cn + " (dotted)", fontsize=12)
    fig.suptitle("g(r) (solid) and cumulative N(r) (dotted) — five systems", fontsize=13)
    out = OUT / "rdf_with_cn_curves_5systems.png"
    fig.savefig(out, dpi=240)
    plt.close(fig)
    return out


def main() -> None:
    outs = [plot_overlay_5(), plot_series(), plot_rdf_with_cn_overlay()]
    print("saved:")
    for p in outs:
        print(" ", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
