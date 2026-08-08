import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import templates as T
from novelty import corpus_reference
rows = [{"name": a["name"], "wl": a["wl"], "cls": a["cls"]} for a in T.archetypes()]
ch, _ = corpus_reference()
json.dump({"archetypes": rows, "corpus_hashes": sorted(ch)},
          open("lna/out/_trackb_ref_hashes.json", "w"))
print("archetypes", len(rows), "corpus hashes", len(ch))
