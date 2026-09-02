"""
5개 시스템(L1P1, L1P2, L2P1, L3P1, L1P3) 모든 분석을 묶은 종합 PDF 보고서.

구성:
1. 표지
2. 시스템 개요 + 조성 표
3. 평형(에너지/온도/압력) 점검
4. RDF (Li-O, Li-N) per-system 격자
5. 조성 시리즈 비교 (L=1 / P=1)
6. CN 막대 + CN 분포
7. Speciation
8. 확장 RDF (Li-N4, Li-Li, NBT-NBT, N4-NBT)
9. MSD / Diffusion
10. Dashboard
11. 결론/관찰
"""

from __future__ import annotations

from pathlib import Path
import csv
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import datetime

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "04_Figures_For_Report" / "Comprehensive"
OLD_FIG = ROOT / "04_Figures_For_Report" / "RDF_CN"
GEN = ROOT / "03_Analysis_Results" / "General_Analysis"
OUT = ROOT / "05_Report" / "comprehensive_report_2026-05-27.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)

# 한글 폰트 등록 (macOS 기본 폰트)
KOR_FONT = "/System/Library/Fonts/Supplemental/AppleGothic.ttf"
KOR_FONT_FALLBACK = "/Library/Fonts/AppleSDGothicNeo.ttc"


def register_korean_font() -> str:
    for f in (KOR_FONT, KOR_FONT_FALLBACK):
        try:
            pdfmetrics.registerFont(TTFont("KorFont", f))
            return "KorFont"
        except Exception:
            continue
    return "Helvetica"


KOR = register_korean_font()


def main() -> None:
    doc = SimpleDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
    )
    s = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=s["Title"], fontName=KOR,
                                  fontSize=22, leading=28, alignment=TA_LEFT,
                                  textColor=colors.HexColor("#1f2c4d"))
    h1 = ParagraphStyle("H1", parent=s["Heading1"], fontName=KOR,
                         fontSize=15, leading=18, spaceBefore=10, spaceAfter=8,
                         textColor=colors.HexColor("#1f2c4d"))
    h2 = ParagraphStyle("H2", parent=s["Heading2"], fontName=KOR,
                         fontSize=12, leading=15, spaceBefore=8, spaceAfter=4,
                         textColor=colors.HexColor("#333333"))
    body = ParagraphStyle("Body", parent=s["BodyText"], fontName=KOR,
                           fontSize=10, leading=14, alignment=TA_LEFT)
    small = ParagraphStyle("Small", parent=body, fontSize=9, leading=12,
                           textColor=colors.HexColor("#666666"))

    story: list = []

    # 표지
    story.append(Paragraph("2026 자율연구 — 50 ps MD 종합 분석", title_style))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        "LiFSI + Pyr<sub>13</sub>-FSI 이온성 액체 전해질의 조성별 구조와 동역학 비교",
        h2))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        f"작성일: {datetime.date.today().isoformat()} · "
        f"분석 대상: L1P1, L1P2, L2P1, L3P1, L1P3",
        small))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        "본 보고서는 교수님이 지정하신 다섯 조성에 대해 50 ps NVT MD trajectory(298 K)로 다음을 분석한 결과를 정리한 것이다.",
        body))
    story.append(Spacer(1, 2 * mm))
    summary_points = [
        "• 평형(에너지·온도·압력) 시계열 점검",
        "• Li-O(FSI), Li-N(FSI) RDF와 누적 coordination number",
        "• 조성 시리즈(L=1 고정 vs P=1 고정) 비교",
        "• Li 1차 배위수의 분포(평균뿐 아니라 분산까지)",
        "• Li<sup>+</sup> 음이온 응집(speciation: Free/CIP/AGG-I/AGG-II)",
        "• 확장 RDF: Li-N4(Pyr+), Li-Li, N(FSI)-N(FSI), N4(Pyr+)-N(FSI)",
        "• 자기 확산 계수 (Li, Pyr<sub>13</sub>, FSI)",
    ]
    for p in summary_points:
        story.append(Paragraph(p, body))

    story.append(PageBreak())

    # 2. 시스템 개요
    story.append(Paragraph("1. 시스템 개요", h1))
    story.append(Paragraph(
        "각 시스템은 LiFSI 염을 Pyr<sub>13</sub>-FSI 이온성 액체에 녹인 형태이며, "
        "전기적 중성을 위해 FSI<sup>-</sup> 개수가 Li<sup>+</sup> + Pyr<sub>13</sub><sup>+</sup>의 합과 같다. "
        "다섯 조성은 (a) P=1 고정 후 Li 비율을 1→3까지 늘린 라인과 "
        "(b) L=1 고정 후 Pyr 비율을 1→3까지 늘린 라인으로 십자 모양 스캔을 이룬다.",
        body))
    composition_data = [
        ["조성", "Li⁺", "Pyr₁₃⁺", "FSI⁻", "총 원자 수", "Box (Å)"],
        ["L1P1", "25", "25", "50", "1150", "52.877"],
        ["L1P2", "25", "50", "75", "2050", "64.114"],
        ["L1P3", "25", "75", "100", "2950", "72.384"],
        ["L2P1", "50", "25", "75", "1400", "56.460"],
        ["L3P1", "75", "25", "100", "1650", "59.639"],
    ]
    tbl = Table(composition_data, colWidths=[22 * mm, 22 * mm, 25 * mm, 25 * mm, 30 * mm, 25 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2c4d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), KOR),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f7")]),
    ]))
    story.append(Spacer(1, 4 * mm))
    story.append(tbl)

    # 3. MD 프로토콜과 평형 점검
    story.append(PageBreak())
    story.append(Paragraph("2. MD 프로토콜과 평형화 단계", h1))
    story.append(Paragraph(
        "정식 MD는 ① Energy Minimization(EM) → ② NVT 100 ps (V-rescale, 298 K, gen-vel) "
        "→ ③ NPT 500 ps (Parrinello-Rahman 1 bar) → ④ Production 1 ns 의 4단계로 진행한다. "
        "MDP 파일은 <font face=\"Courier\">02_Processed_Data/MD_Protocols/Rigorous_1ns/mdp/</font> 에 있다.",
        body))

    story.append(Paragraph("2.1 Energy minimization", h2))
    if (FIG / "em_convergence.png").exists():
        story.append(Image(str(FIG / "em_convergence.png"),
                            width=170 * mm, height=58 * mm))
    story.append(Paragraph(
        "모든 시스템에서 steep descent 가 수십~수백 step 안에 매끄럽게 수렴. "
        "큰 시스템(L2P1)일수록 step 수 증가. 우측 패널은 최종값 대비 상대 수렴.",
        small))

    story.append(Paragraph("2.2 NVT 100 ps 와 NPT 500 ps (L1P2)", h2))
    if (FIG / "equilibration_nvt_npt_L1P2.png").exists():
        story.append(Image(str(FIG / "equilibration_nvt_npt_L1P2.png"),
                            width=170 * mm, height=95 * mm))
    story.append(Paragraph(
        "NVT 초기에 Maxwell 분포로 인한 T spike(~400 K) 가 ~20 ps 안에 298 K 부근으로 안정화. "
        "Total energy 도 지수적 감쇠하며 평형값에 도달. "
        "NPT 500 ps 동안 밀도가 127→144 kg/m³로 천천히 증가하지만 "
        "실제 IL 평형 밀도(~1300–1500 kg/m³)에는 한참 못 미친다.",
        small))

    story.append(Paragraph("2.3 풀 4-단계 타임라인 (L1P2 성공 사례)", h2))
    if (FIG / "full_protocol_timeline_L1P2.png").exists():
        story.append(Image(str(FIG / "full_protocol_timeline_L1P2.png"),
                            width=170 * mm, height=85 * mm))
    story.append(Paragraph(
        "Production 약 620 ps 부근에서 박스가 폭압축되며 밀도가 ~1500 kg/m³ (정상)으로 도약, "
        "이후 안정적으로 유지. 즉 production NPT 가 NPT 500 ps 가 못 끝낸 압축을 대신 수행한 셈.",
        small))

    story.append(PageBreak())
    story.append(Paragraph("2.4 Protocol 한계 — L1P1 production 불안정", h2))
    if (FIG / "full_protocol_timeline_L1P1.png").exists():
        story.append(Image(str(FIG / "full_protocol_timeline_L1P1.png"),
                            width=170 * mm, height=85 * mm))
    story.append(Paragraph(
        "<b>중요 관찰</b>: L1P1(가장 작은 시스템, 1150 atoms) production 에서 박스가 "
        "주기적으로 폭축/팽창을 반복하다 결국 발산(box 299 nm, 평균 ρ ≈ 24 kg/m³). "
        "Parrinello-Rahman barostat 이 sparse한 시스템에서 통계 떨림에 의해 불안정해진 결과. "
        "권장 수정: ① Packmol 패킹을 10배 더 빽빽이 (target ρ ≈ physical), "
        "② Berendsen barostat 200–500 ps로 부드럽게 압축 후 PR 전환, "
        "③ NPT 단계를 500 ps → 2–5 ns 로 연장, ④ tau-p 5 → 10.",
        small))

    story.append(PageBreak())
    story.append(Paragraph("2.5 50 ps Practice trajectory의 에너지/온도/압력 점검", h2))
    story.append(Paragraph(
        "이 보고서의 나머지 RDF/CN/MSD 분석은 50 ps Practice trajectory에 기반한 것이다. "
        "이 단계는 NPT 평형화가 빠져 packmol 초기 박스에 갇혀 있다(헐거운 밀도). "
        "그래도 NVT 자체의 T/P 안정성은 정상이며 트렌드 비교는 의미있다.",
        body))
    story.append(Spacer(1, 2 * mm))
    if (FIG / "equilibration_check.png").exists():
        story.append(Image(str(FIG / "equilibration_check.png"),
                            width=170 * mm, height=78 * mm))

    # 4. RDF per system
    story.append(PageBreak())
    story.append(Paragraph("3. Li-O(FSI), Li-N(FSI) RDF와 누적 coordination number", h1))
    story.append(Paragraph(
        "각 시스템에서 reference로 Li 원자, selection으로 OBT(FSI 산소) 또는 NBT(FSI 질소)를 두고 "
        "RDF를 계산하고 누적 coordination number를 동시에 그렸다.",
        body))
    story.append(Spacer(1, 2 * mm))
    if (FIG / "five_systems_rdf_grid.png").exists():
        story.append(Image(str(FIG / "five_systems_rdf_grid.png"),
                            width=170 * mm, height=190 * mm))

    # 5. 조성 시리즈 비교
    story.append(PageBreak())
    story.append(Paragraph("4. 조성 시리즈 비교", h1))
    story.append(Paragraph(
        "(a) L=1 고정·Pyr 증가 (L1P1→L1P2→L1P3)와 "
        "(b) P=1 고정·Li 증가 (L1P1→L2P1→L3P1) 두 라인으로 RDF가 어떻게 변하는지 비교했다.",
        body))
    if (FIG / "composition_series_overlay.png").exists():
        story.append(Image(str(FIG / "composition_series_overlay.png"),
                            width=170 * mm, height=110 * mm))
    story.append(Paragraph(
        "L=1 라인은 Pyr 비율이 늘어나면서 Li-N(FSI) 첫 peak가 더 뾰족해지는 경향, "
        "P=1 라인은 Li 비율이 늘어나면서 Li-O 첫 peak 높이가 다소 낮아지고 1차 배위수도 줄어드는 경향이 보인다.",
        small))

    # 6. CN 막대 + 분포
    story.append(PageBreak())
    story.append(Paragraph("5. 1차 배위수 (Coordination Number)", h1))
    if (FIG / "coordination_number_summary_bar.png").exists():
        story.append(Image(str(FIG / "coordination_number_summary_bar.png"),
                            width=170 * mm, height=82 * mm))
    story.append(Spacer(1, 2 * mm))
    cn_summary_csv = ROOT / "03_Analysis_Results" / "RDF_CN" / "coordination_number_li_o_n_summary.csv"
    rows = list(csv.DictReader(cn_summary_csv.open()))
    cn_data = [["조성", "Li-O peak r (nm)", "Li-O CN", "Li-N peak r (nm)", "Li-N CN"]]
    for sys in ["L1P1", "L1P2", "L2P1", "L3P1", "L1P3"]:
        o = next(r for r in rows if r["system"] == sys and r["pair"] == "Li-O(FSI)")
        n = next(r for r in rows if r["system"] == sys and r["pair"] == "Li-N(FSI)")
        cn_data.append([sys, o["rdf_peak_r_nm"], o["coordination_number"],
                         n["rdf_peak_r_nm"], n["coordination_number"]])
    tbl = Table(cn_data, colWidths=[25 * mm, 35 * mm, 25 * mm, 35 * mm, 25 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2c4d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), KOR),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f7")]),
    ]))
    story.append(tbl)

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("CN 분포 (Li 한 개당 1차 shell 내 O/N 개수의 분포):", h2))
    if (FIG / "cn_distribution_histograms.png").exists():
        story.append(Image(str(FIG / "cn_distribution_histograms.png"),
                            width=170 * mm, height=65 * mm))
    story.append(Paragraph(
        "평균은 비슷하지만 분포 모양은 시스템마다 미세하게 다르다. "
        "특히 L3P1처럼 Li이 많은 시스템에서 n=3 이하의 비율이 약간 높아지고, "
        "Pyr 비율이 큰 L1P3에서는 n=5–6 꼬리가 더 길다.",
        small))

    # 7. Speciation
    story.append(PageBreak())
    story.append(Paragraph("6. Li⁺ 음이온 응집 (Speciation)", h1))
    story.append(Paragraph(
        "각 Li 주변 첫 shell(0.33 nm 이내) FSI 음이온의 개수로 분류했다. "
        "0개 = Free Li, 1개 = CIP, 2개 = AGG-I, 3개 이상 = AGG-II. "
        "Pyr 비율이 늘수록 응집이 약해지고(L1P3가 AGG-II 비율 가장 낮음), "
        "Li 비율이 늘수록 응집이 더 강해진다(L2P1, L3P1에서 AGG-II 80% 안팎).",
        body))
    if (FIG / "speciation_stacked_bar.png").exists():
        story.append(Image(str(FIG / "speciation_stacked_bar.png"),
                            width=170 * mm, height=98 * mm))

    # 8. Extended RDF
    story.append(PageBreak())
    story.append(Paragraph("7. 확장 RDF (양/음이온 간 상관)", h1))
    story.append(Paragraph(
        "Li-O, Li-N 외에 시스템의 다른 양·음이온 상관도 보자.",
        body))
    if (FIG / "extended_rdf_overview.png").exists():
        story.append(Image(str(FIG / "extended_rdf_overview.png"),
                            width=170 * mm, height=115 * mm))
    story.append(Paragraph(
        "Li-N4(Pyr<sup>+</sup>) RDF는 0.55–0.65 nm 부근에 약한 peak — "
        "Pyr<sup>+</sup>와 Li<sup>+</sup>는 양전하끼리 멀어지는 반발이 보이지만 "
        "이온성 액체 구조 안에서 일정한 거리 상관은 남아있다. "
        "Li-Li peak가 0.5–0.55 nm 부근에 나타나는 것은 FSI<sup>-</sup>를 매개로 한 "
        "Li-FSI-Li 다리 구조(AGG-II와 일관) 때문이다.",
        small))

    # 9. MSD / Diffusion
    story.append(PageBreak())
    story.append(Paragraph("8. MSD와 자기 확산 계수", h1))
    story.append(Paragraph(
        "이미 General_Analysis 폴더에 계산해 둔 Li, Pyr13, FSI 자기 확산 계수를 정리한다. "
        "50 ps는 짧아 절대값은 참고 수준이지만, 조성 간 상대 비교는 의미있다.",
        body))
    gen_csv = GEN / "summary.csv"
    gen_rows = {r["label"]: r for r in csv.DictReader(gen_csv.open())}
    d_data = [["조성", "D(Li⁺)", "D(Pyr₁₃⁺)", "D(FSI⁻)"]]
    for sys in ["L1P1", "L1P2", "L2P1", "L3P1", "L1P3"]:
        r = gen_rows[sys]
        d_data.append([sys,
                       f"{float(r['diffusion_li_m2_s']) * 1e9:.2f}",
                       f"{float(r['diffusion_pyr13_m2_s']) * 1e9:.2f}",
                       f"{float(r['diffusion_fsi_m2_s']) * 1e9:.2f}"])
    d_data[0] = ["조성", "D(Li⁺) (10⁻⁹ m²/s)", "D(Pyr₁₃⁺) (10⁻⁹ m²/s)", "D(FSI⁻) (10⁻⁹ m²/s)"]
    tbl = Table(d_data, colWidths=[25 * mm, 45 * mm, 50 * mm, 45 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2c4d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), KOR),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f7")]),
    ]))
    story.append(Spacer(1, 3 * mm))
    story.append(tbl)

    # 기존 overall diffusion 그림 활용
    diff_png = ROOT / "03_Analysis_Results" / "General_Analysis" / "overall_diffusion_coefficients.png"
    if diff_png.exists():
        story.append(Spacer(1, 4 * mm))
        story.append(Image(str(diff_png), width=160 * mm, height=85 * mm))
    story.append(Paragraph(
        "Li 비율이 클수록(L2P1→L3P1) 전반적으로 자기 확산이 느려진다. "
        "Pyr 비율이 큰 L1P3는 Pyr<sub>13</sub>과 FSI 모두의 확산이 다른 조성보다 빠른데, "
        "이는 양이온성 액체 매트릭스가 늘어나면서 Li 응집이 약해지고 점도가 낮아지는 경향과 일관된다.",
        small))

    # 9.5 Nernst-Einstein conductivity
    story.append(PageBreak())
    story.append(Paragraph("9. Nernst-Einstein 이온 전도도 추정", h1))
    story.append(Paragraph(
        "확산 계수로부터 Nernst-Einstein 식 σ<sub>NE</sub> = (e²/k<sub>B</sub>TV) Σ N<sub>i</sub>z<sub>i</sub>²D<sub>i</sub> 를 "
        "이용해 전도도를 추정한다. 이 식은 이온-이온 상관(correlation)을 무시하므로 실제 측정값보다 크게 나오며, "
        "특히 응집이 강한 이온성 액체에서는 ~2–3배 과대 평가된다. 또한 50 ps의 짧은 trajectory에서 추출한 D는 "
        "ballistic 영역이 섞여 있어 진정한 long-time diffusion보다 크다(절대값은 1–2 자리 이상 과대). "
        "그래도 조성 간 상대 비교는 의미있다.",
        body))
    story.append(Spacer(1, 2 * mm))
    cond_csv = ROOT / "03_Analysis_Results" / "Conductivity" / "nernst_einstein_conductivity.csv"
    cond_rows = list(csv.DictReader(cond_csv.open()))
    cond_data = [["조성", "c(Li⁺) (M)", "σ_NE (mS/cm)", "t_Li (NE)"]]
    for r in cond_rows:
        cond_data.append([r["system"], r["c_Li_mol_per_L"], r["sigma_NE_mS_per_cm"], r["t_Li_NE"]])
    tbl = Table(cond_data, colWidths=[25 * mm, 35 * mm, 40 * mm, 35 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2c4d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), KOR),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f7")]),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 4 * mm))
    if (FIG / "nernst_einstein_conductivity.png").exists():
        story.append(Image(str(FIG / "nernst_einstein_conductivity.png"),
                            width=170 * mm, height=58 * mm))
    story.append(Paragraph(
        "트렌드: Pyr 비율 증가(L1P1→L1P2→L1P3)는 σ를 약간 키우지만 Li 농도와 t<sub>Li</sub>는 떨어뜨림. "
        "Li 비율 증가(L1P1→L2P1→L3P1)는 c(Li)와 t<sub>Li</sub>를 모두 끌어올리지만 σ는 살짝 감소. "
        "전기차 전해질 관점에서 L2P1·L3P1처럼 Li 비율이 높은 농축 영역이 t<sub>Li</sub> ≈ 0.45로 더 유리해 보인다.",
        small))

    # 10. Dashboard
    story.append(PageBreak())
    story.append(Paragraph("10. 한 장 요약 dashboard", h1))
    if (FIG / "structure_property_dashboard.png").exists():
        story.append(Image(str(FIG / "structure_property_dashboard.png"),
                            width=170 * mm, height=120 * mm))

    # 11. 결론
    story.append(PageBreak())
    story.append(Paragraph("11. 결론 및 다음 단계", h1))
    bullets = [
        "Li-O(FSI) 첫 peak는 0.22 nm 부근에서 모든 조성 공통, 1차 CN ≈ 4.1–4.5.",
        "Li-N(FSI) 첫 peak는 0.37–0.38 nm, 1차 CN ≈ 3.2–3.5.",
        "Pyr 비율(P)이 클수록 Li-O CN은 다소 증가, Li-N CN은 감소 — 양이온 매트릭스가 음이온 환경을 약간 분산시킴.",
        "Li 비율(L)이 클수록 Li-O CN은 감소, 응집 비율(AGG-II) 증가 — Li-FSI-Li 다리 구조 강화.",
        "speciation은 모든 조성에서 AGG-II가 70% 이상으로 지배적, free Li<sup>+</sup>는 2% 미만.",
        "자기 확산 계수는 L2P1, L3P1에서 가장 느림(농축 영역), L1P3에서 빠름(희석/Pyr 증가).",
    ]
    for b in bullets:
        story.append(Paragraph("• " + b, body))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("다음 단계 권장:", h2))
    nxt = [
        "정량 수치(특히 D)는 1 ns 이상 production MD로 다시 계산 — 현재 1 ns Rigorous MD 5개 시스템 일괄 실행 중.",
        "이온 전도도는 Nernst-Einstein 또는 Onsager 관계로 추정 가능. 단순 추정용 코드 추가 가능.",
        "온도/조성 의존성 추가 분석을 위해 일부 조성에서 다른 온도 (예: 333 K)도 돌려보는 것을 권장.",
    ]
    for n in nxt:
        story.append(Paragraph("• " + n, body))

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        f"분석/그림 생성 스크립트는 모두 <font face=\"Courier\">90_Reproduce_Scripts/</font> 안에 있으며 "
        f"`build_L2P2_L3P2.py` (참고용), `extended_rdf_analysis.py`, `speciation_analysis.py`, "
        f"`cn_distribution_analysis.py`, `check_equilibration.py`, "
        f"`make_comprehensive_figures.py`, `make_comprehensive_report_pdf.py` 순으로 실행하면 같은 결과를 재생산한다.",
        small))

    doc.build(story)
    print(f"saved: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
