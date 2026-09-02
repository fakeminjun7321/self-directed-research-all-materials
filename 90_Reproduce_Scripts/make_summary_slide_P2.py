"""
교수님 'Simulation Summary' 슬라이드(L1P2, L2P2, L3P2 RDF 오버레이) 재현.

- 왼쪽: g_Li-O(FSI)(r) 비교
- 오른쪽: g_Li-N(FSI)(r) 비교
- 색상: L1P2(녹색), L2P2(빨강), L3P2(파랑) — 교수님 슬라이드와 동일 컬러
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "03_Analysis_Results" / "RDF_CN" / "raw_xvg"
OUT_FIG_DIR = ROOT / "04_Figures_For_Report" / "RDF_CN"
OUT_ANAL_DIR = ROOT / "03_Analysis_Results" / "RDF_CN"

SYSTEMS = ["L1P2", "L2P2", "L3P2"]
COLORS = {"L1P2": "#2ca02c", "L2P2": "#d62728", "L3P2": "#1f77b4"}


def read_xvg(path: Path) -> np.ndarray:
    rows: list[list[float]] = []
    for line in path.read_text(errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "@")):
            continue
        rows.append([float(v) for v in stripped.split()])
    return np.array(rows, dtype=float)


def plot_summary_slide(filename: str, title: str) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.9), constrained_layout=True)

    # 데이터 로드 후 자동 y범위
    obt_data = {sys: read_xvg(RAW / f"{sys}_rdf_li_obt.xvg") for sys in SYSTEMS}
    nbt_data = {sys: read_xvg(RAW / f"{sys}_rdf_li_nbt.xvg") for sys in SYSTEMS}
    obt_ymax = max(d[:, 1].max() for d in obt_data.values()) * 1.08
    nbt_ymax = max(d[:, 1].max() for d in nbt_data.values()) * 1.08

    ax0 = axes[0]
    for sys in SYSTEMS:
        rdf = obt_data[sys]
        ax0.plot(rdf[:, 0], rdf[:, 1], color=COLORS[sys], linewidth=1.6, label=sys)
    ax0.set_xlim(0, 1.0)
    ax0.set_ylim(0, obt_ymax)
    ax0.set_xlabel("r (nm)", fontsize=11)
    ax0.set_ylabel("g$_{Li-O(FSI)}$(r)", fontsize=11)
    ax0.legend(loc="upper right", frameon=True, fontsize=10)
    ax0.grid(True, color="#dddddd", linewidth=0.5)

    ax1 = axes[1]
    for sys in SYSTEMS:
        rdf = nbt_data[sys]
        ax1.plot(rdf[:, 0], rdf[:, 1], color=COLORS[sys], linewidth=1.6, label=sys)
    ax1.set_xlim(0, 0.9)
    ax1.set_ylim(0, nbt_ymax)
    ax1.set_xlabel("r (nm)", fontsize=11)
    ax1.set_ylabel("g$_{Li-N(FSI)}$(r)", fontsize=11)
    ax1.legend(loc="upper right", frameon=True, fontsize=10)
    ax1.grid(True, color="#dddddd", linewidth=0.5)

    fig.suptitle(title, fontsize=13, x=0.02, ha="left")
    out = OUT_FIG_DIR / filename
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=240)
    plt.close(fig)
    return out


def plot_combined_with_cn(filename: str) -> Path:
    """RDF + coordination number까지 함께 보여주는 2-panel 비교 (자동 y범위)."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)

    pairs = [
        (axes[0], "li_obt", "g$_{Li-O(FSI)}$(r)"),
        (axes[1], "li_nbt", "g$_{Li-N(FSI)}$(r)"),
    ]
    for ax, key, ylabel in pairs:
        rdf_data = {sys: read_xvg(RAW / f"{sys}_rdf_{key}.xvg") for sys in SYSTEMS}
        cn_data = {sys: read_xvg(RAW / f"{sys}_coordination_{key}.xvg") for sys in SYSTEMS}
        rdf_ymax = max(d[:, 1].max() for d in rdf_data.values()) * 1.08
        cn_ymax = max(d[:, 1].max() for d in cn_data.values()) * 1.08

        ax2 = ax.twinx()
        for sys in SYSTEMS:
            rdf = rdf_data[sys]
            cn = cn_data[sys]
            ax.plot(rdf[:, 0], rdf[:, 1], color=COLORS[sys], linewidth=1.6, label=sys)
            ax2.plot(cn[:, 0], cn[:, 1], color=COLORS[sys], linewidth=1.1,
                     linestyle=":", alpha=0.8)
        ax.set_xlim(0, 1.0)
        ax.set_ylim(0, rdf_ymax)
        ax.set_xlabel("r (nm)", fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.grid(True, color="#dddddd", linewidth=0.5)
        ax.legend(loc="upper right", frameon=True, fontsize=10)
        ax2.set_ylabel("Coordination number", fontsize=11)
        ax2.set_ylim(0, cn_ymax)

    fig.suptitle("L1P2 / L2P2 / L3P2 — RDF (solid) and cumulative coordination number (dotted)",
                 fontsize=13, x=0.02, ha="left")
    out = OUT_FIG_DIR / filename
    fig.savefig(out, dpi=240)
    plt.close(fig)
    return out


def write_summary_table() -> Path:
    """L1P2/L2P2/L3P2 비교 표 별도 저장."""
    import csv
    src = OUT_ANAL_DIR / "coordination_number_li_o_n_summary.csv"
    rows = list(csv.DictReader(src.open()))
    selected = [r for r in rows if r["system"] in SYSTEMS]
    out = OUT_ANAL_DIR / "summary_table_P2_series.csv"
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(selected[0].keys()))
        writer.writeheader()
        for r in selected:
            writer.writerow(r)
    return out


def plot_cn_bar() -> Path:
    """L1P2 / L2P2 / L3P2 coordination number 막대 비교."""
    import csv
    src = OUT_ANAL_DIR / "coordination_number_li_o_n_summary.csv"
    rows = list(csv.DictReader(src.open()))
    o_cn = [float(next(r for r in rows if r["system"] == s and r["pair"] == "Li-O(FSI)")["coordination_number"]) for s in SYSTEMS]
    n_cn = [float(next(r for r in rows if r["system"] == s and r["pair"] == "Li-N(FSI)")["coordination_number"]) for s in SYSTEMS]

    fig, ax = plt.subplots(figsize=(8.4, 4.8), constrained_layout=True)
    x = np.arange(len(SYSTEMS))
    w = 0.36
    bars_o = ax.bar(x - w / 2, o_cn, w, color="#4c78a8", label="Li-O(FSI)")
    bars_n = ax.bar(x + w / 2, n_cn, w, color="#f58518", label="Li-N(FSI)")
    for bar in list(bars_o) + list(bars_n):
        h = bar.get_height()
        ax.annotate(f"{h:.2f}", (bar.get_x() + bar.get_width() / 2, h),
                    ha="center", va="bottom", fontsize=10)
    ax.set_xticks(x, SYSTEMS, fontsize=12)
    ax.set_ylabel("Coordination number", fontsize=12)
    ax.set_title("L1P2 / L2P2 / L3P2 — first-shell coordination number")
    ax.set_ylim(0, max(max(o_cn), max(n_cn)) * 1.18)
    ax.grid(True, axis="y", color="#dddddd", linewidth=0.6)
    ax.legend(frameon=False, fontsize=11)
    out = OUT_FIG_DIR / "P2_series_coordination_number_bar.png"
    fig.savefig(out, dpi=240)
    plt.close(fig)
    return out


def main() -> None:
    a = plot_summary_slide("summary_slide_P2_series_overlay.png",
                           "L1P2 / L2P2 / L3P2 — Li-O(FSI), Li-N(FSI) RDF")
    b = plot_combined_with_cn("summary_slide_P2_series_with_CN.png")
    c = write_summary_table()
    d = plot_cn_bar()
    print("saved:")
    for p in (a, b, c, d):
        print(" ", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
