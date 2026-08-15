# Annuaire_SIRENE

Application Streamlit locale qui contrôle une liste de SIRET/SIREN contre les fichiers SIRENE au format Parquet, enrichit chaque ligne (établissement + unité légale), détecte les cas de déménagement/transfert/remplacement et exporte le tout en Excel.

## Sommaire

- [Contexte](#contexte)
- [Démarrage rapide](#démarrage-rapide)
- [Utilisation](#utilisation)
- [Configuration](#configuration)
- [Structure du projet](#structure-du-projet)
- [Contribuer et versions](#contribuer-et-versions)
- [Dépannage et FAQ](#dépannage-et-faq)

## Contexte

Nettoyer une base tiers (fournisseurs, clients) suppose de savoir quels SIRET sont encore actifs, lesquels sont fermés, et par quoi les remplacer. L'Insee publie ces données chaque mois, mais sous forme de fichiers de plusieurs gigaoctets, inexploitables sous Excel.

L'application fait ce travail en local : elle croise votre liste d'identifiants avec les fichiers SIRENE Parquet posés sur le poste, et produit un rapport Excel exploitable par un analyste. Aucun appel à une API Insee ou INPI — la fraîcheur du résultat dépend du millésime des fichiers fournis. Aucune compétence en programmation n'est requise.

Le périmètre exact de l'outil — ce qu'il fait et ce qu'il ne fait pas — est détaillé dans [Dépannage et FAQ](#dépannage-et-faq).

## Démarrage rapide

**Prérequis** : Windows 10/11 ou macOS (Linux fonctionne aussi), et Python 3.11 à 3.14. Si Python n'est pas installé, prendre l'installeur sur [python.org/downloads](https://www.python.org/downloads/) — sous Windows, cocher **« Add python.exe to PATH »** avant de lancer l'installation.

1. **Décompresser le projet** dans un dossier local, **hors OneDrive / Dropbox / Google Drive** (ex. `C:\Annuaire_SIRENE` ou `~/Annuaire_SIRENE`). Les fichiers SIRENE pèsent plusieurs Go et un dossier synchronisé provoque saturation de quota et erreurs d'écriture — voir [Dossier synchronisé](#dossier-synchronisé-onedrive--co).
2. **Lancer l'application** : double-clic sur `run_app.bat` (Windows) ou `run_app.command` (macOS/Linux). C'est le seul script à connaître. Au premier lancement, il installe lui-même l'environnement Python — quelques minutes, une seule fois :

   ```
   [INFO] Premiere utilisation : installation de l'environnement en cours.
   [INFO] Cela peut prendre quelques minutes ; ne pas fermer cette fenetre.
   ```

3. **Récupérer les fichiers SIRENE** : dans l'interface qui s'ouvre, cliquer sur **« Mettre à jour les données SIRENE »** (encadré « Données SIRENE », en haut de page). Compter 3,5 à 4 Go au premier téléchargement. À refaire environ une fois par mois.
4. **Charger son fichier et exécuter le contrôle** (voir [Utilisation](#utilisation)).

Les étapes 1 et 2 ne se font qu'une fois ; l'étape 3 est mensuelle ; l'étape 4 est la seule répétée à chaque contrôle.

## Utilisation

### Exécuter un contrôle

1. Charger un fichier utilisateur (`.xlsx`, `.csv` ou `.parquet`) contenant des identifiants SIRET/SIREN.
2. Si le fichier est Excel, choisir la feuille ; indiquer s'il y a une ligne d'en-tête.
3. Cocher les colonnes d'entrée à reprendre dans le rapport final.
4. Sélectionner la colonne d'identifiants :
   - privilégier une colonne **SIRET** plutôt que SIREN : un SIREN identifie l'entreprise, pas l'établissement, et l'application retombe alors sur le siège social (risque de faux doublons) ;
   - une colonne mixte SIRET/SIREN est acceptée (utile si la source est partiellement renseignée) ;
   - option : inclure les lignes hors France si l'identifiant est valide (SIRET 14 ou SIREN 9, clé Luhn) ;
   - si une colonne Pays est utilisée, les valeurs vides et `0` sont conservées comme « pays non précisé ». Le filtre Pays reste actif même si la colonne n'est pas exportée.
5. Vérifier les chemins Parquet SIRENE (pré-remplis automatiquement, voir [Configuration](#configuration)).
6. Choisir le chemin de sortie Excel : par défaut le dossier Téléchargements avec le nom du fichier d'entrée + horodatage, sinon saisie manuelle ou bouton **Browse...**.
7. Cliquer sur **Exécuter le contrôle SIRET/SIREN**, puis suivre la barre de progression et les métriques d'avancement/succès/échecs.

Le fichier Excel est enregistré à l'emplacement choisi et reste téléchargeable depuis l'interface.

### Sortie Excel

Cinq onglets sont produits :

- `siret_overview` — tableau principal, une ligne par identifiant analysé ;
- `statistiques` — synthèse (absents, invalides, fermés avec/sans remplaçant, radiés, actifs, `[ND]`) ;
- `anomalies` — identifiants manquants, non trouvés ou invalides, avec leur motif ;
- `siret_a_cloturer` — SIRET fermés sans remplaçant et SIRET radiés ;
- `dictionnaire_colonnes` — description métier des colonnes.

Structure détaillée de `siret_overview` (catégories de colonnes, couleurs, valeurs de `analysis_data_applied`, statuts, lecture des statistiques) : [`docs/EXPORT_EXCEL.md`](docs/EXPORT_EXCEL.md).

### Mettre à jour l'application

À chaque lancement, l'application compare le fichier `VERSION` local à celui de la branche `main` sur GitHub. Si une version plus récente existe, un message s'affiche avant le lancement puis en haut de la page :

```
[INFO] Nouvelle version disponible : 1.0.3 -> 1.0.4
```

Un bouton **« Mettre à jour maintenant »** applique la mise à jour. Les fichiers Parquet SIRENE, le dossier `export/` et l'environnement virtuel ne sont jamais touchés. Comme l'application en cours d'exécution utilise encore l'ancien code, **la fermer et relancer `run_app`** pour charger la nouvelle version ; si les dépendances ont changé, elles sont réinstallées automatiquement au lancement suivant.

Sans connexion, ou si GitHub est injoignable, la vérification échoue silencieusement et n'empêche jamais le démarrage. Si la mise à jour ne peut pas être appliquée (modifications locales non commitées sur un projet cloné), la page l'indique et rien n'est modifié. Autres méthodes — ZIP hors ligne, ligne de commande — voir [Dépannage et FAQ](#dépannage-et-faq).

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

Sans les fichiers optionnels :

- **sans `stocketablissementlienssuccession`** : pour un SIRET fermé, le remplaçant ne peut plus venir du lien officiel ; l'application retombe sur une règle de repli moins fiable (un autre établissement actif du même SIREN). La note d'analyse n'indique jamais « Succession » et le compteur « Fermés avec succession officielle » reste à 0 ;
- **sans `stocketablissementhistorique`** : aucune adresse ni statut antérieur n'est disponible ; l'application ne peut pas confirmer un déménagement et se limite à l'état courant.

### Téléchargement automatique (recommandé)

Dès l'ouverture de la page, l'application interroge data.gouv.fr et compare la dernière publication aux fichiers locaux. L'encadré « Données SIRENE » affiche une ligne par fichier :

| Pastille | État | Signification |
|---|---|---|
| ✅ | à jour | le fichier local correspond à la dernière publication Insee |
| 🔄 | obsolète | une publication plus récente existe |
| ⬇️ | absent | aucun fichier local pour cette catégorie |
| ❔ | version inconnue | fichier installé manuellement, utilisable sans mise à jour obligatoire |

Le bouton **« Mettre à jour les données SIRENE »** affiche le volume total et télécharge uniquement les fichiers concernés, l'un après l'autre, avec barre de progression. À savoir :

- **aucun déplacement manuel ensuite** : les fichiers sont écrits dans le dossier du projet sous les noms attendus, et les champs de chemin se remplissent seuls ;
- **une interruption ne casse rien** : l'écriture passe par un fichier temporaire et ne remplace l'ancien qu'une fois le transfert terminé. Il suffit de recliquer sur le bouton ;
- **suivi de version** : la version téléchargée est mémorisée dans `.sirene_manifest.json` (local, non versionné, à côté de `app.py`). Le supprimer fait seulement réapparaître les fichiers en ❔ *version inconnue* ; ils restent utilisables ;
- **hors connexion, rien ne bloque** : si data.gouv.fr est injoignable, l'encadré le signale et les fichiers présents restent utilisables ;
- **fichiers installés à la main** : ils sont détectés et utilisables immédiatement, mais l'application ne peut pas deviner leur millésime et les affiche en ❔. Ce n'est ni une erreur ni une obligation de les remplacer.

### Téléchargement manuel (repli)

Les champs de chemin restent pleinement utilisables et sont la seule option dans plusieurs cas : fichiers stockés ailleurs (autre dossier, disque réseau ou externe), Parquet fourni sous forme de dossier de plusieurs morceaux, poste sans accès internet, ou millésime précis à conserver.

Source : [base SIRENE sur data.gouv.fr](https://www.data.gouv.fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret)

> ⚠️ **Prendre les fichiers « (format parquet) »**, pas les `.zip` proposés juste au-dessus. Chaque fichier existe en double sur data.gouv.fr : une version `.zip` contenant un CSV, et une version « (format parquet) » (icône grille) — seule cette seconde version est lisible par l'application.

> ⚠️ **Déplacer ensuite les fichiers dans le dossier du projet** (celui de `app.py`). C'est ce qui permet leur détection automatique ; sinon les 4 chemins sont à saisir à la main à chaque utilisation.

### Détection automatique des chemins

Au démarrage, l'application scanne le dossier du projet et reconnaît les fichiers d'après leur **nom** (pas leur contenu), de façon tolérante :

- insensible à la casse et aux accents (`StockEtablissement`, `stock_etablissement`, `STOCKETABLISSEMENT` sont équivalents) ;
- insensible aux ajouts autour du mot-clé — millésime, date, suffixe `utf8`, tirets et underscores (`StockEtablissement_utf8_2026-07.parquet` est reconnu) ;
- basée sur les mots-clés `etablissement`, `unitelegale`, `lienssuccession`/`succession`, `historique`, quel que soit l'ordre.

Le scan ne porte que sur les fichiers `.parquet` posés **directement à la racine** du dossier du projet (pas de recherche récursive). En cas d'échec, voir [Fichier Parquet non détecté](#fichier-parquet-non-détecté). La détection n'est qu'un confort de saisie : elle ne bloque jamais un contrôle, et les champs restent éditables à tout moment.

### Nomenclature NAF

L'Insee publie progressivement les colonnes NAF 2025 à côté des colonnes historiques (NAF rév. 2), avant bascule définitive prévue en janvier 2027. L'application accepte les deux : elle utilise la colonne historique tant qu'elle est présente, sinon la colonne NAF 2025. Le bloc « Diagnostic des schémas détectés », en bas de la page de résultats, indique la nomenclature retenue pour chaque table. Plus généralement, la détection des colonnes est défensive : une colonne attendue absente du millésime ne fait pas échouer l'analyse.

## Structure du projet

```
app.py               point d'entrée Streamlit
src/                 logique métier (accès données, pipeline, export, mise à jour)
scripts/             outils CLI (mise à jour, dépendances, changelog, export projet)
tests/               tests pytest (aucun accès réseau ni Parquet réel)
docs/                documentation détaillée
VERSION              version sémantique, source de vérité
requirements.txt     dépendances d'exécution
*.bat / *.command    lanceurs Windows / macOS-Linux
```

Détail fichier par fichier : [`docs/CODEMAP.md`](docs/CODEMAP.md). Conventions de code : [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md).

## Contribuer et versions

- Flux de contribution, environnement de développement et règles à respecter : [`CONTRIBUTING.md`](CONTRIBUTING.md).
- Historique des versions : [`CHANGELOG.md`](CHANGELOG.md) (mis à jour uniquement via `scripts/update_changelog.py`).

## Dépannage et FAQ

| Situation | Section |
|---|---|
| Je dois lancer un script à la main pour lire une erreur | [Utiliser un terminal](#utiliser-un-terminal) |
| Savoir si Python est déjà installé, ou l'installer | [Vérifier et installer Python](#vérifier-et-installer-python) |
| À quoi servent les différents scripts | [Les scripts du projet](#les-scripts-du-projet) |
| macOS refuse d'ouvrir un `.command` | [macOS : développeur non identifié](#macos--développeur-non-identifié) |
| `zsh: permission denied` | [macOS : permission denied](#macos--permission-denied) |
| Aucun message de version ne s'affiche jamais | [macOS : certificats de l'installeur python.org](#macos--certificats-de-linstalleur-pythonorg) |
| La page reste blanche, erreurs 500 dans le terminal | [Page blanche et erreurs 500](#page-blanche-et-erreurs-500) |
| Un fichier Parquet n'est pas détecté | [Fichier Parquet non détecté](#fichier-parquet-non-détecté) |
| GitHub est bloqué par le réseau d'entreprise | [Mise à jour hors ligne par ZIP GitHub](#mise-à-jour-hors-ligne-par-zip-github) |
| L'application ne démarre plus, mise à jour impossible | [Mise à jour en ligne de commande](#mise-à-jour-en-ligne-de-commande) |
| « Accès refusé » pendant un téléchargement | [Dossier synchronisé (OneDrive & co)](#dossier-synchronisé-onedrive--co) |
| Sauvegarder le projet ou le transmettre à une IA | [Export du projet](#export-du-projet) |
| Ce que l'outil sait faire — et ne sait pas faire | [Ce que l'outil permet](#ce-que-loutil-permet) |

### Utiliser un terminal

En usage normal, aucun terminal n'est à ouvrir : `run_app.bat` s'ouvre en double-clic sous Windows, et les scripts macOS sont au format `.command` (et non `.sh`) précisément pour qu'un double-clic dans le Finder les ouvre dans **Terminal.app**, sans configuration. Mais si un script affiche une erreur, il faut pouvoir l'exécuter à la main pour lire le message.

- **Windows** : touche `Windows`, taper `PowerShell` ou `Invite de commandes`, ouvrir l'application. Se placer dans le dossier du projet avec `cd` (ex. `cd C:\Users\VotreNom\Downloads\Annuaire_SIRENE`), puis taper le nom du script (`run_app.bat`) et Entrée.
- **macOS** : ouvrir **Terminal** (`Cmd + Espace`, taper `Terminal`). Se placer dans le dossier avec `cd` (ex. `cd ~/Downloads/Annuaire_SIRENE`) — astuce : taper `cd ` puis glisser-déposer le dossier depuis le Finder complète le chemin automatiquement. Lancer ensuite `./run_app.command`.

Ces fenêtres restent ouvertes pendant que l'application tourne ; les fermer arrête l'application.

> Si un éditeur de code (VSCode…) s'ouvre au lieu du Terminal, c'est probablement qu'une ancienne copie `run_app.sh` traîne dans le dossier — utiliser `run_app.command`.

### Vérifier et installer Python

Pour savoir si Python est déjà présent, ouvrir un terminal et taper :

```bash
python3 --version
```

Sous Windows, essayer `python --version` si `python3` n'est pas reconnu. Si une version entre 3.11 et 3.14 s'affiche, rien à faire. Si la commande est inconnue, ou si la version est antérieure à 3.11 :

- **Windows** : installeur depuis [python.org/downloads](https://www.python.org/downloads/) — cocher **« Add python.exe to PATH »** avant « Install Now », sans quoi les scripts ne trouveront pas Python.
- **macOS** : installeur [python.org/downloads](https://www.python.org/downloads/) (le plus simple). Alternative Homebrew, qui n'est pas installé par défaut sur macOS : suivre [brew.sh](https://brew.sh/) puis `brew install python@3.14` (adapter le numéro de version).

Une fois l'installation terminée, fermer et rouvrir le terminal avant de revérifier.

### Les scripts du projet

| Script | Windows | macOS / Linux | Rôle |
|---|---|---|---|
| Lancer l'application | `run_app.bat` | `./run_app.command` | **seul script nécessaire en usage normal** |
| Réinstaller l'environnement | `create_venv.bat` | `./create_venv.command` | dépannage, si l'installation automatique a échoué |
| Mettre à jour le code | `update_project.bat` | `./update_project.command` | alternative au bouton de l'interface |

Avant d'ouvrir l'application, `run_app` met tout en place : création de l'environnement `.venv_annuaire_sirene` s'il est absent, vérification de la version distante, et resynchronisation des dépendances si `requirements.txt` a changé depuis la dernière installation :

```
[INFO] requirements.txt a changé depuis la dernière installation des dépendances.
[INFO] Installation des dépendances depuis requirements.txt...
[SUCCESS] Environnement synchronisé avec requirements.txt.
```

Si cette réinstallation échoue (pas de connexion, wheel indisponible), le message d'erreur et la marche à suivre s'affichent mais l'application est lancée quand même.

**`create_venv`** fait exactement ce que `run_app` exécute au premier lancement, mais en affichant le détail — utile après un échec ou après suppression du dossier `.venv_annuaire_sirene`. Il affiche la version de Python détectée et demande confirmation si elle est hors de la plage testée (3.11-3.14), crée l'environnement, installe et met à jour `pip`, installe les dépendances de `requirements.txt` en forçant `pyarrow` et `duckdb` à n'utiliser que des wheels précompilées (`--only-binary`, pour éviter une compilation depuis les sources), puis enregistre une empreinte des dépendances installées — c'est elle qui permet à `run_app` de détecter plus tard un décalage avec `requirements.txt`.

Pour forcer la resynchronisation sans passer par `run_app` : `python scripts/sync_dependencies.py --force` depuis le dossier du projet, environnement virtuel activé.

### macOS : développeur non identifié

Au premier double-clic sur un `.command`, macOS affiche souvent *« 'run_app.command' Not Opened — Apple could not verify… »* : le fichier a été téléchargé depuis un navigateur (ZIP GitHub) et porte un attribut de quarantaine. Le Ctrl+clic → Ouvrir ne suffit plus depuis macOS Sequoia.

Solution fiable, à faire une seule fois après décompression, depuis le dossier du projet :

```bash
xattr -dr com.apple.quarantine .
```

**Si le blocage persiste** : double-cliquer une fois sur le script pour déclencher le blocage, puis aller dans **Réglages Système → Confidentialité et sécurité**, descendre jusqu'à Sécurité. Un message *« run_app.command a été bloqué »* propose **Ouvrir quand même** — confirmer avec le mot de passe ou Touch ID, puis **Ouvrir** dans le popup suivant. L'autorisation est ensuite mémorisée.

### macOS : permission denied

Si le terminal répond `zsh: permission denied: ./run_app.command`, le fichier a perdu son bit exécutable — cela arrive systématiquement en téléchargeant le ZIP GitHub, l'archive ne conservant pas les permissions Unix. `sudo` ne sert à rien ici. Depuis le dossier du projet :

```bash
chmod +x create_venv.command run_app.command update_project.command
```

En pratique, seul `run_app.command` a besoin de ce bit : c'est le seul à lancer, et il appelle les autres d'une façon qui n'en dépend pas.

### macOS : certificats de l'installeur python.org

Si l'application se lance mais n'affiche jamais de message de version (ni « à jour », ni « nouvelle version disponible ») : ouvrir le dossier « Python 3.x » dans Applications et double-cliquer sur **« Install Certificates.command »**, ou le lancer depuis un terminal en adaptant le numéro de version :

```bash
"/Applications/Python 3.14/Install Certificates.command"
```

Cette étape, propre à l'installeur python.org, installe les certificats SSL nécessaires aux vérifications réseau ; sans elle, elles échouent silencieusement. Inutile avec Homebrew ou sous Windows.

> Autre spécificité macOS : le bouton **Browse...** de sélection de fichier repose sur Tkinter, inclus avec les installeurs python.org. Avec Homebrew : `brew install python-tk@3.14`. En son absence, le chemin de sortie reste saisissable manuellement.

### Page blanche et erreurs 500

Symptôme : la page du navigateur ne se charge pas et le terminal répète `Exception in ASGI application` (par exemple `TypeError: GZipResponder.__init__() missing 1 required keyword-only argument: 'thread_minimum_size'`). L'environnement contient une version de dépendance incompatible avec celle attendue par Streamlit — situation possible sur un environnement installé avant la version 1.1.5.

Correctif : fermer l'application et relancer `run_app`, la réinstallation se déclenche d'elle-même. Si le problème persiste, relancer `create_venv`.

### Fichier Parquet non détecté

La détection automatique ne scanne que les fichiers `.parquet` posés à la racine du dossier du projet. Si les fichiers sont ailleurs (autre dossier, disque réseau, dossier Téléchargements) ou fournis sous forme de **dossier** de plusieurs morceaux, ils ne seront pas détectés — ce n'est pas une erreur : il suffit de saisir le chemin à la main dans le champ correspondant (fichier ou dossier, les deux sont acceptés).

Les avertissements affichés en haut de l'interface :

- *« Aucun fichier Parquet détecté pour '…' (obligatoire) à la racine du dossier »* — aucun nom reconnaissable trouvé à côté de `app.py` → renseigner le chemin à la main.
- **Plusieurs fichiers** correspondent au même mot-clé (ex. deux « etablissement » de millésimes différents) : l'application prend le premier par ordre alphabétique, mais mieux vaut vérifier le champ pour être sûr du millésime.
- Un fichier `.parquet` présent mais **non reconnu** (nom ne contenant aucun mot-clé attendu) est simplement ignoré, sans bloquer l'application.

### Mise à jour hors ligne par ZIP GitHub

Si le réseau d'entreprise bloque GitHub depuis le poste qui exécute l'application, l'encadré **« Mise à jour hors ligne depuis un ZIP GitHub »** reste disponible en haut de l'interface, même quand la vérification automatique de version échoue :

1. depuis un poste ayant accès à GitHub, ouvrir la branche `main` du projet et choisir **Code → Download ZIP** ;
2. transférer ce `.zip` sur le poste de l'application ;
3. glisser-déposer le ZIP dans l'encadré, puis cliquer sur **« Appliquer la mise à jour hors ligne »**.

Avant toute copie, l'application vérifie que l'archive correspond bien au projet Annuaire, que son fichier `VERSION` est valide et plus récent que la version installée, et qu'aucun chemin ne peut sortir du dossier du projet. Elle applique les mêmes exclusions que la mise à jour automatique : Parquet SIRENE, `.git`, environnement virtuel, caches et `export/` sont préservés. Seuls les fichiers de code dont le contenu diffère sont remplacés ; les fichiers locaux absents de l'archive ne sont pas supprimés.

Après le succès, fermer l'application et relancer `run_app`. Le ZIP est seulement lu : il n'est pas conservé dans le projet.

### Mise à jour en ligne de commande

Alternative à l'interface, notamment si l'application ne démarre plus : lancer `update_project.bat` (Windows) ou `./update_project.command` (macOS/Linux). Le script compare la version locale à celle de GitHub (`main`), demande confirmation, puis applique les fichiers à jour. Il **ne touche jamais** à l'environnement virtuel, aux fichiers Parquet SIRENE ni au dossier `export/`.

Deux modes, choisis automatiquement selon la façon dont le projet a été obtenu :

- **projet téléchargé en ZIP** (cas standard) : téléchargement de l'archive de `main` et copie des fichiers mis à jour par-dessus le dossier. Ce mode ne supprime pas les anciens fichiers devenus obsolètes ; en cas de gros doute, un nouveau téléchargement ZIP complet reste la méthode la plus sûre ;
- **projet cloné avec `git`** (usage avancé) : `git fetch` puis `git pull --ff-only`. En présence de modifications locales non commitées, la mise à jour est annulée par sécurité plutôt que de risquer de les écraser.

Si `requirements.txt` a changé, le script le signale : rien de plus à faire, `run_app` réinstalle les paquets au lancement suivant.

### Dossier synchronisé (OneDrive & co)

Les fichiers SIRENE pèsent plusieurs Go. Dans un dossier synchronisé, ils sont réenvoyés dans le cloud à chaque mise à jour mensuelle (quota et bande passante saturés), la synchronisation peut bloquer momentanément l'écriture (message *« Accès refusé »* en fin de téléchargement), et l'option « fichiers à la demande » peut vider un Parquet du disque et faire échouer une analyse.

Attention : dans beaucoup d'entreprises, **Bureau et Documents sont automatiquement redirigés vers OneDrive** — vérifier le chemin affiché dans la barre d'adresse. Un dossier comme `C:\Annuaire_SIRENE` ou `~/Annuaire_SIRENE` évite tous ces cas.

Si aucun emplacement non synchronisé n'est disponible, l'application reste utilisable : une synchronisation cloud ou un antivirus peut garder un fichier ouvert au moment du remplacement, mais l'application réessaie automatiquement et, si le verrou persiste, le signale clairement sans perdre le fichier téléchargé. En cas de blocage persistant, mettre la synchronisation en pause le temps du téléchargement (clic sur l'icône OneDrive → *Suspendre la synchronisation*).

### Export du projet

`scripts/export_project.py` produit une copie du projet destinée à la sauvegarde ou à la transmission à une IA. Il exporte les fichiers `.py`, `.bat`, `.sh`, `.md`, `.txt` et exclut les `.parquet`, les environnements virtuels, les caches, le dossier `export/` et `requirements.txt`.

```bash
python scripts/export_project.py
```

La sortie va dans `export/export_<projet>_<horodatage>_vX.Y.Z/` et contient les fichiers copiés, un `manifest.txt` et un fichier de contexte regroupant tout le code. Options utiles : `--enable-zip-export true` pour générer aussi une archive `.zip`, `--include-extra-items true` pour archiver en plus les éléments lourds.

### Ce que l'outil permet

L'application **compare une liste d'identifiants avec la base SIRENE** pour produire des statistiques globales de qualité et **ramener les informations correspondantes** (établissement + unité légale) à côté de chaque identifiant. Elle ne va pas plus loin.

- Contrôler en masse une liste de SIRET/SIREN par rapport à un millésime SIRENE local : existence, statut (actif/fermé/radié/non trouvé/invalide), adresse, dénomination, code NAF, date de création, etc.
- Produire des statistiques globales de qualité de la base fournie (taux d'absents, d'invalides, de non-trouvés, de fermés avec ou sans remplaçant) pour prioriser un chantier de nettoyage.
- Ramener, pour chaque identifiant reconnu, les données SIRENE en face des données d'entrée, pour faciliter une revue manuelle ou semi-automatisée.
- Proposer un SIRET de remplacement pour les établissements fermés : de façon fiable quand le lien officiel de succession SIRENE l'identifie, sinon via une règle de repli plus approximative (un autre établissement actif du même SIREN, sans certitude que ce soit le véritable successeur).
- Repérer les identifiants en doublon, mal formés (clé Luhn, longueur) ou associés à un pays autre que la France.
- Produire un export Excel structuré, destiné à une exploitation manuelle par un analyste.

### Ce que l'outil ne permet pas

- **Retrouver un identifiant absent ou invalide.** Aucune recherche par nom d'entreprise, adresse ou critère flou : sans SIRET/SIREN exploitable en entrée, la ligne reste « Absent » ou « Invalide ».
- **Identifier le bon établissement à partir d'un SIREN seul.** L'application retombe systématiquement sur le **siège social**, qui peut ne pas être l'établissement concerné par la relation fournisseur. Sur une entreprise multi-établissements, cela peut renvoyer une adresse inattendue et créer de faux doublons SIRET.
- **Enrichir les fournisseurs étrangers.** SIRENE ne couvre que la France : un identifiant hors France peut être compté et conservé dans l'analyse si son format est valide, mais aucune donnée d'établissement n'est récupérée.
- **Garantir la présence des données pour les auto-entrepreneurs et personnes physiques.** Certaines unités légales sont « non diffusibles » (marqueur `[ND]`) dans les fichiers SIRENE eux-mêmes. L'application détecte ce cas (`analysis_nd_detecte`) mais ne peut pas afficher une information que la base ne diffuse pas.
- **Produire un fichier corrigé prêt à réimporter dans un ERP.** L'export Excel est un rapport d'analyse : ni mapping vers un schéma cible, ni validation de compatibilité, ni écriture dans un système tiers.
- **Comparer automatiquement les données SIRENE avec celles déjà présentes chez l'utilisateur.** L'application affiche les données SIRENE à côté des données d'entrée mais ne les confronte pas : elle ne signale pas qu'une adresse ou une raison sociale diffère de celle enregistrée côté client/ERP. **Ce travail de comparaison et d'arbitrage reste à la charge de l'utilisateur.**
- **Fournir une donnée plus fraîche que le millésime SIRENE utilisé.** Aucun appel en direct à une API Insee ou INPI : la fiabilité dépend uniquement de la date des fichiers Parquet fournis.
