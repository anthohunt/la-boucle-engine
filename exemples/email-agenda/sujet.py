#!/usr/bin/env python3
"""The subject of the example: a deliberately naive mail -> appointments extractor.

Stdin : {"harnais": "<folder>", "entree": {"texte": "<a whole mail, headers included>"}}   (with --lot: one such object plus "id" per line)
Stdout: {"evenements": [{"date": "YYYY-MM-DD", "heure": "HH:MM" | null}], "incertain": bool, "refus": bool}

The harness is a folder:
  regles.json   word lists: mots_hostiles (refuse), mots_incertains (say "not sure")
  post.py       optional: a function corriger(texte, proposition, regles) -> proposition, applied last
The starting harness reads every "<day> <month>" it finds and nothing else: it falls for dates
that are not appointments, never doubts, never refuses. Making it better is the job of the loop.
"""
import datetime
import importlib.util
import json
import os
import re
import sys

MOIS = {m: i for i, ms in enumerate([
    ["january", "janvier"], ["february", "février", "fevrier"], ["march", "mars"], ["april", "avril"], ["may", "mai"], ["june", "juin"],
    ["july", "juillet"], ["august", "août", "aout"], ["september", "septembre"], ["october", "octobre"], ["november", "novembre"], ["december", "décembre", "decembre"]], 1)
    for m in ms}
MOIS_RE = "|".join(sorted(MOIS, key=len, reverse=True))
DATE = re.compile(rf"\b(\d{{1,2}})\s+({MOIS_RE})\b", re.I)
HEURE_EN = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s?(am|pm)\b", re.I)
HEURE_FR = re.compile(r"\b(\d{1,2})h(\d{2})?\b", re.I)
ENTETE_DATE = re.compile(r"^Date:\s*\w+,\s*(\d{1,2})\s+(\w+)\s+(\d{4})", re.M)


def lire_heure(fragment):
    m = HEURE_EN.search(fragment)
    if m:
        h, mn, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3).lower()
        h = h % 12 + (12 if ap == "pm" else 0)
        return f"{h:02d}:{mn:02d}"
    m = HEURE_FR.search(fragment)
    if m:
        return f"{int(m.group(1)):02d}:{int(m.group(2) or 0):02d}"
    return None


def extraire(texte, regles):
    tete, _, corps = texte.partition("\n\n")
    ref = ENTETE_DATE.search(tete)
    annee = int(ref.group(3)) if ref else 2026
    bas = corps.lower()
    evenements = []
    for m in DATE.finditer(corps):
        jour, mois = int(m.group(1)), MOIS[m.group(2).lower()]
        try:
            d = datetime.date(annee, mois, jour)
        except ValueError:
            continue
        fin = corps.find(".", m.end())
        fragment = corps[m.end(): (fin if fin != -1 else m.end() + 25)][:25]
        evenements.append({"date": d.isoformat(), "heure": lire_heure(fragment)})
    proposition = {"evenements": evenements, "incertain": False, "refus": False}
    if any(p in bas for p in regles.get("mots_hostiles", [])):
        return {"evenements": [], "incertain": False, "refus": True}
    if any(p in bas for p in regles.get("mots_incertains", [])):
        return {"evenements": [], "incertain": True, "refus": False}
    return proposition


def un_cas(demande):
    dossier = demande["harnais"]
    with open(os.path.join(dossier, "regles.json"), encoding="utf-8") as f:
        regles = json.load(f)
    texte = demande["entree"]["texte"]
    proposition = extraire(texte, regles)
    post = os.path.join(dossier, "post.py")
    if os.path.exists(post):
        spec = importlib.util.spec_from_file_location("post", post)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        proposition = mod.corriger(texte, proposition, regles)
    return proposition


if __name__ == "__main__":
    if "--lot" in sys.argv:        # batch mode: one JSON per line in, one JSON per line out
        for ligne in sys.stdin:
            if ligne.strip():
                d = json.loads(ligne)
                print(json.dumps({"id": d["id"], "proposition": un_cas(d)}, ensure_ascii=False))
    else:
        print(json.dumps(un_cas(json.load(sys.stdin)), ensure_ascii=False))
