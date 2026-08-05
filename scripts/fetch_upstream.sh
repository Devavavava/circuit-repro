#!/usr/bin/env bash
# Re-create every upstream checkout at the commit pinned in UPSTREAM.md,
# then apply the local patches. Safe to re-run: existing clones are left alone
# unless --force is passed.
#
#   bash scripts/fetch_upstream.sh          # clone what is missing
#   bash scripts/fetch_upstream.sh --force  # delete and re-clone everything

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

# local_path <TAB> url <TAB> pinned sha
REPOS=$(cat <<'EOF'
AnalogGenie/repo	https://github.com/xz-group/AnalogGenie.git	efc25358939c6bedd247f28d3df61066964f3a90
AutoCkt/repo	https://github.com/ksettaluri6/AutoCkt.git	a6c8a61d3dffb8b433f19251e135994a5b0f6ee4
CktGNN/repo	https://github.com/zehao-dong/CktGNN.git	416cd035f79dd8cfcb60ac0a4792b43255adf0b7
Krylov-ICML2023/repo	https://github.com/indylab/Circuit-Synthesis.git	98a520ed7e595a72f7e34982134be727ee4dfa40
LaMAGIC2/repo	https://github.com/turtleben/LaMAGIC.git	0cde737684571b58a549f093a3ea3f9a55911433
extensions/AnalogSAGE	https://github.com/xz-group/AnalogSAGE.git	2c272f1d730e24759e005081336451abcb167f4f
extensions/CircuitSense	https://github.com/xz-group/CircuitSense.git	c125509f2a1876536893a349d29e4fca6cc4fca8
extensions/RoSE	https://github.com/xz-group/RoSE.git	50776688f9f0fd27f27fb8c7865c901c83e02bb4
extensions/ZeroSim	https://github.com/xz-group/ZeroSim.git	9af8a6976cf1aae9788eedcd882b7cc201ee95ef
misc/AnalogGenie-Lite	https://github.com/xz-group/AnalogGenie-Lite.git	7ecd75d76549849738a1d0d6128a9f7a3b463b5d
misc/AnalogToBi	https://github.com/Seungmin0825/AnalogToBi.git	e2033e9e5347dd0b702d24a8809de0c0f5470f87
misc/ZOAF	https://github.com/LiyanTan111/ZOAF.git	62615e91348691a225fd005bbf51ffd97d6e45f1
EOF
)

while IFS=$'\t' read -r path url sha; do
    [[ -z "$path" ]] && continue
    dest="$ROOT/$path"

    if [[ -d "$dest/.git" ]]; then
        if [[ $FORCE -eq 1 ]]; then
            echo "[re-clone] $path"
            rm -rf "$dest"
        else
            have=$(git -C "$dest" rev-parse HEAD)
            if [[ "$have" == "$sha" ]]; then
                echo "[ok]       $path @ ${sha:0:7}"
            else
                echo "[WRONG]    $path is at ${have:0:7}, expected ${sha:0:7} — re-run with --force"
            fi
            continue
        fi
    fi

    echo "[clone]    $path"
    mkdir -p "$(dirname "$dest")"
    git clone --quiet "$url" "$dest"
    git -C "$dest" checkout --quiet "$sha"
done <<< "$REPOS"

echo
echo "Applying patches..."

apply_patch() {
    local target="$1" patch="$2"
    if git -C "$ROOT/$target" apply --check "$patch" 2>/dev/null; then
        git -C "$ROOT/$target" apply "$patch"
        echo "[applied]  $(basename "$patch") -> $target"
    else
        echo "[skipped]  $(basename "$patch") — already applied or does not fit"
    fi
}

apply_patch "CktGNN/repo" "$ROOT/patches/cktgnn.patch"

# AutoCkt's netlist .include must point at this machine's checkout. Under Git Bash
# / MSYS, $ROOT is an MSYS path (/c/Users/...) that Windows ngspice cannot open, so
# convert it to a native C:/Users/... form. ngspice accepts forward slashes on both
# platforms, which is why the patch uses them throughout.
autockt_root="$ROOT/AutoCkt/repo"
if command -v cygpath >/dev/null 2>&1; then
    autockt_root="$(cygpath -m "$ROOT/AutoCkt/repo")"
fi

autockt_patch="$(mktemp)"
sed "s|@@AUTOCKT_ROOT@@|$autockt_root|g" "$ROOT/patches/autockt.patch" > "$autockt_patch"
apply_patch "AutoCkt/repo" "$autockt_patch"
rm -f "$autockt_patch"

echo
echo "Installing smoke scripts into the checkouts..."

# Several smoke tests must sit inside an upstream checkout to import it. They cannot
# be tracked at that path — git refuses to add files inside a nested repository — so
# they live under smoke/ mirroring their destination, and are copied into place here.
if [[ -d "$ROOT/smoke" ]]; then
    while IFS= read -r src; do
        rel="${src#"$ROOT/smoke/"}"
        mkdir -p "$(dirname "$ROOT/$rel")"
        cp "$src" "$ROOT/$rel"
        echo "[installed] $rel"
    done < <(find "$ROOT/smoke" -type f)
fi

echo
echo "Done. Large files are not fetched here — see 'Files not tracked' in README.md."
