"""The researcher: any command that turns a harness plus its visible mistakes into a better
harness. It is started once per child, from the chantier folder (so a relative command such as
["python3", "chercheur.py"] works); BOUCLE_SORTIE is a folder that already holds a copy of the
parent harness: the command edits that copy in place and describes its idea.

Environment given to the command:
  BOUCLE_SORTIE         folder to edit: the child harness (a copy of the parent, writable)
  BOUCLE_PARENT         the untouched parent harness (read only by convention)
  BOUCLE_FAUTES         JSON file: the parent's mistakes on the TRAINING set
                        [{"id","critere","entree","corrige","proposition","etat"}]
  BOUCLE_NOTES          JSON file: the parent's marks per category, training and (aggregated) exam
  BOUCLE_CHARTE         markdown file: what may and may not be modified (if the chantier has one)
  BOUCLE_INDEX          number of this child within the round (0, 1, 2…)
  BOUCLE_IMPASSE        comma-separated families that are stuck: do not try them again
  BOUCLE_FAMILLES       comma-separated families already tried
  BOUCLE_DIVERGENCE     "1" when the loop is on a plateau: propose a structurally different approach
  BOUCLE_PALIER         the mark the child must reach to go to the exam
The command must write BOUCLE_SORTIE/noeud.json: {"famille": "<short name>", "idee": "<one line>"}
(and optionally "justification" to retry a family that is stuck). It never receives an exam case.
"""

import json
import os
import shutil
import subprocess

from .util import commande_portable, ecrire_json, empreinte_dossier, env_enfant, lire_json


def preparer_sortie(parent, sortie):
    if os.path.exists(sortie):
        shutil.rmtree(sortie)
    shutil.copytree(parent, sortie, ignore=shutil.ignore_patterns("noeud.json", "mesures-entrainement.json"))


def lancer(chantier, parent, sortie, fautes, notes, index, impasse, familles, divergence, palier):
    """Run the researcher command once. Returns {"ok", "famille", "idee", "justification", "change", "erreur"}."""
    preparer_sortie(parent, sortie)
    dossier = os.path.dirname(os.path.abspath(sortie))
    f_fautes = os.path.join(dossier, f".fautes-{os.path.basename(sortie)}.json")
    f_notes = os.path.join(dossier, f".notes-{os.path.basename(sortie)}.json")
    ecrire_json(f_fautes, fautes)
    ecrire_json(f_notes, notes)
    env = dict(os.environ)
    env.update(
        BOUCLE_SORTIE=os.path.abspath(sortie),
        BOUCLE_PARENT=os.path.abspath(parent),
        BOUCLE_FAUTES=f_fautes,
        BOUCLE_NOTES=f_notes,
        BOUCLE_INDEX=str(index),
        BOUCLE_IMPASSE=",".join(impasse),
        BOUCLE_FAMILLES=",".join(familles),
        BOUCLE_DIVERGENCE="1" if divergence else "0",
        BOUCLE_PALIER=str(palier),
    )
    if chantier.get("charte"):
        env["BOUCLE_CHARTE"] = os.path.join(chantier["racine"], chantier["charte"])
    sortie_cmd = {"ok": False, "famille": "non-declaree", "idee": "", "justification": None, "change": False, "erreur": None}
    try:
        r = subprocess.run(
            commande_portable(chantier["chercheur"]["commande"]),
            env=env_enfant(env),
            cwd=chantier["racine"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=chantier["chercheur"]["timeout_s"],
        )
        if r.returncode != 0:
            sortie_cmd["erreur"] = f"researcher exited with {r.returncode}: {r.stderr.strip()[-300:]}"
            return sortie_cmd
    except (subprocess.TimeoutExpired, OSError) as e:
        sortie_cmd["erreur"] = f"researcher failed: {e}"
        return sortie_cmd
    meta = lire_json(os.path.join(sortie, "noeud.json"), {}) or {}
    sortie_cmd.update(
        ok=True,
        famille=str(meta.get("famille", "non-declaree")),
        idee=str(meta.get("idee", "")),
        justification=meta.get("justification"),
        change=empreinte_dossier(sortie) != empreinte_dossier(parent),
    )
    for f in (f_fautes, f_notes):
        try:
            os.unlink(f)
        except OSError:
            pass
    return sortie_cmd
