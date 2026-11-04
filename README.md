# la-boucle-engine

**La boucle** ("the loop") is a small method, and this is its engine: an agent improves a *harness*
(prompts, rules, code around a model or a program) by trying changes on a **training set**, while a
**sealed exam** that the agent never sees decides whether an improvement is real.

```
researcher agent ──edits──▶ harness copy ──marked on──▶ training set (mistakes visible)
                                                  │ reaches the next step
                                                  ▼
                       judge ──compares with the best version on──▶ SEALED EXAM (never shown)
                                                  │ wins by N points, twice, no more forbidden errors
                                                  ▼
                                           new best version
                      two exam failures in a row ──▶ PAUSE: a human reviews the method
```

Standard library only (Python ≥ 3.10). No model is bundled: the *researcher* is any command (a script, or an
AI agent such as Claude Code), the *subject* is any command. The examples run with scripted researchers,
so you can see the whole loop without an API key.

> Code identifiers and comments are in French (the project's origin), the documentation is in English.

## What you get
- **Benches** as JSONL, sealed by a SHA-256 fingerprint; a changed exam is refused.
- **Three outcomes per case** (right / tolerated error / forbidden error), categories with equal weight.
- **A tree of attempts** with early pruning (a Hoeffding bound valid at every look), steps (*paliers*), families of ideas with stuck-family detection and a plateau alarm.
- **An exam gate**: paired comparison with the best version, minimum gain, a second confirming run, no more forbidden errors.
- **Pause after two exam failures**; resumable state; a journal of every step; a static HTML dashboard.
- Method notes in [`docs/method.md`](docs/method.md); public interface in [`docs/interface.md`](docs/interface.md); chantier settings in [`docs/chantier.md`](docs/chantier.md).

## Install
```bash
git clone https://github.com/anthohunt/la-boucle-engine && cd la-boucle-engine
python3 -m unittest discover -s tests -t .      # 23 tests, under a minute
# optional: pip install .   (installs the `boucle` package; nothing else)
```

## Run the first example (no API key, no model)
Invented support tickets, three labels, five categories. The starting harness is one rule; a scripted
researcher stands in for an AI agent.
```bash
cp -r exemples/tickets /tmp/tickets && cd /tmp/tickets      # work on a copy: the loop writes files next to chantier.json
PYTHONPATH=<path to this repository> python3 -m boucle verifier chantier.json
PYTHONPATH=<path to this repository> python3 -m boucle run chantier.json      # exit 0 = goal reached
PYTHONPATH=<path to this repository> python3 -m boucle tableau chantier.json  # writes tableau.html
```
Typical outcome: the exam mark climbs from 42 to the high 80s or 90s over several passes. The path varies from run to run (the early-pruning order is random): in the installation proof of this repository (6 passes) it ended at 88 with "passes exhausted" (exit code 4); in other runs it reached the goal of 90 (exit code 0). `journal.jsonl` has one line per step.

## Run it with a real AI researcher
`exemples/email-agenda/` is a second case (mails → appointments, six categories: clear, empty, trap,
multiple, ambiguous, hostile). Its researcher calls [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
in print mode, which is a paid product subject to Anthropic's terms:
```bash
cp -r exemples/email-agenda /tmp/mails && cd /tmp/mails
PYTHONPATH=<repo> python3 -m boucle noter chantier.json harnais-0            # starting mark: 50, free
PYTHONPATH=<repo> python3 -m boucle run chantier.json                         # needs `claude` installed and logged in
```
Without `claude`, the researcher stops with a clear message and everything before it still works. The
real-model run has **not** been performed for this repository: only the surrounding code is tested (with a stand-in `claude`).

## Make your own chantier
1. Write two benches (`donnees/entrainement.jsonl`, `donnees/examen.jsonl`): `{"id","critere","entree","corrige"}` per line. Seal them: `python3 -m boucle sceller donnees/examen.jsonl`.
2. Write the subject: a command that reads `{"harnais","entree"}` on stdin and prints its proposal as JSON.
3. Choose a comparator (`egalite` with a mistake matrix, or your own `comparateur.py`).
4. Write the researcher command (and a charter for it).
5. `python3 -m boucle verifier chantier.json`, then `run`.

## Related repositories (planned)
`la-boucle-module` (a Claude Code module that drives a chantier step by step), `la-boucle-methode` (skills that teach the method
to an agent), `mission-loop` (a goal-driven iteration skill), `la-boucle-cas-jeu-de-plis` (a case study on a card-game bot).
They depend on this engine and do not copy it.

## Layout
```
boucle/        the engine (banc, bareme, comparateurs, juge, chercheur, moteur, tableau, CLI)
docs/          method, interface, chantier settings
exemples/      tickets (scripted researcher) and email-agenda (AI researcher)
tests/         unit and end-to-end tests (stand-in subjects and researchers)
```

## Limits (read before trusting a number)
- The exam is hidden by convention, not by a sandbox: run an untrusted researcher in a container.
- A good exam mark means "generalises to an exam like this one". Rebuild the exam when the real traffic changes.
- The examples are small and synthetic, written to show the mechanics, not to benchmark anything.
- This is a first public version (0.1.0); the interfaces may still change.

## Licences
Code: Apache License 2.0 ([`LICENSE`](LICENSE), [`NOTICE`](NOTICE)). Documentation, example data and charters: CC BY 4.0
([`LICENSE-docs`](LICENSE-docs)). No third-party code is included; no runtime dependency.
Inspiration (no code copied): [karpathy/autoresearch](https://github.com/karpathy/autoresearch) (MIT).
