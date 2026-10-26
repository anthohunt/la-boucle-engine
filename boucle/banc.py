"""The bench: a JSONL file, one case per line, sealed by a SHA-256 fingerprint.

A case: {"id": str, "critere": str, "entree": any, "corrige": any}. The *critere* is the
category the case belongs to (the final mark is the mean of the per-category success rates,
so a rare category counts as much as a common one).
"""

import json
import os
from collections import Counter

from .util import ecrire_json, lire_json, maintenant, sha256_octets

CLES = ("id", "critere", "entree", "corrige")


def charger(chemin):
    """Read and validate a bench. Raises ValueError on a malformed case or a duplicate id."""
    cas, vus = [], set()
    with open(chemin, encoding="utf-8") as f:
        for n, ligne in enumerate(f, 1):
            if not ligne.strip():
                continue
            try:
                c = json.loads(ligne)
            except json.JSONDecodeError as e:
                raise ValueError(f"{chemin}:{n}: not JSON ({e})")
            manque = [k for k in CLES if k not in c]
            if manque:
                raise ValueError(f"{chemin}:{n}: missing keys {manque}")
            if c["id"] in vus:
                raise ValueError(f"{chemin}:{n}: duplicate id {c['id']!r}")
            vus.add(c["id"])
            cas.append(c)
    if not cas:
        raise ValueError(f"{chemin}: empty bench")
    return cas


def empreinte(cas):
    """Order-independent SHA-256 of the cases' content."""
    corps = "\n".join(
        json.dumps(c, ensure_ascii=False, sort_keys=True) for c in sorted(cas, key=lambda c: c["id"])
    )
    return sha256_octets(corps.encode("utf-8"))


def chemin_sceau(chemin):
    return chemin + ".sceau"


def sceller(chemin):
    """Write <bench>.sceau with the fingerprint, the size and the per-category counts."""
    cas = charger(chemin)
    sceau = {
        "empreinte": empreinte(cas),
        "nombre": len(cas),
        "par_critere": dict(Counter(c["critere"] for c in cas)),
        "scelle_le": maintenant(),
    }
    ecrire_json(chemin_sceau(chemin), sceau)
    return sceau


def verifier(chemin):
    """Return the cases if the bench still matches its seal; raise ValueError otherwise."""
    sceau = lire_json(chemin_sceau(chemin))
    if sceau is None:
        raise ValueError(f"{os.path.basename(chemin)}: not sealed (run: python3 -m boucle sceller)")
    cas = charger(chemin)
    if empreinte(cas) != sceau["empreinte"]:
        raise ValueError(f"{os.path.basename(chemin)}: the bench changed after sealing")
    return cas
