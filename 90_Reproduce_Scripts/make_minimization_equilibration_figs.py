"""
Rigorous MD 4단계(EM → NVT 100 ps → NPT 500 ps → Production 1 ns)의
최소화/평형화 진행을 시각화한다.

대상: L1P1, L1P2 (현재까지 풀 파이프라인 완료된 시스템).
나머지 시스템(L2P1, L3P1, L1P3)은 백그라운드가 끝나면 같은 스크립트로 재생성하면 됨.

생성물:
- em_convergence.png : 5개 시스템 EM potential energy convergence
- nvt_equilibration.png : NVT 100 ps 동안 T, Etot
- npt_equilibration.png : NPT 500 ps 동안 T, P, density
- full_protocol_timeline.png : EM + NVT + NPT + Prod_1ns 풀 타임라인
"""

from __future__ import annotations

from pathlib import Path
import os
import re
import subprocess
import numpy as np
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
PRACTICE = ROOT / "02_Processed_Data" / "MD_Runs" / "50ps_Practice"
RIG = ROOT / "02_Processed_Data" / "MD_Runs" / "Rigorous_1ns"
OUT = ROOT / "04_Figures_For_Report" / "Comprehensive"
ANAL = ROOT / "03_Analysis_Results" / "Equilibration_Stages"
OUT.mkdir(parents=True, exist_ok=True)
ANAL.mkdir(parents=True, exist_ok=True)

SYSTEMS = ["L1P1", "L1P2", "L2P1", "L3P1", "L1P3"]
COLORS5 = {"L1P1": "#000000", "L1P2": "#2ca02c", "L2P1": "#d62728",
           "L3P1": "#9467bd", "L1P3": "#1f77b4"}

# 어떤 시스템이 어떤 단계까지 완료됐는지 자동 감지
def stages_complete(label: str) -> dict[str, bool]:
    d = RIG / label
    return {
        "em": (d / "em.gro").exists(),
        "nvt": (d / "nvt.gro").exists(),
        "npt": (d / "npt.gro").exists(),
        "prod": (d / "prod_1ns.gro").exists(),
    }


def parse_em_log(log: Path) -> tuple[np.ndarray, np.ndarray]:
    """EM 로그에서 (step, Epot) 시퀀스 추출."""
    text = log.read_text(errors="ignore")
    # gmx EM 로그는 "Step X, Dmax= ..., Epot= -...., Fmax= ..." 같은 form
    pattern = re.compile(r"Step\s*=\s*(\d+).*?Epot\s*=\s*([-\d.eE+]+)", re.DOTALL)
    # 또는 simpler: "Step Time Lambda" header 후 그 다음 줄의 첫 컬럼 = step,
    #               "Energies (kJ/mol)" 그 다음다음 줄의 Potential 컬럼
    # 안전하게 표 형식으로 파싱:
    steps: list[int] = []
    epots: list[float] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if "Step           Time" in line and i + 1 < len(lines):
            try:
                parts = lines[i + 1].split()
                step = int(float(parts[0]))
            except (ValueError, IndexError):
                i += 1
                continue
            # 다음 몇 줄 안에서 "Potential" header 찾고 그 다음 줄의 값을 보기
            for j in range(i + 1, min(i + 12, len(lines))):
                if "Potential" in lines[j]:
                    # 그 다음 행에 숫자들
                    if j + 1 < len(lines):
                        nums = lines[j + 1].split()
                        # column 위치 매칭: header에서 'Potential' index 찾기
                        header_cols = lines[j].split()
                        if "Potential" in header_cols:
                            idx = header_cols.index("Potential")
                            if idx < len(nums):
                                try:
                                    e = float(nums[idx])
                                    steps.append(step)
                                    epots.append(e)
                                except ValueError:
                                    pass
                        break
            i = j
        i += 1
    return np.array(steps), np.array(epots)


def gmx_energy_extract(edr: Path, terms: list[str], out_xvg: Path) -> None:
    """gmx energy로 특정 항을 xvg로 추출."""
    if out_xvg.exists():
        return
    env = os.environ.copy()
    env["GMX_MAXBACKUP"] = "-1"
    sel = "\n".join(terms) + "\n0\n"
    subprocess.run(
        ["gmx", "energy", "-f", str(edr), "-o", str(out_xvg)],
        input=sel, text=True, env=env, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )


def read_xvg(p: Path) -> np.ndarray:
    rows = []
    for line in p.read_text(errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith(("#", "@")):
            continue
        rows.append([float(v) for v in s.split()])
    return np.array(rows, dtype=float)


def fig_em_convergence() -> Path:
    """5개 시스템 EM 단계의 potential energy 수렴 곡선. gmx energy로 .edr에서 추출."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), constrained_layout=True)

    for sys in SYSTEMS:
        rig_edr = RIG / sys / "em.edr"
        prac_edr = PRACTICE / sys / "em.edr"
        if rig_edr.exists():
            edr = rig_edr; tag = "rigorous"
        elif prac_edr.exists():
            edr = prac_edr; tag = "practice"
        else:
            continue
        out_xvg = ANAL / f"{sys}_em_pot_{tag}.xvg"
        try:
            gmx_energy_extract(edr, ["Potential"], out_xvg)
            data = read_xvg(out_xvg)
        except Exception as e:
            print(f"  skip {sys}: {e}")
            continue
        if data.size == 0:
            continue
        steps = data[:, 0]; epots = data[:, 1]

        axes[0].plot(steps, epots, color=COLORS5[sys], lw=1.4, label=f"{sys} ({tag})")
        norm = (epots - epots[-1]) / max(abs(epots[-1]), 1.0)
        axes[1].plot(steps, norm, color=COLORS5[sys], lw=1.4, label=f"{sys}")

    axes[0].set_xlabel("EM step (gmx output stride)")
    axes[0].set_ylabel("Potential energy (kJ/mol)")
    axes[0].set_title("EM potential energy convergence")
    axes[0].grid(True, color="#eeeeee", lw=0.4); axes[0].legend(frameon=False, fontsize=10, ncol=2)

    axes[1].set_xlabel("EM step (gmx output stride)")
    axes[1].set_ylabel(r"$(E_{pot}(t) - E_{pot,\rm final}) / |E_{pot,\rm final}|$")
    axes[1].set_title("Relative convergence to final E")
    axes[1].set_yscale("symlog", linthresh=1e-4)
    axes[1].grid(True, color="#eeeeee", lw=0.4); axes[1].legend(frameon=False, fontsize=10, ncol=2)

    fig.suptitle("Energy minimization convergence", fontsize=13)
    out = OUT / "em_convergence.png"
    fig.savefig(out, dpi=220)
    plt.close(fig)
    return out


def fig_nvt_npt_equilibration(label: str) -> Path | None:
    """L1P1/L1P2처럼 풀 파이프라인 완료된 시스템의 NVT/NPT 평형화 곡선."""
    work = RIG / label
    if not (work / "npt.edr").exists():
        return None

    nvt_xvg = ANAL / f"{label}_nvt_TEP.xvg"
    npt_xvg = ANAL / f"{label}_npt_TEPV.xvg"
    gmx_energy_extract(work / "nvt.edr", ["Total-Energy", "Temperature", "Pressure"], nvt_xvg)
    gmx_energy_extract(work / "npt.edr", ["Total-Energy", "Temperature", "Pressure", "Volume", "Density"], npt_xvg)
    nvt = read_xvg(nvt_xvg)
    npt = read_xvg(npt_xvg)

    fig = plt.figure(figsize=(15, 8.5))
    gs = fig.add_gridspec(3, 2, hspace=0.35, wspace=0.25,
                          left=0.07, right=0.97, top=0.92, bottom=0.08)
    # NVT column
    ax_T_nvt = fig.add_subplot(gs[0, 0])
    ax_T_nvt.plot(nvt[:, 0], nvt[:, 2], color="#d62728", lw=0.7)
    ax_T_nvt.axhline(298, color="grey", lw=0.5, ls="--")
    ax_T_nvt.set_ylabel("T (K)"); ax_T_nvt.set_title(f"NVT equilibration (100 ps) — {label}")
    ax_T_nvt.grid(True, color="#eeeeee", lw=0.4)

    ax_E_nvt = fig.add_subplot(gs[1, 0])
    ax_E_nvt.plot(nvt[:, 0], nvt[:, 1], color="#1f77b4", lw=0.7)
    ax_E_nvt.set_ylabel("Total energy (kJ/mol)")
    ax_E_nvt.grid(True, color="#eeeeee", lw=0.4)

    ax_P_nvt = fig.add_subplot(gs[2, 0])
    ax_P_nvt.plot(nvt[:, 0], nvt[:, 3], color="#7f7f7f", lw=0.7)
    ax_P_nvt.set_ylabel("P (bar)"); ax_P_nvt.set_xlabel("t (ps)")
    ax_P_nvt.grid(True, color="#eeeeee", lw=0.4)

    # NPT column
    ax_T_npt = fig.add_subplot(gs[0, 1])
    ax_T_npt.plot(npt[:, 0], npt[:, 2], color="#d62728", lw=0.5)
    ax_T_npt.axhline(298, color="grey", lw=0.5, ls="--")
    ax_T_npt.set_ylabel("T (K)"); ax_T_npt.set_title(f"NPT equilibration (500 ps) — {label}")
    ax_T_npt.grid(True, color="#eeeeee", lw=0.4)

    ax_P_npt = fig.add_subplot(gs[1, 1])
    ax_P_npt.plot(npt[:, 0], npt[:, 3], color="#7f7f7f", lw=0.5)
    ax_P_npt.axhline(1.0, color="grey", lw=0.5, ls="--")
    ax_P_npt.set_ylabel("P (bar)")
    ax_P_npt.grid(True, color="#eeeeee", lw=0.4)

    ax_D_npt = fig.add_subplot(gs[2, 1])
    if npt.shape[1] >= 6:
        ax_D_npt.plot(npt[:, 0], npt[:, 5], color="#2ca02c", lw=0.7)
        ax_D_npt.set_ylabel(r"Density (kg/m$^3$)")
    else:
        ax_D_npt.plot(npt[:, 0], npt[:, 4], color="#2ca02c", lw=0.7)
        ax_D_npt.set_ylabel(r"Volume (nm$^3$)")
    ax_D_npt.set_xlabel("t (ps)")
    ax_D_npt.grid(True, color="#eeeeee", lw=0.4)

    out = OUT / f"equilibration_nvt_npt_{label}.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def fig_full_protocol_timeline(label: str) -> Path | None:
    """EM + NVT + NPT + Prod_1ns 풀 타임라인 (T, Etot 두 변수 위주)."""
    work = RIG / label
    if not (work / "prod_1ns.edr").exists():
        return None

    nvt_xvg = ANAL / f"{label}_nvt_TEP.xvg"
    npt_xvg = ANAL / f"{label}_npt_TEPV.xvg"
    prod_xvg = ANAL / f"{label}_prod_TEPV.xvg"
    gmx_energy_extract(work / "nvt.edr", ["Total-Energy", "Temperature", "Pressure"], nvt_xvg)
    gmx_energy_extract(work / "npt.edr", ["Total-Energy", "Temperature", "Pressure", "Volume", "Density"], npt_xvg)
    gmx_energy_extract(work / "prod_1ns.edr", ["Total-Energy", "Temperature", "Pressure", "Volume", "Density"], prod_xvg)
    nvt = read_xvg(nvt_xvg); npt = read_xvg(npt_xvg); prod = read_xvg(prod_xvg)

    # 시간축 이어붙이기
    nvt_t = nvt[:, 0]
    npt_t = nvt_t.max() + npt[:, 0]
    prod_t = npt_t.max() + prod[:, 0]

    fig, axes = plt.subplots(3, 1, figsize=(13, 8.5), sharex=True, constrained_layout=True)
    # 영역 배경
    boundaries = [(0, nvt_t.max(), "#fef3c7", "NVT 100 ps"),
                  (nvt_t.max(), npt_t.max(), "#dbeafe", "NPT 500 ps"),
                  (npt_t.max(), prod_t.max(), "#dcfce7", "Production 1 ns")]
    for ax in axes:
        for x0, x1, c, _ in boundaries:
            ax.axvspan(x0, x1, color=c, alpha=0.5, zorder=0)

    axes[0].plot(nvt_t, nvt[:, 2], color="#d62728", lw=0.5)
    axes[0].plot(npt_t, npt[:, 2], color="#d62728", lw=0.4)
    axes[0].plot(prod_t, prod[:, 2], color="#d62728", lw=0.3)
    axes[0].axhline(298, color="grey", lw=0.5, ls="--")
    axes[0].set_ylabel("T (K)")
    axes[0].set_title(f"Full MD protocol timeline — {label}")

    axes[1].plot(nvt_t, nvt[:, 1], color="#1f77b4", lw=0.5)
    axes[1].plot(npt_t, npt[:, 1], color="#1f77b4", lw=0.4)
    axes[1].plot(prod_t, prod[:, 1], color="#1f77b4", lw=0.3)
    axes[1].set_ylabel("Total energy (kJ/mol)")

    if npt.shape[1] >= 6 and prod.shape[1] >= 6:
        axes[2].plot(npt_t, npt[:, 5], color="#2ca02c", lw=0.6)
        axes[2].plot(prod_t, prod[:, 5], color="#2ca02c", lw=0.4)
        axes[2].set_ylabel(r"Density (kg/m$^3$)")
    else:
        axes[2].plot(npt_t, npt[:, 4], color="#2ca02c", lw=0.6)
        axes[2].plot(prod_t, prod[:, 4], color="#2ca02c", lw=0.4)
        axes[2].set_ylabel(r"Volume (nm$^3$)")
    axes[2].set_xlabel("t (ps)")

    # 라벨
    for x0, x1, c, lbl in boundaries:
        axes[0].text((x0 + x1) / 2, axes[0].get_ylim()[1] * 0.96, lbl,
                      ha="center", va="top", fontsize=10, weight="bold",
                      bbox=dict(facecolor="white", edgecolor=c, alpha=0.95))

    for ax in axes:
        ax.grid(True, color="#eeeeee", lw=0.4)
        ax.set_xlim(0, prod_t.max())

    out = OUT / f"full_protocol_timeline_{label}.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def main() -> None:
    outs: list[Path] = []
    outs.append(fig_em_convergence())
    for sys in SYSTEMS:
        eq = fig_nvt_npt_equilibration(sys)
        if eq:
            outs.append(eq)
        tl = fig_full_protocol_timeline(sys)
        if tl:
            outs.append(tl)
    print("saved:")
    for p in outs:
        print(" ", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
