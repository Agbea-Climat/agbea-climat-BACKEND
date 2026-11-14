# Limites administratives officielles (MAP TOGO / geodata.gouv.tg)

| Fichier | Contenu |
|---|---|
| `country.geojson` | contour du Togo = union des 5 régions (un seul polygone, sans trou) |
| `regions.geojson` | 5 régions : `unit_id` (`TG-A`…`TG-E`), `code`, `nom`, `superficie_km2` |
| `prefectures.geojson` | 39 préfectures : `unit_id` (`TG-A01`…), `code`, `nom`, `region`, `parent_id`, `superficie_km2` |
| `meta.json` | source, date, dossier d'origine |

- **Source** : « Contenu provenant de la Plateforme Géodata (geodata.gouv.tg) en date du 2026-10-23 » (découpage PRISE). geodata.gouv.tg livre les polygones sans noms ; ceux-ci ont été rattachés par le projet local MAP TOGO de l'équipe (voir son README).
- **Import / mise à jour** : `python -m pipeline boundaries --map-togo-dir "<projet MAP TOGO>/web/data"`.
- **Qualité vérifiée le 14/11/2026** : géométries valides, préfectures qui pavent exactement les régions (différence 0 km²), surface 56 681 km² (HDX : 56 698 km²).
- **Conditions d'utilisation** (CGU geodata.gouv.tg §7 à 8.2) : citer la source, ne pas altérer le contenu. La réutilisation publique ou commerciale **peut être soumise à une contrepartie financière** : à vérifier avant une diffusion publique de l'application. Solution de repli sans contrainte : `boundaries.admin_source: hdx` dans `pipeline/settings/settings.yaml` (COD-AB OCHA, CC BY-IGO).
