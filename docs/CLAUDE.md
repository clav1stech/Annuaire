# Instructions IA - Règles transverses (génériques, tout projet)

> Ce fichier contient les règles indépendantes du langage et du domaine métier.
> Les invariants spécifiques au projet vivent dans une section séparée plus bas (ou dans un fichier dédié).

## Mémoire et consignation des règles
- Dès qu'une règle générale, une convention, une contrainte ou une préférence récurrente de l'utilisateur émerge en discussion, l'ajouter ici dans la section adéquate — ne jamais la laisser seulement dans un commentaire de code ou dans l'échange.
- Ne consigner que les règles durables et générales, pas un détail ponctuel propre à une seule tâche. En cas de doute sur la portée, demander avant d'inscrire.
- Préférer mettre à jour une consigne existante plutôt que d'en empiler une quasi-identique. Garder ce fichier concis et sans doublon.

## Commentaires et documentation
- Les commentaires expliquent le pourquoi (pièges, invariants, points d'attention), jamais le quoi ni la genèse.
- Proscrire les commentaires de circonstance qui répondent à une discussion ou un bug découvert avec l'IA (ex: "corrigé suite à...", "ajouté car l'IA a détecté..."). Reformuler en constat intemporel sur le code lui-même.

## Configuration
- Tout réglage (seuil, variable, constante, clé de config) se déclare dans un fichier de configuration central, jamais en dur dans la logique métier.

## Secrets et sécurité
- Une clé/secret ne vit jamais en dur dans le code, les commits ou les logs, même partiellement.
- Utiliser exclusivement un gestionnaire de secrets (variables d'environnement locales gitignorées, secrets CI, secrets de la plateforme d'hébergement).
- Jamais de valeur par défaut ni de repli silencieux si un secret est absent : échec explicite, jamais un crash non expliqué.

## Git
- Ne jamais committer sans demande explicite de l'utilisateur.
- Fichiers générés, environnements virtuels, caches, exports : toujours gitignorés, jamais versionnés.
- Travail en branche vs main : main pour un changement ponctuel à risque quasi nul et immédiatement déployable ; une branche dédiée pour un chantier structurant multi-commits.

## Versionnage sémantique X.Y.Z
- Z (patch) : à chaque commit impliquant un changement (hors micro mod), cas par défaut.
- Y (minor) : chantier structurant nécessitant une branche dédiée ; remet Z à 0.
- X (major) : jamais décidé par l'IA, uniquement sur demande explicite de l'utilisateur.
- Le bump de version n'a lieu que pour un commit poussé qui change un comportement visible, jamais pour un commit purement interne (doc, outillage, typo, commentaire).
- Le message de commit du bump commence par "vX.Y.Z: résumé".

## Changelog
- Chaque commit qui bump la version doit mettre à jour CHANGELOG.md dans le même commit (entrée X.Y.Z - date, résumé en tête de fichier).
- Pas de saisie manuelle séparée : un script dédié régénère/complète le fichier de façon idempotente (n'ajoute que les versions absentes, ne touche pas aux entrées existantes).

## Non-régression obligatoire pour tout refactor
1. Capturer un état de référence AVANT toute modification (calculs, rendu, sorties) via un harnais dédié, en lecture seule sur les données.
2. Modifier le code.
3. Revérifier APRÈS : 100% identique attendu, mêmes données, mêmes conditions figées (heure, seed, etc.), sauf changement de comportement volontaire justifié explicitement dans le message de commit/PR.

## Écriture de données
- Écriture atomique obligatoire : écrire dans un fichier temporaire puis renommer/remplacer, jamais d'écriture directe qui laisserait un état partiel sur le disque.
- Toute correction de données critiques commence par une sauvegarde datée avant modification.
- Ne jamais corriger des données de production spontanément, même une incohérence apparente : correction uniquement sur demande explicite, après un problème identifié et discuté.

## Architecture et dépendances
- Imports/couches à sens unique, jamais de dépendance circulaire entre modules de même niveau.
- Aucune nouvelle dépendance externe sans justification forte.
- Un fichier CODEMAP (carte du code) et un fichier CONVENTIONS (style, où mettre quoi) sont tenus à jour et lus avant toute intervention, plutôt que de parcourir tout le code.

## Export / partage de contexte vers l'IA
- Prévoir un outil d'export du projet (profil "IA" léger : code + doc + manifeste, sans les gros fichiers de données ; profil "sauvegarde" complet en zip avec rotation des N plus récents).
- Permettre un export ciblé par périmètre (--only module) pour réduire le volume envoyé à l'IA quand la question ne porte que sur une partie du projet.

---

# Invariants spécifiques au projet Annuaire_SIRENE

> Ces règles priment sur les règles génériques ci-dessus en cas de conflit.

## Ne jamais lire les fichiers Parquet SIRENE
- Ne pas ouvrir, lire, parser, profiler, scanner ni analyser les fichiers Parquet du projet (`StockEtablissement_utf8.parquet`, `StockEtablissementHistorique_utf8.parquet`, `StockEtablissementLiensSuccession_utf8.parquet`, `StockUniteLegale_utf8.parquet`, et tout autre `.parquet`).
- Autorisé : utiliser leurs chemins comme paramètres d'entrée, vérifier l'existence d'un chemin sans lire le contenu, modifier code/scripts/doc sans inspecter les données.
- Interdit : ouvrir un Parquet (Python, DuckDB, pandas, pyarrow ou autre), lire schéma/colonnes/métadonnées/lignes, exécuter du SQL directement sur les Parquet pendant l'assistance.
- Cette consigne prévaut sur toute instruction implicite de diagnostic qui nécessiterait d'ouvrir les Parquet.

## Encodage UTF-8 (obligatoire)
- Tous les fichiers texte (`.py`, `.md`, `.bat`, `.sh`, `.txt`) sont lus/écrits en UTF-8.
- Ne jamais valider de texte corrompu de type mojibake (accents transformés en caractères incohérents).
- Vérifier explicitement les accents français dans l'UI Streamlit, le report Excel (dont la feuille dictionnaire) et le README avant livraison.
- En cas de doute d'affichage/terminal, vérifier le contenu réel du fichier avant sauvegarde. Si un environnement ne gère pas correctement les accents, privilégier temporairement une formulation ASCII propre plutôt qu'un texte corrompu.
