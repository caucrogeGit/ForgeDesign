# Rapport — FD-RELEASE-008

Version corrective Forge Design 0.4.2.
Date : 2026-10-20.

**Verdict : RELEASE_READY — Forge Design 0.4.2.**

## Objectif

Distribuer FD-UX-009, commit `f8627f4` poussé sur `main` : l'accueil (`/`)
devient un espace de travail épuré.

- Avec un projet ouvert : en-tête au nom du projet (initiale, racine, version
  Forge) et grille des six outils, chacun avec une ligne de description.
- Sans projet : « Forge Design », une accroche et un formulaire « Ouvrir un
  projet » qui poste vers `/inspector`.
- Projets récents en lignes sobres, avec la pastille « Ouvert » sur le projet
  courant.

La page reçoit le même contexte qu'avant et ne lance aucune nouvelle analyse.
Aucune route, aucun format et aucun contrat de données ne change. La CSP du
cœur n'est pas assouplie.

## Version

| Source | Valeur |
|---|---|
| `forge_design.__version__` (source unique) | `0.4.2`, commit `e55cb19` |
| Assertions de version exacte | `tests/test_import.py`, `tests/test_module_version_compatibility.py` |
| METADATA / PKG-INFO | `Version: 0.4.2` |
| `forge-design --version` | `Forge Design 0.4.2` (roue, sdist, `.venv` éditable, venv du porteur) |
| `MODULE_API_VERSION` | 1, inchangé |

C'est une version **CORRECTIVE** (`docs/release/versioning.md`) : présentation
seule, sans capacité publique nouvelle ni API publique rompue. Le `.venv` de
développement a été réinstallé en éditable `compat`.

## Validation du dépôt

| Contrôle | Résultat |
|---|---|
| Suite complète (`--basetemp` court) | **5 341 réussis** |
| `ruff check .` / `ruff format --check .` | OK / 486 fichiers |
| `pyright` | 0 erreur |

## Build

Même chaîne qu'en FD-RELEASE-007 : Python 3.13.5, setuptools 84.0.0,
build 1.6.1, hors ligne, `python -m build --no-isolation`. Chaque build part de
`git archive e55cb19`, dans un dossier neuf, avec `SOURCE_DATE_EPOCH` fixé à la
date de ce commit.

| Artefact | Taille | SHA-256 |
|---|---:|---|
| `forge_design-0.4.2-py3-none-any.whl` | 638 916 | `51670212e529e7dcc3acf53a30d87daa1ad2b77a6e1d18ec2e068c802711b733` |
| `forge_design-0.4.2.tar.gz` | 897 376 | `0ad102746331f0a008d125341cda0d000b1b76c9f61c4ce136569b99e9ef5606` |

Les deux artefacts sont dans `tmp/fd-release-008/dist1/`.

## Reproductibilité et identité avec Git

| Contrôle | Résultat |
|---|---|
| Roue : deux builds espacés de plus de 3 s | **Identique octet pour octet** |
| Roue : membres | 176 (171 sous `forge_design/`, 5 en `dist-info`), RECORD vérifié sans écart |
| Roue contre les blobs de `git ls-tree -r e55cb19` | **171/171** identiques ; 0 manquant, 0 en plus |
| sdist : membres | 325, dont 317 suivis identiques aux blobs Git et 8 métadonnées générées |
| Ressources | **41/41** dans la roue et le sdist ; `index.html`, `shell.css` et `recent_projects.py` vérifiés de Git aux artefacts |
| Exclusions, secrets synthétiques | 0 fichier interdit, 0 secret |
| `Requires-Dist`, point d'entrée | Inchangés |

Le seul chemin absolu reste `/home/roger/a`, refusé exprès par
`tests/test_entity_source.py`.

## Installations

| Cible | Résultat |
|---|---|
| sdist, venv neuf Python 3.13.5, hors ligne | `pip check` OK, `Forge Design 0.4.2` |
| Roue du kit, avec Circuit et Flowchart 0.1.0 | `pip check` OK, `forge-design` 0.4.2 |
| **Venv du porteur** `~/.venvs/forge-design` (Python 3.12.13) | Roue `51670212…` installée hors ligne avec `--no-deps` ; seule la ligne `forge-design` change (0.4.1 → 0.4.2) ; `pip check` OK |

## Acceptance

Le kit du commit `e55cb19` a été lancé depuis un **worktree détaché propre** de
ce commit, sans `ONLY`, avec `CIRCUIT_REPO` et `FLOWCHART_REPO` explicites, sur
le port 8796. Seul un lanceur fixe ce port. Les deux passes ont tourné l'une
après l'autre, dans des dossiers neufs, sur le disque racine avec un `TMPDIR`
dédié. Les contrôles ADR-002 du kit (style calculé des aides, un deux-points
par phrase) s'appliquent au nouvel accueil.

| Contrôle | Passe 1 | Passe 2 |
|---|---|---|
| Code / version | 0 / `Forge Design 0.4.2` | 0 / `Forge Design 0.4.2` |
| Chromium / Firefox / sans JavaScript | **32/32 / 32/32 / 12/12** | **32/32 / 32/32 / 12/12** |
| Instantanés | 24 conformes, 0 écart | Idem |
| Garde Host et Origin | Hôte valide 200 ; `localhost`, étranger, rebinding 400 ; POST d'origine étrangère, absente ou cross-site 403 | Identique |
| Processus résiduels | `[]` | `[]` |
| Endurance (RSS) | 53 484 → 60 924 Kio (+7,3 Mio), aucun enfant | 53 416 → 56 156 Kio (+2,7 Mio), aucun enfant |

Les deux passes sont déterministes : étapes et statuts identiques, 37 fichiers
de résultats sans durée identiques, 48 instantanés sur 50 identiques en types,
tailles et SHA-256. Les deux derniers ne diffèrent que par
`.forge-design/history.jsonl` de B-write, qui contient l'heure des
modifications. Le worktree avait un statut vide avant comme après, et il a été
retiré.

L'endurance varie entre les passes comme en 0.4.0 (+7,3 Mio puis +2,6 Mio). La
hausse reste bornée, sans enfant résiduel.

## Smoke sur l'installation du porteur

Serveur de test lancé avec l'interpréteur du venv du porteur
(`run_server(port=8799)`), HOME et XDG isolés :

| Contrôle | Résultat |
|---|---|
| Code chargé | `site-packages` du venv du porteur, version 0.4.2 |
| Accueil sans projet | 200, `h1` « Forge Design », formulaire d'ouverture (`maxlength="4096"`) |
| Accueil avec SéquenCiel ouvert | 200 en 25 ms, `h1` « SequenCiel », 6 tuiles d'outils, pastille « Ouvert » |
| Vue d'ensemble, Routes, Entités, Gabarits, Diagnostic, Éditeur | 200 (942, 1 745, 148, 82, 45 et 896 ms) |
| `/shell.css` | 200, règles de l'accueil présentes |
| SIGTERM | Arrêt en 60 ms, port libéré |

**L'instance du porteur doit être redémarrée.** Elle tournait sur 8765
(PID 1893597) pendant l'installation : elle garde le code Python de la 0.4.1 en
mémoire, alors que les templates et la CSS sont relus depuis le disque. Entre
les deux versions, seuls `index.html`, `shell.css` et `recent_projects.py`
changent. L'ancien code rend donc le nouvel accueil sans erreur, avec seulement
un attribut `maxlength` vide. Le processus n'a pas été arrêté.

## Fichiers

| Commit | Contenu |
|---|---|
| `f8627f4` | FD-UX-009 : accueil, styles, tests adaptés |
| `e55cb19` | `forge_design/__init__.py`, `tests/test_import.py`, `tests/test_module_version_compatibility.py` |
| Ce rapport | `docs/rapports/FD-RELEASE-008.md`, `docs/03-roadmap.md` |

Il n'y a ni tag, ni PyPI, ni GitHub Release.

## Limites

- La typographie ajoute toujours environ 420 ms à la page Routes de SéquenCiel
  (FD-RELEASE-007).
- La grille de l'accueil ne montre aucun chiffre du projet (nombre de routes,
  d'entités…), parce que l'accueil ne lance aucune analyse. La Vue d'ensemble
  reste la page de synthèse.
