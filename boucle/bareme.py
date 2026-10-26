"""The scale: from per-case states to a mark.

Per category: success rate = successes / cases (a tolerated error is not a success).
Mark = mean of the per-category rates, in points out of 100. Forbidden errors are counted
next to it (they cost trust, tolerated ones cost a human round trip) but never change the mark.
"""

from collections import defaultdict


def noter_passage(resultats):
    """resultats: list of {"id", "critere", "etat"}. Returns the report of one pass."""
    par = defaultdict(lambda: {"nombre": 0, "reussis": 0, "tolerees": 0, "interdites": 0})
    for r in resultats:
        c = par[r["critere"]]
        c["nombre"] += 1
        c[{"reussi": "reussis", "tolere": "tolerees", "interdit": "interdites"}[r["etat"]]] += 1
    for c in par.values():
        c["taux"] = c["reussis"] / c["nombre"]
    note = 100.0 * sum(c["taux"] for c in par.values()) / len(par) if par else 0.0
    return {
        "note": round(note, 2),
        "nombre": sum(c["nombre"] for c in par.values()),
        "interdites": sum(c["interdites"] for c in par.values()),
        "par_critere": dict(sorted(par.items())),
    }


def point(etat):
    return 1.0 if etat == "reussi" else 0.0
