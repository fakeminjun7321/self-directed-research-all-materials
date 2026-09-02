"""
5개 시스템(L1P1, L1P2, L2P1, L3P1, L1P3)에 대해 보고서/발표용 종합 그림 묶음.

생성물:
- five_systems_rdf_grid.png : 모든 시스템 RDF (Li-O, Li-N) 격자
- composition_series_overlay.png : 조성 시리즈 두 라인 (P=1, L=1) 비교
- coordination_number_summary_bar.png : 5개 CN 막대
- cn_distribution_histograms.png : Li 주변 O/N 개수 분포
- speciation_stacked_bar.png : Free/CIP/AGG-I/AGG-II 누적 막대
- extended_rdf_overview.png : Li-N4, Li-Li, NBT-NBT, N4-NBT 4-pair 격자
- structure_property_dashboard.png : 한 장 dashboard
"""

from __future__ import annotations

from pathlib import Path
import csv
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

ROOT = Path(__file__).resolve().parents[1]
RDF_DIR = ROOT / "03_Analysis_Results" / "RDF_CN" / "raw_xvg"
EXT_DIR = ROOT / "03_Analysis_Results" / "Extended_RDF" / "raw_xvg"
SPEC_CSV = ROOT / "03_Analysis_Results" / "Speciation" / "speciation_fractions.csv"
CN_DIST_CSV = ROOT / "03_Analysis_Results" / "CN_Distribution" / "cn_distribution.csv"
GEN_DIR = ROOT / "03_Analysis_Results" / "General_Analysis"
SUMMARY_CSV = ROOT / "03_Analysis_Results" / "RDF_CN" / "coordination_number_li_o_n_summary.csv"
GEN_SUMMARY_CSV = GEN_DIR / "summary.csv"
OUT = ROOT / "04_Figures_For_Report" / "Comprehensive"
OUT.mkdir(parents=True, exist_ok=True)

SYSTEMS = ["L1P1", "L1P2", "L2P1", "L3P1", "L1P3"]
P_SERIES = ["L1P1", "L2P1", "L3P1"]  # Li 비율 증가, Pyr 고정
L_SERIES = ["L1P1", "L1P2", "L1P3"]  # Pyr 비율 증가, Li 고정
COMPOSITIONS = {
    "L1P1": (25, 25, 50),  # Li, Pyr, FSI
    "L1P2": (25, 50, 75),
    "L1P3": (25, 75, 100),
    "L2P1": (50, 25, 75),
    "L3P1": (75, 25, 100),
}
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


# ────────────────────────────────────────────────────────────────────────
def fig_five_systems_grid() -> Path:
    fig, axes = plt.subplots(5, 2, figsize=(12, 14), sharex="col", constrained_layout=True)
    for i, sys in enumerate(SYSTEMS):
        for j, (key, ylab) in enumerate([("li_obt", r"$g_{Li-O(FSI)}(r)$"),
                                          ("li_nbt", r"$g_{Li-N(FSI)}(r)$")]):
            rdf = read_xvg(RDF_DIR / f"{sys}_rdf_{key}.xvg")
            cn = read_xvg(RDF_DIR / f"{sys}_coordination_{key}.xvg")
            ax = axes[i, j]
            ax2 = ax.twinx()
            ax.plot(rdf[:, 0], rdf[:, 1], color=COLORS5[sys], lw=1.4)
            ax2.plot(cn[:, 0], cn[:, 1], color="grey", lw=1.0, ls=":", alpha=0.7)
            ax.set_xlim(0, 0.9)
            ax.grid(True, color="#eeeeee", lw=0.5)
            if i == 0:
                ax.set_title(ylab.replace("g_", "g$_{").replace("(r)", "}$(r)"), fontsize=12)
            if i == 4:
                ax.set_xlabel("r (nm)", fontsize=11)
            ax.set_ylabel(f"{sys}", fontsize=11)
            ax2.set_ylabel("CN", fontsize=9, color="grey")
            ax2.tick_params(axis='y', labelcolor="grey", labelsize=8)
    fig.suptitle("Per-system RDF (solid) and cumulative coordination number (dotted)",
                 fontsize=14, y=1.005)
    out = OUT / "five_systems_rdf_grid.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out


# ────────────────────────────────────────────────────────────────────────
def fig_composition_series() -> Path:
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 8), constrained_layout=True)
    series_specs = [
        ("L=1 fixed, P varies (1→2→3)", L_SERIES),
        ("P=1 fixed, L varies (1→2→3)", P_SERIES),
    ]
    pair_specs = [
        ("li_obt", r"$g_{Li-O(FSI)}(r)$", 0.9),
        ("li_nbt", r"$g_{Li-N(FSI)}(r)$", 0.9),
    ]
    for row, (title, series) in enumerate(series_specs):
        for col, (key, ylab, xmax) in enumerate(pair_specs):
            ax = axes[row, col]
            ymax = 0
            for sys in series:
                rdf = read_xvg(RDF_DIR / f"{sys}_rdf_{key}.xvg")
                ax.plot(rdf[:, 0], rdf[:, 1], color=COLORS5[sys], lw=1.8, label=sys)
                ymax = max(ymax, rdf[rdf[:, 0] > 0.15, 1].max())
            ax.set_xlim(0, xmax)
            ax.set_ylim(0, ymax * 1.08)
            ax.set_xlabel("r (nm)", fontsize=11)
            ax.set_ylabel(ylab, fontsize=11)
            ax.legend(frameon=True, fontsize=10, loc="upper right")
            ax.grid(True, color="#eeeeee", lw=0.5)
            if col == 0:
                ax.text(-0.13, 0.5, title, transform=ax.transAxes,
                        rotation=90, va="center", ha="center", fontsize=11, weight="bold")
    fig.suptitle("Composition-series RDF comparison", fontsize=14)
    out = OUT / "composition_series_overlay.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


# ────────────────────────────────────────────────────────────────────────
def fig_cn_summary_bar() -> Path:
    rows = list(csv.DictReader(SUMMARY_CSV.open()))
    o = {s: float(next(r for r in rows if r["system"] == s and r["pair"] == "Li-O(FSI)")["coordination_number"]) for s in SYSTEMS}
    n = {s: float(next(r for r in rows if r["system"] == s and r["pair"] == "Li-N(FSI)")["coordination_number"]) for s in SYSTEMS}
    fig, ax = plt.subplots(figsize=(9.5, 4.6), constrained_layout=True)
    x = np.arange(len(SYSTEMS))
    w = 0.36
    b1 = ax.bar(x - w/2, [o[s] for s in SYSTEMS], w, color="#4c78a8", label="Li-O(FSI)")
    b2 = ax.bar(x + w/2, [n[s] for s in SYSTEMS], w, color="#f58518", label="Li-N(FSI)")
    for bar in list(b1) + list(b2):
        ax.annotate(f"{bar.get_height():.2f}", (bar.get_x() + bar.get_width()/2, bar.get_height()),
                    ha="center", va="bottom", fontsize=10)
    ax.set_xticks(x, SYSTEMS, fontsize=12)
    ax.set_ylabel("Coordination number", fontsize=12)
    ax.set_title("First-shell coordination number — 5 systems")
    ax.set_ylim(0, max(max(o.values()), max(n.values())) * 1.2)
    ax.grid(True, axis="y", color="#eeeeee", lw=0.6)
    ax.legend(frameon=False, fontsize=11)
    out = OUT / "coordination_number_summary_bar.png"
    fig.savefig(out, dpi=240)
    plt.close(fig)
    return out


# ────────────────────────────────────────────────────────────────────────
def fig_cn_histograms() -> Path:
    with CN_DIST_CSV.open() as f:
        reader = csv.reader(f)
        header = next(reader)
        n_cols = [c for c in header if c.startswith("n=")]
        rows = list(reader)
    o_data: dict[str, np.ndarray] = {}
    n_data: dict[str, np.ndarray] = {}
    for r in rows:
        vals = np.array(r[4:], dtype=float)
        total = vals.sum()
        if total > 0:
            vals = vals / total
        if r[1] == "Li-O(FSI)":
            o_data[r[0]] = vals
        else:
            n_data[r[0]] = vals

    fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    x = np.arange(len(n_cols))
    w = 0.16
    for k, sys in enumerate(SYSTEMS):
        axes[0].bar(x + (k - 2) * w, o_data[sys], w, color=COLORS5[sys], label=sys, alpha=0.9)
        axes[1].bar(x + (k - 2) * w, n_data[sys], w, color=COLORS5[sys], label=sys, alpha=0.9)
    for ax, title in zip(axes, ["Li-O(FSI) coordination number distribution",
                                 "Li-N(FSI) coordination number distribution"]):
        ax.set_xticks(x, [c.replace("n=", "") for c in n_cols], fontsize=10)
        ax.set_xlabel("Number in 1st shell (n)", fontsize=11)
        ax.set_ylabel("Probability", fontsize=11)
        ax.set_title(title)
        ax.grid(True, axis="y", color="#eeeeee", lw=0.5)
        ax.legend(frameon=False, fontsize=10, ncol=2)
        ax.set_xlim(-0.5, len(n_cols) - 0.5)
    out = OUT / "cn_distribution_histograms.png"
    fig.savefig(out, dpi=220)
    plt.close(fig)
    return out


# ────────────────────────────────────────────────────────────────────────
def fig_speciation_stacked() -> Path:
    rows = list(csv.DictReader(SPEC_CSV.open()))
    labels = ["Free", "CIP", "AGG-I", "AGG-II"]
    bottoms = np.zeros(len(SYSTEMS))
    colors = ["#9bc6e1", "#f2cb6c", "#f4a261", "#c75c5c"]
    fig, ax = plt.subplots(figsize=(8.6, 5.0), constrained_layout=True)
    x = np.arange(len(SYSTEMS))
    for color, lbl in zip(colors, labels):
        vals = np.array([float(next(r for r in rows if r["system"] == s)[lbl]) for s in SYSTEMS])
        bars = ax.bar(x, vals, 0.6, bottom=bottoms, color=color, label=lbl, edgecolor="white", linewidth=1.2)
        for bar in bars:
            h = bar.get_height()
            if h > 0.03:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_y() + h/2,
                        f"{h*100:.1f}%", ha="center", va="center", fontsize=9, color="white", weight="bold")
        bottoms += vals
    ax.set_xticks(x, SYSTEMS, fontsize=12)
    ax.set_ylabel("Fraction of Li ions", fontsize=12)
    ax.set_ylim(0, 1.05)
    ax.set_title("Li+ speciation: Free / CIP / AGG-I / AGG-II  (R_cut = 0.33 nm)")
    ax.legend(loc="lower right", frameon=True, fontsize=10, ncol=4)
    ax.grid(True, axis="y", color="#eeeeee", lw=0.5)
    out = OUT / "speciation_stacked_bar.png"
    fig.savefig(out, dpi=240)
    plt.close(fig)
    return out


# ────────────────────────────────────────────────────────────────────────
def fig_extended_rdf_grid() -> Path:
    pairs = [("li_n4", "Li-N4(Pyr+)"), ("li_li", "Li-Li"),
             ("nbt_nbt", "N(FSI)-N(FSI)"), ("n4_nbt", "N4(Pyr+)-N(FSI)")]
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 8.5), constrained_layout=True)
    for ax, (key, title) in zip(axes.flatten(), pairs):
        ymax = 0
        for sys in SYSTEMS:
            rdf = read_xvg(EXT_DIR / f"{sys}_rdf_{key}.xvg")
            ax.plot(rdf[:, 0], rdf[:, 1], color=COLORS5[sys], lw=1.4, label=sys)
            if rdf[rdf[:, 0] > 0.15, 1].size:
                ymax = max(ymax, rdf[rdf[:, 0] > 0.15, 1].max())
        ax.set_xlim(0, 1.5)
        ax.set_ylim(0, ymax * 1.1)
        ax.set_xlabel("r (nm)", fontsize=11)
        ax.set_ylabel(f"g(r)", fontsize=11)
        ax.set_title(title, fontsize=12)
        ax.grid(True, color="#eeeeee", lw=0.5)
        ax.legend(frameon=True, fontsize=9, loc="upper right", ncol=2)
    fig.suptitle("Extended RDFs — cation/anion correlations", fontsize=14, y=1.005)
    out = OUT / "extended_rdf_overview.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


# ────────────────────────────────────────────────────────────────────────
def fig_dashboard() -> Path:
    """모든 핵심 결과를 한 장에 — Li-O RDF + CN bar + speciation + diffusion + composition table."""
    fig = plt.figure(figsize=(16, 10))
    gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.45, wspace=0.35,
                           left=0.06, right=0.97, top=0.94, bottom=0.06)

    # 좌상: Li-O(FSI) RDF (5개 오버레이)
    ax = fig.add_subplot(gs[0, 0])
    ymax = 0
    for sys in SYSTEMS:
        rdf = read_xvg(RDF_DIR / f"{sys}_rdf_li_obt.xvg")
        ax.plot(rdf[:, 0], rdf[:, 1], color=COLORS5[sys], lw=1.3, label=sys)
        ymax = max(ymax, rdf[rdf[:, 0] > 0.15, 1].max())
    ax.set_xlim(0, 0.8); ax.set_ylim(0, ymax * 1.1)
    ax.set_xlabel("r (nm)"); ax.set_ylabel(r"$g_{\rm Li-O(FSI)}(r)$")
    ax.set_title("Li-O(FSI) RDF"); ax.grid(True, color="#eeeeee", lw=0.4)
    ax.legend(frameon=False, fontsize=8, loc="upper right", ncol=2)

    # 중상: Li-N(FSI) RDF
    ax = fig.add_subplot(gs[0, 1])
    ymax = 0
    for sys in SYSTEMS:
        rdf = read_xvg(RDF_DIR / f"{sys}_rdf_li_nbt.xvg")
        ax.plot(rdf[:, 0], rdf[:, 1], color=COLORS5[sys], lw=1.3, label=sys)
        ymax = max(ymax, rdf[rdf[:, 0] > 0.15, 1].max())
    ax.set_xlim(0, 0.8); ax.set_ylim(0, ymax * 1.1)
    ax.set_xlabel("r (nm)"); ax.set_ylabel(r"$g_{\rm Li-N(FSI)}(r)$")
    ax.set_title("Li-N(FSI) RDF"); ax.grid(True, color="#eeeeee", lw=0.4)
    ax.legend(frameon=False, fontsize=8, loc="upper right", ncol=2)

    # 우상: 조성 테이블
    ax = fig.add_subplot(gs[0, 2])
    ax.axis("off")
    cell_text = [[s, str(COMPOSITIONS[s][0]), str(COMPOSITIONS[s][1]),
                  str(COMPOSITIONS[s][2])] for s in SYSTEMS]
    table = ax.table(cellText=cell_text, colLabels=["System", "Li+", "Pyr13+", "FSI-"],
                     loc="center", cellLoc="center", colWidths=[0.18, 0.16, 0.18, 0.16])
    table.auto_set_font_size(False); table.set_fontsize(11); table.scale(1.0, 1.7)
    ax.set_title("Composition (per box)", fontsize=12, pad=10)

    # CN 막대
    ax = fig.add_subplot(gs[1, 0])
    rows = list(csv.DictReader(SUMMARY_CSV.open()))
    o = [float(next(r for r in rows if r["system"] == s and r["pair"] == "Li-O(FSI)")["coordination_number"]) for s in SYSTEMS]
    n = [float(next(r for r in rows if r["system"] == s and r["pair"] == "Li-N(FSI)")["coordination_number"]) for s in SYSTEMS]
    x = np.arange(len(SYSTEMS)); w = 0.36
    ax.bar(x - w/2, o, w, color="#4c78a8", label="Li-O(FSI)")
    ax.bar(x + w/2, n, w, color="#f58518", label="Li-N(FSI)")
    ax.set_xticks(x, SYSTEMS, fontsize=10)
    ax.set_ylabel("Coordination number"); ax.set_title("First-shell CN")
    ax.legend(frameon=False, fontsize=10); ax.grid(True, axis="y", color="#eeeeee", lw=0.4)

    # Speciation 누적
    ax = fig.add_subplot(gs[1, 1])
    spec_rows = list(csv.DictReader(SPEC_CSV.open()))
    labels = ["Free", "CIP", "AGG-I", "AGG-II"]
    colors = ["#9bc6e1", "#f2cb6c", "#f4a261", "#c75c5c"]
    bottoms = np.zeros(len(SYSTEMS))
    for color, lbl in zip(colors, labels):
        vals = np.array([float(next(r for r in spec_rows if r["system"] == s)[lbl]) for s in SYSTEMS])
        ax.bar(x, vals, 0.6, bottom=bottoms, color=color, label=lbl, edgecolor="white", lw=1.2)
        bottoms += vals
    ax.set_xticks(x, SYSTEMS, fontsize=10); ax.set_ylim(0, 1.05)
    ax.set_ylabel("Fraction of Li+"); ax.set_title("Li+ speciation")
    ax.legend(frameon=False, fontsize=9, ncol=4, loc="lower center", bbox_to_anchor=(0.5, -0.02))
    ax.grid(True, axis="y", color="#eeeeee", lw=0.4)

    # Diffusion (general analysis summary 사용)
    ax = fig.add_subplot(gs[1, 2])
    gen_rows = {r["label"]: r for r in csv.DictReader(GEN_SUMMARY_CSV.open())}
    d_li = [float(gen_rows[s]["diffusion_li_m2_s"]) * 1e9 for s in SYSTEMS]  # 10^-9 m^2/s
    d_pyr = [float(gen_rows[s]["diffusion_pyr13_m2_s"]) * 1e9 for s in SYSTEMS]
    d_fsi = [float(gen_rows[s]["diffusion_fsi_m2_s"]) * 1e9 for s in SYSTEMS]
    w3 = 0.27
    ax.bar(x - w3, d_li, w3, label="Li+", color="#2ca02c")
    ax.bar(x, d_pyr, w3, label="Pyr13+", color="#9467bd")
    ax.bar(x + w3, d_fsi, w3, label="FSI-", color="#d62728")
    ax.set_xticks(x, SYSTEMS, fontsize=10)
    ax.set_ylabel(r"D ($10^{-9}\ \mathrm{m^2/s}$)")
    ax.set_title("Self-diffusion (50 ps MSD)")
    ax.legend(frameon=False, fontsize=9); ax.grid(True, axis="y", color="#eeeeee", lw=0.4)

    # CN 분포 히스토그램 (Li-O)
    with CN_DIST_CSV.open() as f:
        reader = csv.reader(f); header = next(reader)
        n_cols = [c for c in header if c.startswith("n=")]
        cn_rows = list(reader)
    o_data = {r[0]: np.array(r[4:], dtype=float) for r in cn_rows if r[1] == "Li-O(FSI)"}
    for sys in SYSTEMS:
        tot = o_data[sys].sum()
        if tot > 0:
            o_data[sys] /= tot

    ax = fig.add_subplot(gs[2, 0])
    xn = np.arange(len(n_cols))
    for k, sys in enumerate(SYSTEMS):
        ax.plot(xn, o_data[sys], "-o", color=COLORS5[sys], lw=1.4, label=sys, markersize=4)
    ax.set_xticks(xn, [c.replace("n=", "") for c in n_cols], fontsize=9)
    ax.set_xlim(-0.5, 10); ax.set_xlabel("Li-O coordination n"); ax.set_ylabel("Probability")
    ax.set_title("Li-O(FSI) coordination distribution")
    ax.grid(True, color="#eeeeee", lw=0.4)
    ax.legend(frameon=False, fontsize=9, ncol=2)

    # 확장 RDF (Li-Li)
    ax = fig.add_subplot(gs[2, 1])
    ymax = 0
    for sys in SYSTEMS:
        rdf = read_xvg(EXT_DIR / f"{sys}_rdf_li_li.xvg")
        ax.plot(rdf[:, 0], rdf[:, 1], color=COLORS5[sys], lw=1.3, label=sys)
        ymax = max(ymax, rdf[rdf[:, 0] > 0.2, 1].max())
    ax.set_xlim(0, 1.2); ax.set_ylim(0, ymax * 1.1)
    ax.set_xlabel("r (nm)"); ax.set_ylabel(r"$g_{\rm Li-Li}(r)$"); ax.set_title("Li-Li RDF")
    ax.grid(True, color="#eeeeee", lw=0.4); ax.legend(frameon=False, fontsize=9, ncol=2)

    # 텍스트 요약
    ax = fig.add_subplot(gs[2, 2])
    ax.axis("off")
    txt = [
        "Key observations:",
        "",
        "• Li-O(FSI) 1st peak ≈ 0.22 nm, CN ≈ 4.1–4.5",
        "  (mild decrease as Li ratio ↑ )",
        "",
        "• Li-N(FSI) 1st peak ≈ 0.37–0.38 nm, CN ≈ 3.2–3.5",
        "  (slightly higher at high Li ratio)",
        "",
        "• Speciation dominated by AGG-II (3+ FSI),",
        "  free Li+ < 2% — typical ionic-liquid regime",
        "",
        "• Self-diffusion: L1P2 fastest, L3P1 slowest",
        "  (concentrated electrolyte → slower transport)",
        "",
        "Trajectory: 50 ps NVT (298 K),",
        "GROMACS 2026.1, OPLS-style FF",
    ]
    for i, line in enumerate(txt):
        ax.text(0.0, 1.0 - i * 0.07, line, transform=ax.transAxes,
                fontsize=11.5, va="top",
                weight="bold" if line.startswith("Key") else "normal",
                color="#1f2c4d" if line.startswith("Key") else "#222222")

    fig.suptitle("LiFSI + Pyr13-FSI ionic-liquid electrolyte — five composition scan",
                 fontsize=15, weight="bold", y=0.98)
    out = OUT / "structure_property_dashboard.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    outs = []
    outs.append(fig_five_systems_grid())
    outs.append(fig_composition_series())
    outs.append(fig_cn_summary_bar())
    outs.append(fig_cn_histograms())
    outs.append(fig_speciation_stacked())
    outs.append(fig_extended_rdf_grid())
    outs.append(fig_dashboard())
    print("saved:")
    for p in outs:
        print(" ", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
