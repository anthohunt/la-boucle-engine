"""The chantier file (JSON): everything one loop needs, with defaults. Paths are relative to
the folder that contains the file."""

import copy
import os

from .util import lire_json

DEFAUTS = {
    "nom": "chantier",
    "banc": {"entrainement": "donnees/entrainement.jsonl", "examen": "donnees/examen.jsonl"},
    "harnais_depart": "harnais-0",
    "sujet": {"commande": None, "timeout_s": 60, "mode": "cas"},   # "cas": one process per case; "lot": one per group
    "comparateur": {"nom": "egalite", "options": {}},
    "chercheur": {"commande": None, "timeout_s": 600},
    "parallelisme": 4,
    "largeur": 3,                 # children developed per round at level 1
    "tours_niveau1_max": 6,       # rounds of level 1 per pass
    "passes_max": 6,              # passes (level 1 then exam) before giving up
    "paliers": {"mode": "fixes", "valeurs": [20, 40, 60, 80, 100]},
    "sequentiel": {"actif": True, "tranche": 20, "alpha": 0.05},
    "examen": {"gain_min": 5.0, "echecs_max": 2, "confirmation": True, "interdites_non_croissantes": True},
    "objectif": {"examen_min": 90.0},
    "familles": {"impasse_apres": 3, "plateau_apres": 2},
    "charte": None,               # optional markdown file given to the researcher
    "budget": {"mesures_max": None},
}


def _fusion(base, voulu):
    sortie = copy.deepcopy(base)
    for k, v in voulu.items():
        if isinstance(v, dict) and isinstance(sortie.get(k), dict):
            sortie[k] = _fusion(sortie[k], v)
        else:
            sortie[k] = v
    return sortie


def charger(chemin):
    chemin = os.path.abspath(chemin)
    voulu = lire_json(chemin)
    if voulu is None:
        raise ValueError(f"{chemin}: not found")
    c = _fusion(DEFAUTS, voulu)
    c["racine"] = os.path.dirname(chemin)
    c["fichier"] = chemin
    for cle in ("sujet", "chercheur"):
        if not c[cle].get("commande"):
            raise ValueError(f"chantier: {cle}.commande is required (a list: program and arguments)")
    if c["paliers"]["mode"] not in ("fixes", "relatif"):
        raise ValueError("chantier: paliers.mode must be 'fixes' or 'relatif'")
    return c


def chemin(c, relatif):
    return relatif if os.path.isabs(relatif) else os.path.join(c["racine"], relatif)
