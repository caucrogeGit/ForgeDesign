# Rapport — FD-INSPECTOR-001

## Ticket et objectif

Créer Project Inspector, premier cas d’usage métier de Forge Design : identifier une racine canonique, reconnaître sa structure Forge et rapporter la version déclarée et sa source.
L’Inspector compose les trois API existantes du Bridge en lecture seule.
Il n’introduit ni contrat Tool générique, ni Platform, ni registre, ni interface ou commande CLI.

## État Git initial

- Branche : `main`, synchronisée avec `origin/main`.
- HEAD : `4ab23fc` — `feat: lire la version Forge (FD-FORGE-003)`.
- Répertoire de travail propre.
- `git status` et `git log --oneline --decorate -5` exécutés avant modification.

## Fichiers créés

- [forge_design/tools/__init__.py](../../forge_design/tools/__init__.py) : paquet des cas d’usage métier.
- [forge_design/tools/project_inspector.py](../../forge_design/tools/project_inspector.py) : composition du Bridge et résultat immuable.
- [tests/test_project_inspector.py](../../tests/test_project_inspector.py) : tests unitaires sur fixtures temporaires locales.
- [docs/rapports/FD-INSPECTOR-001.md](FD-INSPECTOR-001.md) : présent rapport, inclus dans le commit du ticket.

## Fichiers modifiés

- [pyproject.toml](../../pyproject.toml) : ajout de `forge_design.tools` à la liste explicite des paquets distribués.

Aucune modification du Bridge ni de ses contrats.

## API ajoutée

```python
from forge_design.tools.project_inspector import inspect_project

inspection = inspect_project(root)
```

Signature :

```python
inspect_project(root: str | PathLike[str]) -> ProjectInspection
```

Résultat sous forme de dataclass gelée :

```python
class ProjectInspection:
    root: Path
    valid: bool
    forge_version: str | None
    forge_version_source: str | None
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
```

## Choix techniques

1. `resolve_project_root` fournit la racine canonique ; ses exceptions restent propagées.
2. `detect_forge_project` fournit la validité structurelle, les erreurs et les avertissements.
3. Si la structure est invalide, l’Inspector retourne immédiatement ce diagnostic, avec version et source à `None`.
4. Si la structure est valide, `read_forge_version` fournit la version et la source ; aucun parsing de fichier n’est ajouté dans l’Inspector.

`valid` signifie exclusivement « structure reconnue ».
Les statuts de version sont traduits comme suit :

| Statut du Bridge | Effet dans l’Inspector |
|---|---|
| `found` | Version et source propagées, sans avertissement supplémentaire |
| `absent` | Avertissement « Version Forge absente ou indéterminable. » |
| `unreadable` | Avertissement « Version Forge illisible. » |
| `conflict` | Avertissement « Déclarations de version Forge contradictoires. » |

Les détails du Bridge sont conservés après cet avertissement.
Les avertissements structurels restent en premier, dans leur ordre d’origine.
Les erreurs structurelles ne sont pas reformulées.
Les problèmes de version ne changent pas `valid` et ne deviennent pas des erreurs structurelles.
La source retournée par le Bridge reste disponible même lorsqu’une version ne peut être déterminée.

Les exceptions inattendues ne sont pas interceptées : aucune capture générale ne masque les causes.
Les vérifications répétées par les API du Bridge sont conservées pour respecter leurs contrats publics ; aucune optimisation ne les contourne.
Le module ne décide pas de la compatibilité, ne lance aucune commande, ne lit aucun fichier directement et ne crée aucun artefact dans le projet.

## Tests ajoutés

16 cas unitaires avec `tmp_path` couvrent :

- projet valide avec version trouvée et résultat immuable ;
- fichier de version absent, déclaration absente et plage indéterminable ;
- avertissements structurels conservés ;
- projet invalide retourné comme diagnostic, sans appel au lecteur de version ;
- racine inexistante, racine fichier et résolution impossible ;
- versions contradictoires et format de version invalide ;
- source de version illisible car de type incorrect ;
- racine canonique propagée depuis un chemin relatif ou un lien ;
- version différente de Forge Design acceptée sans décision de compatibilité ;
- absence de modification, création ou suppression dans le projet ;
- propagation d’une exception inattendue du Bridge.

Les tests unitaires ne nécessitent ni Forge installé ni `forge new`.

## Commandes exécutées et résultats

Les commandes de validation utilisent les exécutables de `.venv` via `PATH`.

| Commande ou contrôle | Résultat |
|---|---|
| `git status` | État initial propre |
| `git log --oneline --decorate -5` | Historique initial vérifié |
| `pytest` | 103 tests réussis, dont 16 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |

Un contrôle séparé, hors de la suite standard, a été exécuté contre `../Forge/skeleton/data`.
La référence locale Forge est `73a956e587e5f169c028415e0e540c149cbaff56`, baseline `1.0.0rc9`.
Le chemin a été passé en argument au script de contrôle ; aucun chemin personnel n’est codé dans les tests.

Commande reproductible depuis la racine Forge Design, avec le chemin du squelette à adapter :

```bash
.venv/bin/python - ../Forge/skeleton/data <<'PY'
import sys
from forge_design.tools.project_inspector import inspect_project

result = inspect_project(sys.argv[1])
assert result.valid
assert result.forge_version == "1.0.0rc9"
assert result.forge_version_source == "requirements.txt"
assert result.errors == result.warnings == ()
print(result)
PY
```

Résultat : racine canonique du squelette, `valid=True`, `forge_version='1.0.0rc9'`, `forge_version_source='requirements.txt'`, aucune erreur ni avertissement.
Ce contrôle ne constitue pas une génération complète par `forge new`.

Une vérification préparatoire de disponibilité de `setuptools` dans `.venv` a échoué avec `ModuleNotFoundError`.
Aucun build de wheel n’a donc été exécuté ; la liste de paquets a été mise à jour et relue.
Cela n’affecte pas les cinq validations demandées, toutes réussies.

## Tests sautés

Aucun test pytest sauté.
Le contrôle sur squelette officiel a été exécuté séparément et ne dépend pas de la suite standard.
Aucun test de génération Forge ni build de distribution n’est revendiqué.

## Besoins observés pour le futur contrat Tool

| Sujet | Besoin observé |
|---|---|
| Entrée projet | Un chemin, résolu par le Bridge en racine canonique |
| Exécution | Une fonction métier synchrone suffit actuellement |
| Résultat | Un objet typé et immuable, avec diagnostics distincts et valeurs optionnelles |
| Erreurs | Distinguer exceptions de racine et diagnostics métier ; conserver les causes |
| Identité | Le module et la fonction identifient le cas d’usage ; aucun identifiant générique requis par son exécution |
| Métadonnées | Aucune métadonnée d’affichage, permission, catégorie ou découverte nécessaire à ce stade |
| Effets | Lecture seule, sans contexte Platform ni état persistant |

Un seul cas d’usage ne suffit pas à établir toutes les abstractions communes.
Ces observations pourront alimenter FD-PLATFORM-001 ; aucun contrat générique n’est implémenté ici.

## Limites restantes

- Le diagnostic hérite des limites du Bridge : reconnaissance structurelle et version déclarée, sans garantie d’exécutabilité ni de version installée.
- Aucun contrôle de compatibilité n’est effectué.
- Le système de fichiers doit rester stable pendant les contrôles successifs ; une modification concurrente peut laisser remonter une exception du Bridge.
- Le contrôle réel porte sur le squelette local de référence et non sur un nouveau projet généré.
- Le build du paquet n’a pas été vérifié dans cet environnement sans `setuptools`.

## État Git final

Livraison dans un seul commit local sur `main`, sans push, comprenant ce rapport et les quatre autres fichiers du ticket.
Message : `feat: ajouter Project Inspector minimal (FD-INSPECTOR-001)`.
Le répertoire de travail est vérifié après le commit ; son état exact et le hash sont communiqués dans la réponse de livraison.

Pour retrouver le commit contenant ce rapport :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-INSPECTOR-001.md
```
