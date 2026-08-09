"""One-shot purge of the stale ngspice scratch dirs in %TEMP% (FINDINGS §17).

Pattern-fenced: only `<prefix><8 alnum>` directories minted by this tree's
`tempfile.mkdtemp` calls, and only those older than --min-age-min so a
concurrently-running sim in another agent's process is never touched.
"""
import os
import re
import sys
import tempfile
import time

PREFIXES = ("size_", "nf_", "nfself_", "stab_", "bias_", "tmpl_", "lna_yield_")
PAT = re.compile("^(?:" + "|".join(re.escape(p) for p in PREFIXES) +
                 r")[A-Za-z0-9_]{8}$")


def main():
    root = tempfile.gettempdir()
    min_age = float(sys.argv[sys.argv.index("--min-age-min") + 1]) * 60 \
        if "--min-age-min" in sys.argv else 60.0
    dry = "--dry-run" in sys.argv
    cutoff = time.time() - min_age
    t0 = time.time()
    seen = matched = skipped_young = removed = failed = 0
    for e in os.scandir(root):
        seen += 1
        if not PAT.match(e.name):
            continue
        try:
            if not e.is_dir(follow_symlinks=False):
                continue
            if e.stat(follow_symlinks=False).st_mtime > cutoff:
                skipped_young += 1
                continue
        except OSError:
            failed += 1
            continue
        matched += 1
        if dry:
            continue
        d = e.path
        try:
            for f in os.scandir(d):
                try:
                    os.unlink(f.path)
                except OSError:
                    pass
            os.rmdir(d)
            removed += 1
        except OSError:
            failed += 1
        if removed % 20000 == 0 and removed:
            print(f"  {removed} removed, {time.time()-t0:.0f}s", flush=True)
    print(f"root={root} seen={seen} matched={matched} "
          f"skipped_young={skipped_young} removed={removed} failed={failed} "
          f"elapsed={time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
