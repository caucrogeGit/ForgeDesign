# Rapport FD-FOUNDATION-003 — CLI minimale

- **Ticket :** FD-FOUNDATION-003.
- **Objectif :** fournir la commande installée `forge-design --version`.
- **Branche :** `main`.
- **Commit :** `c0a8d0f4543cbf0f99447749caed9ec572b0b280`.
- **État Git initial :** arbre de travail propre, `main` et `origin/main` au commit `ab83731`.

## Fichiers créés

- `forge_design/cli.py` : fonction `main(argv)` utilisant argparse.
- `tests/test_cli.py` : trois tests de CLI.
- `tmp/RAPPORT_FD-FOUNDATION-003.md` : présent rapport local, ignoré par Git.

## Fichiers modifiés

- `pyproject.toml` : entrée installée `forge-design = "forge_design.cli:main"`.
- `README.md` : installation dans un environnement virtuel et utilisation de la commande.

## Choix techniques

- Bibliothèque standard `argparse`, sans architecture de sous-commandes.
- Version importée depuis `forge_design.__version__`, sans nouvelle copie de sa valeur.
- `--version` affiche une ligne terminée par un saut de ligne et sort avec le code 0.
- Sans argument : aide et code 0. Option inconnue : erreur sur stderr et code 2, conformément à argparse.
- `main` accepte une liste d'arguments pour permettre des tests Python directs.
- Le test de version appelle le véritable script installé depuis un répertoire temporaire, avec timeout et capture des sorties.

## Dépendances ajoutées

Aucune, ni runtime ni développement. Les outils existants sont réutilisés.

## Tests ajoutés

1. Commande installée `--version` : stdout exactement égal à `Forge Design {__version__}\n`, code 0 et stderr vide.
2. Appel direct `main([])` : aide présente, code 0, stderr vide.
3. Appel direct avec option inconnue : code 2, stdout vide, erreur mentionnant l'option sur stderr.

Le test d'import préexistant reste inchangé.

## Commandes exécutées et résultats complets

| Commande | Résultat |
|---|---|
| `git status --short --branch` | Initialement propre et synchronisé avec la référence locale `origin/main` |
| `git log --oneline --decorate -5` | Historique conforme : commits `ab83731` et `89b6a6a` |
| `cat pyproject.toml forge_design/__init__.py tests/test_import.py README.md` | Lecture du socle existant |
| Recherche `rg --files --hidden -g AGENTS.md` avec exclusions des répertoires Git, environnement et tmp | Aucun fichier correspondant, code 1 normal pour cette recherche |
| `.venv/bin/python -m pip install --no-cache-dir -e '.[dev]'` | Réinstallation éditable réussie, script console créé ; accès réseau autorisé pour le build |
| `.venv/bin/pytest` | **4 réussis, 0 échoué, 0 sauté**, en 0,06 s |
| `.venv/bin/python -m compileall -q forge_design` | Code 0, aucune erreur |
| `.venv/bin/ruff check forge_design tests` | `All checks passed!`, code 0 |
| `.venv/bin/pyright` | `0 errors, 0 warnings, 0 informations`, code 0 |
| `git diff --check` | Code 0 |
| `.venv/bin/forge-design --version` | `Forge Design 0.1.0.dev0`, code 0 |
| `git add README.md pyproject.toml forge_design/cli.py tests/test_cli.py` | Quatre fichiers indexés |
| `git diff --cached --check` | Code 0 |
| `git diff --cached` | Diff intégral inspecté, périmètre respecté |
| `git commit -m "feat: ajouter la CLI minimale (FD-FOUNDATION-003)"` | Commit `c0a8d0f`, quatre fichiers, 75 insertions |
| `git status --short --branch` et `git rev-parse HEAD` | Arbre propre, `main` en avance d'un commit sur `origin/main` |

Environnement : Python 3.13.5, pytest 9.1.1, Ruff 0.16.9, Pyright 1.1.414.

## Tests sautés

Aucun. Aucun échec de test ou de validation.

## Limites restantes

- Exécution validée sous Python 3.13.5 ; Python 3.12 n'a pas été exécuté.
- Commande vérifiée dans l'installation éditable du projet. Pas de nouvelle vérification de wheel pour ce ticket.
- Seules la version et l'aide sont disponibles. Serveur, navigateur, Bridge, Inspector, Platform, Tools, configuration et accès aux projets Forge restent hors périmètre.

## État Git final

Arbre de travail propre. Commit local `c0a8d0f` sur `main`, un commit d'avance sur la référence locale `origin/main`. Aucun push effectué pour ce ticket. Rapport conservé dans `tmp/`, ignoré par Git.
