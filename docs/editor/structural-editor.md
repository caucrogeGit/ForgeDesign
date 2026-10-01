# Éditeur structurel — FD-EDITOR-001, FD-EDITOR-002

Mutations contrôlées d'un `DesignFile` : **ajouter**, **supprimer** et
**déplacer** un bloc. L'éditeur est un moteur en mémoire, réutilisable par une future UI :
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
automatiques, pas de Web, HTMX, JavaScript ni Tool. Pas d'édition de
propriétés, de bindings, de `visible_if` ni de colonnes (FD-EDITOR-003).

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
