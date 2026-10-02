# Rapport — FD-INTERACT-002

## Ticket et objectif

Définir dans Design v0.1 la représentation minimale d'un futur formulaire :
quelle action pour `form`, et pour chaque `field` quel nom, quel type de
contrôle, quel libellé, obligatoire ou non. Ce ticket couvre le modèle, le
schéma, la validation sémantique et l'édition en mémoire. Aucun `<form>` ni
`<input>` n'est généré.

## État Git initial

`main` synchronisée avec `origin/main` à `f1c079f` — FD-INTERACT-001. Seule
modification suivie préexistante : `docs/rapports/FD-CONTRACT-001.md`,
préservée hors commit.

## Décision de modèle

Les informations d'un champ ne sont pas visuelles : elles forment une
propriété explicite `field: FieldDefinition` de `_NodeProperties` (facultative
au niveau générique) et non des `props`. Aucun changement de version
(`0.1`) ; aucune modification de `contracts/models.py`.

## Form binding

Une ligne ajoutée à la table de règles existante de `design/bindings.py` :
`form → action`. Action connue : valide ; action inconnue, ou contrat sans
actions : `design.binding.unknown_action` ; `form` sans binding : rien
signalé. Deux tests historiques qui figeaient `form` en `unsupported` sont
mis à jour, conformément au §6.

## FieldDefinition

`FieldDefinition(name, input_type, label?, required?)`, avec `extra="forbid"`,
`strict` et `frozen` hérités du modèle Design. `null` est refusé sur les
champs facultatifs, comme ailleurs.

## Types de contrôle

`FieldInputType = Literal["text", "email", "password", "number", "date",
"checkbox"]`. `textarea`, `select`, `TEXT`… sont refusés.

## Nom de champ

`name` est une chaîne non vide **opaque**, sans regex HTML : `email`,
`contact.email`, `items[0].name` et `é` sont acceptés. Il n'est jamais déduit.
Le `binding` d'un `field` reste `design.binding.unsupported` (testé).

## Label

Facultatif, chaîne **non vide**. Le ticket écrivait `_Omissible[str]` ; une
chaîne vide aurait été ambiguë avec l'absence (« aucun libellé inventé ») et
contraire à la règle de tous les autres champs textuels du modèle. **Écart à
valider.**

## Required

Facultatif, booléen strict (`"yes"` et `1` sont refusés). `false` est
conservé distinct de l'absence dans le JSON (aller-retour testé).

## Validation sémantique

`design/form_fields.py` : `validate_form_fields(design) ->
FormFieldValidationResult(valid, issues, truncated)`, avec
`FormFieldIssue(code, message, location)`. Parcours préfixe itératif borné par
`MAX_DESIGN_NODES`, `MAX_DESIGN_DEPTH` et `MAX_DESIGN_ISSUES`, marqueur
`design.field.analysis_truncated` inclus dans la borne. Codes :
`missing_definition`, `unsupported_definition` (sur `text`, `form`,
`section`, `button` et la page) et `duplicate_name`. Les erreurs structurelles
restent à Pydantic, sans duplication. L'imbrication reste à
`validate_design_nesting`.

## Unicité des noms

Les noms sont uniques parmi les champs directs d'un même `form` ; deux
formulaires peuvent réutiliser un nom. Avec trois occurrences, deux
diagnostics sont émis, la première occurrence faisant référence.

## Compatibilité Design v0.1

Un Design sans bloc `field` est inchangé. Un ancien `field` sans définition
reste Pydantic-valide (chargeable par `read_design`) mais donne
`design.field.missing_definition` : la migration peut être progressive.

## Schéma

`design.schema.json` est mis à jour à la main : `$defs.FieldDefinition` (six
types, `additionalProperties: false`) et `DesignNode.properties.field`. Le
diff ne contient que des ajouts. Le test de concordance compare désormais
aussi `FieldDefinition` au schéma généré par Pydantic ainsi que l'ensemble des
`$defs` (hors `PropValue`, propre au schéma normatif).

## Editor

`set_field_definition(design, *, path, field)` dans `editor/properties.py`,
exporté par `forge_design.editor`, suit le contrat de FD-EDITOR-003 :

- `None` supprime la définition, sur tout bloc : effacer une définition
  posée par erreur sur un `form` répare le Design ;
- une définition non nulle n'est acceptée que sur un `field`, sinon
  `editor.field_not_supported` ;
- seule une instance `FieldDefinition` est acceptée, sinon
  `editor.invalid_field` (un dict, une chaîne, un nombre ou un objet qui lui
  ressemble avec `model_dump` sont refusés) ; elle est copiée et revalidée ;
- une valeur identique ou un double effacement sont des no-op.

**Unicité ciblée.** La projection d'EDITOR-003 (bloc seul) ne suffit pas, car
l'unicité dépend des frères. `_form_projection` réduit le formulaire parent à
ses champs directs et place le champ édité **en dernier** : un nom déjà porté
par un frère donne `editor.duplicate_field_name` quel que soit l'ordre réel
(testé dans les deux ordres). Les erreurs préexistantes des autres champs
(définition manquante, doublon entre frères) sont ignorées.

## Préservation des données

- Par l'API : `set_design_props` (valeur et effacement),
  `set_design_visibility`, `set_design_binding` sur le formulaire et
  `move_design_block` conservent la définition.
- Par le serveur Web réel, avec sauvegarde : props, `tailwind_add`, deux
  changements de condition, déplacement et binding du formulaire conservent
  les deux définitions (relues sur disque). L'ordre de déplacement est
  vérifié.

L'éditeur Web n'affiche pas encore la définition (§54, facultatif) et le
dossier `web/` n'est pas modifié.

## Génération reportée

`generate_simple_template` considère toujours `form` et `field` comme non
supportés (`generate.unsupported_block`), sans `<form>` ni `<input>` (testé).

## Preview reportée

`preview/` n'est pas modifié : un `field` reste
`<div data-forge-design-type="field"></div>`, et ni le nom ni le type n'y
apparaissent (testé).

## Fichiers créés

- `forge_design/design/form_fields.py`
- `tests/test_design_form_fields.py`
- `docs/rapports/FD-INTERACT-002.md`

## Fichiers modifiés

- `forge_design/design/models.py` : `FieldInputType`, `FieldDefinition`,
  `_NodeProperties.field`.
- `forge_design/design/design.schema.json`
- `forge_design/design/bindings.py` : règle `form → action`.
- `forge_design/design/__init__.py` : exports.
- `forge_design/editor/properties.py`, `forge_design/editor/__init__.py`
- `tests/test_design_schema.py`, `tests/test_design_models.py`,
  `tests/test_design_bindings.py`
- `docs/design/design-json.md`, `docs/editor/structural-editor.md`,
  `docs/02-architecture.md`

Non modifiés : `generate/`, `preview/`, `web/`, `safewrite/`, `tools/`,
`app.py`, `contracts/models.py`, `pyproject.toml`, le JavaScript.

## Tests ajoutés

`tests/test_design_form_fields.py` : 66 cas. Modèle : minimal, complet, 6 types,
4 noms libres, 15 définitions invalides, `false` distinct de l'absence,
aller-retour JSON et `null`, gel. Bindings : action valide, inconnue (2),
`form` sans binding, `field` binding. Validateur : valide, définition
manquante, 4 types non autorisés plus la page, doublon, deux formulaires,
triple doublon, troncature par diagnostics et par nœuds, pureté.
Génération et preview reportées. Éditeur : nominal avec préservation, clear et
no-op, 3 types refusés, réparation, 3 valeurs invalides, objet ressemblant,
doublon dans les deux ordres, autre formulaire, erreurs des frères ignorées,
copie, autres mutations. Web réel : 6 mutations conservent les définitions.
`tests/test_design_schema.py` : 1 test ajouté (`FieldDefinition` normatif).

**Défaut de test corrigé.** Le test de troncature par nœuds échouait parce
que le helper de fixture vérifie l'imbrication, elle-même tronquée au-delà de
la borne. Ce test construit donc son Design directement.

Vérification par mutation, lancée depuis le scratchpad avec restauration
vérifiée : définition manquante tolérée (2 échecs), définition hors `field`
tolérée (6), doublons tolérés (4), noms partagés entre formulaires (1), borne
de nœuds (1), `form` sans règle d'action (4), définition acceptée hors `field`
(3), champ édité laissé à sa place (1), erreurs des frères non filtrées (1),
objet non `FieldDefinition` accepté (1). Toutes les mutations sont détectées.
Deux survivaient d'abord : la première version de la mutation « noms
partagés » ne partageait rien réellement (mutation inefficace, refaite avec un
ensemble global), et aucun test ne couvrait l'objet ressemblant (test ajouté).

## Validations ciblées

Exécutions pytest depuis le scratchpad.

| Commande | Résultat |
|---|---|
| `pytest -q tests/test_design_form_fields.py` | 66 réussis |
| `pytest -q tests/test_design_models.py tests/test_design_schema.py tests/test_design_nesting.py tests/test_design_bindings.py tests/test_design_form_fields.py tests/test_editor_properties.py tests/test_editor_structure.py tests/test_design_io.py tests/test_generate_simple.py tests/test_generate_buttons.py tests/test_preview_render.py` | 1025 réussis |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` / `ruff format --check .` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |

## Validation globale

`pytest` : **3469 réussis** en 37 s. `python -m pip check` : No broken
requirements found.

## Packaging

Wheel `forge_design-0.1.0.dev0-py3-none-any.whl` dans `tmp/wheels`, SHA-256
`f6d43c116f9fa0322ee5cc76c42f9c537230cd49e8aed4605a2a94268dc1ea88`. Elle
contient `design/form_fields.py` et le schéma mis à jour.

## Installation réelle

Installation `--no-deps --no-index --target` temporaire, `python -I`, origine
installée vérifiée :
1. le schéma embarqué contient `FieldDefinition` et ses six `input_type` ;
2. le Design du critère de fin (form avec binding, field défini, button) est
   valide en imbrication, en bindings (`form → action` avec un contrat réel)
   et en champs ;
3. `set_field_definition` fonctionne depuis la wheel.

## Limites restantes

- Aucune génération de formulaire ni d'HTMX de formulaire (FD-INTERACT-003).
- Pas de valeur initiale, de placeholder, de `select`, `textarea`, `radio`,
  d'upload ni de CSRF runtime.
- Preview et éditeur Web n'affichent pas encore la définition.
- `label` non vide : écart à valider (voir « Label »).

## État Git final

Un commit sur `main`, rapport inclus, sans push.
Message : `feat: définir le contrat des formulaires (FD-INTERACT-002)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Hash :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-INTERACT-002.md
```
