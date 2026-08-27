"""Live PDK smoke: each fetched foundry PDK renders a trivial single-NMOS
common-source amp through its adapter, runs ngspice op + ac, and asserts

  (a) the device CONDUCTS (a real DC drain current flows), and
  (b) the stage has GAIN (|Av| > 0 dB at low frequency), and
  (c) ngspice reported NO model-loading error (stderr/log scanned verbatim for
      'unknown model', 'could not find', 'unable to find', 'osdi' errors).

For IHP it additionally instantiates the SiGe HBT (npn13G2, native VBIC) and
asserts it conducts.

Every smoke SKIPS-WITH-NOTE (not a failure) when the PDK is not fetched on this
host -- so a clone with no `.env/pdks/` stays green. Measured numbers are
printed. This is the LIVE counterpart to check_pdk.py's static wiring golden.

    python lna/ref/check_pdk_live.py      # exit 0 iff GREEN (fetched smokes pass)

WHY A SEPARATE HARNESS (not to_spice + extract): the OSDI load order for IHP
(the psp103 .osdi must be loaded via the `osdi` command in a .control block
BEFORE the netlist is parsed, else the psp103va/pspnqs103va model types are
unknown when the .model cards are read) is a driver concern this file owns. The
sky130/gf180 smokes need no OSDI but use the same tiny driver for symmetry.
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.dirname(HERE)
sys.path.insert(0, LNA)

import pdk                                # noqa: E402

NGSPICE = os.environ.get("NGSPICE", "ngspice")

# ngspice log substrings that mean a model/device did NOT load -- any of these
# in the output is a hard fail even if a number came out.
_MODEL_ERRORS = ("unknown model", "could not find", "unable to find",
                 "no such model", "specify .model")


def _run(deck, workdir):
    """Write `deck` to workdir/run.sp, run ngspice -b, return (stdout+stderr)."""
    p = os.path.join(workdir, "run.sp")
    with open(p, "w") as fh:
        fh.write(deck)
    try:
        r = subprocess.run([NGSPICE, "-b", p], capture_output=True, text=True,
                           timeout=120, cwd=workdir)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return f"__RUN_ERROR__ {e}"
    return (r.stdout or "") + (r.stderr or "")


def _num(log, key):
    """First float printed as `<key> = <num>` (ngspice print / meas)."""
    m = re.search(rf"{re.escape(key)}\s*=\s*([-\d.eE+]+)", log)
    return float(m.group(1)) if m else None


def _model_error(log):
    low = log.lower()
    return next((s for s in _MODEL_ERRORS if s in low), None)


def _cs_amp_deck(pdk_name, vdd, vg, rd, subckt, wl, extra_inc_lines, osdi_lines):
    """A common-source NMOS amp: Vdd-Rd-drain, gate at vg with 1 V ac. Emits the
    adapter's own include lines (extra_inc_lines) and, for OSDI PDKs, an `osdi`
    load + `source` split so the model types register before the netlist parses.

    `wl` is the ' w=.. l=.. <nf>' fragment (already unit-correct, in metres)."""
    net = [
        f"* {pdk_name} common-source NMOS smoke",
        *extra_inc_lines,
        f"Vdd vdd 0 {vdd}",
        f"Vin in 0 dc {vg} ac 1",
        f"Rd vdd d {rd}",
        f"XM1 d in 0 0 {subckt}{wl}",
        ".end",
    ]
    if osdi_lines:
        # OSDI: load in control, source the netlist, then analyse.
        with_net = "\n".join(net)
        ctrl = ["* driver", ".control", *osdi_lines,
                "source net.sp", "op", "print v(d)",
                f"let id = ({vdd} - v(d))/{rd}", "print id",
                "ac dec 10 1e3 1e9", "let gdb = db(v(d))",
                "meas ac gainlf find gdb at=1e3", ".endc", ".end"]
        return with_net, "\n".join(ctrl)
    # no OSDI: single deck with an inline control block.
    deck = net[:-1] + [
        ".control", "op", "print v(d)",
        f"let id = ({vdd} - v(d))/{rd}", "print id",
        "ac dec 10 1e3 1e9", "let gdb = db(v(d))",
        "meas ac gainlf find gdb at=1e3", ".endc", ".end",
    ]
    return "\n".join(deck), None


def _smoke_mos(name, vdd, vg, rd, wl):
    ad = pdk.get_pdk(name)
    if pdk.pdk_root(name) is None:
        print(f"  [{name}] MOS: not fetched (.env/pdks/{name} absent) -- "
              f"SKIP (not a failure)")
        return None  # skip
    incs = ad.model_includes()
    osdi = ad.osdi_files() if hasattr(ad, "osdi_files") else []
    subckt = ad.MOS_SUBCKT["NM"]
    with tempfile.TemporaryDirectory(prefix=f"pdksmoke_{name}_") as wd:
        if osdi:
            netbody, driver = _cs_amp_deck(name, vdd, vg, rd, subckt, wl, incs,
                                           [f"osdi {p}" for p in osdi])
            with open(os.path.join(wd, "net.sp"), "w") as fh:
                fh.write(netbody)
            log = _run(driver, wd)
        else:
            deck, _ = _cs_amp_deck(name, vdd, vg, rd, subckt, wl, incs, [])
            log = _run(deck, wd)
    if log.startswith("__RUN_ERROR__"):
        print(f"  [{name}] MOS: ngspice failed: {log}")
        return False
    vd = _num(log, "v(d)")
    idc = _num(log, "id")
    gain = _num(log, "gainlf")
    merr = _model_error(log)
    conducts = idc is not None and idc > 1e-9
    has_gain = gain is not None and gain > 0.0
    ok = conducts and has_gain and merr is None
    idma = idc * 1e3 if idc is not None else float("nan")
    print(f"  [{name}] MOS {subckt}: V(d)={vd:.3f} V  Id={idma:.3f} mA  "
          f"|Av|@LF={gain:.2f} dB   conducts:{conducts} gain>0dB:{has_gain} "
          f"model-err:{merr or 'none'}   [{'ok' if ok else 'FAIL'}]")
    return ok


def _smoke_hbt():
    """IHP SiGe HBT npn13G2 -- native ngspice VBIC (no OSDI). Common-emitter,
    assert collector current flows."""
    name = "ihp_sg13g2"
    ad = pdk.get_pdk(name)
    root = pdk.pdk_root(name)
    if root is None:
        print(f"  [{name}] HBT: not fetched -- SKIP")
        return None
    hbt = os.path.join(root, ad.MODELS_REL, ad.HBT_CORNER).replace(os.sep, "/")
    deck = "\n".join([
        "* IHP npn13G2 SiGe HBT smoke (native VBIC, no OSDI)",
        f'.lib "{hbt}" {ad.HBT_SECTION}',
        "Vcc vcc 0 2.0", "Vb b 0 0.85", "Rc vcc c 2k",
        "X1 c b 0 0 npn13G2",
        ".control", "op", "print v(c)", "let ic = (2.0 - v(c))/2k",
        "print ic", ".endc", ".end",
    ])
    with tempfile.TemporaryDirectory(prefix="pdksmoke_hbt_") as wd:
        log = _run(deck, wd)
    vc = _num(log, "v(c)")
    ic = _num(log, "ic")
    merr = _model_error(log)
    conducts = ic is not None and ic > 1e-9
    ok = conducts and merr is None
    icma = ic * 1e3 if ic is not None else float("nan")
    print(f"  [{name}] HBT npn13G2: V(c)={vc:.3f} V  Ic={icma:.3f} mA   "
          f"conducts:{conducts} model-err:{merr or 'none'}   "
          f"[{'ok' if ok else 'FAIL'}]")
    return ok


def main():
    print("live PDK smokes (skip-with-note when a PDK is not fetched):")
    results = []
    # (name, vdd, vg, rd, ' w=.. l=.. <nf>' in METRES)
    results.append(_smoke_mos("sky130", 1.8, 0.9, "5k",
                              " w=5e-6 l=0.15e-6 nf=1"))
    results.append(_smoke_mos("gf180mcu", 3.3, 1.2, "5k",
                              " w=10e-6 l=0.28e-6 nf=1"))
    results.append(_smoke_mos("ihp_sg13g2", 1.5, 0.55, "10k",
                              " w=10e-6 l=0.13e-6 ng=4"))
    results.append(_smoke_hbt())
    ran = [r for r in results if r is not None]
    ok = all(ran) if ran else True
    n_pass = sum(1 for r in ran if r)
    print(f"check_pdk_live: {'GREEN' if ok else 'RED'} "
          f"({n_pass}/{len(ran)} fetched smoke(s) passed, "
          f"{len(results) - len(ran)} skipped)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
