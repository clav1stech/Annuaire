# Changelog

## 1.1.0 - 2026-07-23
- Téléchargement automatique des fichiers Parquet SIRENE depuis data.gouv.fr (détection des versions publiées, manifeste local de version, bouton unique de mise à jour avec barre de progression et volume en Mo) ; tolérance aux deux nomenclatures NAF (rév. 2 et NAF 2025), la nomenclature retenue étant exposée dans le diagnostic de schéma.

## 1.0.7 - 2026-07-23
- UI : bouton « Mettre à jour maintenant » quand une nouvelle version est détectée, sans passer par le terminal
- Correctif : `create_venv.bat` / `update_project.bat` retenaient l'alias Microsoft Store comme interpréteur Python au lieu d'une installation réelle (Anaconda notamment)
- Typage statique `mypy` ajouté au lint et à la CI ; matrice CI (3.11 → 3.14) resynchronisée avec la documentation

## 1.0.6 - 2026-07-22
- UI: affichage clair du statut de vérification de version (à jour / nouvelle version / échec du check, avec raison)

## 1.0.5 - 2026-07-22
- Alerte Parquet manquant affichée dès le début de l'app (avant l'upload du fichier) et recherche de fichier Parquet dans un dossier accélérée (arrêt au premier match trouvé).

## 1.0.4 - 2026-07-22
- Ajout d'un script de mise à jour du code (update_project), détection automatique de nouvelle version au lancement, et clarifications README (poids Parquet, format parquet vs csv).

## 1.0.3 - 2026-07-22
- Scripts macOS/Linux renommés en .command (run_app, create_venv) pour un double-clic direct dans Terminal.app au lieu de VSCode ; doc mise à jour en conséquence.

## 1.0.2 - 2026-07-22
- Support Python 3.13/3.14 en CI, documentation Python/Homebrew mise a jour, actions CI depreciees remplacees.

Toute nouvelle entrée est ajoutée par `scripts/update_changelog.py` (voir `docs/CLAUDE.md` § Changelog), jamais saisie à la main.

## 1.0.1 - 2026-07-22
- Compatibilite macOS (scripts .sh), depreciation de la recherche par nom (dormant/), fusion des consignes IA (AGENTS.md + docs/CLAUDE.md).

## 1.0.0 - 2026-07-22
- Baseline versionnée du projet (mise en place du versionnage sémantique X.Y.Z).
