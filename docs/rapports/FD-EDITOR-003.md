# Rapport — FD-EDITOR-003

## Ticket et objectif

Configurer en mémoire les propriétés déjà prévues par Design v0.1 —
`binding`, `visible_if`, `props`, `columns` — sans modifier le schéma, avec
validation contractuelle ciblée et toujours sans I/O, sauvegarde, Web ni
JavaScript.

## État Git initial

`main` synchronisée avec `origin/main` à `4d60940` — FD-EDITOR-002. Seule
modification préexistante : `docs/rapports/FD-CONTRACT-001.md`, préservée hors
commit.

## API publique

Quatre fonctions exportées par `forge_design.editor`, une propriété chacune :
`set_design_binding`, `set_design_visibility`, `set_design_props` et
`set_table_columns`. Elles réutilisent exactement `DesignEditResult`,
`DesignEditIssue` et `NodePath`. Aucun Tool (5 Tools), `web/` non modifié.

Organisation : `properties.py` (configuration d'un nœud) à côté de
`structure.py` (arbre). Les helpers communs (`NodePath`, résultats, `Refused`,
`check_path`, `revalidated`, `resolve`, `rebuilt`, `refusal`) sont extraits
dans le module interne `editor/_tree.py`, sous des noms publics, comme
l'autorise le §119. Les importer en tant que noms privés aurait cassé Pyright
strict (`reportPrivateUsage`). `structure.py` les réimporte, son API est
inchangée, et les 121 tests d'EDITOR-001/002 passent sans modification.

## Binding

`set_design_binding(design, *, path, binding, contract)`. Les règles sont
celles de `design/bindings.py` : `title` et `text` → `string`, `table` →
`list`, `button` → action ; aucune table recopiée (absence de `_BINDING_RULES`
dans le module testée). `design.binding.unsupported` devient
`editor.binding_not_supported` (section, carte, page) ; les autres
diagnostics deviennent `editor.invalid_binding` (variable inconnue, mauvais
type, action inconnue). `""`, les nombres, les octets ou une liste donnent
`editor.invalid_binding`. Une sous-classe de `str` est normalisée en `str`
exact.

## Visible if

`set_design_visibility(...)` : variable `boolean` de `contract.context`
obligatoire, sur tout bloc, page comprise, sans restriction ajoutée.
`validate_conditional_bindings` est la source ; tout écart donne
`editor.invalid_condition`.

## Props

`set_design_props(design, *, path, props)`. Tout `Mapping` est copié en `dict`.
Pydantic applique le contrat Design : clés non vides, valeurs scalaires
finies, pas de `null`, de liste ni de dict imbriqué, pas de NaN ni d'infini,
pas de clé non-chaîne. Tout refus donne `editor.invalid_props`. Les props ne
sont pas limitées à `tag` et `class` : `data-role`, `aria-label` et des
valeurs `bool`, `int` ou `float` sont acceptées.

## Colonnes

`set_table_columns(...)`. Seulement sur une `table`, sinon
`editor.columns_not_supported` (carte, section, page). Chaque élément doit
être une `TableColumn`, copiée par `model_dump` puis revalidée. Au plus
`MAX_TABLE_COLUMNS` colonnes (limite exacte acceptée, +1 donnant
`editor.column_limit`). `validate_table_bindings` décide du reste :
- statut autre que `resolved` ou `fields_unavailable` (binding absent,
  variable inconnue, non-`list`) : `editor.invalid_table_binding`, même pour
  `[]` ;
- `fields` absents avec des colonnes non vides : `editor.invalid_table_binding`,
  alors que `[]` est accepté ;
- champ non déclaré : `editor.invalid_table_column`.

Le code `editor.column_limit` s'ajoute aux codes minimaux du ticket pour
distinguer la borne d'une colonne invalide.

## Suppression de propriété

`None` supprime la clé, et le JSON l'omet. Aucune validation contractuelle
n'est faite à la suppression : effacer un binding présent sur une section
répare le Design. Les colonnes peuvent être effacées sur tout bloc ; sur un
bloc qui n'en a pas, c'est un no-op.

## No-op

Même valeur exacte : `DesignEditResult(design reçu, False, path, ())`, testé
pour les quatre fonctions, en valeur comme en `None`. La comparaison est
**stricte au sens JSON** : en Python, `{"n": 1} == {"n": True} == {"n": 1.0}`,
et une comparaison naïve aurait traité un changement de type comme un no-op.
Les types et l'ordre des clés sont donc comparés (4 cas testés).

## Validation Pydantic

Après mutation de la copie : `DesignFile.model_validate`, qui donne le code
propre à la propriété en cas de refus. Viennent ensuite `rebuilt` (Pydantic et
nesting, sinon `editor.invalid_result`, testé par incohérence simulée) puis la
validation contractuelle. Tout `changed=True` est un Design valide et bien
imbriqué.

## Validation contractuelle ciblée

Les règles de binding, de condition et de colonnes ne dépendent que du bloc et
du contrat. Les validateurs existants sont donc appliqués à un **Design
projeté** qui ne porte que le bloc édité, sans ses enfants : la page elle-même
pour `()`, sinon une page contenant ce seul bloc. Les validateurs ne
contrôlent pas l'imbrication, ce qui rend la projection sûre.

Pourquoi pas un filtrage des diagnostics globaux ? À la troncature, les
validateurs **retirent le dernier diagnostic** pour placer leur marqueur ; ce
diagnostic pouvait être celui du bloc édité, et une erreur ailleurs aurait pu
tronquer l'analyse avant lui. La projection élimine les deux risques.
`editor.analysis_truncated` reste émis si un validateur signale une
troncature (testé par simulation) ; en pratique, le nombre de colonnes est
borné en amont.

Le contrat est lui aussi revalidé (`editor.invalid_contract`) : il est
`frozen`, mais ses dictionnaires sont mutables (testé avec un contexte muté).
L'avertissement de sérialisation Pydantic sur un contrat muté est désactivé
(`warnings=False`) ; le refus reste porté par la revalidation.

## Erreurs préexistantes ailleurs

Testé : binding invalide sur un bloc A et édition du bloc B ; condition
invalide ailleurs ; table aux colonnes invalides et édition d'une autre table ;
plus de `MAX_DESIGN_ISSUES` bindings invalides ailleurs, le validateur global
étant **tronqué**, et pourtant l'édition du dernier bloc réussit. Une mutation
validant le Design entier au lieu de la projection fait échouer 2 tests.

## Immutabilité

Le Design reçu (dump, listes, props) et le contrat partagé sont inchangés
après quatre succès et un refus. Le mapping ou la liste de l'appelant, modifié
après l'appel, n'affecte pas le résultat.

## Pureté

Pendant un scénario complet, `open`, `os.open`, `Path.read_text`,
`write_text`, `read_bytes`, `write_bytes`, `socket.socket` et
`subprocess.Popen` sont remplacés par des enregistreurs : aucun appel. Le
module ne référence aucun lecteur, writer, générateur, diff ni preview.

Un premier `test_pure` bloquait aussi `os.stat` et `Path.open`, ce qui faisait
planter le rapport d'erreur de pytest et masquait la vraie cause. Les blocages
sont maintenant levés avant les assertions.

## Déterminisme

Quatre opérations, succès et refus confondus, rejouées deux fois : résultats
égaux.

## Compatibilité EDITOR-001/002

`tests/test_editor_structure.py` : 121 réussis, sans modification, après
l'extraction de `_tree.py`.

## Documentation

- [docs/editor/structural-editor.md](../editor/structural-editor.md) : section
  « Configuration des propriétés — FD-EDITOR-003 » (quatre API, `None`, no-op
  strict, validation ciblée, règles par propriété, limites).
- [docs/02-architecture.md](../02-architecture.md) : schéma append / remove /
  move → configure properties, et paragraphe.

## Fichiers créés

- `forge_design/editor/_tree.py`
- `forge_design/editor/properties.py`
- `tests/test_editor_properties.py`
- `docs/rapports/FD-EDITOR-003.md`

## Fichiers modifiés

- `forge_design/editor/structure.py` : helpers déplacés dans `_tree.py`,
  comportement inchangé.
- `forge_design/editor/__init__.py` : exports.
- `docs/editor/structural-editor.md`
- `docs/02-architecture.md`

Non modifiés : `design/` (modèles, schéma, validateurs), `generate/`,
`safewrite/`, `preview/`, `web/`, `tools/`, `app.py`, `limits.py`,
`pyproject.toml`, le contrat de stockage, le JavaScript.

## Tests ajoutés

`tests/test_editor_properties.py` : 103 cas.
- Binding : 4 valides, 6 invalides, 3 non supportés, 4 valeurs invalides,
  effacement, réparation, no-op, sous-classe.
- Condition : 5 valides, page comprise ; 4 invalides ; 3 valeurs invalides ;
  effacement et no-op.
- Props : 5 valides, `{}`, 9 invalides, effacement et no-op, 4 détections
  strictes, copie, `MappingProxyType`.
- Colonnes : ordre, champ inconnu, sans binding (2), non-`list` (2), `fields`
  absents, `[]` distinct de l'absence, 3 types non supportés, effacement no-op,
  limite, 4 valeurs invalides, no-op et copie.
- Isolation de propriété (2), autres nœuds intacts, 4 cas d'erreur ailleurs
  dont la troncature globale, troncature simulée, politique de page, chemins
  introuvables et invalides × 4 fonctions, contrat invalide et muté, Design
  invalide, résultat invalide, immutabilité, pureté, déterminisme, imports,
  exports et registre, scénario complet du critère de fin.

**Défaut de test corrigé.** La première fixture plaçait `title` et `button`
directement sous une `section`, ce que la matrice interdit. L'éditeur la
refusait correctement (`editor.invalid_design`), et 65 tests échouaient pour
cette raison. La fixture est maintenant valide (`section > card > …`), des
constantes de chemin nommées sont utilisées, et `design()` vérifie
l'imbrication de chaque fixture.

Vérification par mutation (copie restaurée ensuite) : comparaison non stricte
(3 échecs), Design entier au lieu de la projection (2), binding non validé
(11), condition non validée (5), garde table (4), statut de table ignoré (4),
limite de colonnes (1), absence de no-op (5), props non copiées (1, après ajout
du test `MappingProxyType` ; elle survivait auparavant), contrat non revalidé
(1), troncature ignorée (1), `unsupported` non distingué (4). Toutes les
mutations sont détectées.

## Validations ciblées

| Commande | Résultat |
|---|---|
| `pytest -q tests/test_editor_properties.py` | 103 réussis |
| `pytest -q tests/test_editor_structure.py tests/test_editor_properties.py` | 224 réussis |
| idem + `test_design_bindings.py test_conditional_bindings.py test_table_bindings.py test_design_models.py test_design_nesting.py test_tool_registry.py` | 779 réussis |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` / `ruff format --check .` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |

## Tests non exécutés

- Suite globale : non lancée, la phase Editor n'est pas close.
- Wheel : non nécessaire, `forge_design.editor` est déjà packagé (les nouveaux
  modules en font partie) ; exports couverts par test.
- Node, MkDocs : non concernés.

## Limites restantes

- Changer le binding d'une table ne revalide pas ses colonnes existantes (une
  opération, une propriété).
- La projection repose sur le fait que les règles contractuelles sont locales
  au bloc ; une future règle inter-blocs exigerait de revoir cette stratégie.
- Pas d'édition du type d'un bloc ; pas de nouvelle propriété ; pas d'UI.

## État Git final

Un commit sur `main`, rapport inclus, sans push.
Message : `feat: configurer les propriétés Design (FD-EDITOR-003)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Hash :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-EDITOR-003.md
```
