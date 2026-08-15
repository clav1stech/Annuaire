# CODEMAP - Carte du code

> À lire avant toute intervention, à tenir à jour à chaque changement de structure (cf. `docs/CLAUDE.md` § Architecture et dépendances).

## Racine
- `app.py` — point d'entrée Streamlit principal (contrôle de SIRET, enrichissement SIRENE, mise à jour du code en ligne ou par dépôt d'un ZIP GitHub).
- `VERSION` — source de vérité du numéro de version sémantique (X.Y.Z).
- `CHANGELOG.md` — historique des versions, mis à jour uniquement via `scripts/update_changelog.py`.
- `AGENTS.md` — point d'entrée IA, renvoie vers `docs/CLAUDE.md`.
- `LICENSE` — notice de propriété interne (logiciel non open source).
- `CONTRIBUTING.md` — flux de contribution (résumé, renvoie vers `docs/`).
- `pyproject.toml` — métadonnées du package, dépendances (dont `[dev]`), config `pytest`/`ruff`/`mypy`.
- `requirements.txt` — dépendances Python (utilisé par les scripts d'installation). `starlette` y est épinglé explicitement bien qu'il soit transitif : voir le commentaire du fichier et `tests/test_dependencies.py`.
- `run_app.command` / `run_app.bat` — **point d'entrée unique** pour l'utilisateur : crée l'environnement virtuel s'il est absent (en appelant `create_venv`), vérifie la version distante, resynchronise les dépendances (`scripts/sync_dependencies.py`), puis lance Streamlit.
- `create_venv.command` / `create_venv.bat` — création de l'environnement et installation des dépendances : détection de l'interpréteur Python (alias Microsoft Store, Anaconda, plage 3.11-3.14). Appelé par `run_app` au premier lancement ; en usage direct, script de réinstallation/réparation.
- Extension `.command` (macOS / Linux) pour une ouverture directe dans Terminal.app au double-clic ; `.bat` sous Windows. Les `.bat` restent en ASCII sans accents.

## tests/
- Tests `pytest` des fonctions pures (validation SIRET/SIREN, statut, nommage des sorties). Socle de non-régression.
- `test_data_manifest.py` — client data.gouv.fr, manifeste local et téléchargement, avec HTTP simulé (jamais d'appel réseau réel).
- `test_sirene_schema.py` — résolution des colonnes, dont la coexistence des nomenclatures NAF rév. 2 / NAF 2025.
- `test_dependencies.py` — synchronisation des dépendances (pip simulé, aucune installation réelle) et garde-fou de compatibilité Streamlit/starlette.
- `test_atomic_io.py` — remplacement atomique : verrou transitoire réessayé, verrou persistant signalé sans abîmer le fichier existant (`os.replace` et l'attente simulés).
- `test_pipeline_succession.py` — chaîne de succession et choix du SIRET de remplacement (cascade, cycle, repli sur un établissement actif du même SIREN), avec service SIRENE simulé (aucun Parquet lu).

## .github/
- `workflows/ci.yml` — CI (lint `ruff` + `pytest` sur Python 3.11 à 3.14, typage `mypy` sur une version).
- `pull_request_template.md` — gabarit de PR (checklist versionnage/UTF-8/Parquet).

## dormant/
- Fonctionnalités dépréciées, hors flux principal (voir `dormant/README.md`).
- `name_search_app.py` — app Streamlit secondaire (recherche floue par nom), **dépréciée** car peu fiable.
- `run_name_search.bat` — ancien lanceur Windows de cette app.

## scripts/
- `update_changelog.py` — insertion idempotente d'entrées dans `CHANGELOG.md`.
- `update_project.py` — CLI de mise à jour : compare les versions puis délègue l'application à `src/updater.py`.
- `sync_dependencies.py` — CLI de synchronisation de l'environnement virtuel avec `requirements.txt` (`--check-only`, `--force`) ; appelé par `run_app` avant le lancement et par `create_venv` à l'installation.
- `export_project.py` — outil d'export du projet, voir § Export dans `docs/CLAUDE.md`. Trois profils exclusifs :
  `--ai` (défaut : code + doc structurante + manifeste), `--outline` (carte d'architecture sans corps de fonctions),
  `--backup` (zip restaurable avec rotation). Portée réductible via `--only chemins` ou `--preset <sous-module>`
  (`--list-presets` pour la liste). Sorties dans `export/`, gitignoré.

## src/ (package `Annuaire_SIRENE`)
- `__init__.py` — expose `APP_NAME`, `__version__`.
- `config.py` — constantes applicatives, chemins par défaut des parquets SIRENE, listes de champs canoniques, lecture de `VERSION`. Tout réglage global vit ici.
- `atomic_io.py` — remplacement « temporaire → fichier final » avec réessais (`replace_atomically`, `write_text_atomically`, `AtomicWriteError`). Transverse, ne dépend que de `config.py` : un dossier synchronisé ou un antivirus peut verrouiller brièvement la destination sous Windows.
- `siret_utils.py` — normalisation et validation des SIRET/SIREN.
- `sirene_schema.py` — résolution défensive des colonnes des tables SIRENE (alias).
- `sirene_queries.py` — requêtes DuckDB sur les fichiers parquet SIRENE (couche accès données, pas de logique métier).
- `pipeline.py` — logique métier : contrôle SIRET/SIREN, enrichissement à partir de SIRENE.
- `io_utils.py` — lecture des fichiers utilisateur et détection des sources parquet locales.
- `export_utils.py` — génération du rapport Excel (feuilles, mise en forme).
- `ui_helpers.py` — fonctions d'aide au rendu Streamlit.
- `version_check.py` — comparaison version locale / `VERSION` distant sur GitHub (partagé UI + CLI).
- `updater.py` — application d'une mise à jour (git, ZIP téléchargé ou ZIP GitHub déposé manuellement), avec validation de l'archive et copie des seuls fichiers différents ; sans interaction ni sortie standard, renvoie un `UpdateOutcome`. Partagé entre `app.py` et `scripts/update_project.py`.
- `dependencies.py` — cohérence entre `requirements.txt` et les paquets installés : empreinte des dépendances enregistrée dans l'environnement virtuel, détection de désynchronisation, réinstallation pip. Transverse, sans sortie standard (`InstallOutcome`).
- `datagouv_client.py` — métadonnées des ressources Parquet SIRENE sur l'API data.gouv.fr (lien permanent, checksum, taille, date de publication). N'ouvre jamais les Parquet.
- `download_utils.py` — téléchargement en flux avec écriture atomique et rapport de progression. Transport pur, sans connaissance du manifeste ni de l'UI.
- `data_manifest.py` — manifeste local `.sirene_manifest.json` (gitignoré) : versions téléchargées, comparaison avec le distant (`get_data_freshness_status`), orchestration téléchargement + enregistrement.

## Fichiers d'état locaux (non versionnés)
- `.sirene_manifest.json` — version des fichiers SIRENE téléchargés (checksum, taille, date de publication, chemin local, date de téléchargement). Écrit uniquement après un téléchargement complet.

## Flux de dépendances (sens unique)
`io_utils` / `sirene_queries` (accès données) → `pipeline` (métier) → `export_utils` / `ui_helpers` (présentation) → `app.py` (entrypoint).
`config.py`, `atomic_io.py` et `siret_utils.py` / `sirene_schema.py` sont transverses, utilisables par toutes les couches.
`version_check.py` / `updater.py` sont transverses eux aussi (`updater` dépend de `version_check`, jamais l'inverse).
Chaîne données SIRENE, également transverse et à sens unique : `datagouv_client` / `download_utils` → `data_manifest` → `app.py`.

## docs/
- `CLAUDE.md` — règles transverses génériques (tout langage/projet).
- `CONVENTIONS.md` — conventions de code transverses.
- `CODEMAP.md` — ce fichier.
- `DEPANNAGE.md` — guide de dépannage utilisateur (terminal, scripts, cas macOS, mise à jour hors ligne, fichiers SIRENE). Destination de tout le contenu de dépannage sorti du `README.md`.
- `EXPORT_EXCEL.md` — structure détaillée du rapport Excel (onglets, catégories de colonnes de `siret_overview`, valeurs de `analysis_data_applied`, statuts).
- `SUCCESSION.md` — règle de choix du SIRET de remplacement (liens multiples, remplaçant sur un autre SIREN, valeurs de `analysis_data_applied`) et protocole de non-régression associé.
