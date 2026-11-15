"""Vérifie les notebooks sans navigateur : exécute leurs cellules de code, puis appelle chaque fonction
d'affichage avec toutes les combinaisons des menus. Les erreurs levées dans un widget (invisibles
pour `jupyter nbconvert --execute`) font ainsi échouer la vérification.

    docker compose --profile notebooks run --rm notebooks python verifier.py
"""
from __future__ import annotations

import itertools
import json
import random
import sys
import time
import traceback
from pathlib import Path

import ipywidgets as w
import plotly.graph_objects as go
import IPython.display as ipd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Pas de rendu : on veut seulement savoir si le code tourne et construit les figures.
go.Figure.show = lambda self, *a, **k: None
ipd.display = lambda *a, **k: None


def _values(widget):
    return [v for _, v in widget.options] if isinstance(widget.options[0], tuple) else list(widget.options)


def _fake_interact(f, **controls):
    _fake_interact.calls.append((f, controls))


def _fake_output(f, controls):
    _fake_interact.calls.append((f, controls))
    return w.Output()


def run_notebook(path: Path, max_combos: int = 400) -> list[str]:
    errors = []
    _fake_interact.calls = []
    w.interact, w.interactive_output = _fake_interact, _fake_output
    ns = {"__name__": "__notebook__"}
    cells = [c for c in json.loads(path.read_text(encoding="utf-8"))["cells"] if c["cell_type"] == "code"]
    for i, c in enumerate(cells):
        src = "".join(c["source"])
        try:
            exec(compile(src, f"{path.name}[{i}]", "exec"), ns)
        except Exception:  # noqa: BLE001
            errors.append(f"{path.name} cellule {i} :\n{traceback.format_exc(limit=3)}")
    n = 0
    for f, controls in _fake_interact.calls:
        keys = list(controls)
        grids = []
        for k in keys:
            c = controls[k]
            if isinstance(c, w.Checkbox):
                grids.append([True, False])
            elif k == "fichier" and "fichiers" in ns:  # toutes les couches de tous les indicateurs
                grids.append(sorted({f for d in ns["LAYERS"].iterdir() if d.is_dir() for f in ns["fichiers"](d.name)}))
            elif isinstance(c, w.Dropdown):
                grids.append(_values(c))
            else:
                grids.append([c.value])
        combos = [dict(zip(keys, c)) for c in itertools.product(*grids)]
        # menus dépendants (notebook 03) : la couche doit appartenir à l'indicateur choisi
        combos = [kw for kw in combos
                  if not ("fichier" in kw and "fichiers" in ns and kw["fichier"] not in ns["fichiers"](kw["ind"]))]
        if len(combos) > max_combos:  # échantillon reproductible
            combos = random.Random(0).sample(combos, max_combos)
        for kw in combos:
            n += 1
            try:
                f(**kw)
            except Exception:  # noqa: BLE001
                errors.append(f"{path.name} {f.__name__}({kw}) :\n{traceback.format_exc(limit=3)}")
    print(f"{path.name} : {len(cells)} cellules, {n} combinaisons de menus, {len(errors)} erreur(s)")
    return errors


if __name__ == "__main__":
    t0 = time.time()
    all_errors = []
    for nb_path in sorted(HERE.glob("[0-9][0-9]_*.ipynb")):
        all_errors += run_notebook(nb_path)
    for e in all_errors[:20]:
        print("\n" + e)
    print(f"\n{len(all_errors)} erreur(s) en {time.time() - t0:.0f} s")
    sys.exit(1 if all_errors else 0)
