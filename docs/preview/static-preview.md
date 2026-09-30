# Prévisualisation statique — données fictives

FD-PREVIEW-001 prépare un contexte Python sérialisable JSON depuis un ViewContract
validé. Il ne rend pas de HTML ; le renderer local appartient à FD-PREVIEW-002.

```python
from forge_design.preview import generate_preview_data

result = generate_preview_data(contract)
# result.data : dictionnaire fictif ; result.issues : tuple ; result.complete : bool
```

## Valeurs fixes

| Type | Valeur preview |
|---|---|
| string | `"Exemple"` |
| boolean | `true` |
| integer | `42` |
| number | `12.5` |
| object | Objet construit depuis fields, sinon `{}` |
| list | Trois objets construits depuis fields, sinon `[{}, {}, {}]` |
| email (field) | `"contact@example.test"` |
| date (field) | `"2026-05-16"` |

42 et 12.5 sont des conventions explicites. La date est l'exemple fixe du cadrage,
jamais la date courante. Email/date sont des chaînes. Aucun hasard, Faker, UUID,
datetime Python ou Decimal. Les types bool/int/float restent distincts.

## Objets et listes

ViewContextVariable.fields est l'unique source des propriétés fictives pour object
et list. Fields absent ou vide est valide. L'ordre du contexte et des champs est
préservé exactement, sans tri, normalisation Unicode ou transformation des noms.
Les métadonnées label/entity et actions sont ignorées ; aucun nom de champ n'est
inféré depuis une entité réelle. Les éventuels fields sur un scalaire top-level
n'interviennent pas dans la génération de sa valeur.

Les types de champs supportés sont exactement string, boolean, integer, number,
email, date, object et list. Un champ object donne un nouveau `{}`, un champ list
un nouveau `[]` : fields ne décrit pas de structure récursive. Ce dernier cas est
distinct de la variable top-level list, qui produit toujours trois objets.

Les trois objets d'une liste ont des valeurs égales mais des identités distinctes,
y compris leurs conteneurs de champs. Aucun partage mutable entre lignes,
variables ou appels. Modifier les données retournées n'affecte pas le contrat
ni les prochaines générations.

## Types inconnus et complétude

Un type de champ non supporté, tel que money, uuid, image ou une chaîne Unicode
inconnue, est omis. Aucun None ou contenu arbitraire n'est injecté. Une issue
preview.unsupported_field_type est produite par définition de champ, pas trois
fois pour les instances d'une liste. Location :
("context", "contacts", "fields", "avatar"). Les issues suivent l'ordre déclaré.

Le parent reste présent avec les seuls champs générables. complete=False si un
champ est omis ; sinon complete=True. Un contexte vide donne data={}, issues=()
et complete=True. Il n'y a aucune erreur pour label/entity/actions/fields absents.

PreviewDataResult et PreviewDataIssue sont des dataclasses gelées ; issues est un
tuple. **Le gel reste superficiel** : data contient des dicts/listes ordinaires,
mutables pour le futur renderer. Le même contrat inchangé produit toujours les
mêmes valeurs, ordre, diagnostics et complétude.

## Portée et limites

Aucun DesignFile, binding, rendu HTML/Jinja, route, backend Forge, DB, réseau,
subprocess, filesystem ou contexte Web n'est consulté. Aucune mutation du contrat,
revalidation Pydantic ou résolution d'entité. L'entrée doit conserver son contrat
structurel validé ; les mutations arbitraires ou concurrentes ne sont pas prises
en charge.

Complexité O(V+F), avec facteur fixe trois pour les objets de liste. Pas de récursion
métier ni de nouveau plafond : temps, mémoire et nombre de diagnostics suivent la
taille du contrat en mémoire fourni. Le lecteur de contrat garde ses propres bornes,
mais un contrat synthétique peut être beaucoup plus grand.

Les booléens sont toujours True, les listes top-level toujours non vides : ce jeu
nominal n'exerce ni les branches False ni les empty_state d'une future preview.
Aucune variante de scénario n'est ajoutée. FD-PREVIEW-002 consommera ces données
pour le rendu local ; ce ticket ne crée aucune route, page ou Tool.
