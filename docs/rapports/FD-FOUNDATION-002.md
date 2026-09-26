# Rapport FD-FOUNDATION-002 — Paquet Python minimal

- **Ticket :** FD-FOUNDATION-002.
- **Objectif :** créer le socle Python minimal installable de Forge Design.
- **Branche :** `main`.
- **Commit :** `ab837310039f3d0228a106d415ddfc2acc1cd2cc`.
- **État Git initial :** `main` au commit fondateur `89b6a6a654adc5413f2628ebfc3686be20f66143`, fichiers suivis propres ; `tmp/` non suivi contenant les instructions utilisateur. Ce dossier a été conservé et ignoré via le `.gitignore` du ticket.

## Fichiers créés

- `pyproject.toml` : métadonnées, build setuptools, extra de développement et configuration des validations.
- `forge_design/__init__.py` : package importable et version.
- `tests/test_import.py` : contrat d'import et cohérence de version avec les métadonnées installées.
- `.gitignore` : environnements, caches, artefacts Python, fichiers `.env` et dossier local `tmp/`.

Le présent rapport et les artefacts de vérification sont locaux dans `tmp/`, hors commit.

## Fichiers modifiés

Aucun fichier préexistant suivi n'a été modifié. Les documents fondateurs sont préservés.

## Choix techniques

- Distribution `forge-design`, package `forge_design`.
- Version pré-alpha `0.1.0.dev0`, indépendante de Forge, conformément aux instructions.
- Source unique de version dans `forge_design.__version__`, lue par setuptools.
- Python déclaré `>=3.12` ; exécution des validations sous Python `3.13.5`.
- Package explicitement inclus pour ne pas distribuer `tests/`, `docs/` ou `tmp/` comme packages.
- Pyright en mode strict ; Ruff cible Python 3.12 avec règles E, F et I.
- Aucune licence inventée ; la décision reste ouverte avant diffusion versionnée.

## Dépendances ajoutées

- Exécution : aucune.
- Build : `setuptools>=68`.
- Extra `dev` : `pytest>=8`, `ruff>=0.9`, `pyright>=1.1.390`.
- Versions effectivement utilisées : pytest `9.1.1`, Ruff `0.16.9`, Pyright `1.1.414`.
- Dépendances transitives de développement installées : iniconfig `2.3.0`, packaging `26.3`, pluggy `1.6.0`, pygments `2.21.0`, nodeenv `1.10.0`, typing-extensions `4.16.0`.

## Tests ajoutés

`test_import_and_distribution_version` importe le package, vérifie sa version initiale et sa cohérence avec `importlib.metadata.version("forge-design")`.

## Commandes exécutées et résultats complets

Les inspections ont utilisé `git status --short --branch`, `git log --oneline --decorate -5`, `rg --files`, `ls`, `cat`, `python3 --version` et la recherche des outils disponibles. Les instructions et documents fondateurs ont été lus.

| Commande | Résultat |
|---|---|
| `python3 -m venv .venv` | Réussite |
| `.venv/bin/python -m pip install -e '.[dev]'` | Échec initial : accès réseau/DNS bloqué par le sandbox pour les dépendances de build |
| `.venv/bin/python -m pip install --no-cache-dir -e '.[dev]'` | Réussite après autorisation réseau ; installation éditable et outils de développement |
| `.venv/bin/pytest` | **1 réussi, 0 échoué, 0 sauté**, en 0,02 s |
| `.venv/bin/python -m compileall -q forge_design` | Code retour 0 |
| `.venv/bin/ruff check forge_design tests` | `All checks passed!` |
| `.venv/bin/pyright` | `0 errors, 0 warnings, 0 informations` |
| `.venv/bin/python -m pip check` | `No broken requirements found.` |
| `git diff --check` | Code retour 0 |
| `.venv/bin/python -m pip wheel --no-cache-dir --no-deps --wheel-dir tmp/wheels .` | Wheel construite avec succès après autorisation réseau |
| `python3 -m venv tmp/wheel-venv` | Environnement vierge créé |
| `tmp/wheel-venv/bin/python -m pip install --no-index --no-deps tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl` | Installation hors réseau réussie sans dépendances |
| `git add .gitignore pyproject.toml forge_design/__init__.py tests/test_import.py` | Quatre fichiers indexés après autorisation d'écriture dans Git |
| `git diff --cached --check` | Code retour 0 |
| `git diff --cached` | Diff intégral inspecté : quatre fichiers, périmètre conforme |
| `git commit -m "build: créer le paquet Python minimal (FD-FOUNDATION-002)"` | Commit `ab83731`, quatre fichiers créés, 63 insertions |
| `git status --short --branch` et `git rev-parse HEAD` | Arbre de travail propre, `main` en avance d'un commit sur la référence locale `origin/main` |

Vérification supplémentaire de la wheel, exécutée avec succès :

```bash
tmp/wheel-venv/bin/python -I -c 'import forge_design; from importlib.metadata import version, requires; assert forge_design.__version__ == version("forge-design") == "0.1.0.dev0"; assert all("extra ==" in r for r in requires("forge-design") or []); print(forge_design.__file__); print(forge_design.__version__)'
```

Résultat : import depuis `tmp/wheel-venv/lib/python3.13/site-packages/forge_design/__init__.py`, version `0.1.0.dev0`. Le mode isolé empêche un import accidentel depuis le répertoire source. Les dépendances déclarées sont uniquement conditionnelles à un extra.

Wheel : `forge_design-0.1.0.dev0-py3-none-any.whl`, SHA-256 `f8db0c5626cc606f1dabc0783a5b24bdb5ed64e7aaf10342493cfc88d3a73ddf`.

Quelques commandes pip ont signalé que le cache utilisateur n'était pas accessible en écriture ; cela n'a pas empêché les validations. L'échec réseau initial a été résolu par l'exécution autorisée hors sandbox.

## Tests sautés

Aucun test sauté. Python 3.12 n'a pas été exécuté : la validation runtime porte sur Python 3.13.5 ; les configurations statiques ciblent 3.12.

## Limites restantes et roadmap

Implémenté : installation du paquet, import, version et validations minimales.

Restent prévus dans des tickets distincts : CLI, Bridge, Project Inspector, Platform, contrat Tool, registre, serveur et UI. Aucun contrat de compatibilité Forge n'est annoncé : ce ticket n'interagit pas avec Forge. Aucun dossier `.forge-design/` ni service d'écriture projet n'a été créé.

## État Git final

Arbre de travail propre, commit local `ab83731` sur `main`, avance d'un commit sur la référence locale `origin/main`. Aucun push effectué. `tmp/`, `.venv/` et les artefacts de build sont ignorés ; les instructions locales restent présentes.
