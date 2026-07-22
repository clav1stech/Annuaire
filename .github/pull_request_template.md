<!-- Merci de lire docs/CLAUDE.md et docs/CONVENTIONS.md avant de contribuer. -->

## Objectif
<!-- Que fait cette PR et pourquoi ? -->

## Type de changement
- [ ] Correctif (patch, bump Z)
- [ ] Évolution structurante (minor, bump Y)
- [ ] Interne uniquement (doc/outillage/typo — pas de bump de version)

## Checklist
- [ ] `pytest -q` passe en local
- [ ] `ruff check .` ne remonte rien
- [ ] `VERSION` et `CHANGELOG.md` mis à jour si comportement visible modifié (via `scripts/update_changelog.py`)
- [ ] `docs/CODEMAP.md` mis à jour si la structure du code a changé
- [ ] Encodage UTF-8 vérifié (accents FR corrects dans UI / Excel / docs)
- [ ] Aucun fichier Parquet SIRENE lu/versionné, aucun secret en dur

## Non-régression (si refactor)
<!-- Décrire l'état de référence capturé avant/après (cf. docs/CLAUDE.md § Non-régression). -->
