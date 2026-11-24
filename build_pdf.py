#!/usr/bin/env python3
"""
build_pdf.py - builds the application PDF for the Terminus Circuits AMS internship.

1. Edit the APPLICANT block below (anything still in [square brackets] is highlighted
   yellow in the PDF so you can see what is left to fill in).
2. Run  python3 pll_model.py   (refreshes results.json and figures)
3. Run  python3 build_pdf.py   -> Terminus_AMS_Intern_Application.pdf
Every number in the PDF is read from results.json, so text and results cannot drift apart.
"""
import json
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)

# ----------------------------------------------------------------------------
APPLICANT = dict(
    name="[Your Full Name]",
    degree="[M.Tech VLSI / B.E. ECE]",
    college="[College / University]",
    grad="[graduation month, year]",
    email="[your.email@example.com]",
    phone="[+91 XXXXX XXXXX]",
    links="[GitHub / LinkedIn link]",
    courses="[e.g. Analog CMOS design, Control systems, VLSI design]",
    tools="[e.g. Cadence Virtuoso, ngspice, LTspice, MATLAB]",
)
OUTFILE = "Terminus_AMS_Intern_Application.pdf"
# ----------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures")
R = json.load(open(os.path.join(HERE, "results.json")))
D, M, CL, J = R["design"], R["margins"], R["closed_loop"], R["jitter_fs"]
LK, ST, SW, SP = R["lock"], R["step"], R["sweep"], R["spec"]
NZ = R["noise_assumptions"]

NAVY, BLUE, INK, GREY = colors.HexColor("#0B2545"), colors.HexColor("#0072B2"), colors.HexColor("#111827"), colors.HexColor("#6b7280")
LIGHT, LINE = colors.HexColor("#F3F6FA"), colors.HexColor("#D5DCE6")


def ph(key):
    v = APPLICANT[key]
    return f'<font backColor="#FFF1A8">{v}</font>' if v.startswith("[") else v


S = dict(
    body=ParagraphStyle("body", fontName="Helvetica", fontSize=9.2, leading=13, textColor=INK, spaceAfter=5),
    small=ParagraphStyle("small", fontName="Helvetica", fontSize=8, leading=10.5, textColor=GREY),
    cap=ParagraphStyle("cap", fontName="Helvetica-Oblique", fontSize=8, leading=10.5, textColor=GREY, spaceAfter=8, alignment=1),
    h1=ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=NAVY, spaceBefore=2, spaceAfter=6),
    h2=ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=BLUE, spaceBefore=7, spaceAfter=3),
    bullet=ParagraphStyle("bullet", fontName="Helvetica", fontSize=9.2, leading=13, textColor=INK, leftIndent=11, bulletIndent=1, spaceAfter=2.5),
    cell=ParagraphStyle("cell", fontName="Helvetica", fontSize=8.6, leading=11.5, textColor=INK),
    cellb=ParagraphStyle("cellb", fontName="Helvetica-Bold", fontSize=8.6, leading=11.5, textColor=NAVY),
    mono=ParagraphStyle("mono", fontName="Courier", fontSize=8.4, leading=11.5, textColor=INK),
    big=ParagraphStyle("big", fontName="Helvetica-Bold", fontSize=17, leading=20, textColor=NAVY, alignment=1),
    tile=ParagraphStyle("tile", fontName="Helvetica", fontSize=7.4, leading=9.4, textColor=GREY, alignment=1),
    white=ParagraphStyle("white", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.white),
    whiteb=ParagraphStyle("whiteb", fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=colors.white),
)


def P(t, s="body"):
    return Paragraph(t, S[s])


def bullets(items):
    return [Paragraph(t, S["bullet"], bulletText="•") for t in items]


def fig(name, width_mm):
    path = os.path.join(FIG, name)
    iw, ih = ImageReader(path).getSize()
    w = width_mm * mm
    im = Image(path, width=w, height=w * ih / iw)
    im.hAlign = "CENTER"
    return im


def tbl(rows, widths, header=True, zebra=True, valign="TOP"):
    t = Table(rows, colWidths=[w * mm for w in widths])
    st = [("VALIGN", (0, 0), (-1, -1), valign),
          ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
          ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
          ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE)]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
    if zebra:
        for i in range(1 if header else 0, len(rows)):
            if (i % 2) == 0:
                st.append(("BACKGROUND", (0, i), (-1, i), LIGHT))
    t.setStyle(TableStyle(st))
    return t


def hdr(*cells):
    return [Paragraph(f'<font color="white"><b>{c}</b></font>', S["cell"]) for c in cells]


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 13 * mm, 192 * mm, 13 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(GREY)
    canvas.drawString(18 * mm, 8.5 * mm, "Application: AMS Circuit/Layout Design Intern (high-speed circuits)  |  Terminus Circuits Pvt Ltd, Bangalore")
    canvas.drawRightString(192 * mm, 8.5 * mm, f"Page {doc.page}")
    canvas.restoreState()


story = []

# ============================== PAGE 1: APPLICATION SUMMARY ==============================
banner = Table([[P("APPLICATION FOR", "white")],
                [P("AMS Circuit/Layout Design Intern (High-Speed Circuits)", "whiteb")],
                [P("Terminus Circuits Pvt Ltd, Bangalore  |  On-site, 6 to 12 months, starting Dec 2026 / Jan 2027", "white")]],
               colWidths=[174 * mm])
banner.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY),
                            ("LEFTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, -1), 3),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("TOPPADDING", (0, 0), (-1, 0), 10),
                            ("BOTTOMPADDING", (0, -1), (-1, -1), 10)]))
story += [banner, Spacer(1, 8)]

card = Table([[[P(f'<font size="15"><b>{ph("name")}</b></font>', "body"),
                P(f'{ph("degree")}, {ph("college")}<br/>Graduating: {ph("grad")}', "body")],
               [P(f'<b>Email</b>  {ph("email")}<br/><b>Phone</b>  {ph("phone")}<br/><b>Code</b>  {ph("links")}', "body")]]],
             colWidths=[92 * mm, 82 * mm])
card.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                          ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 10),
                          ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
story += [card, Spacer(1, 6)]

story += [P("Profile", "h2"),
          P(f"I am a {ph('degree')} student at {ph('college')}, applying for the AMS Circuit/Layout Design internship. "
            "To show I can work on high-speed clocking, I designed and verified a <b>2.5 GHz charge-pump PLL</b> end to end: "
            "loop-filter synthesis, a per-source phase-noise budget, and an event-driven simulator that I checked against "
            "linear theory. A PLL is the clock-multiplier block inside serial-link PHYs such as PCIe, USB, MIPI M-PHY and "
            "Ethernet, so this project is a small-scale version of the problems the AMS team works on. "
            "It is a behavioural model with stated assumptions, and the next step I plan is a transistor-level "
            "charge pump and VCO.")]

tiles = [[[P(f"{SP['fc']/1e6:.0f} MHz, {SP['PM_deg']:.0f}\u00b0", "big"), P("loop crossover / phase margin", "tile")],
          [P(f"{J['total']:.0f} fs", "big"), P("RMS jitter, 10 kHz to 20 MHz (assumed noise inputs)", "tile")],
          [P(f"{LK['t_lock_us']:.2f} us", "big"), P("lock time from a 2 % frequency error", "tile")],
          [P(f"{ST['rms_dev_ct']*100:.1f} %", "big"), P("RMS gap, event-driven simulator vs linear theory", "tile")]]]
tt = Table(tiles, colWidths=[43.5 * mm] * 4)
tt.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, LINE), ("LINEAFTER", (0, 0), (-2, -1), 0.5, LINE),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
story += [P("Featured project: 2.5 GHz charge-pump PLL (100 MHz reference, x25)", "h2"), tt, Spacer(1, 6)]

rows = [hdr("Your requirement", "What the project shows"),
        [P("Analog and CMOS fundamentals", "cellb"),
         P(f"Derived R, C1 and C2 from crossover and phase margin; analysed how charge-pump current, Kvco and "
           f"capacitor area trade against bandwidth and noise. Relevant coursework: {ph('courses')}.", "cell")],
        [P("Python and coding skill", "cellb"),
         P("Single-file, self-checking model (NumPy, SciPy, Matplotlib): analytic design with assertions, noise "
           "integration, and an event-driven simulator using exact matrix-exponential integration and root finding. "
           "One command regenerates every figure and number in about 2 seconds.", "cell")],
        [P("SPICE / Cadence Virtuoso", "cellb"),
         P(f"The behavioural model is the reference for a transistor-level phase 2 (charge pump, VCO). "
           f"Tools I have used: {ph('tools')}.", "cell")],
        [P("SerDes, PLL/DLL, clocking", "cellb"),
         P(f"Complete PLL study: Bode and closed-loop response, per-source noise shaping, jitter-optimal bandwidth "
           f"(about {SW['opt_fc_MHz']:.1f} MHz for these inputs), lock acquisition and phase-step response.", "cell")],
        [P("Layout awareness", "cellb"),
         P("Phase 2 plan lists the layout items that affect loop performance: charge-pump mirror matching, symmetric "
           "UP/DN routing, MOM capacitors, shielded control line, guard rings.", "cell")]]
story += [P("How this maps to the requirements in your posting", "h2"), tbl(rows, [42, 132])]
story += [Spacer(1, 5), P("Pages 2 to 5 give the project report. All results come from the attached code "
                          "(pll_model.py) and can be reproduced with one command.", "small")]
story.append(PageBreak())

# ============================== PAGE 2: PROJECT OVERVIEW ==============================
story += [P("Project report: design and behavioural verification of a 2.5 GHz charge-pump PLL", "h1"),
          P("1. Objective", "h2"),
          P("Generate a 2.5 GHz clock (the PCIe Gen1 data rate of 2.5 GT/s) from a 100 MHz reference with a type-II "
            "charge-pump PLL. Choose loop bandwidth and phase margin, budget the output jitter by noise source, and verify "
            "the design with a simulator that models the actual PFD and charge-pump behaviour, not only the linear equations."),
          P("2. Architecture and synthesised values", "h2"),
          KeepTogether([fig("fig0_block.png", 165), P("Fig. 1. PLL architecture with the synthesised loop-filter values.", "cap")])]

spec_rows = [hdr("Input", "Value"),
             [P("Reference / output", "cell"), P(f"{SP['fref']/1e6:.0f} MHz / {D['fout_GHz']:.1f} GHz (N = {SP['N']})", "cell")],
             [P("Charge-pump current", "cell"), P(f"{SP['Icp']*1e6:.0f} uA", "cell")],
             [P("VCO gain Kvco", "cell"), P(f"{SP['Kvco_Hz']/1e6:.0f} MHz/V", "cell")],
             [P("Target crossover fc", "cell"), P(f"{SP['fc']/1e6:.0f} MHz (fref/fc = {D['fref_over_fc']:.0f})", "cell")],
             [P("Target phase margin", "cell"), P(f"{SP['PM_deg']:.0f} deg", "cell")]]
der_rows = [hdr("Derived", "Value"),
            [P("Resistor R", "cell"), P(f"{D['R_kohm']:.2f} kohm", "cell")],
            [P("Capacitor C1", "cell"), P(f"{D['C1_pF']:.2f} pF", "cell")],
            [P("Capacitor C2", "cell"), P(f"{D['C2_pF']:.3f} pF", "cell")],
            [P("Zero fz / pole fp", "cell"), P(f"{D['fz_MHz']:.2f} MHz / {D['fp_MHz']:.1f} MHz", "cell")],
            [P("Total capacitance", "cell"), P(f"{D['Ctotal_pF']:.1f} pF", "cell")]]
two = Table([[tbl(spec_rows, [36, 48]), tbl(der_rows, [36, 48])]], colWidths=[87 * mm, 87 * mm])
two.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
story += [two, P("3. Method", "h2")]
story += bullets([
    "<b>Design.</b> Open-loop gain of the type-II, third-order loop, with the closed-form synthesis used in the code:"])
story += [Table([[P("L(s) = K (1 + s/wz) / [ s^2 (1 + s/wp) ],    K = Icp*Kvco / (2*pi*N*(C1+C2))<br/>"
                    "sqrt(wp/wz) = tan(PM) + sqrt(1 + tan^2(PM)),   wc = sqrt(wz*wp),   K = wc^2 / sqrt(wp/wz)<br/>"
                    "C1/C2 = wp/wz - 1,   R = 1 / (wz*C1)", "mono")]], colWidths=[170 * mm],
                style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                                  ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 5),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 5)])), Spacer(1, 4)]
story += bullets([
    "<b>Noise.</b> Reference, charge-pump, filter-resistor and VCO noise are each shaped by their own transfer function "
    "(low-pass for the reference path, high-pass for the VCO) and integrated to RMS jitter.",
    "<b>Event-driven simulation.</b> A tri-state PFD, charge pump, R-C1-C2 filter, VCO and divider are simulated edge by edge. "
    "Between edges the filter voltages and VCO phase are integrated exactly with a matrix exponential, and each divider "
    "edge is located by root finding, so there is no time-step error.",
    "<b>Checks built into the code.</b> Assertions confirm crossover and phase margin match the targets; the simulator is "
    "compared with the linear model (page 5)."])
story.append(PageBreak())

# ============================== PAGE 3: LOOP DYNAMICS ==============================
story += [P("4. Results: loop dynamics", "h1"),
          KeepTogether([fig("fig1_bode.png", 140), P("Fig. 2. Open-loop gain and phase. The dashed curve adds a full Tref/2 sampling delay as a conservative check.", "cap")]),
          KeepTogether([fig("fig2_closedloop.png", 140), P("Fig. 3. Closed-loop responses. The reference path is low-pass, the VCO path is high-pass, and they cross near the loop bandwidth.", "cap")])]
story += bullets([
    f"Crossover is {M['fc_MHz']:.2f} MHz with {M['PM_deg']:.1f} deg phase margin, matching the targets (asserted in the code).",
    f"Closed-loop -3 dB bandwidth is {CL['bw_3db']/1e6:.2f} MHz with {CL['peaking_db']:.2f} dB of peaking at {CL['f_peak']/1e6:.1f} MHz.",
    f"With fref/fc = {D['fref_over_fc']:.0f}, the PFD sampling delay is a second-order effect: a full Tref/2 delay would lower "
    f"the margin to {M['PM_with_sampling_delay_deg']:.1f} deg, and the simulator (page 5) lands much closer to the "
    "continuous-time prediction."])
story.append(PageBreak())

# ============================== PAGE 4: NOISE ==============================
story += [P("5. Results: phase noise and jitter", "h1"),
          KeepTogether([fig("fig3_phasenoise.png", 140), P("Fig. 4. Output phase noise by source. Inside the loop bandwidth the input path dominates; outside it the VCO takes over.", "cap")]),
          KeepTogether([fig("fig4_jitter_vs_bw.png", 140), P("Fig. 5. Jitter versus loop bandwidth. Too narrow lets VCO noise through; too wide passes more reference and charge-pump noise.", "cap")])]
story += bullets([
    f"Total RMS jitter is <b>{J['total']:.0f} fs</b> (10 kHz to 20 MHz): charge pump {J['cp']:.0f}, reference {J['ref']:.0f}, "
    f"VCO {J['vco']:.0f}, filter resistor {J['r']:.0f} fs, combined as root-sum-square.",
    f"The jitter-optimal bandwidth for these inputs is about {SW['opt_fc_MHz']:.1f} MHz ({SW['opt_jitter_fs']:.0f} fs). "
    f"I chose {SP['fc']/1e6:.0f} MHz: about {(J['total']/SW['opt_jitter_fs']-1)*100:.0f} % more jitter, but roughly "
    f"{(SP['fc']/1e6/SW['opt_fc_MHz'])**2:.1f}x smaller capacitors (C scales as 1/fc^2) and faster lock.",
    "Under these assumptions the charge pump is the largest in-band contributor, so charge-pump current and noise is the first "
    "knob to explore at transistor level."])
nrows = [hdr("Assumed noise input (editable in pll_model.py)", "Value"),
         [P("Reference phase-noise floor (100 MHz carrier)", "cell"), P(f"{NZ['ref_floor_dbc']:.0f} dBc/Hz", "cell")],
         [P("Charge-pump output noise, duty-cycle averaged", "cell"), P(f"{NZ['icp_noise']*1e12:.0f} pA/rtHz", "cell")],
         [P("Free-running VCO at 1 MHz offset (2.5 GHz carrier)", "cell"), P(f"{NZ['vco_dbc_1M']:.0f} dBc/Hz, 1/f^2 with {NZ['vco_flicker_corner']/1e3:.0f} kHz flicker corner", "cell")],
         [P("Loop-filter resistor", "cell"), P("thermal noise at 300 K (computed)", "cell")]]
story += [Spacer(1, 3), tbl(nrows, [92, 82]),
          P("These are typical-order assumptions, not measurements. The value of the model is the trade-offs it shows, "
            "not the absolute femtoseconds.", "small")]
story.append(PageBreak())

# ============================== PAGE 5: VERIFICATION, LIMITS, PHASE 2 ==============================
story += [P("6. Verification against linear theory", "h1"),
          KeepTogether([fig("fig5_lock.png", 118), P("Fig. 6. Lock acquisition from a 50 MHz (2 %) frequency error in the event-driven simulator.", "cap")]),
          KeepTogether([fig("fig6_phase_step.png", 118), P("Fig. 7. Response to a 100 ps reference phase step: simulator against linear theory.", "cap")])]
vrows = [hdr("Metric", "Event-driven simulation", "Linear theory"),
         [P("Overshoot of the phase-error step response", "cell"), P(f"{ST['overshoot_sim_pct']:.1f} %", "cell"), P(f"{ST['overshoot_ct_pct']:.1f} %", "cell")],
         [P("2 % settling time", "cell"), P(f"{ST['settle2pct_sim_ns']:.0f} ns", "cell"), P(f"{ST['settle2pct_ct_ns']:.0f} ns", "cell")],
         [P("RMS deviation over 160 reference cycles", "cell"), P(f"{ST['rms_dev_ct']*100:.1f} % of step size", "cell"), P("reference", "cell")],
         [P("Lock time from 2 % frequency error", "cell"), P(f"{LK['t_lock_us']:.2f} us", "cell"), P("n/a", "cell")],
         [P("Final control-voltage error after lock", "cell"), P("below 1 nV", "cell"), P("0", "cell")]]
story += [tbl(vrows, [78, 54, 42])]

story += [P("7. Limitations", "h2")]
story += bullets([
    "Behavioural model only: ideal PFD (no reset delay or dead zone), no charge-pump mismatch or leakage (so no reference spurs), "
    "ideal divider, no supply or substrate noise.",
    "Noise inputs are assumptions, so absolute jitter values are indicative."])
story += [P("8. Phase 2 plan: transistor level and layout", "h2")]
story += bullets([
    "<b>Charge pump:</b> UP/DN current mirrors in ngspice or Virtuoso; measure current mismatch and estimate reference spur level.",
    "<b>VCO:</b> size for Kvco near 200 MHz/V and compare simulated phase noise with the -112 dBc/Hz assumption.",
    "<b>Layout:</b> common-centroid mirror devices with dummies, symmetric UP/DN routing, MOM capacitors for C1 and C2, "
    "shielded and short control line, guard rings, supply isolation."])

doc = BaseDocTemplate(os.path.join(HERE, OUTFILE), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                      topMargin=15 * mm, bottomMargin=18 * mm,
                      title="AMS Circuit/Layout Design Intern application - 2.5 GHz charge-pump PLL project",
                      author=APPLICANT["name"])
doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(18 * mm, 18 * mm, 174 * mm, 264 * mm, id="f", leftPadding=0,
                                                         rightPadding=0, topPadding=0, bottomPadding=0)], onPage=footer)])
doc.build(story)
print("wrote", os.path.join(HERE, OUTFILE))
