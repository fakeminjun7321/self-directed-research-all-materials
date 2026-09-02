"""
Nernst-Einstein 식으로 ionic conductivity (σ_NE) 추정.

σ_NE = (e²/(k_B T V)) Σ_i N_i z_i² D_i

여기서 N_i는 각 이온 종 개수, z_i는 전하, D_i는 자기 확산 계수, V는 박스 부피.

NE 추정은 ion-ion 상관을 무시하므로 실제 측정값보다 항상 크다 (특히 IL은 ~3배 과대).
즉, transport correlation factor f_NE < 1을 곱해야 진짜 측정값 근사. 그래도 조성 간 트렌드 비교는 의미있다.
"""

from __future__ import annotations

from pathlib import Path
import csv
import numpy as np
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "03_Analysis_Results" / "General_Analysis" / "summary.csv"
INIT = ROOT / "01_Raw_Data" / "Initial_Structures_Packmol" / "summary.csv"
OUT_DIR = ROOT / "03_Analysis_Results" / "Conductivity"
FIG_DIR = ROOT / "04_Figures_For_Report" / "Comprehensive"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 물리 상수
E = 1.602176634e-19  # C
K_B = 1.380649e-23   # J/K
T = 298.0            # K
N_A = 6.02214076e23

SYSTEMS = ["L1P1", "L1P2", "L2P1", "L3P1", "L1P3"]
COMPOS = {"L1P1": (25, 25, 50), "L1P2": (25, 50, 75), "L1P3": (25, 75, 100),
          "L2P1": (50, 25, 75), "L3P1": (75, 25, 100)}
BOX = {}


def main() -> None:
    # box 크기 (Å → m)
    for row in csv.DictReader(INIT.open()):
        BOX[row["label"]] = float(row["box_A"]) * 1e-10  # m

    gen_rows = {r["label"]: r for r in csv.DictReader(GEN.open())}

    results = []
    for sys in SYSTEMS:
        n_li, n_pyr, n_fsi = COMPOS[sys]
        box_m = BOX[sys]
        V = box_m ** 3  # m³

        d_li = float(gen_rows[sys]["diffusion_li_m2_s"])
        d_pyr = float(gen_rows[sys]["diffusion_pyr13_m2_s"])
        d_fsi = float(gen_rows[sys]["diffusion_fsi_m2_s"])

        # σ_NE [S/m]
        prefactor = E**2 / (K_B * T * V)
        sigma = prefactor * (n_li * 1**2 * d_li + n_pyr * 1**2 * d_pyr + n_fsi * 1**2 * d_fsi)
        # mS/cm로 환산
        sigma_mS_cm = sigma * 10  # S/m → mS/cm (왜냐: 1 S/m = 10 mS/m = 0.01 S/cm = 10 mS/cm)

        # Li transference number (NE 근사)
        t_li = (n_li * d_li) / (n_li * d_li + n_pyr * d_pyr + n_fsi * d_fsi)

        # mol/L 농도(Li)
        c_li_mol_L = (n_li / N_A) / (V * 1000)  # mol / L

        results.append({
            "system": sys,
            "c_Li_mol_per_L": round(c_li_mol_L, 3),
            "D_Li_e-9_m2_s": round(d_li * 1e9, 3),
            "D_Pyr_e-9_m2_s": round(d_pyr * 1e9, 3),
            "D_FSI_e-9_m2_s": round(d_fsi * 1e9, 3),
            "sigma_NE_S_per_m": round(sigma, 3),
            "sigma_NE_mS_per_cm": round(sigma_mS_cm, 3),
            "t_Li_NE": round(t_li, 3),
        })

    out_csv = OUT_DIR / "nernst_einstein_conductivity.csv"
    with out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        for r in results:
            w.writerow(r)

    # 그림
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), constrained_layout=True)
    x = np.arange(len(SYSTEMS))
    colors_sys = ["#000000", "#2ca02c", "#d62728", "#9467bd", "#1f77b4"]

    # (a) c_Li
    bars = axes[0].bar(x, [r["c_Li_mol_per_L"] for r in results], color=colors_sys)
    for b in bars:
        axes[0].annotate(f"{b.get_height():.2f}", (b.get_x() + b.get_width()/2, b.get_height()),
                          ha="center", va="bottom", fontsize=10)
    axes[0].set_xticks(x, SYSTEMS); axes[0].set_ylabel("Li⁺ concentration (mol/L)")
    axes[0].set_title("Li⁺ salt concentration"); axes[0].grid(True, axis="y", color="#eeeeee", lw=0.4)

    # (b) σ_NE
    bars = axes[1].bar(x, [r["sigma_NE_mS_per_cm"] for r in results], color=colors_sys)
    for b in bars:
        axes[1].annotate(f"{b.get_height():.2f}", (b.get_x() + b.get_width()/2, b.get_height()),
                          ha="center", va="bottom", fontsize=10)
    axes[1].set_xticks(x, SYSTEMS); axes[1].set_ylabel(r"$\sigma_{NE}$ (mS/cm)")
    axes[1].set_title("Nernst-Einstein conductivity"); axes[1].grid(True, axis="y", color="#eeeeee", lw=0.4)

    # (c) t_Li
    bars = axes[2].bar(x, [r["t_Li_NE"] for r in results], color=colors_sys)
    for b in bars:
        axes[2].annotate(f"{b.get_height():.2f}", (b.get_x() + b.get_width()/2, b.get_height()),
                          ha="center", va="bottom", fontsize=10)
    axes[2].set_xticks(x, SYSTEMS); axes[2].set_ylabel(r"$t_{Li}^{NE}$")
    axes[2].set_title("Li⁺ transference number (NE)"); axes[2].grid(True, axis="y", color="#eeeeee", lw=0.4)
    axes[2].set_ylim(0, max(r["t_Li_NE"] for r in results) * 1.2)

    fig.suptitle("Nernst-Einstein conductivity & Li transference number from 50 ps MSD",
                 fontsize=13)
    out_fig = FIG_DIR / "nernst_einstein_conductivity.png"
    fig.savefig(out_fig, dpi=220)
    plt.close(fig)

    print(f"saved: {out_csv.relative_to(ROOT)}")
    print(f"saved: {out_fig.relative_to(ROOT)}")
    for r in results:
        print(f"  {r['system']}: c(Li)={r['c_Li_mol_per_L']:.2f} M, "
              f"σ_NE={r['sigma_NE_mS_per_cm']:.2f} mS/cm, "
              f"t_Li(NE)={r['t_Li_NE']:.2f}")


if __name__ == "__main__":
    main()
