"""Builds small throw-away chantiers for the tests (numbers: "big" if x >= threshold else "small")."""
import json
import os
import random
import textwrap

SUJET = textwrap.dedent('''
    import json, sys

    def un(d):
        h = json.load(open(d["harnais"] + "/regle.json"))
        x = d["entree"]["x"]
        if str(d["entree"]["id"]) in h.get("memo", {}):
            return {"e": h["memo"][str(d["entree"]["id"])]}
        return {"e": "big" if x >= h["seuil"] else "small"}

    if "--lot" in sys.argv:
        for ligne in sys.stdin:
            if ligne.strip():
                d = json.loads(ligne)
                print(json.dumps({"id": d["id"], "proposition": un(d)}))
    else:
        print(json.dumps(un(json.load(sys.stdin))))
''')

# Researcher: moves the threshold toward the true value 50 (honest), or memorizes training answers (overfits).
CHERCHEUR = textwrap.dedent('''
    import json, os
    mode = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mode.txt")).read().strip()
    sortie = os.environ["BOUCLE_SORTIE"]
    fautes = json.load(open(os.environ["BOUCLE_FAUTES"]))
    p = sortie + "/regle.json"
    h = json.load(open(p))
    if mode == "honnete":
        h["seuil"] = h["seuil"] + (10 if h["seuil"] < 50 else -10)
        idee = "move threshold"
    elif mode == "memorise":
        h.setdefault("memo", {})
        for f in fautes:
            h["memo"][str(f["entree"]["id"])] = f["corrige"]["e"]
        idee = "memorize"
    elif mode == "rien":
        idee = "nothing"
    json.dump(h, open(p, "w"))
    json.dump({"famille": mode, "idee": idee}, open(sortie + "/noeud.json", "w"))
''')


def fabriquer(dossier, mode="honnete", n=60, seuil_depart=10, extra=None, memo_fuite=False):
    os.makedirs(os.path.join(dossier, "donnees"), exist_ok=True)
    os.makedirs(os.path.join(dossier, "harnais-0"), exist_ok=True)
    rng = random.Random(7)

    def cas(prefixe, a, b):
        with open(os.path.join(dossier, "donnees", prefixe + ".jsonl"), "w") as f:
            for i in range(n):
                x = rng.randint(0, 99)
                crit = "bas" if x < 50 else "haut"
                f.write(json.dumps({"id": f"{prefixe}{a + i}", "critere": crit, "entree": {"id": f"{prefixe}{a + i}", "x": x},
                                    "corrige": {"e": "big" if x >= 50 else "small"}}) + "\n")

    cas("entrainement", 0, 0)
    cas("examen", 1000, 0)
    with open(os.path.join(dossier, "harnais-0", "regle.json"), "w") as f:
        json.dump({"seuil": seuil_depart}, f)
    with open(os.path.join(dossier, "sujet.py"), "w") as f:
        f.write(SUJET)
    with open(os.path.join(dossier, "chercheur.py"), "w") as f:
        f.write(CHERCHEUR)
    with open(os.path.join(dossier, "mode.txt"), "w") as f:
        f.write(mode)
    c = {
        "nom": "test", "sujet": {"commande": ["python3", "sujet.py", "--lot"], "timeout_s": 20, "mode": "lot"},
        "comparateur": {"nom": "egalite", "options": {"cle": "e"}},
        "chercheur": {"commande": ["python3", "chercheur.py"], "timeout_s": 30},
        "parallelisme": 4, "largeur": 2, "tours_niveau1_max": 3, "passes_max": 4,
        "paliers": {"mode": "relatif", "pas": 10},
        "sequentiel": {"actif": True, "tranche": 10, "alpha": 0.05},
        "examen": {"gain_min": 5.0, "echecs_max": 2, "confirmation": True},
        "objectif": {"examen_min": 95.0},
    }
    if extra:
        c.update(extra)
    chemin = os.path.join(dossier, "chantier.json")
    with open(chemin, "w") as f:
        json.dump(c, f)
    from boucle import banc
    banc.sceller(os.path.join(dossier, "donnees", "entrainement.jsonl"))
    banc.sceller(os.path.join(dossier, "donnees", "examen.jsonl"))
    return chemin
