# The chantier file

```json
{
  "nom": "tickets",
  "banc": {"entrainement": "donnees/entrainement.jsonl", "examen": "donnees/examen.jsonl"},
  "harnais_depart": "harnais-0",
  "sujet": {"commande": ["python3", "sujet.py"], "timeout_s": 60},
  "comparateur": {"nom": "egalite", "options": {"cle": "etiquette", "matrice": {"urgent|rien": "interdit"}, "defaut": "tolere"}},
  "chercheur": {"commande": ["python3", "chercheur.py"], "timeout_s": 600},
  "parallelisme": 4,
  "largeur": 3,
  "tours_niveau1_max": 6,
  "passes_max": 6,
  "paliers": {"mode": "fixes", "valeurs": [20, 40, 60, 80, 100]},
  "sequentiel": {"actif": true, "tranche": 20, "alpha": 0.05},
  "examen": {"gain_min": 5.0, "echecs_max": 2, "confirmation": true, "interdites_non_croissantes": true},
  "objectif": {"examen_min": 90.0},
  "familles": {"impasse_apres": 3, "plateau_apres": 2},
  "charte": null,
  "budget": {"mesures_max": null}
}
```

| Key | Meaning |
|---|---|
| `sujet.mode` | `cas` (default): one process per case. `lot`: one process per group of cases, JSON lines in and out (see `docs/interface.md`) |
| `largeur` | children developed per round at level 1 |
| `tours_niveau1_max` | rounds of level 1 per pass before the pass gives up |
| `paliers` | the steps a child must reach to go to the exam. `fixes`: the next value of the list above the best training mark. `relatif`: `{"mode":"relatif","pas":20}` = best mark + 20 |
| `sequentiel` | early pruning of a child that is certainly worse than its parent (Hoeffding bound valid at every look, risk `alpha`); slices of `tranche` cases in a secret random order. The exam is never cut short |
| `examen.gain_min` | points (out of 100) the candidate must win by on the exam |
| `examen.echecs_max` | failures in a row before the pause |
| `examen.confirmation` | run the exam a second time; the smaller gain counts (useful when the subject is not deterministic) |
| `familles.impasse_apres` | a family of ideas with that many tries in a row without progress is stuck: its next children are discarded unless they carry a `justification` |
| `familles.plateau_apres` | passes without progress after which the researcher is asked for a structurally different approach (`BOUCLE_DIVERGENCE=1`) |
| `budget.mesures_max` | hard cap on subject calls |

The mark is out of 100: the mean, over categories, of the success rate of the category (a tolerated
error is not a success; forbidden errors are counted next to the mark, never inside it).
