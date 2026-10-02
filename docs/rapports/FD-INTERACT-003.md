# Rapport — FD-INTERACT-003

## Ticket et objectif

Générer les premiers formulaires HTML/HTMX contrôlés à partir du contrat de
FD-INTERACT-002 : `<form>` lié à une `ViewAction` (HTML natif et HTMX) et
`<input>` issus de `FieldDefinition`, sans modifier Design ni Contract, sans
CSRF inventé, id, value, submit implicite ni runtime HTMX.

## État Git initial

`main` synchronisée avec `origin/main` à `cefee33` — FD-INTERACT-002. Seule
modification suivie préexistante : `docs/rapports/FD-CONTRACT-001.md`,
préservée hors commit.

**Régression découverte sur la baseline.** `cefee33` contient un test en
échec : `test_design_schema.py::test_official_examples_and_documentation`
exige que **tous** les blocs ```json de `docs/design/design-json.md` soient
les deux fixtures officielles, et FD-INTERACT-002 y a ajouté l'exemple de
formulaire. La suite globale de ce ticket avait été lancée **avant**
l'écriture de cette documentation : le rapport FD-INTERACT-002 annonce donc
« 3469 réussis » alors que le commit poussé échoue sur ce test. Échec
reproduit dans un worktree temporaire de `cefee33`. **Corrigé ici** (voir
« Fichiers modifiés »), et la procédure est rectifiée : la suite globale est
désormais lancée après la dernière modification de documentation.

## Architecture

`generate/forms.py` (`prepare_form`, `render_form_open`/`render_form_close`,
`prepare_field`, `render_field`, `FormPlan`, `FieldPlan`) suit le modèle de
`buttons.py` et `tables.py`, et `simple.py` reste l'orchestrateur. La
politique demandée comme « même politique » ou « même code » que les boutons
(méthodes, CSRF, props HTMX, §18-§27) est **factorisée** dans
`generate/actions.py` (`prepare_interaction`, `render_attributes`,
`METHOD_ATTRIBUTES`, `HTMX_PROPS`). `buttons.py` l'utilise désormais, avec une
sortie identique : les 52 tests de boutons passent sans modification. Le
Protocol de writer est partagé (`InteractionWriter`, alias `ButtonWriter` et
`FormWriter`), sans nouvelle abstraction globale.

## Validation form_fields

`validate_form_fields(design)` est appelé une fois (espion) avant émission :
`missing_definition` et `unsupported_definition` donnent
`generate.invalid_field`, `duplicate_name` donne
`generate.duplicate_field_name`, et la troncature donne
`generate.analysis_truncated`. Tous bloquent la génération entière (aucun
template). Aucune règle n'est recopiée dans `forms.py` (testé).

## Binding du formulaire

`form` rejoint les bindings bloquants (`title`, `text`, `button`, `form`) :
une action inconnue donne `generate.invalid_binding` et aucun template.
`form` sans binding donne `generate.form_missing_action` : formulaire **et
sous-arbre** omis, champs non rendus hors d'un `<form>` (testé : ni `<input>`
ni nom dans le template), le reste de la page est généré.

## GET

`<form action="/search" method="get" hx-get="/search">`, y compris avec
`csrf: true`.

## POST

`<form action="/contacts" method="post" hx-post="/contacts">`, avec
`csrf: false` ou sans `csrf`.

## HTML natif

`action` et `method` en minuscules assurent la dégradation progressive sans
HTMX. Sans l'un ou l'autre, 15 et 16 tests échouent (mutation).

## HTMX

`hx-get`/`hx-post` reprennent **la même** URL échappée que `action`, issue de
`ViewAction.path` (testé avec `?x=1&y=2`, rendu `&amp;` dans les deux).
`PUT`, `PATCH`, `DELETE` et `HEAD` donnent
`generate.unsupported_action_method` et le formulaire est omis.

## Props du formulaire

Liste blanche `class`, `hx-target`, `hx-swap`, `hx-confirm`. Ordre fixe
`action`, `method`, `class`, verbe, `hx-target`, `hx-swap`, `hx-confirm`
(testé avec des props dans le désordre). Une valeur HTMX vide ou non textuelle
donne `generate.invalid_htmx_prop` et le formulaire est omis. `style`,
`onclick`, `hx-trigger`, `hx-vals`, `hx-headers`, `tag` et `id` donnent
`generate.unsupported_prop`, ne sont pas émis, et les autres props restent
générées.

## FieldDefinition

`<input type="…" name="…" [class="…"] [required]>`, dans cet ordre. `name`
vient exclusivement de la définition, est opaque (`contact.email`,
`items[0].name`, `é`) et échappé.

## Types de contrôle

Les six `FieldInputType`, utilisés directement (liste fermée revalidée par
Pydantic en amont).

## Labels

Présent : `<label>Libellé<input …></label>`, libellé englobant, sans `id`
ni `for`. Absent : `<input …>` seul, sans `<label>` vide.

## Required

`true` donne l'attribut booléen `required` ; `false` ou absent : rien.

## Checkbox

`<input type="checkbox" name="active">` : ni `value`, ni champ caché
compagnon. Aucun `min`, `max`, `step`, `autocomplete`, `placeholder` ou `id`
n'est généré, quel que soit le type (testé).

Props d'un champ : seule `class` (chaîne) est émise. Toute autre prop, ou une
`class` non textuelle, donne `generate.unsupported_prop`, ignorée sans
bloquer le champ.

## Échappement

Le chemin, les classes, les valeurs HTMX, les noms et les libellés passent
par `writer.escaped`. Quatre valeurs hostiles (`"><script>`, `{{ }}`,
`{% %}`, LF) ont été testées simultanément dans tous ces emplacements : pas
de `<script>`, aucun délimiteur Jinja, et l'AST Jinja ne contient ni
variable, ni attribut, ni inclusion. Sans échappement du libellé ou du nom,
4 tests échouent.

## Conditions

L'enveloppe `{% if %}` de `simple.py` est réutilisée pour `form` et `field`
(sorties exactes testées). Un formulaire omis ne laisse pas de condition vide.

## CSRF

`GET` : inchangé quel que soit `csrf`. `POST` sans `csrf` ou avec
`csrf: false` : généré, **sans protection fournie par Forge Design**
(documenté). `POST` avec `csrf: true` : `generate.unsupported_csrf`,
formulaire omis. Aucun jeton, champ ni en-tête n'est généré.

## Boutons enfants

Un `button` sous un `form` reste `type="button"` avec **sa propre** action :
`hx-get="/contacts/1/delete"` sous un formulaire `POST /contacts`. `alert`
enfant reste `generate.unsupported_block`.

## Absence de submit implicite

Aucun `type="submit"`, aucun bouton « Envoyer » ajouté : un formulaire généré
peut ne pas avoir de bouton d'envoi (documenté). Le prochain ticket pourra
définir un submit explicite.

## Preview inchangée

`preview/` n'est pas modifié. La preview d'un formulaire n'émet ni `<input>`,
ni `action`, ni `hx-*` (testé).

## Pureté

`open`, `os.open`, `socket` et `subprocess` sont bloqués pendant la
génération. `forms.py` ne référence ni I/O ni validateur recopié.

## Déterminisme

Même Design et même contrat donnent le même résultat.

## Non-mutation

Les dumps du Design et du contrat sont identiques avant et après.

## Fichiers créés

- `forge_design/generate/forms.py`
- `forge_design/generate/actions.py`
- `tests/test_generate_forms.py`
- `docs/rapports/FD-INTERACT-003.md`

## Fichiers modifiés

- `forge_design/generate/simple.py` : `form`/`field` générés, `form`
  bloquant, garde `validate_form_fields`.
- `forge_design/generate/buttons.py` : utilise `actions.py`, sortie
  inchangée.
- `tests/test_generate_simple.py` : `test_unsupported_branches` ne garde que
  `alert` (§134).
- `tests/test_design_form_fields.py` : le test « génération reportée » de
  FD-INTERACT-002 vérifie désormais le formulaire généré.
- `tests/test_design_schema.py` : **correction de la régression de
  `cefee33`.** Les Designs complets documentés doivent toujours être les deux
  fixtures officielles ; les fragments de bloc (l'exemple form/field) sont
  désormais **validés par `DesignNode`** et doivent exister. L'exemple de la
  documentation est donc vérifié, alors qu'il ne l'était pas.
- `docs/generate/template-generation.md`, `docs/02-architecture.md`

Non modifiés : `design/`, `contracts/`, `editor/`, `preview/`, `web/`,
`safewrite/`, `tools/`, `app.py`, `pyproject.toml`, le JavaScript.

## Tests ajoutés

`tests/test_generate_forms.py` : 62 cas. Critère de fin exact, GET (2), POST
(2), même URL, ordre des props, formulaire vide, sans action, action inconnue,
4 méthodes refusées, `csrf: true` en `POST`, 6 types, checkbox, label absent,
`required` (3), 3 noms opaques, aucun attribut inventé, props de champ, `class`
non textuelle, 7 props de formulaire inconnues, 2 valeurs HTMX invalides, 3
validations `form_fields` bloquantes, troncature, validateur réutilisé, 4
valeurs hostiles, conditions de form et de field, condition non laissée vide,
bouton enfant, absence de submit, alert enfant, budget exact et dépassement,
pureté, déterminisme et non-mutation, absence de script et de runtime,
politique partagée, preview inchangée.

Vérification par mutation, lancée depuis le scratchpad avec restauration
vérifiée : `method` natif absent (15 échecs), `action` natif absent (16),
`required: false` émis (1), libellé non échappé (4), nom non échappé (4),
props de champ arbitraires (2), `id` inventé (21), `form` non bloquant (1),
validateur `form_fields` ignoré (3), formulaire omis mais enfants rendus (8),
verbe supplémentaire accepté (4). Toutes les mutations sont détectées.

## Validations ciblées

Exécutions pytest depuis le scratchpad.

| Commande | Résultat |
|---|---|
| `pytest -q tests/test_generate_forms.py` | 62 réussis |
| `pytest -q tests/test_generate_simple.py tests/test_generate_control_flow.py tests/test_generate_tables.py tests/test_generate_buttons.py tests/test_generate_forms.py tests/test_design_bindings.py tests/test_design_form_fields.py tests/test_preview_render.py tests/test_preview_data.py tests/test_preview_responsive.py` | 523 réussis |
| `pytest -q tests/test_design_schema.py` (après correction) | 28 réussis |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` / `ruff format --check .` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |

## Validation globale

Lancée **après** toute la documentation et ce rapport, juste avant le
commit : `pytest` **3529 réussis** en 39 s, aucun échec. Une première exécution, avant
la correction de `test_design_schema.py`, donnait 1 échec et 3528 réussis :
c'est elle qui a révélé la régression de `cefee33`. `python -m pip check` :
No broken requirements found.

## Packaging

Wheel `forge_design-0.1.0.dev0-py3-none-any.whl` dans `tmp/wheels`, SHA-256
`25598b521c6190d15ac27bfa862cbc064a034fef5f761042b224cd4ec536c30f`. Elle
contient `generate/forms.py`, `actions.py` et `buttons.py`.

## Installation réelle

Installation `--no-deps --no-index --target` temporaire, `python -I`, origine
installée vérifiée. Le Design et le contrat du critère de fin produisent
exactement :

```html
<section>
  <form action="/contacts" method="post" class="space-y-4" hx-post="/contacts" hx-target="#content">
    <label>Adresse e-mail<input type="email" name="email" required></label>
  </form>
</section>
```

Seule la génération est vérifiée : aucune interaction navigateur ni runtime
HTMX n'a été exécuté.

## Limites restantes

- Pas de bouton de soumission : un formulaire généré peut ne pas pouvoir être
  envoyé sans HTMX ni bouton explicite. C'est le prochain ticket.
- `GET` et `POST` seulement ; `POST` avec `csrf: true` est refusé ; aucune
  protection CSRF générée.
- Pas de `value`, `placeholder`, `textarea`, `select`, `radio` ni upload.
- `alert` toujours non généré.
- Preview et éditeur Web sans rendu de formulaire réel.

## État Git final

Un commit sur `main`, rapport inclus, sans push.
Message : `feat: générer les formulaires HTMX (FD-INTERACT-003)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Hash :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-INTERACT-003.md
```
