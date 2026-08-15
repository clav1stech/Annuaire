# Contribuer à Annuaire_SIRENE

Projet interne. Ce guide résume le flux de contribution ; les règles détaillées
vivent dans [docs/CLAUDE.md](docs/CLAUDE.md) et [docs/CONVENTIONS.md](docs/CONVENTIONS.md)
(à lire avant toute intervention). En cas de conflit, `docs/CLAUDE.md` fait foi.

## Mise en place

```bash
./create_venv.command                    # macOS / Linux (create_venv.bat sous Windows)
source .venv_annuaire_sirene/bin/activate # Windows : .venv_annuaire_sirene\Scripts\activate
pip install -e ".[dev]"                  # pytest, ruff, mypy
```

L'activation de l'environnement entre les deux commandes n'est pas optionnelle,
sinon les outils de dev s'installent dans le Python système.

En développement, lancer l'application directement plutôt que par `run_app`, qui
refait à chaque fois la vérification de version et la synchronisation des
dépendances :

```bash
streamlit run app.py
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

## Tests

Les tests ne touchent jamais un fichier Parquet réel, ni le réseau. Toute
dépendance externe est remplacée par un double construit dans le test :

- [`tests/test_pipeline_succession.py`](tests/test_pipeline_succession.py) —
  chaînes de succession et choix du SIRET de remplacement, sur des DataFrames
  construits à la main.
- [`tests/test_data_manifest.py`](tests/test_data_manifest.py) — client
  data.gouv.fr et téléchargement, avec HTTP simulé.
- [`tests/test_atomic_io.py`](tests/test_atomic_io.py) — remplacement atomique,
  avec `os.replace` et l'attente simulés.

Ces trois fichiers servent de modèle pour tester une nouvelle fonction qui lit
des données ou appelle le réseau.

## Avant de proposer une PR

```bash
ruff check .   # lint
mypy           # typage statique (périmètre : src/ + app.py)
pytest -q      # tests
```

La CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) rejoue lint + tests
sur Python 3.11, 3.12, 3.13 et 3.14, et le typage statique sur une seule version.
Elle tourne sur `ubuntu-latest` : **aucun lanceur `.bat` ou `.command` n'est
couvert**. Une modification de lanceur se teste à la main, sur les deux OS.

La checklist de [.github/pull_request_template.md](.github/pull_request_template.md)
fait référence ; elle couvre aussi la mise à jour de `docs/CODEMAP.md` et la
non-régression.

## Versionnage, changelog, tags

- Versionnage sémantique `X.Y.Z`, source de vérité dans le fichier `VERSION`.
- `Z` (patch) pour un correctif ; `Y` (minor) pour un chantier structurant ;
  `X` (major) uniquement sur demande explicite.
- Un commit qui change un comportement visible met à jour `CHANGELOG.md` **via
  le script**, jamais à la main :

  ```bash
  python scripts/update_changelog.py
  ```

- Les commits purement internes (doc, outillage, typo) ne bumpent pas la version.
- Chaque bump reçoit un tag annoté sur le commit de bump exact, celui qui porte
  le `VERSION` à jour :

  ```bash
  git tag -a v1.2.3 -m "v1.2.3" && git push origin v1.2.3
  ```

- Release GitHub uniquement pour un bump `Y` ou `X`, titrée `vX.Y` sans le `Z`,
  marquée Latest. Quand un patch sort après une release existante, la faire
  pointer sur le nouveau tag **et** régénérer ses notes dans la même opération :

  ```bash
  gh release edit v1.2 --tag v1.2.3 --notes "..."
  ```

  Déplacer le tag seul laisse le texte de la release périmé.

## Pièges du dépôt

- **`starlette` est épinglé dans [`requirements.txt`](requirements.txt) bien que
  transitif.** Ce n'est pas un oubli : `starlette` 1.4.0 a rendu obligatoire un
  argument que le middleware gzip de Streamlit ne passe pas, ce qui fait tomber
  toutes les requêtes en erreur 500. Le commentaire du fichier et
  `tests/test_dependencies.py` gardent le coup ; ne pas « nettoyer » cette ligne.
- **Les `.bat` restent en ASCII, sans accents**, seule exception à la règle
  UTF-8. Les `.command` et tout le reste sont en UTF-8 accentué.
- **Les lanceurs existent en double** (`run_app`, `create_venv`,
  `update_project`, chacun en `.bat` et `.command`). Un changement de
  comportement se répercute dans les deux, sous peine de divergence silencieuse
  entre Windows et macOS.

## Règles à ne jamais enfreindre

- **Ne jamais lire/ouvrir/parser les fichiers Parquet SIRENE** (seuls leurs
  chemins servent de paramètres d'entrée).
- **UTF-8 partout** : vérifier les accents FR dans l'UI, l'export Excel et les
  docs (exception des `.bat`, ci-dessus).
- Aucun secret en dur ; aucun fichier généré, environnement virtuel, cache ou
  export versionné.
