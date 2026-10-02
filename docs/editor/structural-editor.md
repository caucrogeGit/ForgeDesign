# Éditeur structurel — FD-EDITOR-001 à 006

Mutations contrôlées d'un `DesignFile` : **ajouter**, **supprimer** et
**déplacer** un bloc, puis **configurer ses propriétés**. L'éditeur est un moteur en mémoire, réutilisable par une future UI :
il ne lit, n'écrit, ne prévisualise ni ne génère rien.

```text
DesignFile ─► revalidation ─► localisation ─► règles ─► nouveau DesignFile
                                                         ├── preview future / UI
                                                         └── write_design explicite
```

## API — `forge_design.editor`

```python
result = append_design_block(design, parent=(), block_type="section")
result = append_design_block(result.design, parent=(0,), block_type="card")
result = remove_design_block(result.design, path=(0, 0))
```

| Symbole | Rôle |
|---|---|
| `NodePath` | `tuple[int, ...]` |
| `append_design_block(design, *, parent, block_type)` | ajoute `DesignNode(type=block_type)` en dernier enfant de `parent` |
| `remove_design_block(design, *, path)` | supprime le bloc et tout son sous-arbre |
| `move_design_block(design, *, source, destination)` | déplace le bloc et son sous-arbre en dernier enfant de `destination` |
| `DesignEditResult` | `design`, `changed`, `affected_path`, `issues` |
| `DesignEditIssue` | `code`, `message`, `path` |

Les dataclasses de résultat sont gelées.

## NodePath

```text
()       → page racine
(0,)     → premier enfant de la page
(0, 2)   → troisième enfant du premier enfant
```

Un chemin d'indices est plus simple à manipuler que la forme JSON des
diagnostics (`("root", "children", 0, …)`), qui reste inchangée. Seuls des
`int` non négatifs sont acceptés : un booléen n'est pas un indice, même si
`bool` hérite de `int`.

**Pas d'identifiant de nœud.** Le Design ne reçoit ni `id` ni `uuid`. Après une
insertion ou une suppression, **les indices des frères suivants changent** :
supprimer `(0, 1)` fait de l'ancien `(0, 2)` le nouveau `(0, 1)`. Un chemin
n'est donc valable que pour le Design sur lequel il a été calculé. Des
identifiants stables ne seront étudiés que si un besoin réel apparaît
(déplacement multi-étapes, UI concurrente…).

## Ajout

- Toujours en **fin de liste** : pas d'insertion à une position, pas de
  drag-and-drop.
- Le bloc créé est exactement `{"type": block_type}` : aucun binding, classe,
  texte, colonne ni `visible_if` inventé.
- `affected_path = (*parent, N)`, où `N` est le nombre d'enfants avant l'ajout.
- Un parent sans clé `children` en reçoit une.

## Suppression

- Le bloc **et tous ses descendants** disparaissent. Aucun enfant n'est
  remonté dans le parent.
- `affected_path` est le chemin du **parent** ; pour un enfant direct de la
  page, c'est `()`.
- Si le parent (autre que la page) n'a plus d'enfant, sa clé `children` est
  omise, comme avant tout ajout. Un ajout suivi d'une suppression redonne donc
  exactement le Design initial. La page garde toujours `children: []`.

## Règles d'imbrication

L'éditeur appelle `nesting.can_contain(parent, enfant)` au moment de
l'opération, sans copier la matrice `ALLOWED_CHILDREN`. Les feuilles (`title`,
`text`, `button`, `field`, `alert`, `empty_state`, `grid`) refusent tout enfant
selon cette même règle. `page` n'est jamais insérable comme enfant.

## Diagnostics

| Code | Cas |
|---|---|
| `editor.invalid_path` | chemin qui n'est pas un tuple d'`int` (booléens compris) |
| `editor.path_not_found` | indice négatif ou hors bornes |
| `editor.unknown_block_type` | type hors `DesignNodeType` |
| `editor.root_type_not_insertable` | `block_type="page"` |
| `editor.child_not_allowed` | `can_contain` refuse |
| `editor.node_limit` | Design déjà à `MAX_DESIGN_NODES` (racine comprise) |
| `editor.depth_limit` | le bloc ajouté, ou le sous-arbre déplacé, dépasserait `MAX_DESIGN_DEPTH` |
| `editor.root_not_removable` | `path=()` en suppression |
| `editor.root_not_movable` | `source=()` en déplacement |
| `editor.destination_inside_source` | destination égale à la source ou dans son sous-arbre |
| `editor.invalid_design` | entrée invalide, mal imbriquée, hors bornes ou cyclique |
| `editor.invalid_result` | incohérence interne : résultat non valide |

En cas de refus : `changed=False`, `affected_path=None` et `design` est
**l'objet reçu**, inchangé. Il n'y a jamais de mutation partielle.

## Bornes

Les bornes existantes sont réutilisées, sans limite concurrente :
`MAX_DESIGN_NODES` (racine comprise, même convention que
`validate_design_nesting`) et `MAX_DESIGN_DEPTH` (page à la profondeur 0). La
suppression reste possible à la limite.

La matrice actuelle n'a aucun cycle (page → section → container → card → form
→ field) : un Design valide ne dépasse pas une profondeur d'environ 5, et
`editor.depth_limit` n'est atteignable que si les règles évoluent. La borne est
tout de même appliquée et testée avec une règle élargie.

## Immutabilité et revalidation

Les modèles Pydantic sont `frozen`, mais leurs listes restent mutables. Avant
toute édition, l'entrée est :
1. parcourue de façon bornée et itérative (types de nœuds, nombre, profondeur ;
   un cycle créé par mutation de liste est arrêté par la borne) ;
2. sérialisée par `model_dump(exclude_unset=True)`, puis revalidée par
   `DesignFile.model_validate` et `validate_design_nesting`.

La copie issue du dump (dicts et listes neufs) est modifiée, puis le résultat
est reconstruit par Pydantic et revalidé (modèle et imbrication). Le résultat
ne partage aucune liste avec l'entrée : modifier ses listes ne touche pas
l'original. Il n'y a pas de `deepcopy`. `version`, `view`, `source_contract`,
ainsi que les `props`, `binding`, `visible_if` et `columns` des autres nœuds,
sont conservés à l'identique. Les opérations sont déterministes.

## Hors périmètre

Pas d'I/O (ni `read_design`, ni `write_design`, ni fichier) : la sauvegarde
reste une action explicite de `design/io.py`. Pas de preview, génération ou diff
automatiques, pas de Web, HTMX, JavaScript ni Tool. Les propriétés se
configurent avec les fonctions de FD-EDITOR-003 (section dédiée ci-dessous).

## Déplacement — FD-EDITOR-002

```python
result = move_design_block(design, source=(0, 0), destination=(1,))
```

```text
page                          page
├── section A   (0,)          ├── section A
│   └── card    (0, 0)   →    └── section B
│       ├── title                 └── card      affected_path = (1, 0)
│       └── text                      ├── title
└── section B   (1,)                  └── text
```

- `source` est le bloc déplacé. `destination` est son **nouveau parent** ; il
  peut être la page `()`.
- Le bloc devient le **dernier enfant** de `destination`. Il n'y a ni position
  arbitraire, ni insertion avant ou après, ni drag-and-drop.
- Le **sous-arbre est déplacé intégralement** : le dict complet issu du dump
  (`type`, `binding`, `visible_if`, `props`, `columns`, `children` et tous les
  descendants), sans clone simplifié. Aucun nœud n'est créé ni supprimé.
- `affected_path` est le **nouveau chemin du bloc déplacé**.
- Le parent source vidé perd sa clé `children`, sauf la page.

### Chemins interprétés avant mutation et remapping

`source` et `destination` désignent toujours **l'arbre initial**. Retirer la
source peut décaler la destination. Le helper interne
`_adjust_path_after_removal(path, removed)` recalcule la destination après le
retrait :
- seul l'indice du niveau de `removed` peut changer, et seulement si `path`
  partage le parent de `removed` jusqu'à ce niveau ;
- cet indice baisse de 1 s'il désigne un frère **suivant** de `removed` ;
- un frère précédent, une autre branche, un ancêtre de `removed` ou un chemin
  plus court restent inchangés.

| Source | Destination initiale | Destination après retrait |
|---|---|---|
| `(0,)` | `(2,)` | `(1,)` |
| `(0,)` | `(2, 0, 1)` | `(1, 0, 1)` |
| `(0, 1)` | `(0, 2, 3)` | `(0, 1, 3)` |
| `(0, 1, 0)` | `(0, 1, 1, 2)` | `(0, 1, 0, 2)` |
| `(1,)` | `(0, 4)` | `(0, 4)` |
| `(0, 1)` | `(0,)` (parent) | `(0,)` |

### Même parent et no-op

Déplacer un bloc vers son parent actuel le place en fin de liste :
`[A, B, C]` donne `[B, C, A]` en déplaçant A, et `[A, C, B]` en déplaçant B. Si
le bloc est **déjà le dernier**, l'ordre ne change pas : le résultat est
`changed=False`, `affected_path=source`, `issues=()`, et `design` est l'objet
reçu, sans nouveau `DesignFile` produit.

### Refus

- `source=()` : `editor.root_not_movable`, la page reste l'unique racine.
- Destination égale à la source ou dans son sous-arbre
  (`destination[:len(source)] == source`) :
  `editor.destination_inside_source`. Ce contrôle est fait **avant tout
  retrait**.
- `nesting.can_contain(type destination, type déplacé)` faux :
  `editor.child_not_allowed`. Par exemple, une `card` ne peut pas aller sous la
  page.
- Le sous-arbre doit tenir à sa nouvelle position :
  `len(destination) + 1 + hauteur relative ≤ MAX_DESIGN_DEPTH`, sinon
  `editor.depth_limit`. La hauteur relative (`card → form → field` = 2) est
  calculée de façon itérative et bornée. Une destination plus profonde peut
  dépasser la limite même si l'arbre initial est valide.
- Les chemins suivent la politique `NodePath` (`editor.invalid_path`,
  `editor.path_not_found`). L'entrée et le résultat sont revalidés comme pour
  l'ajout et la suppression.

Les indices restent **non stables** : après un déplacement, les frères suivants
de la source sont décalés. Tout chemin calculé avant l'opération est à
recalculer.

## Configuration des propriétés — FD-EDITOR-003

Module `forge_design/editor/properties.py`. Il configure les propriétés
**déjà prévues par Design v0.1**, sans modifier le schéma ni le modèle.
`structure.py` gère l'arbre, `properties.py` la configuration d'un nœud. Les
deux partagent le socle interne `editor/_tree.py` (chemins, revalidation,
reconstruction) et le même contrat de résultat `DesignEditResult`.

| Fonction | Propriété | Contrat requis |
|---|---|---|
| `set_design_binding(design, *, path, binding, contract)` | `binding` | oui |
| `set_design_visibility(design, *, path, visible_if, contract)` | `visible_if` | oui |
| `set_design_props(design, *, path, props)` | `props` | non |
| `set_table_columns(design, *, path, columns, contract)` | `columns` | oui |
| `set_field_definition(design, *, path, field)` (FD-INTERACT-002) | `field` | non |
| `set_submit_definition(design, *, path, submit)` (FD-INTERACT-004) | `submit` | non |

Une fonction modifie **une seule propriété** : jamais les autres propriétés
du bloc, ses enfants ou les autres blocs. Il n'y a pas d'`update_block(...)`
qui mélangerait « non fourni », « effacer » et « mettre à jour ».

### `None`, valeur vide et no-op

- `None` **supprime** la propriété : la clé est omise du JSON.
- `""` est refusé pour `binding` et `visible_if` : ce n'est pas une absence.
- `props={}` reste `{}` et `columns=[]` reste `[]`, distincts de l'absence.
- Si la propriété est **déjà exactement** dans l'état demandé : `changed=False`,
  `affected_path=path`, `issues=()`, et `design` est l'objet reçu. La
  comparaison est stricte au sens JSON : `1`, `1.0` et `True` diffèrent, et
  l'ordre des clés de `props` compte.
- Les valeurs de l'appelant (mapping, séquence) sont copiées : les modifier
  ensuite n'affecte pas le résultat. Tout `Mapping` est accepté pour `props`.

### Validation

1. Validation du chemin et revalidation de l'entrée, comme pour la structure.
   Le contrat est lui aussi revalidé (`editor.invalid_contract`), car ses
   dictionnaires restent mutables.
2. Pydantic applique le contrat Design : clés de props non vides, valeurs
   `str`, `bool`, `int` ou `float` finies, pas de `null`, colonnes
   `TableColumn` à chaînes non vides.
3. Reconstruction et revalidation de l'imbrication (`editor.invalid_result`).
4. **Validation contractuelle ciblée** par les validateurs existants
   (`validate_design_bindings`, `validate_conditional_bindings`,
   `validate_table_bindings`), appliqués à un Design **projeté** qui ne porte
   que le bloc édité, sans ses enfants. Ces règles ne dépendent que du bloc et
   du contrat. Une erreur préexistante sur un autre bloc ne bloque donc pas une
   correction locale, et ne peut ni épuiser la limite de diagnostics ni tronquer
   l'analyse du bloc édité. Aucune règle n'est recopiée dans l'éditeur.

Supprimer une propriété (`None`) ne requiert aucune validation contractuelle.
Effacer un binding présent sur un type qui n'en accepte pas (une section, par
exemple) permet de réparer un Design.

### Règles par propriété

| Propriété | Accepté | Diagnostic |
|---|---|---|
| `binding` | `title`/`text` → variable `string`, `table` → variable `list`, `button` → action (règles de `design/bindings.py`) | `editor.invalid_binding` ; autre type, page comprise : `editor.binding_not_supported` |
| `visible_if` | variable `boolean` du contexte, sur **tout** bloc, page comprise | `editor.invalid_condition` |
| `props` | tout mapping conforme au modèle, **pas seulement** `tag` et `class` | `editor.invalid_props` |
| `columns` | bloc `table` uniquement, binding vers une variable `list` du contrat ; champs déclarés si `fields` existe ; au plus `MAX_TABLE_COLUMNS` | `editor.columns_not_supported`, `editor.invalid_table_binding`, `editor.invalid_table_column`, `editor.column_limit` |

Les props sont validées selon le **contrat Design**, pas selon les seules props
connues du générateur. Une prop valide mais ignorée par la génération produira
plus tard `generate.unsupported_prop`, ce qui est normal.

Colonnes :
- une table sans binding, liée à une variable inconnue ou non-`list` refuse
  toute liste de colonnes, même vide : `editor.invalid_table_binding` ;
- une collection sans `fields` accepte `[]` mais refuse des colonnes non vides ;
- un champ non déclaré donne `editor.invalid_table_column`.

`editor.analysis_truncated` est émis si un validateur est tronqué sur le bloc
édité. Avec la projection, cela n'arrive pas en pratique : le nombre de
colonnes est borné en amont.

### Limites

- Changer le `binding` d'une table ne revalide pas ses `columns` existantes :
  une opération valide une seule propriété.
- Aucune sauvegarde (`write_design` reste explicite), aucune génération,
  preview, I/O, UI ni Tool : l'interface Web est décrite ci-dessous.

## Interface Web — FD-EDITOR-004

Module `forge_design/web/editor.py`, template `web/templates/editor.html`. La
couche Web fait le parsing HTTP, les lectures, les appels à `editor/*`, la
sauvegarde et le rendu. **Aucune règle d'édition n'y est codée.**

```text
Navigateur ─► Web Editor ─► read_design / read_view_contract
                                │
                                ▼
                          API editor/*  (une opération)
                                │
                                ▼
                          write_design(expected_revision)
                                │
                                ▼
                          .design.json   (aucun .html écrit)
```

### Routes

| Route | Rôle |
|---|---|
| `GET /editor?design=<chemin>&node=<chemin de bloc>` | arbre et bloc sélectionné (la racine par défaut) ; sans `design`, un formulaire d'ouverture |
| `POST /editor/action` | une action : `append`, `remove`, `move`, `binding`, `visibility`, `props`, `columns` |

Il n'existe pas de route de sauvegarde séparée : `POST /editor/save`, présente
dans FD-EDITOR-004, a été retirée par FD-EDITOR-004A (404).

`design` est relatif à `mvc/views` (`contacts/list.design.json`). Il n'y a pas
d'inventaire de Designs : l'accès se fait par URL explicite. Le lien
« Éditeur » est toujours visible ; sans projet, la page répond **409**.

### Sans état, enregistrement par action

Aucun Design n'est gardé en mémoire : ni session, ni cookie, ni singleton, ni
`CurrentProjectContext`. Chaque requête **relit** le `.design.json` et son
contrat. Chaque action réussie suit le chemin suivant :

```text
read_design → une opération editor/* → write_design(expected_revision=révision lue)
            → 303 vers GET /editor?design=…&node=<bloc concerné>&notice=saved
```

L'enregistrement immédiat concerne **uniquement le `.design.json`**, jamais le
template HTML : pas de génération, de diff, de SAFEWRITE ni de journal. Il
évite une session ou un brouillon serveur, et s'appuie sur les garanties de
`write_design` (révision attendue, écriture atomique, conflit détecté).

**Chaque mutation réussie est écrite immédiatement par `write_design`, avec
la révision lue au début de la requête.** C'est une écriture synchrone,
déclenchée par une action explicite de l'utilisateur, et non une sauvegarde
périodique ou en arrière-plan. Ce sont les seules écritures de l'éditeur Web :
- `changed=True` : une écriture, puis 303 ;
- `changed=False` sans diagnostic (no-op) : **aucune** écriture, 303 avec
  « Aucune modification. » ;
- refus de l'éditeur (`issues`) : **aucune** écriture, 422.

Aucune action ne se contente de réécrire le Design sans le modifier. Une
normalisation explicite d'un fichier écrit à la main pourra faire l'objet d'un
ticket dédié si le besoin apparaît.

Bloc sélectionné après une action : le bloc ajouté ou déplacé
(`affected_path`), le parent après une suppression, ou le bloc lui-même après
une propriété.

### Chemins de bloc dans HTTP

`format_node_path` / `parse_node_path` : `()` ↔ `""`, `(0,)` ↔ `"0"`,
`(0, 2)` ↔ `"0.2"`. Seuls des entiers décimaux ASCII, sans zéro initial et
séparés par un seul point, sont acceptés. `-1`, `01`, `0..1`, `a`, `0/1`, les
espaces et les chiffres non ASCII sont refusés, sans normalisation. Un `node`
invalide ou absent de l'arbre donne **400**, sans repli.

### Formulaires

- **Ajouter** : types proposés = `ALLOWED_CHILDREN[type du parent]`, triés.
- **Déplacer** : destinations = blocs hors du sous-arbre source acceptant le
  type (`can_contain`) ; la page n'est jamais déplaçable.
- **Supprimer** : un bouton par bloc, sauf la page. Pas de confirmation en
  JavaScript.
- **Binding** : `<select>` de toutes les variables (avec leur type) et actions
  du contrat, plus « Aucun binding ». `set_design_binding` reste l'autorité.
- **Condition** : variables `boolean` du contrat, plus « Toujours visible ».
- **Props** : champ **JSON** (objet, ou vide pour supprimer), lu par
  `loads_strict_json`. Toutes les props du modèle sont exposées, sans fausse
  restriction à `class` et `tag`.
- **Colonnes** (tables) : tableau JSON de `{"label", "binding"}`. Vide supprime
  la propriété, `[]` donne aucune colonne.

### Contrat indisponible

L'arbre reste affiché. Ajout, suppression, déplacement et props restent
possibles. Binding, condition et colonnes sont **désactivés à l'affichage et
refusés côté serveur** (409), indépendamment du bouton.

### Statuts

| Cas | Statut |
|---|---|
| succès, ou no-op (`notice=noop`, **aucun appel** à `write_design`) | 303 |
| paramètre, chemin, champ, JSON ou forme d'action invalide | 400 |
| origine non locale (`is_local_action`) | 403 |
| Content-Type autre que `application/x-www-form-urlencoded` | 415 |
| Design introuvable | 404 |
| sans projet, Design non éditable, contrat indisponible, conflit de révision | 409 |
| refus de l'éditeur (`editor.*`) ou `InvalidDesignForWriteError` | 422 |
| `DesignWriteError` : sauvegarde **incertaine**, à relire | 500 |

Une requête porte **exactement** les champs de son action : un champ manquant,
en trop (deux propriétés), dupliqué ou de plus de 64 Kio donne 400. Toutes
les pages sont `Cache-Control: no-store`. Toutes les valeurs du projet sont
échappées par Jinja, sans `|safe`.

### Hors périmètre

Pas de JavaScript, de drag-and-drop, de canvas, d'autosave du template, de
génération implicite, d'undo, de session ni de Tool. L'indentation de l'arbre
utilise des listes imbriquées : la CSP de Forge (`style-src 'self'`) interdit
les styles inline.

## Classes Tailwind — FD-EDITOR-005

Assistant Web pour `props.class`, sans changer le modèle Design ni le stockage.
**`props.class` reste la seule source réelle** : aucune clé `tailwind`,
`style` ou `classes`, et aucun fichier annexe.

```text
Web Editor → web/tailwind_classes.py (pur) → set_design_props → write_design
```

### Tokens opaques

Une classe est un token séparé par des **blancs ASCII** (espace, tabulation,
CR, LF, FF, VT). Forge Design n'interprète **aucune grammaire Tailwind** : les
variantes (`md:`, `hover:`, `dark:`, `group-hover:`), les valeurs arbitraires
(`w-[37px]`, `w-[calc(100%-2rem)]`) et les propriétés arbitraires
(`[mask-type:luminance]`) sont conservées telles quelles. Un token est refusé
seulement s'il est vide ou contient un blanc ASCII ou NUL. Forge Design ne
garantit pas qu'une classe existe dans la version Tailwind du projet, seulement
qu'elle est conservée explicitement. Il n'y a ni dépendance Tailwind, ni npm,
ni build CSS, ni JavaScript.

### Actions

| Action | Champs exacts | Effet |
|---|---|---|
| `tailwind_set` | `design`, `path`, `classes` | remplace toute la chaîne ; vide supprime la clé `class` |
| `tailwind_add` | `design`, `path`, `class_token` | ajoute en fin si absent |
| `tailwind_remove` | `design`, `path`, `class_token` | retire **toutes** les occurrences exactes |

Chaque action ne modifie **que** `props["class"]` : les autres props, leurs
valeurs et l'ordre des clés sont conservés. Une clé `class` existante garde sa
position ; une nouvelle est ajoutée en dernier. Si `class` était la seule prop
et qu'elle disparaît, `props` devient `{}` : l'action porte sur la classe, pas
sur la propriété `props` entière. Les nouvelles props passent toujours par
`set_design_props`, qui reste l'autorité, puis par `write_design`.

### Canonicalisation, ordre et doublons

- Toute action qui modifie la chaîne l'écrit sous forme canonique : tokens
  séparés par **un seul espace**, sans blanc en tête ni en fin.
- L'ordre est conservé, sans tri, et l'ajout se fait en fin.
- Les doublons historiques ne sont **pas** nettoyés globalement :
  `mx-auto mx-auto py-8` plus `text-xl` donne `mx-auto mx-auto py-8 text-xl`.
  Ajouter un token déjà présent est un no-op ; le retirer enlève toutes ses
  occurrences.
- Le JSON générique des props reste disponible pour écrire **exactement** une
  autre chaîne, non canonique comprise.

### No-op

Aucune écriture (`write_design` non appelé) et 303 avec « Aucune
modification. » dans trois cas : `tailwind_set` dont la forme canonique est
égale à celle de la chaîne actuelle, `tailwind_add` d'un token présent, et
`tailwind_remove` d'un token absent. Les helpers rendent alors le mapping
d'origine tel quel, même absent, pour que `set_design_props` constate le
no-op : sans cela, un bloc sans props recevrait `{}`.

### Interface

Sous le JSON des props, la section « Classes Tailwind » affiche :
- la **chaîne réelle** dans un champ texte visible, copiable et remplaçable ;
- les tokens actuels, chacun avec un bouton « Retirer » (un formulaire
  indépendant par token) ;
- un champ libre « Ajouter » avec une `<datalist>` de suggestions ;
- des suggestions par catégorie (Layout, Largeur, Espacement, Texte, Couleurs,
  Bordures), sous forme de boutons d'ajout ; ceux déjà présents sont
  désactivés.

Les suggestions sont une **courte liste non normative** : une classe absente
de la liste reste autorisée, et rien n'est téléchargé. Aucun style inline, à
cause de la CSP.

### `props.class` qui n'est pas une chaîne

Le modèle autorise toute `PropValue` (par exemple `{"class": true}`). Dans ce
cas, la valeur est affichée, l'assistant est désactivé et ses actions
répondent 422 sans écrire. Aucune conversion automatique n'est faite :
la correction passe par le JSON des props.

### Sécurité

Inchangée par rapport à FD-EDITOR-004 : `is_local_action` (403), formulaire
urlencodé (415), champs exacts par action (400), 64 Kio par champ, révision
attendue (409 en cas de conflit). Un token invalide donne 400. Après l'action,
le même bloc reste sélectionné.

## Prévisualisation intégrée — FD-EDITOR-006

L'éditeur affiche une **prévisualisation statique et indicative** du Design
enregistré, produite exclusivement par les fonctions existantes :

```text
.design.json + .view.json
   → generate_preview_data(contract)      (données fictives de preview/data.py)
   → render_preview(design, data)         (renderer de preview/render.py)
   → GET /editor/preview                  (document dédié)
   → <iframe sandbox> dans /editor
```

Il n'y a ni second renderer, ni nouvelles données fictives, ni modification
de `forge_design/preview/`. Le backend Forge cible n'est ni importé ni
appelé, et aucun template Jinja n'est exécuté. Le GET est en lecture seule.

### Document encadré

`GET /editor/preview?design=<chemin>&mode=desktop|tablet|mobile` (exactement
ces paramètres ; `mode` vaut `desktop` par défaut) renvoie un document HTML
complet (`preview_frame.html`), stylé par `/editor-preview.css`. Ce CSS
générique sert la lisibilité (marges, tableaux, contours de blocs) et
**n'émule pas Tailwind** : les classes sont conservées dans le HTML mais aucun
build Tailwind du projet n'est chargé. L'aperçu est donc structurel, pas le
rendu final.

Le HTML de `render_preview` est le **seul** contenu marqué sûr (`Markup`, côté
Python) : ce renderer interne échappe valeurs, libellés et classes et n'émet
que des balises en liste blanche. Diagnostics, chemins et messages restent
échappés par Jinja.

Indisponible, avec un message et sans rendu inventé : Design invalide,
contrat absent ou invalide. Sans projet, 409 ; Design introuvable, 404 ;
paramètre inconnu, dupliqué ou invalide, 400. Une preview partielle est
affichée avec « Prévisualisation partielle » et ses diagnostics, séparés en
« Données fictives » (`PreviewDataIssue`) et « Rendu » (`PreviewRenderIssue`),
avec leurs codes.

### Encadrement et sécurité

Forge refuse par défaut tout encadrement (`X-Frame-Options: DENY`,
`frame-ancestors 'none'`) : sans ajustement, l'iframe serait bloquée par le
navigateur. **Seule** la réponse `/editor/preview` définit ses propres
en-têtes, que Forge respecte (`setdefault`) :

```text
Content-Security-Policy: default-src 'none'; style-src 'self' http://127.0.0.1:<port>;
  img-src 'self' data:; frame-ancestors 'self'; base-uri 'none'; form-action 'none'
X-Frame-Options: SAMEORIGIN
```

Cette politique est plus stricte que la politique par défaut (aucun script,
aucune soumission de formulaire), sauf sur un point : l'encadrement en **même
origine**. Toutes les autres pages, l'éditeur compris, gardent `DENY` et
`frame-ancestors 'none'`. L'origine exacte est ajoutée à `style-src` parce
que, dans une iframe sandboxée sans `allow-same-origin`, l'origine du
document est opaque et l'interprétation de `'self'` varie selon les
navigateurs. Elle n'est ajoutée que si `Host` est exactement
`127.0.0.1:<port>`, forme déjà imposée par FD-WEB-003.

L'iframe porte `sandbox` **sans aucune permission** (ni `allow-scripts`, ni
`allow-forms`, ni `allow-same-origin`) et `title="Prévisualisation du Design"`.
Les boutons de preview (`type="button"`) n'ont aucun effet, et la preview ne
peut ni modifier le document parent ni naviguer.

### Modes

`desktop` (1440 px), `tablet` (768 px) et `mobile` (390 px), selon les presets
de `preview/responsive.py`. Les largeurs sont exprimées dans `shell.css`
(`.preview-frame--desktop`, `--tablet` et `--mobile`, avec
`max-width: 100%`) et non par `wrap_preview_html`, qui produit un style
inline interdit par la CSP. Un test vérifie que ces largeurs restent alignées
sur `PREVIEW_VIEWPORTS`.

Le mode se choisit par des liens GET (« Desktop », « Tablette », « Mobile »,
le mode actif portant `aria-current`) et se conserve par le paramètre
`preview` de `/editor`. Il est omis pour `desktop`, si bien que les URL
historiques restent valides. Les liens de l'arbre le conservent. Chaque
formulaire d'action porte un champ `preview` **facultatif** : c'est le seul
champ hors de l'ensemble exact de chaque action ; il est validé (400 si
inconnu) et repris dans la redirection 303.

### Mise à jour

Aucun état ni rafraîchissement : chaque action suit
`POST → write_design → 303 → GET /editor`, et l'iframe recharge
`/editor/preview`, qui relit le Design enregistré. Un no-op ne réécrit rien,
et la preview reste identique.

Depuis FD-INTERACT-006, les formulaires de la preview reflètent la structure
générée : `<input>` issus de `FieldDefinition` (libellé englobant,
`required`) et `<button type="submit">Libellé</button>`, toujours sans
`action`, `method`, `hx-*` ni valeur. Voir
[static-preview.md](../preview/static-preview.md).

### Limites connues

- Données fictives : les booléens valent `true` (les blocs conditionnés sont
  visibles) et les listes ont trois éléments (les `empty_state` ne sont
  généralement pas visibles). Il n'y a pas de bascule dans ce ticket.
- Pas de Tailwind compilé, de backend réel, de JavaScript ni de HTMX.

## Définition de champ — FD-INTERACT-002

`set_field_definition(design, *, path, field: FieldDefinition | None)`, dans
`editor/properties.py`, suit le contrat des autres propriétés : une seule
propriété est modifiée, `None` la supprime (sur tout bloc, pour réparer un
Design), une valeur identique est un no-op, et le résultat est revalidé.

- La définition n'est acceptée que sur un bloc `field`, sinon
  `editor.field_not_supported`.
- La valeur doit être une `FieldDefinition` ; un dict ou un objet qui lui
  ressemble est refusé (`editor.invalid_field`). Elle est copiée, jamais
  conservée par référence.
- Unicité : `validate_form_fields` est appliqué à une projection du
  formulaire parent réduit à ses champs directs, le champ édité **placé en
  dernier**. Un nom déjà porté par un frère donne donc
  `editor.duplicate_field_name`, quel que soit l'ordre réel. Les erreurs
  préexistantes des autres champs sont ignorées.

La définition n'est jamais perdue par les autres mutations : props, classes,
condition, binding du formulaire et déplacement la conservent (testé par
l'API et par le serveur Web réel). L'éditeur Web n'a pas encore de contrôle
dédié pour `field` : il conserve la définition sans l'afficher.

## Bouton de soumission — FD-INTERACT-004

`set_submit_definition(design, *, path, submit: SubmitDefinition | None)`,
dans `editor/properties.py`, suit le contrat des autres propriétés : `None`
supprime la définition (sur tout bloc, pour une correction progressive), une
valeur identique est un no-op, et seule une instance de `SubmitDefinition`
est acceptée (`editor.invalid_submit` sinon, objet ressemblant compris).

Les règles sont celles de `validate_submit_buttons`, appliquées à une
projection réduite au bouton et à **son seul parent direct** : une erreur
ailleurs (et même sur le parent) ne bloque pas l'édition.

| Code | Cas |
|---|---|
| `editor.submit_not_supported` | bloc autre qu'un `button` (page comprise) |
| `editor.submit_conflicting_action` | bouton qui a déjà un `binding` |
| `editor.submit_outside_form` | bouton qui n'est pas enfant direct d'un `form` |

`submit` est conservé par les autres opérations : props, classes Tailwind,
condition, ajout, suppression et déplacement (testé par l'API et par le
serveur Web réel). `move_design_block` n'est pas élargi : un submit peut être
déplacé hors de son formulaire, ce que la validation signale ensuite.

## Preview statique et preview réelle — FD-REALPREVIEW-004

L'éditeur affiche deux zones distinctes :

- **Prévisualisation indicative** (FD-EDITOR-006) : rendu structurel du Design
  avec des données fictives, sans exécuter le projet, dans une iframe
  `sandbox` vide. Elle est inchangée.
- **Preview réelle** : l'application Forge du projet réellement exécutée,
  rendant le template **enregistré sur disque**, et non le Design en mémoire.

La preview réelle n'est jamais lancée automatiquement, ni à l'ouverture de
l'éditeur ou d'un projet, ni après une modification. Elle n'est proposée que
si une route GET publique, statique et unique rend le template du contrat du
Design ; sinon, la raison est affichée. Avant le bouton « Démarrer la preview
réelle », l'avertissement suivant est affiché :

> La preview réelle exécute le projet Forge sélectionné et peut déclencher ses
> effets de bord habituels.

Une fois démarrée, la page reste sur une origine dédiée (proxy local), dans
une iframe qui n'autorise que les scripts et sa propre origine. Formulaires,
popups et navigation de l'éditeur sont bloqués, et le proxy refuse toute
méthode autre que GET/HEAD. « Arrêter la preview réelle » arrête le proxy
puis l'application. En cas d'échec, l'erreur et les derniers logs sont
affichés, avec « Démarrer à nouveau ». Le contrat complet est dans
[docs/preview/real-preview-contract.md](../preview/real-preview-contract.md).
