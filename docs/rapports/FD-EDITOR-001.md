# Rapport — FD-EDITOR-001

## Ticket et objectif

Premières mutations structurelles d'un `DesignFile` en mémoire : ajouter un
bloc en fin de liste et supprimer un bloc avec son sous-arbre. Le service
revalide l'entrée, localise le nœud, applique `can_contain` et produit un
nouveau `DesignFile` valide, sans jamais modifier l'entrée. Ouverture de la
phase Editor.

## État Git initial

`main` synchronisée avec `origin/main` à `ed14e17` — FD-SAFEWRITE-003, phase
SAFEWRITE close. Seule modification préexistante :
`docs/rapports/FD-CONTRACT-001.md`, préservée hors commit.

## API publique

`forge_design.editor` exporte `NodePath`, `DesignEditIssue`,
`DesignEditResult`, `append_design_block(design, *, parent, block_type)` et
`remove_design_block(design, *, path)`. Les dataclasses de résultat sont
gelées. Aucun Tool n'est enregistré (5 Tools) et `web/` n'est pas modifié.

## NodePath

`tuple[int, ...]` : `()` désigne la page, `(0, 2)` le troisième enfant du
premier enfant. Le format des diagnostics existants n'est pas modifié. Aucun
identifiant de nœud n'est ajouté au Design. Les indices des frères suivants
changent après une édition (documenté).

## Résolution des nœuds

`_resolve` est appliqué au dump revalidé. `editor.invalid_path` est émis pour
tout ce qui n'est pas un tuple d'`int` stricts : `bool` est refusé par
`type(index) is not int`, ainsi que `str`, `list`, `float`, `None` ou un `int`
nu. `editor.path_not_found` est émis pour un indice négatif ou hors bornes, à
toute profondeur, y compris sous une feuille sans enfants ; le diagnostic porte
le préfixe du chemin introuvable.

## Ajout

`append_design_block` ajoute `{"type": block_type}` en dernier enfant. Aucun
champ n'est inventé (testé à l'égalité de dict). `affected_path = (*parent, N)`.
L'ordre existant est conservé. Un parent sans clé `children` en reçoit une.
Refus : `unknown_block_type` (type hors `DesignNodeType`, casse comprise),
`root_type_not_insertable` (`page`), `child_not_allowed`, `node_limit`,
`depth_limit`.

## Suppression

`remove_design_block` supprime le bloc et tous ses descendants, sans
réinsertion. `affected_path` est le chemin du parent (`()` pour un enfant de la
page). La racine est refusée (`root_not_removable`). Si un bloc autre que la
page perd son dernier enfant, sa clé `children` est omise : un ajout suivi d'une
suppression redonne exactement le dump initial (testé). La page garde
`children: []`.

## Règles d'imbrication

Seule source : `nesting.can_contain`, appelée par le module au moment de
l'opération. Un espion le prouve, et `ALLOWED_CHILDREN` est absent du module.
Les cas nominaux page→section, section→card, card→title, form→field,
table→empty_state sont testés. Les refus page→card, title→text, table→text et
grid→card aussi, ainsi que les 7 feuilles (`title`, `text`, `button`, `field`,
`alert`, `empty_state`, `grid`) contre 6 types d'enfants chacune, chaque feuille
étant construite par l'éditeur sous un parent valide.

## Bornes

Les bornes existantes sont réutilisées, sans limite concurrente.
`MAX_DESIGN_NODES` compte la racine, comme `validate_design_nesting` :
`MAX - 1` nœuds permettent un ajout, `MAX` le refusent (`node_limit`), et la
suppression reste possible à la limite. `MAX_DESIGN_DEPTH` (page à 0) : un ajout
à la profondeur 128 est accepté, à 129 il est refusé (`depth_limit`).

**Constat.** La matrice `ALLOWED_CHILDREN` n'a aucun cycle : un Design valide
ne dépasse pas une profondeur d'environ 5, et la frontière de profondeur est
inatteignable avec les règles réelles. Elle est testée en élargissant
`can_contain` dans le test ; la borne est conservée pour le cas où les règles
évolueraient.

## Immutabilité

L'entrée n'est jamais mutée : dump comparé et identité des listes conservée
après cinq opérations, refus compris. Le résultat est construit par
`model_validate` à partir d'une copie issue du dump. Il ne partage aucune liste
avec l'entrée : vider ou étendre les listes du résultat laisse l'original
intact, et aucun nœud n'est partagé. Il n'y a pas de `deepcopy`. Les champs
`version`, `view`, `source_contract`, ainsi que les `props`, `binding`,
`visible_if` et `columns` des autres nœuds, restent identiques.

## Revalidation

- **Avant édition.** Parcours itératif borné (types de nœuds, nombre,
  profondeur), puis `model_dump(exclude_unset=True)`, `model_validate` et
  `validate_design_nesting`. Une liste interne mutée avec un non-nœud, une
  liste cyclique ou un Design mal imbriqué donnent `editor.invalid_design`.
  Le parcours borné précède le dump, comme dans `generate/simple.py`, car un
  cycle ferait boucler la sérialisation.
- **Après édition.** `model_validate` puis `validate_design_nesting`, sinon
  `editor.invalid_result`. Ce garde, inatteignable avec les règles réelles,
  est testé par une incohérence simulée. Sans ce test, sa suppression n'était
  détectée par aucun test (vérifié par mutation).

## Pureté

Pendant un scénario complet, `open`, `os.open`, `os.stat`, `socket.socket` et
`subprocess.Popen` sont bloqués. Le module ne référence ni `read_design`,
`write_design`, `snapshot_template`, `write_generated_template`, `os`,
`Path`, ni la génération ou le diff.

## Déterminisme

Même entrée et même opération donnent un `DesignEditResult` égal : Design,
issues et `affected_path`.

## Absence d'I/O

Aucune lecture, écriture, sauvegarde, preview, génération ni diff. La
sauvegarde reste une action explicite de `write_design`.

## Documentation

- [docs/editor/structural-editor.md](../editor/structural-editor.md)
- [docs/02-architecture.md](../02-architecture.md) : section « Éditeur
  structurel — FD-EDITOR-001 », avec le schéma demandé.

## Fichiers créés

- `forge_design/editor/__init__.py`
- `forge_design/editor/structure.py`
- `tests/test_editor_structure.py`
- `docs/editor/structural-editor.md`
- `docs/rapports/FD-EDITOR-001.md`

## Fichiers modifiés

- `pyproject.toml` : package `forge_design.editor`.
- `docs/02-architecture.md`

Non modifiés : `design/models.py`, `design/nesting.py`, `design/io.py`,
`generate/`, `safewrite/`, `contracts/`, `preview/`, `web/`, `tools/`,
`app.py`, le contrat de stockage, le JavaScript.

## Tests ajoutés

`tests/test_editor_structure.py` : 68 cas. Racine, 4 chemins imbriqués,
6 chemins introuvables, 8 types de chemin invalides, 5 ajouts nominaux, ordre,
4 ajouts interdits, 7 feuilles, `page`, 5 types inconnus, absence de champs
inventés, parent sans `children`. Suppressions : feuille, conteneur, premier,
dernier, omission de `children`, racine, autres nœuds intacts. Validité en
chaîne, `can_contain` espionné, Design initial invalide, entrée mutée, entrée
cyclique, non-Design, borne de nœuds, borne de profondeur, résultat invalide,
immutabilité, indépendance du résultat, gel, pureté, déterminisme, imports,
exports et registre, scénario complet.

Un test initialement écrit (`test_leaves_refuse_children`) a été retiré : il
passait à cause d'un Design initial invalide, pas de la règle testée.

Vérification par mutation (chaque garde retiré dans une copie restaurée
ensuite) : `can_contain`, nesting initial, nesting final (après ajout du test
dédié), borne de nœuds, borne de profondeur, `bool` refusé, comptage préalable,
omission de `children`, `page` insérable, racine supprimable. Toutes les
mutations sont détectées.

## Validations ciblées

| Commande | Résultat |
|---|---|
| `pytest -q tests/test_editor_structure.py` | 68 réussis |
| `pytest -q tests/test_editor_structure.py tests/test_design_models.py tests/test_design_nesting.py tests/test_design_schema.py tests/test_design_io.py tests/test_design_bindings.py tests/test_tool_registry.py` | 641 réussis |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` / `ruff format --check .` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |

Une seule suppression de diagnostic Pyright reste dans le code produit, à
l'endroit où `isinstance(path, tuple)` réduit le type à `tuple[Unknown, ...]`.
L'annotation explicite `tuple[object, ...]` en remplace deux.

## Packaging

Wheel `forge_design-0.1.0.dev0-py3-none-any.whl` dans `tmp/wheels`, SHA-256
`c0d0d53c56100adc13132793e964371897a6d054c940fb8deaa2f9a012f49cad`. Elle
contient `forge_design/editor/{__init__,structure}.py` et aucun fichier de
`tests/` ni de `tmp/`. Aucune dépendance nouvelle.

## Installation réelle

Installation `--no-deps --no-index --target` temporaire ; `python -I` depuis un
cwd temporaire, avec vérification de l'origine installée. Scénario avec `open`
et `os.open` bloqués : Design vide, ajout de `section` → `(0,)`, ajout de `card`
dans la section → `(0, 0)`, suppression de la carte → `(0,)`. Le résultat final
est `page[section]` et le Design d'origine est inchangé.

## Tests non exécutés

- Suite globale : non lancée, conformément au ticket, en l'absence de régression
  transversale.
- `pip check` : aucune dépendance nouvelle. Node : aucun JavaScript. MkDocs :
  aucune configuration.

## Limites restantes

- Ajout en fin de liste seulement ; pas de déplacement (FD-EDITOR-002).
- Indices instables après édition ; aucun identifiant de nœud.
- `depth_limit` inatteignable avec la matrice actuelle (aucun cycle).
- La revalidation complète (dump + Pydantic + nesting) à chaque opération est
  en O(n) : un choix d'exactitude, sans optimisation prématurée.
- Un parent vidé perd sa clé `children` ; un `children: []` explicite d'origine
  n'est donc pas restitué après ajout puis suppression.

## État Git final

Un commit sur `main`, rapport inclus, sans push.
Message : `feat: ajouter les mutations structurelles Design (FD-EDITOR-001)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Hash :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-EDITOR-001.md
```
