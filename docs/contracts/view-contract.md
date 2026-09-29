# Contrat de vue minimal

Le contrat décrit ce que la vue est autorisée à utiliser. Le contrôleur produit
les données. Le template les utilise. Forge Design ne déplace pas la logique métier
dans le contrat. Cette déclaration ne constitue pas un mécanisme de contrôle d'accès.

```text
Backend Forge / Controller
            ↓ données préparées
View Contract (.view.json)
            ↓ description
Forge Design / Template
```

## Source normative et convention

Le [schéma produit](../../forge_design/contracts/view_contract.schema.json) est la
seule source normative : JSON Schema Draft 2020-12, distribué dans le package
`forge_design.contracts` sous le nom `view_contract.schema.json`. Aucun `$id`
prétendument publié n'est déclaré. Le format est en construction ; un mécanisme
de version pourra être défini avant stabilisation publique. Aucun `schema_version`
n'est admis dans cette version minimale.

Convention future : `mvc/views/<vue>.view.json` à côté de `mvc/views/<vue>.html`.
Par exemple `mvc/views/contacts/list.view.json` et `mvc/views/contacts/list.html`.
Le nom logique `contacts/list` et le chemin physique du template sont explicitement
renseignés, jamais déduits silencieusement l'un de l'autre. Le schéma ne contrôle
ni leur concordance avec le nom du fichier, ni l'existence des fichiers.

## Racine

| Champ | Présence | Signification |
|---|---|---|
| name | Obligatoire | Identité logique, chaîne de 1 à 256 caractères |
| template | Obligatoire | Chemin relatif au projet, chaîne bornée à 4096 caractères, préfixe mvc/views/ et suffixe non vide |
| context | Obligatoire | Objet des variables exposées, éventuellement vide |
| actions | Optionnel | Objet des actions proposées, éventuellement vide |

Racine stricte : toute autre propriété est refusée structurellement. Les longueurs
comptent les caractères JSON, pas les octets. Aucun trim, normalisation Unicode ou
regex Python n'est imposé aux noms. Un nom non vide n'est pas nécessairement un
identifiant Jinja utilisable avec la notation pointée.
Le préfixe du template est une convention légère, pas la politique `source_parts` :
traversal, symlinks, noms sensibles, taille réelle et existence seront contrôlés par
le futur lecteur sécurisé. Une conformité au schéma ne permet jamais d'ouvrir un chemin.

## Variables de contexte

Chaque clé non vide de `context` nomme un objet `ContextVariable` strict :
`type` obligatoire ; `label`, `entity` et `fields` optionnels.

| Type | Donnée décrite |
|---|---|
| string | Texte |
| boolean | Booléen |
| integer | Entier |
| number | Nombre |
| object | Objet |
| list | Liste |

Ce vocabulaire décrit la donnée attendue, sans embarquer sa valeur réelle.
`label` est un libellé humain, éventuellement vide, destiné à Forge Design.
`entity` est un nom d'entité non vide, sans résolution vers Entity Explorer ; il
peut accompagner notamment une liste ou un objet. Aucune condition entre `type`
et `entity`/`fields` n'est imposée dans ce schéma structurel.

`fields` associe un nom de champ non vide à une chaîne de type non vide. Son
vocabulaire est libre : `email` y est permis, alors qu'il n'est pas un type principal
de variable. Aucun contrôle d'existence ou de compatibilité des champs Forge.
Aucun sous-modèle complexe de champ ni schéma d'élément de liste dans ce ticket.
`can_create` décrit un booléen fourni par le backend, jamais une permission calculée
par le contrat.

## Actions

Chaque clé non vide d'`actions` nomme un objet `ViewAction` strict :
`method` et `path` obligatoires, `csrf` optionnel.
`method` utilise le motif léger `^[A-Z]+$`, sans liste de méthodes du Router.
`path` est une chaîne non vide ; `/contacts/{id}/edit` reste du texte, sans
interprétation ni substitution de `{id}`, ni vérification avec Route Explorer.
`csrf` est un booléen déclaratif. Son absence ne signifie ni false ni true ; aucune
valeur par défaut ou protection effective n'est mise en œuvre par le schéma.

## Exemples officiels

Les fichiers JSON documentaires sont versionnés dans Forge Design, jamais écrits
dans un projet cible. Ces blocs restent synchronisés avec les fixtures par tests.

[Minimal](../../tests/fixtures/contracts/minimal.view.json) :

```json
{
  "name": "home/index",
  "template": "mvc/views/home/index.html",
  "context": {}
}
```

[Contacts](../../tests/fixtures/contracts/contacts-list.view.json), extension de
l'exemple normatif avec champs exposés et action POST :

```json
{
  "name": "contacts/list",
  "template": "mvc/views/contacts/list.html",
  "context": {
    "page_title": {"type": "string", "label": "Titre de page"},
    "contacts": {
      "type": "list",
      "entity": "Contact",
      "fields": {"nom": "string", "email": "email", "telephone": "string"}
    },
    "can_create": {"type": "boolean", "label": "Peut créer un contact"}
  },
  "actions": {
    "create": {"method": "GET", "path": "/contacts/create"},
    "save": {"method": "POST", "path": "/contacts", "csrf": true}
  }
}
```

## Séparation des responsabilités

| Élément | Responsabilité |
|---|---|
| Contrôleur | Produire les données et appliquer la logique métier |
| Entity JSON | Décrire la structure métier persistée |
| .view.json | Décrire ce que la page peut utiliser |
| .design.json futur | Décrire comment la page est composée |
| Route | Définir comment atteindre le contrôleur |
| Action du contrat | Décrire une action que la vue peut proposer |

Le contrat ne contient ni SQL, Python, Jinja exécutable, callback, condition métier,
permission calculée ou base de données parallèle. Il ne configure ni Tailwind,
classes, layout, positions, couleurs ou blocs graphiques. Les propriétés telles
que `source`, `visible_if`, `design`, `metadata`, `states` ou `permissions` ne font
pas partie du format minimal. Les chaînes déclaratives ne sont jamais exécutées ;
le schéma n'analyse pas leur contenu pour y détecter du code.

## Responsabilités reportées

FD-CONTRACT-001 fournit seulement le schéma packagé et sa documentation. Aucun
validateur Python, Pydantic, helper runtime, nouveau Tool ou endpoint Web.
Les tests standard vérifient les déclarations du schéma et les exemples par des
assertions ciblées ; ils ne sont pas un moteur JSON Schema et ne prouvent pas une
validation complète d'instances. Les cas invalides illustrent les contraintes
déclarées sans prétendre avoir été rejetés par un moteur.

```text
JSON Schema — FD-CONTRACT-001
    ↓
Modèles Pydantic — FD-CONTRACT-002
    ↓
Lecteur filesystem sécurisé — FD-CONTRACT-003
```

La validation des instances en mémoire est maintenant assurée par les modèles
du ticket 002 décrits ci-dessous.
Le scan des contrats et les garanties filesystem appartiennent au ticket 003.
L'affichage, la comparaison aux templates, les croisements template/entités/actions,
le rendu et la génération restent futurs. Aucun contrat n'est chargé comme tel par
l'application actuelle ; Template Viewer garde son inventaire générique de fichiers.


## Modèles Python — FD-CONTRACT-002

Pydantic v2 (`pydantic>=2,<3`) fournit la validation en mémoire. Le schéma JSON
packagé reste normatif et inchangé ; les modèles ne lisent aucun fichier projet.
API exportée : `ViewContract`, `ViewContextVariable`, `ViewAction`, `ViewValueType`.
Le vocabulaire Literal reste string/boolean/integer/number/object/list.

```python
from forge_design.contracts import ViewContract

data = {"name": "home/index", "template": "mvc/views/home/index.html", "context": {}}
contract = ViewContract.model_validate(data)
contract = ViewContract.model_validate_json(text)  # JSON déjà disponible en mémoire
payload = contract.model_dump(exclude_unset=True)
text = contract.model_dump_json(exclude_unset=True)
```

Mode strict, propriétés inconnues refusées, aucune coercition volontaire : `1`
ou `"true"` ne deviennent pas un booléen CSRF, et un nombre ne devient pas un label.
Noms, espaces, Unicode et chemins ne sont ni normalisés ni nettoyés. Les clés des
objets context/actions/fields et les valeurs de fields doivent être des chaînes
non vides ; espace, tiret ou emoji sont permis. Aucun contrôle croisé métier.

Les attributs facultatifs absents valent `None` dans l'API Python, mais un `null`
explicitement fourni est refusé pour label/entity/fields/actions/csrf. Un validator
avant validation distingue les valeurs fournies du défaut interne non validé.
`model_fields_set` conserve les présences. La personnalisation du schéma généré
retire la branche null et le défaut interne, sans changer le schéma normatif.
Cette technique utilise les [validators Pydantic v2](https://docs.pydantic.dev/latest/concepts/validators/)
et la [personnalisation du schéma](https://docs.pydantic.dev/latest/concepts/json_schema/).

Utiliser **exclude_unset=True** pour exporter un contrat : aucun null artificiel,
label vide et actions vide préservés, structure revalidable. Un dump sans cette
option peut contenir les None internes et n'est pas un document conforme à exporter.
`ValidationError.errors()` fournit les chemins (`context.contacts.type`,
`actions.save.csrf`) et codes d'erreur ; aucun texte anglais complet n'est figé.
Un JSON mal formé produit également ValidationError.

Les attributs des trois modèles sont frozen. Les mappings restent des dicts Python
mutables, copiés lors de la validation de dictionnaires : ce n'est pas une immutabilité
profonde. Une mutation de dict n'est pas validée automatiquement ; revalider le dump
après modification. Les API Pydantic de confiance `model_construct`, `model_copy(update=...)`
ou les options qui désactivent la validation stricte ne sont pas des entrées de
validation du format. Revalider une instance déjà construite n'assure pas non plus
le contrôle des mutations internes : revalider ses données sérialisées.

Les types number/integer décrivent les données backend, sans valider leur valeur
réelle ici. Le template `mvc/views/../secret.html` peut être structurellement admis :
le lecteur sécurisé FD-CONTRACT-003 devra appliquer sa politique avant toute ouverture.
Aucune résolution filesystem, Entity/Route, vérification CSRF effective, UI ou Tool.
