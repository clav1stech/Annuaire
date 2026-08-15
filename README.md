# Annuaire_SIRENE

Application locale qui contrôle une liste de SIRET/SIREN contre les fichiers SIRENE au format Parquet, enrichit chaque ligne (établissement + unité légale), détecte les cas de déménagement/transfert/remplacement et exporte le tout en Excel. Elle s'utilise dans le navigateur.

## Sommaire

- [Contexte](#contexte)
- [Démarrage rapide](#démarrage-rapide)
- [Utilisation](#utilisation)
- [Configuration](#configuration)
- [Structure du projet](#structure-du-projet)
- [Contribuer, signaler un problème, versions](#contribuer-signaler-un-problème-versions)
- [Dépannage et FAQ](#dépannage-et-faq)
- [Ce que l'outil permet](#ce-que-loutil-permet)
- [Ce que l'outil ne permet pas](#ce-que-loutil-ne-permet-pas)

## Contexte

Nettoyer une base tiers (fournisseurs, clients) suppose de savoir quels SIRET sont encore actifs, lesquels sont fermés, et par quoi les remplacer. L'Insee republie ces données chaque mois, en fichiers de plusieurs gigaoctets qu'Excel ne sait pas ouvrir.

L'application croise une liste d'identifiants avec les fichiers SIRENE posés sur le poste et produit un rapport Excel. Tout se passe en local, sans appel à une API Insee ou INPI : la fraîcheur du résultat dépend du millésime des fichiers fournis. Son utilisation ne demande pas de savoir programmer.

Périmètre détaillé en fin de page : [Ce que l'outil permet](#ce-que-loutil-permet), [Ce que l'outil ne permet pas](#ce-que-loutil-ne-permet-pas).

## Démarrage rapide

**Prérequis** : Windows 10/11 ou macOS (Linux fonctionne aussi), Python 3.11 à 3.14. Si Python n'est pas installé, prendre l'installeur sur [python.org/downloads](https://www.python.org/downloads/). Sous Windows, cocher **« Add python.exe to PATH »** avant de lancer l'installation.

1. **Décompresser le projet** dans un dossier local, hors OneDrive / Dropbox / Google Drive. Les fichiers SIRENE pèsent plusieurs Go : dans un dossier synchronisé, ils saturent le quota et provoquent des erreurs d'écriture. Voir [Dossier synchronisé](docs/DEPANNAGE.md#dossier-synchronisé-onedrive--co).
2. **Lancer l'application** : double-clic sur `run_app.bat` (Windows) ou `run_app.command` (macOS/Linux). Au premier lancement, il installe l'environnement Python, ce qui prend quelques minutes.

   ```
   [INFO] Premiere utilisation : installation de l'environnement en cours.
   [INFO] Cela peut prendre quelques minutes ; ne pas fermer cette fenetre.
   ```

   > ⚠️ **Laisser cette fenêtre noire ouverte pendant toute la durée d'utilisation.** C'est elle qui fait tourner l'application : la fermer coupe l'application, même si l'onglet du navigateur reste affiché. La fermer est aussi la façon de quitter en fin de travail.

3. **Récupérer les fichiers SIRENE** : dans l'interface qui s'ouvre, cliquer sur **« Mettre à jour les données SIRENE »** (encadré « Données SIRENE », en haut de page). Compter 3,5 à 4 Go au premier téléchargement, à refaire environ une fois par mois.
4. **Charger son fichier et exécuter le contrôle**, voir [Utilisation](#utilisation).

## Utilisation

### Exécuter un contrôle

1. Charger un fichier utilisateur (`.xlsx`, `.csv` ou `.parquet`) contenant des identifiants SIRET/SIREN.
2. Si le fichier est Excel, choisir la feuille ; indiquer s'il y a une ligne d'en-tête.
3. Cocher les colonnes d'entrée à reprendre dans le rapport final.
4. Sélectionner la colonne d'identifiants :
   - privilégier une colonne **SIRET** plutôt que SIREN. Un SIREN identifie l'entreprise, pas l'établissement : l'application retombe alors sur le siège social, ce qui peut créer de faux doublons.
   - une colonne **mixte SIRET/SIREN** est acceptée. Elle existe rarement telle quelle dans un export, il faut donc la créer sous Excel avant de charger le fichier : avec le SIRET en colonne B et le SIREN en colonne C, ajouter une colonne `=IF(ISBLANK(B2), C2, B2)` (`=SI(ESTVIDE(B2); C2; B2)` en français) et la recopier vers le bas. Chaque valeur reconnue comme un SIREN passe par le siège social.
   - option : inclure les lignes hors France si l'identifiant est valide (SIRET 14 ou SIREN 9, clé Luhn)
   - les valeurs vides et `0` d'une colonne Pays sont conservées comme « pays non précisé ». Le filtre Pays reste actif même si la colonne n'est pas exportée.
5. Vérifier les chemins Parquet SIRENE, pré-remplis automatiquement (voir [Configuration](#configuration)).
6. Choisir le chemin de sortie Excel : par défaut le dossier Téléchargements avec le nom du fichier d'entrée et un horodatage, sinon saisie manuelle ou bouton **Browse...**.
7. Cliquer sur **Exécuter le contrôle SIRET/SIREN**, puis suivre la barre de progression et les métriques d'avancement/succès/échecs.

Le fichier Excel est écrit à l'emplacement choisi, et l'interface propose en plus un **bouton de téléchargement** une fois le contrôle terminé. Passer par ce bouton évite d'avoir à retrouver le fichier sur le disque.

### Sortie Excel

Cinq onglets sont produits :

- `siret_overview` : tableau principal, une ligne par identifiant analysé
- `statistiques` : synthèse (absents, invalides, fermés avec/sans remplaçant, radiés, actifs, `[ND]`)
- `anomalies` : identifiants manquants, non trouvés ou invalides, avec leur motif
- `siret_a_cloturer` : SIRET fermés sans remplaçant et SIRET radiés
- `dictionnaire_colonnes` : description métier des colonnes

Structure détaillée de `siret_overview` (catégories de colonnes, couleurs, valeurs de `analysis_data_applied`, statuts, lecture des statistiques) : [`docs/EXPORT_EXCEL.md`](docs/EXPORT_EXCEL.md).

### Mettre à jour l'application

À chaque lancement, l'application vérifie si une version plus récente existe. Le cas échéant, un message s'affiche dans la fenêtre de lancement puis en haut de la page :

```
[INFO] Nouvelle version disponible : 1.0.3 -> 1.0.4
```

Le bouton **« Mettre à jour maintenant »** applique la mise à jour. Les fichiers Parquet SIRENE et le dossier `export/` ne sont pas touchés : seuls les fichiers de l'application sont remplacés. Il faut ensuite **fermer l'application et relancer `run_app`** pour charger la nouvelle version, l'instance en cours d'exécution utilisant toujours l'ancien code. Si la nouvelle version a besoin de nouvelles bibliothèques Python, `run_app` les installe à ce redémarrage, ce qui rallonge le lancement de quelques dizaines de secondes.

Si la bannière ne s'affiche pas ou si le bouton échoue, c'est en général le réseau de l'entreprise qui bloque les connexions de l'application ; le site GitHub, lui, reste consultable depuis le navigateur du même poste. La mise à jour se fait alors en téléchargeant une archive ZIP depuis ce navigateur, puis en la déposant dans l'application : voir [Mise à jour hors ligne par ZIP GitHub](docs/DEPANNAGE.md#mise-à-jour-hors-ligne-par-zip-github).

> **Deux boutons voisins, à ne pas confondre :** « Mettre à jour maintenant » (bannière de version) met à jour **le code**, quelques centaines de Ko, et demande un redémarrage. « Mettre à jour les données SIRENE » télécharge **les fichiers Parquet**, plusieurs Go, sans redémarrage. Aucun des deux ne touche à ce que gère l'autre.

## Configuration

### Les 4 fichiers SIRENE attendus

Ils doivent se trouver **dans le dossier du projet**, à côté de `app.py`.

| Fichier | Poids | Statut | Contenu |
|---|---|---|---|
| `stocketablissement` | ≈ 2 Go | obligatoire | un enregistrement par établissement (SIRET) : adresse, statut administratif, code NAF, date de création, indicateur siège |
| `stockunitelegale` | ≈ 700 Mo | obligatoire | un enregistrement par unité légale (SIREN) : dénomination, catégorie juridique, statut administratif et de diffusion, activité principale |
| `stocketablissementlienssuccession` | ≈ 120 Mo | optionnel | liens de succession officiels (SIRET prédécesseur → successeur) |
| `stocketablissementhistorique` | ≈ 850 Mo | optionnel | états successifs d'un établissement (adresses et statuts antérieurs) |

Fichier Parquet unique ou dossier Parquet en plusieurs morceaux : les deux sont acceptés. Total ≈ 3,5 à 4 Go.

Effet de l'absence des fichiers optionnels :

- sans `stocketablissementlienssuccession`, le remplaçant d'un SIRET fermé ne peut plus venir du lien officiel. L'application applique une règle de repli moins fiable, un autre établissement actif du même SIREN. La note d'analyse n'indique plus « Succession » et le compteur « Fermés avec succession officielle » reste à 0.
- sans `stocketablissementhistorique`, aucune adresse ni statut antérieur n'est disponible. L'application ne peut pas confirmer un déménagement et se limite à l'état courant.

### Téléchargement automatique (recommandé)

Dès l'ouverture de la page, l'application interroge data.gouv.fr et compare la dernière publication aux fichiers locaux. L'encadré « Données SIRENE » affiche une ligne par fichier :

| Pastille | État | Signification |
|---|---|---|
| ✅ | à jour | le fichier local correspond à la dernière publication Insee |
| 🔄 | obsolète | une publication plus récente existe |
| ⬇️ | absent | aucun fichier local pour cette catégorie |
| ❔ | version inconnue | millésime indéterminable, fichier utilisable sans mise à jour obligatoire |

Le bouton **« Mettre à jour les données SIRENE »** affiche le volume total et télécharge uniquement les fichiers concernés, l'un après l'autre, avec barre de progression.

- Les fichiers sont écrits dans le dossier du projet sous les noms attendus, et les champs de chemin se remplissent seuls. Aucun déplacement manuel ensuite.
- **Un téléchargement qui échoue ne perd rien.** Connexion coupée, ordinateur mis en veille, application fermée en cours de transfert : le fichier déjà en place reste intact, le nouveau n'est mis à sa place qu'une fois entièrement téléchargé. Recliquer sur le bouton reprend l'opération.
- Si data.gouv.fr est injoignable, l'encadré le signale et les fichiers présents restent utilisables.
- Les fichiers installés à la main sont détectés et utilisables immédiatement, mais leur ancienneté est indéterminable : ils s'affichent en ❔. Voir [Un fichier s'affiche en version inconnue](docs/DEPANNAGE.md#un-fichier-saffiche-en-version-inconnue).

### Téléchargement manuel (repli)

Les champs de chemin restent utilisables et sont la seule option dans plusieurs cas : fichiers stockés ailleurs (autre dossier, disque réseau ou externe), Parquet fourni sous forme de dossier de plusieurs morceaux, poste sans accès internet, ou millésime précis à conserver.

Source : [base SIRENE sur data.gouv.fr](https://www.data.gouv.fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret). Noms exacts des ressources à prendre et pièges à éviter : [Télécharger les fichiers SIRENE à la main](docs/DEPANNAGE.md#télécharger-les-fichiers-sirene-à-la-main).

> ⚠️ **Déplacer ensuite les fichiers dans le dossier du projet** (celui de `app.py`). C'est ce qui permet leur détection automatique ; sinon les 4 chemins sont à saisir à la main à chaque utilisation.

## Structure du projet

```
app.py               point d'entrée de l'application
src/                 logique métier (accès données, pipeline, export, mise à jour)
scripts/             outils CLI (mise à jour, dépendances, changelog, export projet)
tests/               tests pytest (aucun accès réseau ni Parquet réel)
docs/                documentation détaillée
VERSION              version sémantique, source de vérité
requirements.txt     dépendances d'exécution
*.bat / *.command    lanceurs Windows / macOS-Linux
```

Détail fichier par fichier : [`docs/CODEMAP.md`](docs/CODEMAP.md). Conventions de code : [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md).

## Contribuer, signaler un problème, versions

### Signaler un bug ou demander une évolution

Deux canaux, selon ce que contient le signalement :

| Le signalement… | Où l'envoyer |
|---|---|
| ne contient que des informations techniques (message d'erreur, étapes, version) | **issue GitHub**, voir ci-dessous |
| touche à des données client, même indirectement : extrait de fichier, capture montrant des tiers, SIRET repris d'un fichier de travail | **e-mail au développeur**, sur son adresse professionnelle. Pas d'issue. |

En cas de doute, l'e-mail est le bon canal.

### Ouvrir une issue

Vérifier au préalable que le cas n'est pas déjà traité dans [Dépannage et FAQ](docs/DEPANNAGE.md) ni dans une issue existante, puis ouvrir une **New issue** sur [github.com/clav1stech/Annuaire/issues](https://github.com/clav1stech/Annuaire/issues).

Informations à joindre :

- la version de l'application, contenu du fichier `VERSION`, affichée aussi en haut de l'interface
- le système d'exploitation et la version de Python (voir [Vérifier et installer Python](docs/DEPANNAGE.md#vérifier-et-installer-python))
- les étapes suivies au moment du problème, et le résultat attendu
- le message d'erreur complet, recopié depuis la page ou depuis la fenêtre noire de lancement. Copier le texte plutôt qu'une photo d'écran ; une capture de l'interface est utile en complément.
- le millésime des fichiers SIRENE utilisés

> ⚠️ **Une issue GitHub est publique.** Un SIRET est une donnée publique en soi, mais sa présence dans un signalement révèle une relation commerciale : il n'a donc pas sa place dans une issue s'il vient d'un fichier de travail.
>
> Un problème de résultat se décrit sans exemple : le comportement observé, celui attendu, et le nombre de lignes concernées. Si le cas ne peut pas être compris sans les données, passer par l'e-mail.

### Contribuer au code

Flux de contribution, environnement de développement et règles à respecter : [`CONTRIBUTING.md`](CONTRIBUTING.md).

### Versions

Historique des versions : [`CHANGELOG.md`](CHANGELOG.md), mis à jour uniquement via `scripts/update_changelog.py`.

## Dépannage et FAQ

Les problèmes courants et leur solution sont regroupés dans un guide séparé : **[`docs/DEPANNAGE.md`](docs/DEPANNAGE.md)**. Le tableau ci-dessous renvoie directement à la bonne section.

| Situation | Section |
|---|---|
| Savoir si Python est déjà installé, ou l'installer | [Vérifier et installer Python](docs/DEPANNAGE.md#vérifier-et-installer-python) |
| Je dois lancer un script à la main pour lire une erreur | [Utiliser un terminal](docs/DEPANNAGE.md#utiliser-un-terminal) |
| À quoi servent les différents scripts | [Les scripts du projet](docs/DEPANNAGE.md#les-scripts-du-projet) |
| macOS refuse d'ouvrir un `.command` | [macOS : développeur non identifié](docs/DEPANNAGE.md#macos--développeur-non-identifié) |
| `zsh: permission denied` | [macOS : permission denied](docs/DEPANNAGE.md#macos--permission-denied) |
| Aucun message de version ne s'affiche jamais | [macOS : certificats de l'installeur python.org](docs/DEPANNAGE.md#macos--certificats-de-linstalleur-pythonorg) |
| La page reste blanche, erreurs 500 | [Page blanche et erreurs 500](docs/DEPANNAGE.md#page-blanche-et-erreurs-500) |
| Télécharger les fichiers SIRENE à la main | [Télécharger les fichiers SIRENE à la main](docs/DEPANNAGE.md#télécharger-les-fichiers-sirene-à-la-main) |
| Un fichier Parquet n'est pas détecté | [Fichier Parquet non détecté](docs/DEPANNAGE.md#fichier-parquet-non-détecté) |
| Un fichier s'affiche en ❔ version inconnue | [Un fichier s'affiche en version inconnue](docs/DEPANNAGE.md#un-fichier-saffiche-en-version-inconnue) |
| Le code NAF ne correspond pas à la nomenclature attendue | [Nomenclature NAF (rév. 2 / 2025)](docs/DEPANNAGE.md#nomenclature-naf-rév-2--2025) |
| La bannière de version ne s'affiche pas, ou le bouton de mise à jour échoue | [Mise à jour hors ligne par ZIP GitHub](docs/DEPANNAGE.md#mise-à-jour-hors-ligne-par-zip-github) |
| L'application ne démarre plus, mise à jour impossible | [Mise à jour en ligne de commande](docs/DEPANNAGE.md#mise-à-jour-en-ligne-de-commande) |
| « Accès refusé » pendant un téléchargement | [Dossier synchronisé (OneDrive & co)](docs/DEPANNAGE.md#dossier-synchronisé-onedrive--co) |
| Sauvegarder le projet ou le transmettre à une IA | [Export du projet](docs/DEPANNAGE.md#export-du-projet) |

## Ce que l'outil permet

L'application compare une liste d'identifiants avec la base SIRENE pour produire des statistiques globales de qualité et ramener les informations correspondantes (établissement et unité légale) à côté de chaque identifiant.

- Contrôler en masse une liste de SIRET/SIREN par rapport à un millésime SIRENE local : existence, statut (actif/fermé/radié/non trouvé/invalide), adresse, dénomination, code NAF, date de création, etc.
- Produire des statistiques globales de qualité de la base fournie (taux d'absents, d'invalides, de non-trouvés, de fermés avec ou sans remplaçant) pour prioriser un chantier de nettoyage.
- Ramener, pour chaque identifiant reconnu, les données SIRENE en face des données d'entrée, pour faciliter une revue manuelle ou semi-automatisée.
- Proposer un SIRET de remplacement pour les établissements fermés : de façon fiable quand le lien officiel de succession SIRENE l'identifie, sinon via une règle de repli plus approximative (un autre établissement actif du même SIREN, sans certitude que ce soit le véritable successeur).
- Repérer les identifiants en doublon, mal formés (clé Luhn, longueur) ou associés à un pays autre que la France.
- Produire un export Excel structuré, destiné à une exploitation manuelle par un analyste.

## Ce que l'outil ne permet pas

- **Retrouver un identifiant absent ou invalide.** Aucune recherche par nom d'entreprise, adresse ou critère flou : sans SIRET/SIREN exploitable en entrée, la ligne reste « Absent » ou « Invalide ».
- **Identifier le bon établissement à partir d'un SIREN seul.** L'application retombe systématiquement sur le **siège social**, qui peut ne pas être l'établissement concerné par la relation fournisseur. Sur une entreprise multi-établissements, cela peut renvoyer une adresse inattendue et créer de faux doublons SIRET.
- **Enrichir les fournisseurs étrangers.** SIRENE ne couvre que la France : un identifiant hors France peut être compté et conservé dans l'analyse si son format est valide, mais aucune donnée d'établissement n'est récupérée.
- **Garantir la présence des données pour les auto-entrepreneurs et personnes physiques.** Certaines unités légales sont « non diffusibles » (marqueur `[ND]`) dans les fichiers SIRENE eux-mêmes. L'application détecte ce cas (`analysis_nd_detecte`) mais ne peut pas afficher une information que la base ne diffuse pas.
- **Produire un fichier corrigé prêt à réimporter dans un ERP.** L'export Excel est un rapport d'analyse : ni mapping vers un schéma cible, ni validation de compatibilité, ni écriture dans un système tiers.
- **Comparer automatiquement les données SIRENE avec celles déjà présentes chez l'utilisateur.** L'application affiche les données SIRENE à côté des données d'entrée mais ne les confronte pas : elle ne signale pas qu'une adresse ou une raison sociale diffère de celle enregistrée côté client/ERP. **Ce travail de comparaison et d'arbitrage reste à la charge de l'utilisateur.**
- **Fournir une donnée plus fraîche que le millésime SIRENE utilisé.** Aucun appel en direct à une API Insee ou INPI : la fiabilité dépend uniquement de la date des fichiers Parquet fournis.
