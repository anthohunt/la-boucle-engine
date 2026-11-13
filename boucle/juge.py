"""The judge: runs the *subject* (the thing under improvement) on a bench and marks it.

Subject protocol (default mode "cas"): the command is started once per case. It reads one JSON object on stdin,
{"harnais": "<absolute folder of the harness>", "entree": <the case input>}, and writes the
proposal as JSON on stdout. A crash, a timeout or unreadable output gives proposition=None,
which the comparator treats as unreadable (a forbidden error by default).

Isolation: the exam bench and the per-case exam results are read by the judge only; the
researcher gets aggregated per-category marks, never a case. This keeps an honest researcher
honest. It is not a sandbox: run the researcher in a container if it is not trusted.
"""

import json
import math
import os
import random
import subprocess
from concurrent.futures import ThreadPoolExecutor

from . import banc, bareme, comparateurs
from .chantier import chemin as chemin_chantier
from .util import commande_portable, ecrire_json, empreinte_dossier, env_enfant, lire_json


class Juge:
    def __init__(self, chantier):
        self.c = chantier
        self.comparer = comparateurs.charger(chantier["comparateur"], chantier["racine"])
        self.mesures = 0
        self.dossier_prive = os.path.join(chantier["racine"], ".juge")
        os.makedirs(self.dossier_prive, mode=0o700, exist_ok=True)
        os.chmod(self.dossier_prive, 0o700)

    # --- one case ---------------------------------------------------------------------
    def _proposer(self, harnais, entree):
        demande = json.dumps({"harnais": os.path.abspath(harnais), "entree": entree}, ensure_ascii=False)
        try:
            r = subprocess.run(
                commande_portable(self.c["sujet"]["commande"]),
                input=demande,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env_enfant(),
                timeout=self.c["sujet"]["timeout_s"],
                cwd=self.c["racine"],
            )
            if r.returncode != 0:
                return None
            return json.loads(r.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            return None

    def _noter_cas(self, harnais, cas):
        self.mesures += 1
        proposition = self._proposer(harnais, cas["entree"])
        etat = self.comparer(proposition, cas["corrige"], cas["critere"])
        return {"id": cas["id"], "critere": cas["critere"], "etat": etat, "proposition": proposition}

    def _proposer_lot(self, harnais, groupe):
        """Batch mode: one process for a group of cases (cheap when the subject loads a model).
        stdin: one JSON per line {"id","harnais","entree"}; stdout: one JSON per line {"id","proposition"}."""
        demande = "\n".join(json.dumps({"id": c["id"], "harnais": os.path.abspath(harnais), "entree": c["entree"]}, ensure_ascii=False) for c in groupe) + "\n"
        try:
            r = subprocess.run(commande_portable(self.c["sujet"]["commande"]), input=demande, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", env=env_enfant(),
                               timeout=self.c["sujet"]["timeout_s"], cwd=self.c["racine"])
            if r.returncode != 0:
                return {}
            sortie = {}
            for ligne in r.stdout.splitlines():
                try:
                    o = json.loads(ligne)
                    sortie[o["id"]] = o.get("proposition")
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
            return sortie
        except (subprocess.TimeoutExpired, OSError):
            return {}

    def _mesurer_lot(self, harnais, cas):
        p = max(1, self.c["parallelisme"])
        groupes = [cas[i::p] for i in range(p) if cas[i::p]]
        with ThreadPoolExecutor(max_workers=len(groupes) or 1) as pool:
            parts = list(pool.map(lambda g: self._proposer_lot(harnais, g), groupes))
        reponses = {}
        for part in parts:
            reponses.update(part)
        self.mesures += len(cas)
        sortie = []
        for c in cas:
            proposition = reponses.get(c["id"])
            sortie.append({"id": c["id"], "critere": c["critere"], "etat": self.comparer(proposition, c["corrige"], c["critere"]), "proposition": proposition})
        return sortie

    def mesurer(self, harnais, cas):
        """Mark a harness on a list of cases (in parallel). Returns the per-case results."""
        if self.c["sujet"].get("mode") == "lot":
            return self._mesurer_lot(harnais, cas)
        with ThreadPoolExecutor(max_workers=max(1, self.c["parallelisme"])) as pool:
            return list(pool.map(lambda x: self._noter_cas(harnais, x), cas))

    # --- training: visible to the researcher ------------------------------------------
    def entrainement(self):
        return banc.verifier(chemin_chantier(self.c, self.c["banc"]["entrainement"]))

    def noter_entrainement(self, harnais):
        cas = self.entrainement()
        res = self.mesurer(harnais, cas)
        return res, bareme.noter_passage(res)

    def mesure_sequentielle(self, harnais, parent_par_id):
        """Mark a child on the training set against its parent, with early stopping.

        The training cases are taken in a fresh secret random order, in slices. After each
        slice, a Hoeffding bound that stays valid at every look (risk alpha split over the
        slices as alpha / (m (m + 1))) bounds the paired mean difference child - parent.
        If the upper bound is below zero, the child is certainly worse: stop and prune.
        Otherwise the child is marked on everything (a node that might reach the next step is
        never left half measured). Returns (results, report, stopped_early, estimate).
        """
        cas = list(self.entrainement())
        random.SystemRandom().shuffle(cas)
        seq = self.c["sequentiel"]
        tranche = max(1, int(seq["tranche"]))
        res, diffs = [], []
        est = None
        m = 0
        for debut in range(0, len(cas), tranche):
            morceau = cas[debut : debut + tranche]
            part = self.mesurer(harnais, morceau)
            res += part
            diffs += [bareme.point(r["etat"]) - bareme.point(parent_par_id[r["id"]]["etat"]) for r in part]
            m += 1
            k = len(diffs)
            moyenne = sum(diffs) / k
            t = math.sqrt(2.0 * math.log(2.0 * m * (m + 1) / seq["alpha"]) / k)
            est = {"n": k, "sur": len(cas), "ecart_moyen": round(moyenne, 4), "bas": round(moyenne - t, 4), "haut": round(moyenne + t, 4)}
            if seq["actif"] and k < len(cas) and moyenne + t < 0:
                return res, None, True, est
        return res, bareme.noter_passage(res), False, est

    # --- exam: sealed, judge only -----------------------------------------------------
    def _cle_examen(self, harnais):
        sceau = lire_json(banc.chemin_sceau(chemin_chantier(self.c, self.c["banc"]["examen"])))
        if sceau is None:
            raise ValueError("exam bench is not sealed (python3 -m boucle sceller)")
        return f"{sceau['empreinte'][:16]}-{empreinte_dossier(harnais)[:16]}"

    def noter_examen(self, harnais, force=False):
        """Mark a harness on the sealed exam. Per-case results stay in .juge/ (mode 600);
        the caller gets the aggregate only. Cached by (exam seal, harness fingerprint)."""
        cle = self._cle_examen(harnais)
        fichier = os.path.join(self.dossier_prive, f"examen-{cle}.json")
        res = None if force else lire_json(fichier)
        if res is None:
            cas = banc.verifier(chemin_chantier(self.c, self.c["banc"]["examen"]))
            res = [{k: r[k] for k in ("id", "critere", "etat")} for r in self.mesurer(harnais, cas)]
            ecrire_json(fichier, res)
            os.chmod(fichier, 0o600)
        return bareme.noter_passage(res), cle

    def comparer_examen(self, harnais_a, harnais_b, force=False):
        """Paired exam comparison, candidate a against reference b. Aggregates only."""
        _, cle_a = self.noter_examen(harnais_a, force=force)
        _, cle_b = self.noter_examen(harnais_b)
        ra = {r["id"]: r for r in lire_json(os.path.join(self.dossier_prive, f"examen-{cle_a}.json"))}
        rb = {r["id"]: r for r in lire_json(os.path.join(self.dossier_prive, f"examen-{cle_b}.json"))}
        pa = bareme.noter_passage(list(ra.values()))
        pb = bareme.noter_passage(list(rb.values()))
        mieux = sum(1 for i in ra if bareme.point(ra[i]["etat"]) > bareme.point(rb[i]["etat"]))
        pire = sum(1 for i in ra if bareme.point(ra[i]["etat"]) < bareme.point(rb[i]["etat"]))
        return {
            "note_candidat": pa["note"],
            "note_reference": pb["note"],
            "gain": round(pa["note"] - pb["note"], 2),
            "interdites_candidat": pa["interdites"],
            "interdites_reference": pb["interdites"],
            "cas_meilleurs": mieux,
            "cas_pires": pire,
            "par_critere_candidat": {k: round(v["taux"] * 100, 1) for k, v in pa["par_critere"].items()},
        }
