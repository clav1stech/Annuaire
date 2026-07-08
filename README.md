# Annuaire_SIRENE

Application locale Streamlit pour contrôler une liste d'identifiants SIRET/SIREN à partir des fichiers SIRENE au format Parquet, enrichir les informations établissement/unité légale, détecter des cas potentiels de déménagement/transfert/remplacement, et exporter en Excel.

## Prérequis

- Windows 10/11
- Python 3.11 ou 3.12 (plage officiellement testée), ou Python 3.14 (supporté grâce aux wheels précompilées `pyarrow`/`duckdb`, non testé aussi largement)
- Fichiers SIRENE au format Parquet disponibles en local

## Installation

1. Ouvrir un terminal dans le dossier du projet.
2. Exécuter:

```bat
create_venv.bat
```

Ce script:
- affiche la version de Python détectée et avertit si elle est hors de la plage testée (3.11-3.12), en demandant confirmation avant de continuer,
- crée `.venv_annuaire_sirene` si nécessaire,
- installe/upgrade `pip`,
- installe les dépendances depuis `requirements.txt`, en forçant `pyarrow` et `duckdb` (`>=15,<25` et `>=1.1,<2`) à utiliser uniquement des wheels précompilées (`--only-binary`) pour éviter une compilation depuis les sources qui échouerait faute de cmake/Visual Studio.

## Lancement

```bat
run_app.bat
```

L’interface Streamlit s’ouvre dans le navigateur.

## Fichiers SIRENE attendus

Téléchargement des fichiers Parquet SIRENE: https://www.data.gouv.fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret

- Obligatoires:
  - `stocketablissement` (fichier parquet ou dossier parquet) — un enregistrement par établissement (SIRET): adresse, statut administratif (actif/fermé), code activité (NAF), date de création, indicateur siège social. C'est la table de base pour le statut et l'adresse de chaque SIRET.
  - `stockunitelegale` (fichier parquet ou dossier parquet) — un enregistrement par unité légale (SIREN): dénomination/nom, catégorie juridique, statut administratif et statut de diffusion, activité principale. Sert à enrichir chaque SIRET avec l'identité de l'entreprise.
- Optionnels:
  - `stocketablissementlienssuccession` — table officielle des liens de succession SIRENE (SIRET prédécesseur → SIRET successeur lors d'un transfert/déménagement d'établissement).
  - `stocketablissementhistorique` — historique des états successifs d'un établissement (adresses et statuts précédents dans le temps).

Impact de l'absence des fichiers optionnels sur le résultat:
- Sans `stocketablissementlienssuccession`: pour les SIRET fermés, le remplaçant recommandé ne peut plus provenir du lien de succession officiel; l'application retombe sur une heuristique plus faible (un autre établissement actif du même SIREN, s'il existe). La note d'analyse ne peut jamais indiquer "Succession", et le compteur "Fermés avec succession officielle" reste à 0.
- Sans `stocketablissementhistorique`: aucune adresse ou statut antérieur n'est disponible pour un SIRET; l'application ne peut plus confirmer un historique de déménagement et se limite à l'état courant (photo unique) fourni par `stocketablissement`.

L’application détecte les colonnes disponibles de manière défensive selon le millésime et n’échoue pas si certaines colonnes attendues sont absentes.

## Exemple d’usage

1. Charger un fichier utilisateur (`.xlsx`, `.csv` ou `.parquet`) contenant des identifiants SIRET/SIREN.
2. Si le fichier est Excel, choisir la feuille.
3. Indiquer s’il y a une ligne d’en-tête.
4. Choisir les colonnes d'entrée à exporter dans le report final (checkbox).
5. Sélectionner la colonne d'identifiants (SIRET/SIREN).
   - Privilégier autant que possible une colonne SIRET plutôt que SIREN: un SIREN identifie l'entreprise mais pas un établissement précis, l'application retombe alors sur le siège social, ce qui peut créer de faux doublons SIRET si l'entreprise a plusieurs établissements.
   - Si le fichier source a des données partielles (parfois SIRET renseigné, parfois seulement SIREN), on peut créer une colonne mixte sous Excel (ex. en priorisant le SIRET si présent, sinon le SIREN) et la sélectionner ici: l'application sait traiter une colonne mixte SIRET/SIREN, en retombant sur le siège social pour chaque valeur reconnue comme un SIREN.
   - Optionnel: inclure aussi les lignes hors France si l'identifiant est valide (SIRET 14 + Luhn ou SIREN 9 + Luhn).
   - Si une colonne Pays est utilisée, les valeurs vides (et `0`) sont conservées dans l'analyse (traitées comme "pays non précisé").
6. Renseigner les chemins Parquet SIRENE.
   - Le filtre Pays (si sélectionné) reste actif même si la colonne Pays n'est pas exportée.
7. Choisir le chemin de sortie Excel:
   - par défaut: dossier Téléchargements avec le nom du fichier d'entrée + horodatage,
   - saisie manuelle dans le champ, ou
   - bouton **Browse...** sur la même ligne.
8. Cliquer sur **Exécuter le contrôle SIRET/SIREN**.
9. Suivre la barre de progression et les métriques d’avancement/succès/échecs.
10. Le fichier Excel est enregistré à l’emplacement choisi et reste téléchargeable dans l’UI.

## Sortie Excel

Onglets produits:
- `siret_overview` (tableau unique orienté nettoyage base tiers)
- `statistiques` (aperçu synthétique: absents, invalides, fermés avec/sans remplaçant, types de succession, radiés, actifs, [ND])
- `anomalies` (Motif + colonnes d'entrée sélectionnées: identifiants manquants, non trouvés, invalides)
- `siret_a_cloturer` (SIRET fermés sans remplaçant + SIRET radiés)
- `dictionnaire_colonnes` (description métier simple des colonnes principales)

### Feuille `siret_overview`

Cette feuille est le tableau principal du report: une ligne par identifiant analysé, avec toutes les colonnes utiles au nettoyage. Pour faciliter la lecture d'un fichier potentiellement large, la ligne 1 regroupe les colonnes par catégorie (couleur de fond commune, centrée sur la plage de colonnes du groupe) et la ligne 2 porte les en-têtes détaillés de chaque colonne; les données démarrent en ligne 3.

Les 4 catégories (couleur de la ligne 1) sont, dans l'ordre d'apparition des colonnes:
- **Input utilisateur** (bleu clair) — toutes les colonnes d'entrée sélectionnées par l'utilisateur à l'étape 4 (colonnes du fichier source telles quelles), plus `siret_entree` (l'identifiant brut tel que saisi, avant nettoyage).
- **Contrôles format** (vert clair) — colonnes techniques produites par la validation de l'identifiant: `siret_normalise`, `identifiant_recherche`, `siret_format_valide`, `siret_doublon_entree`, `siren_doublon_entree`.
- **Données brutes SIRENE** (orange clair) — toutes les colonnes issues directement des fichiers SIRENE (établissement, unité légale, succession, historique...), sans transformation d'analyse métier. C'est la catégorie "par défaut": toute colonne qui n'appartient à aucune des trois autres groupes y est rattachée.
- **Analyse situation** (jaune) — colonnes calculées par l'application pour qualifier chaque ligne: toutes les colonnes préfixées `analysis_` (priorité, note d'analyse, etc.), ainsi que `siret_status`, `cleaning_action` et `siret_remplacement_recommande`.

En complément du regroupement par colonnes, certaines cellules de données sont elles-mêmes colorées pour faciliter le tri visuel:
- `siret_status`: Actif (vert), Fermé (orange), Non trouvé (bleu), Invalide (orange clair), Radiée (jaune pâle).
- `analysis_priority`: Haute (orange foncé), Moyenne (jaune), Basse (vert clair).

Le classement d'une colonne dans une catégorie ne dépend que de son nom technique (préfixe/liste fixe), pas de son contenu; si une nouvelle colonne SIRENE apparaît dans les fichiers Parquet fournis, elle sera automatiquement rattachée à "Données brutes SIRENE".

Marqueur de diffusion partielle:
- `analysis_nd_detecte` indique `Oui` si un marqueur `[ND]` est détecté dans les données.

Lecture des stats "absents":
- `SIRET en doublon dans le fichier d'entrée` = lignes où la clé normalisée apparaît au moins 2 fois dans les lignes analysées.
- `Identifiants absents dans le fichier d'entrée` = lignes sans identifiant (vide ou 0).
- `SIRET sans correspondance dans SIRENE` = identifiants présents/valides mais non retrouvés dans la base SIRENE.
- `Fournisseurs Etranger` = lignes dont le pays est renseigné et différent de FR/FRA/France.
- `Fournisseurs pays non précisé` = lignes dont le pays est vide/non renseigné (ou `0`) et conservées dans l'analyse.
- `dont Hors France retenus (identifiant valide)` = affiché uniquement si l'option d'inclusion est cochée; lignes hors France conservées car l'identifiant passe le contrôle de format (SIRET/SIREN).

Règle métier appliquée pour les SIRET fermés:
- si un remplaçant est identifié: les données établissement affichées sont celles du remplaçant,
- si aucun remplaçant n'est identifié: les données business sont vidées.

Statuts `siret_status` dans le report:
- `Actif`
- `Fermé`
- `Radiée`
- `Invalide`
- `Non trouvé`

Définition métier:
- `Fermé` = l'établissement du SIRET est fermé, mais au moins un autre établissement du même SIREN est actif.
- `Radiée` = la société (SIREN) n'a plus aucun établissement actif.

## Limites connues

- Les règles de détection de déménagement/transfert sont volontairement simples (heuristique initiale).
- La qualité des résultats dépend de la complétude des colonnes présentes dans les millésimes fournis.
- L’application reste 100 % locale et ne dépend d’aucune base externe.

## Export project snapshot (backup + AI handoff)

Script available at project root: export_project.py.

What it exports:
- .py, .bat, .md, .txt
- excludes .parquet, virtual env folders, caches, export/, requirements.txt

Output location:
- export/export_<project>_<timestamp>_vX.Y.Z/
- includes copied files, manifest.txt, and one AI-ready context file with all code/content
- also creates a .zip archive of the snapshot folder

Run from VS Code Play / Run and Debug:
- select configuration Python: Export Project Snapshot
- click Play
