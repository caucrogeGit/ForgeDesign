# Rapport FD-FORGE-001 — Racine projet sûre

- **Ticket :** FD-FORGE-001.
- **Objectif :** transformer un chemin utilisateur en dossier racine canonique existant, indépendamment de la logique métier Forge.
- **Branche :** `main`.
- **Commit :** `c1ebddfdee16f045aa7b3ea6866c8f48598e6a2c`.
- **État Git initial :** arbre propre ; `HEAD`, `main` et `origin/main` au commit `c0a8d0f`.

## Fichiers créés

- `forge_design/forge/__init__.py`.
- `forge_design/forge/project_root.py`.
- `tests/test_project_root.py`.
- Présent rapport dans `tmp/`, local et ignoré par Git.

## Fichiers modifiés

- `pyproject.toml` : ajout explicite du sous-package `forge_design.forge` aux packages distribués.

## API ajoutée

```python
from forge_design.forge.project_root import resolve_project_root

root = resolve_project_root(path)
```

Signature : `resolve_project_root(path: str | PathLike[str]) -> Path`.
Le résultat est un `Path` absolu canonique pointant sur un dossier existant lors de la validation.

Trois erreurs explicites, dérivées de `ValueError` :

- `ProjectRootNotFoundError` : cible inexistante, notamment lien cassé.
- `ProjectRootNotDirectoryError` : cible ou composant intermédiaire non répertoire.
- `ProjectRootResolutionError` : chemin vide, caractère nul, boucle de liens, erreur d'accès ou autre impossibilité de résolution/vérification.

## Choix de sécurité

- `Path.resolve(strict=True)` avant la vérification du type via `stat` et `S_ISDIR`.
- Chemins relatifs résolus depuis le répertoire courant ; composants `..` et symlinks résolus par le filesystem.
- Symlink racine accepté uniquement si sa cible résolue existe et est un dossier.
- Aucun contenu de fichier lu, aucun scan, aucune écriture ni création dans le projet cible.
- Messages d'erreur explicites ; les exceptions système attendues sont traduites sans chaînage affiché. Cette API Python lève des exceptions : les futures interfaces devront les intercepter pour présenter le message utilisateur sans traceback. La CLI actuelle reste inchangée.
- Retour d'un `Path` simple, sans classe d'état, singleton ou constructeur réalisant des accès implicites.
- Validation ponctuelle documentée : les futurs lecteurs devront vérifier leurs propres cibles et gérer les changements ultérieurs du filesystem. Aucun contrat de confinement des symlinks internes n'est introduit.
- Aucune dépendance ajoutée ; bibliothèque standard uniquement.

## Tests ajoutés

Douze cas : dossier absolu ; dossier relatif ; `..` ; absence ; fichier ; fichier comme composant parent ; symlink racine avec assertions de canonisation, stabilité et absence de création ; lien cassé ; boucle de lien ; chaîne vide ; caractère nul ; erreur d'accès simulée.

Les cas filesystem utilisent `tmp_path`. Le refus d'accès est simulé avec `monkeypatch` pour rester indépendant des privilèges de l'utilisateur de test. Aucun vrai projet Forge n'est requis.

## Commandes exécutées et résultats complets

| Commande | Résultat |
|---|---|
| `git status` | Initialement propre, synchronisé avec la référence locale `origin/main` |
| `git log --oneline --decorate -5` | Historique inspecté, dernier commit `c0a8d0f` |
| `cat pyproject.toml` et `rg --files forge_design tests` | Socle et configuration de distribution inspectés |
| `.venv/bin/pytest` | **16 réussis, 0 échoué, 0 sauté**, en 0,08 s ; 12 nouveaux cas et 4 tests existants |
| `.venv/bin/python -m compileall -q forge_design` | Code 0 |
| `.venv/bin/ruff check forge_design tests` | `All checks passed!`, code 0 |
| `.venv/bin/pyright` | `0 errors, 0 warnings, 0 informations`, code 0 |
| `git diff --check` | Code 0 |
| `.venv/bin/python -m pip wheel --no-cache-dir --no-deps --wheel-dir tmp/fd-forge-001-wheels .` | Wheel construite avec accès réseau autorisé pour les dépendances de build |
| `python3 -m venv tmp/fd-forge-001-venv` | Environnement vierge créé |
| `tmp/fd-forge-001-venv/bin/python -m pip install --no-index --no-deps tmp/fd-forge-001-wheels/forge_design-0.1.0.dev0-py3-none-any.whl` | Installation hors réseau et sans dépendances réussie |
| Vérification Python isolée ci-dessous | Import depuis le `site-packages` de la wheel et résolution d'un dossier temporaire réussis |
| `git add pyproject.toml forge_design/forge/__init__.py forge_design/forge/project_root.py tests/test_project_root.py` | Quatre fichiers indexés |
| `git diff --cached --check` | Code 0 |
| `git diff --cached` | Diff complet inspecté, conforme au périmètre |
| `git commit -m "feat: sécuriser la racine projet (FD-FORGE-001)"` | Commit unique `c1ebddf`, 137 insertions et 1 suppression dans quatre fichiers |
| `git status` et `git rev-parse HEAD` | Arbre propre, un commit local d'avance |

Vérification exécutée sur l'installation de la wheel :

```bash
tmp/fd-forge-001-venv/bin/python -I -c 'from tempfile import TemporaryDirectory; from pathlib import Path; from forge_design.forge.project_root import resolve_project_root; import forge_design.forge.project_root as module; print(module.__file__); directory = TemporaryDirectory(); assert resolve_project_root(directory.name) == Path(directory.name).resolve(); directory.cleanup(); print("Installed root API: OK")'
```

Résultat : module chargé depuis `tmp/fd-forge-001-venv/lib/python3.13/site-packages/forge_design/forge/project_root.py`, puis `Installed root API: OK` ; code 0.

Environnement : Python 3.13.5, pytest 9.1.1, Ruff 0.16.9, Pyright 1.1.414. Pip a signalé un cache utilisateur non accessible en écriture lors de l'installation locale ; celle-ci a néanmoins réussi.

## Tests sautés

Aucun test sauté, aucun test échoué.

## Limites restantes

- Python 3.12 non exécuté ; configurations statiques ciblant 3.12 et exécution sous 3.13.5.
- La validation ne garantit pas l'immuabilité future du chemin ou du dossier.
- Aucun support métier Forge annoncé : détection, version, scan et politiques des lecteurs restent pour leurs tickets respectifs.
- Aucun serveur, UI, Inspector, Platform, registre, configuration, commande Forge, lecture de secrets ou dossier `.forge-design/` ajouté.

## État Git final

Arbre de travail propre sur `main`, commit local `c1ebddf`, un commit d'avance sur la référence locale `origin/main`. Aucun push effectué. Rapport et artefacts de vérification conservés sous `tmp/`, ignorés par Git.
