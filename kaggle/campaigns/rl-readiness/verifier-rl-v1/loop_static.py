"""(c) static guard coverage of the R4 junk mutants (no simulation).
usage: loop_static.py <out.json>
For each mutant x its 2 test cells: the rl-v1-form spec's topology screen
(VERIFY_TOPO_LIMITS) and structural_degeneracy (VERIFY_STRUCT) evaluated
INDEPENDENTLY (smoke_run stops at the first, topo), plus the parent template's
own result (must pass both = no false positive)."""
import sys, os, json
REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
for p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop"):
    sys.path.insert(0, p)
import bench_anchor_prep as PREP                              # noqa: E402
import proposal as P                                          # noqa: E402
from topology import Topology                                 # noqa: E402
from spec import Spec                                         # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v1_drv as D                                            # noqa: E402


def main(outp):
    od = os.path.join(os.environ.get("TMPDIR", "/tmp"), "specs", str(os.getpid()))
    out = []
    names = ["template"] + ["net:" + n for n in json.load(open(D.R4 + "mutations.json"))]
    for band, cells in D.MUT_CELLS.items():
        for cell in cells:
            spec = Spec.load(PREP.rl_v1_spec(f"{D.LIB}/{cell}/spec.yaml", out_dir=od))
            for n in names:
                if n != "template" and not n[4:].startswith(band):
                    continue
                topo = Topology(list(D.tokens_for(cell, n)))
                tl = PREP.topo_limits(spec, topo)
                st = PREP.structural_degeneracy(topo)
                out.append({"cell": cell, "cand": n, "n_devices": topo.n_devices,
                            "n_inductors": topo.n_inductors,
                            "topo_failed": tl["failed"], "struct": st})
                print(cell, n, topo.n_devices, topo.n_inductors, tl["failed"], st)
    json.dump(out, open(outp, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
