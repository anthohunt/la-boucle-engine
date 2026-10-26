"""Command line: python3 -m boucle <command> …

  sceller <bench.jsonl>        seal a bench (fingerprint in <bench>.sceau)
  verifier <chantier.json>     check the chantier file and that both benches match their seals
  noter <chantier.json> <harnais> [--examen]   mark one harness (the exam prints aggregates only)
  run <chantier.json>          run (or resume) the loop; exit 0 goal, 3 pause, 4 stopped
  tableau <chantier.json>      write tableau.html next to the chantier file
"""

import argparse
import json
import os
import sys

from . import banc, bareme, chantier as chantier_mod, tableau
from .juge import Juge
from .moteur import Moteur


def main(argv=None):
    p = argparse.ArgumentParser(prog="python3 -m boucle", description="La boucle: a researcher agent improves a harness, a sealed exam decides.")
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("sceller"); s.add_argument("banc")
    v = sp.add_parser("verifier"); v.add_argument("chantier")
    n = sp.add_parser("noter"); n.add_argument("chantier"); n.add_argument("harnais"); n.add_argument("--examen", action="store_true")
    r = sp.add_parser("run"); r.add_argument("chantier")
    t = sp.add_parser("tableau"); t.add_argument("chantier")
    a = p.parse_args(argv)
    try:
        if a.cmd == "sceller":
            print(json.dumps(banc.sceller(a.banc), indent=2, ensure_ascii=False))
            return 0
        c = chantier_mod.charger(a.chantier)
        if a.cmd == "verifier":
            for cle in ("entrainement", "examen"):
                cas = banc.verifier(chantier_mod.chemin(c, c["banc"][cle]))
                print(f"{cle}: {len(cas)} cases, seal OK")
            print("chantier OK")
            return 0
        if a.cmd == "noter":
            j = Juge(c)
            if a.examen:
                rapport, _ = j.noter_examen(a.harnais)
                rapport = {k: rapport[k] for k in ("note", "nombre", "interdites")} | {"par_critere": {k: round(x["taux"] * 100, 1) for k, x in rapport["par_critere"].items()}}
            else:
                _, rapport = j.noter_entrainement(a.harnais)
            print(json.dumps(rapport, indent=2, ensure_ascii=False))
            return 0
        if a.cmd == "run":
            return Moteur(c).run()
        if a.cmd == "tableau":
            print(tableau.ecrire(c["racine"]))
            return 0
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
