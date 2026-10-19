# Rapport — FD-RELEASE-005

Version corrective Forge Design 0.3.1.
Date : 2026-10-19.

**Verdict : RELEASE_READY — Forge Design 0.3.1.**

## Objectif

Distribuer la correction du serveur Web (`6bf5464`) : une connexion ouverte sans
requête ne fige plus Forge Design.

Le défaut a été constaté le 2026-10-19 sur l'instance installée du porteur
(roue 0.3.0, `~/.venvs/forge-design`). Le transfert de port de VS Code avait
ouvert vers `127.0.0.1:8765` une connexion qui n'envoyait rien. Le serveur
`wsgiref`, à un seul thread et sans délai, l'attendait indéfiniment, avec sa file
d'écoute pleine (5/5) et toutes les autres requêtes en attente. Le même code
avalait aussi un SIGTERM reçu pendant une requête : il fallait `kill -9`.

## Correction livrée

| Élément | Avant (0.3.0) | Après (0.3.1) |
|---|---|---|
| Lecture et écriture des connexions | Une à la fois, dans le thread principal, sans délai | Un thread par connexion, délai client de 15 s (`CLIENT_TIMEOUT`) |
| Exécution de l'application | Une requête à la fois | Une requête à la fois, inchangé (`ForgeDesignServer.dispatching`) |
| Connexion muette | Bloque tout le serveur | Fermée sans réponse à l'échéance, sans effet sur les autres |
| Arrêt | La requête en cours peut être interrompue | Requêtes suivantes en 503, requête courante terminée, puis preview réelle fermée ; les connexions muettes ne sont pas attendues |
| SIGTERM pendant une requête | Avalé par `wsgiref` | Reçu par le thread principal, arrêt immédiat |

La garantie de l'éditeur est conservée : deux POST portant la même révision
passent l'un après l'autre, et le second est refusé en 409. Le test qui la porte
(`test_http_server_serialises_requests`) vérifie maintenant la garantie
elle-même, et non l'absence de `ThreadingMixIn`. Le proxy de la preview réelle
utilisait déjà ce modèle (`ThreadingMixIn`, délai client de 15 s).

## Version

| Source | Valeur |
|---|---|
| `forge_design.__version__` (source unique) | `0.3.1`, commit `9d05397` |
| Assertions de version exacte | `tests/test_import.py` et `tests/test_module_version_compatibility.py`, de 0.3.0 à 0.3.1, sans affaiblissement |
| METADATA / PKG-INFO | `Version: 0.3.1` |
| `forge-design --version` | `Forge Design 0.3.1` (roue, sdist, `.venv` éditable, venv du porteur) |
| `MODULE_API_VERSION` | 1, inchangé |

C'est une version **CORRECTIVE** (`docs/release/versioning.md`) : correction
compatible, sans capacité publique nouvelle. Le `.venv` de développement a été
réinstallé en éditable `compat`, hors ligne, avec setuptools 84.0.0 local
(`.pth`, métadonnée 0.3.1), sans `build/` résiduel.

## Validation du dépôt

| Contrôle | Résultat |
|---|---|
| Suite complète (`--basetemp` court) | **5 310 réussis** (5 305 + 5 tests de régression du serveur) |
| `ruff check .` / `ruff format --check .` | OK / 481 fichiers |
| `pyright` | 0 erreur |
| Test de la connexion muette rejoué contre l'ancien `server.py` | Échoue (`TimeoutError`), comme le défaut constaté |

## Build

Chaîne de FD-RELEASE-004 : Python 3.13.5, setuptools 84.0.0, build 1.6.1, hors
ligne, `python -m build --no-isolation`. Chaque build part de `git archive
9d05397`, extrait dans un dossier neuf.

Un premier essai sans réglage donnait deux roues de **contenu identique** mais de
SHA-256 différents : les horodatages zip des 4 métadonnées générées
(`METADATA`, `WHEEL`, `entry_points.txt`, `top_level.txt`) suivaient l'heure du
build, 16:26:00 contre 16:26:02. En 0.3.0, l'identité tenait à des builds faits
dans la même fenêtre de 2 s. Les builds retenus fixent donc
`SOURCE_DATE_EPOCH=1792427155`, la date du commit `9d05397`.

| Artefact | Taille | SHA-256 |
|---|---:|---|
| `forge_design-0.3.1-py3-none-any.whl` | 325 625 | `d2a03aca960bf8bf4a60d6a1c40007c176370a1e5ee25e5aab2d5b1b1ba22658` |
| `forge_design-0.3.1.tar.gz` | 576 547 | `0a44efbc331b4ffdbd7958f75442ebc959eafcf98b4a281381b1a833e8716e63` |

Les deux artefacts sont rangés dans `tmp/fd-release-005-dist/`, ignoré par Git.

## Reproductibilité et identité avec Git

| Contrôle | Résultat |
|---|---|
| Roue : deux builds espacés de plus de 3 s | **Identique octet pour octet** |
| Roue : membres | 169 (164 sous `forge_design/`, 5 en `dist-info`), RECORD vérifié sans écart |
| Roue contre les blobs de `git ls-tree -r 9d05397` | **164/164** identiques ; 0 manquant, 0 en plus |
| sdist : membres | 317 : 309 suivis, identiques aux blobs Git, et 8 métadonnées générées |
| sdist : différence entre les deux builds | En-têtes tar des 8 métadonnées et horodatage gzip seulement, comme en 0.3.0 |
| Ressources | 35/35 présentes dans la roue et le sdist |
| Exclusions, secrets synthétiques | 0 fichier interdit, 0 secret |
| Chemin absolu | `tests/test_entity_source.py`, entrée hostile volontaire, déjà classée en 0.3.0 |
| `Requires-Dist`, point d'entrée | Inchangés : `forge-mvc==1.0.0rc9`, `jinja2==3.1.6`, `pydantic<3,>=2`, `packaging>=24.0` ; `forge-design = forge_design.cli:main` |

## Installations

| Cible | Résultat |
|---|---|
| sdist, venv neuf Python 3.13, hors ligne | `pip check` OK, `Forge Design 0.3.1` |
| Roue du kit d'acceptance, avec Circuit et Flowchart 0.1.0 | `pip check` OK ; `forge-design` 0.3.1, `forge-design-circuit` 0.1.0, `forge-design-flowchart` 0.1.0, `forge-mvc` 1.0.0rc9 |
| **Venv du porteur** `~/.venvs/forge-design` (Python 3.12.13) | Roue `d2a03aca…` installée hors ligne avec `--no-deps` ; seule la ligne `forge-design` change (0.3.0 → 0.3.1) ; `pip check` OK ; code chargé depuis `site-packages` |

Les modules Circuit et Flowchart (`forge-design>=0.2.0,<1`) acceptent la 0.3.1
sans modification.

## Smoke sur l'installation du porteur

La vraie commande `forge-design --no-browser` a été lancée avec HOME et XDG
isolés, sur `127.0.0.1:8765` :

| Contrôle | Résultat |
|---|---|
| Démarrage | `Forge Design 0.3.1`, `http://127.0.0.1:8765/` |
| `/`, `/inspector`, `/routes` avec **8 connexions muettes** ouvertes (plus que la file d'écoute) | 200 en 26, 19 et 72 ms |
| Connexion muette | Fermée sans réponse par le serveur, environ 15 s après son ouverture |
| SIGTERM | Arrêt en 54 ms, port libéré, aucune trace d'erreur |

Avec le code 0.3.0 dans le même venv, le même scénario expire au bout de 5 s, et
SIGTERM ne suffit plus à arrêter le serveur.

## Acceptance

Le kit du commit `9d05397` a été lancé depuis un **worktree détaché propre** de
ce commit, sans `ONLY`, avec `CIRCUIT_REPO` et `FLOWCHART_REPO` explicites, dans
deux dossiers neufs.

| Contrôle | Passe 1 | Passe 2 |
|---|---|---|
| Code de sortie / version | 0 / `Forge Design 0.3.1` | 0 / `Forge Design 0.3.1` |
| Chromium / Firefox / sans JavaScript | **32/32 / 32/32 / 12/12** | **32/32 / 32/32 / 12/12** |
| Instantanés | 24 « conforme » et l'arrêt conforme, 0 écart | Idem |
| Garde Host et Origin | Hôte valide 200 ; `localhost`, étranger et rebinding 400 ; POST d'origine étrangère, absente ou cross-site 403 | Identique |
| Processus résiduels | `[]` | `[]` |
| Endurance (RSS) | 52 820 → 54 892 Kio, aucun enfant | 52 752 → 54 700 Kio |
| Durée | 2 min 19 s | 2 min 53 s |

Les fichiers de résultats déterministes des deux passes sont **identiques octet
pour octet**. Les étapes qui sollicitent le plus le nouveau transport réussissent
toutes :
- l'éditeur, y compris la vue périmée dans deux onglets refusée en 409 ;
- les deux Real Preview ;
- les commandes runtime, avec le délai dépassé à environ 10 s ;
- les modules.

Le worktree avait un statut vide avant comme après, et il a été retiré.

## Fichiers

| Commit | Contenu |
|---|---|
| `6bf5464` | `forge_design/web/server.py`, `tests/test_web_server.py`, `tests/test_web_editor_revision.py`, `tests/test_cli.py`, `docs/02-architecture.md` |
| `9d05397` | `forge_design/__init__.py`, `tests/test_import.py`, `tests/test_module_version_compatibility.py` |
| Ce rapport | `docs/rapports/FD-RELEASE-005.md`, `docs/03-roadmap.md` |

Non modifiés : `pyproject.toml`, le kit d'acceptance, les modules,
`FD-CONTRACT-001.md`. Hors Git : `tmp/fd-release-005/` (builds, deux passes,
venv sdist) et `tmp/fd-release-005-dist/` (artefacts). Il n'y a ni tag, ni
PyPI, ni GitHub Release.

## Limites

- La file d'écoute reste de 5 connexions (`request_queue_size` de `socketserver`).
  Les connexions sont désormais acceptées et confiées à un thread aussitôt, et
  la file ne se remplit plus.
- Une connexion muette garde son thread jusqu'à 15 s, même après l'arrêt du
  serveur. Ces threads sont des démons et n'empêchent pas la sortie.
- L'application reste sérialisée : une requête longue, comme `project:check`
  bornée à 10 s ou un démarrage de preview réelle, retarde toujours les autres.
  C'est le comportement voulu, inchangé.
