"""A self-contained HTML dashboard (no network, no script) built from etat.json and journal.jsonl."""

import html
import os

from .util import lire_json, lire_jsonl


def _svg_courbe(points, hauteur=160, largeur=640):
    """points: list of (label, value 0..100). Returns an inline SVG polyline."""
    if not points:
        return ""
    marge = 28
    n = max(1, len(points) - 1)
    xs = [marge + (largeur - 2 * marge) * i / n for i in range(len(points))]
    ys = [hauteur - marge - (hauteur - 2 * marge) * v / 100.0 for _, v in points]
    ligne = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    grille = "".join(
        f'<line x1="{marge}" x2="{largeur - marge}" y1="{hauteur - marge - (hauteur - 2 * marge) * g / 100:.1f}" '
        f'y2="{hauteur - marge - (hauteur - 2 * marge) * g / 100:.1f}" stroke="#ddd"/>'
        f'<text x="2" y="{hauteur - marge - (hauteur - 2 * marge) * g / 100 + 4:.1f}" font-size="10" fill="#666">{g}</text>'
        for g in (0, 50, 100)
    )
    pts = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#2563eb"><title>{html.escape(l)}: {v}</title></circle>' for (l, v), x, y in zip(points, xs, ys))
    return (f'<svg viewBox="0 0 {largeur} {hauteur}" width="100%" role="img" aria-label="training mark per measured node">{grille}'
            f'<polyline fill="none" stroke="#2563eb" stroke-width="2" points="{ligne}"/>{pts}</svg>')


def construire(racine):
    etat = lire_json(os.path.join(racine, "etat.json"))
    if etat is None:
        raise ValueError("no etat.json: run the loop first")
    journal = lire_jsonl(os.path.join(racine, "journal.jsonl"))
    noeuds = sorted(etat["noeuds"].values(), key=lambda n: n["id"])
    courbe = [(n["id"], n["note_entrainement"]) for n in noeuds if n["note_entrainement"] is not None]
    lignes = "".join(
        "<tr><td>{id}</td><td>{p}</td><td>{f}</td><td>{i}</td><td>{s}</td><td>{e}</td><td>{x}</td></tr>".format(
            id=n["id"], p=n["parent"] or "", f=html.escape(n["famille"]), i=html.escape(n["idee"]), s=n["statut"],
            e="" if n["note_entrainement"] is None else n["note_entrainement"],
            x="" if n.get("note_examen") is None else n["note_examen"],
        )
        for n in noeuds
    )
    exams = "".join(
        "<tr><td>{n}</td><td>{g:+.1f}</td><td>{ok}</td></tr>".format(n=e["noeud"], g=e["gain"], ok="accepted" if e["accepte"] else "refused")
        for e in journal if e.get("evenement") == "examen"
    )
    familles = "".join(
        "<tr><td>{n}</td><td>{e}</td><td>{s}</td><td>{i}</td></tr>".format(n=html.escape(k), e=v["essais"], s=v["sans_progres"], i="stuck" if v["impasse"] else "")
        for k, v in sorted(etat["familles"].items())
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(etat['nom'])}: loop dashboard</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:860px;margin:2rem auto;padding:0 1rem;color:#111}}
table{{border-collapse:collapse;width:100%;margin:.5rem 0 1.5rem}}td,th{{border-bottom:1px solid #e5e5e5;padding:.3rem .5rem;text-align:left}}
.k{{display:inline-block;margin-right:2rem}}.k b{{font-size:1.6rem;display:block}}</style></head><body>
<h1>{html.escape(etat['nom'])}</h1>
<p><span class="k"><b>{etat['note_examen_meilleure']}</b>exam mark, best version {etat['meilleure_version']}</span>
<span class="k"><b>{etat['echecs_examen']}</b>exam failures in a row</span>
<span class="k"><b>{html.escape(etat['statut'])}</b>status</span></p>
<h2>Training mark per measured node</h2>{_svg_courbe(courbe)}
<h2>Nodes</h2><table><tr><th>node</th><th>parent</th><th>family</th><th>idea</th><th>status</th><th>training</th><th>exam</th></tr>{lignes}</table>
<h2>Exams</h2><table><tr><th>candidate</th><th>gain</th><th>decision</th></tr>{exams}</table>
<h2>Families of ideas</h2><table><tr><th>family</th><th>tries</th><th>tries without progress</th><th></th></tr>{familles}</table>
</body></html>"""


def ecrire(racine, sortie=None):
    sortie = sortie or os.path.join(racine, "tableau.html")
    with open(sortie, "w", encoding="utf-8") as f:
        f.write(construire(racine))
    return sortie
