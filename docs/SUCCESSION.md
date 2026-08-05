# Succession et SIRET de remplacement

> Pourquoi un SIRET fermé peut se voir recommander un remplaçant appartenant à une **autre entreprise**, comment l'application choisit ce remplaçant, et comment lire les colonnes qui en rendent compte.
> Traite la question posée dans l'issue #6. Règles de code : `docs/CONVENTIONS.md`. Colonnes de sortie côté utilisateur : `README.md` § Feuille `siret_overview`.

## Le constat de départ

Une utilisatrice a signalé un SIRET de remplacement dont le **SIREN n'avait aucun rapport** avec celui d'origine, sur des lignes portant `analysis_data_applied = NO_DATA_REPLACEMENT_NOT_LOADED`. Deux questions distinctes se cachaient derrière ce signalement, et elles appellent des réponses opposées.

## 1. Un remplaçant sur un autre SIREN n'est pas une anomalie

Mesures sur `StockEtablissementLiensSuccession` (stock de juillet 2026, 9,69 M de liens) :

| Lien de succession | Nombre | Part |
|---|---|---|
| Successeur sur le **même** SIREN | 7 552 166 | 78 % |
| Successeur sur un **autre** SIREN | 2 140 693 | 22 % |
| … dont continuité économique déclarée | 1 646 907 | 77 % des liens inter-SIREN |

Le répertoire SIRENE relie couramment un établissement à un successeur d'une autre entreprise : c'est le cas d'une **cession ou d'un apport d'établissement**, où l'activité et le lieu continuent sous une autre entité juridique. Le lien est donc légitime et exploitable.

Il reste qu'un changement d'entité juridique change le contrat, le RIB et le numéro de TVA. L'application ne peut ni l'écarter, ni l'appliquer en silence : **elle le signale**.

- `analysis_alerte_siren_different` = `Oui` (autre SIREN) / `Non` (même SIREN) / vide (pas de remplaçant).
- Le cas est repris en clair dans `analysis_status_note` et compté dans la feuille `statistiques` (« Remplaçants sur un autre SIREN »).
- Les colonnes d'unité légale (dénomination, état, compteurs d'établissements) sont laissées **vides** plutôt que reprises de l'entreprise d'origine, qui ne décrit plus rien.

Implémentation : `_build_siret_overview` pour la colonne d'alerte, `_apply_closed_row_data_policy` pour le vidage des champs d'unité légale (`src/pipeline.py`).

## 2. Le vrai défaut : le lien retenu était arbitraire

Un même SIRET prédécesseur porte souvent **plusieurs** liens de succession :

| | Nombre |
|---|---|
| SIRET prédécesseurs | 9 289 019 |
| … portant plus d'un lien | 367 862 |
| … dont les successeurs relèvent de plusieurs SIREN | 254 265 (69 % des précédents) |
| Maximum de liens pour un seul prédécesseur | 175 |

Jusqu'à la v1.1.7, `_succession_map_from_links` faisait `drop_duplicates(keep="first")` : le remplaçant retenu dépendait de **l'ordre de lecture du fichier Parquet**, sans aucun critère métier. Il pouvait désigner une reprise vieille de vingt ans par une entreprise sans rapport, alors qu'un mouvement récent décrivait la situation réelle.

Exemple réel, prédécesseur `32686414700029` :

| Successeur | Date du lien | Continuité économique | Lecture |
|---|---|---|---|
| `41306451000014` | 1997-08-01 | oui | reprise ancienne, autre entreprise |
| `55211071000068` | 2003-04-05 | oui | autre reprise, autre entreprise encore |
| `32686414700037` | 2011-07-25 | non | **transfert interne, même SIREN** |

Depuis la v1.1.8, l'ordre est explicite et documenté dans le code :

1. `dateLienSuccession` la plus récente (dates SIRENE en ISO, donc l'ordre lexicographique suffit ; une date absente passe en dernier) ;
2. puis `continuiteEconomique` vraie ;
3. puis le SIRET successeur le plus petit, pour rester déterministe à égalité parfaite.

Le résultat ne dépend plus de l'ordre du fichier. Impact mesuré sur le stock complet : 197 781 prédécesseurs (2,1 %) changent de remplaçant, dont 19 943 repassent d'un autre SIREN vers le même SIREN.

Ce choix de premier niveau alimente ensuite la cascade existante (`_resolve_active_successor`, v1.1.4) qui suit la chaîne jusqu'à un successeur exploitable.

## 3. `NO_DATA_REPLACEMENT_NOT_LOADED` ne veut pas dire « remplacement invalide »

Valeurs possibles de `analysis_data_applied` :

| Valeur | Signification |
|---|---|
| `INPUT_SIRET_DATA` | les colonnes métier décrivent l'identifiant d'entrée |
| `REPLACEMENT_SIRET_DATA` | elles décrivent le remplaçant recommandé |
| `NO_DATA_REPLACEMENT_NOT_LOADED` | un remplaçant est recommandé, mais son établissement **n'a pas été chargé** dans le lot interrogé |
| `NO_DATA_CLOSED_NO_REPLACEMENT` | SIRET fermé, aucun remplaçant identifié |

Le troisième cas est le plus mal lu. L'application n'interroge SIRENE que sur le périmètre des identifiants d'entrée et de leurs SIREN ; un remplaçant relevant d'un **autre** SIREN tombe hors de ce périmètre, donc hors du lot chargé. C'est une **donnée absente**, pas un lien invalide : le SIRET reste renseigné dans `siret_remplacement_recommande`, seules les colonnes métier sont vides. La légitimité du lien se lit dans `analysis_alerte_siren_different`, qui reste calculable dans ce cas puisqu'elle ne compare que les 9 premiers chiffres.

## Limite connue

Quand la chaîne partant du lien le plus récent aboutit à une impasse (successeur fermé, sans successeur exploitable à son tour), l'application ne redescend pas vers les liens plus anciens : elle retombe sur la règle du frère actif du même SIREN, voire ne propose rien. Un lien plus ancien mais encore exploitable est donc ignoré. Le comportement reste préférable au tirage arbitraire d'avant, et le cas est rare (2 lignes sur 1 610 dans l'échantillon de contrôle), mais il est identifié : essayer les liens suivants par ordre d'ancienneté serait l'amélioration naturelle.

## Vérifier une modification de ces règles

Ces règles touchent le cœur du livrable : toute modification doit être mesurée, pas supposée. Le protocole utilisé pour la v1.1.8, reproductible :

1. Créer un worktree sur la version de référence (`git worktree add <dir> <tag>`).
2. Construire un échantillon d'entrée couvrant explicitement les populations sensibles — actifs, fermés sans lien, fermés à lien unique, fermés multi-liens à SIREN divergents, SIREN seuls, identifiants limites.
3. Exécuter `run_siret_control_pipeline` avec les deux versions du code sur les **mêmes** fichiers Parquet, et comparer `siret_overview` colonne par colonne.
4. Attendu : aucune ligne modifiée hors des populations visées, et statut métier (`siret_status`, `cleaning_action`, `siret_format_valide`, `analysis_priority`) identique partout.

Mesure obtenue en v1.1.8 sur 1 610 identifiants réels : 36 lignes modifiées, toutes fermées avec lien de succession ; 0 sur les actifs, les fermés sans lien, les SIREN seuls et les cas limites ; aucun remplaçant gagné ni perdu ; statuts métier identiques sur 100 % des lignes.

Les tests unitaires correspondants (service SIRENE simulé, aucun Parquet lu) sont dans `tests/test_pipeline_succession.py`.
