#!/usr/bin/env python3
"""A scripted stand-in for the researcher agent (so the example runs without any AI model).

It reads the parent's mistakes on the training set (BOUCLE_FAUTES), picks one family of ideas and
edits the child harness (BOUCLE_SORTIE/regles.json). A real run replaces this command by an AI agent
(see ../chercheur-claude/) that reads the same inputs and edits the same folder.

Families: mots-cles (urgent words), verifier (words that call for a human), negations (cues that
cancel an alarm), ordres (injected orders). Child number i of a round takes the i-th family in turn,
skipping families that are stuck (BOUCLE_IMPASSE).
"""
import json
import os
import re
from collections import Counter

FAMILLES = ["mots-cles", "negations", "ordres", "verifier"]
INUTILES = set("the and for with that this have from your you are was were not but all any can how what where there when after before every since just only into out our has had its it's i'm".split())
CUES_NEGATION = ["fixed", "no longer", "resolved", "not urgent", "no problem", "works again", "is back", "nothing more"]
CUES_ORDRES = ["ignore previous", "system:", "disregard your", "you must answer"]


def mots(texte):
    return [m for m in re.findall(r"[a-z']{4,}", texte.lower()) if m not in INUTILES]


def candidats(famille, fautes, regles):
    if famille in ("mots-cles", "verifier"):
        attendu = "urgent" if famille == "mots-cles" else "a_verifier"
        cible = regles["urgent" if famille == "mots-cles" else "a_verifier"]
        pour = Counter()
        contre = set()
        for f in fautes:
            texte = f["entree"]["texte"]
            if f["corrige"]["etiquette"] == attendu and f["proposition"] and f["proposition"].get("etiquette") == "rien":
                pour.update(set(mots(texte)))
            elif f["corrige"]["etiquette"] != attendu:
                contre.update(mots(texte))
        return [m for m, _ in pour.most_common() if m not in contre and not any(m in c or c in m for c in cible)]
    if famille == "negations":
        vus = Counter()
        for f in fautes:
            if f["corrige"]["etiquette"] == "rien" and f["proposition"] and f["proposition"].get("etiquette") == "urgent":
                vus.update(c for c in CUES_NEGATION if c in f["entree"]["texte"].lower())
        return [c for c, _ in vus.most_common() if c not in regles["negations"]]
    if famille == "ordres":
        vus = Counter()
        for f in fautes:
            if f["corrige"]["etiquette"] == "a_verifier" and f["proposition"] and f["proposition"].get("etiquette") != "a_verifier":
                vus.update(c for c in CUES_ORDRES if c in f["entree"]["texte"].lower())
        return [c for c, _ in vus.most_common() if c not in regles["ordres"]]
    return []


def main():
    sortie = os.environ["BOUCLE_SORTIE"]
    index = int(os.environ.get("BOUCLE_INDEX", "0"))
    impasse = [x for x in os.environ.get("BOUCLE_IMPASSE", "").split(",") if x]
    decalage = 1 if os.environ.get("BOUCLE_DIVERGENCE") == "1" else 0
    with open(os.environ["BOUCLE_FAUTES"], encoding="utf-8") as f:
        fautes = json.load(f)
    chemin = os.path.join(sortie, "regles.json")
    with open(chemin, encoding="utf-8") as f:
        regles = json.load(f)
    ordre = [FAMILLES[(index + decalage + k) % len(FAMILLES)] for k in range(len(FAMILLES))]
    for famille in ordre:
        if famille in impasse:
            continue
        propositions = candidats(famille, fautes, regles)
        if not propositions:
            continue
        cle = {"mots-cles": "urgent", "verifier": "a_verifier", "negations": "negations", "ordres": "ordres"}[famille]
        ajout = propositions[:1] if famille in ("mots-cles", "verifier") else propositions
        regles[cle] = regles[cle] + ajout
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(regles, f, indent=2, ensure_ascii=False)
        with open(os.path.join(sortie, "noeud.json"), "w", encoding="utf-8") as f:
            json.dump({"famille": famille, "idee": f"add {ajout} to {cle}"}, f)
        return
    with open(os.path.join(sortie, "noeud.json"), "w", encoding="utf-8") as f:
        json.dump({"famille": "aucune-idee", "idee": "nothing to try"}, f)


if __name__ == "__main__":
    main()
