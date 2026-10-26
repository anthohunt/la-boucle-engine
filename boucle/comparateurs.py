"""Comparators: decide, for one case, whether the proposal is right, a tolerated error or a
forbidden error. Three states only, tested in this order: "interdit", "tolere", "reussi".

A comparator is a function (proposition, corrige, critere, options) -> "reussi"|"tolere"|"interdit".
Built-ins below; a chantier may point to its own (a .py file with a `comparer` function).
"""

import importlib.util
import os

ETATS = ("reussi", "tolere", "interdit")


def egalite(proposition, corrige, critere, options):
    """Right if proposition == corrige on the key options["cle"] (default: whole value).

    options["matrice"]: {"<expected>|<proposed>": "interdit"|"tolere"} sets the cost of each
    kind of mistake; any mistake not listed is options.get("defaut", "tolere").
    A malformed proposition (not a dict when a key is expected, or missing the key) is
    options.get("illisible", "interdit"): saying nothing readable must never look like success.
    """
    cle = options.get("cle")
    try:
        attendu = corrige[cle] if cle else corrige
        propose = proposition[cle] if cle else proposition
    except (KeyError, TypeError, IndexError):
        return options.get("illisible", "interdit")
    if propose == attendu:
        return "reussi"
    return options.get("matrice", {}).get(f"{attendu}|{propose}", options.get("defaut", "tolere"))


INTEGRES = {"egalite": egalite}


def charger(spec, racine):
    """spec: {"nom": "egalite", "options": {...}} or {"fichier": "comparateur.py", "options": {...}}.
    Returns a function (proposition, corrige, critere) -> state."""
    options = spec.get("options", {})
    if "fichier" in spec:
        chemin = os.path.join(racine, spec["fichier"])
        s = importlib.util.spec_from_file_location("comparateur_chantier", chemin)
        mod = importlib.util.module_from_spec(s)
        s.loader.exec_module(mod)
        f = mod.comparer
    else:
        nom = spec.get("nom", "egalite")
        if nom not in INTEGRES:
            raise ValueError(f"unknown comparator {nom!r} (built-in: {sorted(INTEGRES)})")
        f = INTEGRES[nom]

    def comparer(proposition, corrige, critere):
        etat = f(proposition, corrige, critere, options)
        if etat not in ETATS:
            raise ValueError(f"comparator returned {etat!r}, expected one of {ETATS}")
        return etat

    return comparer
