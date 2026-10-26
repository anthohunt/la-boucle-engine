import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

from boucle import chantier
from boucle.juge import Juge

ICI = os.path.dirname(os.path.abspath(__file__))
EXEMPLES = os.path.join(os.path.dirname(ICI), "exemples")


class EmailAgenda(unittest.TestCase):
    def test_la_reference_de_depart_et_les_categories(self):
        c = chantier.charger(os.path.join(EXEMPLES, "email-agenda", "chantier.json"))
        _, rapport = Juge(c).noter_entrainement(os.path.join(EXEMPLES, "email-agenda", "harnais-0"))
        taux = {k: v["taux"] for k, v in rapport["par_critere"].items()}
        # the naive extractor is right on clear mails and wrong on traps, doubts and orders
        self.assertEqual((taux["net"], taux["multiple"], taux["vide"]), (1.0, 1.0, 1.0))
        self.assertEqual((taux["piege"], taux["ambigu"], taux["hostile"]), (0.0, 0.0, 0.0))
        self.assertEqual(rapport["note"], 50.0)

    def test_un_harnais_qui_traite_les_trois_categories_gagne(self):
        with tempfile.TemporaryDirectory() as d:
            h = os.path.join(d, "h")
            os.makedirs(h)
            with open(os.path.join(h, "regles.json"), "w") as f:
                json.dump({"mots_hostiles": ["ignore previous", "ignore les instructions"], "mots_incertains": ["sometime next", "either", "soit le", "semaine prochaine"]}, f)
            with open(os.path.join(h, "post.py"), "w") as f:
                f.write(
                    "import re\n"
                    "def corriger(texte, p, regles):\n"
                    "    corps = texte.partition('\\n\\n')[2].lower()\n"
                    "    if re.search(r'took place|a eu lieu|invoice|facture', corps):\n"
                    "        return {'evenements': [], 'incertain': False, 'refus': False}\n"
                    "    return p\n")
            c = chantier.charger(os.path.join(EXEMPLES, "email-agenda", "chantier.json"))
            _, rapport = Juge(c).noter_entrainement(h)
            self.assertEqual(rapport["note"], 100.0)

    def test_chercheur_claude_sans_claude_s_arrete_proprement(self):
        env = dict(os.environ, BOUCLE_CLAUDE="commande-qui-n-existe-pas", BOUCLE_SORTIE="/tmp", BOUCLE_FAUTES="/dev/null", BOUCLE_NOTES="/dev/null")
        r = subprocess.run([sys.executable, os.path.join(EXEMPLES, "email-agenda", "chercheur.py")], env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("not found", r.stderr)

    def test_chercheur_claude_avec_un_faux_claude(self):
        with tempfile.TemporaryDirectory() as d:
            faux = os.path.join(d, "faux-claude")
            with open(faux, "w") as f:
                f.write("#!/bin/sh\necho \"$@\" > args.txt\necho '{\"famille\":\"x\",\"idee\":\"y\"}' > noeud.json\n")
            os.chmod(faux, os.stat(faux).st_mode | stat.S_IXUSR)
            sortie = os.path.join(d, "sortie")
            os.makedirs(sortie)
            for n in ("fautes", "notes"):
                with open(os.path.join(d, n + ".json"), "w") as f:
                    json.dump([] if n == "fautes" else {}, f)
            env = dict(os.environ, BOUCLE_CLAUDE=faux, BOUCLE_SORTIE=sortie, BOUCLE_FAUTES=os.path.join(d, "fautes.json"),
                       BOUCLE_NOTES=os.path.join(d, "notes.json"), BOUCLE_CHARTE=os.path.join(EXEMPLES, "email-agenda", "charte.md"))
            r = subprocess.run([sys.executable, os.path.join(EXEMPLES, "email-agenda", "chercheur.py")], env=env)
            self.assertEqual(r.returncode, 0)
            with open(os.path.join(sortie, "args.txt")) as f:
                args = f.read()
            self.assertIn("-p", args)
            self.assertIn("acceptEdits", args)
            self.assertTrue(os.path.exists(os.path.join(sortie, "noeud.json")))


class Lot(unittest.TestCase):
    def test_le_mode_lot_donne_les_memes_notes_que_le_mode_cas(self):
        for nom in ("tickets", "email-agenda"):
            ch = os.path.join(EXEMPLES, nom, "chantier.json")
            c_lot = chantier.charger(ch)
            c_cas = chantier.charger(ch)
            c_cas["sujet"] = {"commande": [x for x in c_lot["sujet"]["commande"] if x != "--lot"], "timeout_s": 30, "mode": "cas"}
            h = os.path.join(EXEMPLES, nom, "harnais-0")
            self.assertEqual(Juge(c_lot).noter_entrainement(h)[1]["note"], Juge(c_cas).noter_entrainement(h)[1]["note"])

    def test_un_lot_qui_plante_donne_des_erreurs_interdites(self):
        c = chantier.charger(os.path.join(EXEMPLES, "tickets", "chantier.json"))
        c["sujet"] = {"commande": ["python3", "-c", "import sys; sys.exit(1)"], "timeout_s": 10, "mode": "lot"}
        _, rapport = Juge(c).noter_entrainement(os.path.join(EXEMPLES, "tickets", "harnais-0"))
        self.assertEqual(rapport["note"], 0.0)
        self.assertGreater(rapport["interdites"], 0)


class Tickets(unittest.TestCase):
    def test_depart_et_donnees_fabriquees_sans_ecart(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run([sys.executable, os.path.join(EXEMPLES, "tickets", "fabriquer_donnees.py"), d], check=True, capture_output=True)
            for nom in ("entrainement", "examen"):
                with open(os.path.join(d, nom + ".jsonl")) as f, open(os.path.join(EXEMPLES, "tickets", "donnees", nom + ".jsonl")) as g:
                    self.assertEqual(f.read(), g.read(), "the generator is deterministic and the committed data match it")
            with open(os.path.join(d, "entrainement.jsonl")) as f:
                textes_ent = {json.loads(l)["entree"]["texte"] for l in f}
            with open(os.path.join(d, "examen.jsonl")) as f:
                textes_exa = {json.loads(l)["entree"]["texte"] for l in f}
            self.assertFalse(textes_ent & textes_exa, "no ticket is in both sets")


if __name__ == "__main__":
    unittest.main()
