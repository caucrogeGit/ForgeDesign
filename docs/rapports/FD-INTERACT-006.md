# Rapport — FD-INTERACT-006

## Ticket et objectif

Aligner la preview statique sur les formulaires générés (`form`, `field`,
`submit`) tout en la gardant inerte, déterministe, locale, sans script, sans
soumission ni backend, et sans modifier le générateur. Seul
`forge_design/preview/render.py` change parmi les modules de code.

## État Git initial

`main` synchronisée avec `origin/main` à `56ff45c` — FD-INTERACT-005. Seule
modification suivie préexistante : `docs/rapports/FD-CONTRACT-001.md`,
préservée hors commit.

## Form preview

Le rendu générique existant convient déjà : `<form data-forge-design-type="form"
[class]>`, sans changement de code. Il n'émet jamais `action`, `method` ni
`hx-*` : un `binding` est ignoré et les props `hx-*` donnent
`preview.unsupported_prop`. Un `form` sans binding n'est pas signalé
(`form_missing_action` reste propre au générateur).

## Field preview

Nouvelle branche `_Renderer.field`, appelée **après** l'évaluation de
`visible_if` :
`<input data-forge-design-type="field" type="…" name="…" [class="…"]
[required]>`, enveloppé par `<label>Libellé…</label>` si un libellé existe.
`type` vient de `input_type` (six types testés), `name` de `field.name`,
échappé. `<input>` est un élément vide, jamais `<input></input>`. Pas de
`value` (les données fictives décrivent le contexte, pas l'état d'un
formulaire ; testé avec un champ portant le nom d'une variable), ni `id`, ni
`for`. Sans définition : `preview.missing_field_definition`, aucun faux
`<input>`.

## Submit preview

Nouvelle branche `_Renderer.submit_button` pour `button` avec `submit` :
`<button data-forge-design-type="button" type="submit" [class]>Libellé</button>`.
Le libellé vient exclusivement de `submit.label`, échappé, et n'est jamais
remplacé par `Action`. Un bouton avec `binding` et `submit` donne
`preview.invalid_submit` (politique préférée du ticket) et n'est pas rendu.
Un submit hors formulaire n'est pas détecté : le validateur Design en reste
responsable, sans refactoring du renderer.

## Action button

Le flux générique est inchangé : `<button … type="button">Action</button>`
(testé), sans `hx-*`.

## Props

Helper `classes_only` pour `field` et `submit` : `class` (chaîne) est émise ;
toute autre prop (`tag`, `placeholder`, `id`, `hx-target`, `hx-swap`,
`hx-confirm`, `onclick`…) donne `preview.unsupported_prop` et n'est pas
émise, sans empêcher le rendu. Le traitement générique des props des autres
blocs est inchangé. Il n'y a pas de système de composants.

## Classes

Elles sont échappées comme aujourd'hui et sans interprétation Tailwind. Sur
un champ, `class` est posée sur l'`<input>`, jamais sur le `<label>`, comme
dans le générateur.

## Labels

Présent : `<label>` englobant. Absent : `<input>` seul, sans `<label>` vide.

## Required

`true` donne l'attribut booléen `required` ; `false` ou absent : rien
(3 cas testés).

## Échappement

Noms, libellés de champ, libellés de submit et classes passent par
`escaped`. Les valeurs hostiles (`"><script>…`, `<img onerror>`) restent du
texte : aucun `<script>` ni `<img>`, et les attributs relus par un parseur
HTML redonnent exactement la valeur d'origine.

## Conditions

`visible_if` s'applique avant les nouvelles branches : `false` n'émet ni champ
ni submit (le `<form>` reste) ; une condition manquante garde
`preview.missing_condition`. Une mutation qui rend le champ avant la
condition fait échouer 2 tests.

## Absence de HTMX

Le critère de fin vérifie l'absence d'`action=`, `method=`, `hx-get=`,
`hx-post=`, `hx-target=`, `hx-swap=`, `hx-confirm=`, `value=`, `id=`, `for=` et
`<script`.

## Absence de backend

La preview ne reçoit toujours ni contrat ni réseau. `open`, `os.open`,
`socket` et `subprocess` sont bloqués pendant le rendu, qui reste
déterministe et ne mute pas le Design.

## Diagnostics

Deux codes ajoutés, nécessaires : `preview.missing_field_definition` et
`preview.invalid_submit`. Les codes historiques sont conservés. Tout
diagnostic donne `complete=False`.

## Limites de taille

Les libellés de champ et de submit consomment `MAX_PREVIEW_HTML_CHARS` : un
dépassement donne `preview.output_too_large` et le document d'erreur contrôlé
(testé avec un budget réduit).

## Web iframe

Aucun changement dans `web/` : `/editor/preview` utilise `render_preview`
et affiche le nouveau rendu. Les tests de l'iframe passent sans modification
(CSP, sandbox, en-têtes).

## Fichiers modifiés

- `forge_design/preview/render.py` : branches `field` et `submit_button`,
  helper `classes_only` (69 lignes ajoutées, aucune supprimée).
- `tests/test_preview_render.py` : tests ajoutés. Le helper `Parsed` connaît
  désormais l'élément vide `input`. `test_node_limits` utilise une feuille
  neutre (`alert`) au lieu d'un `field` sans définition, désormais
  diagnostiqué, ce qui saturait la borne de diagnostics : l'intention (borne
  de nœuds) est inchangée. `field` est retiré de `test_block_mapping`, qui
  vérifiait l'ancien rendu en `div`.
- Tests qui figeaient l'ancien rendu, mis à jour vers le nouveau
  (`tests/test_design_form_fields.py`, `tests/test_design_submit_buttons.py`,
  `tests/test_generate_buttons.py`, `tests/test_generate_forms.py`) : ils
  vérifient maintenant le champ et le submit rendus, toujours sans action ni
  HTMX.
- `docs/preview/static-preview.md`, `docs/editor/structural-editor.md`,
  `docs/02-architecture.md`

Fichier créé : `docs/rapports/FD-INTERACT-006.md`. Non modifiés : `design/`,
`contracts/`, `editor/`, `generate/` (vérifié par `git diff --stat`), `web/`,
`safewrite/`, `tools/`, `app.py`, `pyproject.toml`, le JavaScript.

## Tests ajoutés

`tests/test_preview_render.py` : 32 cas. Critère de fin exact, formulaire
sans attributs d'action, champ minimal, 6 types, `required` (3), sans valeur
issue des données fictives, `class` et props refusées sur un champ,
définition manquante, 2 champs hostiles, submit minimal avec `class`, 5 props
refusées sur un submit, libellé hostile, `binding` et `submit` invalides,
bouton d'action inchangé, conditions visibles et masquées, diagnostic de
condition, budget, pureté et déterminisme.

Vérification par mutation, lancée depuis le scratchpad avec restauration
vérifiée : champ en `div` générique (17 échecs), submit en bouton d'action
(11), faux `<input>` sans définition (1), `required: false` émis (1), libellé
non échappé (2), nom non échappé (2), `binding` et `submit` tolérés (1),
libellé de submit non échappé (1), props arbitraires émises (6), champ rendu
avant la condition (2). Toutes les mutations sont détectées.

## Validations ciblées

Exécutions pytest depuis le scratchpad.

| Commande | Résultat |
|---|---|
| `pytest -q tests/test_preview_render.py` | 104 réussis |
| `pytest -q tests/test_preview_render.py tests/test_preview_data.py tests/test_preview_responsive.py tests/test_web_editor_preview.py tests/test_generate_buttons.py tests/test_generate_forms.py tests/test_design_form_fields.py tests/test_design_submit_buttons.py` | 457 réussis |

## Validation globale finale

Ordre suivi, conformément au §107 : code, tests ciblés, documentation, ce
rapport, statique final, suite globale finale, puis commit.

| Commande | Résultat |
|---|---|
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` / `ruff format --check .` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |
| `pytest` (depuis le scratchpad, `--rootdir` vers le dépôt) | **3641 réussis** en 38 s, aucun échec |
| `python -m pip check` | No broken requirements found |

Seul ce tableau a été ajouté au rapport après l'exécution. Les validations
statiques et la suite globale ont ensuite été relancées sur le contenu final,
avec un résultat identique, et aucun `storage/` n'a été créé dans le
répertoire d'exécution.

## Packaging

Wheel `forge_design-0.1.0.dev0-py3-none-any.whl` dans `tmp/wheels`, SHA-256
`9cd1e4be5226c170c76e1e0c204e41e844f7af4d0f7298e44fd22e2440a8e6f1`.

## Installation réelle

Installation `--no-deps --no-index --target` temporaire, `python -I`, origine
installée vérifiée :
1. `render_preview` produit exactement
   `<form data-forge-design-type="form"><label>Adresse e-mail<input data-forge-design-type="field" type="email" name="email" required></label><button data-forge-design-type="button" type="submit">Enregistrer</button></form>` ;
2. serveur réel : projet ouvert, `GET /editor/preview` : 200, avec la même
   structure dans le document encadré, sans `action`, `method`, `hx-`,
   `value` ni `<script>` dans le contenu de la preview.

## Validation navigateur

**Non effectuée.** Le HTML et la réponse HTTP de l'iframe sont vérifiés ;
l'apparence dans un navigateur ne l'est pas.

## Limites restantes

- Le formulaire de la preview ne porte ni `action` ni `method` (pas de
  contrat) : c'est un aperçu structurel, pas un formulaire fonctionnel.
- Un submit hors formulaire n'est pas signalé par la preview.
- Les données fictives ne remplissent pas les champs.
- `alert` garde son rendu générique.

## État Git final

Un commit sur `main`, rapport inclus, sans push.
Message : `feat: aligner la preview des formulaires (FD-INTERACT-006)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Hash :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-INTERACT-006.md
```
