# Rapport — FD-REALPREVIEW-008

Accès à Real Preview depuis Route Explorer, sans Design ni contrat de vue.
Date : 2026-10-18.

## Objectif

Lever le blocage de FD-SEQUENCIEL-005 sans modifier SéquenCiel. Il s'agit
d'ajouter un second point d'entrée utilisateur vers **le même** Real Preview,
depuis une route éligible de Route Explorer, sur un projet qui n'a aucun
`.design.json` ni `.view.json`.

L'objectif est de découpler l'accès à Real Preview de l'existence d'un Design,
sans le découpler de ses règles strictes de sélection et de sécurité.

**Verdict : REALPREVIEW_ROUTE_ENTRY_PASS.**

## Baseline

| Élément | Valeur |
|---|---|
| Dépôt | ForgeDesign, `main` à `385587b` (FD-SEQUENCIEL-005), 4 commits d'avance sur `origin/main` (`bb16f90`) |
| Version | 0.2.1 (inchangée dans ce ticket) |
| Forge | forge-mvc 1.0.0rc9 |
| Suites avant modification | Real Preview et Route Explorer : 322 réussis |

## État Git initial

`main` à `385587b`, propre en dehors de `docs/rapports/FD-CONTRACT-001.md`
(modification utilisateur, préservée) et des 9 entrées non suivies historiques
(rapports et dossiers de vérification). Aucun autre changement.

## Analyse du parcours actuel

Parcours historique, lu dans `web/real_preview.py` :

1. `/editor?design=…` affiche le panneau Real Preview ;
2. `POST /editor/real-preview/start` exige le champ `design`, puis un Design
   lisible (sinon 409) ;
3. `load_contract` charge le contrat de vue (sinon 409 « Contrat
   indisponible ») ;
4. `route_selection` lance Route Explorer, puis
   `select_real_preview_route(contrat.template, routes)` ;
5. `runtime.start(context.root)`.

Le runtime (`RealPreviewRuntime`, `RealPreviewController`, `child_bootstrap.py`,
proxy, origine dédiée, garde `Host`) ne dépend que de la racine du projet. Le
Design et le contrat ne servent qu'à **choisir la route**.

`select_real_preview_route` répond à la question « pour ce template, quelle
route unique le rend ? ». Elle contient :

- **des garanties sur la route retenue** : GET, chemin statique, handler
  vérifié, template exact et présent, route publique ;
- **deux clauses de désambiguïsation template → route** : refus si **n'importe
  quelle autre** route GET du projet a un template indéterminable (l. 82 et 91),
  ou si plusieurs routes rendent ce template.

## Blocage issu de FD-SEQUENCIEL-005

Sur SéquenCiel (0 Design, 0 contrat), le parcours historique est inaccessible :
voir [FD-SEQUENCIEL-005](FD-SEQUENCIEL-005.md).

Les deux clauses de désambiguïsation l'auraient de plus bloqué même avec un
Design. Avec 34 templates dynamiques et 2 ambigus (FD-SEQUENCIEL-001), `uncertain`
est vrai sur tout le projet, donc `GET /` vers `home/index.html` serait refusée.

## Architecture retenue

Décision prise avec le porteur avant tout code : **garanties de route**. Toutes
les garanties portant sur la route désignée sont conservées, et l'unicité de son
identité `GET <chemin>` s'y ajoute. Les deux clauses template → route ne
s'appliquent pas : l'utilisateur désigne la route, son URL est fixée, et aucune
route n'est choisie à la place d'une autre.

```text
Route Explorer (/routes)
  └ chaîne GET /x éligible → [Prévisualiser réellement]
       POST /routes/real-preview/start  (champ unique : route)
         → inventaire relu → égalité exacte → éligibilité recalculée
         → RealPreviewRuntime.start(root)   ← même runtime que l'éditeur
       303 → GET /routes/real-preview?route=/x  (état, iframe, Stop ; ne démarre rien)
       POST /routes/real-preview/stop → RealPreviewRuntime.stop()
```

Ni nouveau runner, ni nouveau bootstrap, ni nouveau serveur WSGI, ni nouveau
proxy, ni gestionnaire de processus parallèle. Fonctions ajoutées :

| Couche | Ajout |
|---|---|
| `real_preview/route_selection.py` | `route_preview_refusal(route)` (garanties d'une route), `route_preview_selection(route, routes)` (désignation depuis l'inventaire, unicité d'identité), `select_route_for_preview(path, routes)` (chemin reçu → route inventoriée par égalité exacte), `method_refusal` et 9 raisons |
| `web/real_preview.py` | `route_entry_selection` (inventaire relu à chaque appel), `valid_route_field`, `route_preview_url`, `RealPreviewPanel.view_route`, `show_route_real_preview` (GET), `route_real_preview_action` (POST Start et Stop), `render_route_preview` |
| `web/routes.py` + `routes.html` | Éligibilité calculée par chaîne sur l'inventaire complet ; bouton et avertissement, ou raison |
| `web/server.py` | `GET /routes/real-preview`, `POST /routes/real-preview/start` et `/stop` |
| `web/templates/route_real_preview.html` | Page d'état de la preview d'une route |

`select_real_preview_route` (parcours éditeur) n'est **pas modifiée**. La
construction de l'état du panneau est factorisée (`RealPreviewPanel._web_state`)
et partagée par `view` (éditeur) et `view_route` (Route Explorer), sans
changement de comportement : les 116 tests préexistants passent tels quels.

Aucune fonction `start_real_preview_for_route` n'est extraite. Les deux
parcours appellent directement `runtime.start(context.root)` après validation
côté serveur, qui est déjà l'entrée générique : une couche de plus n'aurait
rien ajouté.

## Réutilisation du runtime

- Le même `RealPreviewRuntime` est créé par `create_application`, avec une seule
  instance de `RealPreviewPanel(runtime, registry)` pour les deux entrées.
- Start depuis Route Explorer sur un projet déjà actif ne redémarre rien
  (`test_route_start_twice_same_project`).
- `test_editor_and_route_entry_share_one_runtime` : Start par Route Explorer,
  iframe et Stop visibles dans l'éditeur, Start éditeur sans second runner, Stop
  éditeur, plus d'iframe côté Route Explorer.
- `real_preview/controller.py`, `child_bootstrap.py`, `proxy.py` et `models.py`
  sont **inchangés**.

## Réutilisation de la sélection de route

`route_preview_refusal` applique **les garanties que `select_real_preview_route`
exige de la route qu'elle retient**, avec les mêmes primitives
(`is_static_route_path`, statuts de Route Explorer). Seule la présence « non
vérifiée » reçoit une raison propre au lieu de « absent ».

Un **test de propriété** (`test_editor_selection_implies_route_eligibility`)
parcourt toutes les paires d'un jeu de 49 routes variées. Toute route retenue
par l'éditeur y est éligible depuis Route Explorer, **avec une exception
démontrée** :

- deux déclarations `GET <chemin>` **différentes** du même chemin, par exemple
  l'une qui rend `list.html` et l'autre `show.html` ;
- l'éditeur retient la route pour `list.html` sans voir l'autre déclaration,
  alors que Forge sert la première déclarée ;
- Route Explorer la refuse (« identité ambiguë »).

Le parcours B est donc **plus strict** sur ce point. Le parcours éditeur reste
inchangé, comme l'exige le ticket, et le cas est consigné
(`test_editor_does_not_detect_conflicting_declarations`, Limites).

## Éligibilité Route Explorer

Une route n'est prévisualisable que si :

1. méthode `GET` ;
2. chemin statique (`is_static_route_path`) ;
3. handler présent, non dynamique, méthode de contrôleur vérifiée (`found`) ;
4. template exact (`found`, chemin connu) ;
5. template présent sur disque (`present`) ;
6. route publique ;
7. identité `GET <chemin>` unique : des déclarations identiques (visibilité,
   handler, template) comptent pour une, des déclarations différentes sont
   ambiguës.

Aucune exception de projet ni de route : ni « SéquenCiel », ni « / ». La
capacité est générique.

## Revalidation serveur

À chaque `POST /routes/real-preview/start` :

1. contrôle de forme (origine, type, champ unique `route`, chemin statique,
   longueur bornée) → 400 ou 403 ou 415 ;
2. **relecture** de l'inventaire par Route Explorer (`registry.get("route-explorer").run`) ;
3. recherche de la route GET par **égalité exacte** du chemin, sans
   normalisation ni complétion → 404 si absente ;
4. **recalcul** de l'éligibilité → 409 si elle n'est plus remplie ;
5. seulement alors, `runtime.start`.

L'état HTML précédent n'est jamais cru. La page `GET /routes/real-preview`
revalide aussi la route avant d'encadrer quoi que ce soit.

Pas de TOCTOU naïf (`test_route_start_revalidates_after_display`) : route
affichée éligible, puis rendue protégée, privée de son template, renommée ou
rendue dynamique avant le POST → 409 ou 404, **aucun runner**. Une route
modifiée n'est jamais remplacée par une autre.

## Sécurité POST

| Protection | Parcours B |
|---|---|
| Méthode | POST seulement pour Start et Stop ; le GET de la page d'état ne démarre jamais rien |
| Origine | `check_editor_post` → `is_local_action` : `Origin` exact `http://127.0.0.1:<port>`, `Sec-Fetch-Site` same-origin ou absent (sinon 403) |
| Format | `application/x-www-form-urlencoded` seul (sinon 415) |
| Champs | Exactement `{"route"}`, chaque champ une seule fois, longueur bornée (sinon 400) |
| CSRF | Même convention que toutes les actions locales : `csrf=False` et contrôle d'origine exacte |
| `no-store` | Sur les trois routes |
| Garde `Host` | Middleware global inchangé |

Tests forgés : origine absente ou étrangère, port faux, `cross-site`,
`text/plain`, `multipart` → 403 ou 415 ; champs `design`, `port`, `url`,
`template`, `method`, `path` et `route` en double → 400.

## UI Route Explorer

Une seule stratégie : **pas d'action pour une route non éligible, raison
lisible à la place**.

- Chaque chaîne porte `data-real-preview="available|unavailable"`.
- Une route éligible a la mention « prévisualisable » dans son résumé, puis,
  dans son détail, l'avertissement « La preview réelle exécute le projet Forge
  sélectionné et peut déclencher ses effets de bord habituels. » et le bouton
  **Prévisualiser réellement**.
- Une route non éligible affiche « Preview réelle indisponible : <raison> »,
  sans formulaire.
- Si le runtime est indisponible (fermé), aucune action n'est proposée :
  « Preview réelle indisponible sur ce serveur. »
- L'éligibilité est calculée sur l'inventaire **complet**, pas sur la vue
  filtrée : l'unicité de l'identité ne dépend pas des filtres.

Aucune intégration dans Template Viewer, Project Inspector ni Debug Center.

## Routes éligibles

- Fixture Web : `GET /contacts` → `ContactsController.index` →
  `contacts/list.html`, publique, sans Design ni contrat.
- Fixture réelle (squelette forge-mvc rc9) : `GET /` → `home/index.html`.
- Acceptance : `A-route-preview`, copie de A sans `list.design.json` ni
  `list.view.json`, route `GET /contacts`.

## Routes refusées

| Cas | Raison (UI et 409) |
|---|---|
| POST | « Méthode POST : seule une route GET est prévisualisable. » (POST forgé : 404 « Route GET absente », car aucune GET n'a ce chemin) |
| GET dynamique `/contacts/{id}` | « Route dynamique : aucune valeur fictive n'est utilisée. » |
| Template dynamique | « Template dynamique : le rendu n'est pas déterminable statiquement. » |
| Template ambigu | « Plusieurs templates possibles : rendu ambigu. » |
| Aucun rendu | « Aucun template rendu détecté pour cette route. » |
| Handler fonction, non résolu ou dynamique | « Handler non analysé […] » |
| Méthode non vérifiée | « Méthode du contrôleur non vérifiée […] » |
| Présence non vérifiée (chaîne partielle, borne de templates) | « Présence du template non vérifiée (analyse partielle). » |
| Template absent | « Le template rendu par la route est absent du projet. » |
| Route privée | « Route protégée par authentification. » |
| Déclarations conflictuelles du même chemin | « Route GET déclarée plusieurs fois : identité ambiguë. » |
| Chemin inconnu ou approchant (`/inconnue`, `/etc/passwd`, `/../etc/passwd`, `/contacts/`, `/Contacts`) | 404 « Route GET absente de l'inventaire du projet. » |
| Chemin mal formé (vide, relatif, `//hôte`, requête, fragment, `{…}`, espace, non ASCII, `\`, chemin de template, URL absolue, plus de 4 096 caractères) | 400 « Chemin de route refusé. » |

## Parcours sans Design

Cas central (§35, §43) :

- **Web (double)** : `test_routes_offers_preview_without_design` vérifie
  0 `.design.json` et 0 `.view.json`, puis action disponible, Start, iframe et
  Stop.
- **Réel** : `test_real_route_entry_without_design`, sur le squelette rc9 réel
  avec 0 Design et 0 contrat :
  - `/routes` propose `GET /` ;
  - POST, puis page d'état avec iframe `http://127.0.0.1:<proxy>/` ;
  - la CSP `frame-src` vise ce proxy ;
  - le proxy rend la page HTML (200) ;
  - Stop : proxy fermé, aucun processus ;
  - **instantané du projet identique** (aucun bytecode ni écriture).
- **Acceptance** : Chromium, Firefox et sans JavaScript sur `A-route-preview`
  (voir plus bas).

## Parcours historique avec Design

Inchangé et revérifié :

- les 80 tests Web préexistants (Start, iframe, CSP, 409, Stop, changement de
  projet, arrêt par signal, intégration réelle) et les 36 tests de sélection
  préexistants passent **sans modification** ;
- le Start de l'éditeur refuse toujours tout champ `route`
  (`test_start_refuses_unexpected_or_duplicate_fields`) ;
- acceptance : l'étape « preview réelle A-preview » reste OK dans Chromium et
  Firefox ;
- aucun format modifié : ni `DesignFile`, ni `ViewContract`, ni
  `source_contract`, ni les schémas.

## Start / Stop

| Action | Résultat |
|---|---|
| Start valide | 303 vers `/routes/real-preview?route=<chemin>` ; état `running` ; iframe |
| Start, runner en échec | 303, état `failed`, logs visibles, « Démarrer à nouveau » |
| Start, runtime fermé | 409 « indisponible sur ce serveur » |
| Start sans projet | 409 |
| Stop | 303 ; proxy fermé, puis runner (ordre du runtime) ; idempotent ; indépendant de l'éligibilité de la route |
| Stop impossible | 500 « Preview réelle impossible à arrêter. » |

Le Stop de l'éditeur reste distinct : il exige un Design pour sa redirection.
Les deux appellent `RealPreviewRuntime.stop()` et arrêtent la même preview.

## Processus

Intégration réelle (`test_real_route_entry_without_design`, `no_survivors`) :

- **argv** : `<projet>/.venv/bin/python -I -B -u …/forge_design/real_preview/child_bootstrap.py --port <p>`, identique au parcours éditeur ;
- **session** : `getsid(pid) == getpgid(pid) == pid` (nouvelle session) ;
- **cwd** : la racine du projet ;
- **après Stop** : aucun processus mentionnant le projet, aucun thread de proxy ;
- **ACC-003** : l'instantané complet du projet avant et après est identique,
  `__pycache__` et `.pyc` compris.

Acceptance : `strays: []` après chaque navigateur, après le parcours sans
JavaScript et après l'arrêt par Ctrl+C.

## Loopback / Host / Origin

Aucune modification de `127.0.0.1`, de la garde `Host` ni de l'origine dédiée.

- `hostguard.json` : Host valide 200 ; `localhost`, Host étranger et rebinding →
  400 ; POST d'origine étrangère, sans origine ou `cross-site` → 403.
- `listen.json` : `127.0.0.1:8765` seul, aucune écoute hors loopback ; pendant
  la preview à l'arrêt, uniquement des ports loopback.
- La CSP de la page d'état n'est élargie (`frame-src 'self' <proxy>`) que si un
  proxy est actif. `/routes` et les autres pages gardent la CSP Forge, et
  `X-Frame-Options: DENY` reste en place.

## Chromium

Acceptance complète **32/32**. Nouvelle étape « preview réelle A-route-preview :
Route Explorer sans Design, démarrage, iframe, arrêt » : OK en 1 037 ms.

- La chaîne `GET /contacts` est `available`, l'avertissement est affiché, et le
  bouton est cliqué à la souris.
- La page `/routes/real-preview?route=%2Fcontacts` est `running`, avec une
  iframe vers `http://127.0.0.1:59569/contacts`, un port différent de celui de
  Forge Design ; le `GET` de cette URL donne 200, en HTML de 1 531 octets.
- Stop → `stopped`, plus d'iframe, et le proxy refuse la connexion.
- Chaque page passe le contrôle a11y, CSP et secrets du kit.

## Firefox

Acceptance complète **32/32**. Même étape : OK en 1 012 ms, avec l'iframe
`http://127.0.0.1:53071/contacts` (200, 1 531 octets), Stop et proxy fermé.

## Sans JavaScript

Firefox avec `javascript.enabled=false` : **12/12**. Nouvelle étape « preview
réelle depuis Route Explorer sans Design, POST natif, arrêt » : OK.

- La chaîne `GET /contacts` est `available`.
- Un vrai clic sur le `summary` ouvre `<details>` (natif), puis un vrai clic
  sur « Prévisualiser réellement » envoie un POST natif.
- Résultat : état `running` et iframe vers `/contacts`, sans fuite.
- Le Stop natif donne l'état `stopped`, sans iframe.

Le helper `click` du kit accepte désormais un localisateur XPath et un clic
sans attente de chargement, pour ouvrir `<details>`. Les appels existants sont
inchangés.

## Acceptance

`scripts/acceptance/run.sh` **sans filtre**, dossier neuf
(`tmp/fd-realpreview-008-acc`, ignoré par Git), code de sortie 0.

| Étape | Résultat |
|---|---|
| Roues | 3 roues, inspection de la roue : 169 fichiers (17 gabarits HTML), 0 manquant, 0 interdit |
| Installation hors ligne | `pip check` OK |
| Démarrage, sécurité locale | Écoute loopback seule, garde Host et Origin conformes |
| Chromium / Firefox | 32/32 et 32/32 ; **12 instantanés de projets conformes** chacun, dont `A-route-preview` (0 écriture tolérée) ; `strays: []` |
| Sans JavaScript | 12/12 ; `strays: []` |
| Mesures | Sans écart |
| Arrêt par Ctrl+C avec preview réelle active | `A-preview` conforme, `strays: []` |

Le **premier passage** a échoué dès l'étape Roues, et c'était un vrai défaut :
le nouveau gabarit `route_real_preview.html` **manquait dans la roue**, car la
liste `package-data` de `pyproject.toml` est explicite. Corrections :

- entrée ajoutée ;
- nouveau test `test_web_package_data_lists_every_template_and_asset`, qui
  compare la liste déclarée aux gabarits et assets présents. Une mutation qui
  retire l'entrée le fait bien échouer.

Le second passage, complet, est entièrement vert.

## Tests Python

| Fichier | Nouveaux cas | Total | Contenu |
|---|---:|---:|---|
| `tests/test_real_preview_route_selection.py` | 47 | 83 | Éligible ; 17 refus par cause ; chemins non statiques ; déclarations identiques ou conflictuelles ; autres routes incertaines non bloquantes ; POST du même chemin ; 10 chemins inconnus ou approchants ; propriété éditeur ⇒ Route Explorer ; constat de l'éditeur |
| `tests/test_web_real_preview.py` | 61 | 141 | Offre sans Design ; raisons sans action ; runtime fermé ; Start, iframe, CSP et `no-store` ; Start répété ; origine et format (6×2) ; champs (9) ; chemins mal formés (13) ; routes inconnues (5) ; POST forgés non éligibles (3) ; revalidation TOCTOU (4) ; sans projet ; Stop (ordre, idempotence, indépendance, échec) ; échec du runner ; page GET (7) ; route inconnue ; runtime partagé avec l'éditeur ; **intégration réelle sans Design** |
| `tests/test_packaging.py` | 1 | 4 | Gabarits et assets Web tous déclarés dans `package-data` |

Suite globale : **5305 réussis**, 0 échec (exécution finale, après toutes les
modifications).

## Tests Node

`node --test tests/js/graphics/*.test.mjs` : **134/134**. Aucun fichier
JavaScript du cœur n'est modifié.

## Documentation

- `docs/preview/real-preview-contract.md` :
  - nouvelle section « Deux parcours d'accès » : **parcours A** Design → contrat
    → route → preview, **parcours B** Route Explorer → route éligible →
    preview ;
  - le Design n'était qu'un moyen de choisir la route ;
  - protections, revalidation, page d'état et Stop partagé ;
  - section « Route désignée » : garanties, tableau des raisons, clauses non
    appliquées et pourquoi, constat de l'éditeur ;
  - la phrase « le chemin de route n'est jamais reçu du navigateur » est
    précisée pour le parcours B.
- `docs/tools/route-explorer.md` : introduction (seule exception à la lecture
  seule) et section « Preview réelle depuis une route ».
- `scripts/acceptance/README.md` et `build_projects.py` : fixture
  `A-route-preview`.

## Compatibilité

- **Modules** : `MODULE_API_VERSION`, `ModuleDescriptor` et `ResourceBinding`
  sont inchangés. Circuit et Flowchart ne sont pas nécessaires à la capacité ;
  ils sont toujours actifs et acceptés dans l'acceptance (roues 0.1.0,
  `pip check` OK).
- **Formats** : Design, ViewContract et schémas inchangés.
- **Parcours éditeur** : comportement inchangé.
- **API Python** : ajouts seulement (`route_selection`, `web/real_preview`).

## Versionnement

Capacité publique additive (nouvelle entrée utilisateur et nouvelles routes
HTTP). Selon la politique de version, la prochaine version est une **MINEURE :
0.3.0**. Elle n'est **pas publiée ici** : `forge_design.__version__` reste
0.2.1, et la montée de version et la qualification de release reviennent à
FD-RELEASE-004.

## Limites

- **Constat sur le parcours éditeur** (non corrigé, hors périmètre, §23) :
  `select_real_preview_route` ne détecte pas deux déclarations `GET <chemin>`
  **différentes** du même chemin. Elle peut retenir la route pour un template
  alors que Forge sert la première déclaration, qui en rend un autre. Le
  parcours B refuse ce cas. Un ticket de correction est recommandé.
- Les chaînes partielles faute de présence vérifiée (borne globale de 128
  templates, FD-SEQUENCIEL-001) ne sont pas éligibles : sur un grand projet,
  des routes saines peuvent être refusées tant que FD-ROUTES-023 n'est pas
  traité. `GET /` de SéquenCiel était une chaîne complète en FD-SEQUENCIEL-001.
- Le bouton est dans le détail repliable de chaque chaîne : sur un très grand
  projet, la mention « prévisualisable » du résumé est le seul repère visible
  sans ouvrir la chaîne.
- Une route GET publique exécute le code de son handler à chaque affichage de
  l'iframe. L'avertissement l'annonce : ce n'est pas un bac à sable.

## Verdict

**REALPREVIEW_ROUTE_ENTRY_PASS**

| Condition (§66) | Constat |
|---|---|
| Real Preview démarre depuis Route Explorer sans Design | Oui : doubles, intégration réelle, Chromium, Firefox, sans JavaScript |
| Seules les routes éligibles sont proposées | Oui : `data-real-preview`, aucune action sinon |
| Le serveur revalide la route au POST | Oui : inventaire relu, égalité exacte, éligibilité recalculée ; TOCTOU testé |
| Le runtime existant est réutilisé | Oui : même `RealPreviewRuntime` ; runner et proxy inchangés |
| Aucune régression du parcours éditeur | Oui : 116 tests préexistants inchangés, acceptance A-preview OK |
| Sécurité locale inchangée | Oui : Origin, Host, loopback, CSP, `no-store` |
| Acceptance verte | Oui : complète, sans filtre |

Aucune condition de BLOCKED (§67) : la sélection n'est pas affaiblie, puisque
les garanties de route sont toutes conservées, l'unicité d'identité ajoutée et
la décision prise avec le porteur ; il n'y a pas de second runner, aucune
confiance dans le navigateur, et ni le parcours Design ni la sécurité ne
régressent.

## Recommandation ticket suivant

1. **FD-RELEASE-004** : Forge Design **0.3.0**, montée de version et
   qualification complète et reproductible de la nouvelle capacité (deux
   passes, roue et sdist identiques à Git, installations hors ligne, modules
   Circuit et Flowchart).
2. Puis **reprise de FD-SEQUENCIEL-005** sur la roue 0.3.0 : Real Preview
   réelle sur SéquenCiel depuis Route Explorer, `GET /` vers `home/index.html`,
   avec la méthode des tickets précédents (lecture de `app.py` et `wsgi.py`,
   base arrêtée, `strace`, instantanés pendant la preview).

Hors chemin critique : un ticket de correction du constat de l'éditeur
(déclarations conflictuelles), et FD-ROUTES-023.

## Fichiers créés

- `forge_design/web/templates/route_real_preview.html`
- `docs/rapports/FD-REALPREVIEW-008.md`

## Fichiers modifiés

| Fichier | Changement |
|---|---|
| `forge_design/real_preview/route_selection.py` | Garanties de route, désignation, recherche exacte, raisons |
| `forge_design/web/real_preview.py` | Entrée Route Explorer, page d'état, actions, factorisation du panneau |
| `forge_design/web/routes.py` | Éligibilité par chaîne sur l'inventaire complet |
| `forge_design/web/server.py` | Trois routes |
| `forge_design/web/templates/routes.html` | Action ou raison par chaîne, mention dans le résumé |
| `pyproject.toml` | `templates/route_real_preview.html` dans `package-data` |
| `tests/test_real_preview_route_selection.py` | 47 cas |
| `tests/test_web_real_preview.py` | 61 cas |
| `tests/test_packaging.py` | 1 cas |
| `scripts/acceptance/build_projects.py`, `README.md` | Fixture `A-route-preview` |
| `scripts/acceptance/scenario.mjs` | Étape 9 bis |
| `scripts/acceptance/nojs.mjs` | Étape sans JavaScript ; options de `click` |
| `docs/preview/real-preview-contract.md`, `docs/tools/route-explorer.md` | Deux parcours, route désignée |
| `docs/03-roadmap.md` | FD-REALPREVIEW-008 et la suite |

Non modifiés : `real_preview/controller.py`, `child_bootstrap.py`, `proxy.py`,
`models.py`, `graphics/*`, `modules/*`, schémas Design et ViewContract, Circuit,
Flowchart, SéquenCiel, `docs/rapports/FD-CONTRACT-001.md`.

## Validation finale

| Commande | Résultat |
|---|---|
| `python -m compileall -q forge_design tests` | OK |
| `ruff check .` | All checks passed |
| `ruff format --check .` | Tous les fichiers formatés (Markdown compris) |
| `pyright` | 0 erreur, 0 avertissement |
| `pytest` (suite globale, cwd hors dépôt, basetemp court) | **5305 réussis** |
| `node --test tests/js/graphics/*.test.mjs` | 134/134 |
| `git diff --check` | OK |
| `scripts/acceptance/run.sh` sans filtre | Code 0 ; Chromium 32/32, Firefox 32/32, sans JS 12/12, instantanés conformes, `strays` vides |

## État Git final

Un commit sur `main` :
`feat: ouvrir Real Preview depuis Route Explorer (FD-REALPREVIEW-008)`. Il n'est
pas poussé : 5 commits d'avance sur `origin/main`.
`docs/rapports/FD-CONTRACT-001.md` et les entrées non suivies historiques sont
inchangés et hors du commit, ajouté par sélection explicite.
