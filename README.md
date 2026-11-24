# 2.5 GHz Charge-Pump PLL: design, noise analysis and event-driven verification

A serial-link clock multiplier (100 MHz reference x 25 = 2.5 GHz), designed from first
principles and verified with an event-driven behavioural simulator written in Python.
This is the clocking block at the heart of PCIe / USB / Ethernet-class SerDes PHYs.

**This is a behavioural model, not transistor-level silicon data.** Noise inputs are
stated assumptions (see below). Phase 2 (transistor-level CP / VCO and layout) is planned,
not done.

## Run it

```bash
pip install numpy scipy matplotlib reportlab
python3 pll_model.py     # ~2 s: regenerates figures/*.png and results.json
python3 build_pdf.py     # builds the application PDF from results.json
```

## What is in the model

| Stage | What it does |
|---|---|
| Design | Closed-form loop-filter synthesis (R, C1, C2) from crossover fc, phase margin, Icp, Kvco, N |
| Frequency domain | Open-loop Bode, closed-loop response, peaking, -3 dB bandwidth |
| Noise | Reference, charge pump, filter-R and VCO phase noise, each shaped by its own transfer function; integrated RMS jitter; jitter-vs-bandwidth sweep |
| Time domain | Event-driven tri-state PFD + charge pump + R-C1-C2 filter + VCO + divide-by-N. The filter and VCO phase are integrated exactly between events (matrix exponential); divider edges are located by root finding |

Design equations (type-II, third order):

```
L(s) = K (1 + s/wz) / ( s^2 (1 + s/wp) ),   K = Icp*Kvco / (2*pi*N*(C1+C2))
sqrt(wp/wz) = tan(PM) + sqrt(1 + tan^2(PM)),  wc = sqrt(wz*wp),  K = wc^2 / sqrt(wp/wz)
C1/C2 = wp/wz - 1,   R = 1 / (wz*C1)
```

## Results (all reproduced by `pll_model.py`)

| Item | Value |
|---|---|
| Specification | fref 100 MHz, N = 25, fout 2.5 GHz, Icp 200 uA, Kvco 200 MHz/V, fc 3 MHz, PM 60 deg |
| Loop filter | R = 12.69 kohm, C1 = 15.60 pF, C2 = 1.207 pF (fz 0.80 MHz, fp 11.2 MHz) |
| Closed loop | -3 dB bandwidth 4.69 MHz, peaking 1.70 dB |
| RMS jitter (10 kHz - 20 MHz) | 380 fs total: ref 180, charge pump 253, filter R 128, VCO 179 (root-sum-square) |
| Bandwidth optimum | about 1.9 MHz (362 fs); the chosen 3 MHz costs about 5 % more jitter but needs about 2.5x less capacitor area |
| Lock acquisition | locks in 0.43 us from a 50 MHz (2 %) initial frequency error; final Vctrl within 1 nV of ideal |
| Simulator vs linear theory | 100 ps reference phase step: overshoot 18.9 % vs 18.8 %, 2 % settling 510 ns vs 513 ns, RMS deviation 1.4 % of step size |

## Assumed noise inputs (edit `NOISE` in `pll_model.py`)

- Reference phase-noise floor: -150 dBc/Hz at the 100 MHz carrier
- Charge-pump output noise: 2 pA/sqrt(Hz), duty-cycle averaged
- Free-running VCO: -112 dBc/Hz at 1 MHz offset (2.5 GHz carrier), 1/f^2 with a 100 kHz flicker corner
- Filter resistor: thermal noise at 300 K (computed)

Jitter numbers are only as good as these assumptions; the value of the model is the
trade-offs it shows, not the absolute femtoseconds.

## Not modelled (yet)

Ideal PFD (no reset delay or dead zone), no charge-pump mismatch or leakage (so no
reference spurs), ideal divider, no supply or substrate noise, no VCO tuning-curve
nonlinearity. Sampling delay of the PFD is a second-order effect at fref/fc = 33; the
simulator agrees with the continuous-time model to within 1.4 %.

## Phase 2 plan (transistor-level and layout)

1. Charge pump: UP/DN current mirrors in ngspice or Virtuoso; measure current mismatch and
   estimate reference spur level against the behavioural model.
2. VCO: LC or ring VCO sized for Kvco about 200 MHz/V; check phase noise against the -112 dBc/Hz assumption.
3. Layout considerations: common-centroid mirror devices with dummies, symmetric UP/DN routing,
   MOM capacitors for C1/C2, shielded Vctrl line, guard rings, supply isolation.

## Files

```
pll_model.py     design + analysis + simulator + plots (single file)
build_pdf.py     builds the application PDF (edit the APPLICANT block at the top)
results.json     every number quoted above
figures/         fig0..fig6 PNGs
```
