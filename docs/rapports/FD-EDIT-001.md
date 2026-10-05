# Rapport — FD-EDIT-001

Normatif : [Actions bornées des modules](../modules/module-actions.md) ;
contexte : [Architecture des modules](../modules/module-architecture.md),
[Hôte des modules](../modules/module-host.md).

## Ticket et objectif

Ajouter au cœur un contrat générique et borné d'actions POST pour les modules
spécialisés. Un module activé déclare une mutation métier ; Forge Design
l'exécute (origine, payload, lecture, révision, validation, écriture
atomique, historique, statut HTTP) sans jamais transmettre au module Request,
Response, Router, racine de projet ni système de fichiers. Le ticket prouve le
contrat avec un module témoin limité aux tests : aucune action électrique,
aucune édition Circuit.

## État Git initial

```text
$ git log --oneline -5
c308c6c refactor: retirer Circuit du cœur (FD-MODULES-003)
2a0db00 feat: implémenter l'hôte des modules spécialisés (FD-MODULES-002)
558933b feat: définir le contrat des modules spécialisés (FD-MODULES-001)
69f48d8 feat: migrer Debug Center sur le Graphic Core (FD-GRAPHICS-008)
c24dc6c feat: ajouter la minicarte au Graphic Core (FD-GRAPHICS-007)
$ git rev-parse --short HEAD          → c308c6c
$ git rev-parse --short origin/main   → c308c6c
$ git rev-list --left-right --count origin/main...HEAD → 0 0
$ git status --short
 M docs/rapports/FD-CONTRACT-001.md
```

`FD-CONTRACT-001.md` reste une modification locale préexistante, hors commit.

## État ForgeDesign-Circuit

Commit local `d8d1912 feat: extraire Circuit depuis Forge Design`, arbre
propre. `origin` (`caucrogeGit/ForgeDesign-Circuit`) est toujours vide
(`git ls-remote` ne renvoie rien). Ce ticket ne modifie pas ce dépôt et ne le
pousse pas. Sa suite reste verte contre le cœur modifié (324 réussis, Pyright
strict 0 erreur), ce qui montre que l'ajout est compatible avec un module
d'API 1 existant.

## Pourquoi un contrat d'action

FD-MODULES-003 a conclu que l'édition pilotée par Circuit pouvait commencer,
à condition d'ouvrir d'abord une voie de mutation côté hôte. Sans contrat, un
module devrait recevoir une requête ou écrire lui-même : la frontière (le cœur
possède le système de fichiers, la révision et l'historique) tomberait au
premier geste. Le contrat fixe cette voie avant le premier besoin réel, sur un
témoin, sans figer de vocabulaire métier dans le cœur.

## Périmètre

Fait : `ModuleAction`, payload borné, jeton de révision, routes POST exactes,
cycle lecture → handler → écriture, matrice de statuts, capability gate,
notice PRG, témoin de test, documentation.

Non fait, conformément au ticket : déplacer, tourner, créer ou supprimer un
composant, fil, ports graphiques, glisser, snap, undo/redo, routage
interactif, simulation, UI d'action, modification du Graphic Core ou de
ForgeDesign-Circuit.

## Architecture

```text
navigateur ── POST /modules/<id>/actions/<action>
   ─▶ module_action (web/modules.py)        origine, 415, 413, enveloppe, champs
   ─▶ ModuleHost.execute_action (modules/host.py)
        read_specialized_resource ─▶ jeton ─▶ handler(document, payload)
        ─▶ no-op ? ─▶ write_specialized_resource ─▶ history.jsonl
   ─▶ ACTION_STATUS (web/modules.py) ─▶ 303 vers la page ressource ou page d'erreur
```

Nouveau fichier `forge_design/modules/actions.py` : contrat public, payload,
jeton. Aucun nouveau module JS, aucun asset, aucune modification du Graphic
Core.

## ModuleAction

`ModuleAction(id, resource_type, fields, handler, capability="edit")`, gelée
et validée à la construction :

- identifiant kebab-case d'au plus 48 caractères ;
- type kebab-case ;
- `fields` : tuple d'au plus 16 noms `[a-z][a-z0-9_-]*` d'au plus
  32 caractères, uniques, jamais réservés (`type`, `path`, `revision`,
  `_method`) ;
- handler appelable ;
- capacité du vocabulaire plateforme.

Le handler rend un `ModuleActionResult(resource)`, jamais une réponse.

## Déclaration des actions

`ModuleDescriptor.actions: tuple[ModuleAction, ...] = ()` accepte au plus
32 actions, aux identifiants uniques. Chaque action vise un type déclaré par le
module, `editable`, qui déclare `save` et la capacité de l'action. Sinon le
descripteur est refusé à la construction, et l'hôte le diagnostique comme
`descriptor-invalid`. `action_url(id)` calcule l'URL sous `base_url`, comme
`asset_url`.

## Compatibilité API module

**Décision M : `MODULE_API_VERSION` reste 1.**

- L'ajout est purement additif : un champ facultatif à défaut `()`.
- Tout descripteur d'API 1 existant reste valide sans modification :
  ForgeDesign-Circuit, inchangé, passe 324/324, et les témoins de
  FD-MODULES-002 aussi.
- Dans l'autre sens, un module qui déclarerait des actions et serait chargé
  par un cœur antérieur échouerait à la construction de son descripteur
  (argument inconnu). L'hôte le signalerait (`module-import-failed`) au lieu
  de l'ignorer en silence.

Incrémenter l'API aurait rendu incompatibles tous les modules lecture seule
sans aucun bénéfice.

## Namespace HTTP

`POST /modules/<module-id>/actions/<action-id>`, une route exacte par action
exposée, enregistrée dans `create_application` à côté des routes GET du
module. Aucun motif dynamique : `/actions/`, `/actions/inconnue` et
`/actions/rename-title/x` répondent 404. Un GET sur une route d'action répond
405 (Router Forge).

## Activation et capability gate

L'action est exposée si son module est actif, compatible, exposé et muni d'une
`UiEntry`, et si sa capacité **et** `save` figurent dans
`available_capabilities` (après la sonde de dépendances). La décision est
prise une fois au démarrage, dans `ModuleHost.__init__`.

**Décision (§19–20)** : une action indisponible n'est **pas routée** (404),
plutôt que refusée par `capability-unavailable`. C'est cohérent avec les pages
et les assets. Une sonde en échec rend aussi la capacité indisponible. Les
tests le couvrent : sonde `{"spice": False}` avec `edit` dépendant, sonde
levant une exception, module sans action, cœur sans module.

## Payload

**Décision A : formulaire `application/x-www-form-urlencoded` borné.**

| Critère | Formulaire | JSON |
|---|---|---|
| Simplicité | `request.body` déjà analysé par Forge | `request.json_body` |
| Forge `Request` existant | `parse_qs` : doublons visibles (une liste par clé) | `json.loads` permissif : JSON invalide → `{}` silencieux, doublons fusionnés, `NaN`/`Infinity` acceptés, octets bruts non conservés |
| Bornes | taille, nombre, longueur, doublons, tout contrôlable | corps mal formé indiscernable d'un objet vide |
| Types | texte + conversions strictes du cœur | scalaires natifs |
| Futur éditeur JS | `fetch(url, {method: "POST", body: new URLSearchParams(...)})` | `JSON.stringify` |
| Sécurité | garde d'origine identique à l'éditeur de Design (même format) | idem |

La recommandation du ticket (JSON strict, mais seulement si Forge le
supporte proprement) conduit au formulaire. Le JSON de Forge n'est pas
strict, et le rendre strict aurait exigé un parseur HTTP parallèle, ce que le
ticket interdit.

## Bornes

| Constante | Valeur | Contrôle |
|---|---|---|
| `MAX_MODULE_ACTION_BYTES` | 16 Kio | `Content-Length` → 413 ; Forge refuse déjà au-delà de 1 Mio |
| `MAX_MODULE_ACTION_FIELDS` | 16 | payload (enveloppe en plus) |
| `MAX_MODULE_ACTION_KEY_CHARS` | 32 | nom de champ |
| `MAX_MODULE_ACTION_TEXT_CHARS` | 1024 | valeur, sans caractère de contrôle (tabulation, CR, LF admis) |
| `MAX_MODULE_ACTIONS` | 32 | actions par module |
| `MAX_SAFE_INTEGER` | 2⁵³ − 1 | `integer()` |

## Parsing

Le cœur lit `request.body` tel que Forge l'a analysé :

- type de contenu exact (sinon 415) ;
- aucun paramètre d'URL ;
- chaque champ fourni une seule fois ;
- `_method` refusé ;
- `type`, `path` et `revision` extraits ;
- les autres champs forment le payload, qui doit être exactement `fields`.

`ModuleActionPayload` est un `Mapping[str, str]` en lecture seule, avec
accesseurs typés stricts : `text`, `integer` (forme canonique, entier sûr,
bornes), `number` (décimal canonique fini) et `boolean` (`true`/`false`).
`null` n'a pas de représentation (**refusé**, §119). Il n'y a ni liste ni
objet imbriqué. Le module valide la sémantique et lève
`ModuleActionPayloadError` (400) ou `ModuleActionRefused` (422).

## Révision publique

La révision interne (`SpecializedResourceRevision` : taille, mtime, sha256,
périphérique, inode, ctime) ne quitte jamais le serveur. La page ressource
publie `data-revision-token`, seulement si le type a une action exposée. Les
pages des modules en lecture seule restent identiques (vérifié par HTTP et en
navigateur).

## Token de révision

Options (§40) :

| Option | Décision |
|---|---|
| A. SHA-256 du contenu seul | rejetée : ignore la révision de l'hôte (métadonnées, identité du fichier) |
| B. HMAC à secret de processus | rejetée : il n'y a rien à authentifier (la garde d'origine protège), et un redémarrage invaliderait toutes les pages ouvertes |
| C. Encodage opaque des champs nécessaires | **retenue**, sous forme de condensat : `sha256(json([module, type, path, size, mtime_ns, digest, device, inode, changed_ns]))` |

C'est le minimum qui permette une comparaison exacte. Le serveur relit la
ressource, recalcule le jeton et compare avec `hmac.compare_digest`. Il ne
fait jamais confiance à des champs séparés venus du client. Le jeton est lié
au module, au type et au chemin.

## Lecture avant mutation

`read_specialized_resource` est toujours appelé avant le handler, avec le
codec du module :

| Résultat de la lecture | Réponse |
|---|---|
| Ressource introuvable | 404 |
| Chemin refusé (traversée, hors espace, suffixe, lien) | 400 |
| Illisible, invalide (bloquante) ou version non prise en charge | 409, diagnostics affichés, aucune action |

Une exception du codec est isolée (500). Le navigateur n'envoie que
l'intention, jamais le document (**décision D**).

## Handler métier

Le handler est appelé exactement par `action.handler(document, payload)`,
avec deux arguments positionnels et aucun nommé (test espion). Il ne reçoit ni
Request, ni Response, ni Router, ni racine, ni chemin, ni hôte, ni descripteur
de fichier (**décisions B, C**). Ses exceptions sont isolées et journalisées
sur `forge_design.modules`. Le message rendu au navigateur est borné, sans
trace.

## Immutabilité

Le handler doit rendre une **nouvelle** instance. L'hôte encode le document
lu avant l'appel, puis le réencode après. Si les encodages diffèrent, le
module a muté son entrée : 500 (« L'action du module a modifié le document
lu. »), et aucune écriture. Le test le vérifie par
`object.__setattr__` sur un document gelé.

## Validation

Il n'y a pas de validation dupliquée côté hôte. `write_specialized_resource`
appelle `codec.validate` et applique `blocking_validation_levels` du type.
Une erreur bloquante donne `InvalidSpecializedResourceError` → 422, avec les
diagnostics listés et aucune écriture. Un simple avertissement (niveau non
bloquant) n'empêche pas l'écriture, ce qui est testé (**décision G**).

## Écriture ResourceHost

L'écriture passe toujours par `write_specialized_resource(...,
expected_revision=révision lue)`, qui assure :

- le confinement du chemin ;
- l'encodage et sa borne de taille ;
- la validation ;
- la vérification de version ;
- la publication atomique (`replace`) ;
- la relecture du condensat.

Le module n'écrit jamais (**décision H** : le cœur écrit). Une action ne
touche qu'une ressource (**décision J**) et n'en lit aucune autre
(**décision K**). Elle ne lance aucun runtime (**décision L**).

## Historique

`write_specialized_resource` ajoute l'événement `write_specialized_resource`
(chemin) dans `.forge-design/history.jsonl`. Le format de l'historique V1 est
inchangé : pas d'`action_id` (§73), le chemin et le type suffisent ici. Le
module n'écrit jamais l'historique. L'historique persistant n'est pas un
undo/redo interactif.

## Conflits

Deux niveaux, sans retry automatique (**décision F** : c'est le
ResourceHost qui détecte) :

1. Le jeton reçu diffère de celui de la révision lue (autre onglet, autre
   écriture) : 409.
2. Le fichier change entre la lecture de l'hôte et sa publication :
   `SpecializedResourceConflictError` levée par `write_specialized_resource`,
   puis 409. Un test écrit dans le handler pour le provoquer.

Dans les deux cas, le contenu concurrent est préservé et il n'y a pas
d'événement d'historique.

## No-op

**Décision (§53–55)** : si `codec.encode(nouveau) == codec.encode(lu)`,
l'hôte n'écrit pas, n'ajoute aucun événement et garde la révision. Il répond
303 avec `?notice=unchanged` (« Aucune modification. »). L'égalité d'encodage
est fiable et générique : elle ne dépend pas d'un `__eq__` du module.

## Statuts HTTP

Matrice normative (`ACTION_STATUS` et garde Web) — **décision I** : le cœur
seul décide.

| Statut | Cas |
|---|---|
| 303 | `saved`, `unchanged` → page ressource avec `notice` |
| 400 | enveloppe, jeton mal formé, champ en double ou inconnu ou manquant, `_method` non surchargé, paramètres d'URL, `ModuleActionPayloadError`, type étranger à l'action, chemin refusé |
| 403 | origine absente ou étrangère, `Origin: null`, `Sec-Fetch-Site: cross-site` |
| 404 | action ou route inconnue, action non exposée, ressource introuvable, cœur sans module |
| 405 | GET (ou autre méthode) sur une route d'action ; `_method=DELETE` surchargé par Forge avant routage |
| 409 | aucun projet, racine invalide, jeton périmé, conflit d'écriture, ressource inutilisable |
| 413 | corps > 16 Kio |
| 415 | type de contenu autre que formulaire encodé |
| 422 | `ModuleActionRefused`, validation bloquante, ressource encodée trop grande |
| 500 | exception du module, résultat non `ModuleActionResult`, document lu muté, écriture incertaine, journal non écrit |

La surcharge `_method` de Forge (`POST` + `_method=DELETE` traité comme
`DELETE` avant routage) donne 405 sans jamais atteindre le handler. Une
valeur non surchargée (`_method=GET`) est refusée en 400.

## Origine locale

`module_action` appelle `is_local_action(request)` avant tout autre
traitement :

- Host exact `127.0.0.1:<port>` ;
- `Origin` identique ;
- `Sec-Fetch-Site` absent ou `same-origin`.

Les routes sont déclarées `csrf=False` **uniquement** sous cette garde, comme
les autres mutations locales sans session (inspecteur, éditeur de Design).
La garde DNS rebinding `_require_local_host` reste en amont.

## Sécurité Web

- Seul POST mute ; une route exacte par action.
- La réponse d'erreur est une page du cœur (`module_action.html`), avec un
  message et des diagnostics échappés par Jinja et un lien de rechargement
  calculé par le cœur.
- Aucune redirection choisie par le module : la cible 303 est toujours la
  page ressource du module courant. `notice` est en liste fermée (400 sinon).
- `no-store` sur les routes d'action.
- CSP inchangée.
- Aucune trace dans une réponse 500 (test de non-divulgation d'un chemin
  `/home/secret`).

## Sécurité filesystem

Le module n'a aucun accès au système de fichiers. Le chemin est confiné par
l'hôte : espace de sources, suffixe, politique lexicale, ouverture relative
sans lien. La lecture comme l'écriture passent par les primitives existantes
de FD-SPECIALIZED-002. Aucun dossier n'est créé et aucune nouvelle primitive
d'entrée/sortie n'est ajoutée.

## ModuleHost

Ajouts :

- `actions(module_id)` : actions exposées ;
- `action(module_id, action_id)` : `KeyError` si non exposée ;
- `execute_action(module_id, action_id, root, type_id, path, token, fields)` :
  rend un `ModuleActionOutcome(code, message, issues, truncated, revision)`
  avec un code fermé (`saved`, `unchanged`, `payload-invalid`,
  `type-mismatch`, `resource-not-found`, `resource-refused`,
  `resource-unusable`, `conflict`, `refused`, `invalid-resource`,
  `module-error`, `write-failed`) ;
- `ModuleResourceView.revision_token`.

L'hôte contrôle le module, le type, le chemin, la révision, le payload, la
lecture et l'écriture. Le handler ne contrôle que la transformation métier.

## Fake module

Les témoins sont limités aux tests (`tests/module_support.py`) :

- action `rename-title` (champ `title`, texte non vide d'au plus 200
  caractères), handler pur qui rend `replace(document, title=…)` ;
- option `edit_dependency` qui fait dépendre `edit` de la sonde ;
- `StrictCodec` (titre `INTERDIT` bloquant) pour le 422.

Le harnais navigateur, hors dépôt, utilise trois modules injectés :
`witness` (action), `lecture` (aucune action) et `gated` (`edit` dépendant
d'une sonde indisponible). Aucun témoin n'est livré dans la distribution.

Scénario nominal vérifié :

```text
titre « Avant », révision R1 ─▶ POST rename-title {title: « Après »} + R1
─▶ écriture ─▶ R2 ─▶ GET : « Après », « Modification enregistrée. »
```

## Isolation inter-modules

Chaque module a ses propres routes d'action. Une action de `witness` appelée
avec le chemin et le jeton d'une ressource de `other` est refusée en 400 :
le chemin est hors de l'espace de sources du type de `witness`, et rien n'est
écrit. L'action homonyme de `other` agit sur sa ressource et redirige sous
`/modules/other/`. Il n'y a ni résolution d'action par chemin, ni accès
croisé.

## ToolRegistry

Toujours cinq Tools (`test_graphics_and_tool_registry_know_no_module`). Les
modules et leurs actions ne sont pas des Tools.

## Graphic Core

**Décision N : aucune modification.** Aucun fichier de
`forge_design/web/static/` n'a changé (`git diff --stat` vide), et il n'y a ni
nouveau module JS ni asset. Les suites Node restent à 102/102.
`module-resource.js` est inchangé : le jeton n'est lu que par le futur éditeur
du module.

## Tests Python

| Fichier | Tests | Couverture |
|---|---|---|
| `tests/test_module_actions.py` (nouveau) | 78 | voir ci-dessous |
| `tests/test_web_module_actions.py` (nouveau) | 22 | voir « Tests HTTP » |
| `tests/test_modules_contract.py` | 46 (inchangé en nombre) | `hashlib`, `hmac`, `math` ajoutés à la liste blanche de la bibliothèque standard de `forge_design.modules` |
| `tests/module_support.py` | — | action témoin `rename-title`, option `edit_dependency` |

Couverture de `test_module_actions.py` :

- déclarations refusées (16 cas) et défauts ;
- descripteur : actions facultatives, API 1, 7 cas refusés ;
- payload : bornes, lecture seule, `text`, `integer`, `number`, `boolean`,
  `null` refusé ;
- jeton (opaque, exact sur chaque champ) ;
- cycle hôte : nominal avec historique, espion des arguments, no-op, conflit
  par jeton, conflit pendant l'écriture, payload invalide (5 cas), enveloppe,
  ressource inutilisable, refus métier, exception, mauvais retour, mutation de
  l'entrée, validation bloquante, échecs d'écriture (3 cas), capability gate,
  isolation.

## Tests HTTP

Serveur réel (`create_server`, port éphémère), requêtes `http.client`.
`test_web_module_actions.py` couvre :

- PRG nominal : 303, `Location`, GET avec la notice, nouveau jeton et
  historique ;
- no-op : notice `unchanged`, pas d'historique ;
- conflit : 409, contenu concurrent préservé ;
- payload invalide : 400 (7 cas, dont `_method=DELETE` en 405) ;
- enveloppe : 9 cas, plus les paramètres d'URL ;
- validation : 422 avec les diagnostics ;
- refus métier : 422 ;
- exception du module : 500 sans trace ;
- origines : 4 cas en 403 ;
- 413 et 415 ;
- routes : inconnues 404, GET 405, PUT, cœur sans module, module en lecture
  seule, capacité indisponible (404 et aucun jeton) ;
- 409 sans projet ;
- isolation inter-modules ;
- `notice` fermée.

## Chromium

Chrome 154.0.8037.92 headless (CDP). Deux serveurs de test lancés avec le
venv du cœur :

- 8766 : trois modules témoins injectés ;
- 8767 : aucun module.

Corpus temporaire `tmp/gxe-browser`. **10/10** :

- accueil avec trois modules ;
- ressource : jeton R1 de 64 caractères, scène « Avant », aucun formulaire
  livré ;
- **formulaire POST réel** (créé par le test, Origin posé par le navigateur)
  → 303 suivie → « Après », notice, R2 ≠ R1 ;
- `fetch` avec R1 périmé → 409, R2 préservée ;
- même intention → redirection, révision inchangée ;
- 400, 422 et GET 405 ;
- `lecture` et `gated` sans jeton, routes 404 ;
- isolation inter-modules 400 ;
- cœur sans module 404 ;
- aucune exception, boîte de dialogue ni violation CSP.

Sans JavaScript : page ressource identique (métadonnées, message
« La visualisation graphique nécessite JavaScript. », aucune scène).

## Firefox

Firefox 153.4.0 headless (WebDriver BiDi), même scénario : **10/10**, aucune
erreur ni violation CSP. Sans JavaScript (profil `javascript.enabled=false`) :
OK.

Un premier passage Firefox, lancé sur le corpus déjà modifié par le passage
Chromium, a échoué sur 5 points, comme attendu, puisque le titre était déjà
« Après ». Le corpus a été recréé et le scénario relancé : 10/10.

## Mutations

16/16 tuées (cible : actions, payload, contrat, ressource spécialisée et
frontières), avec un lancement hors du dépôt :

| Sabotage | Tué par |
|---|---|
| action reçoit Request (`request=` en plus) | 17 tests, dont nominal et espion |
| action reçoit root | 17 tests |
| action contourne ResourceHost (écriture directe) | 8 tests (historique absent) |
| révision ignorée | 3 tests, dont nominal (jeton consommé) |
| conflit écrasé (révision relue avant écriture) | `test_conflict_detected_by_the_resource_host_during_write` |
| payload non borné (champs exacts ignorés) | 3 tests |
| unknown action exécutée | 2 tests |
| capability gate ignoré | 10 tests |
| cross-module action (module choisi par chemin) | 2 tests |
| validation bloquante ignorée | 4 tests |
| exception module expose la trace | 2 tests |
| origine hostile acceptée | 4 tests |
| historique contourné | 5 tests |
| no-op écrit quand même | 2 tests |
| mutation du document lu tolérée | 1 test |
| taille du corps non bornée | 1 test |

Le test espion a été durci avant la campagne : il accepte `*args, **kwargs`
et exige exactement deux arguments positionnels, sans argument nommé.

Tests statiques (§183) : `test_core_distribution_ships_no_circuit` interdit
déjà « circuit » dans tout le code livré, actions comprises. De son côté,
`test_module_contract_depends_only_on_the_specialized_contract` limite les
imports de `forge_design.modules` : pas de Web, pas de `core.http`.

## Packaging

`forge_design/modules/actions.py` appartient au paquet existant
`forge_design.modules`. `templates/module_action.html` est ajouté au
package-data de `forge_design.web`. Il n'y a ni nouvel asset JS, ni nouvelle
dépendance.

## Wheel

Roue `forge_design-0.1.0.dev0-py3-none-any.whl` construite après suppression
du dossier `build/` : elle contient `modules/actions.py`, `module_action.html`
et `module_resource.html`, et aucun « circuit ». Installée dans un venv neuf
(`pip check` propre), avec le témoin injecté (`server_e1.py`, API publique
seulement) sur un port de test, elle passe **10/10** :

- installation depuis la roue ;
- cycle nominal R1 → 303 → « Après » et R2 ;
- conflit 409 ;
- origine 403 ;
- 422 ;
- lecture seule et capacité indisponible en 404, sans jeton ;
- une seule ligne d'historique ;
- cœur sans module 404 ;
- deux arrêts propres.

PEP 561 : un paquet externe fictif (hors des deux dépôts) déclare une action
`move-point` (`id`, `x`, `y`, `snap`, `step`) avec la seule API publique.
Pyright strict, depuis le venv de ForgeDesign-Circuit : 0 erreur.

## Limites V1

- Aucune UI d'action dans le produit : le futur éditeur du module enverra le
  formulaire avec le jeton publié.
- Une ressource par action ; pas de lot ni de transaction.
- Payload scalaire texte ; ni liste ni objet ; `null` non représentable.
- Pas d'undo/redo, de fragment ou de HTMX ; PRG seulement.
- `action_id` absent de l'historique.
- Le jeton dépend des métadonnées : un `touch` du fichier rend une page
  ouverte périmée (409), comme pour toute révision du ResourceHost.
- Capability gate calculé au démarrage, comme le reste de l'hôte.

## Circuit futur

Le premier geste réel (déplacer un composant) tient dans ce contrat :

```text
ModuleAction("move-component", "schematic", ("component", "x", "y"), move)
payload.text("component") · payload.integer("x", minimum=…, maximum=…)
─▶ ModuleActionRefused si le composant est inconnu
─▶ ModuleActionResult(document avec la nouvelle position)
```

Le module publiera l'action dans son descripteur et son JS enverra
`type`, `path`, `revision` et les champs. Les capacités génériques manquantes
du moteur (glisser, ports) seront construites contre ce besoin, dans les
tickets suivants.

## Roadmap

[03-roadmap.md](../03-roadmap.md) : FD-EDIT-001 **fait** ; **suivant** :
ForgeDesign-Circuit, premier geste d'édition réel (déplacer un composant).

### Décisions

| | Question | Réponse |
|---|---|---|
| A | Format payload V1 ? | **formulaire `application/x-www-form-urlencoded` borné**, conversions typées strictes par le cœur |
| B | Le module reçoit-il Request ? | **non** |
| C | Le module reçoit-il root/path filesystem ? | **non** : document et payload seulement |
| D | Le navigateur envoie-t-il le document complet ? | **non** : intention seulement |
| E | Révision obligatoire ? | **oui** : jeton absent ou mal formé → 400, périmé → 409 |
| F | Qui détecte le conflit ? | **ResourceHost** (jeton relu par l'hôte, puis `write_specialized_resource`) |
| G | Qui valide le nouveau document ? | **codec + `write_specialized_resource`** |
| H | Qui écrit ? | **core** |
| I | Qui décide le statut HTTP ? | **host core** (`ACTION_STATUS`) |
| J | Une action peut-elle écrire plusieurs ressources ? | **non** |
| K | Une action peut-elle lire une autre ressource ? | **non** |
| L | Une action peut-elle lancer un runtime externe ? | **non** |
| M | API module reste-t-elle v1 ? | **oui** : ajout additif, modules d'API 1 inchangés et valides |
| N | Le Graphic Core change-t-il ? | **non** |
| O | Le prochain ticket peut-il implémenter le premier geste Circuit réel ? | **oui** : contrat validé en Python, HTTP, wheel isolée, Chromium et Firefox |

## Fichiers créés

- `forge_design/modules/actions.py`
- `forge_design/web/templates/module_action.html`
- `tests/test_module_actions.py`
- `tests/test_web_module_actions.py`
- `docs/modules/module-actions.md`
- `docs/rapports/FD-EDIT-001.md`

## Fichiers modifiés

- `forge_design/modules/__init__.py` : API publique des actions.
- `forge_design/modules/descriptor.py` : `actions`, `_check_actions` et
  `action_url`.
- `forge_design/modules/host.py` : actions exposées, jeton,
  `execute_action` et `ModuleActionOutcome`.
- `forge_design/web/modules.py` : `module_action`, `parse_action_request`,
  `ACTION_STATUS` et `notice`.
- `forge_design/web/server.py` : routes POST exactes.
- `forge_design/web/templates/module_resource.html` : notice et
  `data-revision-token`.
- `pyproject.toml` : package-data `module_action.html`.
- `tests/module_support.py`, `tests/test_modules_contract.py`.
- `docs/modules/module-architecture.md`, `docs/modules/module-host.md`,
  `docs/02-architecture.md`, `docs/03-roadmap.md`.

## Validation globale finale

| Contrôle | Résultat |
|---|---|
| `python -m compileall -q forge_design` | Réussi |
| `ruff check forge_design tests` | Réussi |
| `ruff format --check .` | Réussi (Markdown compris) |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Réussi |
| `node --check` et suites Node `tests/js/graphics` | 102 réussis |
| Ciblés : actions, Web, contrat, hôte, ressources spécialisées, CLI, serveur | 326 réussis |
| Mutations | 16/16 tuées |
| Suite globale `pytest` (hors du dépôt, `--basetemp` court sous `tmp/`) | **4561 réussis** (4461 + 100), relancée après insertion de ces résultats. Un passage intermédiaire a donné 4560 réussis et 1 échec : `test_runtime_detects_dead_proxy`, le test Real Preview instable connu (course du harnais du proxy, sans lien avec les modules). Relancé isolément 5/5, puis suite complète 4561/4561 ; non corrigé ici (§191) |
| `python -m pip check` | Aucune dépendance cassée |
| Wheel isolée avec témoin injecté | 10/10 |
| Pyright strict d'un module externe fictif | 0 erreur |
| ForgeDesign-Circuit contre ce cœur (non modifié) | 324 réussis, Pyright 0 erreur |
| Chromium 154 / Firefox 153 | 10/10 chacun ; sans JavaScript OK dans les deux |
| MkDocs | N/A : aucune configuration MkDocs |

## État Git final

Commit unique `feat: ajouter les actions bornées des modules (FD-EDIT-001)`,
au-dessus de `c308c6c`. `docs/rapports/FD-CONTRACT-001.md` reste modifié
localement, hors commit. Aucun push. ForgeDesign-Circuit est inchangé
(`d8d1912`, distant vide).

Aucun service n'est laissé ouvert : les serveurs de test 8766, 8767 et 8768,
Chromium et les deux Firefox sont arrêtés. L'instance de l'utilisateur sur
8765 n'a été ni sondée ni touchée.
