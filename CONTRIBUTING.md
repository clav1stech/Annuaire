# Contribuer à Annuaire_SIRENE

Projet interne. Ce guide résume le flux de contribution ; les règles détaillées
vivent dans [docs/CLAUDE.md](docs/CLAUDE.md) et [docs/CONVENTIONS.md](docs/CONVENTIONS.md)
(à lire avant toute intervention). En cas de conflit, `docs/CLAUDE.md` fait foi.

## Mise en place

```bash
./create_venv.command     # macOS / Linux (create_venv.bat sous Windows)
pip install -e ".[dev]"   # dépendances de développement (pytest, ruff, mypy)
```

## Se repérer dans le code

Consulter [docs/CODEMAP.md](docs/CODEMAP.md) plutôt que de parcourir tout le
dépôt. Architecture en couches à sens unique :

```
io_utils / sirene_queries (accès données)
    → pipeline (métier)
        → export_utils / ui_helpers (présentation)
            → app.py (entrypoint Streamlit)
```

`config.py`, `siret_utils.py`, `sirene_schema.py` sont transverses.

## Avant de proposer une PR

```bash
ruff check .   # lint
mypy           # typage statique (périmètre : src/ + app.py)
pytest -q      # tests
```

La CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) rejoue lint + tests
sur Python 3.11, 3.12, 3.13 et 3.14, et le typage statique sur une seule version.

## Versionnage & changelog

- Versionnage sémantique `X.Y.Z`, source de vérité dans le fichier `VERSION`.
- `Z` (patch) pour un correctif ; `Y` (minor) pour un chantier structurant ;
  `X` (major) uniquement sur demande explicite.
- Un commit qui change un comportement visible met à jour `CHANGELOG.md` **via
  le script**, jamais à la main :

  ```bash
  python scripts/update_changelog.py
  ```

- Les commits purement internes (doc, outillage, typo) ne bumpent pas la version.

## Règles à ne jamais enfreindre

- **Ne jamais lire/ouvrir/parser les fichiers Parquet SIRENE** (seuls leurs
  chemins servent de paramètres d'entrée).
- **UTF-8 partout** : vérifier les accents FR dans l'UI, l'export Excel et les docs.
- Aucun secret en dur ; aucun fichier généré, environnement virtuel, cache ou
  export versionné.
