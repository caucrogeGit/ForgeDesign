# Rapport — FD-INTERACT-005

## Ticket et objectif

Générer les boutons de soumission définis par `submit` (FD-INTERACT-004) sous
la forme `<button type="submit">Libellé</button>`, sans changer les boutons
d'action autonomes. Ce ticket complète la première tranche « formulaire
interactif contrôlé » : `form` porte l'action HTMX, `field` la donnée et
`submit` la soumission explicite.

## État Git initial

`main` synchronisée avec `origin/main` à `de21773` — FD-INTERACT-004. Seule
modification suivie préexistante : `docs/rapports/FD-CONTRACT-001.md`,
préservée hors commit.

## Validation submit

`validate_submit_buttons(design)` est appelé dans `generate_simple_template`
(une fois, vérifié par un espion), dans l'ordre stable : nesting, bindings,
conditions, champs, **submits**, tables, puis génération. Toute erreur du
validateur (`unsupported_definition`, `conflicting_action`, `outside_form`)
donne `generate.invalid_submit` et bloque tout le template ; la troncature
donne `generate.analysis_truncated`. L'ordre préfixe est conservé (un bouton à
la fois en conflit et hors formulaire donne deux diagnostics). Aucune règle
n'est recopiée dans `buttons.py` (vérifié). `validate_design_bindings` n'est
pas modifié : un submit valide n'a pas de binding, et une action autonome
inconnue reste `generate.invalid_binding`.

## Bouton action

Sortie strictement inchangée : les 52 tests historiques passent **sans
modification de leurs attentes**. `ButtonPlan` reçoit seulement un champ
`label` ; pour une action, il vaut `BUTTON_LABEL = "Action"`, constante
conservée et désormais documentée comme le libellé des seuls boutons
d'action. `render_button` n'utilise plus une constante unique : il émet
`plan.label`.

## Bouton submit

`prepare_button` traite `node.submit` en premier, par `_prepare_submit`, qui
**n'appelle pas** `prepare_interaction` : un submit n'a pas d'action propre.
Sortie : `type="submit"`, puis `class` si présente. Un bouton sans `binding`
ni `submit` reste `generate.button_missing_action` (inchangé).

## Label

Il vient exclusivement de `submit.label`, échappé par `writer.escaped` avec la
location `(…, "submit", "label")`. Il n'est jamais remplacé par `Action`
(testé : `>Action<` absent) ni par un libellé inventé. Les valeurs hostiles
(`"><script>`, `{{ danger }}`, `{% if x %}`, LF) sont neutralisées : aucune
balise, aucun délimiteur Jinja, et l'AST ne contient ni variable, ni
attribut, ni condition.

## Classes

`class` (chaîne) seulement, échappée, après `type`. Une `class` non textuelle
donne `generate.unsupported_prop`, est ignorée, et le submit est généré.

## Props refusées

`hx-target`, `hx-swap`, `hx-confirm`, `hx-post`, `onclick`, `tag` et `style`
donnent `generate.unsupported_prop`, ne sont **pas émis**, et le bouton reste
généré. Une prop `hx-*` sur le submit créerait une seconde action implicite
alors que le formulaire parent porte déjà l'interaction.

## Conditions

`visible_if` réutilise l'enveloppe `{% if %}` de `simple.py` (sortie exacte
testée).

## Intégration formulaire

Le critère de fin est testé à l'octet :

```html
<section>
  <form action="/contacts" method="post" hx-post="/contacts">
    <input type="email" name="email">
    <button type="submit" class="px-4 py-2">Enregistrer</button>
  </form>
</section>
```

Plusieurs submits sont générés dans l'ordre du Design. Un submit et un bouton
d'action peuvent cohabiter dans un même formulaire, chacun avec sa sortie. Un
formulaire omis (`form_missing_action`…) n'est pas parcouru : son submit
n'apparaît jamais seul.

## Absence d'action propre

Aucun `hx-`, `action=`, `formaction`, `formmethod`, `name=` ni `value=` sur un
submit (testé). Le générateur ne relit pas le `FormPlan` : la position est
garantie par le validateur.

## Preview inchangée

`preview/` n'est pas modifié. La preview reste structurelle : un submit y est
un bouton générique, sans `type="submit"` ni libellé (testé et documenté).

## Pureté

`open`, `os.open`, `socket` et `subprocess` sont bloqués pendant la
génération.

## Déterminisme

Même Design et même contrat donnent le même résultat.

## Non-mutation

Les dumps du Design et du contrat sont identiques avant et après.

## Fichiers modifiés

- `forge_design/generate/buttons.py` : `ButtonPlan.label`, `_prepare_submit`,
  `render_button` sur `plan.label`.
- `forge_design/generate/simple.py` : garde `validate_submit_buttons`.
- `tests/test_generate_buttons.py` : tests submit ajoutés (52 tests
  historiques inchangés).
- `tests/test_design_submit_buttons.py` : le test d'INTERACT-004 qui
  documentait la limite provisoire (submit vu comme un bouton sans action)
  vérifie désormais le submit généré.
- `docs/generate/template-generation.md`, `docs/02-architecture.md`

Fichier créé : `docs/rapports/FD-INTERACT-005.md`. Non modifiés : `design/`,
`contracts/`, `editor/`, `preview/`, `web/`, `safewrite/`, `tools/`,
`app.py`, `pyproject.toml`, le JavaScript.

## Tests ajoutés

`tests/test_generate_buttons.py` : 31 cas ajoutés (83 au total). Critère de
fin exact, submit minimal, jamais `Action`, aucune action propre, 7 props
refusées, `class` non textuelle, 4 valeurs hostiles, condition, plusieurs
submits, action et submit côte à côte, 2 submits invalides et un submit avec
binding bloquants, ordre préfixe, troncature, validateur réutilisé, bouton
vide, formulaire omis masquant le submit, budget exact et dépassement,
déterminisme et non-mutation, pureté, preview structurelle.

Vérification par mutation, lancée depuis le scratchpad avec restauration
vérifiée : submit traité comme action (21 échecs), `type="button"` sur submit
(13), libellé `Action` sur submit (15), libellé non échappé (3), `hx-*` accepté
sur submit (4), validateur submit ignoré (4), troncature ignorée (1). Toutes
les mutations sont détectées.

## Validations ciblées

Exécutions pytest depuis le scratchpad.

| Commande | Résultat |
|---|---|
| `pytest -q tests/test_generate_buttons.py tests/test_design_submit_buttons.py` | 133 réussis |
| `pytest -q tests/test_generate_simple.py tests/test_generate_control_flow.py tests/test_generate_tables.py tests/test_generate_buttons.py tests/test_generate_forms.py tests/test_design_submit_buttons.py tests/test_preview_render.py` | 418 réussis |

## Validation globale finale

Ordre suivi, conformément au §82 : code, tests ciblés, documentation, ce
rapport, statique final, suite globale finale, puis commit.

| Commande | Résultat |
|---|---|
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` / `ruff format --check .` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |
| `pytest` (depuis le scratchpad, `--rootdir` vers le dépôt) | **3611 réussis** en 37 s, aucun échec |
| `python -m pip check` | No broken requirements found |

Seul ce tableau de résultats a été ajouté au rapport après l'exécution. Les
validations statiques et la suite globale ont ensuite été relancées sur le
contenu final, avec un résultat identique, et aucun `storage/` n'a été créé
dans le répertoire d'exécution.

## Packaging

Wheel `forge_design-0.1.0.dev0-py3-none-any.whl` dans `tmp/wheels`, SHA-256
`59b0118fdb3d3689f7863b7823554e8e27a9136a5d2d2c68dba76a4d1ce1cddf`. Installée
avec `--no-deps --no-index --target` et `python -I` (origine vérifiée), elle
produit exactement le HTML du critère de fin. Seule la génération est
vérifiée : aucune soumission navigateur ni runtime HTMX n'a été exécuté.

## Limites restantes

- Preview structurelle : le submit n'y est pas rendu comme dans le template
  généré.
- Les submits multiples ne se distinguent pas côté serveur (pas de
  `name`/`value`).
- Pas de `hx-*` propre au submit : l'interaction reste celle du formulaire.
- `POST` avec `csrf: true` toujours refusé ; aucune protection CSRF générée.
- Aucune vérification navigateur.

## État Git final

Un commit sur `main`, rapport inclus, sans push.
Message : `feat: générer les boutons submit (FD-INTERACT-005)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Hash :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-INTERACT-005.md
```
