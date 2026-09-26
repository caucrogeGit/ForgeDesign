# Rapport — FD-FORGE-003

## Ticket et objectif

FD-FORGE-003 — Lire la version Forge déclarée par un projet reconnu et identifier sa source, sans exécuter le projet ni décider de sa compatibilité.

- Branche : `main`.
- Commit : commit contenant ce rapport, intitulé `feat: lire la version Forge (FD-FORGE-003)`.
- Pour retrouver son identifiant : `git log -1 --format=%H -- docs/rapports/FD-FORGE-003.md`.
- État initial : `main` synchronisée avec `origin/main`, HEAD `8c5a2a7` ; rapports précédents non suivis dans `docs/rapports/`.

## Sources de version étudiées

Forge `main` a été vérifié avec `git ls-remote https://github.com/caucrogeGit/Forge.git refs/heads/main`.
Le résultat correspond au dépôt local inspecté : `73a956e587e5f169c028415e0e540c149cbaff56`.

| Source étudiée | Constat et décision |
|---|---|
| [`skeleton/data/requirements.txt`](https://github.com/caucrogeGit/Forge/blob/73a956e587e5f169c028415e0e540c149cbaff56/skeleton/data/requirements.txt) | Déclare `forge-mvc==1.0.0rc9` ; source retenue |
| `skeleton/data/pyproject.toml` | Configuration des outils, sans `[project]` ; exclu |
| `skeleton/data/app.py` | Mention de version dans la documentation du fichier ; pas un contrat de dépendance, exclu |
| `skeleton/data/bootstrap.py`, `config.py` | Pas de déclaration de version du framework à retenir |
| `forge.py`, création officielle | Matérialise le squelette ; peut adapter la dépendance selon la provenance de l'installation |
| `cli/project/install_source.py` | Une installation Git du CLI remplace le pin par `forge-mvc @ git+…@commit` ; aucune version de distribution ne doit être déduite du commit |
| `forge --version` | Affiche la version du CLI exécuté, pas celle déclarée par un projet précis ; commande non exécutée |

Le lecteur ne consulte ni le Forge global ni les métadonnées d'une installation dans `.venv`.
En mode `FORGE_DEV_SRC`, la version installée peut différer de celle déclarée dans le fichier : le ticket porte uniquement sur cette dernière.

## Source retenue et ordre de priorité

Une seule source officielle : `requirements.txt` à la racine canonique du projet.
Aucun ordre de priorité entre fichiers et aucun fallback.
Les tests multi-fichiers sont donc remplacés par des tests de déclarations multiples au sein de cette source.
Un test vérifie aussi qu'une version différente dans `pyproject.toml` n'est pas consultée.

Les exigences sont analysées avec `packaging`, ajouté comme dépendance explicite (`packaging>=24.0`).
Un pin `==` exact, sans joker ni condition, fournit une version normalisée PEP 440.
Les préversions et les variantes normalisées du nom `forge-mvc` sont acceptées.
Les dépendances des opt-ins, par exemple `forge-mvc-entities`, ne sont pas confondues avec le framework.

## Gestion des résultats et conflits

| Statut | Résultat |
|---|---|
| `found` | Version exacte, inconditionnelle et cohérente |
| `absent` | Source absente, déclaration absente ou version exacte non déterminable |
| `unreadable` | Accès impossible, format invalide, source refusée ou directive non prise en charge |
| `conflict` | Pins exacts contradictoires dans `requirements.txt` |

Seul `found` fournit `version`.
`source` vaut `requirements.txt`, sauf si le fichier est absent (`None`).
`details` explique les cas non résolus sans recopier le contenu du fichier.

Les doublons équivalents selon PEP 440 sont acceptés.
La première déclaration fournit la représentation normalisée ; ses spécificateurs sont triés pour un résultat déterministe.
L'ordre de décision est : erreur de lecture ou format, conflit de pins exacts, déclaration non résolue, version trouvée.
Une URL Git, une plage, un joker ou un marqueur conditionnel produit `absent`, même en présence d'un autre pin exact.
Les inclusions, contraintes externes, installations éditables et continuations de ligne produisent `unreadable` et ne sont jamais suivies.

## API ajoutée

```python
read_forge_version(root: str | PathLike[str]) -> ForgeVersionInfo
```

Dataclass gelée :

```python
status: Literal["found", "absent", "unreadable", "conflict"]
version: str | None
source: str | None
details: tuple[str, ...]
```

L'API appelle `resolve_project_root` et le détecteur existant.
Les exceptions de résolution restent propagées ; un projet non reconnu déclenche `NotForgeProjectError`.

La lecture UTF-8, avec BOM accepté, est limitée à 1 Mio.
Les liens symboliques et fichiers spéciaux sont refusés.
Le descripteur ouvert est vérifié avant lecture ; `O_NOFOLLOW` et `O_NONBLOCK` sont utilisés lorsqu'ils sont disponibles.
Aucun import du projet, sous-processus, accès réseau, scan général ou écriture n'est effectué par le lecteur.

## Fichiers créés

- [forge_design/forge/project_version.py](../../forge_design/forge/project_version.py)
- [tests/test_project_version.py](../../tests/test_project_version.py)
- [docs/rapports/FD-FORGE-003.md](FD-FORGE-003.md)

## Fichiers modifiés

- [pyproject.toml](../../pyproject.toml) : dépendance explicite `packaging`.
- [docs/04-compatibilite-forge.md](../04-compatibilite-forge.md) : contrat réel de source, résultats et limites de lecture.

Les rapports antérieurs non suivis sont conservés sans modification et exclus du commit.

## Tests ajoutés

43 cas couvrent : versions exactes et préversions, source absente, version absente, format invalide, doublons cohérents et contradictoires, noms normalisés, extras, commentaires, BOM, plages, URLs Git, marqueurs, inclusions refusées, liens et fichiers spéciaux, permissions, encodage, taille limite, racine invalide, racine liée, remplacement de la source avant ouverture, priorité des erreurs et absence de modification.

Le test de lecture restreinte vérifie que seul `requirements.txt` est ouvert, malgré la présence d'`app.py`, de `pyproject.toml` et de faux fichiers de secrets dans la fixture.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat |
|---|---|
| `git status --short --branch` et `git log --oneline -5` | État initial inspecté |
| `git ls-remote https://github.com/caucrogeGit/Forge.git refs/heads/main` | Commit distant identique à la référence locale inspectée |
| Inspection ciblée du squelette et du générateur Forge | Source de déclaration et cas Git confirmés |
| `pytest` | 87 tests réussis, aucun sauté |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |

Validation exécutée avec Python 3.13.5, pytest 9.1.1 et packaging 26.3 dans `.venv`.

Une lecture directe du squelette officiel local avec `read_forge_version('../Forge/skeleton/data')` retourne :

```python
ForgeVersionInfo(
    status="found",
    version="1.0.0rc9",
    source="requirements.txt",
    details=(),
)
```

Ce contrôle ne constitue pas une nouvelle intégration complète avec `forge new` ; aucune génération complète n'a été exécutée pour ce ticket.

## Limites restantes

- Version déclarée uniquement, pas version effectivement installée.
- Aucun arbitrage de compatibilité avec Forge Design.
- Une référence Git n'est pas convertie en version ; aucune consultation réseau.
- Ce lecteur n'est pas un interpréteur complet du format pip : inclusions, continuations et éditions locales restent hors contrat.
- La racine et ses parents doivent rester stables pendant l'appel ; les contrôles du fichier ne constituent pas une garantie générale contre les modifications concurrentes du système de fichiers.

## État Git de livraison

Le ticket est livré dans un commit local sur `main`, sans push.
Les rapports antérieurs déjà non suivis restent non suivis.
Le hash exact du commit et l'état final vérifié sont également communiqués dans la réponse de livraison.
