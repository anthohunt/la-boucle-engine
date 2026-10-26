#!/usr/bin/env python3
"""The subject of the example: a rule-based ticket classifier driven by a harness.

Stdin : {"harnais": "<folder>", "entree": {"texte": "..."}}      (with --lot: one such object plus "id" per line)
Stdout: {"etiquette": "urgent" | "a_verifier" | "rien"}          (with --lot: {"id", "proposition"} per line)

The harness is one file, regles.json:
  urgent      words/phrases that mark an outage
  a_verifier  words/phrases that mark a ticket a human must read
  negations   cues that cancel the urgent words of the same sentence ("fixed", "no longer"…)
  ordres      phrases that try to give orders to the classifier: such a ticket goes to a_verifier
  defaut      label when nothing matches
"""
import json
import re
import sys


def classer(texte, regles):
    t = texte.lower()
    if any(p in t for p in regles.get("ordres", [])):
        return "a_verifier"
    for phrase in re.split(r"[.!?]", t):
        if any(m in phrase for m in regles.get("urgent", [])) and not any(n in phrase for n in regles.get("negations", [])):
            return "urgent"
    if any(m in t for m in regles.get("a_verifier", [])):
        return "a_verifier"
    return regles.get("defaut", "rien")


def un_cas(demande):
    with open(demande["harnais"].rstrip("/") + "/regles.json", encoding="utf-8") as f:
        regles = json.load(f)
    return {"etiquette": classer(demande["entree"]["texte"], regles)}


if __name__ == "__main__":
    if "--lot" in sys.argv:        # batch mode: one JSON per line in, one JSON per line out
        for ligne in sys.stdin:
            if ligne.strip():
                d = json.loads(ligne)
                print(json.dumps({"id": d["id"], "proposition": un_cas(d)}))
    else:
        print(json.dumps(un_cas(json.load(sys.stdin))))
