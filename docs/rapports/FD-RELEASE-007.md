# Rapport — FD-RELEASE-007

Version corrective Forge Design 0.4.1.
Date : 2026-10-20.

**Verdict : RELEASE_READY — Forge Design 0.4.1.**

## Objectif

Distribuer FD-UX-008, commit `421d957` poussé sur `main` : l'interface est
rédigée selon la partie « écran » de l'ADR-002 de style de SéquenCiel.

- Noms d'outils courts : Accueil, Vue d'ensemble, Routes, Entités, Gabarits,
  Éditeur, Diagnostic.
- Ni tiret cadratin ni point-virgule affichés. « · » sépare, « – » marque une
  valeur absente.
- Une phrase compte au plus un deux-points. Les préfixes de gravité et de
  fichier sont séparés par « · ».
- `render_page` applique `french_typography` : espaces insécables devant
  « : ; ? ! » et dans les guillemets, une phrase par ligne. Le code, les
  attributs, les boutons et le Design rendu dans l'aperçu ne sont pas touchés.
- Les aides suivent leur formulaire, en noir et en italique.

Le code n'est pas traduit. Aucune route, aucun format et aucun contrat de
données ne change. La CSP du cœur n'est pas assouplie.

## Version

| Source | Valeur |
|---|---|
| `forge_design.__version__` (source unique) | `0.4.1`, commit `1704969` |
| Assertions de version exacte | `tests/test_import.py`, `tests/test_module_version_compatibility.py` |
| METADATA / PKG-INFO | `Version: 0.4.1` |
| `forge-design --version` | `Forge Design 0.4.1` (roue, sdist, `.venv` éditable, venv du porteur) |
| `MODULE_API_VERSION` | 1, inchangé |

C'est une version **CORRECTIVE** (`docs/release/versioning.md`) : textes,
typographie et style, sans capacité publique nouvelle. Les API publiques
supportées (`forge_design.modules`, `forge_design.specialized`, contrat
`GraphicScene`, Graphic Core) sont inchangées. Seul le texte de certains
libellés de scène change, par exemple « Entité · 3 champs ». Le `.venv` de
développement a été réinstallé en éditable `compat`.

## Validation du dépôt

| Contrôle | Résultat |
|---|---|
| Suite complète (`--basetemp` court) | **5 341 réussis** |
| Tests Node du Graphic Core | 134/134 |
| `ruff check .` / `ruff format --check .` | OK / 485 fichiers |
| `pyright` | 0 erreur |

## Build

Même chaîne qu'en FD-RELEASE-006 : Python 3.13.5, setuptools 84.0.0,
build 1.6.1, hors ligne, `python -m build --no-isolation`. Chaque build part de
`git archive 1704969`, dans un dossier neuf, avec `SOURCE_DATE_EPOCH` fixé à la
date de ce commit.

| Artefact | Taille | SHA-256 |
|---|---:|---|
| `forge_design-0.4.1-py3-none-any.whl` | 636 892 | `03d84003861ae397f4eb73d3af42c069563500d2c955e82fa66ca39ac3bea086` |
| `forge_design-0.4.1.tar.gz` | 895 619 | `618241b1e34d657bb38e449dcd61c708c96367baaa444a255f579f8b6b0357c2` |

Les deux artefacts sont dans `tmp/fd-release-007/dist1/`.

## Reproductibilité et identité avec Git

| Contrôle | Résultat |
|---|---|
| Roue : deux builds espacés de plus de 3 s | **Identique octet pour octet** |
| Roue : membres | 176 (171 sous `forge_design/`, 5 en `dist-info`), RECORD vérifié sans écart |
| Roue contre les blobs de `git ls-tree -r 1704969` | **171/171** identiques ; 0 manquant, 0 en plus |
| sdist : membres | 325, dont 317 suivis identiques aux blobs Git et 8 métadonnées générées |
| sdist : différence entre les deux builds | En-têtes tar des métadonnées générées et horodatage gzip seulement |
| Ressources | **41/41** dans la roue et le sdist ; `typography.py` et `shell.css` vérifiés de Git aux artefacts |
| Exclusions, secrets synthétiques | 0 fichier interdit, 0 secret |
| `Requires-Dist`, point d'entrée | Inchangés |

Le seul chemin absolu trouvé est `/home/roger/a` dans
`tests/test_entity_source.py` du sdist. C'est un chemin que ce test fait
refuser exprès, déjà présent en 0.4.0.

## Installations

| Cible | Résultat |
|---|---|
| sdist, venv neuf Python 3.13.5, hors ligne | `pip check` OK, `Forge Design 0.4.1` |
| Roue du kit, avec Circuit et Flowchart 0.1.0 | `pip check` OK, `forge-design` 0.4.1 |
| **Venv du porteur** `~/.venvs/forge-design` (Python 3.12.13) | Roue `03d84003…` installée hors ligne avec `--no-deps` ; seule la ligne `forge-design` change (0.4.0 → 0.4.1) ; `pip check` OK |

## Acceptance

Le kit du commit `1704969` a été lancé depuis un **worktree détaché propre** de
ce commit, sans `ONLY`, avec `CIRCUIT_REPO` et `FLOWCHART_REPO` explicites. Il
tournait sur le port 8796. Seul un lanceur fixe ce port pour la CLI installée
par le kit ; le reste du kit est celui du commit. Les deux passes ont tourné
l'une après l'autre (`setsid --wait`), dans des dossiers neufs, sur le disque
racine avec un `TMPDIR` dédié, car `/tmp` est presque plein.

Ce kit contient deux contrôles ajoutés par FD-UX-008, faits sur chaque page
visitée. Chaque `.help-text` doit se calculer en `--ink` et en italique. Aucune
phrase d'un bloc ne doit compter plus d'un deux-points.

| Contrôle | Passe 1 | Passe 2 |
|---|---|---|
| Code / version | 0 / `Forge Design 0.4.1` | 0 / `Forge Design 0.4.1` |
| Chromium / Firefox / sans JavaScript | **32/32 / 32/32 / 12/12** | **32/32 / 32/32 / 12/12** |
| Instantanés | 24 conformes, 0 écart | Idem |
| Garde Host et Origin | Hôte valide 200 ; `localhost`, étranger, rebinding 400 ; POST d'origine étrangère, absente ou cross-site 403 | Identique |
| Processus résiduels | `[]` | `[]` |
| Endurance (RSS) | 53 508 → 56 188 Kio (+2,6 Mio), aucun enfant | 53 524 → 56 272 Kio (+2,7 Mio), aucun enfant |

Les deux passes sont déterministes. Les étapes et leurs statuts sont
identiques. Les 37 fichiers de résultats sans durée ni chemin propre à la passe
sont identiques. Sur 50 instantanés, 48 donnent les mêmes types, tailles et
SHA-256. Les deux derniers ne diffèrent que par
`.forge-design/history.jsonl` de B-write, qui contient l'heure des
modifications. Le worktree avait un statut vide avant comme après, et il a été
retiré.

## Smoke sur l'installation du porteur

Serveur de test lancé avec l'interpréteur du venv du porteur
(`run_server(port=8799)`), HOME et XDG isolés, et SéquenCiel ouvert en lecture
seule :

| Contrôle | Résultat |
|---|---|
| Code chargé | `site-packages` du venv du porteur, version 0.4.1 |
| Ouverture de SéquenCiel | 200 en 935 ms |
| Accueil, Vue d'ensemble, Routes, Entités, Gabarits, gabarit brut, Diagnostic, Éditeur | 200, aucun tiret cadratin, espaces insécables présents, nouveaux noms affichés |
| Aides `.help-text` | 3 sur la Vue d'ensemble, 1 sur Routes, 3 sur Diagnostic, 3 dans l'Éditeur |
| `/fonts/IBMPlexSans-Regular.woff2`, `/shell.css` | 200, `font/woff2` et `text/css` ; règle finale des aides présente |
| SIGTERM | Arrêt en 81 ms, port libéré |

Aucune instance du porteur ne tournait sur 8765 pendant l'installation. Au
prochain lancement de `~/.venvs/forge-design/bin/forge-design`, c'est la 0.4.1
qui démarre.

## Fichiers

| Commit | Contenu |
|---|---|
| `421d957` | FD-UX-008 : interface, typographie, cliquet ADR-002, kit d'acceptance |
| `1704969` | `forge_design/__init__.py`, `tests/test_import.py`, `tests/test_module_version_compatibility.py` |
| Ce rapport | `docs/rapports/FD-RELEASE-007.md`, `docs/03-roadmap.md` |

Il n'y a ni tag, ni PyPI, ni GitHub Release.

## Limites

- **Coût de la typographie sur un grand projet.** Sur SéquenCiel, la page
  Routes pèse 4,1 Mo. `french_typography` y prend environ 420 ms, sur les
  1 744 ms de l'affichage. Les autres pages restent sous 160 ms, sauf la Vue
  d'ensemble et l'Éditeur, dont le temps vient de l'analyse du projet. Cela
  s'ajoute à la dette déjà notée : Route Explorer charge toutes les chaînes,
  sans pagination.
- Les règles de l'ADR-002 qui portent sur le code (identifiants en français)
  ne sont pas appliquées, comme convenu.
- Les venvs de ForgeDesign-Circuit et ForgeDesign-Flowchart déclarent encore
  le cœur en 0.2.0 dans leur métadonnée éditable, comme lors des versions
  précédentes. Ils exécutent bien le code du dépôt.
