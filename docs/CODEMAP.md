# CODEMAP - Carte du code

> À lire avant toute intervention, à tenir à jour à chaque changement de structure (cf. `docs/CLAUDE.md` § Architecture et dépendances).

## Racine
- `app.py` — point d'entrée Streamlit principal (contrôle de SIRET, enrichissement SIRENE).
- `VERSION` — source de vérité du numéro de version sémantique (X.Y.Z).
- `CHANGELOG.md` — historique des versions, mis à jour uniquement via `scripts/update_changelog.py`.
- `AGENTS.md` — point d'entrée IA, renvoie vers `docs/CLAUDE.md`.
- `LICENSE` — notice de propriété interne (logiciel non open source).
- `CONTRIBUTING.md` — flux de contribution (résumé, renvoie vers `docs/`).
- `pyproject.toml` — métadonnées du package, dépendances (dont `[dev]`), config `pytest`/`ruff`.
- `requirements.txt` — dépendances Python (utilisé par les scripts d'installation).
- `create_venv.command` / `run_app.command` — installation et lancement (macOS / Linux ; extension `.command` pour ouverture directe dans Terminal.app au double-clic).
- `create_venv.bat` / `run_app.bat` — installation et lancement (Windows).

## tests/
- Tests `pytest` des fonctions pures (validation SIRET/SIREN, statut, nommage des sorties). Socle de non-régression.

## .github/
- `workflows/ci.yml` — CI (lint `ruff` + `pytest` sur Python 3.11/3.12).
- `pull_request_template.md` — gabarit de PR (checklist versionnage/UTF-8/Parquet).

## dormant/
- Fonctionnalités dépréciées, hors flux principal (voir `dormant/README.md`).
- `name_search_app.py` — app Streamlit secondaire (recherche floue par nom), **dépréciée** car peu fiable.
- `run_name_search.bat` — ancien lanceur Windows de cette app.

## scripts/
- `update_changelog.py` — insertion idempotente d'entrées dans `CHANGELOG.md`.
- `export_project.py` — outil d'export du projet (profils IA / sauvegarde), voir § Export dans `docs/CLAUDE.md`.

## src/ (package `Annuaire_SIRENE`)
- `__init__.py` — expose `APP_NAME`, `__version__`.
- `config.py` — constantes applicatives, chemins par défaut des parquets SIRENE, listes de champs canoniques, lecture de `VERSION`. Tout réglage global vit ici.
- `siret_utils.py` — normalisation et validation des SIRET/SIREN.
- `sirene_schema.py` — résolution défensive des colonnes des tables SIRENE (alias).
- `sirene_queries.py` — requêtes DuckDB sur les fichiers parquet SIRENE (couche accès données, pas de logique métier).
- `pipeline.py` — logique métier : contrôle SIRET/SIREN, enrichissement à partir de SIRENE.
- `io_utils.py` — lecture des fichiers utilisateur et détection des sources parquet locales.
- `export_utils.py` — génération du rapport Excel (feuilles, mise en forme).
- `ui_helpers.py` — fonctions d'aide au rendu Streamlit.

## Flux de dépendances (sens unique)
`io_utils` / `sirene_queries` (accès données) → `pipeline` (métier) → `export_utils` / `ui_helpers` (présentation) → `app.py` (entrypoint).
`config.py` et `siret_utils.py` / `sirene_schema.py` sont transverses, utilisables par toutes les couches.

## docs/
- `CLAUDE.md` — règles transverses génériques (tout langage/projet).
- `CONVENTIONS.md` — conventions de code transverses.
- `CODEMAP.md` — ce fichier.
