# Incident: main-checkout sparse-checkout accident (2026-08-27)

**What happened.** During the PDK fetch (agent work, commit 002184fb), a
`git clone --no-checkout` of sky130_fd_pr failed (this host's git lacks the
remote-https helper), the follow-up `cd` into the clone therefore failed, and
`git sparse-checkout init --cone && git sparse-checkout set models cells` ran
with cwd inside `/home/dpatni/circuit-repro/.env/pdks/` -- git walked UP,
found the MAIN repository, and sparsified its working tree to ~1% (root files
+ .env/pdks/{cells,models}/ cone parents). Recovery: `git sparse-checkout
disable` restored every tracked file; goldens green; nothing tracked was lost.

**Untracked casualties in the main checkout** (git removes tracked files on
sparsify; the untracked vendor trees were separately damaged in the same
session): AnalogGenie/repo upstream files + Dataset + Pretrain.pth (public,
re-downloadable from HF/GitHub), lna/out/ft_p5v7_v2.pth (user holds the only
other copy), lna/data/{sim_points,op_points}.jsonl (gitignored byproduct
tables; box-era rows lost; the primary tracked tables topo_labels/l1_labels
are in git and safe), AutoCkt/misc-ZOAF upstream remainders (public).
`.env/` (conda, ngspice-47, kaggle auth, fetched PDKs, OpenVAF) survived.

**Standing rules from this incident (binding for every future session/agent):**
1. NEVER run `git sparse-checkout`, `git clean`, `git checkout <ref> -- .`,
   or any repo-reconfiguring git command in an agent task. If a fetch needs a
   sparse/partial clone, do it in `$CLAUDE_JOB_DIR/tmp` -- NEVER anywhere
   under the repo tree: gitignored is NOT outside-the-repo for git commands,
   which walk up to find a repository.
2. Scratch/staging directories for any fetch live outside the repo tree.
3. After any git command that failed or behaved unexpectedly in a fetch
   sequence, STOP and inspect `git status` at the repo root before continuing.
