# Rapport — FD-EDITOR-005

## Ticket et objectif

Assister l'édition de `props.class` dans l'éditeur Web (remplacer la chaîne,
ajouter et retirer une classe) sans modifier le modèle Design, le moteur
editor, le stockage, ni ajouter de dépendance frontend. La chaîne réellement
enregistrée reste visible et éditable.

## État Git initial

`main` synchronisée avec `origin/main` à `087abfb` — FD-EDITOR-004A. Seule
modification suivie préexistante : `docs/rapports/FD-CONTRACT-001.md`,
préservée hors commit. Le dossier `storage/` de 09:03 (FD-EDITOR-004) est
toujours sur le disque, ignoré par `/storage/`, non ouvert et non modifié.

## Source réelle props.class

Aucune clé, aucun fichier ni aucune métadonnée UI ajoutés : le contrat de
stockage et `design/models.py` sont inchangés. Toutes les actions construisent
un nouveau mapping `props` et appellent `set_design_props`, puis
`write_design` ; le Web ne modifie jamais un modèle lui-même (espion : un
ajout appelle `set_design_props` avec `{"class": "p-4 flex"}`).

## Helpers Tailwind

`forge_design/web/tailwind_classes.py`, module pur (sans I/O, testé) :
`parse_class_tokens`, `validate_class_token`, `current_classes`,
`set_classes`, `add_class`, `remove_class`, `ClassNotEditableError` et
`SUGGESTIONS`. Ils ne touchent qu'à la clé `"class"` d'une copie et ne
mutent pas l'entrée.

## Tokens

Découpage sur les blancs ASCII (espace, `\t`, `\n`, `\r`, `\f`, `\v`). Un
blanc Unicode non ASCII reste dans le token, sans interprétation. Un token est
refusé s'il est vide ou contient un blanc ASCII ou NUL. Aucune regex Tailwind :
`w-[37px]`, `md:grid-cols-2`, `hover:bg-slate-100`, `[mask-type:luminance]`,
`w-[calc(100%-2rem)]`, `md:hover:bg-red-500`, `dark:text-white`,
`!font-bold` et `group-hover:underline` sont acceptés.

## Canonicalisation

Toute action qui modifie la chaîne l'écrit avec un espace unique entre tokens,
sans blanc en tête ni en fin (`"  b\ta   c "` donne `"b a c"`). Le JSON des
props reste le moyen d'écrire exactement une autre chaîne.

## Doublons

Pas de nettoyage global : `mx-auto mx-auto py-8` plus `text-xl` donne
`mx-auto mx-auto py-8 text-xl`. Ajouter un token présent est un no-op ; le
retirer enlève toutes ses occurrences exactes (`mx-auto-x` est conservé).

## Suggestions

Six catégories (Layout, Largeur, Espacement, Texte, Couleurs, Bordures),
environ 40 tokens. Liste courte, non normative, sans doublon et sans source
externe ; une classe absente reste autorisée. Affichées en boutons d'ajout
(un formulaire par catégorie, seul le bouton cliqué transmet `class_token`,
ce qui respecte la règle des champs exacts) et dans une `<datalist>`. Une
suggestion déjà présente est désactivée.

## Chaîne libre

Champ texte avec la chaîne réelle (`value="mx-auto py-8"`), visible, copiable
et remplaçable par `tailwind_set`.

## Ajout

`tailwind_add` : en fin, sans tri, la clé `class` gardant sa position. Sur un
bloc sans props, le résultat est `{"class": token}`. Un token avec blanc ou
NUL donne 400 sans écriture.

## Suppression

`tailwind_remove` : toutes les occurrences exactes. Si `class` était la seule
prop, `props` devient `{}`, conformément au §31.

## Remplacement

`tailwind_set` : chaîne canonique ; une chaîne vide supprime la clé `class`
seulement.

## Conservation des autres props

Avec `{"class": "mx-auto py-8", "tag": "section", "data-test": "hero"}`,
l'ajout de `max-w-5xl` ne change que `class` ; l'ordre des clés et l'autre
bloc du Design sont identiques (testé sur disque).

## Class non-string

`{"class": true}` ou `{"class": 3}` : la valeur est affichée (`<code>true</code>`),
l'assistant est désactivé et les trois actions répondent 422 sans écrire. Il
n'y a pas de conversion, et la correction par le JSON des props fonctionne
(testé).

## Interface Web

Section « Classes Tailwind » sous le JSON des props : chaîne réelle, tokens
avec « Retirer », ajout libre et suggestions. Aucun style inline, à cause de
la CSP (testé : pas de `style=`) ; les tokens sont stylés par `shell.css`. Les
tokens sont échappés par Jinja, sans `|safe`. Aucun JavaScript.

## Sécurité POST

Actions ajoutées à `_ACTION_FIELDS` avec leurs champs exacts. Inchangé :
`is_local_action` (403), Content-Type (415), champ en trop ou manquant (400),
borne de 64 Kio, révision attendue. Un conflit externe avant `write_design`
donne 409 et le contenu externe est conservé. Un chemin inconnu donne 422
(`editor.path_not_found`, posé par l'éditeur lui-même). Après l'action, 303
vers le même bloc.

## No-op

Aucun `write_design` (espion) dans cinq cas testés : `tailwind_set` de même
forme canonique, ajout d'un token présent, retrait d'un token absent, chaîne
vide et retrait sur un bloc sans props. Pour cela, les helpers rendent le
mapping d'origine **tel quel**, même `None`, et `set_design_props` constate le
no-op. Sans cette précaution, un bloc sans props aurait reçu `{}` et été
réécrit.

## Absence de parser Tailwind

Les préfixes et les valeurs arbitraires sont des tokens opaques. Aucune
validation CSS.

## Absence de dépendance frontend

Ni tailwindcss, ni npm, ni PostCSS, ni Vite, ni JavaScript. `pyproject.toml`
est inchangé : le module appartient déjà au package `forge_design.web`.

## Fichiers créés

- `forge_design/web/tailwind_classes.py`
- `tests/test_tailwind_classes.py`
- `docs/rapports/FD-EDITOR-005.md`

## Fichiers modifiés

- `forge_design/web/editor.py` : actions, `_node_props`, `_tailwind`,
  contexte de rendu. `EditorNodeView.props` est maintenant typé `PropValue`.
- `forge_design/web/templates/editor.html`
- `forge_design/web/static/shell.css`
- `tests/test_web_editor.py`
- `docs/editor/structural-editor.md`, `docs/02-architecture.md` (une phrase).

Non modifiés : `editor/`, `design/`, `generate/`, `safewrite/`, `contracts/`,
`tools/`, `app.py`, `pyproject.toml`, le JavaScript, le contrat de stockage.

## Tests ajoutés

- `tests/test_tailwind_classes.py` : 44 cas. Découpage (8), NUL, 9 tokens
  libres, 9 tokens invalides, ajout avec autres props et ordre, nouvelle clé en
  fin, no-op par identité, ordre et doublons, retrait de toutes les
  occurrences, absence, dernier token, remplacement canonique, no-op canonique,
  effacement, doublons, valeurs non-chaîne (3), suggestions, pureté.
- `tests/test_web_editor.py` : 104 cas (27 nouveaux). Rendu, ajout et
  relecture, 4 tokens libres, bloc sans props, 5 tokens invalides × 2 actions,
  retrait de doublons, `{}`, remplacement limité à `class`, effacement, 5
  no-op sans écriture, non-chaîne (2), chemin inconnu, sécurité, conflit, appel
  de `set_design_props`.

**Tests existants ajustés.** `test_selected_node_and_choices` vérifiait
l'absence totale de ` disabled` pour prouver que les contrôles du contrat
étaient actifs ; les suggestions déjà présentes étant désormais désactivées,
il vérifie précisément les deux `<select>` du contrat.

Vérification par mutation, lancée **depuis le scratchpad** (aucun nouveau
`storage/`), avec restauration : doublon ajouté (2 échecs), retrait d'une
seule occurrence (2), no-op canonique ignoré (2), token non validé (14),
non-chaîne convertie (5), `{}` au lieu de l'identité (2), tri (11), statut 422
(2), statut 400 (5). Toutes les mutations sont détectées.

## Validations ciblées

Toutes les exécutions pytest sont lancées depuis le scratchpad.

| Commande | Résultat |
|---|---|
| `pytest -q tests/test_tailwind_classes.py` | 44 réussis |
| `pytest -q tests/test_web_editor.py tests/test_tailwind_classes.py` | 148 réussis |
| `pytest -q tests/test_editor_structure.py tests/test_editor_properties.py tests/test_web_editor.py tests/test_tailwind_classes.py tests/test_web_server.py` | 449 réussis |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` / `ruff format --check .` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |

Suite globale non lancée : le ticket ne touche que la couche Web de l'éditeur,
couverte par les régressions ci-dessus.

## Packaging

Wheel `forge_design-0.1.0.dev0-py3-none-any.whl` dans `tmp/wheels`, SHA-256
`ff0e2f58163b469091ad793018eea1cbb78508a6e800be3a777e72cc0c48aebd`. Elle
contient `web/tailwind_classes.py`, `editor.html` et `shell.css` à jour.

## Installation réelle

Installation `--no-deps --no-index --target` temporaire, `python -I`, origine
installée vérifiée, serveur réel, Design avec
`{"class": "max-w-5xl py-8", "tag": "section", "data-test": "hero"}` :
1. la classe réelle est visible ;
2. ajout de `mx-auto` : `max-w-5xl py-8 mx-auto`, affiché au GET ;
3. retrait de `mx-auto` : retour à l'état initial, plus affiché ;
4. `tag`, `data-test` et l'ordre des clés sont inchangés à chaque étape.

## Limites restantes

- Pas d'assistant pour les variantes (breakpoint, hover, focus, dark) : saisie
  libre seulement.
- Aucune vérification que les classes existent dans le Tailwind du projet.
- `tailwind_set` sur une chaîne non canonique dont les tokens sont identiques
  est un no-op : la chaîne n'est pas réécrite. Pour la normaliser, il faut
  passer par une autre action ou par le JSON des props.
- Pas de prévisualisation (prochain ticket).

## État Git final

Un commit sur `main`, rapport inclus, sans push.
Message : `feat: assister l'édition des classes Tailwind (FD-EDITOR-005)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Hash :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-EDITOR-005.md
```
