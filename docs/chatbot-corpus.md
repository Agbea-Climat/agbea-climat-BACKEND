# Corpus RAG du chatbot : guide pour l'équipe IA

Ce document explique ce que contient `data/corpus/`, comment il est produit, et comment le chatbot
peut en tirer le meilleur parti. Le corpus est préparé par l'équipe données ; l'ingestion et la recherche
sont dans `worker/rag_ingest.py` et `chatbot/tools/retrieve.py`.

## 1. Contenu (64 documents, 122 morceaux au 15/11/2026)

| Type | Fichiers | Produit par | `region_ids` | Usage |
|---|---|---|---|---|
| Fiches des jeux de données | `fiche_gpm_imerg.md`, `fiche_modis_ndvi.md`, `fiche_modis_lst.md`, `fiche_nasadem.md` | à la main | `[]` | « d'où vient la donnée ? », limites |
| Comprendre un indicateur | `comprendre_pluie_imerg.md`, `comprendre_ndvi.md`, `comprendre_temperature_sol.md` | à la main (pages NASA) | `[]` | explications simples |
| Calendrier agricole | `calendrier_agricole_togo.md` | à la main (FAO GIEWS 2026, UNICEF 2025) | 5 régions | semis, récoltes, saisons des pluies |
| Climat du Togo | `climat_togo_tendances.md` | à la main (UNICEF / ministère, 2025) | 5 régions | tendances des stations, inondations, sécheresses, érosion |
| Limites des données | `limites_donnees_agbea.md` | à la main | 5 régions | faible couverture, pluie côtière, dérive de Terra |
| Glossaire et FAQ | `glossaire_faq.md` | à la main | `[]` | normale, écart, tendance, « pas de prévision », sites pilotes |
| Méthodologie | `methodologie_agbea.md` | **généré** (copie de `docs/data/methodologie.md`) | `[]` | profil chercheur |
| Fiches de zone | `fiches/pays_togo.md`, `fiches/region_<nom>.md` (5), `fiches/prefecture_<nom>.md` (39), `fiches/site_<nom>.md` (7) | **généré** (`python -m pipeline corpus`) | région de la zone | relief, climat habituel, tendances, dernières valeurs |

Chaque fiche de zone contient, pour sa zone :
- **où** : région ou préfecture parente, superficie, centre ;
- **relief** : altitude, part sous 10 m ;
- **climat habituel** : normales 2001-2020, mois les plus et les moins pluvieux, verts et chauds ;
- **tendances** testées : Mann-Kendall à 5 %, pente de Sen. Elles couvrent pluie, NDVI, température du sol le jour et **la nuit**. Seules les tendances significatives sont chiffrées ;
- **dernières observations fiables**, datées.

Les fiches de zone apportent ce que l'API n'a pas :
- **les 39 préfectures et les 7 sites pilotes** ; l'API ne connaît que les 5 régions ;
- **les tendances**, et la température du sol la nuit (seule hausse confirmée par deux satellites).

## 2. Format de `sources.json`

Une entrée par document :

```json
{"file": "fiches/site_kpalime-mont-agou.md", "title": "Fiche climatique AGBÉA : site pilote Kpalimé & Mont Agou",
 "source_url": "https://github.com/.../data/corpus/fiches/site_kpalime-mont-agou.md",
 "region_ids": ["plateaux"], "indicators": ["precipitation", "ndvi", "lst_day", "elevation"]}
```

- Le fichier est écrit en ASCII (accents échappés `é`). Il se lit donc quel que soit l'encodage par défaut.
- `region_ids: []` désigne un document général : le filtre de `retrieve.py` le garde pour toutes les régions.
- Les entrées `fiches/…` et `methodologie_agbea.md` sont **réécrites** à chaque `python -m pipeline corpus`. Les autres sont gardées telles quelles.

## 3. Mise à jour

1. **Données** : `export`, puis `corpus` (voir `docs/data/pipeline.md`). L'étape `corpus` fait aussi partie de `all`. Elle a besoin de `data/api/`, qui n'est pas versionné : seul un poste qui a lancé `export` peut régénérer les fiches.
2. **Ingestion** : la CI appelle `POST /api/v1/admin/rag/ingest` après chaque déploiement. En local : `curl -X POST http://localhost:8000/api/v1/admin/rag/ingest`. C'est idempotent (id = sha1(fichier + index)).
3. **Ajouter un document écrit à la main** :
   - placer le `.md`, `.txt` ou `.pdf` dans `data/corpus/` ;
   - ajouter son entrée dans `sources.json` (`title`, `source_url` obligatoires) ;
   - lancer l'ingestion.

   Préférer un **résumé sourcé** en Markdown à un PDF complet : c'est plus sûr pour les droits et le découpage est plus propre.

## 4. Règles à respecter

- **Aucun chiffre inventé** :
  - les chiffres des fiches de zone viennent tous de `data/api/`, et chaque valeur est datée ;
  - **ne jamais modifier une fiche à la main** : la régénérer.
  - **Question à trancher par l'équipe** : la règle 5 du `CLAUDE.md` dit que l'IA ne cite que des chiffres renvoyés par les services. Les fiches de zone sont une source citée, avec URL. Si l'on veut que le chatbot cite leurs chiffres, la règle doit les autoriser explicitement : chiffres de documents du corpus, toujours avec la source.
- **Pas de prévision** : aucun document du corpus ne contient de prévision. Ne pas ajouter de prévisions saisonnières (AGRHYMET/PRESASS, bulletins prévisionnels).
- **Limites des données à rappeler** :
  - la pluie s'arrête en 2025-09 (IMERG Final) ;
  - la température du sol, en 2022-12 (dérive de Terra, D30) ; ses tendances, en 2020 ;
  - une valeur peut être en faible couverture (« peu fiable », nuages).
- **Tendances des préfectures et des sites** : des dizaines de séries sont testées, et environ une sur vingt peut paraître significative par hasard. Les fiches le disent ; le chatbot doit le rappeler s'il cite une tendance locale isolée.

## 5. Constats du test du 15/11/2026 (mode gabarits, sans clé LLM)

L'ingestion donne 64 documents et 122 morceaux, sans doublon. La recherche retrouve le glossaire, les limites, la méthodologie et la fiche du site de Lomé sur des questions adaptées. Trois défauts restent du côté du chatbot :

1. **Sans LLM, les gabarits n'utilisent pas le contenu des documents**, seulement leur titre (« Pour en savoir plus : … »). Les questions générales (« Qu'est-ce qu'une normale ? », « Comment sont calculées les tendances ? ») reçoivent « Précisez une région ». Piste : sans région, et quand un document général est trouvé (`region_ids: []`), citer son passage le plus pertinent, comme c'est déjà fait pour le calendrier agricole.
2. **La recherche lexicale (`hash-v1`) noie les documents généraux sous les fiches de zone.** Les 52 fiches répètent « normale », « pluie », « tendance ». Pistes :
   - sans région ni zone dans la question, exclure les fichiers `fiches/` de la recherche ;
   - avec une région, une préfecture ou un site détecté, aller chercher **directement** la fiche par son nom de fichier (`fiches/prefecture_<nom>.md`, `fiches/site_<nom>.md`) plutôt que par similarité ;
   - à terme, un vrai modèle d'embeddings (`EMBEDDING_MODEL`) remplacerait le hachage de mots.
3. **Les préfectures, les sites et la température de nuit ne sont pas reconnus dans les questions.**
   - « Tendance de la température la nuit à Kpalimé » répond par la température de jour de la région Plateaux, et la fiche du site de Kpalimé n'est pas citée.
   - Piste : reconnaître les noms des 39 préfectures et des 7 sites (liste : `data/api/summaries/index.json`, ou les titres de `sources.json`), puis répondre depuis leur fiche.

## 6. Pour aller plus loin (sources externes possibles)

Ces sources ne sont pas encore dans le corpus. Elles sont à résumer et sourcer, comme les documents existants :
- CDN révisée du Togo (2021, registre CCNUCC) ;
- Plan national d'adaptation (PNACC) ;
- 4e Communication nationale (CCNUCC, 2022 : téléchargement automatique bloqué, à récupérer à la main) ;
- profil de risque climatique de la Banque mondiale (2025) et programme WACA sur l'érosion côtière ;
- rapports OCHA / ReliefWeb sur les inondations.
