# Éditeur structurel — FD-EDITOR-001

Premières mutations contrôlées d'un `DesignFile` : **ajouter** et **supprimer**
un bloc. L'éditeur est un moteur en mémoire, réutilisable par une future UI :
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
| `editor.depth_limit` | le nouveau bloc dépasserait `MAX_DESIGN_DEPTH` |
| `editor.root_not_removable` | `path=()` en suppression |
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
automatiques, pas de Web, HTMX, JavaScript ni Tool. Pas de déplacement
(FD-EDITOR-002), d'édition de propriétés, de bindings, de `visible_if` ni de
colonnes.
