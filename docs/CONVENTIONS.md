# Conventions de code - Règles transverses (génériques, tout projet)

> Règles courtes pour toute contribution humaine ou IA, indépendantes du langage.
> Les règles spécifiques au projet (nommage métier, architecture interne) sont ajoutées séparément.

## Langue et style
- Docstrings et commentaires : denses, orientés "pourquoi" (pièges, invariants), jamais la genèse.
- Ne pas renommer sans nécessité : les noms sont le contrat des harnais de non-régression et des intégrations.
- Respecter la limite de longueur de ligne déjà en vigueur dans le projet (adopter l'existant, ne pas l'imposer arbitrairement).

## Où mettre quoi
- Un réglage (seuil, variable, constante) va dans la config, jamais en dur dans la logique.
- Accès/sélection de données séparés du calcul métier (pas de logique métier dans la couche d'accès aux données).
- Une fonctionnalité générique (utilisable par plusieurs modules) va dans une couche transverse ; une fonctionnalité spécifique reste dans son module/domaine dédié.

## Imports et dépendances
- Imports absolus de préférence.
- Sens unique entre couches (ex: runtime → data → logique métier → UI), jamais l'inverse.
- Aucune nouvelle dépendance externe sans justification forte.

## Données
- Toute source de données externe (fichier legacy, base tierce) : lecture seule côté application, sauf mécanisme explicite documenté de mise à jour avec sauvegarde préalable.
- Ne jamais écrire directement dans un fichier de données partagé sans passer par la fonction de persistance dédiée et testée.

## Non-régression obligatoire pour tout refactor
1. Capturer un état de référence avant modification (harnais dédié).
2. Modifier.
3. Vérifier 100% identique après, sauf changement de comportement voulu et justifié dans le message de commit/PR.

## Git
- Ne jamais committer sans demande explicite de l'utilisateur.
- Environnements, caches, artefacts d'export : jamais versionnés.
