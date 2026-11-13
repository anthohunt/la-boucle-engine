"""Small helpers shared by the modules: JSON files, atomic writes, hashing, clock."""

import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone


def maintenant():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def lire_json(chemin, defaut=None):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return defaut


def ecrire_json(chemin, objet):
    """Atomic write: a reader never sees a half-written file."""
    dossier = os.path.dirname(os.path.abspath(chemin))
    os.makedirs(dossier, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dossier, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(objet, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, chemin)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def ajouter_jsonl(chemin, objet):
    os.makedirs(os.path.dirname(os.path.abspath(chemin)), exist_ok=True)
    with open(chemin, "a", encoding="utf-8") as f:
        f.write(json.dumps(objet, ensure_ascii=False, sort_keys=True) + "\n")


def lire_jsonl(chemin):
    try:
        with open(chemin, encoding="utf-8") as f:
            return [json.loads(ligne) for ligne in f if ligne.strip()]
    except FileNotFoundError:
        return []


def sha256_octets(donnees):
    return hashlib.sha256(donnees).hexdigest()


def sha256_fichier(chemin):
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def empreinte_dossier(dossier):
    """Stable hash of a harness folder: names and contents, sorted."""
    h = hashlib.sha256()
    for racine, sous, fichiers in os.walk(dossier):
        sous.sort()
        for nom in sorted(fichiers):
            if nom in ("noeud.json", "mesures-entrainement.json"):
                continue
            chemin = os.path.join(racine, nom)
            h.update(os.path.relpath(chemin, dossier).encode())
            h.update(b"\0")
            with open(chemin, "rb") as f:
                h.update(f.read())
            h.update(b"\0")
    return h.hexdigest()


def commande_portable(commande):
    """On Windows, "python3" is often missing or a Store stub: run the same interpreter as the engine instead.
    Elsewhere the command is left as written."""
    commande = list(commande)
    if os.name == "nt" and commande and commande[0] in ("python3", "python"):
        commande[0] = sys.executable
    return commande


def env_enfant(env=None):
    """Children speak UTF-8 on every platform (Windows pipes default to the local code page)."""
    env = dict(os.environ if env is None else env)
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env
