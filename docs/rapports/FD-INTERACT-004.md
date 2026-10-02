# Rapport — FD-INTERACT-004

## Ticket et objectif

Représenter explicitement dans Design v0.1 la différence entre un bouton
d'action autonome (`binding`) et un bouton de soumission du formulaire
parent (`submit`), avec schéma, validation sémantique et édition en mémoire.
Aucun `type="submit"` n'est généré.

## État Git initial

`main` synchronisée avec `origin/main` à `152803f` — FD-INTERACT-003, poussé
(correction de la régression de `cefee33` comprise). Seule modification
suivie préexistante : `docs/rapports/FD-CONTRACT-001.md`, préservée hors
commit.

## Décision de modèle

Nouvelle propriété explicite `submit: SubmitDefinition` de `_NodeProperties`,
facultative. Pas de `role`, de `kind` ni de nouvelle sémantique de `binding`.
La version reste `0.1`, et `contracts/` n'est pas modifié.

## SubmitDefinition

`SubmitDefinition(label)` : `label` est une chaîne non vide obligatoire, avec
`extra="forbid"`, `strict`, `frozen` et `null` refusé, comme les autres
modèles Design. Il n'y a ni `name`, ni `value`, ni `formaction`, ni
`formmethod`, ni `confirm`, ni `variant` (refusés, testé).

## Bouton action existant

`binding` sans `submit` reste une action autonome (FD-INTERACT-001), sans
changement : `validate_design_bindings` le valide, et les 52 tests de
génération des boutons sont inchangés.

## Bouton submit

`submit` sans `binding` : bouton de soumission. `validate_design_bindings` ne
signale rien (binding absent), et `validate_form_fields` non plus. Un bouton
sans `binding` ni `submit` reste structurellement valide et n'est jamais
transformé implicitement en submit.

## Conflit action / submit

`binding` et `submit` sur le même bouton donnent
`design.submit.conflicting_action`.

## Position dans le formulaire

Un submit doit être **enfant direct** d'un `form` (`form → field | button |
alert`), sinon `design.submit.outside_form`. Un `form` ancêtre ne suffit pas :
c'est testé avec une imbrication invalide construite à dessein, car le
validateur ne dépend pas de nesting. Plusieurs submits par formulaire sont
admis, ainsi qu'un submit dans chacun de deux formulaires. Un bouton d'action
dans un `form` n'est pas signalé.

## Validation sémantique

`design/submit_buttons.py` : `validate_submit_buttons(design) ->
SubmitButtonValidationResult(valid, issues, truncated)`, avec
`SubmitButtonIssue(code, message, location)`. Parcours préfixe borné par
`MAX_DESIGN_NODES`, `MAX_DESIGN_DEPTH` et `MAX_DESIGN_ISSUES` (marqueur
`design.submit.analysis_truncated`), type du parent porté par la pile. Codes :
`unsupported_definition` (sur `text`, `form`, `section` et la page),
`conflicting_action` et `outside_form`, les deux derniers pouvant coexister.
Aucun contrat n'est reçu : l'action du `form` parent relève de
`validate_design_bindings`.

## Editor

`set_submit_definition(design, *, path, submit)` dans `editor/properties.py`,
exporté par `forge_design.editor`. `None` supprime la définition (sur tout
bloc) ; une valeur identique est un no-op ; une instance de `SubmitDefinition`
est obligatoire (`editor.invalid_submit` pour un dict, une chaîne, un nombre
ou un objet ressemblant) ; la valeur est copiée.

Validation ciblée : `_parent_projection` réduit le Design au bouton et à son
**seul parent direct**, puis les diagnostics de `validate_submit_buttons` sur
le bouton sont convertis en `editor.submit_not_supported`,
`editor.submit_conflicting_action` et `editor.submit_outside_form`. Une erreur
ailleurs, **ou sur le parent lui-même** (`submit` posé sur le `form`), ne
bloque pas l'édition (testé).

## Préservation des données

Modifier `submit` ne change ni `binding`, ni `visible_if`, ni `props`, ni les
autres blocs. Inversement, `submit` est conservé :
- par l'API : props (valeur et effacement), condition, ajout, suppression et
  déplacement (dans le formulaire et hors du formulaire) ;
- par le serveur Web réel, avec sauvegarde : props, ajout et retrait Tailwind,
  condition, ajout et suppression de bloc ; relu sur disque.

`move_design_block` n'est pas élargi : sortir un submit de son formulaire est
accepté par nesting, et `validate_submit_buttons` signale ensuite
`outside_form` (testé).

## Compatibilité Design v0.1

Les Designs existants et les boutons `binding` sont inchangés.
`write_design` puis `read_design` conservent `submit` à l'octet (aller-retour
réel testé, révision identique).

## Génération reportée

`generate/` n'est pas modifié. Un submit est vu comme un bouton sans action :
`generate.button_missing_action`, bouton omis, sans `type="submit"` ni
libellé, et le `<form>` reste généré (test documentant cette limite).

## Preview reportée

`preview/` n'est pas modifié : ni `type="submit"`, ni libellé.

## Documentation

- `docs/design/design-json.md` : section « Boutons submit ». L'exemple est un
  **fragment** de bloc `form`, explicitement désigné comme tel. Le test des
  exemples officiels (corrigé en FD-INTERACT-003) le valide comme
  `DesignNode`, et la liste des Designs complets est inchangée.
- `docs/editor/structural-editor.md` : `set_submit_definition`.
- `docs/02-architecture.md` : schéma action et soumission.

## Fichiers créés

- `forge_design/design/submit_buttons.py`
- `tests/test_design_submit_buttons.py`
- `docs/rapports/FD-INTERACT-004.md`

## Fichiers modifiés

- `forge_design/design/models.py` : `SubmitDefinition`, `_NodeProperties.submit`.
- `forge_design/design/design.schema.json` : uniquement des ajouts
  (`$defs.SubmitDefinition`, `DesignNode.properties.submit`).
- `forge_design/design/__init__.py` : exports.
- `forge_design/editor/properties.py`, `forge_design/editor/__init__.py`
- `tests/test_design_schema.py` (listes de définitions et propriétés, test
  `SubmitDefinition`), `tests/test_design_models.py` (concordance).
- `docs/design/design-json.md`, `docs/editor/structural-editor.md`,
  `docs/02-architecture.md`

Non modifiés : `contracts/`, `generate/`, `preview/`, `web/`, `safewrite/`,
`tools/`, `app.py`, `pyproject.toml`, le JavaScript.

## Tests ajoutés

`tests/test_design_submit_buttons.py` : 50 cas. Modèle : nominal, 7 invalides,
`null` sur le nœud, gel, aller-retour JSON. Validateur : enfant direct, 2 cas
hors formulaire, 3 types non autorisés, page, conflit, conflit et hors
formulaire, boutons d'action et vides, plusieurs submits et formulaires,
troncature par diagnostics et par nœuds, pureté, ancêtre `form` insuffisant.
Bindings : action toujours valide, submit sans diagnostic. Éditeur : nominal
avec préservation, clear et no-op, 4 types refusés, conflit, hors formulaire,
3 valeurs invalides, objet ressemblant, correction progressive, erreur du
parent ignorée, copie. Préservation : propriétés, structure, Web réel.
Persistance `write_design`/`read_design`. Génération et preview reportées.
Non-mutation. `tests/test_design_schema.py` : 1 test ajouté.

Vérification par mutation, lancée depuis le scratchpad avec restauration
vérifiée : submit hors bouton toléré (7 échecs), action et submit tolérés (4),
hors formulaire toléré (5), ancêtre `form` accepté (1), règle « un seul
submit » inventée (1), borne de nœuds (1), erreurs ailleurs non filtrées (1),
projection sans parent (4), objet non `SubmitDefinition` accepté (1), submit
sans contrôle (6). Toutes les mutations sont détectées. Trois survivaient à
la première version des tests (ancêtre, filtrage, objet ressemblant), et un
test a été ajouté pour chacune.

## Validations ciblées

Exécutions pytest depuis le scratchpad.

| Commande | Résultat |
|---|---|
| `pytest -q tests/test_design_submit_buttons.py` | 50 réussis |
| `pytest -q tests/test_design_schema.py tests/test_design_models.py` | 227 réussis (puis 29 réussis pour `test_design_schema.py` après la documentation) |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` / `ruff format --check .` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |

## Validation globale finale

Ordre suivi, conformément au §55 : code, puis documentation, puis ce
rapport, puis seulement la suite globale finale. Le résultat ci-dessous est
celui de la suite lancée sur le contenu commité, rapport compris.

| Commande | Résultat |
|---|---|
| `pytest` (depuis le scratchpad, `--rootdir` vers le dépôt) | **3580 réussis** en 37 s, aucun échec |
| `python -m pip check` | No broken requirements found |

Seule cette ligne de résultat a été ajoutée au rapport après l'exécution. La
suite a ensuite été relancée sur le contenu final, avec un résultat
identique (3580 réussis), et aucun `storage/` n'a été créé dans le répertoire
d'exécution.

## Packaging

Wheel `forge_design-0.1.0.dev0-py3-none-any.whl` dans `tmp/wheels`, SHA-256
`47b33fc9136de9bf2d66b2debc4b354b253a222b2ee52c01c7ba80b596ac8fba`. Elle
contient `design/submit_buttons.py` et le schéma mis à jour.

## Installation réelle

Installation `--no-deps --no-index --target` temporaire, `python -I`, origine
installée vérifiée :
1. le schéma embarqué contient `SubmitDefinition` et `submit` ;
2. `set_submit_definition` fonctionne depuis la wheel : un submit et un
   bouton d'action coexistent dans le même formulaire, et le Design est
   valide ;
3. `write_design` puis `read_design` dans un projet Forge temporaire
   conservent `{"type": "button", "submit": {"label": "Enregistrer"}}`.

## Limites restantes

- Pas de `type="submit"` généré : un submit est omis par le générateur
  (`generate.button_missing_action`) jusqu'à FD-INTERACT-005.
- Preview et éditeur Web sans rendu ni contrôle dédiés au submit.
- Un déplacement peut sortir un submit de son formulaire ; seule la validation
  le signale.
- Les submits multiples ne se distinguent pas fonctionnellement (pas de
  `name`/`value`).

## État Git final

Un commit sur `main`, rapport inclus, sans push.
Message : `feat: définir les boutons submit (FD-INTERACT-004)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Hash :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-INTERACT-004.md
```
