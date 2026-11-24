#!/usr/bin/env python3
"""
pll_model.py
============
Design, noise analysis and event-driven behavioural verification of a
type-II, third-order charge-pump PLL (100 MHz reference -> 2.5 GHz output).

What this script does
---------------------
1. DESIGN      - closed-form loop-filter synthesis from (fc, phase margin, Icp, Kvco, N)
2. FREQ-DOMAIN - open-loop Bode, closed-loop response, peaking, margins
3. NOISE       - ref / charge-pump / loop-filter-R / VCO phase-noise contributions,
                 integrated RMS jitter, jitter-vs-bandwidth optimisation
4. TIME-DOMAIN - event-driven simulation of a real tri-state PFD + charge pump +
                 R-C1-C2 filter + VCO (exact piece-wise integration of the filter
                 and VCO phase, divider edges located by root finding).
                 Used for (a) lock acquisition from a 2 % frequency error and
                 (b) a small reference phase step, compared with the linear model.

Run:  python3 pll_model.py          (about 20-60 s)
Out:  figures/*.png and results.json
"""
import json
import os
import time

import numpy as np
from scipy import signal
from scipy.linalg import expm
from scipy.optimize import brentq

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures")
KB, TEMP = 1.380649e-23, 300.0

# ----------------------------------------------------------------------------
# Specification and (assumed) noise inputs.  Change these and re-run.
# ----------------------------------------------------------------------------
SPEC = dict(fref=100e6, N=25, fc=3e6, PM_deg=60.0, Icp=200e-6, Kvco_Hz=200e6)

NOISE = dict(
    ref_floor_dbc=-150.0,      # reference phase-noise floor, dBc/Hz (at 100 MHz carrier)
    icp_noise=2e-12,           # effective charge-pump output noise, A/sqrt(Hz), duty averaged
    vco_dbc_1M=-112.0,         # free-running VCO phase noise @ 1 MHz offset, 2.5 GHz carrier
    vco_flicker_corner=100e3,  # 1/f^3 corner of the VCO, Hz
    band=(10e3, 20e6),         # jitter integration band, Hz
)

C = dict(blue="#0072B2", red="#D55E00", green="#009E73", orange="#E69F00",
         pink="#CC79A7", grey="#6b7280", ink="#111827")


# ----------------------------------------------------------------------------
# 1. DESIGN
# ----------------------------------------------------------------------------
def design(fref, N, fc, PM_deg, Icp, Kvco_Hz):
    """Loop filter synthesis.  Passive R-C1 // C2 filter, crossover fc, phase margin PM.

    L(s) = K (1 + s/wz) / ( s^2 (1 + s/wp) ),   K = Icp*Kvco / (2*pi*N*(C1+C2))
    Maximum phase at wc = sqrt(wz*wp) gives  sqrt(wp/wz) = tan(PM) + sqrt(1+tan^2(PM)).
    |L(jwc)| = 1  ->  K = wc^2 / sqrt(wp/wz).
    """
    Kvco = 2 * np.pi * Kvco_Hz                    # rad/s/V
    wc = 2 * np.pi * fc
    x = np.tan(np.radians(PM_deg))
    s = x + np.sqrt(x * x + 1.0)                  # sqrt(wp/wz)
    b = s * s                                     # wp/wz = 1 + C1/C2
    wz, wp = wc / s, wc * s
    K = wc ** 2 / s
    Ct = Icp * Kvco / (2 * np.pi * N * K)
    C2 = Ct / b
    C1 = Ct - C2
    R = 1.0 / (wz * C1)
    return dict(fref=fref, N=N, fc=fc, PM_deg=PM_deg, Icp=Icp, Kvco_Hz=Kvco_Hz, Kvco=Kvco,
                wc=wc, wz=wz, wp=wp, b=b, K=K, Ct=Ct, C1=C1, C2=C2, R=R, fout=fref * N)


# ----------------------------------------------------------------------------
# 2. FREQUENCY-DOMAIN ANALYSIS
# ----------------------------------------------------------------------------
def L_of(p, f, delay=False):
    """Open-loop gain.  delay=True adds the ~Tref/2 sampling delay of the PFD/charge pump."""
    s = 2j * np.pi * np.asarray(f, float)
    L = p["K"] * (1 + s / p["wz"]) / (s ** 2 * (1 + s / p["wp"]))
    return L * np.exp(-s / (2 * p["fref"])) if delay else L


def phase_deg(p, f, delay=False):
    w = 2 * np.pi * np.asarray(f, float)
    ph = -180 + np.degrees(np.arctan(w / p["wz"]) - np.arctan(w / p["wp"]))
    return ph - np.degrees(w / (2 * p["fref"])) if delay else ph


def Z_of(p, s):
    """Loop-filter impedance seen by the charge pump."""
    R, C1, C2, Ct = p["R"], p["C1"], p["C2"], p["Ct"]
    return (1 + s * R * C1) / (s * Ct * (1 + s * R * C1 * C2 / Ct))


def margins(p, delay=False):
    g = lambda lf: np.log(np.abs(L_of(p, np.exp(lf), delay)))
    fc = float(np.exp(brentq(g, np.log(1e4), np.log(1e8))))
    return fc, float(180 + phase_deg(p, fc, delay))


def closed_loop_stats(p):
    f = np.logspace(4, 8, 40001)
    L = L_of(p, f)
    H = 20 * np.log10(np.abs(L / (1 + L)))
    ipk = int(np.argmax(H))
    j = ipk + int(np.argmax(H[ipk:] < -3.0))
    f3 = float(np.interp(-3.0, [H[j], H[j - 1]], [f[j], f[j - 1]]))
    return dict(bw_3db=f3, peaking_db=float(H[ipk]), f_peak=float(f[ipk]))


# ----------------------------------------------------------------------------
# 3. NOISE
# ----------------------------------------------------------------------------
def noise_psd(p, f, nz=NOISE):
    """Output phase-noise PSDs in rad^2/Hz for each contributor."""
    f = np.asarray(f, float)
    s = 2j * np.pi * f
    L = L_of(p, f)
    E, H = 1 / (1 + L), L / (1 + L)
    N = p["N"]
    S_ref = N ** 2 * 2 * 10 ** (nz["ref_floor_dbc"] / 10) * np.abs(H) ** 2
    S_cp = np.abs(p["Kvco"] / s * Z_of(p, s) * E) ** 2 * nz["icp_noise"] ** 2
    HR = 1 / (1 + p["C2"] / p["C1"] + s * p["R"] * p["C2"])
    S_R = np.abs(p["Kvco"] / s * HR * E) ** 2 * 4 * KB * TEMP * p["R"]
    fcor = nz["vco_flicker_corner"]
    S_free = (2 * 10 ** (nz["vco_dbc_1M"] / 10) * (1e6 / f) ** 2
              * (1 + fcor / f) / (1 + fcor / 1e6))
    S_vco = np.abs(E) ** 2 * S_free
    return dict(ref=S_ref, cp=S_cp, r=S_R, vco=S_vco, vco_free=S_free,
                total=S_ref + S_cp + S_R + S_vco)


def rms_jitter_fs(p, f, S, band):
    m = (f >= band[0]) & (f <= band[1])
    var = np.trapezoid(S[m], f[m])                # rad^2
    return float(np.sqrt(var) / (2 * np.pi * p["fout"]) * 1e15)


def jitter_breakdown(p, nz=NOISE):
    f = np.logspace(3, 8.3, 6000)
    P = noise_psd(p, f, nz)
    out = {k: rms_jitter_fs(p, f, P[k], nz["band"]) for k in ("ref", "cp", "r", "vco", "total")}
    return f, P, out


def bandwidth_sweep(spec, nz=NOISE):
    fcs = np.logspace(np.log10(0.3e6), np.log10(10e6), 45)
    rows = []
    for fc in fcs:
        q = design(**{**spec, "fc": fc})
        _, _, j = jitter_breakdown(q, nz)
        rows.append((fc, j["total"], j["vco"], np.sqrt(j["ref"] ** 2 + j["cp"] ** 2 + j["r"] ** 2),
                     q["R"], q["C1"], q["C2"]))
    return np.array(rows)


# ----------------------------------------------------------------------------
# 4. TIME-DOMAIN, EVENT-DRIVEN SIMULATION
# ----------------------------------------------------------------------------
def build_A(p, f_free):
    """Linear state matrix. x = [V1, V2, phi(cycles), 1, I/Icp].
    V1: voltage on C1, V2: control voltage (on C2).  f_vco = f_free + Kvco_Hz * V2."""
    R, C1, C2 = p["R"], p["C1"], p["C2"]
    A = np.zeros((5, 5))
    A[0, 0], A[0, 1] = -1 / (R * C1), 1 / (R * C1)
    A[1, 0], A[1, 1], A[1, 4] = 1 / (R * C2), -1 / (R * C2), p["Icp"] / C2
    A[2, 1], A[2, 3] = p["Kvco_Hz"], f_free
    return A


def simulate(p, f_free, t_end, v0=(0.0, 0.0), ref_step=(None, 0.0)):
    """Tri-state PFD + charge pump + RC filter + VCO + /N, simulated exactly between events.
    ref_step = (k_step, dT): reference edges from index k_step on are delayed by dT seconds."""
    A = build_A(p, f_free)
    Tref, N = 1.0 / p["fref"], p["N"]
    k_step, dT = ref_step
    ref_time = lambda k: k * Tref + (dT if (k_step is not None and k >= k_step) else 0.0)

    x = np.array([v0[0], v0[1], 0.0, 1.0, 0.0])
    t, up, dn, k, thr = 0.0, False, False, 1, float(N)
    next_ref = ref_time(k)
    ref_t, div_t, rec = [], [], [(0.0, v0[0], v0[1], 0)]

    while t < t_end:
        x[3], x[4] = 1.0, float(up) - float(dn)
        xr = expm(A * (next_ref - t)) @ x
        if xr[2] >= thr:                                   # divider edge comes first
            g = lambda s: (expm(A * s) @ x)[2] - thr
            s = brentq(g, 0.0, next_ref - t, xtol=1e-17, rtol=1e-12)
            x = expm(A * s) @ x
            t += s
            div_t.append(t)
            ev = 1
            if up:
                up = False
            else:
                dn = True
            thr += N
        else:                                              # reference edge comes first
            x, t = xr, next_ref
            ref_t.append(t)
            ev = 0
            if dn:
                dn = False
            else:
                up = True
            k += 1
            next_ref = ref_time(k)
        rec.append((t, x[0], x[1], ev))
    return dict(rec=np.array(rec), ref_t=np.array(ref_t), div_t=np.array(div_t))


def error_step_response(p, t, delay=False, w0=1e7):
    """Step response of E(s) = 1/(1+L(s)) (phase error for a reference phase step).
    delay=True inserts a first-order Pade model of the Tref/2 sampling delay."""
    P = np.polynomial.polynomial
    Nl = p["K"] * np.array([1.0, w0 / p["wz"]])
    Dl = P.polymul([0, 0, w0 ** 2], [1.0, w0 / p["wp"]])
    if delay:
        tau = 0.5 / p["fref"]
        Nl = P.polymul(Nl, [1.0, -w0 * tau / 2])
        Dl = P.polymul(Dl, [1.0, w0 * tau / 2])
    den = P.polyadd(Dl, Nl)
    sc = den[-1]
    sys = signal.TransferFunction((Dl / sc)[::-1], (den / sc)[::-1])
    tt, y = signal.step(sys, T=t * w0)
    return y


def settle_time(t, y, tol):
    bad = np.where(np.abs(y) > tol)[0]
    return float(t[bad[-1] + 1]) if len(bad) and bad[-1] + 1 < len(t) else float(t[0])


# ----------------------------------------------------------------------------
# PLOTTING
# ----------------------------------------------------------------------------
def style():
    plt.rcParams.update({
        "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9, "legend.fontsize": 8,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": "#e5e7eb", "grid.linewidth": 0.6,
        "axes.edgecolor": "#9ca3af", "axes.labelcolor": C["ink"],
        "xtick.color": "#374151", "ytick.color": "#374151",
        "figure.dpi": 100, "savefig.dpi": 220, "savefig.bbox": "tight",
    })


def save(fig, name):
    fig.savefig(os.path.join(FIG, name))
    plt.close(fig)


def fig_block(p):
    fig, ax = plt.subplots(figsize=(7.6, 2.7))
    ax.set_xlim(0, 17.4)
    ax.set_ylim(0, 5)
    ax.axis("off")
    yb, h = 2.7, 1.6
    yc = yb + h / 2

    def box(x, w, title, sub, fc="#eef6fb", ec=C["blue"], yy=yb, hh=h):
        ax.add_patch(FancyBboxPatch((x, yy), w, hh, boxstyle="round,pad=0.02,rounding_size=0.12",
                                    fc=fc, ec=ec, lw=1.3))
        ax.text(x + w / 2, yy + hh / 2 + 0.28, title, ha="center", va="center",
                fontsize=9, fontweight="bold", color=C["ink"])
        ax.text(x + w / 2, yy + hh / 2 - 0.32, sub, ha="center", va="center", fontsize=7, color="#374151")

    def arrow(x0, y0, x1, y1):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color=C["ink"], lw=1.2, shrinkA=0, shrinkB=0))

    box(1.6, 1.8, "PFD", "tri-state")
    box(4.6, 2.5, "Charge pump", f"Icp = {p['Icp']*1e6:.0f} uA")
    box(8.0, 3.9, "Loop filter", f"R {p['R']/1e3:.1f}k | C1 {p['C1']*1e12:.1f}p | C2 {p['C2']*1e12:.2f}p")
    box(12.8, 2.6, "VCO", f"Kvco = {p['Kvco_Hz']/1e6:.0f} MHz/V", fc="#fdf1e7", ec=C["red"])
    box(7.2, 2.6, f"Divider /{p['N']}", "feedback path", fc="#eef8f3", ec=C["green"], yy=0.2, hh=1.4)

    ax.text(0.1, yc, "fref\n100 MHz", ha="left", va="center", fontsize=8, color=C["ink"])
    arrow(1.05, yc, 1.6, yc)
    arrow(3.4, yc, 4.6, yc)
    ax.text(4.0, yc + 0.34, "UP/DN", ha="center", fontsize=6.5, color="#374151")
    arrow(7.1, yc, 8.0, yc)
    arrow(11.9, yc, 12.8, yc)
    ax.text(12.35, yc + 0.22, "Vctrl", ha="center", fontsize=6.5, color="#374151")
    ax.plot([15.4, 16.1], [yc, yc], color=C["ink"], lw=1.2)
    arrow(15.9, yc, 16.15, yc)
    ax.text(16.25, yc, "fout\n2.5 GHz", ha="left", va="center", fontsize=8, color=C["ink"])
    ax.plot([15.75], [yc], "o", color=C["ink"], ms=3.5)
    ax.plot([15.75, 15.75], [yc, 0.9], color=C["ink"], lw=1.2)
    ax.plot([15.75, 9.8], [0.9, 0.9], color=C["ink"], lw=1.2)
    arrow(10.2, 0.9, 9.8, 0.9)
    ax.plot([7.2, 2.5], [0.9, 0.9], color=C["ink"], lw=1.2)
    ax.plot([2.5, 2.5], [0.9, yb - 0.02], color=C["ink"], lw=1.2)
    arrow(2.5, yb - 0.45, 2.5, yb)
    save(fig, "fig0_block.png")

def fig_bode(p):
    f = np.logspace(4, 8, 2000)
    L = L_of(p, f)
    fc, pm = margins(p)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(6.6, 4.4), sharex=True)
    a1.semilogx(f, 20 * np.log10(np.abs(L)), color=C["blue"], lw=2)
    a1.axhline(0, color=C["grey"], lw=0.8)
    a1.set_ylabel("|L(f)|  (dB)")
    a1.set_title("Open-loop gain and phase margin")
    a2.semilogx(f, phase_deg(p, f), color=C["blue"], lw=2, label="continuous-time model")
    a2.semilogx(f, phase_deg(p, f, True), color=C["red"], lw=1.6, ls="--",
                label="conservative: extra Tref/2 sampling delay")
    a2.axhline(-180, color=C["grey"], lw=0.8)
    a2.set_ylabel("Phase (deg)")
    a2.set_xlabel("Frequency (Hz)")
    for a in (a1, a2):
        a.axvline(fc, color=C["green"], lw=1, ls=":")
        a.axvline(p["wz"] / 2 / np.pi, color=C["grey"], lw=0.8, ls=":")
        a.axvline(p["wp"] / 2 / np.pi, color=C["grey"], lw=0.8, ls=":")
    a1.text(fc * 1.12, 38, f"fc = {fc/1e6:.2f} MHz", fontsize=8.5, color=C["green"])
    a2.annotate("", xy=(fc, -180 + pm), xytext=(fc, -180),
                arrowprops=dict(arrowstyle="<->", color=C["green"], lw=1.3, shrinkA=0, shrinkB=0))
    a2.text(fc * 0.9, -172, f"PM = {pm:.1f} deg", fontsize=8.5, color=C["green"], ha="right")
    a2.text(p["wz"] / 2 / np.pi * 0.92, -108, "fz", ha="right", fontsize=8, color=C["grey"])
    a2.text(p["wp"] / 2 / np.pi * 1.08, -108, "fp", ha="left", fontsize=8, color=C["grey"])
    a2.legend(loc="upper left", frameon=False)
    a2.set_ylim(-185, -100)
    fig.tight_layout()
    save(fig, "fig1_bode.png")

def fig_closed(p):
    f = np.logspace(4, 8, 2000)
    L = L_of(p, f)
    H, E = 20 * np.log10(np.abs(L / (1 + L))), 20 * np.log10(np.abs(1 / (1 + L)))
    st = closed_loop_stats(p)
    fig, ax = plt.subplots(figsize=(6.6, 3.2))
    ax.semilogx(f, H, color=C["blue"], lw=2, label="Ref / CP / R path:  L/(1+L)  (low-pass)")
    ax.semilogx(f, E, color=C["red"], lw=2, label="VCO path:  1/(1+L)  (high-pass)")
    ax.axhline(-3, color=C["grey"], lw=0.8, ls=":")
    ax.axvline(st["bw_3db"], color=C["green"], lw=1, ls=":")
    ax.text(st["bw_3db"] * 1.1, -45,
            f"-3 dB BW = {st['bw_3db']/1e6:.2f} MHz\npeaking = {st['peaking_db']:.2f} dB",
            fontsize=8.5, color=C["green"])
    ax.set_ylim(-60, 8)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Magnitude (dB)")
    ax.set_title("Closed-loop transfer functions")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2, frameon=False)
    fig.tight_layout()
    save(fig, "fig2_closedloop.png")


def fig_noise(p, f, P, jit):
    dbc = lambda S: 10 * np.log10(np.maximum(S, 1e-30) / 2)
    fig, ax = plt.subplots(figsize=(6.6, 3.7))
    ax.semilogx(f, dbc(P["vco_free"]), color=C["grey"], lw=1.2, ls="--", label="VCO free-running")
    ax.semilogx(f, dbc(P["ref"]), color=C["blue"], lw=1.4, label="Reference")
    ax.semilogx(f, dbc(P["cp"]), color=C["green"], lw=1.4, label="Charge pump")
    ax.semilogx(f, dbc(P["r"]), color=C["orange"], lw=1.4, label="Filter R")
    ax.semilogx(f, dbc(P["vco"]), color=C["red"], lw=1.4, label="VCO (shaped by loop)")
    ax.semilogx(f, dbc(P["total"]), color=C["ink"], lw=2.4, label="Total output")
    b = NOISE["band"]
    ax.axvspan(b[0], b[1], color=C["blue"], alpha=0.06,
               label=f"integration band {b[0]/1e3:.0f} kHz - {b[1]/1e6:.0f} MHz: {jit['total']:.0f} fs RMS")
    ax.set_ylim(-165, -70)
    ax.set_xlim(1e3, 2e8)
    ax.set_xlabel("Offset frequency (Hz)")
    ax.set_ylabel("Phase noise (dBc/Hz)")
    ax.set_title("Output phase noise of the 2.5 GHz PLL, by source")
    ax.legend(loc="upper right", ncol=2, frameon=False)
    fig.tight_layout()
    save(fig, "fig3_phasenoise.png")


def fig_sweep(sw, p, j_design):
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    ax.semilogx(sw[:, 0], sw[:, 1], color=C["ink"], lw=2.4, label="Total")
    ax.semilogx(sw[:, 0], sw[:, 2], color=C["red"], lw=1.4, label="VCO (loop too slow to clean it)")
    ax.semilogx(sw[:, 0], sw[:, 3], color=C["blue"], lw=1.4, label="Ref + CP + R (passed to output)")
    i = int(np.argmin(sw[:, 1]))
    ax.plot(sw[i, 0], sw[i, 1], "o", color=C["green"], ms=7, zorder=5)
    ax.annotate(f"optimum ~ {sw[i,0]/1e6:.1f} MHz\n{sw[i,1]:.0f} fs", (sw[i, 0], sw[i, 1]),
                (0.62e6, 55), fontsize=8.5, color=C["green"], va="bottom",
                arrowprops=dict(arrowstyle="-", color=C["green"]))
    ax.plot(p["fc"], j_design, "s", color=C["orange"], ms=7, zorder=5)
    ax.annotate(f"chosen design\nfc = {p['fc']/1e6:.0f} MHz, {j_design:.0f} fs", (p["fc"], j_design),
                (3.3e6, 10), fontsize=8.5, color="#b45309", va="bottom",
                arrowprops=dict(arrowstyle="-", color="#b45309"))
    ax.set_xlabel("Loop crossover frequency fc (Hz)")
    ax.set_ylabel("RMS jitter, 10 kHz - 20 MHz (fs)")
    ax.set_title("Jitter vs loop bandwidth (PM = 60 deg, fixed Icp and Kvco)")
    ax.legend(loc="upper center", frameon=False, ncol=1)
    ax.set_ylim(0, 1000)
    fig.tight_layout()
    save(fig, "fig4_jitter_vs_bw.png")

def fig_lock(p, sim, f_free, t_lock):
    rec = sim["rec"]
    rec = rec[rec[:, 3] == 0]                       # sample once per reference edge
    t = rec[:, 0] * 1e6
    f_err = (f_free + p["Kvco_Hz"] * rec[:, 2] - p["fout"]) / 1e6
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(6.6, 4.2), sharex=True)
    a1.plot(t, rec[:, 2], color=C["blue"], lw=1.5)
    a1.axhline((p["fout"] - f_free) / p["Kvco_Hz"], color=C["grey"], lw=0.8, ls=":")
    a1.set_ylabel("Control voltage (V)")
    a1.set_title(f"Lock acquisition from {abs(f_err[0]):.0f} MHz ({abs(f_err[0])/25:.1f} %) frequency error")
    a2.plot(t, f_err, color=C["red"], lw=1.5)
    a2.axhline(0, color=C["grey"], lw=0.8, ls=":")
    a2.set_ylabel("f_vco - 2.5 GHz (MHz)")
    a2.set_xlabel("Time (us)")
    for a in (a1, a2):
        a.axvline(t_lock * 1e6, color=C["green"], lw=1, ls="--")
    a2.text(t_lock * 1e6 + 0.04, f_err.min() * 0.55, f"locked at {t_lock*1e6:.2f} us", color=C["green"], fontsize=8.5)
    a2.set_xlim(0, 1.6)
    fig.tight_layout()
    save(fig, "fig5_lock.png")

def fig_step(tn, e_sim, tm, y_ct, dT):
    fig, ax = plt.subplots(figsize=(6.6, 3.3))
    ax.plot(tm * 1e6, -y_ct, color=C["blue"], lw=1.6, label="Linear model (continuous-time)")
    ax.plot(tn * 1e6, e_sim / dT, "o", color=C["ink"], ms=3.4, label="Event-driven simulation")
    ax.axhline(0, color=C["grey"], lw=0.8)
    ax.set_xlabel("Time after reference phase step (us)")
    ax.set_ylabel("Phase error / step size")
    ax.set_title(f"Response to a {dT*1e12:.0f} ps reference phase step: simulation vs linear theory")
    ax.set_xlim(0, tn.max() * 1e6)
    ax.legend(loc="lower right", frameon=False)
    fig.tight_layout()
    save(fig, "fig6_phase_step.png")


# ----------------------------------------------------------------------------
def main():
    t0 = time.time()
    os.makedirs(FIG, exist_ok=True)
    style()
    R = {"spec": SPEC, "noise_assumptions": {k: (list(v) if isinstance(v, tuple) else v) for k, v in NOISE.items()}}

    # --- design ---
    p = design(**SPEC)
    R["design"] = dict(R_kohm=p["R"] / 1e3, C1_pF=p["C1"] * 1e12, C2_pF=p["C2"] * 1e12,
                       Ctotal_pF=p["Ct"] * 1e12, fz_MHz=p["wz"] / 2 / np.pi / 1e6,
                       fp_MHz=p["wp"] / 2 / np.pi / 1e6, K=p["K"], fout_GHz=p["fout"] / 1e9,
                       fref_over_fc=p["fref"] / p["fc"])
    fc, pm = margins(p)
    fcd, pmd = margins(p, delay=True)
    assert abs(fc / SPEC["fc"] - 1) < 1e-3, "crossover does not match target"
    assert abs(pm - SPEC["PM_deg"]) < 0.05, "phase margin does not match target"
    R["margins"] = dict(fc_MHz=fc / 1e6, PM_deg=pm, PM_with_sampling_delay_deg=pmd)
    R["closed_loop"] = closed_loop_stats(p)
    print(f"design: R={p['R']/1e3:.2f}k C1={p['C1']*1e12:.2f}p C2={p['C2']*1e12:.3f}p  "
          f"fc={fc/1e6:.3f} MHz PM={pm:.2f} (with delay {pmd:.2f})")

    # --- noise ---
    f, P, jit = jitter_breakdown(p)
    R["jitter_fs"] = jit
    sw = bandwidth_sweep(SPEC)
    i = int(np.argmin(sw[:, 1]))
    R["sweep"] = dict(opt_fc_MHz=sw[i, 0] / 1e6, opt_jitter_fs=sw[i, 1])
    print("jitter (fs):", {k: round(v, 1) for k, v in jit.items()}, " optimum fc = %.2f MHz" % (sw[i, 0] / 1e6))

    # --- time domain: lock acquisition ---
    f_free = 2.45e9
    sim = simulate(p, f_free, 6e-6, v0=(0.0, 0.0))
    n = min(len(sim["ref_t"]), len(sim["div_t"]))
    e = sim["div_t"][:n] - sim["ref_t"][:n]
    Tref = 1 / p["fref"]
    ew = (e + Tref / 2) % Tref - Tref / 2                    # wrap to +/- Tref/2
    bad = np.where(np.abs(ew) > 0.01 * Tref)[0]              # |error| > 1 % of Tref (100 ps)
    t_lock = float(sim["ref_t"][bad[-1] + 1]) if len(bad) else 0.0
    R["lock"] = dict(initial_freq_error_MHz=(2.5e9 - f_free) / 1e6, t_lock_us=t_lock * 1e6,
                     final_Vctrl=float(sim["rec"][-1, 2]), ideal_Vctrl=(p["fout"] - f_free) / p["Kvco_Hz"],
                     events=int(len(sim["rec"])))
    print(f"lock: {t_lock*1e6:.2f} us, final Vc={sim['rec'][-1,2]:.5f} V (ideal {(p['fout']-f_free)/p['Kvco_Hz']:.5f})")

    # --- time domain: small phase step vs linear theory ---
    dT, k_step, n_after = 100e-12, 20, 160
    sim2 = simulate(p, p["fout"], (k_step + n_after + 2) * Tref, ref_step=(k_step, dT))
    m = min(len(sim2["ref_t"]), len(sim2["div_t"]))
    e2 = sim2["div_t"][:m] - sim2["ref_t"][:m]
    idx = np.arange(k_step - 1, k_step - 1 + n_after)
    e_sim = e2[idx]
    tn = np.arange(n_after) * Tref
    tm = np.linspace(0, tn.max(), 1500)
    y_ct = error_step_response(p, tm)
    y_dl = error_step_response(p, tm, delay=True)
    ym = lambda y: np.interp(tn, tm, y)
    rms = lambda a, b: float(np.sqrt(np.mean((a - b) ** 2)))
    err_ct, err_dl = rms(e_sim / dT, -ym(y_ct)), rms(e_sim / dT, -ym(y_dl))
    tol = 0.02
    R["step"] = dict(dT_ps=dT * 1e12, rms_dev_ct=err_ct, rms_dev_delay=err_dl,
                     pre_step_max_err_ps=float(np.max(np.abs(e2[:k_step - 1])) * 1e12),
                     settle2pct_sim_ns=settle_time(tn, e_sim / dT, tol) * 1e9,
                     settle2pct_ct_ns=settle_time(tm, y_ct, tol) * 1e9,
                     settle2pct_delay_ns=settle_time(tm, y_dl, tol) * 1e9,
                     overshoot_sim_pct=float(max(0.0, np.max(e_sim / dT)) * 100),
                     overshoot_ct_pct=float(max(0.0, -np.min(y_ct)) * 100))
    print("step:", {k: round(v, 3) for k, v in R["step"].items()})

    # --- figures ---
    fig_block(p)
    fig_bode(p)
    fig_closed(p)
    fig_noise(p, f, P, jit)
    fig_sweep(sw, p, jit["total"])
    fig_lock(p, sim, f_free, t_lock)
    fig_step(tn, e_sim, tm, y_ct, dT)

    R["runtime_s"] = time.time() - t0
    with open(os.path.join(HERE, "results.json"), "w") as fh:
        json.dump(R, fh, indent=2)
    print(f"done in {R['runtime_s']:.1f} s")


if __name__ == "__main__":
    main()
