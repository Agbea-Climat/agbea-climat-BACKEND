"""Corpus RAG généré à partir des données (étape `corpus`, D31).

Écrit dans data/corpus/ :
  fiches/<niveau>_<nom>.md   une fiche par unité publiée dans data/api/summaries (pays, 5 régions,
                             39 préfectures, 7 sites pilotes) : relief, climat habituel, tendances testées,
                             dernières observations. Tous les chiffres viennent des fichiers de data/api/.
  methodologie_agbea.md      copie de docs/data/methodologie.md (profil chercheur)
et met à jour data/corpus/sources.json : les entrées écrites à la main sont gardées, les entrées générées
(fiches/…, methodologie_agbea.md) sont remplacées.

Prérequis : `export` (data/api/summaries, data/api/tables/climatology.parquet).
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from pathlib import Path

import pandas as pd

from . import config
from .backend_export import REGION_SLUGS

CORPUS = config.DATA / "corpus"
FICHES = "fiches"
METHODO_SRC = config.ROOT / "docs" / "data" / "methodologie.md"
METHODO_DST = "methodologie_agbea.md"
REPO_URL = "https://github.com/Agbea-Climat/agbea-climat-BACKEND/blob/main/"
ALL_REGIONS = list(REGION_SLUGS.values())
INDICATORS = ["precipitation", "ndvi", "lst_day", "elevation"]

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre"]
NIVEAU = {"country": "Pays", "region": "Région", "prefecture": "Préfecture", "site": "Site pilote"}
PREFIXE = {"country": "pays", "region": "region", "prefecture": "prefecture", "site": "site"}
SAISON = {"annual": "sur l'année", "jfm": "janvier-mars, saison sèche",
          "mjjaso": "mai-octobre, saison des pluies"}
NOM_IND = {"rainfall": "Pluie", "ndvi": "Végétation (NDVI)", "lst_day": "Température du sol le jour",
           "lst_night": "Température du sol la nuit"}
NOM_COURT = {"rainfall": "pluie", "ndvi": "végétation (NDVI)", "lst_day": "température du sol le jour",
             "lst_night": "température du sol la nuit"}
UNITE_PENTE = {"rainfall": "mm", "ndvi": "", "lst_day": "°C", "lst_night": "°C"}
DEC_PENTE = {"rainfall": 1, "ndvi": 3, "lst_day": 2, "lst_night": 2}


# ----------------------------------------------------------------------------- formatage

def fr(x: float, nd: int = 1) -> str:
    """Nombre au format français (virgule décimale), sans séparateur de milliers : même règle que
    chatbot/prompts/i18n.py, pour que le garde-fou des chiffres du chatbot lise chaque nombre en entier."""
    s = f"{x:.{nd}f}"
    if float(s) == 0:
        s = s.lstrip("-")                                   # pas de « -0,0 »
    return s.replace(".", ",")


def mois_annee(ym: str) -> str:
    y, m = ym.split("-")
    return f"{MOIS[int(m) - 1]} {y}"


def slug(name: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFKD", name.lower()) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


# ----------------------------------------------------------------------------- contenu d'une fiche

def _localisation(u: dict, idx: dict) -> str:
    lvl = u["level"]
    if lvl == "country":
        return "Togo, ensemble du pays (5 régions, 39 préfectures)."
    parent = idx.get(u.get("parent_id") or "")
    if lvl == "region":
        return f"Région {u['name']} du Togo."
    if lvl == "prefecture":
        return f"Préfecture {u['name']}, région {parent['name']}." if parent else f"Préfecture {u['name']}."
    region = idx.get(parent.get("parent_id")) if parent else None
    return (f"Site pilote {u['name']}, dans la préfecture {parent['name']}"
            + (f" (région {region['name']})." if region else "."))


def region_slugs(u: dict, idx: dict) -> list[str]:
    cur = u
    while cur and cur["level"] not in ("region", "country"):
        cur = idx.get(cur.get("parent_id") or "")
    if not cur or cur["level"] == "country":
        return ALL_REGIONS
    return [REGION_SLUGS[cur["id"]]] if cur["id"] in REGION_SLUGS else ALL_REGIONS


def _climat(clim: pd.DataFrame) -> list[str]:
    out = []
    r = clim[clim.indicator == "rainfall"].set_index("month").clim_mean
    if len(r) == 12:
        wet = r.sort_values(ascending=False)
        out.append(f"- Pluie : environ {fr(r.sum(), 0)} mm par an. Mois les plus pluvieux : "
                   + ", ".join(f"{MOIS[m - 1]} ({fr(v, 0)} mm)" for m, v in wet.head(3).items())
                   + f". Mois le plus sec : {MOIS[r.idxmin() - 1]} ({fr(r.min(), 1)} mm).")
    n = clim[clim.indicator == "ndvi"].set_index("month").clim_mean
    if len(n) == 12:
        out.append(f"- Végétation (NDVI, de -1 à 1) : la plus verte en {MOIS[n.idxmax() - 1]} ({fr(n.max(), 2)}), "
                   f"la moins verte en {MOIS[n.idxmin() - 1]} ({fr(n.min(), 2)}).")
    t = clim[clim.indicator == "lst_day"].set_index("month").clim_mean
    if len(t) == 12:
        out.append(f"- Température du sol le jour : la plus chaude en {MOIS[t.idxmax() - 1]} ({fr(t.max(), 1)} °C), "
                   f"la plus fraîche en {MOIS[t.idxmin() - 1]} ({fr(t.min(), 1)} °C).")
    return out


def _tendances(trends: dict, level: str) -> list[str]:
    sig, non = [], []
    for ind in ["rainfall", "ndvi", "lst_day", "lst_night"]:
        for season, t in (trends.get(ind) or {}).items():
            if season not in SAISON or not t:
                continue
            per = f"{t['first_year']}-{t['last_year']}"
            label = f"{NOM_COURT[ind]} ({SAISON[season]}, {per})"
            if t.get("significant"):
                nd, u = DEC_PENTE[ind], UNITE_PENTE[ind]
                unit = f" {u}" if u else ""
                pct = (f", soit {fr(t['sen_slope_pct_per_decade'], 1)} %"
                       if ind == "rainfall" and t.get("sen_slope_pct_per_decade") is not None else "")
                sens = "hausse" if t["sen_slope_per_decade"] > 0 else "baisse"
                sig.append(f"- {NOM_IND[ind]} ({SAISON[season]}, {per}) : {sens} de "
                           f"{fr(abs(t['sen_slope_per_decade']), nd)}{unit} par décennie{pct} "
                           f"(intervalle de confiance à 95 % : {fr(t['sen_ci95_low_per_decade'], nd)} à "
                           f"{fr(t['sen_ci95_high_per_decade'], nd)}{unit}).")
            else:
                non.append(label)
    out = ["Test de Mann-Kendall au seuil de 5 %, pente de Sen. On ne parle de tendance que si le test est "
           "significatif."]
    out += [""] + (sig or ["- Aucune tendance significative."])
    if non:
        out.append("- Pas de tendance significative pour : " + " ; ".join(non) + ".")
    # lignes vides : chaque remarque est une unité citable à part (chatbot/tools/retrieve._units)
    out += ["", "Les tendances de température du sol s'arrêtent en 2020 (dérive d'orbite du satellite Terra)."]
    if level in ("prefecture", "site"):
        out += [""]
        out.append("À l'échelle des préfectures et des sites, des dizaines de séries sont testées : environ une sur "
                   "vingt peut paraître significative par hasard. Une tendance isolée est à confirmer avec les zones voisines.")
    return out


def _dernieres(latest: dict) -> list[str]:
    out = []
    r = latest.get("rainfall")
    if r and r.get("value") is not None:
        ecart = f", écart {'+' if r['anomaly_pct'] > 0 else ''}{fr(r['anomaly_pct'], 1)} %" if r.get("anomaly_pct") is not None else ""
        out.append(f"- Pluie, {mois_annee(r['date'])} : {fr(r['value'], 1)} mm (normale du mois : "
                   f"{fr(r['clim_mean'], 1)} mm{ecart}). La série de pluie (IMERG Final) s'arrête pour l'instant à ce mois.")
    for ind, unit, nd in (("ndvi", "", 3), ("lst_day", " °C", 1)):
        v = latest.get(ind)
        if v and v.get("value") is not None:
            ecart = v["value"] - v["clim_mean"]
            txt = (f"- {NOM_IND[ind]}, {mois_annee(v['date'])} : {fr(v['value'], nd)}{unit} (normale du mois : "
                   f"{fr(v['clim_mean'], nd)}{unit}, écart {'+' if ecart > 0 else ''}{fr(ecart, nd)}{unit}).")
            if ind == "lst_day":
                txt += " Température du sol publiée jusqu'en décembre 2022."
            if (v.get("valid_frac") or 1) < 0.5:
                txt += " Attention : moins de la moitié de la zone visible (nuages), valeur peu fiable."
            out.append(txt)
    if out:
        out.insert(0, "Dernière valeur fiable de chaque indicateur (au moins la moitié de la zone visible) :")
    return out


def fiche(s: dict, idx: dict, clim: pd.DataFrame, today: str) -> str:
    u = s["unit"]
    lvl = u["level"]
    titre = {"country": "Togo (pays)", "region": f"Région {u['name']}",
             "prefecture": f"Préfecture {u['name']}", "site": f"Site pilote {u['name']}"}[lvl]
    e = s.get("elevation_m") or {}
    lines = [
        f"# {titre} : fiche climatique AGBÉA CLIMAT", "",
        f"Source : AGBÉA CLIMAT, fiche générée le {today} par le pipeline de données (`python -m pipeline corpus`) "
        "à partir de NASA GPM IMERG Final V07 (pluie), MODIS Terra MOD13A1 (végétation, NDVI), MODIS Terra MOD11A2 "
        "(température du sol) et NASADEM (altitude). Normales : moyenne 2001-2020. Estimations satellite moyennées "
        "sur toute la zone, pas des mesures de station.", "",
        "## Où", "",
        _localisation(u, idx) + (f" Superficie : {fr(u['area_km2'], 0)} km²." if u.get("area_km2") else "")
        + (f" Centre : longitude {fr(u['centroid'][0], 3)}, latitude {fr(u['centroid'][1], 3)}." if u.get("centroid") else ""),
        "",
    ]
    if e:
        lines += ["## Relief (NASADEM)", "",
                  f"Altitude moyenne {fr(e['mean'], 0)} m (de {fr(e['min'], 0)} à {fr(e['max'], 0)} m). "
                  f"{fr(e['pct_below_10m'], 1)} % du territoire est à moins de 10 m d'altitude"
                  + (" (zones basses, exposées aux inondations et à la mer)." if e["pct_below_10m"] >= 5 else "."), ""]
    c = _climat(clim)
    if c:
        lines += ["## Climat habituel (normales 2001-2020)", "", *c, ""]
    lines += ["## Tendances observées", "", *_tendances(s.get("trends") or {}, lvl), ""]
    d = _dernieres(s.get("latest") or {})
    if d:
        lines += ["## Dernières observations", "", *d, ""]
    lines += ["## À retenir", "",
              "AGBÉA CLIMAT montre ce que les satellites ont observé. Il ne fait pas de prévision et ne remplace pas "
              "les prévisions officielles (ANAMET) ni les systèmes d'alerte.", ""]
    return "\n".join(lines)


# ----------------------------------------------------------------------------- étape

def run() -> None:
    summaries = config.API / "summaries"
    index = json.loads((summaries / "index.json").read_text(encoding="utf-8"))
    idx = {u["id"]: u for u in index}
    clim_all = pd.read_parquet(config.API / "tables" / "climatology.parquet")
    today = date.today().isoformat()
    out_dir = CORPUS / FICHES
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.md"):
        old.unlink()

    generated = []
    for u in index:
        path = summaries / f"{u['id']}.json"
        if not path.exists():
            continue
        s = json.loads(path.read_text(encoding="utf-8"))
        name = f"{PREFIXE[u['level']]}_{slug(u['name'])}.md"
        (out_dir / name).write_text(fiche(s, idx, clim_all[clim_all.unit_id == u["id"]], today), encoding="utf-8")
        titre = {"country": "Togo (pays)", "region": f"région {u['name']}", "prefecture": f"préfecture {u['name']}",
                 "site": f"site pilote {u['name']}"}[u["level"]]
        generated.append({"file": f"{FICHES}/{name}", "title": f"Fiche climatique AGBÉA : {titre}",
                          "source_url": f"{REPO_URL}data/corpus/{FICHES}/{name}",
                          "region_ids": region_slugs(u, idx), "indicators": INDICATORS})

    if METHODO_SRC.exists():
        txt = METHODO_SRC.read_text(encoding="utf-8")
        (CORPUS / METHODO_DST).write_text(
            "Source : méthodologie du pipeline de données AGBÉA CLIMAT (docs/data/methodologie.md), copiée par "
            f"`python -m pipeline corpus` le {today}.\n\n" + txt, encoding="utf-8")
        generated.append({"file": METHODO_DST, "title": "Méthodologie des données AGBÉA CLIMAT (calculs, contrôles, limites)",
                          "source_url": f"{REPO_URL}docs/data/methodologie.md", "region_ids": [],
                          "indicators": ["precipitation", "ndvi", "lst_day"]})
    else:
        print(f"  {METHODO_SRC} absent (monter ./docs dans le conteneur) : méthodologie non copiée")

    src_path = CORPUS / "sources.json"
    manual = [e for e in json.loads(src_path.read_text(encoding="utf-8"))
              if not e["file"].startswith(f"{FICHES}/") and e["file"] != METHODO_DST]
    entries = manual + generated
    # ASCII (\u échappés) : lisible quel que soit l'encodage par défaut (D29)
    src_path.write_text(json.dumps(entries, ensure_ascii=True, indent=2) + "\n", encoding="ascii")
    print(f"Corpus → {len(generated)} document(s) généré(s) + {len(manual)} écrit(s) à la main ; "
          f"sources.json : {len(entries)} entrées")
