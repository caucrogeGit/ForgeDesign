# Rapport — FD-PLATFORM-003

## Ticket et objectif

Ajouter un point de composition explicite construisant un registre indépendant contenant Project Inspector comme unique Tool intégré.
Aucun serveur, interface, configuration utilisateur ou découverte dynamique n'est ajouté.

## État Git initial

- Branche : `main`, synchronisée avec `origin/main`.
- HEAD : `0aeb21b` — `feat: ajouter le registre des Tools (FD-PLATFORM-002)`.
- Répertoire de travail propre.
- `git status` et `git log --oneline --decorate -5` exécutés avant modification.

## Point de composition retenu

`forge_design/app.py` contient `create_tool_registry()`.
Ce module d'application assemble les implémentations concrètes au-dessus de la Platform et des Tools.
Le choix des Tools intégrés ne relève ni du registre générique ni du Bridge.

## Composants assemblés

La fonction construit un `ToolRegistry`, crée un `ProjectInspectorTool`, l'enregistre explicitement et retourne le registre.
Le contrat `Tool` est réutilisé via la signature `ToolRegistry.register(Tool[object])` ; aucune duplication ni nouvel adaptateur n'est nécessaire.
La liste intégrée contient exactement `project-inspector`.

## Gestion de l'état

Le registre et le Tool sont créés à chaque appel.
Aucune instance n'est conservée au niveau module, aucun cache ni singleton n'est ajouté.
L'ajout d'un Tool à un registre retourné n'affecte ni les registres existants ni les compositions ultérieures.
La composition ne reçoit aucun chemin projet et n'exécute pas Project Inspector.

## Alternatives étudiées

- Assemblage dans `ToolRegistry` : écarté pour garder le registre indépendant des Tools concrets.
- Registre global : écarté pour éviter un état partagé entre appels.
- Module `composition.py` : possible, mais `app.py` suffit pour cet unique assemblage d'application.
- Infrastructure d'injection ou configuration : aucun besoin actuel ; non introduite.

## Fichiers créés

- [forge_design/app.py](../../forge_design/app.py)
- [tests/test_app.py](../../tests/test_app.py)
- [docs/rapports/FD-PLATFORM-003.md](FD-PLATFORM-003.md)

## Fichiers modifiés

- [docs/02-architecture.md](../02-architecture.md) : point de composition réellement disponible et lien depuis la section registre.

Aucune modification du contrat Tool, du registre, de Project Inspector, du Bridge ou des dépendances.
`app.py` appartient au paquet `forge_design` déjà déclaré ; aucun changement de packaging n'est requis.

## API ajoutée

```python
from forge_design.app import create_tool_registry

registry = create_tool_registry()
tool = registry.get("project-inspector")
```

Signature : `create_tool_registry() -> ToolRegistry`.
Le registre retourné conserve son API existante ; la composition ne rajoute aucune responsabilité.

## Tests ajoutés

Quatre tests regroupent les dix comportements demandés :

1. Construction d'un `ToolRegistry`, présence de l'identifiant exact `project-inspector`, liste contenant un seul Tool et récupération de la même instance par `get`.
2. Exécution réelle du Tool récupéré sur une fixture locale : racine canonique, structure valide, version `1.0.0rc9` et source `requirements.txt`.
3. Registres et instances distincts entre appels, ajout d'un faux Tool dans un seul registre et absence de contamination d'une composition ultérieure.
4. Absence d'exécution automatique : la méthode `run` et l'API métier sont remplacées par des fonctions qui échoueraient si elles étaient appelées durant la composition.

Le faux Tool reste exclusivement dans les tests.
Les tests existants continuent de couvrir les contrats du registre, du Tool et du Bridge.

## Commandes exécutées et résultats

Validations exécutées avec les outils de `.venv` via `PATH`.

| Commande | Résultat final |
|---|---|
| `git status` | État initial propre |
| `git log --oneline --decorate -5` | Historique initial inspecté |
| `pytest` | 137 tests réussis, dont 4 nouveaux tests |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |

Une ligne trop longue dans les tests a été corrigée après le premier passage de Ruff.
Le diff complet, rapport compris, est relu avant le commit.

## Tests sautés

Aucun test pytest sauté.
Aucune génération Forge, intégration réseau ou construction de distribution n'est revendiquée pour cet assemblage Python.

## Limites restantes

- Project Inspector est le seul Tool de production intégré.
- Le registre conserve l'effacement contrôlé du type de résultat en `object`.
- Le point de composition n'est pas relié à la CLI ou à un serveur.
- Les contrats et limites des composants assemblés restent inchangés.

## État Git final

Livraison sur `main` dans un seul commit local, rapport inclus, sans push.
Message : `feat: ajouter le point de composition (FD-PLATFORM-003)`.
Le hash et l'état Git vérifié après commit sont communiqués dans la réponse de livraison.

Pour retrouver le commit :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-PLATFORM-003.md
```
