# Actions bornées des modules spécialisés

Statut : **normatif et implémenté** (FD-EDIT-001). Code :
`forge_design/modules/actions.py`, `ModuleHost.execute_action`
(`forge_design/modules/host.py`), `module_action` (`forge_design/web/modules.py`).
Contrat général : [Architecture des modules](module-architecture.md) ; hôte :
[Hôte des modules](module-host.md).

## Objectif

Un module explicitement activé peut déclarer des **mutations métier bornées**
sur ses ressources. Il ne reçoit jamais Request, Response, Router, racine de
projet, chemin, descripteur de fichier ni hôte : seulement le document décodé
et un payload déjà borné. Lecture, révision, validation, écriture atomique,
historique et statut HTTP restent au cœur.

```text
navigateur ── POST /modules/<id>/actions/<action>  (type, path, revision, champs)
    ↓
cœur : origine locale · format · taille · enveloppe · champs exacts
    ↓
read_specialized_resource()        ← lecture et validation par l'hôte
    ↓
jeton de révision courant = jeton reçu ?   sinon 409
    ↓
action.handler(document, payload)  ← module : transformation pure
    ↓
encodage identique ?  → no-op (303, aucune écriture)
    ↓
write_specialized_resource(expected_revision=révision lue)
    ├── validation bloquante du codec (422)
    ├── conflit détecté par l'hôte (409)
    ├── publication atomique
    └── historique (write_specialized_resource)
    ↓
303 See Other → page ressource (?notice=saved)
```

## Contrat

```python
from forge_design.modules import (
    ModuleAction,
    ModuleActionPayload,
    ModuleActionResult,
    ModuleActionPayloadError,
    ModuleActionRefused,
)


def rename(document: Note, payload: ModuleActionPayload) -> ModuleActionResult:
    title = payload.text("title", max_chars=200, empty=False)
    return ModuleActionResult(replace(document, title=title))


ACTION = ModuleAction("rename-title", "document", ("title",), rename)
ModuleDescriptor(..., actions=(ACTION,))
```

| Champ de `ModuleAction` | Contrat |
|---|---|
| `id` | kebab-case, au plus 48 caractères, unique dans le module |
| `resource_type` | type déclaré par le module, `editable`, qui déclare `save` |
| `fields` | tuple exact des champs du payload (au plus 16), `[a-z][a-z0-9_-]*`, au plus 32 caractères, jamais `type`, `path`, `revision` ni `_method` |
| `handler` | `(document, payload) -> ModuleActionResult`, appelable |
| `capability` | capacité plateforme exigée, `edit` par défaut, déclarée par le type |

`ModuleDescriptor.actions` est facultatif (`()`), au plus 32 actions. Les
contrôles sont faits à la construction du descripteur : un module invalide
est refusé à l'activation (`descriptor-invalid`).

Le handler est **pur** : pas d'entrée/sortie, pas de journal, pas de HTTP,
pas d'autre ressource, pas de runtime externe. Il rend une **nouvelle**
ressource, sans modifier celle qu'il a reçue : l'hôte compare l'encodage du
document lu avant et après l'appel, et refuse (500) un module qui l'a muté.

Erreurs publiques d'un module :

| Exception | Sens | Statut |
|---|---|---|
| `ModuleActionPayloadError` | champ absent ou mal formé | 400 |
| `ModuleActionRefused` | intention refusée sur ce document (élément inconnu…) | 422 |
| toute autre exception | erreur de programmation du module | 500, sans trace |

Le message d'un module est affiché comme texte, sur une ligne, sans caractère
de contrôle, au plus 200 caractères. Un module ne choisit jamais un statut
HTTP, une réponse ni une redirection.

## Payload

**Décision : formulaire `application/x-www-form-urlencoded` borné.**

| Critère | Formulaire | JSON |
|---|---|---|
| Forge `Request` | `request.body` (`parse_qs`) : doublons visibles | `json_body` : JSON invalide → `{}` silencieux, doublons fusionnés, `NaN` accepté |
| Bornes | nombre, longueur des clés et valeurs, doublons | idem, mais un corps mal formé est indiscernable d'un objet vide |
| Types | texte, conversion stricte par le cœur | scalaires natifs |
| Éditeur JS futur | `new URLSearchParams(...)` + `fetch` | `JSON.stringify` |
| Sécurité | même garde d'origine que l'éditeur de Design | idem |

Le JSON de Forge n'est pas strict : l'adopter aurait demandé un parseur HTTP
parallèle, ce que le contrat exclut. Le premier besoin réel (déplacer un
composant : `id`, `x`, `y`) tient en scalaires.

Le corps contient l'enveloppe et les champs de l'action :

| Champ | Rôle |
|---|---|
| `type` | type de ressource ; doit être celui de l'action |
| `path` | chemin relatif de la ressource (au plus la longueur des sources) |
| `revision` | jeton de révision (64 hexadécimaux minuscules) |
| autres | exactement `fields`, ni plus ni moins |

Le module lit des valeurs typées par `ModuleActionPayload` (lecture seule) :

| Accesseur | Forme acceptée |
|---|---|
| `text(key, max_chars=None, empty=True)` | texte tel quel |
| `integer(key, minimum, maximum)` | `-?(0\|[1-9][0-9]*)`, entier sûr (±2⁵³−1) et bornes données |
| `number(key)` | décimal canonique, fini (`NaN`, infini, `.5`, `1.` refusés) |
| `boolean(key)` | `true` ou `false` |

`null` n'a pas de représentation : un champ est présent ou la requête est
refusée. Ni liste ni objet imbriqué en V1.

## Bornes

| Constante | Valeur |
|---|---|
| `MAX_MODULE_ACTION_BYTES` | 16 Kio de corps (`Content-Length`), sinon 413 ; Forge refuse déjà au-delà de 1 Mio |
| `MAX_MODULE_ACTION_FIELDS` | 16 champs de payload |
| `MAX_MODULE_ACTION_KEY_CHARS` | 32 caractères par nom de champ |
| `MAX_MODULE_ACTION_TEXT_CHARS` | 1024 caractères par valeur, sans caractère de contrôle (tabulation et fins de ligne admises) |
| `MAX_MODULE_ACTIONS` | 32 actions par module |
| `MAX_SAFE_INTEGER` | 2⁵³ − 1 |

Paramètres d'URL refusés : l'enveloppe vient du corps seulement. Un champ
fourni deux fois est refusé.

## Révision et jeton

Toute action porte la révision attendue. Le navigateur ne reçoit qu'un
**jeton opaque** : SHA-256 de `[module, type, chemin, taille, mtime, sha256 du
contenu, périphérique, inode, ctime]`. Le serveur recalcule le jeton de la
révision qu'il vient de lire et compare à temps constant. Le navigateur ne voit
ni périphérique ni inode et ne reconstruit jamais une
`SpecializedResourceRevision`.

| Option | Retenue |
|---|---|
| SHA-256 du contenu seul | non : ignore la révision de l'hôte (métadonnées, identité du fichier) |
| HMAC à secret de processus | non : rien à authentifier (la garde d'origine protège), et un redémarrage invaliderait les pages ouvertes |
| Condensat opaque de la révision complète | **oui** : minimal, déterministe, sans fuite |

Le jeton est publié sur la page ressource
(`<dd data-revision-token="…">`), seulement si le type a au moins une action
exposée. Les modules en lecture seule ont donc des pages inchangées.

## Cycle lecture → transformation → écriture

1. Le cœur lit la ressource (`read_specialized_resource`). Une ressource
   introuvable donne 404 et un chemin refusé 400. Une ressource illisible,
   invalide (bloquante) ou d'une autre version donne 409 : aucune action.
2. Il compare le jeton : différent → 409, sans retry automatique.
3. Il appelle le handler du module, isolé.
4. **No-op** : si `codec.encode(nouveau) == codec.encode(lu)`, aucune écriture,
   aucun événement d'historique, révision inchangée → 303 `?notice=unchanged`.
5. Sinon `write_specialized_resource(..., expected_revision=révision lue)` :
   validation bloquante selon `blocking_validation_levels` (422, aucune
   écriture), conflit si le fichier a changé entre-temps (409), publication
   atomique, événement `write_specialized_resource` dans `history.jsonl`. Le
   format de l'historique est inchangé : le chemin suffit en V1, sans
   `action_id`.
6. 303 vers `/modules/<id>/resource?type=…&path=…&notice=saved`. La page
   affiche « Modification enregistrée. » ou « Aucune modification. » ; tout
   autre `notice` répond 400.

Une action ne lit ni n'écrit d'autre ressource et ne lance aucun runtime.

## Statuts HTTP

Décidés par le cœur seul (`ACTION_STATUS`, `web/modules.py`).

| Statut | Cas |
|---|---|
| 303 | succès (`saved`) ou aucune modification (`unchanged`) |
| 400 | enveloppe ou payload invalide, champ en double ou inconnu, `ModuleActionPayloadError`, type étranger à l'action, chemin refusé (traversée, hors espace), paramètres d'URL |
| 403 | origine absente, étrangère ou `Sec-Fetch-Site` non `same-origin` |
| 404 | module, action ou route inconnue ; action non exposée (capacité indisponible, module en lecture seule) ; ressource introuvable |
| 405 | autre méthode que POST sur une route d'action (Router Forge), dont la surcharge `_method=DELETE/PUT/PATCH` |
| 409 | aucun projet ouvert ou racine invalide ; jeton périmé ; conflit d'écriture ; ressource inutilisable |
| 413 | corps au-delà de `MAX_MODULE_ACTION_BYTES` |
| 415 | autre type de contenu que le formulaire encodé |
| 422 | `ModuleActionRefused` ; validation bloquante ou taille encodée refusée par l'hôte |
| 500 | exception du module (handler, codec), résultat qui n'est pas un `ModuleActionResult`, document lu muté, écriture incertaine ou journal non écrit |

Un 500 n'expose aucune trace : message borné (`Action du module en échec
(RuntimeError).`), trace sur le logger `forge_design.modules` seulement.

## Activation et capability gate

Une action n'est routée que si elle est déclarée **et** si sa capacité ainsi
que `save` sont **disponibles** après la sonde de dépendances, pour un module
actif, compatible, exposé et muni d'une `UiEntry`. Sinon la route
n'existe pas (404), décision prise une fois au démarrage, comme le reste de
l'hôte. Il n'y a pas de route d'action sans module, ni pour un module sans
action.

## Sécurité

- Garde d'origine `is_local_action` du cœur (Host `127.0.0.1:<port>`, Origin
  exact, `Sec-Fetch-Site` absent ou `same-origin`) ; routes `csrf=False`
  seulement sous cette garde, comme les autres mutations locales.
- La garde DNS rebinding (`_require_local_host`) reste en amont de tout.
- Aucun GET ne modifie : chaque action est un POST exact, sans motif
  dynamique.
- Le chemin est confiné par l'hôte (espace de sources du type, suffixe,
  politique lexicale, aucun lien) : une action d'un module ne peut pas viser
  une ressource d'un autre module (400).
- Le module ne touche jamais le système de fichiers ; l'écriture passe
  toujours par `write_specialized_resource`.

## Compatibilité de l'API

`MODULE_API_VERSION` reste **1** : `actions` est un champ additif à défaut
`()`, et tout descripteur d'API 1 existant reste valide sans modification. Un
module qui déclare des actions et serait chargé par un cœur antérieur échoue
à la construction de son descripteur (argument inconnu). L'hôte le signale
(`module-import-failed`) au lieu de l'ignorer en silence, et la contrainte
`forge-design>=…` du module le prévient à l'installation.

## Limites V1

- Pas d'UI d'action générique : le cœur n'affiche aucun formulaire métier.
  Le futur éditeur JS du module enverra le formulaire encodé avec le jeton
  publié.
- Une action vise une seule ressource ; pas de lot, pas de transaction
  multi-ressources.
- Payload scalaire texte ; pas de liste ni d'objet.
- Pas d'undo/redo : l'historique persistant du cœur n'est pas une pile
  d'annulation interactive.
- Pas de réponse fragment ni de HTMX : POST/Redirect/GET.
- `action_id` absent de l'historique.
