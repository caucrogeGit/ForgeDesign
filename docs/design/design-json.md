# Format .design.json — v0.1

Le `.design.json` est la source graphique structurée et éditable de Forge Design.
Il décrit une composition lisible manuellement, sans devenir la source unique de
vérité d'un projet Forge. **Sa suppression ne doit jamais empêcher Forge d'utiliser
le template `.html` existant.** Le runtime Forge ne doit pas en dépendre.

| Fichier | Responsabilité |
|---|---|
| .view.json | Ce que la page peut utiliser : données disponibles |
| .design.json | Comment la page est composée : source éditable Forge Design |
| .html | Template final utilisable par Forge |

## Source normative et emplacement

Le [schéma produit](../../forge_design/design/design.schema.json) est l'unique
source normative, JSON Schema Draft 2020-12. Il est distribué dans
`forge_design.design/design.schema.json`, sans `$id` public fictif.
Convention physique : `mvc/views/<vue>.design.json`, par exemple
`mvc/views/contacts/list.design.json`, dans l'espace des vues du projet.
Aucune liaison réelle au template voisin n'est déduite ni effectuée ici.

## Racine stricte

| Propriété obligatoire | Contrat |
|---|---|
| version | Chaîne constante `"0.1"`, jamais nombre 0.1 |
| view | Identité logique, chaîne de 1 à 256 caractères, sans regex métier |
| source_contract | Référence relative à mvc/views, suffixe .view.json |
| root | Unique PageRoot, type page et children obligatoire |

Toutes les autres propriétés racine sont interdites, notamment template, roots,
metadata, editor, hash et generated_at. Les limites de chaînes comptent les
caractères, pas les octets. Aucun trim ou normalisation Unicode implicite.

`source_contract` est une chaîne non vide de 4096 caractères au plus, telle que
`contacts/list.view.json`, pas `mvc/views/contacts/list.view.json`.
Le motif de segments interdit slash initial, backslash, deux-points, segments vides
et CR/LF ; les exclusions légères refusent les segments `.`/`..`, le préfixe
mvc/views/ et un nom `.view.json` sans stem. Les espaces et Unicode sont permis.
Les motifs ne constituent pas une autorisation d'ouverture : noms sensibles,
liens, existence et confinement seront contrôlés par le lecteur FD-DESIGN-004.
Aucune copie de toute la politique source_parts dans le schéma.

## Nœuds

`DesignNode` est un objet strict. Seul `type` est obligatoire pour un descendant.
Vocabulaire exact : page, section, container, grid, card, title, text, button,
table, form, field, alert, empty_state.

`PageRoot` réutilise DesignNode via allOf et impose type=page ainsi que children.
Sa strictesse est héritée de DesignNode : aucune duplication de propriétés.
Dans cette première définition structurelle, un descendant page reste admis ;
FD-DESIGN-003 décidera les règles d'imbrication. Aucune règle Form→Field ou
Button→aucun enfant n'est anticipée.

| Champ facultatif du nœud | Déclaration |
|---|---|
| binding | Chaîne non vide, référence déclarative |
| visible_if | Chaîne non vide, référence booléenne de visibilité (FD-BINDING-003) |
| props | Objet à clés non vides, valeurs scalaires simples |
| columns | Tableau de TableColumn |
| children | Tableau récursif de DesignNode |

`children` et `columns` peuvent être vides. Une feuille n'a pas à déclarer children.
Aucune profondeur métier ni taille fichier n'est définie par ce schéma ; les futurs
modèles/lecteurs devront borner leur traitement. Aucun ID de bloc, action ou content
inventé dans cette version.

## Props, bindings et colonnes

PropValue autorise seulement string, boolean, integer et number (integer est un
sous-ensemble de number en JSON Schema). Absence représentée par omission : aucun
null, objet ou tableau imbriqué dans props. Les chaînes vides sont permises.
`class` et `tag` sont des chaînes explicites, pas un objet Tailwind ou style parallèle.
Aucun contrôle des propriétés propre à chaque type de bloc dans ce ticket.

Un binding comme `page_title` ou `contacts` nomme une donnée déclarative ; il ne
contient pas de Jinja à exécuter et ne déclenche aucune évaluation. Le schéma exige
seulement une chaîne non vide, sans parser son contenu ni vérifier son existence.
Ne pas écrire `{{ page_title }}` ou une expression métier. Depuis FD-BINDING-003,
visible_if est une référence déclarative distincte vers un boolean du contexte.
Les propriétés if/unless/condition restent hors du format.

TableColumn est strict : label et binding sont des chaînes non vides obligatoires.
Columns reste facultatif sur DesignNode, sans condition exigeant type=table.
Les futurs modèles/règles pourront affiner les propriétés, sans les anticiper ici.

## Exemples officiels

Les fixtures appartiennent uniquement au dépôt Forge Design ; aucun fichier n'est
créé dans un projet cible. Ordre conceptuel recommandé : version, view,
source_contract, root ; puis type, binding, visible_if, props, columns, children. L'ordre des
clés JSON n'a pas de signification fonctionnelle.

[Minimal](../../tests/fixtures/design/minimal.design.json) :

```json
{
  "version": "0.1",
  "view": "home/index",
  "source_contract": "home/index.view.json",
  "root": {
    "type": "page",
    "children": []
  }
}
```

[Contacts](../../tests/fixtures/design/contacts-list.design.json) :

```json
{
  "version": "0.1",
  "view": "contacts/list",
  "source_contract": "contacts/list.view.json",
  "root": {
    "type": "page",
    "children": [
      {
        "type": "section",
        "props": {
          "tag": "header",
          "class": "max-w-5xl mx-auto py-8"
        },
        "children": [
          {
            "type": "text",
            "binding": "page_title",
            "props": {
              "tag": "h1",
              "class": "text-3xl font-bold"
            }
          }
        ]
      },
      {
        "type": "table",
        "binding": "contacts",
        "props": {
          "class": "w-full border border-slate-200"
        },
        "columns": [
          {
            "label": "Nom",
            "binding": "nom"
          },
          {
            "label": "Email",
            "binding": "email"
          },
          {
            "label": "Téléphone",
            "binding": "telephone"
          }
        ]
      }
    ]
  }
}
```

## Données interdites et limites

Le document ne doit contenir ni secret/password/token/credential/session/API key,
ni données backend réelles, résultats SQL ou utilisateur courant. Aucun état runtime
(modal_open, selected_tab, csrf_token, flash_message), ni état opaque d'éditeur
(zoom, viewport, selection, drag_state, undo_stack, editor_cache).
Ces interdictions sont architecturales : aucune détection de secret ou de code dans
les chaînes libres n'est prétendue. Les clés non prévues sont refusées aux niveaux
racine/nœud/colonne, mais props ne filtre pas sémantiquement tous les noms possibles.
Aucune logique métier, condition exécutable, génération ou dépendance runtime Forge.

## Responsabilités futures

```text
ViewContract + DesignFile
            ↓
validation des bindings
            ↓
génération du template
            ↓
diff → écriture contrôlée
```

FD-DESIGN-002 : modèles Pydantic de blocs ; FD-DESIGN-003 : imbrication ;
FD-DESIGN-004 : lecture/écriture sécurisée ; FD-BINDING-001 : bindings.
FD-DESIGN-001 apporte seulement le schéma packagé, les exemples et les tests de
ses déclarations. Aucun validateur Python ni moteur jsonschema. Les assertions
structurelles et tests ciblés de motifs ne prouvent pas une validation complète
d'instances. Aucun scan projet, UI, drag-and-drop, Tool ou helper runtime.
Les contrats et Template Viewer restent inchangés : ce dernier peut afficher les
.design.json comme fichiers génériques ; la liaison contractuelle les exclut localement.

## Modèles Python — FD-DESIGN-002

Pydantic v2 valide maintenant le document déjà disponible en mémoire. API exportée
par `forge_design.design` : DesignFile, DesignNode, PageRoot, TableColumn,
DesignNodeType et PropValue. Aucune lecture/écriture de fichier ni helper load/read.
Le schéma normatif v0.1 reste inchangé.

```python
from forge_design.design import DesignFile

design = DesignFile.model_validate(data)
design = DesignFile.model_validate_json(text)
payload = design.model_dump(exclude_unset=True)
text = design.model_dump_json(exclude_unset=True)
```

DesignNode reste générique et récursif, avec les treize types existants. PageRoot
est la seule spécialisation : type page et children obligatoires, sans défauts
implicites, avec binding/props/columns toujours possibles. Des propriétés communes
internes évitent un override incompatible de children ; aucune classe par bloc.
Page descendant, button avec children et columns sur section restent admis à cette
étape structurelle. Aucune validation d'imbrication ou de binding.

Types stricts, extra interdit, attributs frozen. PropValue conserve str/bool/int/float :
`"true"` reste une chaîne, 12 reste int, true reste bool, 0.5 reste float. Chaîne vide
admise dans props ; null, objets et listes refusés. NaN/Infinity ne sont pas des
nombres JSON et sont refusés via allow_inf_nan=False. Aucune interprétation d'intention.
Clés props non vides, sans normalisation, même Unicode ; aucune conversion de bytes.

Les attributs facultatifs absents valent None dans l'API Python ; BeforeValidator
refuse un None/null fourni explicitement. Le schéma généré retire la branche null
et le défaut interne. `model_fields_set` conserve la présence et
**exclude_unset=True** préserve l'omission, les objets/listes vides explicitement
fournis et le round-trip. Un dump sans cette option peut ajouter les None internes
et ne représente pas l'export conforme recommandé.

source_contract combine les bornes et motif normatifs avec un validator ciblé
pour les quatre exclusions `not.anyOf`. Aucun accès au schéma pendant la validation,
aucun appel source_parts. Les contraintes générées restent comparées au normatif.
Un nom sensible ou caché admis structurellement ne devient pas autorisé en lecture :
le confinement filesystem appartient toujours à FD-DESIGN-004.

ValidationError.errors() fournit les loc/codes, notamment root.children.0.type et
root.children.1.columns.0.binding. JSON mal formé : json_invalid ; une boucle Python
récursive : recursion_loop contrôlé. Arbre de 30 niveaux testé. Aucune borne métier
MAX_DESIGN_DEPTH ajoutée ; les limites internes du parser/validateur subsistent.

Le gel est superficiel : children/columns sont des listes, props un dictionnaire,
modifiables sans nouvelle validation automatique. Après mutation, revalider les
données sérialisées, pas seulement une instance existante. Les API de confiance
Pydantic (model_construct, model_copy avec update) et overrides permissifs ne sont
pas des frontières de validation. Aucune garantie d'immuabilité profonde.

Aucun changement des contrats, Tools, Web, générateur ou dépendances. Les étapes
suivantes restent FD-DESIGN-003 (imbrication), FD-DESIGN-004 (I/O) et les bindings.

## Règles d’imbrication — FD-DESIGN-003

La validation d'imbrication est une étape pure distincte de Pydantic. Le schéma,
les modèles et les deux fixtures officielles restent inchangés. Un DesignFile
peut être structurellement valide et contenir des relations parent/enfant invalides.

```python
from forge_design.design import DesignFile, can_contain, validate_design_nesting

design = DesignFile.model_validate(data)
result = validate_design_nesting(design)
assert can_contain("section", "text")
# result.valid, result.issues, result.truncated
```

| Parent | Enfants autorisés v0.1 |
|---|---|
| page | section, table |
| section | container, grid, card, form, table, alert, text |
| container | grid, card, form, table, text, button |
| card | title, text, form, button, grid |
| form | field, button, alert |
| table | empty_state |
| grid | aucun |
| title | aucun |
| text | aucun |
| button | aucun |
| field | aucun |
| alert | aucun |
| empty_state | aucun |

La fixture contacts-list contient également une table directement sous page.
Le ticket exige simultanément sa validité sans modification et page → section
uniquement. Pour préserver la fixture livrée, **page → table** est ajouté
explicitement à la matrice, sans exception fondée sur le nom du fichier ou le binding.
Il s'agit d'une seconde correction de cohérence des sources, distincte de section → text.

ALLOWED_CHILDREN est un mapping non modifiable de frozenset, typé avec
DesignNodeType. DesignNestingIssue et DesignNestingResult sont des dataclasses
gelées ; issues est un tuple. La règle dépend seulement des types parent/enfant :
props, binding et columns sont ignorés. TableColumn n'est pas un bloc enfant.
Aucune présence obligatoire de columns, props ou binding n'est ajoutée.

La relation section → text complète explicitement la réduction du cadrage au
vocabulaire existant : l'exemple normatif contacts-list utilise déjà text/tag=h1
sous section. Cela n'autorise pas section → title. Grid, title, text, button,
field, alert et empty_state sont feuilles selon une **politique v0.1 conservatrice**.
Le cadrage et le vocabulaire actuel ne fournissent pas de règle Grid fiable ;
cette décision ne préjuge pas des versions futures. Header, main, footer, image,
hidden_field et actions ne sont pas ajoutés. Aucune page descendante n'est permise.

Chaque mauvaise relation produit design.nesting.child_not_allowed, avec message
humain, parent_type, child_type et path tuple, par exemple
("root", "children", 0, "children", 2). Les diagnostics suivent le parcours préfixe,
profondeur d'abord et ordre source, même sous un parent déjà signalé. Aucun tri
ou dédoublonnage des occurrences.

Les bornes d'analyse sont centralisées dans limits.py :

| Borne | Valeur | Sémantique |
|---|---:|---|
| MAX_DESIGN_NODES | 4096 | Racine comprise ; occurrences inspectées |
| MAX_DESIGN_DEPTH | 128 | Racine à profondeur 0 ; 128 admis |
| MAX_DESIGN_ISSUES | 512 | Marqueur terminal compris |

Une limite exactement atteinte sans surplus ne tronque pas. Au premier surplus,
l'analyse entière s'arrête avec truncated=True et valid=False. Un unique diagnostic
terminal design.nesting.analysis_truncated identifie le nœud qui déclenche l'arrêt.
Si 512 diagnostics existent déjà, le dernier est remplacé par le marqueur : les
511 premières erreurs sont préservées. À 512 erreurs sans surplus, les 512 restent
présentes et truncated=False. Le message précise la borne atteinte ; le code et
le path constituent le contrat machine.

Parcours itératif par pile d'itérateurs, sans model_dump ni copie des listes
d'enfants. La largeur ne gonfle pas la pile ; les chemins et la pile sont bornés
par la profondeur. Coût linéaire dans les occurrences inspectées à profondeur
plafonnée. Un cycle introduit par mutation des listes s'arrête à la borne de
profondeur. L'entrée doit conserver ses types Pydantic ; aucune réparation ou
revalidation générale des modèles mutés arbitrairement n'est réalisée.

valid=True signifie uniquement absence d'erreur d'imbrication et analyse complète.
Aucun accès filesystem, contexte, contrat, Web, génération ou nouveau Tool.
Les références et contenus des objets sont conservés. Le lecteur/écrivain sécurisé
reste FD-DESIGN-004 et la validation des bindings appartient à une étape ultérieure.

## Lecture / écriture — FD-DESIGN-004

Les API publiques travaillent sur **un seul fichier**, relatif à `mvc/views/` :
`contacts/list.design.json`. design_source() combine le suffixe exact avec la
politique template_source/source_parts. Il faut un nom avant `.design.json` ;
`design.json`, `.design.json`, variantes de casse et suffixes de sauvegarde sont
refusés. Préfixe mvc/views, chemins absolus, segments cachés, traversées, antislash,
deux-points, NUL et noms sensibles sont refusés avant ouverture.

```python
from forge_design.design import read_design, write_design

read = read_design(root, "contacts/list.design.json")
# Examiner read.issues ; read.design peut être présent malgré un nesting invalide.
if read.design is not None and not read.issues:
    saved = write_design(
        root,
        "contacts/list.design.json",
        read.design,
        expected_revision=read.revision,
    )
# Pour créer un fichier absent : expected_revision=None, obligatoire explicitement.
```

La racine est résolue et reconnue comme projet Forge, sans importer son code.
Lecture ancrée par descripteurs, parents O_NOFOLLOW, cible régulière contrôlée par
stat/fstat/samestat, ouverture O_NONBLOCK et plafond commun de 1 Mio. Les octets
sont lus une seule fois et contrôlés après lecture (size/mtime/ctime/longueur).
SourceContent et les API historiques du Source Viewer sont conservés ; une primitive
commune retourne maintenant aussi les octets et métadonnées sans décodage.

Le JSON doit être UTF-8, avec BOM initial facultatif. Le parseur strict partagé
avec les contrats refuse clés dupliquées, NaN/Infinity/-Infinity, commentaires et
virgules finales. Pydantic valide ensuite la structure, puis le validateur
d'imbrication produit ses diagnostics. Aucun binding, contrat lié ou template
n'est consulté pour accepter un design.

DesignReadResult et DesignIssue sont des dataclasses gelées. Le résultat expose
path relatif, size, modified_ns, revision, design et issues tuple. Une lecture sûre
conserve les métadonnées même si le décodage ou le JSON échoue. Une lecture refusée
n'a pas de révision. Une cible absente lève FileNotFoundError ; chemin lexical
invalide : SourceReadError ; projet invalide : exceptions projet historiques.

| Code | Sens |
|---|---|
| design.unreadable | Lecture refusée ou encodage non UTF-8 |
| design.json_invalid | Syntaxe JSON stricte invalide |
| design.validation_error | Structure Pydantic invalide |
| design.nesting_error | Relation parent/enfant invalide |
| design.analysis_truncated | Diagnostics ou analyse d'imbrication plafonnés |

Si seul le nesting échoue, le DesignFile reste présent pour permettre une réparation
future. location conserve le chemin Pydantic/nesting ; parent_type et child_type
conservent les informations d'imbrication. Le nombre de diagnostics Pydantic est
également plafonné à MAX_DESIGN_ISSUES, marqueur terminal compris.

DesignRevision contient size, modified_ns et SHA-256 des octets réellement lus,
ainsi que device/inode/changed_ns. Ces trois derniers champs détectent aussi un
remplacement à contenu et mtime identiques. La révision est une métadonnée runtime,
jamais ajoutée au JSON. Conserver l'objet retourné par read_design/write_design.

Avant toute I/O d'écriture, le writer sérialise avec exclude_unset=True et revalide
les données avec DesignFile.model_validate : le gel superficiel n'est pas une
frontière de confiance. Les mutations invalides, NaN, cycles, nesting invalide ou
tronqué et sortie supérieure à 1 Mio sont refusés par InvalidDesignForWriteError,
qui expose issues. Aucune correction automatique. Sérialisation UTF-8 sans BOM,
ensure_ascii=False, indent=2, allow_nan=False, sans sort_keys et avec un unique
newline final. Ordre des champs produit par les modèles ; mêmes données, mêmes octets.

Deux modes de sauvegarde :

- expected_revision=None : création seulement si le chemin est absent.
- Révision fournie : mise à jour seulement si tous ses champs correspondent au
  fichier courant. Mtime modifié seul, disparition, remplacement, lien symbolique,
  contenu différent même de taille identique : DesignWriteConflictError.

Il n'existe aucune option force. Les autres échecs d'écriture sont transformés en
DesignWriteError. Aucun dossier parent n'est créé ; aucun backup ou historique.
Aucun template, contrat, fichier de configuration XDG ou autre fichier projet
n'est modifié. Seuls la cible design et son temporaire interne sont manipulés.

Le temporaire `.forge-design-write-<aléatoire>` est créé dans le dossier cible par
O_CREAT|O_EXCL|O_NOFOLLOW, manipulé par dirfd et synchronisé avec fsync. Les écritures
partielles sont complétées. Après contrôle d'identité du temporaire et dernier
contrôle de révision, l'update utilise os.replace. Pour une création, link puis
unlink du temporaire publient atomiquement **sans écrasement**, même si une cible
apparaît après le dernier contrôle. Le système doit supporter ces primitives POSIX ;
aucun fallback moins sûr. Une collision de temporaire est refusée sans suivre ni
supprimer le fichier préexistant. Les temporaires créés sont nettoyés à la sortie.

Le dossier est synchronisé puis la cible relue pour retourner DesignWriteResult
(path, created, size, modified_ns, revision) correspondant aux octets finaux.
Un échec après publication (fsync du dossier, relecture ou nettoyage) peut laisser
le nouveau fichier en place : **relire avant de réessayer**, pas de rollback annoncé.
Une erreur de nettoyage liée aux permissions ou une interruption brutale peut
laisser un temporaire ; aucune garantie de récupération après crash n'est promise.

Mode de création 0o666 soumis à l'umask ; update préserve les bits &0o777. ACL,
xattrs, propriétaire particulier et liens physiques ne sont pas préservés : le
remplacement crée un nouvel inode et laisse les autres hard links sur l'ancien.

Il n'y a pas de verrou interprocessus ni de transaction filesystem complète. Une
fenêtre de race résiduelle existe entre le dernier contrôle et replace : un autre
processus peut alors modifier/remplacer la cible. Même limite entre contrôle et
publication du nom temporaire face à un acteur pouvant écrire dans le même dossier.
Les descripteurs empêchent le suivi des liens, mais un dossier ouvert peut être
renommé ; il n'existe pas d'instantané global de l'arborescence. Ces limites ne
permettent pas de promettre un compare-and-swap face à un adversaire concurrent.


## Visibilité déclarative — FD-BINDING-003

Extension additive de v0.1 : visible_if est une chaîne non vide facultative sur
DesignNode et PageRoot, sans changement du vocabulaire de blocs. Absence conservée
au dump exclude_unset=True ; null explicite, chaîne vide et valeurs non textuelles
refusés. Les documents v0.1 historiques restent valides, d'où le maintien de version
0.1. Les anciens lecteurs stricts ne connaissant pas cette propriété peuvent refuser
les nouveaux documents : la compatibilité est celle des anciens documents avec
le format étendu, pas une promesse de lecture par les anciens binaires.

Exemple de nœud : button avec binding=create et visible_if=can_create. Le premier
nom vise une action ; le second une clé exacte de context de type boolean.
Aucun moteur d'expression, permission interprétée ou valeur runtime évaluée.
La [fixture conditionnelle](../../tests/fixtures/design/conditional.design.json)
utilise page → section → container → button, compatible avec le nesting actuel.
Les deux fixtures précédentes sont inchangées.

La propriété traverse le cycle write_design/read_design sans adaptation du module
I/O. Celui-ci continue à valider Pydantic et nesting seulement : la résolution de
visible_if contre un contrat explicitement fourni reste une étape indépendante.
Voir les [bindings conditionnels](bindings.md#bindings-conditionnels--fd-binding-003).

## Form / Field contract — FD-INTERACT-002

Représentation minimale d'un futur formulaire HTML/HTMX. **Rien n'est encore
généré** : ni `<form>`, ni `<input>`, ni HTMX de formulaire.

```json
{
  "type": "form",
  "binding": "create_contact",
  "children": [
    {
      "type": "field",
      "field": {
        "name": "email",
        "input_type": "email",
        "label": "Adresse e-mail",
        "required": true
      }
    },
    { "type": "button", "binding": "create_contact" }
  ]
}
```

### Form

`form.binding` désigne une **action** du contrat (`ViewContract.actions`),
exactement comme un `button`. `validate_design_bindings` applique la règle
`form → action` : une action inconnue donne `design.binding.unknown_action`.
Un `form` sans binding reste structurellement valide et n'est pas signalé ;
la génération future décidera qu'un formulaire actif exige une action.

### Field

Les informations d'un champ ne sont pas visuelles : elles ne vont pas dans
`props`. Elles forment la propriété explicite `field` (`FieldDefinition`) :

| Clé | Obligatoire | Sens |
|---|---|---|
| `name` | oui | futur attribut HTML `name`, chaîne non vide **opaque** (`email`, `contact.email`, `items[0].name`), jamais déduite du libellé, du contexte, du type ni de la position |
| `input_type` | oui | `text`, `email`, `password`, `number`, `date` ou `checkbox` |
| `label` | non | libellé non vide ; absent, aucun libellé ne sera inventé |
| `required` | non | `true` (obligatoire), `false` (déclaré non obligatoire) ; absent, aucune exigence déclarée, distinct de `false` |

`null`, les clés inconnues (`value`, `default`, `placeholder`…), un type
inconnu et un `name` vide sont refusés par le modèle et le schéma. Le
`binding` d'un `field` reste refusé (`design.binding.unsupported`) : le nom du
champ est `field.name`, pas une troisième sémantique de `binding`.

### Validation sémantique

`validate_form_fields(design)` (`design/form_fields.py`) est borné par
`MAX_DESIGN_NODES`, `MAX_DESIGN_DEPTH` et `MAX_DESIGN_ISSUES` :

| Code | Cas |
|---|---|
| `design.field.missing_definition` | bloc `field` sans `field` |
| `design.field.unsupported_definition` | `field` porté par un autre type (page comprise) |
| `design.field.duplicate_name` | même `name` deux fois dans un **même** `form` (deux formulaires peuvent réutiliser un nom) |
| `design.field.analysis_truncated` | borne atteinte |

L'imbrication reste du ressort de `validate_design_nesting` : `form` contient
`field`, `button` et `alert`, et `field` est une feuille, sans changement.

### Compatibilité v0.1

La version reste `0.1`, format pré-stable. `field` est facultatif au niveau
générique : un Design sans bloc `field` est inchangé. Un ancien bloc `field`
sans définition reste **valide pour Pydantic**, donc chargeable, mais il est
**sémantiquement incomplet** (`design.field.missing_definition`). La
migration peut ainsi se faire progressivement.

### Limites

Pas encore de `<form>` ni d'`<input>` générés (`generate.unsupported_block`),
pas de rendu de champ dans la preview (un `field` reste un `<div>` générique),
pas de valeur initiale, de placeholder, de `select`, `textarea`, `radio` ni
d'upload, et pas de CSRF runtime.
