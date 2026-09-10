#!/usr/bin/env python
"""gf180-physaudit-v0 driver — device-physics audit of the gf180mcu ladder wall.

Pre-reg: kaggle/CAMPAIGN-GF180-PHYSAUDIT.md (frozen before results).
Box-side only. Zero store writes. Raw decks + verbatim ngspice logs kept.

Usage:
  python kaggle/gf180_physaudit.py --out <dir> [--quick] [--probe-vectors]
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from lna.pdk import pdk_root  # noqa: E402

import numpy as np  # noqa: E402
import yaml  # noqa: E402

NGSPICE = os.environ.get("NGSPICE", "ngspice")
Z0 = 50.0
K4T = 1.65678e-20          # 4kT at 300 K (harness constant 8.283894e-19 / 50)
W_REF = 20e-6
NF_REF = 10                # 2 um/finger harness convention
L_FIXED = "0.28e-6"
W_BOX = (0.22e-6, 100e-6)  # sizer device_ranges for gf180mcu
VDS_GRID = (1.1, 1.65, 2.2)
VGS_GRID = [round(0.45 + i * 0.075, 3) for i in range(15)]      # 0.45..1.50
VGS_T2 = [0.55, 0.625, 0.7, 0.775, 0.85, 0.95, 1.1, 1.3]        # T2 subset
RS_GRID = [10, 15, 25, 40, 65, 100, 160, 250, 400, 650, 1000]   # ohm
LG_GRID = [0, 0.5e-9, 1e-9, 2e-9, 3e-9, 5e-9, 8e-9, 12e-9, 18e-9, 25e-9]
F_TARGETS = {  # spec eval frequencies (Hz); wideband s21 at 3.0 GHz edge
    "0.915": 0.915e9, "1.575": 1.57542e9, "1.75": 1.75e9,
    "2.442": 2.442e9, "3.0": 3.0e9, "3.5": 3.5e9, "5.8": 5.8e9,
}
SOLVED_FENCE = ("cap-e01-wifi", "cap-m06-wifi")  # must NOT be device-infeasible
NF_SLACK_DB = 0.5
GAIN_BORDER_DB = 3.0
STAGES = (1, 2, 3)


def gf_root():
    return Path(pdk_root("gf180mcu"))  # already the <root>/gf180mcu dir


def includes():
    r = gf_root()
    return (f'.include "{r}/models/ngspice/design.ngspice"\n'
            f'.lib "{r}/models/ngspice/sm141064.ngspice" typical\n')


def run_deck(deck: str, rawdir: Path, tag: str, timeout=180):
    rawdir.mkdir(parents=True, exist_ok=True)
    f = rawdir / f"{tag}.cir"
    f.write_text(deck)
    p = subprocess.run([NGSPICE, "-b", f.name], cwd=rawdir,
                       capture_output=True, text=True, timeout=timeout)
    log = (p.stdout or "") + (p.stderr or "")
    (rawdir / f"{tag}.log").write_text(log)
    return log


def deck_smoke():
    # check_pdk_live's gf180 CS smoke, reproduced verbatim (plumbing fence a)
    return (f"* physaudit fence: check_pdk_live gf180 smoke repro\n{includes()}"
            "Vdd vdd 0 3.3\nVin in 0 dc 1.2 ac 1\nRd vdd d 5k\n"
            "XM1 d in 0 0 nmos_3p3 w=10e-6 l=0.28e-6 nf=1\n"
            ".control\nop\nprint v(d)\nlet id = (3.3 - v(d))/5k\nprint id\n"
            "ac dec 10 1e3 1e9\nlet gdb = db(v(d))\n"
            "meas ac gainlf find gdb at=1e3\n.endc\n.end\n")


def deck_sp(vgs, vds, w=W_REF, nfing=NF_REF, tag="sp", donoise=1):
    return (f"* physaudit T1 sp vgs={vgs} vds={vds} w={w}\n{includes()}"
            f"Vg gb 0 dc {vgs}\nLg gb g 1\n"
            f"Vd db 0 dc {vds}\nLd db d 1\n"
            "Vp1 p1 0 dc 0 ac 1 portnum 1 z0 50\nCp1 p1 g 1\n"
            "Vp2 p2 0 dc 0 ac 0 portnum 2 z0 50\nCp2 p2 d 1\n"
            f"X1 d g 0 0 nmos_3p3 w={w:g} l={L_FIXED} nf={nfing}\n"
            ".control\nop\nlet id = -i(Vd)\nprint id\n"
            f"sp dec 20 1e8 5e11 {donoise}\n"
            "set wr_singlescale\nset wr_vecnames\n"
            "let s11r=real(S_1_1)\nlet s11i=imag(S_1_1)\n"
            "let s12r=real(S_1_2)\nlet s12i=imag(S_1_2)\n"
            "let s21r=real(S_2_1)\nlet s21i=imag(S_2_1)\n"
            "let s22r=real(S_2_2)\nlet s22i=imag(S_2_2)\n"
            f"wrdata {tag}_sp.csv s11r s11i s12r s12i s21r s21i s22r s22i\n"
            + ("display\n" if donoise else "")
            + ".endc\n.end\n")


def deck_sp_noisevec(vgs, vds, tag):
    # probe/extract sp-donoise noise vectors if present (NF/NFmin/Rn)
    return (f"* physaudit T2p sp-noise vgs={vgs} vds={vds}\n{includes()}"
            f"Vg gb 0 dc {vgs}\nLg gb g 1\n"
            f"Vd db 0 dc {vds}\nLd db d 1\n"
            "Vp1 p1 0 dc 0 ac 1 portnum 1 z0 50\nCp1 p1 g 1\n"
            "Vp2 p2 0 dc 0 ac 0 portnum 2 z0 50\nCp2 p2 d 1\n"
            f"X1 d g 0 0 nmos_3p3 w={W_REF:g} l={L_FIXED} nf={NF_REF}\n"
            ".control\nop\nlet id = -i(Vd)\nprint id\n"
            "sp dec 20 1e8 2e10 1\n"
            "set wr_singlescale\nset wr_vecnames\n"
            "let nfr = real(NF)\nlet nfminr = real(NFmin)\n"
            "let rnr = real(Rn)\n"
            "wrdata {t}_nfv.csv nfr nfminr rnr\n.endc\n.end\n"
            .replace("{t}", tag))


def deck_noise(vgs, rs, lg, tag, vds=1.65):
    src = f"Vnz nin 0 dc 0 ac 1\nRns nin n1 {rs}\n"
    if lg > 0:
        src += f"Lser n1 n2 {lg:g}\nCblk n2 g 1\n"
    else:
        src += "Cblk n1 g 1\n"
    return (f"* physaudit T2 noise vgs={vgs} rs={rs} lg={lg:g}\n{includes()}"
            f"{src}"
            f"Vg gb 0 dc {vgs}\nLgb gb g 1\n"
            f"Vd db 0 dc {vds}\nLd db d 1\n"
            f"X1 d g 0 0 nmos_3p3 w={W_REF:g} l={L_FIXED} nf={NF_REF}\n"
            ".control\nop\nlet id = -i(Vd)\nprint id\n"
            "noise v(d) Vnz dec 10 8e8 6.5e9\nsetplot noise1\n"
            "set wr_singlescale\nset wr_vecnames\n"
            "let inr = inoise_spectrum\n"
            f"wrdata {tag}_nz.csv inr\n.endc\n.end\n")


def parse_id(log):
    m = re.search(r"^id\s*=\s*([-+0-9.eE]+)", log, re.M)
    return float(m.group(1)) if m else None


def read_wrdata(path):
    """wr_vecnames+wr_singlescale file -> dict of name -> np.array."""
    if not path.exists():
        return None
    lines = path.read_text().strip().splitlines()
    if len(lines) < 2:
        return None
    names = lines[0].split()
    data = np.array([[float(x) for x in ln.split()] for ln in lines[1:]])
    return {n: data[:, i] for i, n in enumerate(names)}


def s_to_figures(d):
    """From wrdata dict -> dict of freq-domain figures arrays."""
    f = d["frequency"]
    S11 = d["s11r"] + 1j * d["s11i"]
    S12 = d["s12r"] + 1j * d["s12i"]
    S21 = d["s21r"] + 1j * d["s21i"]
    S22 = d["s22r"] + 1j * d["s22i"]
    det = S11 * S22 - S12 * S21
    absS12S21 = np.abs(S12 * S21)
    with np.errstate(divide="ignore", invalid="ignore"):
        K = (1 - np.abs(S11) ** 2 - np.abs(S22) ** 2 + np.abs(det) ** 2) / (
            2 * absS12S21)
        msg = np.abs(S21) / np.abs(S12)
        mag = np.where(K >= 1, msg * (K - np.sqrt(np.maximum(K * K - 1, 0))),
                       np.nan)
    # Y-params (z0-normalized) for h21 and Mason U
    y0 = 1.0 / Z0
    dn = (1 + S11) * (1 + S22) - S12 * S21
    Y11 = y0 * ((1 - S11) * (1 + S22) + S12 * S21) / dn
    Y12 = y0 * (-2 * S12) / dn
    Y21 = y0 * (-2 * S21) / dn
    Y22 = y0 * ((1 + S11) * (1 - S22) + S12 * S21) / dn
    h21 = np.abs(Y21 / Y11)
    with np.errstate(divide="ignore", invalid="ignore"):
        U = (np.abs(Y21 - Y12) ** 2) / np.maximum(
            4 * (Y11.real * Y22.real - Y12.real * Y21.real), 1e-30)
    return {"f": f, "K": K, "MSG": msg, "MAG": mag, "h21": h21, "U": U}


def unity_crossing(f, mag_arr):
    """First downward |x|=1 crossing, log-log interpolated; None if absent."""
    v = np.log10(np.maximum(mag_arr, 1e-12))
    for i in range(1, len(f)):
        if v[i - 1] > 0 >= v[i]:
            x0, x1 = math.log10(f[i - 1]), math.log10(f[i])
            t = v[i - 1] / (v[i - 1] - v[i])
            return 10 ** (x0 + t * (x1 - x0))
    return None


def interp_at(f, arr, ft_):
    return float(np.interp(ft_, f, arr))


def load_ladder():
    ladder = json.loads((REPO / "kaggle/specs-ladder/ladder.json").read_text())
    specs = []
    for row in ladder["specs"]:
        y = yaml.safe_load((REPO / "kaggle/specs-ladder" / row["file"]).read_text())
        band = y["band"]
        wide = row["band_type"] == "wideband"
        specs.append({
            "spec": row["name"], "tier": row["tier"],
            "band": row["band"], "band_type": row["band_type"],
            "f0": float(band["f0"]),
            "f_s21": 3.0e9 if wide else float(band["f0"]),
            "s21_gate": float(row["s21_min_db"]),
            "nf_gate": float(row["nf_max_db"]),
            "idd_cap_ma": float(row["idd_max_ma"]),
        })
    return specs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--quick", action="store_true",
                    help="reduced grids (plumbing smoke, NOT the audit)")
    ap.add_argument("--probe-vectors", action="store_true",
                    help="run one sp donoise deck, print available vectors, exit")
    ap.add_argument("--t2-mode", choices=["grid", "spnoise", "both"],
                    default="both")
    args = ap.parse_args()

    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    raw = out / "raw"
    t0 = time.time()

    # ---- fence (a): check_pdk_live smoke repro --------------------------------
    log = run_deck(deck_smoke(), raw, "fence_smoke")
    m = re.search(r"^id\s*=\s*([-+0-9.eE]+)", log, re.M)
    g = re.search(r"gainlf\s*=\s*([-+0-9.eE]+)", log)
    smoke_id = float(m.group(1)) if m else None
    smoke_gain = float(g.group(1)) if g else None
    if not (smoke_id and smoke_id > 1e-9 and smoke_gain is not None
            and smoke_gain > 0.0):
        (out / "FENCE-FAIL").write_text(
            f"smoke repro failed: id={smoke_id} gainlf={smoke_gain}\n")
        print(f"FENCE-FAIL smoke: id={smoke_id} gainlf={smoke_gain}")
        return 2
    print(f"[fence a] smoke OK id={smoke_id:.4e} gainlf={smoke_gain:.2f} dB")

    if args.probe_vectors:
        log = run_deck(deck_sp(0.8, 1.65, tag="probe", donoise=1), raw, "probe")
        print("---- vectors visible after sp donoise=1 ----")
        for ln in log.splitlines():
            print(ln)
        return 0

    vgs_grid = VGS_GRID[::3] if args.quick else VGS_GRID
    vds_grid = (1.65,) if args.quick else VDS_GRID
    vgs_t2 = VGS_T2[::3] if args.quick else VGS_T2
    rs_grid = RS_GRID[::3] if args.quick else RS_GRID
    lg_grid = LG_GRID[::3] if args.quick else LG_GRID

    # ---- T1 sweep -------------------------------------------------------------
    t1 = []  # rows: vgs, vds, id, J, figures dict
    for vds in vds_grid:
        for vgs in vgs_grid:
            tag = f"t1_vg{vgs:g}_vd{vds:g}"
            log = run_deck(deck_sp(vgs, vds, tag=tag, donoise=0), raw, tag)
            idv = parse_id(log)
            d = read_wrdata(raw / f"{tag}_sp.csv")
            if idv is None or d is None or idv <= 0:
                continue
            fig = s_to_figures(d)
            t1.append({"vgs": vgs, "vds": vds, "id_a": idv,
                       "j_ma_um": idv * 1e3 / (W_REF * 1e6), "fig": fig})
            print(f"[t1] vgs={vgs:g} vds={vds:g} id={idv*1e3:.3f} mA "
                  f"ft={unity_crossing(fig['f'], fig['h21']) or 0:.3e} "
                  f"MSG@2.442G={interp_at(fig['f'], fig['MSG'], 2.442e9):.1f}")
            sys.stdout.flush()
    if not t1:
        (out / "FENCE-FAIL").write_text("T1 sweep produced no valid rows\n")
        return 2

    # ---- fence (b): W-invariance spot-check at W=60um -------------------------
    inv_fail = []
    mid_rows = sorted((r for r in t1 if abs(r["vds"] - 1.65) < 1e-9),
                      key=lambda r: r["id_a"])
    for ref in (mid_rows[len(mid_rows) // 3], mid_rows[2 * len(mid_rows) // 3]):
        vgs = ref["vgs"]
        tag = f"inv_w60_vg{vgs:g}"
        log = run_deck(deck_sp(vgs, 1.65, w=60e-6, nfing=30, tag=tag,
                               donoise=0), raw, tag)
        idv = parse_id(log)
        d = read_wrdata(raw / f"{tag}_sp.csv")
        if idv is None or d is None:
            inv_fail.append(f"{tag}: missing data")
            continue
        figw = s_to_figures(d)
        j_ratio = (idv / 60e-6) / (ref["id_a"] / W_REF)
        msg_ref = interp_at(ref["fig"]["f"], ref["fig"]["MSG"], 2.442e9)
        msg_w = interp_at(figw["f"], figw["MSG"], 2.442e9)
        d_db = abs(10 * math.log10(max(msg_w, 1e-9) / max(msg_ref, 1e-9)))
        if abs(j_ratio - 1) > 0.10 or d_db > 0.5:
            inv_fail.append(f"{tag}: J-ratio={j_ratio:.3f} dMSG={d_db:.2f} dB")
        print(f"[fence b] {tag}: J-ratio={j_ratio:.3f} dMSG={d_db:.3f} dB")
    if inv_fail:
        (out / "FENCE-FAIL").write_text("W-invariance: " +
                                        "; ".join(inv_fail) + "\n")
        print("FENCE-FAIL invariance:", inv_fail)
        return 2

    # ---- T2 spnoise (sp donoise NFmin vectors, if supported) ------------------
    t2sp = []  # rows: vgs, id, J, f array, nfmin/nf50 arrays (dB)
    if args.t2_mode in ("spnoise", "both"):
        for vgs in vgs_grid:  # amendment: full T1 Vgs grid at Vds=1.65
            tag = f"t2p_vg{vgs:g}"
            log = run_deck(deck_sp_noisevec(vgs, 1.65, tag), raw, tag)
            idv = parse_id(log)
            d = read_wrdata(raw / f"{tag}_nfv.csv")
            if idv is None or d is None or "nfminr" not in d or idv <= 0:
                continue
            t2sp.append({"vgs": vgs, "id_a": idv,
                         "j_ma_um": idv * 1e3 / (W_REF * 1e6),
                         "f": d["frequency"], "nfmin_db": d["nfminr"],
                         "nf50_db": d["nfr"]})
            print(f"[t2p] vgs={vgs:g} id={idv*1e3:.3f} mA "
                  f"NFmin@2.442G={interp_at(d['frequency'], d['nfminr'], 2.442e9):.2f} dB "
                  f"NF50={interp_at(d['frequency'], d['nfr'], 2.442e9):.2f} dB")
            sys.stdout.flush()

    # ---- T2 grid (frozen pre-reg method) --------------------------------------
    t2g = []  # rows: vgs, id, J, rs, lg, f array, nf array (dB)
    if args.t2_mode in ("grid", "both"):
        n_g = len(vgs_grid)
        biases = vgs_t2 if args.t2_mode == "grid" else [
            vgs_grid[n_g // 4], vgs_grid[n_g // 2], vgs_grid[3 * n_g // 4]]
        rs_g = rs_grid if args.t2_mode == "grid" else sorted(
            set([50] + rs_grid[::2]))  # 50 ohm needed for NF50 cross-check
        lg_g = lg_grid if args.t2_mode == "grid" else lg_grid[::2]
        n = 0
        for vgs in biases:
            for rs in rs_g:
                for lg in lg_g:
                    tag = f"t2g_vg{vgs:g}_rs{rs:g}_lg{lg*1e9:g}"
                    log = run_deck(deck_noise(vgs, rs, lg, tag), raw, tag)
                    idv = parse_id(log)
                    d = read_wrdata(raw / f"{tag}_nz.csv")
                    if idv is None or d is None:
                        continue
                    inr = d["inr"]
                    nf_db = 10 * np.log10(np.maximum(
                        inr * inr / (K4T * rs), 1e-30))
                    t2g.append({"vgs": vgs, "id_a": idv,
                                "j_ma_um": idv * 1e3 / (W_REF * 1e6),
                                "rs": rs, "lg": lg,
                                "f": d["frequency"], "nf_db": nf_db})
                    n += 1
                    if n % 50 == 0:
                        print(f"[t2g] {n} decks done"); sys.stdout.flush()

    # ---- amendment cross-check fences (t2 grid vs sp-donoise) -----------------
    if args.t2_mode == "both" and t2sp and t2g:
        probs = []
        for gr in t2g:
            spr = min(t2sp, key=lambda r: abs(r["vgs"] - gr["vgs"]))
            if abs(spr["vgs"] - gr["vgs"]) > 1e-9:
                continue
            if gr["rs"] == 50 and gr["lg"] == 0:
                d50 = abs(interp_at(gr["f"], gr["nf_db"], 2.442e9)
                          - interp_at(spr["f"], spr["nf50_db"], 2.442e9))
                print(f"[fence c] NF50 vgs={gr['vgs']:g}: delta={d50:.3f} dB")
                if d50 > 0.75:
                    probs.append(f"NF50 vgs={gr['vgs']:g} delta={d50:.2f}")
        for vgs in sorted({gr["vgs"] for gr in t2g}):
            spr = min(t2sp, key=lambda r: abs(r["vgs"] - vgs))
            if abs(spr["vgs"] - vgs) > 1e-9:
                continue
            gmin = min(interp_at(gr["f"], gr["nf_db"], 2.442e9)
                       for gr in t2g if gr["vgs"] == vgs)
            smin = interp_at(spr["f"], spr["nfmin_db"], 2.442e9)
            print(f"[fence c] bound vgs={vgs:g}: grid-min={gmin:.2f} "
                  f"sp-NFmin={smin:.2f} dB")
            if gmin < smin - 0.25:
                probs.append(f"bound vgs={vgs:g} grid={gmin:.2f}<sp={smin:.2f}")
        if probs:
            (out / "FENCE-FAIL").write_text("t2 cross-check: " +
                                            "; ".join(probs) + "\n")
            print("FENCE-FAIL t2 cross-check:", probs)
            return 2

    # ---- classification -------------------------------------------------------
    specs = load_ladder()
    rows, md = [], []
    fence_fail = []
    for sp in specs:
        cap_a = sp["idd_cap_ma"] * 1e-3
        # gain ceiling over stage splits
        best = {"cum_gain_db": -1e9}
        for k in STAGES:
            id_k = cap_a / k
            j_min = id_k * 1e3 / (W_BOX[1] * 1e6)  # mA/um floor from W box
            for r in t1:
                if r["j_ma_um"] < j_min:
                    continue
                msg = interp_at(r["fig"]["f"], r["fig"]["MSG"], sp["f_s21"])
                msg_db = 10 * math.log10(max(msg, 1e-9))  # MSG is a power ratio
                cum = k * msg_db
                if cum > best["cum_gain_db"]:
                    best = {"cum_gain_db": cum, "k": k, "vgs": r["vgs"],
                            "vds": r["vds"], "j_ma_um": r["j_ma_um"],
                            "stage_msg_db": msg_db,
                            "ft_ghz": (unity_crossing(r["fig"]["f"],
                                                      r["fig"]["h21"]) or 0) / 1e9,
                            "fmax_ghz": None,
                            "fmax_note": "undefined under rgateMod=0 "
                            "(Re[Y11]~0, Mason U numerically degenerate)"}
        # noise floor (primary = spnoise if available, else grid)
        nfmin_sp = min((interp_at(r["f"], r["nfmin_db"], sp["f0"])
                        for r in t2sp), default=None)
        nfmin_grid = min((interp_at(r["f"], r["nf_db"], sp["f0"])
                          for r in t2g), default=None)
        # advisory floor: grid (realizable matching) preferred over sp (~0 dB)
        nfmin = nfmin_grid if nfmin_grid is not None else nfmin_sp
        gain_margin = best["cum_gain_db"] - sp["s21_gate"]
        nf_margin = (sp["nf_gate"] - nfmin) if nfmin is not None else None
        # AMENDMENT 2: noise axis advisory only (tnoiMod=0/rgateMod=0 -> model
        # NFmin ~ 0 dB by construction; nf cannot bind at device level).
        gain_inf = gain_margin < 0
        if gain_inf:
            cls = "DEVICE-INFEASIBLE"
        elif gain_margin <= GAIN_BORDER_DB:
            cls = "BORDERLINE"
        else:
            cls = "TOPOLOGY-GAP"
        if sp["spec"] in SOLVED_FENCE and cls == "DEVICE-INFEASIBLE":
            fence_fail.append(sp["spec"])
        row = {**sp, "gain_best": best, "gain_margin_db": round(gain_margin, 2),
               "nfmin_sp_db": None if nfmin_sp is None else round(nfmin_sp, 3),
               "nf_floor_grid_adv_db": None if nfmin_grid is None
               else round(nfmin_grid, 3),
               "nf_margin_adv_db": None if nf_margin is None
               else round(nf_margin, 3),
               "nf_axis": "advisory only: model-non-binding "
               "(tnoiMod=0, rgateMod=0 => NFmin~0 dB by construction)",
               "class": cls, "ts": time.time()}
        rows.append(row)
        md.append(f"| {sp['spec']} | {sp['band']} | {sp['s21_gate']:g} | "
                  f"{best['cum_gain_db']:.1f} (k={best.get('k','-')}) | "
                  f"{sp['nf_gate']:g} | "
                  f"{'-' if nfmin is None else f'{nfmin:.2f}'} | "
                  f"{sp['idd_cap_ma']:g} | {cls} |")

    with open(out / "results.jsonl", "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=float) + "\n")
        fh.flush(); os.fsync(fh.fileno())

    hdr = ("# gf180-physaudit-v0 results\n\n"
           f"era-audit-df7d9052 · box · {time.strftime('%Y-%m-%d')} · "
           f"T1 rows {len(t1)} · T2 spnoise rows {len(t2sp)} · "
           f"T2 grid rows {len(t2g)} · wall {(time.time()-t0)/60:.1f} min\n\n")
    if fence_fail:
        (out / "FENCE-FAIL").write_text(
            "solved-cell fence: " + ", ".join(fence_fail) +
            " classified DEVICE-INFEASIBLE\n")
        (out / "results.md").write_text(
            hdr + "**VALIDATION FENCE FAILED** — classifications withheld "
            f"per pre-reg (cells: {', '.join(fence_fail)}). See results.jsonl "
            "raw figures only.\n")
        print("FENCE-FAIL solved-cell:", fence_fail)
        return 2
    (out / "results.md").write_text(
        hdr + "NF axis ADVISORY per Amendment 2 (tnoiMod=0/rgateMod=0: model "
        "NFmin~0 dB by construction; class rests on the gain axis).\n\n"
        "| spec | band | s21 gate | gain ceiling dB (stages) | nf gate | "
        "nf floor adv dB | Idd cap mA | class |\n|---|---|---|---|---|---|---|---|\n"
        + "\n".join(md) + "\n")
    counts = {}
    for r in rows:
        counts[r["class"]] = counts.get(r["class"], 0) + 1
    print("classes:", counts, f"wall={(time.time()-t0)/60:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
