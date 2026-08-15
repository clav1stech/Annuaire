# Sortie Excel — structure du rapport

Détail des onglets produits par l'application et de la mise en forme de la feuille principale.
Vue d'ensemble et usage courant : [README.md § Utilisation](../README.md#utilisation).

## Onglets produits

- `siret_overview` — tableau unique orienté nettoyage de base tiers.
- `statistiques` — aperçu synthétique : absents, invalides, fermés avec/sans remplaçant, types de succession, radiés, actifs, `[ND]`.
- `anomalies` — Motif + colonnes d'entrée sélectionnées : identifiants manquants, non trouvés, invalides.
- `siret_a_cloturer` — SIRET fermés sans remplaçant + SIRET radiés.
- `dictionnaire_colonnes` — description métier des colonnes principales.

## Feuille `siret_overview`

Une ligne par identifiant analysé. La ligne 1 regroupe les colonnes par catégorie (fond de couleur commun, centré sur la plage du groupe), la ligne 2 porte les en-têtes détaillés, les données démarrent en ligne 3.

Les 4 catégories, dans l'ordre d'apparition :

| Catégorie | Couleur | Contenu |
|---|---|---|
| Input utilisateur | bleu clair | colonnes d'entrée sélectionnées par l'utilisateur, plus `siret_entree` (identifiant brut avant nettoyage) |
| Contrôles format | vert clair | `siret_normalise`, `identifiant_recherche`, `siret_format_valide`, `siret_doublon_entree`, `siren_doublon_entree` |
| Données brutes SIRENE | orange clair | colonnes issues directement des fichiers SIRENE (établissement, unité légale, succession, historique), sans transformation métier — catégorie par défaut |
| Analyse situation | jaune | colonnes préfixées `analysis_`, plus `siret_status`, `cleaning_action`, `siret_remplacement_recommande` |

Le classement dépend uniquement du nom technique de la colonne (préfixe ou liste fixe), pas de son contenu : une nouvelle colonne SIRENE apparaissant dans un millésime est automatiquement rattachée à « Données brutes SIRENE ».

Certaines cellules de données sont colorées pour faciliter le tri visuel :

- `siret_status` — Actif (vert), Fermé (orange), Non trouvé (bleu), Invalide (orange clair), Radiée (jaune pâle) ;
- `analysis_priority` — Haute (orange foncé), Moyenne (jaune), Basse (vert clair).

## Colonnes d'analyse

### `analysis_nd_detecte`

`Oui` si un marqueur `[ND]` (donnée non diffusible) est détecté dans les données.

### `analysis_alerte_siren_different`

`Oui` quand le remplaçant recommandé porte un SIREN différent de l'identifiant d'entrée, `Non` quand il porte le même, vide s'il n'y a pas de remplaçant.

Ce cas n'est **pas** une anomalie : dans la base SIRENE, 22 % des liens de succession pointent vers un établissement d'un autre SIREN (cession ou apport d'établissement). Il change en revanche d'entité juridique — donc de contrat, de RIB et de n° de TVA — et mérite une vérification manuelle avant reprise dans une base tiers. Les colonnes d'unité légale (dénomination, état, compteurs d'établissements) sont alors laissées vides plutôt que reprises de l'entreprise d'origine.

Quand plusieurs liens de succession existent pour un même SIRET fermé (cas fréquent : 368 000 SIRET dans le stock SIRENE), l'application retient le lien à la **date de succession la plus récente**, puis celui portant une continuité économique, puis le plus petit SIRET successeur. Le choix est reproductible d'une exécution à l'autre.

Détail complet de ces règles, chiffres à l'appui et limite connue : [`SUCCESSION.md`](SUCCESSION.md).

### `analysis_data_applied`

- `INPUT_SIRET_DATA` — les colonnes métier décrivent l'identifiant d'entrée.
- `REPLACEMENT_SIRET_DATA` — elles décrivent le remplaçant recommandé.
- `NO_DATA_REPLACEMENT_NOT_LOADED` — un remplaçant est recommandé, mais son établissement n'a pas été chargé dans le lot interrogé (le plus souvent parce qu'il relève d'un autre SIREN, hors du périmètre des SIREN d'entrée). C'est une **donnée absente du lot, pas un remplacement invalide** : le SIRET reste renseigné dans `siret_remplacement_recommande`, seules les colonnes métier sont vides.
- `NO_DATA_CLOSED_NO_REPLACEMENT` — SIRET fermé sans remplaçant identifié.

## Lecture des statistiques « absents »

- `SIRET en doublon dans le fichier d'entrée` — lignes où la clé normalisée apparaît au moins 2 fois parmi les lignes analysées.
- `Identifiants absents dans le fichier d'entrée` — lignes sans identifiant (vide ou `0`).
- `SIRET sans correspondance dans SIRENE` — identifiants présents et valides, non retrouvés dans la base.
- `Fournisseurs Etranger` — lignes dont le pays est renseigné et différent de FR/FRA/France.
- `Fournisseurs pays non précisé` — lignes dont le pays est vide ou `0`, conservées dans l'analyse.
- `dont Hors France retenus (identifiant valide)` — affiché uniquement si l'option d'inclusion est cochée ; lignes hors France conservées car l'identifiant passe le contrôle de format.

## Statuts et règle métier

Valeurs de `siret_status` : `Actif`, `Fermé`, `Radiée`, `Invalide`, `Non trouvé`.

- `Fermé` = l'établissement du SIRET est fermé, mais au moins un autre établissement du même SIREN est actif.
- `Radiée` = la société (SIREN) n'a plus aucun établissement actif.

Pour les SIRET fermés : si un remplaçant est identifié, les données établissement affichées sont celles du remplaçant ; sinon, les données métier sont vidées.
