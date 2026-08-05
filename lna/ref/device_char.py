"""Device characterization sweep for the 45nm BPTM NMOS (WP-REF, 02-REF §2.1).

Every later reference-LNA decision reads this table instead of guessing. For a
grid of widths and Vgs it extracts the small-signal parameters an RF designer
needs: Id, gm, gmb, Cgs, Cgd, and fT = gm / (2*pi*(Cgs+Cgd)).

Two model quirks handled: BSIM4 reports the small-signal capacitances with a
negative sign (WORKLOG F1.3) -- magnitudes are used; and ngspice needs the
device parameters `save`d before the analysis runs (X3).

    python lna/ref/device_char.py                 # writes device_tables.csv (+ .png)
    python lna/ref/device_char.py --vds 0.6 --plot

Bias point for the sweep: drain held at --vds (default 0.6 V, mid-saturation),
source and bulk grounded, so Vgs is the swept variable and Vsb = 0.
"""
import argparse
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.abspath(os.path.join(
    HERE, "..", "..", "AutoCkt", "repo", "eval_engines", "ngspice",
    "ngspice_inputs", "spice_models", "45nm_bulk.txt"))
NGSPICE = os.environ.get("NGSPICE", r"C:\msys64\ucrt64\bin\ngspice_con.exe")

TWO_PI = 6.283185307179586
WIDTHS_UM = [10, 20, 40, 80, 160]


def _win(path):
    """ngspice_con is a Windows binary: give it forward-slash Windows paths."""
    return os.path.abspath(path).replace(os.sep, "/")


def sweep_width(w_um, vds, vgs_lo, vgs_hi, step, workdir):
    out = os.path.join(workdir, f"dev_W{w_um}.txt")
    deck = f"""* device characterization, W={w_um}um
.include {_win(MODELS)}
M1 d g 0 0 nmos W={w_um}u L=45n
Vd d 0 {vds}
Vg g 0 0.5
.control
save @m1[id] @m1[gm] @m1[gmbs] @m1[cgs] @m1[cgd]
dc Vg {vgs_lo} {vgs_hi} {step}
let id=@m1[id]
let gm=@m1[gm]
let gmbs=@m1[gmbs]
let cgs=@m1[cgs]
let cgd=@m1[cgd]
wrdata {_win(out)} id gm gmbs cgs cgd
.endc
.end
"""
    deck_path = os.path.join(workdir, f"dev_W{w_um}.cir")
    open(deck_path, "w").write(deck)
    subprocess.run([NGSPICE, "-b", deck_path], capture_output=True,
                   text=True, timeout=60)
    rows = []
    with open(out) as fh:
        for line in fh:
            c = line.split()
            if len(c) < 10:
                continue
            vgs = float(c[0])
            idd, gm, gmbs = float(c[1]), float(c[3]), float(c[5])
            cgs, cgd = abs(float(c[7])), abs(float(c[9]))
            ft = gm / (TWO_PI * (cgs + cgd)) if (cgs + cgd) > 0 else 0.0
            rows.append((w_um, vds, vgs, idd, gm, abs(gmbs), cgs, cgd, ft))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vds", type=float, default=0.6)
    ap.add_argument("--vgs-lo", type=float, default=0.2)
    ap.add_argument("--vgs-hi", type=float, default=0.9)
    ap.add_argument("--step", type=float, default=0.025)
    ap.add_argument("--out", default=os.path.join(HERE, "device_tables.csv"))
    ap.add_argument("--plot", action="store_true")
    args = ap.parse_args()

    workdir = tempfile.mkdtemp(prefix="devchar_")
    all_rows = []
    for w in WIDTHS_UM:
        all_rows.extend(sweep_width(w, args.vds, args.vgs_lo, args.vgs_hi,
                                    args.step, workdir))

    header = ["W_um", "Vds_V", "Vgs_V", "Id_A", "gm_S", "gmb_S",
              "Cgs_F", "Cgd_F", "fT_Hz"]
    with open(args.out, "w", newline="") as fh:
        fh.write(",".join(header) + "\n")
        for r in all_rows:
            fh.write(f"{r[0]},{r[1]},{r[2]:.4f},{r[3]:.6e},{r[4]:.6e},"
                     f"{r[5]:.6e},{r[6]:.6e},{r[7]:.6e},{r[8]:.6e}\n")
    print(f"wrote {args.out}  ({len(all_rows)} points, {len(WIDTHS_UM)} widths)")

    # quick digest: at each width, the point nearest gm+gmb = 20 mS (the CG target)
    print(f"\n  width sweep @ Vds={args.vds} V -- point nearest gm+gmb = 20 mS:")
    print(f"  {'W(um)':>6} {'Vgs':>5} {'Id(mA)':>7} {'gm(mS)':>7} "
          f"{'gmb(mS)':>7} {'gm+gmb':>7} {'Cgs(fF)':>8} {'fT(GHz)':>8}")
    for w in WIDTHS_UM:
        rows = [r for r in all_rows if r[0] == w]
        best = min(rows, key=lambda r: abs((r[4] + r[5]) - 20e-3))
        print(f"  {w:>6} {best[2]:>5.3f} {best[3]*1e3:>7.2f} {best[4]*1e3:>7.2f} "
              f"{best[5]*1e3:>7.3f} {(best[4]+best[5])*1e3:>7.2f} "
              f"{best[6]*1e15:>8.1f} {best[8]/1e9:>8.0f}")

    if args.plot:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except Exception as e:  # noqa: BLE001
            print(f"  (plot skipped: {e})")
            return 0
        fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
        for w in WIDTHS_UM:
            rows = [r for r in all_rows if r[0] == w]
            idd = [r[3] * 1e3 for r in rows]
            gm = [r[4] * 1e3 for r in rows]
            ft = [r[8] / 1e9 for r in rows]
            ax[0].plot(idd, gm, marker=".", label=f"W={w}um")
            ax[1].plot(idd, ft, marker=".", label=f"W={w}um")
        ax[0].set(xlabel="Id (mA)", ylabel="gm (mS)", title="gm vs Id")
        ax[1].set(xlabel="Id (mA)", ylabel="fT (GHz)", title="fT vs Id")
        for a in ax:
            a.grid(True, alpha=0.3)
            a.legend(fontsize=8)
        png = os.path.splitext(args.out)[0] + ".png"
        fig.tight_layout()
        fig.savefig(png, dpi=110)
        print(f"  wrote {png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
