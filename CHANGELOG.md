# Changelog

## 1.1.11 - 2026-08-15
- Documentation utilisateur réorganisée : le README est recentré sur l'installation, l'usage courant et la configuration des fichiers SIRENE ; le dépannage (terminal, scripts, cas macOS, mise à jour hors ligne par ZIP, détection des Parquet, nomenclature NAF) passe dans un guide dédié `docs/DEPANNAGE.md` et la structure du rapport Excel dans `docs/EXPORT_EXCEL.md`. Nouvelle procédure de signalement d'un problème : issue GitHub pour un cas purement technique, e-mail au développeur dès qu'une donnée client est en jeu, aucune donnée client dans une issue publique. `CONTRIBUTING.md` complété (tests sans Parquet ni réseau, flux tags et releases, pièges du dépôt).

## 1.1.10 - 2026-08-05
- Fichiers SIRENE installés manuellement utilisables sans mise à jour obligatoire ; ajout d'une mise à jour hors ligne du code par glisser-déposer du ZIP GitHub, avec validation de l'archive et remplacement des seuls fichiers nécessaires.

## 1.1.9 - 2026-08-05
- Écriture des fichiers tolérante aux dossiers synchronisés : le remplacement d'un fichier téléchargé ou du manifeste de version est réessayé quand la destination est momentanément verrouillée (OneDrive, antivirus), au lieu d'échouer immédiatement sur une traceback « Accès refusé » après plusieurs centaines de Mo transférés ; si le verrou persiste, l'application affiche un message explicite et conserve le fichier téléchargé ainsi que le manifeste précédent. Le README recommande désormais d'installer le projet hors dossier synchronisé (OneDrive/Dropbox/Google Drive), y compris quand Bureau et Documents y sont redirigés par l'entreprise.

## 1.1.8 - 2026-08-05
- Remplaçant recommandé : quand un SIRET fermé porte plusieurs liens de succession, le lien retenu est désormais le plus récent (puis continuité économique, puis SIRET) au lieu du premier lu dans le fichier, choix jusqu'ici arbitraire qui pouvait désigner une reprise ancienne par une entreprise sans rapport ; nouvelle colonne `analysis_alerte_siren_different` (+ ligne de statistiques et mention dans la note d'analyse) signalant les remplaçants relevant d'un autre SIREN, et documentation des valeurs de `analysis_data_applied` (dont `NO_DATA_REPLACEMENT_NOT_LOADED` = donnée absente du lot chargé, pas remplacement invalide).

## 1.1.7 - 2026-08-05
- Clé de contrôle SIRET de La Poste : les SIRET du SIREN 356000000 sont désormais reconnus valides quand la somme de leurs 14 chiffres est un multiple de 5 (règle INSEE propre à ce SIREN), en plus de la clé de Luhn ; ils étaient jusqu'ici classés `INVALID_SIRET_FORMAT` à tort.

## 1.1.6 - 2026-08-05
- `run_app` devient le seul script à lancer : il crée l'environnement virtuel au premier démarrage (plus besoin de lancer `create_venv` séparément) et répare un environnement incomplet avant d'ouvrir l'application.

## 1.1.5 - 2026-08-05
- Correctif erreur 500 au lancement (starlette 1.4 incompatible avec le middleware gzip de Streamlit) : la version de starlette est désormais épinglée et un test de non-régression vérifie la compatibilité ; `run_app` réinstalle automatiquement les dépendances quand `requirements.txt` a changé, sans repasser par `create_venv`.

## 1.1.4 - 2026-08-05
- Remplacement recommandé : la chaîne de succession est suivie jusqu'à un SIRET exploitable (successeur fermé ignoré, reprise en cascade sur plusieurs niveaux, garde anti-cycle et limite de profondeur) au lieu de s'arrêter au premier successeur.

## 1.1.3 - 2026-07-29
- Ajout du n° de TVA intracommunautaire calculé (à partir du SIREN) dans les feuilles de sortie de l'export Excel.

## 1.1.2 - 2026-07-25
- Mise a jour zip ne copie que les fichiers modifies et retablit le bit executable des .command.

## 1.1.1 - 2026-07-24
- Correctif : boutons Tout cocher/Tout decocher des colonnes d'entree sans effet visuel (etat des cases a cocher non synchronise) ; suppression du FutureWarning pandas lors du nettoyage des lignes vides.

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
