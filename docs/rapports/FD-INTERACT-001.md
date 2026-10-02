# Rapport — FD-INTERACT-001

## Ticket et objectif

Rendre générable un bloc `button` lié à une action du contrat : produire un
`<button>` HTML portant des attributs HTMX déclaratifs (`hx-get`/`hx-post`,
`hx-target`, `hx-swap`, `hx-confirm`), sans modifier les modèles Design et
Contract, sans script, CDN, runtime HTMX ni CSRF inventé. Les formulaires HTMX
sont hors périmètre.

## État Git initial

`main` synchronisée avec `origin/main` à `ff2f899` — FD-EDITOR-006. Seule
modification suivie préexistante : `docs/rapports/FD-CONTRACT-001.md`,
préservée hors commit.

## Représentation Design

Inchangée : `button` avec `binding` et `props` existants. Aucun `hx_get`,
`target` ni `interaction` dans le schéma. `design/models.py` et le schéma ne
sont pas modifiés.

## ViewAction

Le `ViewAction` existant (`method`, `path`, `csrf`) est la seule source :
aucun second format. La revalidation du contrat déjà faite par le générateur
couvre un modèle muté (une méthode `get` en minuscules donne
`generate.invalid_contract`, testé).

## Binding button

La résolution reste celle de `validate_design_bindings` (règle `button →
action`). `simple.py` ajoute seulement `button` à l'ensemble des bindings
**bloquants** (`title`, `text`, `button`) : une action inconnue ou un binding
vers une variable donne `generate.invalid_binding`, sans template. Un bouton
sans binding donne `generate.button_missing_action` : bouton omis, reste du
template généré, `complete=False`.

## GET

`GET` donne `hx-get`. Sortie exacte testée :
`<button type="button" hx-get="/contacts/create">Action</button>`. L'URL vient
uniquement de `ViewAction.path` (testé avec un chemin sans rapport avec le nom
de l'action), sans vérification contre le routeur ni import du projet.

## POST

`POST` donne `hx-post` : `<button type="button" hx-post="/contacts">Action</button>`
(sans `csrf` et avec `csrf: false`).

## Props HTMX

Liste blanche : `class`, `hx-target`, `hx-swap`, `hx-confirm`. Ordre
d'émission fixe (`type`, `class`, méthode, `hx-target`, `hx-swap`,
`hx-confirm`), indépendant de l'ordre des props, sur une ligne comme le reste
du générateur. Les valeurs `hx-*` sont opaques : `#content`, `closest tr`,
`this`, `innerHTML`, `beforeend swap:1s` et `none` sont acceptées sans
analyse. Une prop inconnue (`onclick`, `style`, `hx-trigger`, `hx-get`,
`hx-post`, `data-secret`, `tag`) donne `generate.unsupported_prop`,
**non émise** (testé : aucune trace de sa valeur dans le template).

**Code ajouté.** `generate.invalid_htmx_prop` pour une prop `hx-*` présente
mais vide ou non textuelle. Le ticket exige une « chaîne non vide si
présente » (§19-22) et une préparation qui écarte les « props invalides
bloquantes » (§42) ; le bouton est donc omis.

## Classes

`class` est conservée telle quelle (`px-4 py-2 rounded`), sans traduction. Une
`class` non textuelle suit la politique existante (`unsupported_prop`,
ignorée).

## Escaping

`class`, le chemin et les valeurs `hx-*` passent par `escaped` du générateur :
`html.escape(quote=True)`, `{`/`}` neutralisées, CR/LF encodés. Cinq valeurs
hostiles sont testées (`"><script>`, `{{ secret }}`, `{% include %}`,
`{# #}`, CR/LF) dans le chemin, `class`, `hx-target` et `hx-confirm` : une
seule balise `<button>`, aucun `<script>`, aucun délimiteur Jinja, et l'AST
Jinja ne contient ni variable, ni attribut, ni inclusion.

## Conditions

L'enveloppe `{% if … %}` existante est réutilisée (sortie exacte testée). Un
bouton omis ne laisse pas de condition vide. Une condition inconnue ou non
booléenne garde `generate.invalid_condition`.

## CSRF

Aucun jeton, champ ni en-tête généré. `GET` est généré quel que soit `csrf`
(`csrf: true` compris). `POST` sans `csrf` ou avec `csrf: false` est généré
sans protection fournie par Forge Design, ce qui est documenté. `POST` avec
`csrf: true` donne `generate.unsupported_csrf` et le bouton est omis : Forge
Design ne connaît ni jeton, ni session, ni nom de champ.

## Méthodes reportées

`PUT`, `PATCH`, `DELETE` et `HEAD` donnent `generate.unsupported_action_method`
et le bouton est omis.

## Preview inerte

`forge_design/preview/` n'est pas modifié. Test ajouté : avec des props
`hx-*`, `render_preview` n'émet ni `hx-` ni chemin, rend un
`<button data-forge-design-type="button"…>` et signale
`preview.unsupported_prop`.

## Absence de runtime HTMX

Aucun `<script>`, CDN (`unpkg`, `htmx.org`) ni mention CSRF dans le template
(testé). Aucune dépendance npm, et aucune vérification qu'HTMX est installé
dans le projet cible.

## Pureté

`open`, `os.open`, `socket` et `subprocess` sont bloqués pendant la
génération. Le module ne référence ni I/O ni routeur.

## Déterminisme

Même Design et même contrat donnent le même résultat.

## Non-mutation

Les dumps du Design et du contrat sont identiques avant et après.

## Fichiers créés

- `forge_design/generate/buttons.py`
- `tests/test_generate_buttons.py`
- `docs/rapports/FD-INTERACT-001.md`

## Fichiers modifiés

- `forge_design/generate/simple.py` : `button` dans le dispatch, préparation
  avant émission, binding bloquant, actions transmises.
- `tests/test_generate_simple.py` : `button` retiré de
  `test_unsupported_branches`, qui couvre encore `form`, `field` et `alert`
  (ajustement prévu par le §95).
- `docs/generate/template-generation.md` : section « Boutons HTMX ».
- `docs/02-architecture.md` : schéma et paragraphe.

Non modifiés : `design/`, `contracts/`, `preview/`, `editor/`, `web/`,
`safewrite/`, `tools/`, `app.py`, `pyproject.toml`, le JavaScript, le contrat
de stockage.

## Tests ajoutés

`tests/test_generate_buttons.py` : 52 cas. GET exact, POST (2), GET avec
`csrf: true`, ordre fixe des props, critère de fin, 7 valeurs HTMX opaques,
`class` seule, binding absent, action inconnue (2), contrat sans actions, 4
méthodes refusées, `POST` `csrf: true`, méthode mutée, URL du contrat, 7 props
inconnues, 4 valeurs `hx-*` invalides, `class` non textuelle, 5 valeurs
hostiles, condition, condition non laissée vide, 2 conditions invalides,
budget exact et dépassement, pureté, déterminisme et non-mutation, absence de
script et de CDN, portée du module, preview inerte.

Vérification par mutation, lancée depuis le scratchpad avec restauration
vérifiée : binding absent toléré (1 échec), toute méthode acceptée (5),
`csrf: true` ignoré (1), `csrf` refusé aussi en `GET` (1), props arbitraires
émises (8), valeur `hx-*` vide tolérée (1), chemin non échappé (5), `hx-*`
non échappé (5), `type="button"` absent (16), binding de bouton non bloquant
(3). Toutes les mutations sont détectées.

## Validations ciblées

Exécutions pytest depuis le scratchpad.

| Commande | Résultat |
|---|---|
| `pytest -q tests/test_generate_buttons.py` | 52 réussis |
| `pytest -q tests/test_generate_simple.py tests/test_generate_control_flow.py tests/test_generate_tables.py tests/test_generate_buttons.py tests/test_generate_diff.py tests/test_design_bindings.py tests/test_conditional_bindings.py tests/test_table_bindings.py tests/test_preview_data.py tests/test_preview_render.py tests/test_preview_responsive.py` | 511 réussis (avant l'ajout du test de preview inerte) |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` / `ruff format --check .` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |

## Tests non exécutés

- Suite globale : non obligatoire pour ce ticket ciblé sur la génération ;
  régressions de génération, de bindings et de preview vertes.
- Wheel : `generate/buttons.py` appartient à un package existant, sans API
  publique nouvelle.
- Tests Editor et Web : aucun fichier partagé touché.
- Node, MkDocs : non concernés.

## Limites restantes

- Libellé fixe `Action`, en attendant une représentation Design explicite du
  libellé.
- `GET` et `POST` seulement ; `csrf: true` en `POST` est refusé.
- Aucune prop HTMX au-delà de `hx-target`, `hx-swap` et `hx-confirm`
  (`hx-trigger`, `hx-indicator`, `hx-vals`… reportées).
- Aucune vérification que le chemin existe dans le routeur ni qu'HTMX est
  chargé.
- Pas d'assistant HTMX dans l'éditeur Web : configuration par le binding et
  le JSON des props.
- Formulaires HTMX : FD-INTERACT-002, après définition de l'usage des
  contrats par `form` et `field`.

## État Git final

Un commit sur `main`, rapport inclus, sans push.
Message : `feat: générer les boutons HTMX (FD-INTERACT-001)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Hash :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-INTERACT-001.md
```
