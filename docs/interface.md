# Public interface of la-boucle-engine

Python ≥ 3.10, standard library only. Command: `python3 -m boucle <command>` (run it from the
repository root, or install with `pip install git+https://github.com/anthohunt/la-boucle-engine`
and run `python3 -m boucle`).

## Commands
| Command | What it does |
|---|---|
| `python3 -m boucle sceller <bench.jsonl>` | seals a bench: writes `<bench>.sceau` (SHA-256, size, cases per category) |
| `python3 -m boucle verifier <chantier.json>` | checks the chantier file and that both benches still match their seals |
| `python3 -m boucle noter <chantier.json> <harness-folder> [--examen]` | marks one harness; with `--examen` prints aggregates only |
| `python3 -m boucle run <chantier.json>` | runs or resumes the loop. Exit code: `0` goal reached, `3` pause (two exam failures in a row, see `PAUSE.md`), `4` stopped (passes or budget exhausted), `1` error |
| `python3 -m boucle tableau <chantier.json>` | writes `tableau.html` (static page, no network) |

## Files of a chantier (all paths relative to the chantier file)
• `chantier.json`: settings, see `docs/chantier.md`. Required: `sujet.commande`, `chercheur.commande`.
• `donnees/entrainement.jsonl`, `donnees/examen.jsonl`: one case per line `{"id","critere","entree","corrige"}`; both sealed.
• `harnais-0/`: the starting harness (any folder; the subject reads it).
• Written by the loop: `etat.json` (resumable state), `journal.jsonl` (one event per line), `noeuds/nXXXX/` (one harness per tree node, with `mesures-entrainement.json`), `tableau.html`, `PAUSE.md`, `.juge/` (private exam results, mode 600).

## Protocols
**Subject** (the thing being improved): a command started once per case. Stdin: `{"harnais": "<abs folder>", "entree": <case input>}`. Stdout: the proposal, as JSON. A crash or unreadable output is `null`, which is a *forbidden error* by default.
**Subject, batch mode** (`"sujet": {"mode": "lot"}`): the command is started once per group of cases (at most `parallelisme` processes per measurement). Stdin: one JSON per line `{"id","harnais","entree"}`; stdout: one JSON per line `{"id","proposition"}`. A missing id counts as `null`. Use it when starting the subject is expensive (loading a model). `timeout_s` then applies to a whole group.
**Comparator**: built-in `egalite` (options `cle`, `matrice`, `defaut`, `illisible`), or your own file with `comparer(proposition, corrige, critere, options) -> "reussi" | "tolere" | "interdit"`.
**Researcher**: a command started once per child from the chantier folder; `BOUCLE_SORTIE` is a writable copy of the parent harness. It reads its inputs from `BOUCLE_*` environment variables (training mistakes, aggregated marks, charter, stuck families, …; full list in `boucle/chercheur.py`) and writes `noeud.json` `{"famille","idee"}`. It never receives an exam case.

## Guarantees
• The exam bench is read by the judge only; the researcher gets aggregated per-category marks of the best version.
• An exam bench modified after sealing is refused.
• A candidate reaches the exam only after beating the next *palier* on the training set; it must then win by `examen.gain_min` points, confirmed by a second run, without more forbidden errors.
• Two exam failures in a row stop the loop (`PAUSE.md`); it never retries by itself.
• Not a sandbox: run an untrusted researcher in a container.
