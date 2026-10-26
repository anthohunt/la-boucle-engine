"""The loop. Two levels, as in the method:

LEVEL 1 (autonomous, training set only): the best harness so far is the root of a tree. Each
round, `largeur` children are written by the researcher from the mistakes the parent makes on
the training set. A child is marked against its parent (early stop if it is certainly worse =
prune). A child that reaches the next step (a *palier*) becomes a candidate.

LEVEL 2 (exam): the candidate is compared, case by case, with the best version on the sealed
exam. It must win by `gain_min` points (and, by default, make no more forbidden errors); the
exam is then run a second time as a confirmation and the smaller gain counts. Success: new best
version. Failure: counted; after `echecs_max` failures in a row the loop PAUSES and asks the
operator to review the method (it never retries by itself).

Stops: goal reached (exit 0), pause (exit 3), passes or budget exhausted (exit 4).
Every step is appended to journal.jsonl; the state is saved after every node, so a run that
is killed can be started again with the same command.
"""

import os
import shutil

from . import bareme
from .chantier import chemin as chemin_chantier
from .chercheur import lancer as lancer_chercheur
from .juge import Juge
from .util import ajouter_jsonl, ecrire_json, empreinte_dossier, lire_json, maintenant

SORTIE_OK, SORTIE_PAUSE, SORTIE_ARRET = 0, 3, 4


class Moteur:
    def __init__(self, chantier, sortie=print):
        self.c = chantier
        self.juge = Juge(chantier)
        self.dire = sortie
        self.f_etat = os.path.join(chantier["racine"], "etat.json")
        self.f_journal = os.path.join(chantier["racine"], "journal.jsonl")
        self.d_noeuds = os.path.join(chantier["racine"], "noeuds")
        self.etat = lire_json(self.f_etat)
        self.pannes_chercheur = 0

    # --- bookkeeping --------------------------------------------------------------------
    def journal(self, evenement, **champs):
        ajouter_jsonl(self.f_journal, {"quand": maintenant(), "evenement": evenement, **champs})

    def sauver(self):
        self.etat["mesures"] = self.etat.get("mesures_avant", 0) + self.juge.mesures
        ecrire_json(self.f_etat, self.etat)

    def dossier(self, nid):
        return os.path.join(self.d_noeuds, nid)

    def nouveau_id(self):
        self.etat["compteur"] += 1
        return f"n{self.etat['compteur']:04d}"

    def noeud(self, nid):
        return self.etat["noeuds"][nid]

    def budget_epuise(self):
        m = self.c["budget"]["mesures_max"]
        return m is not None and self.etat.get("mesures_avant", 0) + self.juge.mesures >= m

    # --- step 0 -------------------------------------------------------------------------
    def etape0(self):
        depart = chemin_chantier(self.c, self.c["harnais_depart"])
        if not os.path.isdir(depart):
            raise ValueError(f"harnais_depart not found: {depart}")
        racine = "n0000"
        os.makedirs(self.d_noeuds, exist_ok=True)
        shutil.copytree(depart, self.dossier(racine), dirs_exist_ok=True)
        res, rapport = self.juge.noter_entrainement(self.dossier(racine))
        ecrire_json(os.path.join(self.dossier(racine), "mesures-entrainement.json"), res)
        exam, _ = self.juge.noter_examen(self.dossier(racine))
        self.etat = {
            "nom": self.c["nom"],
            "noeuds": {
                racine: {
                    "id": racine, "parent": None, "famille": "depart", "idee": "starting harness",
                    "note_entrainement": rapport["note"], "statut": "mesure", "developpe": False,
                    "interdites": rapport["interdites"], "note_examen": exam["note"], "passe": 0,
                }
            },
            "meilleure_version": racine,
            "note_examen_meilleure": exam["note"],
            "par_critere_examen": {k: round(v["taux"] * 100, 1) for k, v in exam["par_critere"].items()},
            "echecs_examen": 0,
            "passes_sans_progres": 0,
            "passe": 0,
            "compteur": 0,
            "familles": {},
            "statut": "en_cours",
            "mesures_avant": 0,
        }
        self.journal("etape0", note_entrainement=rapport["note"], note_examen=exam["note"], par_critere=rapport["par_critere"])
        self.dire(f"step 0: training {rapport['note']}, exam {exam['note']}")
        self.sauver()

    # --- helpers for level 1 ------------------------------------------------------------
    def palier_suivant(self, note):
        p = self.c["paliers"]
        if p["mode"] == "relatif":
            return min(100.0, note + p["pas"])
        for v in sorted(p["valeurs"]):
            if v > note:
                return float(v)
        return 100.0

    def racine_n1(self):
        """The best fully measured training node (never a pruned one)."""
        mesures = [n for n in self.etat["noeuds"].values() if n["note_entrainement"] is not None and n["statut"] in ("mesure", "promu", "echec_examen")]
        return max(mesures, key=lambda n: (n["note_entrainement"], n["id"]))

    def famille(self, nom):
        return self.etat["familles"].setdefault(nom, {"essais": 0, "sans_progres": 0, "meilleure": None, "impasse": False})

    def notes_pour_chercheur(self, nid):
        return {
            "entrainement": self.noeud(nid)["note_entrainement"],
            "examen_agrege_par_critere": self.etat["par_critere_examen"],
        }

    def fautes(self, nid):
        mesures = lire_json(os.path.join(self.dossier(nid), "mesures-entrainement.json"), [])
        cas = {c["id"]: c for c in self.juge.entrainement()}
        return [
            {"id": r["id"], "critere": r["critere"], "entree": cas[r["id"]]["entree"], "corrige": cas[r["id"]]["corrige"],
             "proposition": r["proposition"], "etat": r["etat"]}
            for r in mesures if r["etat"] != "reussi"
        ]

    # --- level 1 ------------------------------------------------------------------------
    def niveau1(self, divergence):
        """Returns the id of a candidate node, or None when the tree gave nothing this pass."""
        racine = self.racine_n1()
        palier = self.palier_suivant(racine["note_entrainement"])
        self.journal("niveau1_debut", racine=racine["id"], note=racine["note_entrainement"], palier=palier, divergence=divergence)
        self.dire(f"level 1: root {racine['id']} at {racine['note_entrainement']}, next step {palier}")
        utilises_racine = 0
        for tour in range(self.c["tours_niveau1_max"]):
            parents = [n for n in self.etat["noeuds"].values()
                       if n["statut"] == "mesure" and not n["developpe"] and n["note_entrainement"] is not None and n["id"] != racine["id"]]
            parents.sort(key=lambda n: -n["note_entrainement"])
            parents = parents[: self.c["largeur"]]
            while len(parents) < self.c["largeur"] and utilises_racine < self.c["largeur"] * 2:
                parents.append(racine)
                utilises_racine += 1
            if not parents:
                break
            for index, parent in enumerate(parents):
                if self.budget_epuise():
                    self.journal("budget_epuise")
                    return None
                if self.pannes_chercheur >= 3:
                    return None
                cand = self.developper(parent, index, palier, divergence)
                if cand:
                    return cand
            for p in parents:
                p["developpe"] = True
            self.sauver()
        return None

    def developper(self, parent, index, palier, divergence):
        fam = self.etat["familles"]
        impasse = sorted(k for k, v in fam.items() if v["impasse"])
        nid = self.nouveau_id()
        sortie = self.dossier(nid)
        r = lancer_chercheur(
            self.c, self.dossier(parent["id"]), sortie, self.fautes(parent["id"]),
            self.notes_pour_chercheur(parent["id"]), index, impasse, sorted(fam), divergence, palier,
        )
        noeud = {"id": nid, "parent": parent["id"], "famille": r["famille"], "idee": r["idee"], "note_entrainement": None,
                 "statut": "mesure", "developpe": False, "interdites": None, "note_examen": None, "passe": self.etat["passe"]}
        self.etat["noeuds"][nid] = noeud
        f = self.famille(r["famille"])
        if not r["ok"]:
            self.pannes_chercheur += 1
            noeud["statut"] = "echec_chercheur"
            self.journal("chercheur", noeud=nid, parent=parent["id"], erreur=r["erreur"])
            self.dire(f"  {nid}: researcher failed ({r['erreur']})")
            self.sauver()
            return None
        if not r["change"]:
            noeud["statut"] = "sans_changement"
            self.journal("chercheur", noeud=nid, parent=parent["id"], famille=r["famille"], resultat="sans_changement")
            self.sauver()
            return None
        if f["impasse"] and not r["justification"]:
            noeud["statut"] = "ecarte"
            self.journal("chercheur", noeud=nid, parent=parent["id"], famille=r["famille"], resultat="famille_en_impasse")
            self.dire(f"  {nid}: family '{r['famille']}' is stuck, discarded without measuring")
            self.sauver()
            return None
        self.pannes_chercheur = 0
        f["essais"] += 1
        parent_res = {m["id"]: m for m in lire_json(os.path.join(self.dossier(parent["id"]), "mesures-entrainement.json"), [])}
        res, rapport, tot, est = self.juge.mesure_sequentielle(sortie, parent_res)
        ecrire_json(os.path.join(sortie, "mesures-entrainement.json"), res)
        progres = False
        if tot:
            noeud["statut"] = "elague"
            noeud["estimation"] = est
            self.journal("mesure", noeud=nid, parent=parent["id"], famille=r["famille"], idee=r["idee"], arret_tot=True, estimation=est)
            self.dire(f"  {nid} [{r['famille']}]: pruned after {est['n']}/{est['sur']} cases (difference {est['ecart_moyen']:+.2f}, upper bound {est['haut']:+.2f})")
        else:
            noeud["note_entrainement"] = rapport["note"]
            noeud["interdites"] = rapport["interdites"]
            progres = rapport["note"] > parent["note_entrainement"]
            if rapport["note"] < parent["note_entrainement"]:
                noeud["statut"] = "elague"
            self.journal("mesure", noeud=nid, parent=parent["id"], famille=r["famille"], idee=r["idee"], note=rapport["note"],
                         note_parent=parent["note_entrainement"], par_critere=rapport["par_critere"])
            self.dire(f"  {nid} [{r['famille']}]: {rapport['note']} (parent {parent['note_entrainement']})")
        if progres:
            f["sans_progres"] = 0
            f["meilleure"] = max(f["meilleure"] or 0, noeud["note_entrainement"])
        else:
            f["sans_progres"] += 1
            if f["sans_progres"] >= self.c["familles"]["impasse_apres"] and not f["impasse"]:
                f["impasse"] = True
                self.journal("famille_en_impasse", famille=r["famille"])
        self.sauver()
        if noeud["note_entrainement"] is not None and noeud["note_entrainement"] >= palier and noeud["statut"] == "mesure":
            noeud["statut"] = "candidat"
            self.journal("candidat", noeud=nid, note=noeud["note_entrainement"], palier=palier)
            self.dire(f"  {nid} reaches the step {palier}: candidate for the exam")
            self.sauver()
            return nid
        return None

    # --- level 2 ------------------------------------------------------------------------
    def examen(self, nid):
        meilleure = self.etat["meilleure_version"]
        cmp1 = self.juge.comparer_examen(self.dossier(nid), self.dossier(meilleure))
        gain = cmp1["gain"]
        confirmation = None
        if self.c["examen"]["confirmation"]:
            confirmation = self.juge.comparer_examen(self.dossier(nid), self.dossier(meilleure), force=True)
            gain = min(gain, confirmation["gain"])
        ok = gain >= self.c["examen"]["gain_min"]
        if ok and self.c["examen"]["interdites_non_croissantes"] and cmp1["interdites_candidat"] > cmp1["interdites_reference"]:
            ok = False
            cmp1["motif"] = "more forbidden errors than the reference"
        n = self.noeud(nid)
        n["note_examen"] = cmp1["note_candidat"]
        self.journal("examen", noeud=nid, reference=meilleure, gain=gain, accepte=ok, comparaison=cmp1,
                     confirmation=None if confirmation is None else confirmation["gain"])
        if ok:
            n["statut"] = "promu"
            self.etat["meilleure_version"] = nid
            self.etat["note_examen_meilleure"] = cmp1["note_candidat"]
            self.etat["par_critere_examen"] = cmp1["par_critere_candidat"]
            self.etat["echecs_examen"] = 0
            self.etat["passes_sans_progres"] = 0
            self.dire(f"exam: {nid} wins ({cmp1['note_reference']} -> {cmp1['note_candidat']}, gain {gain:+.1f}): new best version")
        else:
            n["statut"] = "echec_examen"
            self.etat["echecs_examen"] += 1
            self.etat["passes_sans_progres"] += 1
            self.dire(f"exam: {nid} fails (gain {gain:+.1f}, needs {self.c['examen']['gain_min']}); failures in a row: {self.etat['echecs_examen']}")
        self.sauver()
        return ok

    def pause(self):
        texte = (
            f"# Pause: {self.etat['echecs_examen']} exam failures in a row\n\n"
            f"Date: {maintenant()}\n\nBest version: {self.etat['meilleure_version']} "
            f"(exam {self.etat['note_examen_meilleure']}).\n\n"
            "The loop does not retry by itself. Read journal.jsonl (events `examen`), then decide:\n"
            "1. is the training set representative of the exam (same categories, same difficulty)?\n"
            "2. is the researcher charter too narrow, or too loose?\n"
            "3. is the exam gain threshold (examen.gain_min) realistic?\n"
            "After the change, delete this file and run the same command again.\n"
        )
        with open(os.path.join(self.c["racine"], "PAUSE.md"), "w", encoding="utf-8") as f:
            f.write(texte)
        self.etat["statut"] = "pause"
        self.journal("pause", echecs=self.etat["echecs_examen"])
        self.sauver()
        self.dire("PAUSE: two failures in a row. See PAUSE.md.")

    # --- the whole run ------------------------------------------------------------------
    def run(self):
        pause = os.path.join(self.c["racine"], "PAUSE.md")
        if os.path.exists(pause):
            self.dire("PAUSE.md exists: the operator must review the method and delete it first.")
            return SORTIE_PAUSE
        if self.etat is None:
            self.etape0()
        else:
            self.etat["mesures_avant"] = self.etat.get("mesures", 0)
            if self.etat["statut"] == "pause":
                self.etat["echecs_examen"] = 0
            self.etat["statut"] = "en_cours"
        if self.etat["note_examen_meilleure"] >= self.c["objectif"]["examen_min"]:
            return self.fin("objectif_atteint", SORTIE_OK)
        while self.etat["passe"] < self.c["passes_max"]:
            self.etat["passe"] += 1
            divergence = self.etat["passes_sans_progres"] >= self.c["familles"]["plateau_apres"]
            self.dire(f"pass {self.etat['passe']}" + (" (plateau: divergence)" if divergence else ""))
            cand = self.niveau1(divergence)
            if cand is None:
                self.etat["passes_sans_progres"] += 1
                self.journal("passe_sans_candidat", passe=self.etat["passe"])
                self.sauver()
                if self.budget_epuise():
                    return self.fin("budget_epuise", SORTIE_ARRET)
                if self.pannes_chercheur >= 3:
                    return self.fin("chercheur_en_panne", SORTIE_ARRET)
                continue
            if self.examen(cand):
                if self.etat["note_examen_meilleure"] >= self.c["objectif"]["examen_min"]:
                    return self.fin("objectif_atteint", SORTIE_OK)
            elif self.etat["echecs_examen"] >= self.c["examen"]["echecs_max"]:
                self.pause()
                return SORTIE_PAUSE
        return self.fin("passes_epuisees", SORTIE_ARRET)

    def fin(self, raison, code):
        self.etat["statut"] = raison
        self.journal("fin", raison=raison, meilleure=self.etat["meilleure_version"], note_examen=self.etat["note_examen_meilleure"])
        self.sauver()
        self.dire(f"end: {raison}; best version {self.etat['meilleure_version']} at {self.etat['note_examen_meilleure']} on the exam")
        return code
