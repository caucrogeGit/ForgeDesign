# Bindings simples — FD-BINDING-001

Un binding relie un bloc Design à un nom déclaré dans un ViewContract fourni
explicitement. La validation est pure et indépendante des fichiers et du nesting.

```python
from forge_design.design import DesignFile, validate_design_bindings
from forge_design.contracts import ViewContract

design = DesignFile.model_validate(design_data)
contract = ViewContract.model_validate(contract_data)
result = validate_design_bindings(design, contract)
# result.valid, result.issues, result.truncated
```

## Sémantique v0.1

| Bloc | Namespace | Type requis |
|---|---|---|
| title, text | context | string |
| table | context | list |
| button | actions | Nom d'action présent |
| page, section, container, grid, card | Aucun | Binding non supporté |
| form, field | Reporté | Binding non supporté |
| alert, empty_state | Aucun | Binding non supporté |

Le format ne possède ni bloc condition ni champ action dédié. Pour représenter
l'exemple « Button → action create », **button.binding="create" désigne actions.create**.
Cette sémantique propre au bouton pourra évoluer avec un futur champ action.
Aucune syntaxe action:create, @create ou actions.create n'est interprétée : de tels
noms ne fonctionnent que comme clés littérales présentes dans le namespace choisi.

La recherche utilise les dictionnaires context/actions existants, sans reconstruire
d'index. Homonymes autorisés : button cherche uniquement actions, text uniquement
context. Actions absent ou vide donne unknown_action pour tout binding de bouton.
Aucune vérification de method, path, csrf ou route réelle. Pour les variables,
égalité exacte du type : aucune conversion de boolean/integer/number/object/list
en string pour text/title. Une table attend seulement list ; entity et fields
n'interviennent pas encore.

Un binding absent est accepté sur tous les types. Un binding présent sur un type
sans sémantique v0.1 produit unsupported, même si le nom existe dans le contrat.
Les props ne changent jamais la règle. Les noms sont comparés exactement : pas de
strip, casefold, normalisation Unicode ni découpage sur point, slash, deux-points
ou crochets. contact.email cherche une clé littérale ; aucune navigation de champ.

## Résultat et diagnostics

DesignBindingResult et DesignBindingIssue sont des dataclasses gelées ; issues
est un tuple. Une erreur ordinaire au maximum par occurrence de nœud.

| Code | Sens |
|---|---|
| design.binding.unknown_variable | Nom absent de context |
| design.binding.unknown_action | Nom absent de actions |
| design.binding.type_mismatch | Type déclaré différent du type requis |
| design.binding.unsupported | Binding sur un bloc sans sémantique définie |
| design.binding.analysis_truncated | Analyse interrompue par une borne |

Chaque issue expose message humain, location, node_type et binding. Une erreur
ordinaire vise le champ binding : ("root", "children", 0, "binding"). Le binding
racine est unsupported à ("root", "binding"). Le marqueur de troncature vise le
nœud qui déclenche l'arrêt, sans suffixe binding ; binding peut alors être None
si aucun binding n'est présent. Aucun binding artificiel n'est inventé.

## Parcours et bornes

Parcours préfixe itératif par pile d'itérateurs, racine comprise, sans copie des
listes ni model_dump. Les occurrences partagées sont analysées à chaque chemin.
Les erreurs suivent l'ordre source ; aucun tri ni dédoublonnage.

| Limite existante | Sémantique |
|---|---|
| MAX_DESIGN_NODES = 4096 | Racine comprise |
| MAX_DESIGN_DEPTH = 128 | Racine à profondeur zéro |
| MAX_DESIGN_ISSUES = 512 | Marqueur terminal compris |

Une borne exactement atteinte sans surplus ne tronque pas. Au premier surplus,
l'analyse s'arrête avec un marqueur terminal unique, truncated=True et valid=False.
Si 512 erreurs existent déjà, la dernière est remplacée par le marqueur ; les
511 premières restent présentes. Sans surplus, les 512 erreurs sont conservées.
Priorité des bornes simultanées : nœuds, profondeur, issues. Une référence de nœud
supplémentaire peut être consommée pour détecter le surplus.

valid=True signifie absence d'erreur de binding et analyse complète uniquement.
Un cycle introduit dans les listes mutables s'arrête à une borne. Coût O(N) pour
les occurrences inspectées à profondeur bornée, recherches dictionnaire O(1) moyen.
Les modèles doivent conserver leurs types structurels ; pas de réparation des
mutations arbitraires ni de garantie en cas de modification concurrente.

## Responsabilités reportées

- Colonnes et champs : FD-BINDING-002. columns[].binding n'est pas parcouru ; aucune
  issue unknown_field, même pour une colonne inconnue sur une table correctement liée.
- Conditions : FD-BINDING-003, avec représentation explicite à définir. Aucun
  condition, visible_if ou comportement déduit de props n'est ajouté.
- Formulaires : aucune action de formulaire n'est représentée aujourd'hui ; form
  et field avec binding restent unsupported.

Pydantic, nesting et bindings restent composables. Cette fonction ne relance aucun
autre validateur, ne lit aucun design/contrat et ne vérifie ni source_contract,
ni design.view == contract.name. Aucun objet ou conteneur d'entrée n'est modifié.
Aucun Web, Tool, génération ou accès projet. Le [format Design](design-json.md)
et le contrat conservent leurs schémas et modèles actuels.
