# Annuaire_SIRENE

Application locale Streamlit pour contrôler une liste d'identifiants SIRET/SIREN à partir des fichiers SIRENE au format Parquet, enrichir les informations établissement/unité légale, détecter des cas potentiels de déménagement/transfert/remplacement, et exporter en Excel.

Aucune compétence en programmation n'est requise pour utiliser l'application : ce README détaille chaque étape, y compris l'installation de Python et l'usage d'un terminal si vous ne les avez jamais utilisés.

## Ce qu'il faut faire, et à quelle fréquence

Trois temps bien distincts :

| Fréquence | Action | Section |
|---|---|---|
| **Une seule fois** (à l'installation du poste) | Installer Python, télécharger le projet, exécuter le script d'installation | [Installation (une seule fois)](#installation-une-seule-fois) |
| **Environ une fois par mois** | Télécharger la nouvelle base SIRENE (fichiers Parquet) sur data.gouv.fr, pour disposer de données à jour | [Fichiers SIRENE attendus](#fichiers-sirene-attendus) |
| **À chaque utilisation** | Lancer l'application et faire tourner un contrôle | [Lancement (à chaque usage)](#lancement-à-chaque-usage) |

L'installation (étape 1) n'est donc à refaire que si vous changez de poste ou réinstallez le projet. La mise à jour des fichiers SIRENE (étape 2) n'a aucun rapport avec le code : c'est un simple téléchargement de fichiers, à faire régulièrement pour ne pas travailler sur des données obsolètes. Le lancement (étape 3) est la seule action répétée à chaque contrôle.

## Prérequis

- Windows 10/11 **ou** macOS (Linux fonctionne aussi via les scripts `.sh`)
- Python 3.11 à 3.14 (plage officiellement testée) — installer de préférence la dernière version disponible
- Fichiers SIRENE au format Parquet disponibles en local

### Utiliser un terminal (si vous n'en avez jamais ouvert)

Les scripts d'installation et de lancement peuvent s'utiliser en double-cliquant dessus, sans jamais ouvrir de terminal. Mais si un script affiche une erreur, il faut pouvoir l'exécuter "à la main" pour lire le message :

- **Windows** : touche `Windows`, taper `PowerShell` ou `Invite de commandes`, ouvrir l'application. Se déplacer dans le dossier du projet avec `cd` (exemple : `cd C:\Users\VotreNom\Downloads\Annuaire_SIRENE`), puis lancer le script en tapant son nom (ex. `create_venv.bat`) et Entrée.
- **macOS** : ouvrir **Terminal** (via Spotlight : `Cmd + Espace`, taper `Terminal`, Entrée). Se déplacer dans le dossier du projet avec `cd` (exemple : `cd ~/Downloads/Annuaire_SIRENE`) — astuce : taper `cd ` (avec l'espace) puis glisser-déposer le dossier depuis le Finder dans la fenêtre du Terminal complète automatiquement le chemin. Lancer ensuite le script avec `./create_venv.sh`.

Ces terminaux restent ouverts pendant que l'application tourne ; les fermer arrête l'application.

### Installer Python (si nécessaire)

Vérifier d'abord si Python est déjà installé, en ouvrant un terminal (voir ci-dessus) et en tapant :

```bash
python3 --version
```

(sous Windows, essayer `python --version` si `python3` n'est pas reconnu). Si une version entre 3.11 et 3.14 s'affiche, Python est prêt et l'étape suivante peut être ignorée. Si la commande est inconnue, ou si une version antérieure à 3.11 s'affiche :

- **Windows** : télécharger l'installeur sur [python.org/downloads](https://www.python.org/downloads/) (la dernière version proposée convient). **Important** : lors de l'installation, cocher la case **"Add python.exe to PATH"** avant de cliquer sur "Install Now" — sans cela, les scripts ne trouveront pas Python.
- **macOS** : télécharger l'installeur sur [python.org/downloads](https://www.python.org/downloads/) (méthode la plus simple si rien n'est encore installé). Alternative pour qui préfère Homebrew : Homebrew n'est pas installé par défaut sur macOS, il faut d'abord l'installer en suivant les instructions sur [brew.sh](https://brew.sh/), puis lancer `brew install python@3.14` (remplacer `3.14` par la version voulue si besoin).

Une fois l'installation terminée, fermer et rouvrir le terminal, puis revérifier avec `python3 --version` (ou `python --version`).

## Installation (une seule fois)

1. Télécharger le code du projet (zip) et le décompresser dans un dossier facile à retrouver (ex. Documents, Bureau).
2. Lancer le script d'installation adapté à votre système : double-clic dessus dans l'explorateur de fichiers, ou depuis un terminal ouvert dans le dossier du projet.

**Windows :**

```bat
create_venv.bat
```

**macOS / Linux :**

```bash
./create_venv.sh
```

Ces scripts font la même chose :
- affichent la version de Python détectée et avertissent si elle est hors de la plage testée (3.11-3.14), en demandant confirmation avant de continuer,
- créent `.venv_annuaire_sirene` si nécessaire,
- installent/upgradent `pip`,
- installent les dépendances depuis `requirements.txt`, en forçant `pyarrow` et `duckdb` à utiliser uniquement des wheels précompilées (`--only-binary`) pour éviter une compilation depuis les sources.

> macOS : si `python3` n'est pas installé, utiliser [python.org](https://www.python.org/downloads/) (voir [Installer Python](#installer-python-si-nécessaire) ci-dessus). Le bouton **Browse...** de sélection de fichier repose sur Tkinter (inclus avec les installeurs python.org ; avec Homebrew, si utilisé à la place : `brew install python-tk@3.14`, en adaptant le numéro de version si besoin). En son absence, le chemin de sortie reste saisissable manuellement.

Cette étape ne prend que quelques minutes et **n'est à refaire qu'une fois** (sauf changement de poste ou de dossier du projet). Le résultat est un dossier `.venv_annuaire_sirene` contenant tout ce dont l'application a besoin pour fonctionner ; il n'y a rien d'autre à installer par la suite.

## Lancement (à chaque usage)

**Windows :**

```bat
run_app.bat
```

**macOS / Linux :**

```bash
./run_app.sh
```

L’interface Streamlit s’ouvre dans le navigateur. Ce script est celui à utiliser à chaque fois que vous voulez faire tourner un contrôle SIRET/SIREN — contrairement au script d'installation, qui ne sert qu'une fois.

## Fichiers SIRENE attendus

> **Mise à jour mensuelle recommandée.** La base SIRENE est republiée par l'Insee chaque mois. Pour travailler sur des données à jour, retélécharger les fichiers ci-dessous (mêmes noms, écraser les anciens ou pointer l'application vers le nouveau dossier) environ une fois par mois. Cette opération est un simple téléchargement/remplacement de fichiers : elle ne touche pas au code et ne nécessite pas de relancer l'installation.

Téléchargement des fichiers Parquet SIRENE: https://www.data.gouv.fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret

- Obligatoires:
  - `stocketablissement` (fichier parquet ou dossier parquet) — un enregistrement par établissement (SIRET): adresse, statut administratif (actif/fermé), code activité (NAF), date de création, indicateur siège social. C'est la table de base pour le statut et l'adresse de chaque SIRET.
  - `stockunitelegale` (fichier parquet ou dossier parquet) — un enregistrement par unité légale (SIREN): dénomination/nom, catégorie juridique, statut administratif et statut de diffusion, activité principale. Sert à enrichir chaque SIRET avec l'identité de l'entreprise.
- Optionnels:
  - `stocketablissementlienssuccession` — table officielle des liens de succession SIRENE (SIRET prédécesseur → SIRET successeur lors d'un transfert/déménagement d'établissement).
  - `stocketablissementhistorique` — historique des états successifs d'un établissement (adresses et statuts précédents dans le temps).

Impact de l'absence des fichiers optionnels sur le résultat:
- Sans `stocketablissementlienssuccession`: pour les SIRET fermés, le remplaçant recommandé ne peut plus provenir du lien de succession officiel; l'application retombe sur une règle de repli moins fiable (un autre établissement actif du même SIREN, s'il existe). La note d'analyse ne peut jamais indiquer "Succession", et le compteur "Fermés avec succession officielle" reste à 0.
- Sans `stocketablissementhistorique`: aucune adresse ou statut antérieur n'est disponible pour un SIRET; l'application ne peut plus confirmer un historique de déménagement et se limite à l'état courant (photo unique) fourni par `stocketablissement`.

L’application détecte les colonnes disponibles de manière défensive selon le millésime et n’échoue pas si certaines colonnes attendues sont absentes.

### Détection automatique des fichiers (et que faire si elle échoue)

Au démarrage, l'application scanne **le dossier du projet** (celui où se trouve `app.py`) et essaie de reconnaître automatiquement les 4 fichiers ci-dessus, pour pré-remplir les champs de chemin. La reconnaissance se fait sur le **nom du fichier**, pas sur son contenu, et elle est volontairement tolérante :

- insensible à la casse et aux accents (`StockEtablissement`, `stock_etablissement`, `STOCKETABLISSEMENT` sont équivalents),
- insensible aux ajouts autour du mot-clé — millésime, date, suffixe `utf8`, tirets/underscores (ex. `StockEtablissement_utf8_2026-07.parquet` est bien reconnu comme `stocketablissement`),
- basée sur une simple recherche de mot-clé dans le nom (`etablissement`, `unitelegale`, `lienssuccession`/`succession`, `historique`), peu importe l'ordre ou le reste du nom.

Cette détection automatique ne porte que sur des **fichiers `.parquet` posés directement à la racine du dossier du projet** (pas dans un sous-dossier, pas de recherche récursive). Si vos fichiers SIRENE sont ailleurs (autre dossier, disque réseau, dossier Téléchargements...), ou fournis sous forme de **dossier** contenant plusieurs morceaux Parquet, l'application ne les détectera pas automatiquement — ce n'est pas une erreur, il suffit de renseigner le chemin manuellement dans le champ correspondant (fichier unique ou dossier, les deux sont acceptés une fois le chemin saisi à la main).

En cas de souci, l'application affiche un avertissement explicite en haut de l'interface plutôt que d'échouer silencieusement :
- *"Aucun fichier Parquet détecté pour '...' (obligatoire) à la racine du dossier"* : aucun fichier au nom reconnaissable n'a été trouvé à côté de `app.py` → renseigner le chemin à la main.
- Un avertissement si **plusieurs fichiers** correspondent au même mot-clé (ex. deux fichiers "etablissement" de millésimes différents) : l'application en choisit un par défaut (le premier par ordre alphabétique), mais mieux vaut vérifier/corriger le champ pour être sûr d'utiliser le bon millésime.
- Un avertissement pour tout fichier `.parquet` présent mais non reconnu (nom ne contenant aucun des mots-clés attendus) : il est simplement ignoré par la détection automatique, sans bloquer l'application — le champ peut toujours être renseigné manuellement avec son chemin exact.

Dans tous les cas, la détection automatique n'est qu'un confort de saisie : elle ne bloque jamais le lancement d'un contrôle, et le champ de chemin reste éditable/saisissable à la main à tout moment.

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

- La détection de remplacement/succession est fiable quand elle s'appuie sur le fichier officiel `stocketablissementlienssuccession` (donnée SIRENE officielle, pas une déduction de l'application). Elle est en revanche approximative en son absence, ou pour la détection de déménagement au sens large (basée sur l'historique d'adresses, sans lien officiel équivalent) — voir le détail plus haut dans "Fichiers SIRENE attendus".
- La qualité des résultats dépend de la complétude des colonnes présentes dans les millésimes fournis.
- L’application reste 100 % locale et ne dépend d’aucune base externe.

## Export du projet (sauvegarde + transmission à une IA)

Script disponible dans `scripts/export_project.py`.

Ce qu'il exporte :
- fichiers `.py`, `.bat`, `.sh`, `.md`, `.txt`,
- exclut les `.parquet`, environnements virtuels, caches, le dossier `export/` et `requirements.txt`.

Emplacement de sortie :
- `export/export_<projet>_<horodatage>_vX.Y.Z/`,
- contient les fichiers copiés, un `manifest.txt` et un fichier de contexte prêt pour l'IA (tout le code/contenu regroupé).

Lancement depuis la racine du projet :

```bash
python scripts/export_project.py
```

## Ce que permet / ne permet pas ce projet

Pour éviter tout malentendu sur la nature du résultat produit : l'application **compare une liste d'identifiants avec la base SIRENE** pour produire des statistiques globales de qualité et **ramener les informations correspondantes** (établissement + unité légale) à côté de chaque identifiant. Elle ne va pas plus loin que ça.

### Ce que ça permet

- Contrôler en masse une liste de SIRET/SIREN par rapport à un millésime SIRENE local : existence, statut (actif/fermé/radié/non trouvé/invalide), adresse, dénomination, code NAF, date de création, etc.
- Produire des statistiques globales de qualité de la base fournie (taux d'absents, d'invalides, de non-trouvés, de fermés avec/sans remplaçant...) pour prioriser un chantier de nettoyage.
- Ramener, pour chaque identifiant reconnu, les données SIRENE correspondantes en face des données d'entrée, pour faciliter une revue manuelle.
- Proposer un SIRET de remplacement pour les établissements fermés : de façon fiable lorsque le lien officiel de succession SIRENE (`stocketablissementlienssuccession`) l'identifie, ou sinon via une règle de repli plus approximative (un autre établissement actif du même SIREN, sans certitude que ce soit le véritable successeur).
- Repérer les identifiants en doublon, mal formés (échec de la clé de contrôle Luhn, mauvaise longueur), ou associés à un pays autre que la France.
- Produire un export Excel structuré, destiné à une lecture/exploitation manuelle par un analyste.

### Ce que ça ne permet pas

- **Retrouver un identifiant absent ou invalide.** L'application ne fait aucune recherche par nom d'entreprise, adresse ou autre critère flou (pas de rapprochement approximatif) : sans SIRET/SIREN exploitable en entrée, la ligne reste "Absent" ou "Invalide", point final.
- **Identifier le bon établissement à partir d'un SIREN seul.** Si seul le SIREN est fourni (pas de SIRET), l'application retombe systématiquement sur le **siège social** de l'entreprise — qui peut ne pas être l'établissement réellement concerné par la relation fournisseur. Sur une entreprise multi-établissements, cela peut renvoyer une adresse différente de celle attendue et créer de faux doublons SIRET.
- **Enrichir les fournisseurs étrangers.** La base SIRENE ne couvre que la France : un identifiant hors France peut être compté et éventuellement conservé dans l'analyse (si son format est valide), mais aucune donnée d'établissement n'est récupérée pour ces lignes.
- **Garantir la présence des données pour les auto-entrepreneurs/personnes physiques.** Certaines unités légales (notamment micro-entrepreneurs) sont "non diffusibles" (marqueur `[ND]`) dans les fichiers SIRENE eux-mêmes, pour des raisons de protection des données personnelles. L'application détecte ce cas (`analysis_nd_detecte`) mais ne peut pas afficher une information que la base ne diffuse pas.
- **Produire un fichier corrigé prêt à réimporter dans un ERP.** L'export Excel est un rapport d'analyse et de contrôle qualité, pas un fichier de correction au format d'import d'un ERP : il n'y a ni mapping vers un schéma cible, ni validation de compatibilité, ni écriture automatique dans un système tiers.
- **Comparer/croiser automatiquement les données SIRENE avec celles déjà présentes chez l'utilisateur.** L'application affiche les données SIRENE (nom, adresse...) à côté des données d'entrée, mais ne les confronte pas entre elles : elle ne signale pas qu'une adresse ou une raison sociale diffère de celle enregistrée côté client/ERP. **Ce travail de comparaison et d'arbitrage reste entièrement à la charge de l'utilisateur.**
- **Fournir une donnée plus fraîche que le millésime SIRENE utilisé.** Il n'y a aucun appel en direct à une API Insee/INPI : la fiabilité du résultat dépend uniquement de la date des fichiers Parquet fournis (voir la mise à jour mensuelle recommandée plus haut).

Options utiles :
- `--enable-zip-export true` pour générer aussi une archive `.zip` du dossier snapshot,
- `--include-extra-items true` pour archiver en plus les éléments lourds (environnements virtuels, etc.).
