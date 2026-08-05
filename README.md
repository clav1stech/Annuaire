# Annuaire_SIRENE

Application locale Streamlit pour contrôler une liste d'identifiants SIRET/SIREN à partir des fichiers SIRENE au format Parquet, enrichir les informations établissement/unité légale, détecter des cas potentiels de déménagement/transfert/remplacement, et exporter en Excel.

Aucune compétence en programmation n'est requise pour utiliser l'application : ce README détaille chaque étape, y compris l'installation de Python et l'usage d'un terminal si vous ne les avez jamais utilisés.

## Sommaire / mode opératoire express

Toutes les étapes, dans l'ordre, avec leur fréquence et un lien direct vers la section détaillée :

| # | Étape | Fréquence | Section |
|---|---|---|---|
| 1 | Installer Python | Une fois | [Installer Python](#installer-python-si-nécessaire) |
| 2 | Télécharger le projet et le décompresser | Une fois | [Installation](#installation-une-seule-fois) |
| 3 | *(rien à faire : l'environnement est installé par `run_app` au premier lancement)* | Une fois | [Installation](#installation-une-seule-fois) |
| 4 | Télécharger les fichiers SIRENE (Parquet) — bouton **« Mettre à jour les données SIRENE »** en haut de l'interface | Mensuel | [Fichiers SIRENE attendus](#fichiers-sirene-attendus) |
| 5 | *(uniquement en téléchargement manuel)* **Placer ces fichiers Parquet dans le dossier du projet** | Mensuel | [Fichiers SIRENE attendus](#fichiers-sirene-attendus) |
| 6 | Lancer l'application (`run_app`) — installe l'environnement au premier lancement | À chaque usage | [Lancement](#lancement-à-chaque-usage) |
| 7 | Charger son fichier et exécuter le contrôle | À chaque usage | [Exemple d'usage](#exemple-dusage) |
| 8 | Mettre à jour le code si une nouvelle version est signalée (bouton, ZIP GitHub hors ligne, ou `update_project`) | Occasionnel | [Mettre à jour le code du projet](#mettre-à-jour-le-code-du-projet) |

En cas de blocage ou pour savoir ce que l'outil couvre exactement, voir aussi : [FAQ et limites du projet](#faq-et-limites-du-projet).

L'installation (étapes 1 à 3) se résume à décompresser le projet puis à lancer `run_app` une première fois, qui met en place l'environnement Python tout seul. La mise à jour des fichiers SIRENE (étapes 4 et 5) n'a aucun rapport avec le code : c'est un simple téléchargement/dépôt de fichiers, à refaire régulièrement pour ne pas travailler sur des données obsolètes. Le lancement (étapes 6 et 7) est la seule action répétée à chaque contrôle. La mise à jour du code (étape 8) n'est nécessaire que lorsque le projet évolue sur GitHub.

## Prérequis

- Windows 10/11 **ou** macOS (Linux fonctionne aussi via les scripts `.command`)
- Python 3.11 à 3.14 (plage officiellement testée) — installer de préférence la dernière version disponible
- Fichiers SIRENE au format Parquet disponibles en local, **déplacés dans le dossier du projet** (voir [Fichiers SIRENE attendus](#fichiers-sirene-attendus))

### Utiliser un terminal (pour dépannage ou utilisation avancée)

Les scripts du projet peuvent s'utiliser en double-cliquant dessus, sans jamais ouvrir de terminal manuellement — en usage normal, seul `run_app` est nécessaire :

- **Windows** : double-clic sur `run_app.bat` ouvre directement une invite de commandes.
- **macOS** : les scripts sont au format `.command` (et non `.sh`) précisément pour qu'un double-clic dans le Finder les ouvre directement dans **Terminal.app**, sans configuration ni "Ouvrir avec" à modifier.

Mais si un script affiche une erreur, il faut pouvoir l'exécuter "à la main" pour lire le message :

- **Windows** : touche `Windows`, taper `PowerShell` ou `Invite de commandes`, ouvrir l'application. Se déplacer dans le dossier du projet avec `cd` (exemple : `cd C:\Users\VotreNom\Downloads\Annuaire_SIRENE`), puis lancer le script en tapant son nom (ex. `run_app.bat`) et Entrée.
- **macOS** : ouvrir **Terminal** (via Spotlight : `Cmd + Espace`, taper `Terminal`, Entrée). Se déplacer dans le dossier du projet avec `cd` (exemple : `cd ~/Downloads/Annuaire_SIRENE`) — astuce : taper `cd ` (avec l'espace) puis glisser-déposer le dossier depuis le Finder dans la fenêtre du Terminal complète automatiquement le chemin. Lancer ensuite le script avec `./run_app.command`.

Ces terminaux restent ouverts pendant que l'application tourne ; les fermer arrête l'application.

### macOS : "impossible d'ouvrir" / "développeur non identifié"

Au premier double-clic sur un fichier `.command`, macOS affiche souvent un avertissement du type *"'run_app.command' Not Opened - Apple could not verify..."*, car le fichier a été téléchargé depuis un navigateur (zip GitHub) et porte un attribut de quarantaine. Le Ctrl+clic → Ouvrir ne suffit plus sur les versions récentes de macOS (Sequoia et ultérieures).

**Solution fiable, à faire une seule fois** après avoir décompressé le dossier du projet : ouvrir Terminal (voir ci-dessus) et taper (en remplaçant le chemin par le vôtre, ou en glissant-déposant le dossier après `cd ` puis en tapant la commande depuis ce dossier) :

```bash
xattr -dr com.apple.quarantine .
```

Cette commande retire l'attribut de quarantaine de tout le dossier du projet. Les scripts `.command` s'ouvrent ensuite normalement en double-clic, sans aucun autre avertissement.

**Si le blocage persiste malgré la commande ci-dessus** (une boîte de dialogue système apparaît toujours) : double-cliquer une fois sur le script pour déclencher le blocage, puis aller dans **Réglages Système → Confidentialité et sécurité**, descendre jusqu'à la section Sécurité. Un message *"run_app.command a été bloqué"* y propose un bouton **Ouvrir quand même** — cliquer dessus, confirmer avec le mot de passe/Touch ID, puis cliquer **Ouvrir** sur le nouveau popup. Cette autorisation est ensuite mémorisée.

### macOS : "permission denied" en lançant un `.command`

Si le terminal répond `zsh: permission denied: ./run_app.command`, c'est que le fichier a perdu son bit exécutable — cela arrive systématiquement en téléchargeant le zip GitHub (l'archive ne conserve pas les permissions Unix), et pouvait aussi arriver après une mise à jour en mode zip avant correction de ce comportement. `sudo` ne sert à rien ici (`cd` est une commande interne au shell, pas un problème de droits admin) : il faut redonner le bit exécutable, une seule fois, depuis Terminal dans le dossier du projet :

```bash
chmod +x create_venv.command run_app.command update_project.command
```

Les scripts peuvent ensuite être relancés normalement (`./run_app.command` ou double-clic). En pratique, seul `run_app.command` a besoin de ce bit exécutable : c'est le seul à lancer, et il appelle les autres d'une façon qui n'en dépend pas.

### Installer Python (si nécessaire)

Vérifier d'abord si Python est déjà installé, en ouvrant un terminal (voir ci-dessus) et en tapant :

```bash
python3 --version
```

(sous Windows, essayer `python --version` si `python3` n'est pas reconnu). Si une version entre 3.11 et 3.14 s'affiche, Python est prêt et l'étape suivante peut être ignorée. Si la commande est inconnue, ou si une version antérieure à 3.11 s'affiche :

- **Windows** : télécharger l'installeur sur [python.org/downloads](https://www.python.org/downloads/) (la dernière version proposée convient). **Important** : lors de l'installation, cocher la case **"Add python.exe to PATH"** avant de cliquer sur "Install Now" — sans cela, les scripts ne trouveront pas Python.
- **macOS** : télécharger l'installeur sur [python.org/downloads](https://www.python.org/downloads/) (méthode la plus simple si rien n'est encore installé). Alternative pour qui préfère Homebrew : Homebrew n'est pas installé par défaut sur macOS, il faut d'abord l'installer en suivant les instructions sur [brew.sh](https://brew.sh/), puis lancer `brew install python@3.14` (remplacer `3.14` par la version voulue si besoin).

> **macOS + installeur python.org uniquement** : si l'application se lance mais n'affiche jamais de message de version (ni "à jour", ni "nouvelle version disponible"), ouvrir Terminal, se rendre dans le dossier "Python 3.x" du Launchpad/Applications et double-cliquer sur **"Install Certificates.command"** (ou le lancer depuis Terminal : `"/Applications/Python 3.14/Install Certificates.command"`, en adaptant le numéro de version). Cette étape, propre à l'installeur python.org, installe les certificats SSL nécessaires aux vérifications réseau (dont la détection de nouvelle version) ; sans elle, ces vérifications échouent silencieusement. Non nécessaire avec Homebrew ni sous Windows.

Une fois l'installation terminée, fermer et rouvrir le terminal, puis revérifier avec `python3 --version` (ou `python --version`).

## Installation (une seule fois)

1. Télécharger le code du projet (zip) et le décompresser dans un dossier facile à retrouver (ex. Documents, Bureau).

> ⚠️ **Choisir un dossier local, hors OneDrive / Dropbox / Google Drive.** Les fichiers SIRENE pèsent plusieurs gigaoctets : dans un dossier synchronisé, ils sont réenvoyés dans le cloud à chaque mise à jour mensuelle (quota et bande passante saturés), la synchronisation peut bloquer momentanément l'écriture des fichiers (message *« Accès refusé »* en fin de téléchargement), et l'option « fichiers à la demande » peut vider un Parquet du disque et faire échouer une analyse. Un dossier comme `C:\Annuaire_SIRENE` (Windows) ou `~/Annuaire_SIRENE` (macOS) évite tous ces cas.
>
> Attention : dans beaucoup d'entreprises, **Bureau et Documents sont automatiquement redirigés vers OneDrive** — vérifier le chemin affiché dans la barre d'adresse (s'il contient « OneDrive », le dossier est synchronisé). Si aucun emplacement non synchronisé n'est disponible, l'application reste utilisable : elle réessaie automatiquement quand un fichier est verrouillé, et signale clairement l'échec au lieu de s'interrompre. En cas de blocage persistant, mettre la synchronisation en pause le temps du téléchargement (clic sur l'icône OneDrive → *Suspendre la synchronisation*).

2. Lancer `run_app` (voir [Lancement](#lancement-à-chaque-usage)) : **il n'y a pas de script d'installation séparé à lancer**. Au premier démarrage, `run_app` constate qu'aucun environnement n'existe et l'installe lui-même avant d'ouvrir l'application :

```
[INFO] Premiere utilisation : installation de l'environnement en cours.
[INFO] Cela peut prendre quelques minutes ; ne pas fermer cette fenetre.
```

Cette étape prend quelques minutes (téléchargement des bibliothèques Python) et ne se reproduit plus ensuite : les lancements suivants démarrent directement.

### Réinstaller ou réparer l'environnement (`create_venv`)

Le script `create_venv` reste disponible pour reconstruire l'environnement à la main, par exemple si l'installation automatique a échoué et que vous voulez relire le détail des messages, ou après avoir supprimé le dossier `.venv_annuaire_sirene` :

**Windows :**

```bat
create_venv.bat
```

**macOS / Linux :**

```bash
./create_venv.command
```

C'est exactement ce que `run_app` exécute au premier lancement :
- affichent la version de Python détectée et avertissent si elle est hors de la plage testée (3.11-3.14), en demandant confirmation avant de continuer,
- créent `.venv_annuaire_sirene` si nécessaire,
- installent/upgradent `pip`,
- installent les dépendances depuis `requirements.txt`, en forçant `pyarrow` et `duckdb` à utiliser uniquement des wheels précompilées (`--only-binary`) pour éviter une compilation depuis les sources,
- enregistrent dans l'environnement virtuel une empreinte des dépendances installées, qui permet à `run_app` de détecter plus tard un décalage avec `requirements.txt` et de le corriger tout seul (voir [Lancement](#lancement-à-chaque-usage)).

> macOS : si `python3` n'est pas installé, utiliser [python.org](https://www.python.org/downloads/) (voir [Installer Python](#installer-python-si-nécessaire) ci-dessus). Le bouton **Browse...** de sélection de fichier repose sur Tkinter (inclus avec les installeurs python.org ; avec Homebrew, si utilisé à la place : `brew install python-tk@3.14`, en adaptant le numéro de version si besoin). En son absence, le chemin de sortie reste saisissable manuellement.

Le résultat est un dossier `.venv_annuaire_sirene` contenant tout ce dont l'application a besoin pour fonctionner ; il n'y a rien d'autre à installer par la suite.

## Lancement (à chaque usage)

**Windows :**

```bat
run_app.bat
```

**macOS / Linux :**

```bash
./run_app.command
```

> Le script est au format `.command` : un double-clic dans le Finder l'ouvre directement dans Terminal.app. Si un éditeur de code (VSCode, etc.) s'ouvre à la place, c'est probablement qu'une copie `run_app.sh` traîne encore dans le dossier — utiliser `run_app.command`, ou lancer manuellement depuis un terminal (voir [Utiliser un terminal](#utiliser-un-terminal-pour-dépannage-ou-utilisation-avancée)).

L’interface Streamlit s’ouvre dans le navigateur. **C'est le seul script à connaître** : il est à utiliser à chaque fois que vous voulez faire tourner un contrôle SIRET/SIREN, y compris la toute première fois (voir [Installation](#installation-une-seule-fois)).

Avant d'ouvrir l'application, le script se charge de tout ce qui doit être en place :
- si l'environnement `.venv_annuaire_sirene` n'existe pas, il est créé et les bibliothèques installées (premier lancement, quelques minutes) ;
- si une nouvelle version du code existe sur GitHub, un message le signale (voir [Mettre à jour le code du projet](#mettre-à-jour-le-code-du-projet)) ;
- si les dépendances déclarées dans `requirements.txt` ne correspondent plus à celles installées (typiquement après une mise à jour du code), les paquets sont réinstallés automatiquement — quelques dizaines de secondes de plus au lancement, sans aucune manipulation :

```
[INFO] requirements.txt a changé depuis la dernière installation des dépendances.
[INFO] Installation des dépendances depuis requirements.txt...
[SUCCESS] Environnement synchronisé avec requirements.txt.
```

Si cette réinstallation échoue (pas de connexion, wheel indisponible), le message d'erreur et la marche à suivre s'affichent, mais l'application est lancée quand même : en cas de dysfonctionnement, il reste possible de repasser par `create_venv`.

### La page reste blanche et le terminal enchaîne des erreurs 500

Symptôme typique : la page du navigateur ne se charge pas et le terminal répète `Exception in ASGI application` (par exemple `TypeError: GZipResponder.__init__() missing 1 required keyword-only argument: 'thread_minimum_size'`). L'environnement contient une version de dépendance incompatible avec celle attendue par Streamlit — situation possible sur un environnement installé avant la version 1.1.5.

Correctif : fermer l'application, relancer `run_app` (la réinstallation décrite ci-dessus se déclenche d'elle-même). Si le problème persiste, relancer `create_venv`.

## Mettre à jour le code du projet

Le code du projet évolue sur GitHub (corrections, nouvelles fonctionnalités). Cette mise à jour concerne uniquement les fichiers du projet (`app.py`, `src/`, scripts...) — elle n'a aucun rapport avec les fichiers Parquet SIRENE, qui se mettent à jour séparément (voir [Fichiers SIRENE attendus](#fichiers-sirene-attendus)).

> **Deux boutons différents, à ne pas confondre** — ils sont voisins en haut de l'interface :
> - **« Mettre à jour maintenant »** (bannière de version) → met à jour **le code** de l'application, quelques centaines de kilo-octets, nécessite de relancer `run_app` ensuite.
> - **« Mettre à jour les données SIRENE »** (encadré « Données SIRENE ») → télécharge **les fichiers Parquet** de l'Insee, plusieurs giga-octets, sans relancer quoi que ce soit.
>
> Aucun des deux ne touche à ce que gère l'autre.

### 1. Détection automatique d'une nouvelle version

À chaque lancement via `run_app.command` / `run_app.bat`, l'application vérifie automatiquement (en quelques secondes, sans bloquer si hors ligne) si une version plus récente existe sur GitHub, en comparant le fichier `VERSION` local à celui de la branche `main` du dépôt. Si une nouvelle version est disponible, un message s'affiche dans le terminal juste avant le lancement de Streamlit, par exemple :

```
[INFO] Nouvelle version disponible : 1.0.3 -> 1.0.4
[HINT] Lancer 'python scripts/update_project.py' pour mettre à jour.
```

L'interface Streamlit affiche la même information en haut de page. Sans connexion internet, ou si GitHub est injoignable, la vérification échoue silencieusement (un simple avertissement) et n'empêche jamais l'application de démarrer.

### 2. Appliquer la mise à jour depuis l'interface (le plus simple)

Quand une nouvelle version est détectée, l'application affiche un bouton **« Mettre à jour maintenant »** sous le message d'alerte. Un clic applique la mise à jour, avec les mêmes garanties que le script en ligne de commande (voir ci-dessous) : rien n'est touché du côté des fichiers Parquet SIRENE, du dossier `export/` ni de l'environnement virtuel.

Le compte rendu s'affiche directement dans la page. Comme l'application en cours d'exécution utilise toujours l'ancien code, **il faut la fermer et relancer `run_app`** pour que la nouvelle version soit chargée. Si la mise à jour a changé les dépendances, `run_app` les réinstalle de lui-même au lancement suivant : il n'y a pas à repasser par `create_venv`.

Si la mise à jour ne peut pas être appliquée (par exemple des modifications locales non commitées sur un projet cloné avec `git`), la page l'indique avec la marche à suivre, et rien n'est modifié.

### 3. Appliquer une mise à jour hors ligne avec le ZIP GitHub

Si le réseau d'entreprise bloque GitHub depuis le poste qui exécute l'application, l'encadré **« Mise à jour hors ligne depuis un ZIP GitHub »** reste disponible en haut de l'interface, même lorsque la vérification automatique de version échoue :

1. depuis un poste ayant accès à GitHub, ouvrir la branche `main` du projet et choisir **Code → Download ZIP** ;
2. transférer ce fichier `.zip` sur le poste de l'application ;
3. glisser-déposer le ZIP dans l'encadré, puis cliquer sur **« Appliquer la mise à jour hors ligne »**.

Avant toute copie, l'application vérifie que l'archive correspond bien au projet Annuaire, que son fichier `VERSION` est valide et plus récent que la version installée, et qu'aucun chemin ne peut sortir du dossier du projet. Elle applique ensuite exactement les mêmes exclusions que la mise à jour automatique : les Parquet SIRENE, `.git`, l'environnement virtuel, les caches et `export/` sont préservés. Parmi les fichiers de code, seuls ceux dont le contenu diffère sont remplacés ; les fichiers locaux absents de l'archive ne sont pas supprimés.

Après le succès, fermer l'application et relancer `run_app`, comme pour une mise à jour en ligne. Le ZIP est seulement lu pendant l'opération : il n'est pas conservé dans le projet.

### 4. Appliquer la mise à jour en ligne de commande

Alternative à l'interface, notamment si l'application ne démarre plus. Lancer le script dédié, comme pour l'installation ou le lancement :

**Windows :**

```bat
update_project.bat
```

**macOS / Linux :**

```bash
./update_project.command
```

Ce script :
- compare à nouveau la version locale à celle de GitHub (`main`),
- si une nouvelle version existe, demande confirmation puis télécharge et applique automatiquement les fichiers à jour,
- **ne touche jamais** à l'environnement virtuel (`.venv_annuaire_sirene`), aux fichiers/dossiers Parquet SIRENE, ni au dossier `export/` — pas besoin de refaire l'installation ni de retélécharger les fichiers SIRENE après une mise à jour du code.

Deux modes de mise à jour, choisis automatiquement selon la façon dont le projet a été obtenu :
- **Projet téléchargé en zip** (cas standard, voir [Installation](#installation-une-seule-fois)) : le script télécharge l'archive de la branche `main` sur GitHub et copie les fichiers mis à jour par-dessus le dossier du projet. Ce mode ne supprime pas d'anciens fichiers devenus obsolètes ; en cas de gros doute, un nouveau téléchargement zip complet reste la méthode la plus sûre.
- **Projet cloné avec `git`** (utilisation avancée) : le script utilise `git fetch` puis `git pull --ff-only`. Si des modifications locales non commitées existent, la mise à jour est annulée par sécurité (message explicite) plutôt que de risquer de les écraser.

Si `requirements.txt` a changé dans la mise à jour (nouvelle dépendance ou version), le script l'indique en fin d'exécution : rien de plus à faire, `run_app` réinstalle les paquets concernés au lancement suivant. Pour forcer cette réinstallation sans passer par `run_app` (dépannage) : `python scripts/sync_dependencies.py --force` depuis le dossier du projet, environnement virtuel activé.

## Fichiers SIRENE attendus

> **Mise à jour mensuelle recommandée.** La base SIRENE est republiée par l'Insee chaque mois. Pour travailler sur des données à jour, récupérer les fichiers ci-dessous environ une fois par mois — le plus simple étant de laisser l'application le faire (voir juste en dessous). Cette opération est un simple téléchargement/remplacement de fichiers : elle ne touche pas au code et ne nécessite pas de relancer l'installation.

### Téléchargement automatique depuis l'application (recommandé)

Dès l'ouverture de la page, **avant même de charger un fichier à contrôler**, l'application interroge data.gouv.fr et compare la dernière publication aux fichiers présents sur votre poste. Le résultat s'affiche en haut de l'interface, sous forme d'un encadré « Données SIRENE » : une ligne par fichier, avec sa taille et son état.

| Pastille | État | Signification |
|---|---|---|
| ✅ | à jour | le fichier local correspond à la dernière publication Insee |
| 🔄 | obsolète | une publication plus récente existe |
| ⬇️ | absent | aucun fichier local pour cette catégorie |
| ❔ | version inconnue | fichier installé manuellement, utilisable sans mise à jour obligatoire |

Si au moins un fichier est à récupérer, un bouton **« Mettre à jour les données SIRENE »** affiche le volume total et lance le téléchargement des fichiers concernés, l'un après l'autre, avec barre de progression et compteur en Mo. Les fichiers déjà à jour sont ignorés — inutile donc de tout retélécharger chaque mois : en pratique, seuls les fichiers réellement republiés sont repris.

Points à connaître :

- **Aucun déplacement manuel ensuite.** Les fichiers sont écrits directement dans le dossier du projet, sous les noms attendus par la détection automatique, et les champs de chemin de l'étape 4 se remplissent tout seuls.
- **Une interruption ne casse rien.** L'écriture se fait dans un fichier temporaire et ne remplace l'ancien qu'une fois le transfert terminé : une coupure réseau ne laisse jamais un Parquet tronqué à la place d'un fichier valide. Il suffit de recliquer sur le bouton.
- **Prévoir le temps et la place.** Le premier téléchargement représente environ 3,5 à 4 Go pour les 4 fichiers, soit plusieurs minutes selon la connexion.
- **Comment l'application sait où elle en est.** La version téléchargée est mémorisée dans un fichier `.sirene_manifest.json` (local, non versionné, à côté de `app.py`). Le supprimer n'a d'autre effet que de faire réapparaître les fichiers comme « version inconnue » au lancement suivant ; ils restent utilisables sans téléchargement.
- **Hors connexion, rien ne bloque.** Si data.gouv.fr est injoignable, l'encadré l'indique simplement et les fichiers déjà présents restent parfaitement utilisables.
- **Dossier synchronisé (OneDrive & co).** Une synchronisation cloud ou un antivirus peut garder un fichier ouvert au moment où l'application le remplace, ce qui provoque un *« Accès refusé »*. L'application réessaie automatiquement, et si le verrou persiste elle l'annonce sans perdre le fichier téléchargé. Voir l'avertissement de l'[Installation](#installation-une-seule-fois) : le mieux reste d'installer le projet hors dossier synchronisé.

> **Fichiers installés à la main :** ils sont détectés et utilisables immédiatement, mais l'application ne peut pas deviner de quel millésime ils datent — elle les affiche donc en ❔ *version inconnue*, même s'ils sont tout frais. Ce n'est ni une erreur ni une obligation de les remplacer : l'utilisateur peut poursuivre directement avec ces fichiers. Seuls les fichiers réellement absents ou connus comme obsolètes sont proposés au téléchargement automatique.

### Téléchargement manuel (repli)

Le téléchargement automatique ne rend rien obsolète : **les champs de chemin de l'étape 4 restent pleinement utilisables**, et restent la seule option dans plusieurs cas courants — fichiers stockés ailleurs (autre dossier, disque réseau, disque externe), Parquet fourni sous forme de **dossier** de plusieurs morceaux, poste sans accès internet, ou millésime précis à conserver plutôt que la dernière publication.

Téléchargement des fichiers Parquet SIRENE: https://www.data.gouv.fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret

> ⚠️ **Attention au format téléchargé : bien prendre les fichiers "(format parquet)"**, et pas les fichiers `.zip` proposés juste au-dessus (qui contiennent des CSV). Sur la page data.gouv.fr, chaque fichier existe en double : une version standard (icône zip, ex. "Sirene : Fichier StockEtablissement - ... .zip") contenant un CSV, et une version "(format parquet)" (icône grille) — c'est **uniquement cette seconde version** qu'il faut télécharger, l'application ne lit pas les CSV.

> ⚠️ **Important : les fichiers Parquet téléchargés doivent être déplacés dans le dossier du projet** (celui où se trouve `app.py`), à côté des scripts `create_venv`/`run_app`. C'est ce qui permet leur détection automatique au lancement (voir [Détection automatique des fichiers](#détection-automatique-des-fichiers-et-que-faire-si-elle-échoue) ci-dessous). Sans ça, il faut renseigner les 4 chemins manuellement à chaque utilisation.

### Les 4 fichiers attendus

Quelle que soit la méthode de récupération (bouton de l'application ou téléchargement manuel), ce sont ces 4 fichiers qui sont utilisés :

- Obligatoires:
  - `stocketablissement` (fichier parquet ou dossier parquet, **≈ 2 Go**) — un enregistrement par établissement (SIRET): adresse, statut administratif (actif/fermé), code activité (NAF), date de création, indicateur siège social. C'est la table de base pour le statut et l'adresse de chaque SIRET.
  - `stockunitelegale` (fichier parquet ou dossier parquet, **≈ 700 Mo**) — un enregistrement par unité légale (SIREN): dénomination/nom, catégorie juridique, statut administratif et statut de diffusion, activité principale. Sert à enrichir chaque SIRET avec l'identité de l'entreprise.
- Optionnels:
  - `stocketablissementlienssuccession` (**≈ 120 Mo**) — table officielle des liens de succession SIRENE (SIRET prédécesseur → SIRET successeur lors d'un transfert/déménagement d'établissement).
  - `stocketablissementhistorique` (**≈ 850 Mo**) — historique des états successifs d'un établissement (adresses et statuts précédents dans le temps).

> Poids approximatifs constatés (millésime courant), à titre indicatif : le total avoisine **3,5 à 4 Go** pour les 4 fichiers Parquet. Prévoir une connexion stable et de la place disque en conséquence — un téléchargement interrompu ("network connection lost") doit être relancé.

Impact de l'absence des fichiers optionnels sur le résultat:
- Sans `stocketablissementlienssuccession`: pour les SIRET fermés, le remplaçant recommandé ne peut plus provenir du lien de succession officiel; l'application retombe sur une règle de repli moins fiable (un autre établissement actif du même SIREN, s'il existe). La note d'analyse ne peut jamais indiquer "Succession", et le compteur "Fermés avec succession officielle" reste à 0.
- Sans `stocketablissementhistorique`: aucune adresse ou statut antérieur n'est disponible pour un SIRET; l'application ne peut plus confirmer un historique de déménagement et se limite à l'état courant (photo unique) fourni par `stocketablissement`.

L’application détecte les colonnes disponibles de manière défensive selon le millésime et n’échoue pas si certaines colonnes attendues sont absentes.

**Nomenclature d'activité (NAF).** L'Insee publie progressivement les colonnes NAF 2025 à côté des colonnes historiques (NAF rév. 2), avant bascule définitive prévue en janvier 2027. L'application accepte les deux : elle utilise la colonne historique tant qu'elle est présente, sinon la colonne NAF 2025. Le bloc « Diagnostic des schémas détectés », en bas de la page de résultats, indique pour chaque table la nomenclature effectivement retenue — c'est là qu'il faut regarder pour savoir si un export référence l'ancienne ou la nouvelle classification.

### Détection automatique des fichiers (et que faire si elle échoue)

Au démarrage, l'application scanne **le dossier du projet** (celui où se trouve `app.py`) et essaie de reconnaître automatiquement les 4 fichiers ci-dessus, pour pré-remplir les champs de chemin. Les fichiers récupérés via le bouton **« Mettre à jour les données SIRENE »** y sont écrits sous les noms attendus : cette section ne concerne donc, en pratique, que les fichiers installés manuellement. La reconnaissance se fait sur le **nom du fichier**, pas sur son contenu, et elle est volontairement tolérante :

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

Remplaçant relevant d'une autre entreprise:
- `analysis_alerte_siren_different` indique `Oui` quand le remplaçant recommandé porte un SIREN différent de l'identifiant d'entrée, `Non` quand il porte le même, et reste vide s'il n'y a pas de remplaçant. Ce cas n'est **pas** une anomalie: dans la base SIRENE, 22 % des liens de succession pointent vers un établissement d'un autre SIREN (cession ou apport d'établissement à une autre entreprise). Il change en revanche d'entité juridique — donc de contrat, de RIB et de n° de TVA — et mérite une vérification manuelle avant reprise dans une base tiers. Les colonnes d'unité légale (dénomination, état, compteurs d'établissements) sont alors laissées vides plutôt que reprises de l'entreprise d'origine.
- Quand plusieurs liens de succession existent pour un même SIRET fermé (cas fréquent: 368 000 SIRET dans le stock SIRENE), l'application retient le lien à la **date de succession la plus récente**, puis celui portant une continuité économique, puis le plus petit SIRET successeur. Le choix est donc reproductible d'une exécution à l'autre.
- Détail complet de ces règles, chiffres à l'appui et limite connue: [`docs/SUCCESSION.md`](docs/SUCCESSION.md).

Valeurs de `analysis_data_applied`:
- `INPUT_SIRET_DATA` — les colonnes métier décrivent l'identifiant d'entrée.
- `REPLACEMENT_SIRET_DATA` — elles décrivent le remplaçant recommandé.
- `NO_DATA_REPLACEMENT_NOT_LOADED` — un remplaçant est recommandé, mais son établissement n'a pas été chargé dans le lot interrogé (le plus souvent parce qu'il relève d'un autre SIREN, hors du périmètre des SIREN d'entrée). C'est une **donnée absente du lot, pas un remplacement invalide**: le SIRET reste renseigné dans `siret_remplacement_recommande`, seules les colonnes métier sont vides.
- `NO_DATA_CLOSED_NO_REPLACEMENT` — SIRET fermé sans remplaçant identifié.

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

Options utiles :
- `--enable-zip-export true` pour générer aussi une archive `.zip` du dossier snapshot,
- `--include-extra-items true` pour archiver en plus les éléments lourds (environnements virtuels, etc.).

## FAQ et limites du projet

Sommaire rapide de cette dernière partie :

| Question | Section |
|---|---|
| Un fichier Parquet n'est pas détecté automatiquement | [Détection automatique des fichiers](#détection-automatique-des-fichiers-et-que-faire-si-elle-échoue) |
| Une nouvelle version du code est disponible sur GitHub, comment l'appliquer | [Mettre à jour le code du projet](#mettre-à-jour-le-code-du-projet) |
| La page reste blanche, le terminal affiche des erreurs 500 | [La page reste blanche et le terminal enchaîne des erreurs 500](#la-page-reste-blanche-et-le-terminal-enchaîne-des-erreurs-500) |
| L'installation automatique au premier lancement a échoué | [Réinstaller ou réparer l'environnement](#réinstaller-ou-réparer-lenvironnement-create_venv) |
| Le remplaçant proposé pour un SIRET fermé semble peu fiable | [Impact de l'absence des fichiers optionnels](#fichiers-sirene-attendus) |
| Je veux savoir ce que l'outil peut faire | [Ce que ça permet](#ce-que-ça-permet) |
| Je veux savoir ce que l'outil ne fait pas (avant de m'en servir) | [Ce que ça ne permet pas](#ce-que-ça-ne-permet-pas) |

Pour éviter tout malentendu sur la nature du résultat produit : l'application **compare une liste d'identifiants avec la base SIRENE** pour produire des statistiques globales de qualité et **ramener les informations correspondantes** (établissement + unité légale) à côté de chaque identifiant. Elle ne va pas plus loin que ça.

### Ce que ça permet

- Contrôler en masse une liste de SIRET/SIREN par rapport à un millésime SIRENE local : existence, statut (actif/fermé/radié/non trouvé/invalide), adresse, dénomination, code NAF, date de création, etc.
- Produire des statistiques globales de qualité de la base fournie (taux d'absents, d'invalides, de non-trouvés, de fermés avec/sans remplaçant...) pour prioriser un chantier de nettoyage.
- Ramener, pour chaque identifiant reconnu, les données SIRENE correspondantes en face des données d'entrée, pour faciliter une revue manuelle ou semi-automatisée (Excel).
- Proposer un SIRET de remplacement pour les établissements fermés : de façon fiable lorsque le lien officiel de succession SIRENE (`stocketablissementlienssuccession`) l'identifie, ou sinon via une règle de repli plus approximative (un autre établissement actif du même SIREN, sans certitude que ce soit le véritable successeur).
- Repérer les identifiants en doublon, mal formés (échec de la clé de contrôle Luhn, mauvaise longueur), ou associés à un pays autre que la France.
- Produire un export Excel structuré, destiné à une lecture/exploitation manuelle/excel par un analyste.

### Ce que ça ne permet pas

- **Retrouver un identifiant absent ou invalide.** L'application ne fait aucune recherche par nom d'entreprise, adresse ou autre critère flou (pas de rapprochement approximatif) : sans SIRET/SIREN exploitable en entrée, la ligne reste "Absent" ou "Invalide".
- **Identifier le bon établissement à partir d'un SIREN seul.** Si seul le SIREN est fourni (pas de SIRET), l'application retombe systématiquement sur le **siège social** de l'entreprise — qui peut ne pas être l'établissement réellement concerné par la relation fournisseur. Sur une entreprise multi-établissements, cela peut renvoyer une adresse différente de celle attendue et créer de faux doublons SIRET.
- **Enrichir les fournisseurs étrangers.** La base SIRENE ne couvre que la France : un identifiant hors France peut être compté et éventuellement conservé dans l'analyse (si son format est valide), mais aucune donnée d'établissement n'est récupérée pour ces lignes.
- **Garantir la présence des données pour les auto-entrepreneurs/personnes physiques.** Certaines unités légales (notamment micro-entrepreneurs) sont "non diffusibles" (marqueur `[ND]`) dans les fichiers SIRENE eux-mêmes, pour des raisons de protection des données personnelles. L'application détecte ce cas (`analysis_nd_detecte`) mais ne peut pas afficher une information que la base ne diffuse pas.
- **Produire un fichier corrigé prêt à réimporter dans un ERP.** L'export Excel est un rapport d'analyse et de contrôle qualité, pas un fichier de correction au format d'import d'un ERP : il n'y a ni mapping vers un schéma cible, ni validation de compatibilité, ni écriture automatique dans un système tiers.
- **Comparer/croiser automatiquement les données SIRENE avec celles déjà présentes chez l'utilisateur.** L'application affiche les données SIRENE (nom, adresse...) à côté des données d'entrée, mais ne les confronte pas entre elles : elle ne signale pas qu'une adresse ou une raison sociale diffère de celle enregistrée côté client/ERP. **Ce travail de comparaison et d'arbitrage reste entièrement à la charge de l'utilisateur.**
- **Fournir une donnée plus fraîche que le millésime SIRENE utilisé.** Il n'y a aucun appel en direct à une API Insee/INPI : la fiabilité du résultat dépend uniquement de la date des fichiers Parquet fournis (voir la mise à jour mensuelle recommandée plus haut).
