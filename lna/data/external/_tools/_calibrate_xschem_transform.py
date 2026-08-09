"""One-off: determine xschem's placement rotation/flip transform empirically
by testing candidate formulas against a schematic whose correct netlist is
already known (the GPS_LNA nmos testbench). Not part of the shipped
flattener; used once to pick the right transform, then hardcoded there.
"""
import re
import os
from collections import defaultdict

SYM_DIR = r"C:\Users\Devavrat\AppData\Local\Temp\xschem_syms"
SCH = r"C:\Users\Devavrat\AppData\Local\Temp\xschem_test\top.sch"

# device name (as it appears in the .sch) -> (real symbol pin name -> net)
# from the known-good lna_tb_xyce_rf_rfmos.spice, using each symbol's REAL
# pin names/order (confirmed by reading the .sym files directly, not guessed):
#   rppd/rsil: P, M (sim_pinnumber 1,2)      cap_rfcmim: c0, c1, bn(body, skip)
#   ind: p, m (lowercase, pinnumber 1,2)     transistor: D, G, S, B
GROUNDTRUTH = {
    "R2": {"P": "net3", "M": "net1"},
    "R1": {"P": "net1", "M": "VDD"},
    "R3": {"P": "net2", "M": "vin"},
    "L1": {"p": "VDD", "m": "vout"},
    "L2": {"p": "net6", "m": "GND"},
    "L3": {"p": "net3", "m": "net5"},
    "C1": {"c0": "net2", "c1": "net3"},
    "C2": {"c0": "net2", "c1": "net3"},
    "M3": {"D": "net1", "G": "net1", "S": "GND", "B": "GND"},
    "M2": {"D": "vout", "G": "VDD", "S": "net4", "B": "GND"},
    "M1": {"D": "net4", "G": "net5", "S": "net6", "B": "GND"},
}


def parse_sym(path):
    pins = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("B 5"):
                m = re.match(r"B 5 ([\d.-]+) ([\d.-]+) ([\d.-]+) ([\d.-]+) \{(.*)\}", line.strip())
                if not m:
                    continue
                x1, y1, x2, y2, attrs = m.groups()
                x1, y1, x2, y2 = map(float, (x1, y1, x2, y2))
                name_m = re.search(r"name=(\S+)", attrs)
                if name_m:
                    pins.append((name_m.group(1), (x1 + x2) / 2, (y1 + y2) / 2))
    return pins


def parse_sch(path):
    wires = []
    comps = []
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    for m in re.finditer(r"^N ([\d.-]+) ([\d.-]+) ([\d.-]+) ([\d.-]+) \{(.*?)\}$", text, re.M):
        x1, y1, x2, y2, attrs = m.groups()
        lab_m = re.search(r"lab=(\S+)", attrs)
        wires.append((float(x1), float(y1), float(x2), float(y2), lab_m.group(1) if lab_m else None))
    for m in re.finditer(r"^C \{([^}]*)\} ([\d.-]+) ([\d.-]+) (\d+) (\d+) \{", text, re.M):
        sym, x, y, rot, flip = m.groups()
        start = m.end() - 1
        depth, i = 0, m.end() - 1
        while i < len(text):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        props = text[start:i + 1]
        name_m = re.search(r"name=(\S+)", props)
        comps.append((sym, float(x), float(y), int(rot), int(flip), name_m.group(1) if name_m else None))
    return wires, comps


def transform(x, y, rot, flip):
    if flip:
        return [(-x, y), (-y, -x), (x, -y), (y, x)][rot]
    else:
        return [(x, y), (-y, x), (-x, -y), (y, -x)][rot]


def main():
    wires, comps = parse_sch(SCH)
    sym_cache = {}
    mine = {}
    for sym, x, y, rot, flip, name in comps:
        if name not in GROUNDTRUTH:
            continue
        sym_file = sym.split("/")[-1]
        if sym_file not in sym_cache:
            path = os.path.join(SYM_DIR, sym_file)
            sym_cache[sym_file] = parse_sym(path) if os.path.exists(path) else []
        for pin_name, lx, ly in sym_cache[sym_file]:
            if pin_name not in GROUNDTRUTH[name]:
                continue
            tx, ty = transform(lx, ly, rot, flip)
            ax, ay = x + tx, y + ty
            found = [lab for (x1, y1, x2, y2, lab) in wires
                     if (abs(x1 - ax) < 1e-6 and abs(y1 - ay) < 1e-6) or
                        (abs(x2 - ax) < 1e-6 and abs(y2 - ay) < 1e-6)]
            mine[(name, pin_name)] = found[0] if found else f"NOMATCH@({ax},{ay})"

    gt_groups = defaultdict(set)
    for dev, pins in GROUNDTRUTH.items():
        for pin, net in pins.items():
            gt_groups[net].add((dev, pin))
    my_groups = defaultdict(set)
    for key, lab in mine.items():
        my_groups[lab].add(key)

    gt_partition = sorted([frozenset(g) for g in gt_groups.values()], key=lambda s: sorted(map(str, s)))
    my_partition = sorted([frozenset(g) for g in my_groups.values()], key=lambda s: sorted(map(str, s)))

    print(f"total pins checked: {len(mine)}")
    print(f"groundtruth partition ({len(gt_partition)} groups):")
    for g in gt_partition:
        print("  ", sorted(g))
    print(f"mine partition ({len(my_partition)} groups):")
    for g in my_partition:
        print("  ", sorted(g))
    print("MATCH:", gt_partition == my_partition)


if __name__ == "__main__":
    main()
