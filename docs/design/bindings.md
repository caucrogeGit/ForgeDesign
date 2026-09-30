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

## Bindings de listes et tableaux — FD-BINDING-002

Cette étape complète les bindings simples avec la validation des colonnes. Les deux
fonctions restent indépendantes et se composent explicitement :

```python
from forge_design.design import validate_design_bindings, validate_table_bindings

simple = validate_design_bindings(design, contract)
tables = validate_table_bindings(design, contract)
# Une validation complète de ces deux étapes exige simple.valid et tables.valid.
```

Le validateur détaille toutes les occurrences table dans l'ordre préfixe, même si
le nesting est invalide. Il ne relance aucun autre validateur. Les autres blocs
sont parcourus uniquement pour trouver des tables et leurs enfants directs.
Une table sans binding n'est pas une erreur ; une référence inconnue ou non-list
reste diagnostiquée par FD-BINDING-001, sans cascade d'unknown_field ici.
Ainsi simple.valid=False et tables.valid=True est possible et intentionnel.

### Résolution et projection

TableBindingResult expose valid, tables, issues et truncated. Chaque TableBindingInfo
expose location du nœud, binding, entity informative, available_fields, columns,
status et has_empty_state. Les statuts sont :

| Status | Sens |
|---|---|
| no_binding | Aucun binding principal fourni |
| unresolved_variable | Nom absent du contexte |
| type_mismatch | Variable présente mais non-list |
| fields_unavailable | List résolue, structure de champs absente |
| resolved | List résolue et dictionnaire fields présent, même vide |

Seul ViewContextVariable.fields fournit les champs disponibles. Aucun accès à
l'entité désignée par entity, à Entity Explorer ou au filesystem. available_fields
conserve l'ordre du dictionnaire, sans tri. Les colonnes configurées conservent
index, label, binding, field_type et valid dans l'ordre du Design.

- fields absent : structure non décrite. Sans colonne, aucune erreur ; avec des
  colonnes, une seule issue design.table.fields_unavailable sur (..., "columns").
- fields={} : aucun champ déclaré. Chaque colonne configurée est inconnue.
- Champ présent : valid=True, field_type conserve la chaîne exacte, sans enum cachée.
- Champ absent du dictionnaire : valid=False, field_type=None et une issue
  design.table.unknown_field à (..., "columns", index, "binding").
- Collection non résolue, non-list, binding absent ou fields absent : colonnes
  projetées avec valid=None/field_type=None, car elles n'ont pas été validées.

Les labels sont visuels, sans effet sur la résolution. Aucun strip/casefold ou
normalisation Unicode. profile.email est une clé littérale ; aucune navigation.
Deux colonnes liées au même champ sont permises. Aucun type attendu n'existe dans
TableColumn : aucune compatibilité colonne/type supplémentaire n'est imposée.

### Suggestions non destructives

```python
from forge_design.design import suggest_table_columns

suggestions = suggest_table_columns(contract.context["contacts"])
```

La précondition est type=list ; sinon ValueError. Fields absent ou vide donne ().
Chaque SuggestedTableColumn gelée contient binding, field_type et label, ce dernier
égal au nom exact du champ. Ordre de déclaration conservé ; aucun title-case,
inférence depuis entity, création de TableColumn ou modification de DesignNode.columns.
Cette projection propose des choix en mémoire ; elle ne génère aucun fichier.

### État vide et bornes

has_empty_state=True si au moins un enfant **direct inspecté** est empty_state.
Aucun état vide obligatoire, aucune unicité et aucune sémantique de binding/content
ajoutée. Un état vide indirect ne compte pas. Le repérage utilise le parcours des
nœuds, pas une recherche indépendante dans tous les descendants.

MAX_DESIGN_NODES, MAX_DESIGN_DEPTH et MAX_DESIGN_ISSUES gardent leurs sémantiques
(racine comprise, profondeur zéro, marqueur terminal compris). MAX_TABLE_COLUMNS=512
borne les colonnes projetées/inspectées par occurrence, y compris lorsque la
collection n'est pas résolue. 512 sans surplus : pas de troncature ; 513 : arrêt
global avec design.table.analysis_truncated. Les budgets de nœuds/issues sont
globaux à l'appel ; le budget de colonnes est par table.

Un surplus produit un seul marqueur terminal, truncated=True et valid=False.
Si le budget de diagnostics est plein, le dernier est remplacé par le marqueur.
Les tables déjà découvertes, dont la table partiellement analysée, restent exposées.
En cas de troncature, les colonnes et états vides reflètent uniquement le préfixe
inspecté : has_empty_state=False ne prouve alors pas l'absence d'un enfant ultérieur.
Les locations de troncature pointent le nœud ou la colonne qui déclenche l'arrêt.

Parcours itératif par itérateurs, sans copie préalable de toutes les colonnes.
Coût O(N+C) pour les occurrences et colonnes inspectées, plus O(F) pour matérialiser
les noms disponibles des dictionnaires fields distincts rencontrés. Ces tuples
sont réutilisés entre tables partageant le même dictionnaire. Suggestions : O(F),
retour complet du contrat fourni. MAX_TABLE_COLUMNS borne les colonnes configurées,
pas les champs disponibles ni les suggestions ; leur taille suit le contrat.

Toutes les dataclasses de résultat sont gelées et leurs collections publiques sont
des tuples. Entrées inchangées, résultat déterministe sans mutation concurrente.
Aucun filesystem, route, pagination, filtre, condition, formulaire avancé, Web,
Tool ou génération HTML. Les bindings simples FD-BINDING-001 restent inchangés.
