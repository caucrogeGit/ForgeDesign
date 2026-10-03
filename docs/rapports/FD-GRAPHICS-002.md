# Rapport — FD-GRAPHICS-002

API réelle : [Moteur graphique — API JavaScript](../graphics/graphics-engine.md) ;
contrat : [Graphic Core](../graphics/graphics-core-contract.md#implémentation-minimale--fd-graphics-002).

## Ticket et objectif

Implémenter le premier noyau graphique 2D exécutable (JavaScript navigateur)
et l'éprouver avec Route Explorer, premier client, sans que le moteur connaisse
Route Explorer :

```text
RoutesResult → RouteGraph → RouteGraphLayout → adaptateur Route Explorer
  → GraphicScene → Graphic Core JS → renderer SVG → navigateur
```

## Changement de priorité architectural

Forge Design porte l'analyse de projet, Platform, le moteur graphique générique
et l'infrastructure des modules spécialisés ; les domaines (Circuit, Network,
Flowchart…) utiliseront le moteur ensuite. Ordre : Graphics solide → preuve sur
la plateforme → autres clients plateforme → modules spécialisés.

Le ticket demandait de ne pas démarrer FD-CIRCUIT-003 ; celui-ci était déjà
réalisé et commité localement (`2023aea`, non poussé). Question posée au
porteur : **conservé**. FD-GRAPHICS-002 est construit par-dessus ; la roadmap
marque FD-CIRCUIT-003 réalisé et la suite Circuit en attente du socle Graphics.

## État Git initial

```text
$ git log --oneline -3
2023aea feat: implémenter le domaine Circuit V1 (FD-CIRCUIT-003)
d8275f2 feat: définir la ressource Circuit v0.1 (FD-CIRCUIT-002)
c2a135e docs: définir le noyau graphique commun depuis DrawCiel (FD-GRAPHICS-001)
$ git rev-parse --short origin/main
d8275f2
$ git status --short
 M docs/rapports/FD-CONTRACT-001.md
```

## Référence DrawCiel

`git fetch` : `origin/main` = `aac36b27`, inchangé ; référence figée.

## Delta DrawCiel

Vide. Journal mis à jour pour consigner le ticket.

## Choix JavaScript

JavaScript natif, sans build, sans npm runtime, sans dépendance ni CDN.
Aucun bundler : rien ne le justifie pour cinq modules.

## Choix modules

**ES modules natifs** : la CSP Forge (`script-src 'self'`) les autorise sans
modification lorsqu'ils sont servis localement ; Node 24.18 (déjà présent,
déjà utilisé par les tests JS du dépôt) les charge nativement pour des tests
hors DOM ; le packaging se limite à des fichiers statiques. Servis par cinq
routes **fixes** `/graphics/<module>.js` (liste fermée `GRAPHICS_MODULES`,
`text/javascript; charset=utf-8`) : aucun serveur de fichiers générique ;
`/graphics/absent.js` et `/graphics/../server.py` donnent 404.

## GraphicScene

`{width, height, title?, description?, nodes, edges}`, transmise au moteur,
jamais persistée ; validée puis copiée et gelée.

## Node

`id` opaque, `kind` (`node`), `label` accessible, `rect`, `lines` affichées,
`presentation` (`variant` `default`/`category-1..6`, `tone`
`default`/`warning`/`muted`), `data` opaque restituée au client.

## Edge

`id`, `source`, `target` (nœuds existants), `points` (polyligne fournie),
`label`/`labelAt` facultatifs, `presentation` (`line`, `arrow`, `tone`).
**Décision** : une arête vers un nœud absent fait **refuser la scène** (pas de
diagnostic partiel) ; une scène refusée n'est jamais rendue.

## Geometry

`point`, `rect` (dimensions strictement positives), `Number.isFinite`,
`|v| ≤ 10⁶`, NaN et Infinity refusés ; flèche calculée depuis le dernier
segment. Aucune transformation.

## Validation

Objets simples seulement (prototype `Object` ou nul), clés inconnues refusées
à tous les niveaux, types primitifs, identités uniques (nœuds, arêtes),
références résolues, présentations dans des listes fermées (aucune CSS libre),
limites ; erreurs `GraphicSceneError` avec chemin.

## Limits

`MAX_GRAPHIC_NODES` 5 000, `MAX_GRAPHIC_EDGES` 20 000, identités et libellés
8 192 (un chemin source Forge peut atteindre 4 096 caractères et figure dans
l'identité JSON), textes 2 048, 4 lignes de 256, 64 points par arête, 16
données de 512, coordonnées 10⁶. Bornes testées à la limite et limite + 1.
Une scène trop grande laisse Route Explorer sur son repli statique, avec un
message.

## Renderer SVG

`renderScene(container, scene)` : `createElementNS`, attributs fixes ou
numériques, `textContent` ; aucun balisage injecté, aucun style en ligne,
aucune référence d'identifiant partagée (flèches en polygones, pas de
`<marker id>`), donc aucune collision entre instances. Apparence par classes
`gx-*` (`shell.css`). Remplaçable : le moteur ne lui transmet que la scène et
l'état de sélection.

## Accessibilité

SVG `role="group"`, `aria-label`, `<title>`, `<desc>` ; nœuds
`role="button"`, `tabindex="0"`, `aria-pressed`, `aria-label`, `<title>` ;
focus visible ; ton toujours doublé d'un texte (présence), cycle en pointillés
avec libellé « (cycle) ».

## Sélection

Simple, runtime : `select(id)` (identité inconnue refusée, état inchangé),
`clearSelection()`, bascule au clic, Entrée, Espace ; Échap efface et rend le
focus ; incidence et voisins directs en O(degré) grâce à un index O(V + E) ;
aucune analyse transitive ; `onSelectionChange` par instance, sans bus global.

## Cycle de vie d'une instance

`createGraphicEngine(container, scene, options)` → `render`, `select`,
`clearSelection`, `focus`, `selection`, `node`, `scene`, `destroy`,
`isDestroyed`. Écouteurs liés à un `AbortController` par rendu ; `destroy()`
les retire, supprime le SVG et l'état ; toute opération ultérieure lève une
erreur. Aucun timer.

## Transport de la scène

Options comparées : bloc JSON inerte, point d'accès JSON local, attributs
`data-*`. **Retenu** : `<script type="application/json" data-graphic-scene>`
dans la page — même rendu serveur que le reste de Route Explorer, aucune
requête supplémentaire (un point d'accès relancerait l'analyse ou exigerait
un cache), aucune limite de taille d'attribut. Sécurité : `scene_json_payload`
échappe `<`, `>`, `&`, U+2028, U+2029 en `\uXXXX` ; un libellé
`</script><svg onload=…>` ne peut pas fermer le bloc ; lecture par
`textContent` puis `JSON.parse`, sans `eval`, `Function` ni balisage. Un bloc
`application/json` n'est pas exécuté : CSP inchangée.

## Sécurité

Contenu de projet toujours traité comme texte ; scène validée comme contenu non
fiable ; aucun accès réseau, stockage ni cookie dans le moteur ; aucune
lecture ni écriture de projet. Libellé hostile du projet de test
(`</script><svg onload=alert(1)>.html`) rendu comme texte dans Chromium et
Firefox, sans dialogue ni exception.

## Progressive enhancement

**Stratégie A** : le SVG serveur reste le repli sans JavaScript, sans attribut
d'interaction (plus de `role="button"` ni d'identités exposées), dans
`data-graphic-fallback` ; le moteur rend dans `data-graphic-host` puis masque
le repli. Tableau, diagnostics, cycles, filtres, liens source, analyse
transitive et liste textuelle des relations sont inchangés. Le message
d'état sans JavaScript remplace l'ancien `<noscript>`. Duplication assumée :
le repli et la scène sont deux vues du même `RouteGraphLayout` (les points des
arêtes produisent aussi le chemin SVG du repli, testé).

## Adaptateur Route Explorer

`forge_design/web/route_graph_scene.py`, pur : `build_route_graphic_scene(layout)`
réutilise les identités du `RouteGraph`, dérive l'identité d'arête de
`(source, cible, type)` (unique dans un `RouteGraph`), traduit
route/handler/contrôleur/template en `category-1..4`, présence en ton et ligne
de texte, cycle en pointillés. `route_graph_layout.py` expose désormais les
points de chaque arête (`PositionedEdge.points`, chemin SVG inchangé). Aucun
nouvel appel au Tool, aucun accès au projet, Bridge et registre (cinq Tools)
inchangés.

## Ancienne implémentation Route Explorer

`route-graph.js` est **remplacé** : il devient un client module (lecture de la
scène, création de l'instance, panneau de détails) ; toute logique de
sélection est dans le moteur. Une seule interaction graphique. Le double DOM
`tests/js/route_graph_dom.cjs` de l'ancien script est supprimé ; les règles
CSS `.graph-node.is-*` remplacées par `gx-*`. La section d'architecture
« Interaction locale du graphe » est marquée remplacée.

## Démonstration réelle

Projet synthétique (variante « rich » des tests de stabilité, plus un include
hostile) : 22 nœuds et 19 arêtes rendus par le moteur ; sélection du handler
`HomeController.index` : voisins `GET /`, `home/index.html`,
`mvc/controllers/home_controller.py`, 3 arêtes incidentes, panneau rempli.

## Témoin générique test-only

Scène A → B, A → C sans vocabulaire Forge : validée, indexée, rendue et
sélectionnée par le même moteur dans Node (double DOM) et dans les deux
navigateurs (import dynamique de `/graphics/engine.js`).

## Absence de métier dans Graphics

Test : aucun module Graphics ne contient, en mot entier, `route-explorer`,
`handler`, `controller`, `template`, `circuit`, `resistor`, `entity`,
`network` ; ni `innerHTML`, `eval(`, `fetch(`, `localStorage`,
`document.cookie`, `.style`, `window.`, `globalThis`.

## Tests JavaScript

`tests/js/graphics/` (`node --test`, piloté par `tests/test_route_graph_script.py`,
saut propre si Node absent) : 22 tests — géométrie, scène nominale, doublons
de nœuds et d'arêtes, extrémités absentes, forme stricte (16 mutations
d'entrée), limites borne et borne + 1, vocabulaire, incidence, voisins, boucle,
pas de transitivité, sélection (remplacement, effacement, identité inconnue),
index de 4 000 arêtes, rendu, libellés hostiles, souris et clavier, deux
instances, `destroy`, re-rendu, scène invalide, client Route Explorer (montage,
repli sur scène refusée ou JSON illisible, absence de contournement).
`node --check` sur les 6 modules livrés et les 6 fichiers de test.

## Tests Python

`tests/test_route_graph_scene.py` (nouveau, 10) : identités reprises,
présentation générique, arêtes uniques et résolues, points ↔ chemin du repli,
pureté, transport non fermable (5 caractères). `tests/test_web_inspector.py`
mis à jour au nouveau contrat : scripts JSON inerte et module, absence
d'attributs d'interaction dans le repli, scène JSON cohérente et échappée,
cinq modules servis, 404 hors liste.

## Tests navigateur

Infrastructure de FD-REALPREVIEW-005 réutilisée (bibliothèque standard),
serveur de test sur le port 8766 (le 8765 était occupé par l'instance
Forge Design du porteur, laissée intacte), projet synthétique sous `tmp/`.

| Vérification | Chromium 154.0.8037.92 (CDP) | Firefox 153.4.0 (BiDi) |
|---|---|---|
| SVG, nœuds, arêtes, labels visibles ; repli masqué | OK | OK |
| Libellé hostile rendu comme texte, aucune exécution | OK | OK |
| Clic souris réel, voisins directs, panneau | OK | OK |
| Échap (effacement et focus), Entrée, Tab, Espace réels | OK | OK |
| Témoin générique et deux instances isolées, `destroy` | OK | OK |
| Aucune erreur console ni violation CSP | OK (seul 404 : favicon, connu) | OK |
| MIME des modules | OK | — |
| Sans JavaScript : repli statique, tableau, message | OK | non exécuté (BiDi sans bascule simple ; couvert par Chromium et les tests HTTP) |

Captures examinées : graphe rendu, nœud sélectionné, arêtes incidentes,
flèches, panneau de détails.

## CSP

Inchangée : `default-src 'self'; style-src 'self'; script-src 'self'; …` sans
`unsafe-inline` ; aucun script en ligne exécutable (bloc JSON inerte), aucun
style en ligne.

## Packaging

`pyproject.toml` : cinq modules `static/graphics/*.js` en package-data.
Wheel : modules, `route-graph.js` et `route_graph_scene.py` présents.
Installée isolément (`pip install --target`) : serveur lancé depuis
l'installation, projet ouvert, `/routes` (22 nœuds, 19 arêtes, script
module), six scripts servis en `text/javascript; charset=utf-8`, CSP
inchangée ; aucun accès réseau externe.

## Performance

Validation, index d'incidence et rendu en O(V + E) ; voisins en O(degré) ;
aucun benchmark. Index de 2 000 nœuds et 4 000 arêtes dans les tests ; rendu
réel de 22 nœuds immédiat.

## Limitations

Pas de layout, ports, routage, grille, zoom/pan, glisser, édition, commandes,
historique, multi-sélection ni groupes. Un seul client réel. Lignes de
nœud non tronquées par le moteur (l'adaptateur fournit des lignes déjà
courtes). Firefox non exercé sans JavaScript.

## DrawCiel : éléments repris ou non

Repris en principe (sans code) : création SVG par `createElementNS`, nœuds
focusables, sélection et focus. Non repris : `render()` monolithique (REWRITE),
`innerHTML`, marqueurs à identifiant, routage (`cleanRoute`, `adaptedRoute`,
`moveWireSegmentStable` : ticket ultérieur). Aucun code DrawCiel copié.

## Mutations

12 sabotages, tous détectés (Node et/ou pytest) :

| Sabotage | Détecté par |
|---|---|
| Nœud dupliqué accepté | `identités dupliquées refusées` |
| Extrémité absente acceptée | `scène invalide : aucune instance ni rendu` |
| NaN accepté | `géométrie : nombres finis seulement` |
| Libellé via innerHTML | rendu (double DOM refusant innerHTML) et contrat statique |
| Pas de nettoyage d'instance | `destroy retire le SVG, les écouteurs et l'état` |
| Sélection globale entre instances | `deux instances indépendantes` |
| Incidence incorrecte (source seule) | `sélection souris et clavier, voisins directs` |
| Escape sans effet | idem |
| Route Explorer contournant le moteur | `montage` et contrat statique du client |
| Payload JSON non échappé (script hostile) | `test_payload_cannot_close_script` |
| Scène absente de la page | `test_web_transitive_graph` |
| Présentation libre acceptée | `forme stricte` |

## Critères architecturaux

| | Question | Réponse |
|---|---|---|
| A | Scène test-only sans donnée Forge ? | **Oui** (Node, Chromium, Firefox) |
| B | Route Explorer connaît Graphics ? | **Oui**, via son adaptateur et son client |
| C | Graphics connaît Route Explorer ? | **Non** (test de vocabulaire) |
| D | Format persistant propre ? | **Non** |
| E | Lit un projet Forge ? | **Non** |
| F | Sauvegarde quelque chose ? | **Non** |
| G | Sélection runtime seulement ? | **Oui** |
| H | Renderer remplaçable ? | **Oui** (`svg-renderer.js` isolé, entrée = scène) |
| I | Deux instances indépendantes ? | **Oui** |
| J | Sans JavaScript, informations essentielles conservées ? | **Oui** |

## Roadmap mise à jour

Phase 10 : changement de priorité, FD-GRAPHICS-002 fait, FD-CIRCUIT-003
réalisé et conservé, suite Circuit en attente ; FD-GRAPHICS-003 à choisir
après cette preuve. **Recommandation** : migrer d'abord Entity Explorer comme
deuxième client. La tranche a montré que le contrat de scène tient pour un
client réel, mais un second client (deux colonnes, arêtes multiples, pivots)
éprouvera la généricité avant d'élargir l'API ; viewport et zoom/pan ne
manquent à aucun des deux graphes actuels, déjà défilables.

## Fichiers créés

- `forge_design/web/static/graphics/geometry.js`, `model.js`, `scene.js`,
  `svg-renderer.js`, `engine.js`
- `forge_design/web/route_graph_scene.py`
- `tests/js/graphics/fake-dom.mjs`, `scenes.mjs`, `model.test.mjs`,
  `selection.test.mjs`, `engine.test.mjs`, `route-client.test.mjs`
- `tests/test_route_graph_scene.py`
- `docs/graphics/graphics-engine.md`, `docs/rapports/FD-GRAPHICS-002.md`

## Fichiers modifiés

- `forge_design/web/static/route-graph.js` (client du moteur),
  `templates/routes.html` (repli, hôte, scène, module), `routes.py`
  (scène), `route_graph_layout.py` (points), `server.py` (routes fixes),
  `static/shell.css` (classes `gx-*`), `pyproject.toml`
- `tests/test_route_graph_script.py` (pilote Node), `tests/test_web_inspector.py`
- `docs/graphics/graphics-core-contract.md`, `docs/02-architecture.md`,
  `docs/03-roadmap.md`, `docs/circuit/circuit-scope.md`,
  `docs/graphics/drawciel-reference.md`

Supprimé : `tests/js/route_graph_dom.cjs`.

## Validation globale finale

| Contrôle | Résultat |
|---|---|
| `python -m compileall -q forge_design` | Réussi |
| `ruff check forge_design tests` | Réussi |
| `ruff format --check .` | 371 fichiers conformes |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Réussi |
| `node --check` (6 modules livrés, 6 fichiers de test) | Réussi |
| Suites Node `tests/js/graphics` | 22 réussis |
| `tests/test_route_graph_scene.py` + `tests/test_route_graph_script.py` | 24 réussis |
| Route Explorer et Web (`tests/test_route*`, `tests/test_web*`) | 822 réussis |
| Suite globale `pytest` (hors du dépôt, `--basetemp` sous `tmp/`) | **4531 réussis**, relancée après insertion de ces résultats |
| `python -m pip check` | Aucune dépendance cassée |
| Chromium 154 / Firefox 153 | Toutes vérifications réussies |
| Wheel installée isolément | Serveur, `/routes` et assets servis |

## État Git final

Avant commit (fichiers du ticket ; `FD-CONTRACT-001.md` hors commit) :

```text
 M docs/02-architecture.md
 M docs/03-roadmap.md
 M docs/circuit/circuit-scope.md
 M docs/graphics/drawciel-reference.md
 M docs/graphics/graphics-core-contract.md
 M docs/rapports/FD-CONTRACT-001.md
 M forge_design/web/route_graph_layout.py
 M forge_design/web/routes.py
 M forge_design/web/server.py
 M forge_design/web/static/route-graph.js
 M forge_design/web/static/shell.css
 M forge_design/web/templates/routes.html
 M pyproject.toml
D  tests/js/route_graph_dom.cjs
 M tests/test_route_graph_script.py
 M tests/test_web_inspector.py
?? docs/graphics/graphics-engine.md
?? docs/rapports/FD-GRAPHICS-002.md
?? forge_design/web/route_graph_scene.py
?? forge_design/web/static/graphics/
?? tests/js/graphics/
?? tests/test_route_graph_scene.py
```

Commit unique : `feat: implémenter le premier noyau graphique avec Route
Explorer (FD-GRAPHICS-002)`, au-dessus de `2023aea` (FD-CIRCUIT-003, conservé).
Aucun push.
