#!/usr/bin/env python3
"""Researcher of the email -> agenda example: an AI agent (Claude Code in print mode).

It is the real thing: it calls a paid model. It needs the `claude` command installed and logged in
(https://docs.anthropic.com/en/docs/claude-code). Without it the script stops with a clear message
and exit code 2: everything that comes before (benches, subject, judge, marks) still works.

Environment: the BOUCLE_* variables of the loop (see boucle/chercheur.py), plus
  BOUCLE_CLAUDE   command to run (default: claude)
  BOUCLE_MODELE   model name passed with --model (default: the Claude Code default)
"""
import json
import os
import shutil
import subprocess
import sys

MAX_FAUTES = 12


def main():
    commande = os.environ.get("BOUCLE_CLAUDE", "claude")
    if shutil.which(commande) is None:
        print(f"researcher: '{commande}' not found. Install Claude Code and log in, or replace this command "
              "in chantier.json (chercheur.commande) by your own researcher.", file=sys.stderr)
        return 2
    sortie = os.environ["BOUCLE_SORTIE"]
    with open(os.environ["BOUCLE_FAUTES"], encoding="utf-8") as f:
        fautes = json.load(f)[:MAX_FAUTES]
    with open(os.environ["BOUCLE_NOTES"], encoding="utf-8") as f:
        notes = json.load(f)
    charte = ""
    if os.environ.get("BOUCLE_CHARTE"):
        with open(os.environ["BOUCLE_CHARTE"], encoding="utf-8") as f:
            charte = f.read()
    consigne = (
        f"{charte}\n\n# This round\n"
        f"Harness folder (your working directory): {sortie}\n"
        f"Next step to reach on the training set: {os.environ.get('BOUCLE_PALIER')}\n"
        f"Stuck families (do not retry): {os.environ.get('BOUCLE_IMPASSE') or 'none'}\n"
        f"Families already tried: {os.environ.get('BOUCLE_FAMILLES') or 'none'}\n"
        f"Plateau, propose something structurally different: {os.environ.get('BOUCLE_DIVERGENCE') == '1'}\n"
        f"Marks: {json.dumps(notes, ensure_ascii=False)}\n\n"
        f"Mistakes of the parent harness on the training mails (first {MAX_FAUTES}):\n"
        f"{json.dumps(fautes, ensure_ascii=False, indent=1)}\n\n"
        "Make ONE improvement, then write noeud.json. Do not run the loop yourself."
    )
    cmd = [commande, "-p", consigne, "--permission-mode", "acceptEdits", "--allowedTools", "Read,Edit,Write"]
    if os.environ.get("BOUCLE_MODELE"):
        cmd += ["--model", os.environ["BOUCLE_MODELE"]]
    return subprocess.run(cmd, cwd=sortie).returncode


if __name__ == "__main__":
    sys.exit(main())
