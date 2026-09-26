# Rapport — FD-PLATFORM-001

## Ticket et objectif

Extraire de Project Inspector un contrat Tool minimal : identité, description, entrée projet, exécution synchrone et résultat typé.
Le ticket n'introduit ni registre ni système de plugins.

## État Git initial

- Branche : `main`, synchronisée avec `origin/main`.
- HEAD : `b072d88` — `feat: ajouter Project Inspector minimal (FD-INSPECTOR-001)`.
- Aucun changement de fichier suivi.
- Quatre rapports historiques non suivis : `FD-FORGE-002.md`, `RAPPORT_FD-FORGE-001.md`, `RAPPORT_FD-FOUNDATION-002.md`, `RAPPORT_FD-FOUNDATION-003.md`, dans `docs/rapports/`.
- `git status` et `git log --oneline --decorate -5` exécutés avant modification.

## Besoins extraits de Project Inspector

- Identité technique stable : `project-inspector`.
- Nom d'affichage : `Project Inspector`.
- Responsabilité courte, sans métadonnées de présentation supplémentaires.
- Entrée projet explicite sous forme de `Path`.
- Appel synchrone en lecture seule.
- Résultat métier `ProjectInspection` préservé.
- Erreurs de l'API métier propagées sans transformation générique.

## Contrat retenu

Un `Protocol` générique avec résultat covariant, trois propriétés en lecture seule et une méthode :

```python
class Tool(Protocol[Result_co]):
    @property
    def id(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    def run(self, project_root: Path) -> Result_co: ...
```

Le paramètre de résultat préserve le typage spécifique sans créer de `ToolResult` ou autre enveloppe.
La covariance convient à un type uniquement retourné.
Le protocole est structurel : aucun héritage requis pour l'implémentation ni pour un faux Tool.
La conformité est vérifiée par Pyright sur des fonctions consommatrices explicitement typées.
Aucun `runtime_checkable` n'est nécessaire : un test de présence d'attributs à l'exécution ne vérifierait pas les signatures ni la sémantique.

L'identifiant doit être stable et en kebab-case.
La lecture seule et la conservation des erreurs sont documentées comme obligations des implémentations.
Le protocole ne constitue ni une sandbox ni un validateur de métadonnées.
La racine n'est pas nécessairement canonique à l'entrée : l'implémentation réutilise le Bridge pour la résoudre.

## Alternatives étudiées

| Alternative | Décision |
|---|---|
| Classe abstraite | Héritage et hiérarchie inutiles pour ce seul cas ; écartée |
| Dataclass contenant un callable | Possible, mais nécessiterait de transporter le callable dans une enveloppe ; non nécessaire pour une simple méthode de délégation |
| Retour `object` | Minimal, mais ferait perdre le type `ProjectInspection` aux consommateurs ; remplacé par un paramètre de type |
| Résultat universel ou contexte d'exécution | Aucun besoin observé ; non introduit |
| Validation dynamique du protocole | Aucun consommateur ne la nécessite ; vérification statique retenue |

## Fichiers créés

- [forge_design/platform/__init__.py](../../forge_design/platform/__init__.py)
- [forge_design/platform/tool.py](../../forge_design/platform/tool.py)
- [tests/test_tool.py](../../tests/test_tool.py)
- [docs/rapports/FD-PLATFORM-001.md](FD-PLATFORM-001.md)

## Fichiers modifiés

- [forge_design/tools/project_inspector.py](../../forge_design/tools/project_inspector.py) : ajout de l'adaptateur.
- [forge_design/tools/__init__.py](../../forge_design/tools/__init__.py) : description du paquet actualisée.
- [pyproject.toml](../../pyproject.toml) : ajout de `forge_design.platform` aux paquets distribués.
- [docs/02-architecture.md](../02-architecture.md) : description ciblée du contrat réellement implémenté.

Aucune modification du Bridge ou de Forge Core et aucune nouvelle dépendance.
Les rapports historiques non suivis restent hors du commit.

## API ajoutée

```python
from pathlib import Path
from forge_design.platform.tool import Tool
from forge_design.tools.project_inspector import ProjectInspection, ProjectInspectorTool

tool: Tool[ProjectInspection] = ProjectInspectorTool()
result: ProjectInspection = tool.run(Path("mon-projet"))
```

Métadonnées de `ProjectInspectorTool` :

```text
id          project-inspector
name        Project Inspector
description Reconnaître un projet Forge et lire sa version déclarée.
```

## Adaptation de Project Inspector

`ProjectInspectorTool` est une petite dataclass gelée.
Ses trois champs de métadonnées utilisent `init=False` : ils ne sont pas paramétrables à la construction.
Sa méthode `run` contient uniquement `return inspect_project(project_root)`.
La fonction métier, le résultat `ProjectInspection`, les appels au Bridge et leurs diagnostics sont inchangés.
Aucune logique de parsing ou de résolution de chemin n'est dupliquée dans l'adaptateur ou la Platform.
Aucun service supplémentaire n'est requis, donc aucune infrastructure d'injection n'est créée.

## Tests ajoutés

9 cas couvrent :

- conformité statique de Project Inspector à `Tool[ProjectInspection]` et métadonnées exactes ;
- immutabilité des trois métadonnées ;
- égalité du résultat via le contrat et via l'API métier, pour des projets valide et invalide ;
- délégation unique à l'API métier, retour du même objet et transmission du chemin sans validation supplémentaire ;
- propagation d'une erreur de racine ;
- faux Tool minimal sans héritage retournant une chaîne via `Tool[str]`.

Les assertions de type sont contrôlées par Pyright.
Les tests Inspector et Bridge existants continuent de vérifier le comportement métier, notamment la lecture seule.

## Commandes exécutées et résultats

Les validations utilisent les exécutables de `.venv` via `PATH`.

| Commande | Résultat |
|---|---|
| `git status` | État initial inspecté |
| `git log --oneline --decorate -5` | Historique initial inspecté |
| `pytest` | 112 tests réussis, dont 9 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |

Le diff du ticket est relu avant le commit ; le rapport est inclus avec le code.

## Tests sautés

Aucun test pytest sauté.
Aucune génération Forge, intégration réseau ou construction de wheel n'est nécessaire ni revendiquée pour ce contrat Python.

## Limites restantes

- Le contrat s'appuie sur un seul Tool métier réel ; une généralisation supplémentaire attendra un deuxième cas réel.
- Les obligations de lecture seule et de convention d'identifiant ne sont pas contrôlées automatiquement par le protocole.
- La conformité est statique et ne remplace pas les tests métier.
- Les limites et exceptions du Bridge sont conservées par l'adaptateur.
- Aucun registre, plugin externe, contexte, rendu ou interface n'est ajouté.

## État Git final

Livraison sur `main` dans un seul commit local contenant ce rapport :
`feat: définir le contrat Tool minimal (FD-PLATFORM-001)`.
Aucun push effectué.
Les quatre rapports historiques initialement non suivis restent non suivis.
Le hash et l'état final vérifié sont communiqués dans la réponse de livraison.

Pour retrouver le commit du ticket :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-PLATFORM-001.md
```
