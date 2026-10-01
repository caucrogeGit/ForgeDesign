# Rapport — FD-EDITOR-002

## Ticket et objectif

Déplacer un bloc existant, avec tout son sous-arbre, en dernier enfant d'un
autre parent, dans un `DesignFile` en mémoire.

## État Git initial

`main` synchronisée avec `origin/main` à `d6d8c87` — FD-EDITOR-001. Seule
modification préexistante : `docs/rapports/FD-CONTRACT-001.md`, préservée hors
commit.

## API publique

`move_design_block(design, *, source, destination) -> DesignEditResult`,
ajoutée à `forge_design/editor/structure.py` (pas de second moteur) et
exportée par `forge_design.editor`. Le remapping reste interne. Aucun autre
export, aucun Tool (5 Tools), `web/` non modifié.

Réutilisation : `_check_path`, `_revalidated`, `_resolve`, `_rebuilt`,
`_refusal`. La suppression et sa normalisation de `children` sont factorisées
dans `_detach`, désormais partagé par `remove_design_block` et le déplacement.
Les 68 tests d'EDITOR-001 restent verts après cette factorisation.

## Sémantique source/destination

`source` est le bloc déplacé et `destination` le nouveau parent ; la page `()`
est une destination valide. Les deux chemins sont interprétés **dans l'arbre
initial**. Séquence : validation des chemins, `source=()` refusée,
revalidation de l'entrée, résolution des deux chemins, refus d'une destination
dans la source, no-op, `can_contain`, profondeur future, retrait (`_detach`),
remapping, résolution de la destination ajustée, append, `_rebuilt`.

`affected_path = (*destination ajustée, nombre d'enfants avant l'append)`.

## Préservation du sous-arbre

Le dict complet issu du dump est retiré puis rattaché : `type`, `binding`,
`visible_if`, `props`, `columns`, `children` et tous les descendants. Il n'y a
pas de clone simplifié. Les tests comparent le dict du bloc avant et après :
une carte avec `visible_if`, `props` et deux enfants, et une table avec
`binding`, `columns` et `empty_state`.

## Règles d'imbrication

`nesting.can_contain(type destination, type déplacé)` est la seule source
(espion). Les refus testés : `text` vers une `table`, `title` vers une `table`,
`card` vers `text`, `card` vers la page.

## Remapping des chemins

`_adjust_path_after_removal(path, removed)` : seul l'indice du niveau de
`removed` peut changer. Il baisse de 1 si `path` partage le parent de
`removed` et désigne un frère suivant. Tout autre chemin est inchangé : frère
précédent, autre branche, ancêtre, chemin plus court, racine. Un `path` situé
dans `removed` lève `ValueError` (cas déjà refusé en amont).

Tests :
- 12 cas directs sur le helper, dont `(2, 0, 1)` après retrait de `(0,)`
  donnant `(1, 0, 1)` ;
- 3 cas « dans le sous-arbre retiré » ;
- 5 déplacements de bout en bout : source avant la destination (au premier
  niveau et plus profond), source après, autre branche, et destination
  profonde après un frère retiré.

**Constat.** Avec la matrice réelle, aucun bloc de la page (section, table) ne
peut aller à la profondeur 3. Le cas `(0,)` → `(2, 0, 1)` du ticket est donc
testé de bout en bout avec `can_contain` élargi, et directement sur le helper.

## Déplacement même parent

`[A, B, C]` donne `[B, C, A]` en déplaçant A et `[A, C, B]` en déplaçant B.
Avec quatre enfants de types différents, le bloc déplacé est vérifié identique
à sa nouvelle position. Le parent ne change pas de chemin, car il est plus
court que la source.

## No-op

Si la source est déjà le dernier enfant de la destination :
`DesignEditResult(design reçu, False, source, ())`. Aucun nouveau `DesignFile`
(identité vérifiée), dans une section comme à la racine.

## Cycles interdits

`destination[:len(source)] == source` est vérifié avant tout retrait et donne
`editor.destination_inside_source` pour la source elle-même, un enfant direct
ou un descendant profond.

## Profondeur

`len(destination) + 1 + hauteur relative ≤ MAX_DESIGN_DEPTH`, sinon
`editor.depth_limit`. La hauteur relative est calculée de façon itérative et
bornée. Le test, avec règle élargie, déplace un sous-arbre de hauteur 27 :
accepté sous une destination de profondeur 100, refusé à 101. Une mutation qui
ignore la hauteur est détectée.

## Validation finale

`_rebuilt` (Pydantic + nesting) est appliqué à tout déplacement réussi. Une
incohérence simulée (nesting refusé au second appel) donne
`editor.invalid_result`, avec l'entrée rendue intacte.

## Immutabilité

Le dump de l'entrée et le contenu des listes (enfants de la racine, de la
section source, de la carte déplacée, de la section destination) sont
inchangés après un succès et après un refus. Vider les listes du résultat
n'affecte pas l'entrée.

## Pureté

`open`, `os.open`, `socket.socket` et `subprocess.Popen` sont bloqués pendant
les déplacements. Aucun import d'I/O dans le module (test d'EDITOR-001
toujours valide).

## Déterminisme

Même Design, même source et même destination donnent un résultat égal
(Design, `affected_path`, issues), en succès comme en refus.

## Compatibilité EDITOR-001

Les 68 tests d'ajout et de suppression passent sans modification.

## Documentation

- [docs/editor/structural-editor.md](../editor/structural-editor.md) : section
  « Déplacement — FD-EDITOR-002 » (sémantique, schéma, table de remapping,
  même parent, no-op, refus, indices non stables) et tableaux d'API et de
  diagnostics complétés.
- [docs/02-architecture.md](../02-architecture.md) : une phrase, l'éditeur
  supporte append, remove et move.

## Fichiers créés

- `docs/rapports/FD-EDITOR-002.md`

## Fichiers modifiés

- `forge_design/editor/structure.py`
- `forge_design/editor/__init__.py`
- `tests/test_editor_structure.py` (tests étendus dans le fichier existant)
- `docs/editor/structural-editor.md`
- `docs/02-architecture.md`

Non modifiés : `design/`, `generate/`, `safewrite/`, `contracts/`, `preview/`,
`web/`, `tools/`, `app.py`, `limits.py`, `pyproject.toml`, le contrat de
stockage, le JavaScript.

## Tests ajoutés

53 cas dans `tests/test_editor_structure.py` (121 au total) : entre sections,
sous-arbre de table, même parent (2 + ordre A/B/C), no-op section et racine,
12 + 3 cas de remapping direct, 5 remappings de bout en bout, 4 cycles,
racine, vers la racine (table, section, carte refusée), 3 parents
incompatibles, 7 chemins invalides × source/destination, 3 chemins
introuvables, profondeur, Design initial invalide, résultat invalide,
immutabilité, indépendance, pureté et déterminisme, `can_contain` espionné,
export.

Deux attentes de test étaient fausses à la première exécution (ordre après
déplacement dans le même parent) ; le code était correct et les attentes ont
été corrigées.

Vérification par mutation (copie restaurée ensuite) : contrôle de cycle (4
échecs), no-op (2), `can_contain` (4), borne de profondeur (1), hauteur ignorée
(1), absence de remapping (3), remapping sans décrément (8), préfixe ignoré
(2), `children` vide conservé (4), racine déplaçable (1). Toutes les mutations
sont détectées.

## Validations ciblées

| Commande | Résultat |
|---|---|
| `pytest -q tests/test_editor_structure.py` | 121 réussis |
| `pytest -q tests/test_editor_structure.py tests/test_design_models.py tests/test_design_nesting.py tests/test_design_schema.py tests/test_tool_registry.py` | 553 réussis |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` / `ruff format --check .` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |

## Tests non exécutés

- Suite globale : non lancée, la phase Editor n'est pas close.
- Wheel : non nécessaire, `forge_design.editor` est déjà packagé ; export
  couvert par test.
- Node, MkDocs : non concernés.

## Limites restantes

- Ajout en fin de liste seulement ; pas de position arbitraire ni de
  réordonnancement par index.
- Indices non stables après un déplacement ; aucun identifiant de nœud.
- `depth_limit` inatteignable avec la matrice actuelle.
- Revalidation complète en O(n) à chaque opération.

## État Git final

Un commit sur `main`, rapport inclus, sans push.
Message : `feat: déplacer les blocs Design (FD-EDITOR-002)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Hash :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-EDITOR-002.md
```
