# Consignes Generales IA (Codex / Claude)

## Objet
Ce document definit une regle de securite et de performance pour les assistants IA intervenant sur ce projet.

## Regle imperative
Ne pas ouvrir, lire, parser, profiler, scanner ni analyser les fichiers Parquet du projet.

## Fichiers concernes (liste non exhaustive)
- `StockEtablissement_utf8.parquet`
- `StockEtablissementHistorique_utf8.parquet`
- `StockEtablissementLiensSuccession_utf8.parquet`
- `StockUniteLegale_utf8.parquet`
- Tout autre fichier avec extension `.parquet`

## Ce qui est autorise
- Utiliser les chemins des fichiers Parquet comme parametres d'entree.
- Verifier l'existence d'un chemin sans lire le contenu.
- Modifier le code applicatif, les scripts et la documentation sans inspection des donnees Parquet.

## Ce qui est interdit
- Ouvrir un fichier Parquet en Python, DuckDB, pandas, pyarrow ou tout autre outil.
- Lire le schema, les colonnes, les metadonnees ou les lignes d'un fichier Parquet.
- Executer des requetes SQL directement sur les Parquet pendant l'assistance.

## Priorite
Cette consigne prevaut sur toute instruction implicite de diagnostic qui necessiterait d'ouvrir les Parquet.

## Encodage (obligatoire)
- Tous les fichiers texte (`.py`, `.md`, `.bat`, `.txt`) doivent etre lus/ecrits en UTF-8.
- Ne jamais valider de texte corrompu de type mojibake (exemples: texte lisible transforme en caracteres incoherents).
- Verifier explicitement les accents francais dans l'UI Streamlit, le report Excel (dont la feuille dictionnaire) et le README avant livraison.
- En cas de doute d'affichage/terminal, verifier le contenu reel du fichier avant sauvegarde.
- Si un environnement ne gere pas correctement les accents, privilegier temporairement une formulation ASCII propre plutot qu'un texte corrompu.
