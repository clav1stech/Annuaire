# Dépannage et FAQ

Guide de dépannage d'Annuaire_SIRENE. Usage courant et installation : [README.md](../README.md).
Si le problème n'est pas traité ici, ouvrir une issue en joignant les informations listées dans [README.md § Signaler un bug](../README.md#signaler-un-bug-ou-demander-une-évolution).

## Sommaire

| Situation | Section |
|---|---|
| Savoir si Python est déjà installé, ou l'installer | [Vérifier et installer Python](#vérifier-et-installer-python) |
| Je dois lancer un script à la main pour lire une erreur | [Utiliser un terminal](#utiliser-un-terminal) |
| À quoi servent les différents scripts | [Les scripts du projet](#les-scripts-du-projet) |
| macOS refuse d'ouvrir un `.command` | [macOS : développeur non identifié](#macos--développeur-non-identifié) |
| `zsh: permission denied` | [macOS : permission denied](#macos--permission-denied) |
| Aucun message de version ne s'affiche jamais | [macOS : certificats de l'installeur python.org](#macos--certificats-de-linstalleur-pythonorg) |
| La page reste blanche, erreurs 500 | [Page blanche et erreurs 500](#page-blanche-et-erreurs-500) |
| Télécharger les fichiers SIRENE à la main | [Télécharger les fichiers SIRENE à la main](#télécharger-les-fichiers-sirene-à-la-main) |
| Un fichier Parquet n'est pas détecté | [Fichier Parquet non détecté](#fichier-parquet-non-détecté) |
| Un fichier s'affiche en ❔ version inconnue | [Un fichier s'affiche en version inconnue](#un-fichier-saffiche-en-version-inconnue) |
| Le code NAF ne correspond pas à la nomenclature attendue | [Nomenclature NAF (rév. 2 / 2025)](#nomenclature-naf-rév-2--2025) |
| Le poste n'a pas accès à GitHub | [Mise à jour hors ligne par ZIP GitHub](#mise-à-jour-hors-ligne-par-zip-github) |
| L'application ne démarre plus, mise à jour impossible | [Mise à jour en ligne de commande](#mise-à-jour-en-ligne-de-commande) |
| « Accès refusé » pendant un téléchargement | [Dossier synchronisé (OneDrive & co)](#dossier-synchronisé-onedrive--co) |
| Sauvegarder le projet ou le transmettre à une IA | [Export du projet](#export-du-projet) |

## Vérifier et installer Python

Pour savoir si Python est déjà présent, ouvrir un terminal (voir [Utiliser un terminal](#utiliser-un-terminal)) et taper :

```bash
python3 --version
```

Sous Windows, essayer `python --version` si `python3` n'est pas reconnu. Si une version entre 3.11 et 3.14 s'affiche, rien à faire. Si la commande est inconnue, ou si la version est antérieure à 3.11 :

- **Windows** : installeur depuis [python.org/downloads](https://www.python.org/downloads/) — cocher **« Add python.exe to PATH »** avant « Install Now », sans quoi les scripts ne trouveront pas Python.
- **macOS** : installeur [python.org/downloads](https://www.python.org/downloads/) (le plus simple). Alternative Homebrew, qui n'est pas installé par défaut sur macOS : suivre [brew.sh](https://brew.sh/) puis `brew install python@3.14` (adapter le numéro de version).

Une fois l'installation terminée, fermer et rouvrir le terminal avant de revérifier.

## Utiliser un terminal

En usage normal, aucun terminal n'est à ouvrir : `run_app.bat` s'ouvre en double-clic sous Windows, et les scripts macOS sont au format `.command` (et non `.sh`) précisément pour qu'un double-clic dans le Finder les ouvre dans **Terminal.app**, sans configuration. Mais si un script affiche une erreur, il faut pouvoir l'exécuter à la main pour lire le message.

- **Windows** : touche `Windows`, taper `PowerShell` ou `Invite de commandes`, ouvrir l'application. Se placer dans le dossier du projet avec `cd` (ex. `cd C:\Users\VotreNom\Downloads\Annuaire_SIRENE`), puis taper le nom du script (`run_app.bat`) et Entrée.
- **macOS** : ouvrir **Terminal** (`Cmd + Espace`, taper `Terminal`). Se placer dans le dossier avec `cd` (ex. `cd ~/Downloads/Annuaire_SIRENE`) — astuce : taper `cd ` puis glisser-déposer le dossier depuis le Finder complète le chemin automatiquement. Lancer ensuite `./run_app.command`.

Ces fenêtres restent ouvertes pendant que l'application tourne, et **les fermer arrête l'application** — c'est aussi la façon normale de la quitter une fois le travail terminé.

> Si un éditeur de code (VSCode…) s'ouvre au lieu du Terminal, c'est probablement qu'une ancienne copie `run_app.sh` traîne dans le dossier — utiliser `run_app.command`.

## Les scripts du projet

| Script | Windows | macOS / Linux | Rôle |
|---|---|---|---|
| Lancer l'application | `run_app.bat` | `./run_app.command` | **seul script nécessaire en usage normal** |
| Réinstaller l'environnement | `create_venv.bat` | `./create_venv.command` | dépannage, si l'installation automatique a échoué |
| Mettre à jour le code | `update_project.bat` | `./update_project.command` | alternative au bouton de l'interface |

Avant d'ouvrir l'application, `run_app` met tout en place : création de l'environnement `.venv_annuaire_sirene` s'il est absent, vérification de la version distante, et réinstallation des bibliothèques Python si la liste `requirements.txt` a changé depuis la dernière installation :

```
[INFO] requirements.txt a changé depuis la dernière installation des dépendances.
[INFO] Installation des dépendances depuis requirements.txt...
[SUCCESS] Environnement synchronisé avec requirements.txt.
```

Si cette réinstallation échoue — le plus souvent parce que le poste n'a pas accès à internet, ou parce qu'une bibliothèque n'est pas disponible pour cette version de Python — le message d'erreur et la marche à suivre s'affichent, mais l'application est lancée quand même. En cas de dysfonctionnement, relancer `create_venv`.

**`create_venv`** fait exactement ce que `run_app` exécute au premier lancement, mais en affichant le détail — utile après un échec ou après suppression du dossier `.venv_annuaire_sirene`. Il affiche la version de Python détectée et demande confirmation si elle est hors de la plage testée (3.11-3.14), crée l'environnement, installe et met à jour `pip`, installe les dépendances de `requirements.txt` en forçant `pyarrow` et `duckdb` à n'utiliser que des versions précompilées (`--only-binary`, pour éviter une compilation depuis les sources), puis enregistre une empreinte des dépendances installées — c'est elle qui permet à `run_app` de détecter plus tard un décalage avec `requirements.txt`.

Pour forcer la resynchronisation sans passer par `run_app` : `python scripts/sync_dependencies.py --force` depuis le dossier du projet, environnement virtuel activé.

## macOS : développeur non identifié

Au premier double-clic sur un `.command`, macOS affiche souvent *« 'run_app.command' Not Opened — Apple could not verify… »* : le fichier a été téléchargé depuis un navigateur (ZIP GitHub) et porte un attribut de quarantaine. Le Ctrl+clic → Ouvrir ne suffit plus depuis macOS Sequoia.

Solution fiable, à faire une seule fois après décompression, depuis le dossier du projet :

```bash
xattr -dr com.apple.quarantine .
```

**Si le blocage persiste** : double-cliquer une fois sur le script pour déclencher le blocage, puis aller dans **Réglages Système → Confidentialité et sécurité**, descendre jusqu'à Sécurité. Un message *« run_app.command a été bloqué »* propose **Ouvrir quand même** — confirmer avec le mot de passe ou Touch ID, puis **Ouvrir** dans le popup suivant. L'autorisation est ensuite mémorisée.

## macOS : permission denied

Si le terminal répond `zsh: permission denied: ./run_app.command`, le fichier a perdu son bit exécutable — cela arrive systématiquement en téléchargeant le ZIP GitHub, l'archive ne conservant pas les permissions Unix. `sudo` ne sert à rien ici. Depuis le dossier du projet :

```bash
chmod +x create_venv.command run_app.command update_project.command
```

En pratique, seul `run_app.command` a besoin de ce bit : c'est le seul à lancer, et il appelle les autres d'une façon qui n'en dépend pas.

## macOS : certificats de l'installeur python.org

Si l'application se lance mais n'affiche jamais de message de version (ni « à jour », ni « nouvelle version disponible ») : ouvrir le dossier « Python 3.x » dans Applications et double-cliquer sur **« Install Certificates.command »**, ou le lancer depuis un terminal en adaptant le numéro de version :

```bash
"/Applications/Python 3.14/Install Certificates.command"
```

Cette étape, propre à l'installeur python.org, installe les certificats SSL nécessaires aux vérifications réseau ; sans elle, elles échouent silencieusement. Inutile avec Homebrew ou sous Windows.

> Autre spécificité macOS : le bouton **Browse...** de sélection de fichier repose sur Tkinter, inclus avec les installeurs python.org. Avec Homebrew : `brew install python-tk@3.14`. En son absence, le chemin de sortie reste saisissable manuellement.

## Page blanche et erreurs 500

Symptôme : la page du navigateur ne se charge pas et la fenêtre de lancement répète `Exception in ASGI application` (par exemple `TypeError: GZipResponder.__init__() missing 1 required keyword-only argument: 'thread_minimum_size'`). L'environnement contient une version de bibliothèque incompatible avec celle attendue par Streamlit — situation possible sur un environnement installé avant la version 1.1.5.

Correctif : fermer l'application et relancer `run_app`, la réinstallation se déclenche d'elle-même. Si le problème persiste, relancer `create_venv`.

## Télécharger les fichiers SIRENE à la main

Utile quand le bouton **« Mettre à jour les données SIRENE »** ne convient pas : poste sans accès à data.gouv.fr, millésime précis à conserver, ou fichiers à stocker ailleurs que dans le dossier du projet.

Page source : [base SIRENE sur data.gouv.fr](https://www.data.gouv.fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret)

Les 4 ressources à récupérer, telles qu'elles apparaissent dans la liste des fichiers :

| Ressource sur data.gouv.fr | Nom du fichier téléchargé | Statut |
|---|---|---|
| Sirene : Fichier StockEtablissement **(format parquet)** | `StockEtablissement_utf8.parquet` | obligatoire |
| Sirene : Fichier StockUniteLegale **(format parquet)** | `StockUniteLegale_utf8.parquet` | obligatoire |
| Sirene : Fichier StockEtablissementLiensSuccession **(format parquet)** | `StockEtablissementLiensSuccession_utf8.parquet` | optionnel |
| Sirene : Fichier StockEtablissementHistorique **(format parquet)** | `StockEtablissementHistorique_utf8.parquet` | optionnel |

> ⚠️ **Bien prendre la mention « (format parquet) »**, pas les `.zip` proposés juste au-dessus. Chaque fichier existe en double sur la page : une version `.zip` (icône zip) qui contient un CSV, et une version « (format parquet) » (icône grille). L'application **ne lit pas les CSV** — seule la seconde version fonctionne.

Déplacer ensuite les fichiers **dans le dossier du projet**, à côté de `app.py` : c'est ce qui permet leur détection automatique. S'ils restent ailleurs, les 4 chemins sont à saisir à la main à chaque utilisation (fichier unique ou dossier Parquet, les deux sont acceptés).

Le total avoisine 3,5 à 4 Go : prévoir une connexion stable et la place disque correspondante. Un téléchargement interrompu (« network connection lost ») doit être relancé.

## Fichier Parquet non détecté

Au démarrage, l'application scanne le dossier du projet et reconnaît les fichiers d'après leur **nom** (pas leur contenu), de façon volontairement tolérante :

- insensible à la casse et aux accents (`StockEtablissement`, `stock_etablissement`, `STOCKETABLISSEMENT` sont équivalents) ;
- insensible aux ajouts autour du mot-clé — millésime, date, suffixe `utf8`, tirets et underscores (`StockEtablissement_utf8_2026-07.parquet` est reconnu) ;
- basée sur les mots-clés `etablissement`, `unitelegale`, `lienssuccession`/`succession`, `historique`, quel que soit l'ordre.

Le scan ne porte que sur les fichiers `.parquet` posés **directement à la racine** du dossier du projet, sans recherche dans les sous-dossiers. Si les fichiers sont ailleurs (autre dossier, disque réseau, dossier Téléchargements) ou fournis sous forme de **dossier** de plusieurs morceaux, ils ne seront pas détectés — ce n'est pas une erreur : il suffit de saisir le chemin à la main dans le champ correspondant.

Les avertissements affichés en haut de l'interface :

- *« Aucun fichier Parquet détecté pour '…' (obligatoire) à la racine du dossier »* — aucun nom reconnaissable trouvé à côté de `app.py` → renseigner le chemin à la main.
- **Plusieurs fichiers** correspondent au même mot-clé (ex. deux « etablissement » de millésimes différents) : l'application prend le premier par ordre alphabétique, mais mieux vaut vérifier le champ pour être sûr du millésime.
- Un fichier `.parquet` présent mais **non reconnu** (nom ne contenant aucun mot-clé attendu) est simplement ignoré, sans bloquer l'application.

La détection n'est qu'un confort de saisie : elle ne bloque jamais un contrôle, et les champs restent éditables à tout moment.

## Un fichier s'affiche en version inconnue

La pastille ❔ signifie seulement que l'application ne sait pas de quel millésime date le fichier — pas qu'il est abîmé ou périmé. Il reste pleinement utilisable, et aucune mise à jour n'est imposée.

Causes possibles :

- le fichier a été **installé à la main** (téléchargement depuis data.gouv.fr, copie depuis un collègue ou un disque externe) : il n'est jamais passé par le bouton de mise à jour, donc son millésime n'a pas été enregistré ;
- le fichier de suivi `.sirene_manifest.json`, écrit à côté de `app.py` lors des téléchargements automatiques, a été supprimé ou n'a pas suivi lors d'une copie du dossier du projet vers un autre poste.

Pour repasser en ✅, il suffit d'utiliser une fois le bouton **« Mettre à jour les données SIRENE »** : le fichier retéléchargé sera suivi normalement. Ce n'est utile que si l'on veut réellement le dernier millésime.

## Nomenclature NAF (rév. 2 / 2025)

L'Insee publie progressivement les colonnes NAF 2025 à côté des colonnes historiques (NAF rév. 2), avant bascule définitive prévue en janvier 2027. L'application accepte les deux : elle utilise la colonne historique tant qu'elle est présente, sinon la colonne NAF 2025.

Pour savoir laquelle a servi à un export, regarder le bloc **« Diagnostic des schémas détectés »**, en bas de la page de résultats : il indique la nomenclature retenue pour chaque table. C'est là qu'il faut vérifier si un rapport référence l'ancienne ou la nouvelle classification.

Plus généralement, la détection des colonnes est défensive : une colonne attendue absente du millésime fourni ne fait pas échouer l'analyse.

## Mise à jour hors ligne par ZIP GitHub

Ce n'est pas le site GitHub qui est en cause : dans la plupart des entreprises, il reste consultable depuis un navigateur. Ce qui est bloqué, ce sont les **connexions sortantes du script de mise à jour** (proxy, filtrage, pare-feu). Résultat : la bannière de version ne s'affiche pas, ou le bouton « Mettre à jour maintenant » échoue, alors que la page GitHub s'ouvre normalement dans le navigateur.

L'encadré **« Mise à jour hors ligne depuis un ZIP GitHub »** reste disponible en haut de l'interface, même quand la vérification automatique de version a échoué. Marche à suivre :

1. **Télécharger l'archive depuis un navigateur** — sur le poste de l'application si GitHub y est consultable, sinon depuis n'importe quel autre poste :
   - ouvrir [github.com/clav1stech/Annuaire](https://github.com/clav1stech/Annuaire) ;
   - vérifier que la branche affichée en haut à gauche est bien **`main`** ;
   - cliquer sur le bouton vert **`< > Code`**, puis, tout en bas du menu déroulant, sur **Download ZIP** ;
   - un fichier `Annuaire-main.zip` arrive dans le dossier Téléchargements. **Ne pas le décompresser.**
2. **Transférer ce `.zip`** sur le poste de l'application s'il a été téléchargé ailleurs (clé USB, partage réseau, e-mail).
3. **Déposer le ZIP dans l'application** : glisser-déposer le fichier dans l'encadré (ou cliquer pour le sélectionner), puis cliquer sur **« Appliquer la mise à jour hors ligne »**.
4. **Fermer l'application et relancer `run_app`** pour charger la nouvelle version.

Avant toute copie, l'application vérifie que l'archive correspond bien au projet Annuaire, que son fichier `VERSION` est valide et plus récent que la version installée, et qu'aucun chemin ne peut sortir du dossier du projet. Elle applique les mêmes exclusions que la mise à jour automatique : Parquet SIRENE, `.git`, environnement virtuel, caches et `export/` sont préservés. Seuls les fichiers de code dont le contenu diffère sont remplacés ; les fichiers locaux absents de l'archive ne sont pas supprimés. Le ZIP est seulement lu pendant l'opération : il n'est pas conservé dans le projet.

## Mise à jour en ligne de commande

Alternative à l'interface, notamment si l'application ne démarre plus : lancer `update_project.bat` (Windows) ou `./update_project.command` (macOS/Linux). Le script compare la version locale à celle publiée sur GitHub, demande confirmation, puis applique les fichiers à jour. Il **ne touche jamais** aux fichiers Parquet SIRENE ni au dossier `export/`.

Deux modes, choisis automatiquement selon la façon dont le projet a été obtenu :

- **projet téléchargé en ZIP** (cas standard) : téléchargement de l'archive de `main` et copie des fichiers mis à jour par-dessus le dossier. Ce mode ne supprime pas les anciens fichiers devenus obsolètes ; en cas de gros doute, un nouveau téléchargement ZIP complet reste la méthode la plus sûre ;
- **projet cloné avec `git`** (usage avancé) : `git fetch` puis `git pull --ff-only`. En présence de modifications locales non commitées, la mise à jour est annulée par sécurité plutôt que de risquer de les écraser — le message l'indique explicitement et rien n'est modifié.

Si la liste des bibliothèques a changé, le script le signale : rien de plus à faire, `run_app` les installe au lancement suivant.

## Dossier synchronisé (OneDrive & co)

Les fichiers SIRENE pèsent plusieurs Go. Dans un dossier synchronisé, ils sont réenvoyés dans le cloud à chaque mise à jour mensuelle (quota et bande passante saturés), la synchronisation peut bloquer momentanément l'écriture (message *« Accès refusé »* en fin de téléchargement), et l'option « fichiers à la demande » peut vider un Parquet du disque et faire échouer une analyse.

Attention : dans beaucoup d'entreprises, **Bureau et Documents sont automatiquement redirigés vers OneDrive** — vérifier le chemin affiché dans la barre d'adresse de l'explorateur (s'il contient « OneDrive », le dossier est synchronisé). Le dossier **Téléchargements** est en général un bon choix, car rarement synchronisé ; sinon, un dossier créé à la racine comme `C:\Annuaire_SIRENE` ou `~/Annuaire_SIRENE` évite tous ces cas.

Si aucun emplacement non synchronisé n'est disponible, l'application reste utilisable : une synchronisation cloud ou un antivirus peut garder un fichier ouvert au moment du remplacement, mais l'application réessaie automatiquement et, si le verrou persiste, le signale clairement sans perdre le fichier téléchargé. En cas de blocage persistant, mettre la synchronisation en pause le temps du téléchargement (clic sur l'icône OneDrive → *Suspendre la synchronisation*).

## Export du projet

`scripts/export_project.py` produit une copie du projet destinée à la sauvegarde ou à la transmission à une IA. Il exporte les fichiers `.py`, `.bat`, `.sh`, `.md`, `.txt` et exclut les `.parquet`, les environnements virtuels, les caches, le dossier `export/` et `requirements.txt`.

```bash
python scripts/export_project.py
```

La sortie va dans `export/export_<projet>_<horodatage>_vX.Y.Z/` et contient les fichiers copiés, un `manifest.txt` et un fichier de contexte regroupant tout le code. Options utiles : `--enable-zip-export true` pour générer aussi une archive `.zip`, `--include-extra-items true` pour archiver en plus les éléments lourds.
