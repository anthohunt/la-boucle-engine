import json
import os
import stat
import tempfile
import unittest

from boucle import banc, bareme, chantier, comparateurs
from boucle.juge import Juge
from boucle.moteur import Moteur, SORTIE_ARRET, SORTIE_OK, SORTIE_PAUSE
from boucle.util import lire_json
from tests.aide import fabriquer


class Banc(unittest.TestCase):
    def test_scelle_et_detecte_une_modification(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "b.jsonl")
            with open(p, "w") as f:
                f.write(json.dumps({"id": "a", "critere": "x", "entree": 1, "corrige": 2}) + "\n")
            sceau = banc.sceller(p)
            self.assertEqual(sceau["nombre"], 1)
            self.assertEqual(len(banc.verifier(p)), 1)
            with open(p, "a") as f:
                f.write(json.dumps({"id": "b", "critere": "x", "entree": 1, "corrige": 3}) + "\n")
            with self.assertRaises(ValueError):
                banc.verifier(p)

    def test_refuse_identifiant_double_et_cle_manquante(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "b.jsonl")
            ligne = json.dumps({"id": "a", "critere": "x", "entree": 1, "corrige": 2})
            with open(p, "w") as f:
                f.write(ligne + "\n" + ligne + "\n")
            with self.assertRaises(ValueError):
                banc.charger(p)
            with open(p, "w") as f:
                f.write(json.dumps({"id": "a"}) + "\n")
            with self.assertRaises(ValueError):
                banc.charger(p)


class Bareme(unittest.TestCase):
    def test_taux_par_critere_et_moyenne_des_criteres(self):
        res = [{"id": i, "critere": "a", "etat": "reussi"} for i in range(9)] + [{"id": 9, "critere": "a", "etat": "tolere"}]
        res += [{"id": 10, "critere": "b", "etat": "interdit"}]
        r = bareme.noter_passage(res)
        self.assertEqual(r["par_critere"]["a"]["taux"], 0.9)
        self.assertEqual(r["note"], 45.0)  # (0.9 + 0.0) / 2
        self.assertEqual(r["interdites"], 1)

    def test_une_erreur_toleree_n_est_pas_une_reussite(self):
        r = bareme.noter_passage([{"id": 1, "critere": "a", "etat": "tolere"}])
        self.assertEqual(r["note"], 0.0)


class Comparateurs(unittest.TestCase):
    def test_egalite_matrice_et_illisible(self):
        f = comparateurs.charger({"nom": "egalite", "options": {"cle": "e", "matrice": {"a|b": "interdit"}}}, ".")
        self.assertEqual(f({"e": "a"}, {"e": "a"}, "c"), "reussi")
        self.assertEqual(f({"e": "b"}, {"e": "a"}, "c"), "interdit")
        self.assertEqual(f({"e": "c"}, {"e": "a"}, "c"), "tolere")
        self.assertEqual(f(None, {"e": "a"}, "c"), "interdit")  # silence is never a success

    def test_comparateur_inconnu(self):
        with self.assertRaises(ValueError):
            comparateurs.charger({"nom": "nope"}, ".")


class Juge_(unittest.TestCase):
    def test_arret_sequentiel_elague_un_enfant_certainement_pire(self):
        with tempfile.TemporaryDirectory() as d:
            c = chantier.charger(fabriquer(d, n=100, seuil_depart=50))
            j = Juge(c)
            parent = os.path.join(d, "harnais-0")
            res, rapport = j.noter_entrainement(parent)
            self.assertEqual(rapport["note"], 100.0)
            os.makedirs(os.path.join(d, "enfant"))
            with open(os.path.join(d, "enfant", "regle.json"), "w") as f:
                json.dump({"seuil": 99}, f)
            avant = j.mesures
            res2, rapport2, tot, est = j.mesure_sequentielle(os.path.join(d, "enfant"), {r["id"]: r for r in res})
            self.assertTrue(tot)
            self.assertIsNone(rapport2)
            self.assertLess(j.mesures - avant, 100)

    def test_enfant_identique_est_mesure_en_entier(self):
        with tempfile.TemporaryDirectory() as d:
            c = chantier.charger(fabriquer(d, n=40, seuil_depart=50))
            j = Juge(c)
            res, _ = j.noter_entrainement(os.path.join(d, "harnais-0"))
            _, rapport, tot, _ = j.mesure_sequentielle(os.path.join(d, "harnais-0"), {r["id"]: r for r in res})
            self.assertFalse(tot)
            self.assertEqual(rapport["note"], 100.0)

    def test_resultats_d_examen_prives(self):
        with tempfile.TemporaryDirectory() as d:
            c = chantier.charger(fabriquer(d, n=20))
            j = Juge(c)
            rapport, cle = j.noter_examen(os.path.join(d, "harnais-0"))
            self.assertEqual(rapport["nombre"], 20)
            mode = stat.S_IMODE(os.stat(os.path.join(d, ".juge")).st_mode)
            self.assertEqual(mode, 0o700)
            fichier = os.path.join(d, ".juge", f"examen-{cle}.json")
            self.assertEqual(stat.S_IMODE(os.stat(fichier).st_mode), 0o600)

    def test_examen_modifie_apres_scellement_est_refuse(self):
        with tempfile.TemporaryDirectory() as d:
            c = chantier.charger(fabriquer(d, n=20))
            with open(os.path.join(d, "donnees", "examen.jsonl"), "a") as f:
                f.write(json.dumps({"id": "z", "critere": "bas", "entree": {"id": "z", "x": 1}, "corrige": {"e": "small"}}) + "\n")
            with self.assertRaises(ValueError):
                Juge(c).noter_examen(os.path.join(d, "harnais-0"))


class Moteur_(unittest.TestCase):
    def test_atteint_l_objectif(self):
        with tempfile.TemporaryDirectory() as d:
            c = chantier.charger(fabriquer(d, mode="honnete", n=80, seuil_depart=10))
            code = Moteur(c, sortie=lambda *a: None).run()
            self.assertEqual(code, SORTIE_OK)
            etat = lire_json(os.path.join(d, "etat.json"))
            self.assertGreaterEqual(etat["note_examen_meilleure"], 95.0)
            self.assertEqual(etat["statut"], "objectif_atteint")

    def test_deux_echecs_a_l_examen_mettent_en_pause(self):
        with tempfile.TemporaryDirectory() as d:
            # the researcher memorizes the training answers: training soars, the exam does not move
            c = chantier.charger(fabriquer(d, mode="memorise", n=60, seuil_depart=10, extra={"familles": {"impasse_apres": 9}}))
            code = Moteur(c, sortie=lambda *a: None).run()
            self.assertEqual(code, SORTIE_PAUSE)
            self.assertTrue(os.path.exists(os.path.join(d, "PAUSE.md")))
            # it never retries by itself
            self.assertEqual(Moteur(c, sortie=lambda *a: None).run(), SORTIE_PAUSE)
            etat = lire_json(os.path.join(d, "etat.json"))
            self.assertEqual(etat["meilleure_version"], "n0000")

    def test_chercheur_en_panne_arrete_la_boucle(self):
        with tempfile.TemporaryDirectory() as d:
            c = chantier.charger(fabriquer(d, extra={"chercheur": {"commande": ["python3", "inexistant.py"], "timeout_s": 5}}))
            self.assertEqual(Moteur(c, sortie=lambda *a: None).run(), SORTIE_ARRET)
            etat = lire_json(os.path.join(d, "etat.json"))
            self.assertEqual(etat["statut"], "chercheur_en_panne")

    def test_chercheur_sans_changement_n_est_pas_mesure(self):
        with tempfile.TemporaryDirectory() as d:
            c = chantier.charger(fabriquer(d, mode="rien", n=30, extra={"passes_max": 1}))
            m = Moteur(c, sortie=lambda *a: None)
            self.assertEqual(m.run(), SORTIE_ARRET)
            etats = {n["statut"] for n in m.etat["noeuds"].values()}
            self.assertIn("sans_changement", etats)

    def test_reprise_apres_arret(self):
        with tempfile.TemporaryDirectory() as d:
            c = chantier.charger(fabriquer(d, mode="honnete", n=60, extra={"passes_max": 1, "objectif": {"examen_min": 100.0}}))
            Moteur(c, sortie=lambda *a: None).run()
            n1 = len(lire_json(os.path.join(d, "etat.json"))["noeuds"])
            c["passes_max"] = 3
            Moteur(c, sortie=lambda *a: None).run()
            n2 = len(lire_json(os.path.join(d, "etat.json"))["noeuds"])
            self.assertGreater(n2, n1)

    def test_le_chercheur_ne_recoit_aucun_cas_d_examen(self):
        with tempfile.TemporaryDirectory() as d:
            c = chantier.charger(fabriquer(d, mode="honnete", n=40, extra={"passes_max": 1}))
            with open(os.path.join(d, "chercheur.py"), "a") as f:
                f.write(textwrap_espion())
            Moteur(c, sortie=lambda *a: None).run()
            with open(os.path.join(d, "espion.txt")) as fh:
                vu = fh.read()
            self.assertNotIn("examen", vu.replace("examen_agrege_par_critere", ""))


def textwrap_espion():
    return '''
import glob
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "espion.txt"), "a") as f:
    f.write(open(os.environ["BOUCLE_FAUTES"]).read())
    f.write(open(os.environ["BOUCLE_NOTES"]).read())
'''


if __name__ == "__main__":
    unittest.main()
