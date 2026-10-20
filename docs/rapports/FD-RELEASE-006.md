# Rapport — FD-RELEASE-006

Version mineure Forge Design 0.4.0.
Date : 2026-10-20.

**Verdict : RELEASE_READY — Forge Design 0.4.0.**

## Objectif

Distribuer la refonte de l'interface, faite en sept commits poussés sur
`main` :

| Commit | Ticket | Contenu |
|---|---|---|
| `cfe3bba` | FD-UX-001 | Shell d'application et système de design « Atelier » : barre latérale, barre du haut, pleine largeur, polices IBM Plex locales, icônes en masques CSS, tableaux à défilement contenu |
| `238e381` | FD-UX-002 | Project Inspector en tableau de bord (tuiles, priorités, commandes) |
| `43e9a7b` | FD-UX-003 | Route Explorer organisé autour des chaînes |
| `7dc326f` | FD-UX-004 | Éditeur de Design en studio à trois colonnes |
| `fea5ba2` | FD-UX-005 | Entity Explorer organisé autour des entités ; barre latérale fixe |
| `23c9ac1` | FD-UX-006 | Template Viewer groupé par dossier, détail côte à côte |
| `26df5c9` | FD-UX-007 | Debug Center en cartes de commande |

Les mêmes informations et les mêmes actions sont réorganisées. Aucune route
métier, aucun format et aucun contrat de données ne change. La CSP du cœur
(`style-src 'self'`) n'est pas assouplie.

## Version

| Source | Valeur |
|---|---|
| `forge_design.__version__` (source unique) | `0.4.0`, commit `d082f77` |
| Assertions de version exacte | `tests/test_import.py`, `tests/test_module_version_compatibility.py` |
| METADATA / PKG-INFO | `Version: 0.4.0` |
| `forge-design --version` | `Forge Design 0.4.0` (roue, sdist, `.venv` éditable, venv du porteur) |
| `MODULE_API_VERSION` | 1, inchangé |

C'est une version **MINEURE** (`docs/release/versioning.md`). Les capacités sont
additives et compatibles : nouvelle interface, routes fixes `/fonts/<nom>.woff2`
et fonctions de présentation du Template Viewer. Aucune API publique supportée
n'est rompue. Le `.venv` de développement a été réinstallé en éditable `compat`.

## Validation du dépôt

| Contrôle | Résultat |
|---|---|
| Suite complète (`--basetemp` court) | **5 315 réussis** |
| `ruff check .` / `ruff format --check .` | OK / 482 fichiers |
| `pyright` | 0 erreur |

Pendant la refonte, un test du runner
(`test_child_started_by_imported_code_never_survives`) a échoué une fois sous la
charge de la suite complète. Il a réussi 5 fois sur 5 en isolé, puis à chaque
relance complète. C'est une course de timing préexistante, sans lien avec ces
changements.

## Build

Chaîne de FD-RELEASE-004 et FD-RELEASE-005 : Python 3.13.5, setuptools 84.0.0,
build 1.6.1, hors ligne, `python -m build --no-isolation`. Chaque build part de
`git archive d082f77`, dans un dossier neuf, avec
`SOURCE_DATE_EPOCH` fixé à la date de ce commit.

| Artefact | Taille | SHA-256 |
|---|---:|---|
| `forge_design-0.4.0-py3-none-any.whl` | 634 883 | `1ec0e3d08d1bd6dbe888d6af805dc5bdb889a941155587f58f3957d54aa5710e` |
| `forge_design-0.4.0.tar.gz` | 889 991 | `559b7c6a841f4a90dd9b99636ffc1700736868d0d0086e54e4f8bbf7090e5717` |

La roue pèse 309 Kio de plus que la 0.3.1 : ce sont les cinq polices woff2 (294
Kio) et leur licence. Les deux artefacts sont dans `tmp/fd-release-006-dist/`.

## Reproductibilité et identité avec Git

| Contrôle | Résultat |
|---|---|
| Roue : deux builds espacés de plus de 3 s | **Identique octet pour octet** |
| Roue : membres | 175 (170 sous `forge_design/`, 5 en `dist-info`), RECORD vérifié sans écart |
| Roue contre les blobs de `git ls-tree -r d082f77` | **170/170** identiques ; 0 manquant, 0 en plus |
| sdist : membres | 323, dont 315 suivis identiques aux blobs Git et 8 métadonnées générées |
| sdist : différence entre les deux builds | En-têtes tar des métadonnées générées et horodatage gzip seulement |
| Ressources | **41/41** dans la roue et le sdist : les 35 d'avant, 5 polices woff2 et `LICENSE-IBM-Plex.txt` |
| Exclusions, secrets synthétiques | 0 fichier interdit, 0 secret |
| `Requires-Dist`, point d'entrée | Inchangés |

## Installations

| Cible | Résultat |
|---|---|
| sdist, venv neuf Python 3.13, hors ligne | `pip check` OK, `Forge Design 0.4.0` |
| Roue du kit, avec Circuit et Flowchart 0.1.0 | `pip check` OK ; `forge-design` 0.4.0, Circuit 0.1.0, Flowchart 0.1.0, `forge-mvc` 1.0.0rc9 |
| **Venv du porteur** `~/.venvs/forge-design` (Python 3.12.13) | Roue `1ec0e3d0…` installée hors ligne avec `--no-deps` ; seule la ligne `forge-design` change (0.3.1 → 0.4.0) ; `pip check` OK |

## Acceptance

Le kit du commit `d082f77` a été lancé depuis un **worktree détaché propre** de
ce commit, sans `ONLY`, avec `CIRCUIT_REPO` et `FLOWCHART_REPO` explicites. Il
tournait sur le port 8796, parce que l'instance du porteur occupait le 8765.
Seul un lanceur fixe ce port pour la CLI installée par le kit ; le reste du kit
est celui du commit.

| Contrôle | Passe 1 | Passe 2 |
|---|---|---|
| Code / version | 0 / `Forge Design 0.4.0` | 0 / `Forge Design 0.4.0` |
| Chromium / Firefox / sans JavaScript | **32/32 / 32/32 / 12/12** | **32/32 / 32/32 / 12/12** |
| Instantanés | 24 conformes, 0 écart | Idem |
| Garde Host et Origin | Hôte valide 200 ; `localhost`, étranger, rebinding 400 ; POST d'origine étrangère, absente ou cross-site 403 | Identique |
| Processus résiduels | `[]` | `[]` |
| Endurance (RSS) | 53 392 → 60 828 Kio (+7,3 Mio), aucun enfant | 53 432 → 56 060 Kio (+2,6 Mio), aucun enfant |

Les fichiers de résultats déterministes des deux passes sont **identiques octet
pour octet**. Le worktree avait un statut vide avant comme après, et il a été
retiré.

Un premier lancement avait démarré les deux passes en même temps : `setsid`,
lancé en premier plan, se dédouble et rend la main aussitôt. La passe 2 avait
alors échoué au build de la roue, faute d'arbre libre. Ces résultats ont été
écartés, et les deux passes rejouées l'une après l'autre (`setsid --wait`) dans
des dossiers neufs. Seuls ces derniers résultats figurent ici.

L'endurance varie entre les passes : +7,3 Mio puis +2,6 Mio, contre +2,0 Mio en
0.3.1. La hausse reste bornée, sans enfant résiduel. C'est à surveiller.

## Smoke sur l'installation du porteur

Serveur de test lancé avec l'interpréteur du venv du porteur
(`run_server(port=8799)`), HOME et XDG isolés, et SéquenCiel ouvert :

| Contrôle | Résultat |
|---|---|
| Code chargé | `site-packages` du venv du porteur |
| Accueil, Project Inspector, Route Explorer, Entity Explorer, Template Viewer, template brut, Debug Center, Éditeur | Chargés, sans débordement horizontal à 1 440 px, aucune réponse 5xx |
| `/fonts/IBMPlexSans-Regular.woff2`, `/fonts/IBMPlexMono-Medium.woff2` | 200, `font/woff2` |
| `/inspector` avec 8 connexions muettes | 200 en 908 ms (analyse complète de SéquenCiel) |
| SIGTERM | Arrêt en 54 ms, port libéré |

**L'instance du porteur doit être redémarrée.** Elle tournait pendant
l'installation : elle garde l'ancien code Python en mémoire, alors que les
templates et la CSS sont relus depuis le disque.

## Fichiers

| Commit | Contenu |
|---|---|
| `d082f77` | `forge_design/__init__.py`, `tests/test_import.py`, `tests/test_module_version_compatibility.py` |
| Ce rapport | `docs/rapports/FD-RELEASE-006.md`, `docs/03-roadmap.md` |

Il n'y a ni tag, ni PyPI, ni GitHub Release.

## Limites

- La refonte réorganise l'existant. Plusieurs éléments de la maquette restent à
  faire :
  - la sélection d'un bloc en cliquant dans l'aperçu de l'éditeur ;
  - une palette en boutons ;
  - le renommage de la navigation.
- La liste de Template Viewer reste longue sur un grand projet (499 fichiers
  pour SéquenCiel), même groupée par dossier.
- Route Explorer charge toujours toutes les chaînes, sans pagination.
