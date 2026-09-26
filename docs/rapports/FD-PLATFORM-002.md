# Rapport — FD-PLATFORM-002

## Ticket et objectif

Créer un registre explicite et minimal des instances Tool intégrées : enregistrer, lister et retrouver par identifiant.
Aucun mécanisme de découverte, plugin ou composition finale n'est ajouté.

## État Git initial

- Branche : `main`, synchronisée avec `origin/main`.
- HEAD : `7df7ac0` — `docs: ajouter les rapports historiques Forge Design`.
- Répertoire de travail propre.
- `git status` et `git log --oneline --decorate -5` exécutés avant modification.

## Contrat du registre

`ToolRegistry` démarre vide et conserve les instances reçues explicitement.

- `register(tool)` ajoute une instance, sans l'exécuter.
- `get(tool_id)` retourne l'instance enregistrée, sans copie.
- `list()` retourne un tuple instantané dans l'ordre d'enregistrement.

L'ordre d'insertion est déterministe pour une même séquence d'enregistrements et ne requiert aucune option de tri.
Le tuple ne permet ni remplacement, ni ajout, ni suppression dans le registre.
Il reste inchangé après un enregistrement ultérieur ; les instances référencées ne sont pas copiées.
Chaque registre possède son propre dictionnaire privé.

## Gestion des identifiants

Une validation courte respecte la convention du contrat Tool :

```text
[a-z][a-z0-9]*(?:-[a-z0-9]+)*
```

Les identifiants commencent par une lettre ASCII minuscule ; les segments suivants peuvent contenir des lettres minuscules ou des chiffres, séparés par un seul tiret.
Un mot unique est accepté.
Les identifiants vides, espaces, majuscules, underscores, tirets isolés ou doublés sont refusés avec `ValueError` avant toute insertion.
Aucune normalisation silencieuse n'est effectuée.
L'identifiant est lu une fois lors de l'enregistrement ; sa stabilité ultérieure reste une obligation du contrat Tool.

## Gestion des doublons

`DuplicateToolError`, sous-classe de `ValueError`, signale un identifiant déjà présent.
L'instance originale n'est jamais remplacée et l'ordre est conservé.
Réenregistrer la même instance est également un doublon.

## Gestion d'un Tool inconnu

`get` lève `UnknownToolError`, sous-classe de `KeyError`, avec l'identifiant demandé dans les arguments de l'exception.
Ce choix rend l'absence explicite sans imposer un retour optionnel à chaque appelant.
Une recherche, même infructueuse, ne modifie pas le registre.

## Typage retenu

Le stockage et les retours utilisent `Tool[object]`.
La covariance existante permet d'accepter `Tool[ProjectInspection]` ou `Tool[str]` sans cast.
Un appel à `run` après récupération produit statiquement `object` : le registre hétérogène ne promet pas de conserver le résultat spécifique à partir d'une chaîne d'identifiant.
Les objets réels restent inchangés.
Aucun `Any`, cast dispersé, contexte ou enveloppe de résultat n'est ajouté.
La conformité des instances au protocole reste vérifiée statiquement, comme pour le contrat Tool existant.

## Fichiers créés

- [forge_design/platform/tool_registry.py](../../forge_design/platform/tool_registry.py)
- [tests/test_tool_registry.py](../../tests/test_tool_registry.py)
- [docs/rapports/FD-PLATFORM-002.md](FD-PLATFORM-002.md)

## Fichiers modifiés

- [docs/02-architecture.md](../02-architecture.md) : description du registre réellement implémenté et actualisation de la mention précédente de son absence.

Aucune modification du contrat Tool, de Project Inspector, du Bridge, du packaging ou des dépendances.
Le module est inclus dans le paquet `forge_design.platform` déjà déclaré.

## API ajoutée

```python
class ToolRegistry:
    def register(self, tool: Tool[object]) -> None: ...
    def get(self, tool_id: str) -> Tool[object]: ...
    def list(self) -> tuple[Tool[object], ...]: ...
```

Exemple d'assemblage explicite, exercé dans les tests uniquement :

```python
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.project_inspector import ProjectInspectorTool

registry = ToolRegistry()
registry.register(ProjectInspectorTool())
tool = registry.get("project-inspector")
```

Exceptions ajoutées : `DuplicateToolError` et `UnknownToolError`.
Aucun enregistrement automatique ni instance globale de registre.

## Tests ajoutés

21 cas couvrent :

- registre vide ;
- enregistrement, recherche et liste ;
- deux Tools et ordre d'insertion distinct de l'ordre alphabétique ;
- doublon de la même instance et doublon d'une autre instance, sans remplacement ;
- recherche inconnue ;
- dix formats d'identifiant invalides ;
- identifiants à un mot et contenant des chiffres ;
- tuple non modifiable et instantané indépendant des enregistrements ultérieurs ;
- Project Inspector et faux Tool utilisables après récupération ;
- absence d'exécution implicite ;
- indépendance entre registres.

Pyright vérifie les types `Tool[object]`, `tuple[Tool[object], ...]` et le résultat `object`.
Le test d'écriture interdite sur un tuple contient une suppression Pyright locale et ciblée, uniquement pour exercer cette erreur à l'exécution.

## Commandes exécutées et résultats

Les validations utilisent les exécutables de `.venv` via `PATH`.

| Commande | Résultat final |
|---|---|
| `git status` | État initial propre |
| `git log --oneline --decorate -5` | Historique initial inspecté |
| `pytest` | 133 tests réussis, dont 21 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |

La première exécution de Pyright a signalé l'affectation intentionnellement interdite au tuple : le code de diagnostic de la suppression locale a été corrigé (`reportIndexIssue`).
Les validations finales sont propres.
Le diff complet est inspecté avant le commit, rapport compris.

## Tests sautés

Aucun test pytest sauté.
Aucune génération Forge ou intégration réseau n'est nécessaire à ce registre ; aucune n'est revendiquée.

## Limites restantes

- Le registre ne garantit pas le type spécifique du résultat après recherche par identifiant.
- Les instances restent celles fournies par l'appelant ; le tuple protège la collection, pas les objets eux-mêmes.
- Un Tool doit respecter la stabilité de son identifiant après enregistrement.
- Aucun contrôle dynamique complet du protocole ni mécanisme de concurrence n'est ajouté.
- Le point de composition final, la découverte et les plugins restent hors périmètre.

## État Git final

Livraison dans un seul commit local sur `main`, rapport inclus, sans push.
Message : `feat: ajouter le registre des Tools (FD-PLATFORM-002)`.
Le hash et l'état Git vérifié après le commit sont communiqués dans la réponse de livraison.

Pour retrouver le commit contenant le rapport :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-PLATFORM-002.md
```
