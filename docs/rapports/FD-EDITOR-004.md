# Rapport — FD-EDITOR-004

## Ticket et objectif

Première interface Web de l'éditeur : ouvrir un `.design.json` existant,
afficher son arbre, sélectionner un bloc, ajouter, supprimer, déplacer,
configurer binding, condition, props et colonnes, puis sauvegarder par
`write_design`. Le ticket utilise exclusivement les API d'EDITOR-001 à 003,
`design/io.py` et `contracts/reader.py`, sans logique d'édition dans le Web.

## État Git initial

`main` synchronisée avec `origin/main` à `49cabd5` — FD-EDITOR-003, poussé
par l'utilisateur. Seule modification préexistante :
`docs/rapports/FD-CONTRACT-001.md`, préservée hors commit.

## Routes

`GET /editor`, `POST /editor/action` et `POST /editor/save`, toutes
`no_store`, enregistrées dans `server.py`. Les POST utilisent `csrf=False`
avec le contrôle d'origine stricte existant, comme les autres mutations sans
session ; aucun middleware global n'est désactivé.

**Écart à arbitrer.** Le ticket impose l'enregistrement après chaque action
(§14) et demande aussi `POST /editor/save` (§6). Chaque action étant déjà
enregistrée, `/editor/save` est implémenté comme une **réécriture explicite
dans la forme canonique** de `write_design` (révision lue, écriture
atomique) : utile pour normaliser un fichier écrit à la main, sans autre rôle.
Cette route est à conserver, à retirer ou à redéfinir selon la décision.

## Architecture Web

`web/editor.py` fait le parsing HTTP, appelle `read_design`,
`read_view_contract`, une seule fonction de `editor/*` et `write_design`, puis
construit le contexte de rendu. Il ne contient aucune règle d'édition : les
listes de choix proposées (`ALLOWED_CHILDREN`, `can_contain`) ne servent qu'à
l'affichage, et l'API editor reste l'autorité. Aucun Tool n'est ajouté (5
Tools). `editor/` et `design/` ne sont pas modifiés.

## Chargement Design

`design` est un paramètre relatif à `mvc/views`, validé par `design_source`.
`read_design(root, design)` est ensuite appelé : absent donne 404, chemin
refusé 400, projet devenu indisponible 409. Si le Design n'a pas pu être
chargé, les diagnostics sont affichés sans arbre partiel. S'il est chargé mais
présente des diagnostics (imbrication invalide), l'arbre est affiché sans
aucun formulaire d'édition.

## Chargement Contract

`read_view_contract(root, design.source_contract)` : `source_contract` suit la
même convention, relative à `mvc/views`, que le lecteur. Le contrat n'est pas
déduit du template. Introuvable, refusé ou invalide : l'arbre reste visible
avec un message, et binding, condition et colonnes sont désactivés.

## Projection arbre

`EditorNodeView` est une projection **plate en ordre préfixe**, construite
itérativement et bornée par `MAX_DESIGN_NODES`. Le rendu se fait en une simple
boucle Jinja, sans récursion. L'indentation passe par de vraies listes `<ul>`
imbriquées (`opens`, `close_levels`), comme dans le Template Viewer.

**Défaut corrigé avant les tests.** Une première version indentait avec
`style="--depth: N"`, ce que la CSP de Forge (`style-src 'self'`, sans
`unsafe-inline`) aurait bloqué.

## NodePath HTTP

`format_node_path` / `parse_node_path` : `""`, `"0"`, `"0.2"`. Forme
canonique stricte (entiers décimaux ASCII, sans zéro initial, séparés par un
seul point) et bornée en longueur et en profondeur. `node` invalide ou absent
de l'arbre : 400, sans repli. Paramètre inconnu, dupliqué ou `notice` hors de
la liste : 400.

## Ajout

Types proposés : `ALLOWED_CHILDREN[type]`, triés. `append_design_block` est la
seule autorité, et un type interdit ou inconnu envoyé directement donne 422.
Bloc sélectionné ensuite : `affected_path`.

## Suppression

Un bouton par bloc, sauf la page ; `remove_design_block`. La racine envoyée
directement donne 422. Bloc sélectionné ensuite : le parent.

## Déplacement

Destinations proposées : blocs hors du sous-arbre source acceptant le type.
`move_design_block` ; une destination incompatible ou dans la source donne
422, et un déplacement déjà en dernière position est un no-op. La matrice
réelle étant acyclique, le filtre du sous-arbre n'est observable qu'avec une
règle élargie (testé).

## Binding

`<select>` de toutes les variables (avec leur type) et actions du contrat,
plus « Aucun binding » (`""` donne `None`). `set_design_binding` tranche, et
une règle recopiée est absente du Web.

## Visible if

Variables `boolean` du contrat, plus « Toujours visible ».
`set_design_visibility` tranche (une variable `string` donne 422).

## Props

Champ JSON lu par `loads_strict_json` : un objet, ou vide pour supprimer.
JSON invalide, autre qu'un objet, `NaN` ou clé dupliquée donnent 400 ; une
valeur refusée par le modèle (liste) donne 422. Toutes les props sont
exposées, sans restriction à `class` et `tag`.

## Colonnes

Tables seulement. Tableau JSON converti explicitement en `TableColumn` (une
forme invalide donne 400). `set_table_columns` tranche (un champ inconnu donne
422). Vide supprime la propriété, `[]` donne aucune colonne (distinction
testée).

## Sauvegarde Design

`changed=True` : `write_design(root, design, result.design,
expected_revision=read.revision)`, puis 303. `changed=False` sans diagnostic :
**aucun appel** à `write_design` (espion), puis 303 avec `notice=noop`.
Diagnostics : 422 avec les messages `editor.*`, et rien n'est écrit.

## Révision attendue

Toujours la révision de la lecture de la même requête (espion : une écriture,
révision non nulle). Une mutation qui passerait `None` fait échouer 11 tests.

## Conflits

`DesignWriteConflictError` : 409, « Le Design a été modifié depuis sa lecture.
Rechargez la page avant de recommencer. » (modification externe simulée entre
la lecture et l'écriture ; le contenu externe est conservé).
`InvalidDesignForWriteError` : 422, diagnostics affichés, présenté comme un
défaut interne. `DesignWriteError` : 500, « Sauvegarde incertaine », car
`write_design` ne garantit pas l'absence de publication.

## Sécurité POST

Dans cet ordre : `is_local_action` (sinon 403), Content-Type urlencodé
(sinon 415), projet courant (sinon 409). Une requête porte **exactement** les
champs de son action : un champ manquant, en trop (deux propriétés à la fois)
ou dupliqué donne 400. Champs bornés à 64 Kio, sous la limite de corps Forge
d'1 Mo ; la borne est testée avec un JSON *valide*. Actions dépendant du
contrat sans contrat valide : 409 côté serveur, sans s'appuyer sur les
boutons désactivés.

## Stateless

Aucun état d'éditeur en mémoire. Deux applications sur le même projet : la
mutation de l'une est lue par l'autre ; une modification externe est relue à
la requête suivante. GET et POST relisent le Design et le contrat.

## No-store

`Cache-Control: no-store` vérifié sur GET, sur une redirection 303 et sur une
réponse 422.

## Échappement HTML

Autoescape Jinja sans `|safe` : une prop et un binding hostiles
(`<script>`, `<img onerror>`) sont rendus inertes.

## Absence de JavaScript

Formulaires HTML, Jinja et CSS (`shell.css` étendu). Aucun fichier JS ajouté
ni modifié.

## Absence de génération template

Le template `.html` du projet est inchangé (octets et mtime), aucun
`.forge-design/` n'est créé, et seul le `.design.json` est écrit.

## Fichiers créés

- `forge_design/web/editor.py`
- `forge_design/web/templates/editor.html`
- `tests/test_web_editor.py`
- `docs/rapports/FD-EDITOR-004.md`

## Fichiers modifiés

- `forge_design/web/server.py` : trois routes.
- `forge_design/web/templates/layout.html` : lien « Éditeur ».
- `forge_design/web/static/shell.css` : arbre et panneau.
- `pyproject.toml` : `templates/editor.html` en package-data.
- `docs/editor/structural-editor.md`, `docs/02-architecture.md`

Non modifiés : `editor/`, `design/`, `generate/`, `safewrite/`, `tools/`,
`app.py`, le JavaScript, le contrat de stockage.

## Tests ajoutés

`tests/test_web_editor.py` : 74 cas, par HTTP réel.
- Chemins HTTP (4 allers-retours, 14 formes refusées).
- GET : sans projet, arbre ordonné et imbriqué, choix d'ajout et de
  destinations, racine par défaut, Design absent, 4 chemins refusés, Design
  invalide et mal imbriqué, sans contrat, contrat invalide, 6 `node`
  invalides, 3 paramètres invalides, formulaire d'ouverture, échappement.
- POST : 403, 415, 409, 7 actions mal formées ; ajout (redirection, fichier,
  relecture), 3 ajouts refusés, suppression, déplacement, binding, contrat
  absent, condition, props, colonnes, no-op sans écriture, conflit, révision
  passée, sauvegarde canonique.
- Deux applications, absence d'I/O directe, template et journal intacts,
  no-store, registre, filtre du sous-arbre avec règle élargie.

Vérification par mutation (copie restaurée ensuite) : origine, Content-Type,
champs exacts, doublons, borne de champ, contrat exigé, révision, no-op,
`node` introuvable, `notice`, zéro initial, filtre du sous-arbre. Toutes les
mutations sont détectées. Deux d'entre elles survivaient à la première
version des tests : la borne (le test envoyait un JSON invalide, refusé pour
une autre raison) et le filtre (inobservable avec la matrice réelle). Les deux
tests ont été corrigés.

## Validations ciblées

| Commande | Résultat |
|---|---|
| `pytest -q tests/test_web_editor.py` | 74 réussis |
| `pytest -q tests/test_editor_structure.py tests/test_editor_properties.py tests/test_web_editor.py tests/test_design_io.py tests/test_view_contract_reader.py tests/test_web_server.py` | 508 réussis |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` / `ruff format --check .` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |

## Validation globale

`pytest` : **3237 réussis** en 33 s. `python -m pip check` : No broken
requirements found.

## Packaging

`python -m pip wheel --no-deps --wheel-dir tmp/wheels .` produit
`forge_design-0.1.0.dev0-py3-none-any.whl`, SHA-256
`fbc449d845c4a6775ff074f420e5624711fa78324de0e54f823370b89347e22e`. Elle
contient `web/editor.py`, `templates/editor.html` et `shell.css` à jour, ainsi
que le package `editor/` ; aucun fichier de `tests/` ni de `tmp/`.

## Installation réelle

Installation `--no-deps --no-index --target` temporaire ; `python -I` depuis un
cwd temporaire, avec vérification de l'origine installée. Le serveur réel tourne
sur un port éphémère avec un projet Forge temporaire :
1. ouverture du projet, `GET /editor` : 200, arbre affiché, `no-store` ;
   `/shell.css` contient les styles de l'éditeur ;
2. `POST append` d'une carte : 303 et `.design.json` réellement réécrit ;
3. `GET` de la redirection : la carte est affichée avec la notice ;
4. `POST props` puis `GET` : la prop est affichée et enregistrée ;
5. template `.html` intact (octets et mtime), aucun `.forge-design/`.

## Limites restantes

- `/editor/save` : rôle à confirmer (voir « Routes »).
- Pas d'inventaire des Designs : l'ouverture se fait par chemin explicite.
- Props et colonnes saisies en JSON brut, sans aide à la saisie (prévu pour
  FD-EDITOR-005).
- Pas de confirmation avant suppression, ni d'undo.
- Rendu non vérifié visuellement dans un navigateur ; le HTML, le CSS
  (servi, sans style inline) et le comportement HTTP sont testés.

## État Git final

Un commit sur `main`, rapport inclus, sans push.
Message : `feat: ajouter l'éditeur structurel Web (FD-EDITOR-004)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Hash :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-EDITOR-004.md
```
