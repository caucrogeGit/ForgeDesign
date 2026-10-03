# Rapport — FD-GRAPHICS-004

API : [Moteur graphique — API JavaScript](../graphics/graphics-engine.md#viewport) ;
contrat : [Graphic Core](../graphics/graphics-core-contract.md#viewport--fd-graphics-004).

## Ticket et objectif

Ajouter au Graphic Core un viewport 2D générique (fit, zoom, zoom autour d'un
point, pan, home, état runtime) pour présenter des scènes plus grandes que
leur zone, sans modifier les scènes, les graphes ni les layouts métier.

## État Git initial

```text
$ git log --oneline -1
106a53e feat: migrer Entity Explorer sur le Graphic Core (FD-GRAPHICS-003)
$ git rev-parse --short origin/main
106a53e
$ git status --short
 M docs/rapports/FD-CONTRACT-001.md
```

## Référence DrawCiel précédente

`aac36b27`.

## Référence DrawCiel du ticket

`git fetch` : `origin/main` = **`3a1753a2`** (3 octobre 2026, « feat(documents):
confirmer chaque page avant transmission »), figée pour le ticket.

## Delta DrawCiel

`aac36b27..3a1753a2` : un commit SéquenCiel (documents, 41 fichiers), **aucun
fichier DrawCiel** (`static/vendor/drawciel`, adaptateurs, tests navigateur
DrawCiel) modifié. Impact : aucun ; le code viewport étudié est identique à
`aac36b27`.

## Code DrawCiel viewport étudié

`static/vendor/drawciel/js/app.js` à `3a1753a2` : `viewportWorld`,
`viewportCenterWorld`, `applyTransform`, `zoomAt`, `fit`, `zoom100`,
`fitSelection`, `homeView`, `centerWorldPoint`, `navigationBounds`,
`projectBounds`, `viewSnapshot`/`restoreView` (historique de vue), gestion de
la molette (`scrollArea.addEventListener('wheel', zoomAt)`) et du déplacement
du plan (bouton droit, bouton du milieu, Espace + glisser, `capturePointer`).
État DrawCiel : globales `zoom` et `pan {x, y}` (écran = monde × zoom + pan),
appliquées par une transformation CSS sur le plan de travail HTML ; zoom
borné à 0,25–3, molette 1,1 / 0,9, fit à marge 55 px et emprise minimale 120.

## Classification REUSE / EXTRACT / ADAPT / REWRITE

| Élément DrawCiel | Classe | Destination / adaptation |
|---|---|---|
| `zoomAt` (formule pan' = m − (m − pan)·z'/z) | **ADAPT** | `zoomAtState` : même invariant, sur `{scale, x, y}`, pur ; facteur symétrique 1,25 et molette normalisée au lieu de 1,1 / 0,9 (dérive à l'aller-retour) ; Ctrl/Cmd requis |
| `fit` | REWRITE | `fitState` : même principe (échelle limitante, centrage) ; marge 16 px, plafond 100 %, bornes 0,02–4, zone nulle neutre |
| `viewportWorld`, `viewportCenterWorld` | REWRITE | `viewBox`, centre de zone : sans `getBoundingClientRect` ni globales |
| `centerWorldPoint` | REWRITE | intégré au centrage du fit |
| `applyTransform` (CSS `transform`) | non repris | `viewBox` : pas de style en ligne (CSP `style-src 'self'`) |
| Geste bouton du milieu | ADAPT | conservé ; bouton droit non repris (menu contextuel), Espace + glisser non repris (Espace sélectionne le nœud focalisé) ; bouton principal sur le fond ajouté (pas de sélection rectangle dans le moteur) |
| `capturePointer` | ADAPT | `setPointerCapture` / `releasePointerCapture` de l'instance |
| `homeView` (origine de page) | non repris | home = fit |
| `zoom100`, `fitSelection`, historique de vue, minicarte, plan de travail | non repris | hors besoin (pas de persistance ni minicarte) |

Aucun REUSE-AS-IS ni EXTRACT : aucune ligne de DrawCiel n'est copiée ; la
seule capitalisation est la formule du point fixe et le geste du bouton du
milieu. Provenance consignée en tête de `viewport.js` et dans le journal
DrawCiel. Aucun code électrique.

## Besoin réel

Scène Route du projet synthétique : 2120 × 1306 ; Entity : 780 × 750. Avant
le ticket, le SVG prenait la taille logique de la scène et imposait un
défilement dans les deux axes, sans vue d'ensemble.

## Architecture viewport

```text
GraphicScene (inchangée) → svg-renderer (nœuds, arêtes)
                           → viewport.js (état pur) → viewBox du SVG
engine.js : barre d'outils, molette, pointeur, clavier, ResizeObserver, cycle de vie
```

## Choix viewBox ou transform

**Décision A : `viewBox`.** Un seul attribut sur le SVG racine, sans groupe
transformé concurrent ; le SVG occupe la zone par CSS (`width/height: 100 %`),
donc taille visible et taille logique sont enfin distinctes. Les calculs sont
directs (viewBox = x y largeur/scale hauteur/scale), le zoom autour du pointeur
exact (le rapport largeur/hauteur du viewBox est toujours celui de la zone, le
`preserveAspectRatio` par défaut n'introduit aucun décalage), le hit-testing
natif reste correct, aucun style en ligne n'est nécessaire, les tests sont
déterministes. Avant mesure, le viewBox est celui de la scène.

## ViewportState

**Décision B** : `{ scale, x, y }` gelé — `(x, y)` point monde au coin
supérieur gauche, `scale` pixels écran par unité monde — plus la taille de zone
`{ width, height }` mesurée (`clientWidth/clientHeight`) ; `engine.viewport()`
expose les cinq valeurs. Équivalent à `{zoom, pan}` de DrawCiel
(`pan = −x·scale`), sans signe inversé.

## Fit

Échelle = min((L − 32)/l, (H − 32)/h, 1), bornée à 0,02–4, scène centrée ;
marge de 16 px de chaque côté (mesurée exactement 16 px dans les deux
navigateurs) ; zone étroite (≤ 32 px) sans marge ; zone nulle ou non mesurée :
état neutre, jamais NaN ni Infinity. Déterministe.

## Home

**Décision H : home = fit.** Pas d'origine arbitraire.

## Zoom

**Décision C** : `MIN_SCALE = 0,02` (vue d'ensemble jusqu'à ~20 000 unités dans
450 px : les scènes croissent d'un couloir de 24 à 26 unités par arête ; 0,05
initialement envisagé ne permettait pas de voir une scène de 20 000 unités,
cas révélé par les tests), `MAX_SCALE = 4` (texte de 12 à 48 px),
`FIT_MAX_SCALE = 1` (une petite scène n'est jamais agrandie par le fit).
**Décision D** : `ZOOM_STEP = 1,25`, symétrique (+ puis − revient exactement à
l'échelle de départ à 10⁻⁹ près).

## Zoom autour d'un point

Invariant vérifié en Node (écart ≤ 10⁻⁹) et en navigateur réel (écart < 0,5
unité monde, dû à l'arrondi des coordonnées du pointeur). Boutons : centre de
la zone ; molette : pointeur.

## Pan

**Décision F** : glisser au bouton principal sur le fond (jamais sur un nœud :
le clic y reste une sélection) ou au bouton du milieu partout ; Maj + flèches
(15 % de la zone) pour le clavier ; pan exact (100 / −50 px mesurés). Aucune
édition de nœud ; sélection conservée pendant et après le pan.

## Pointer Events

`pointerdown/move/up/cancel` sur la zone, capture du pointeur, classe
`gx-panning` (curseur), `touch-action: none` limité à la zone graphique.

## Wheel

**Décision E** : molette seule non interceptée (défilement de la page
vérifié, +200 px dans les deux navigateurs, viewport inchangé) ; Ctrl/Cmd +
molette — et le pincement de pavé tactile, qui produit Ctrl + molette — zoome
sous le pointeur sans faire défiler la page. Facteur normalisé (pixels, lignes,
pages) et borné à un pas par événement.

## Resize

**Décision G** : tant que l'utilisateur n'a pas zoomé ni déplacé (ou après
Ajuster), le fit suit la zone ; ensuite l'échelle et le centre visible sont
conservés. `ResizeObserver` observe la zone (et `engine.resize()` permet une
remesure explicite) ; sans `ResizeObserver`, la taille initiale reste
utilisée. Vérifié dans les deux navigateurs en redimensionnant la zone (poignée
CSS `resize: vertical`, simulée) et la fenêtre (1400 → 700 px).

## Limites

Échelle 0,02–4, fit plafonné à 1, marge 16 px, pas 1,25, pas clavier 15 %.

## Toolbar

`role="toolbar"`, « Ajuster », « + », « − » (boutons natifs `type="button"`,
`title`, `aria-label`), échelle courante en texte (« 34 % »). Fournie par le
moteur, identique pour les deux clients ; aucun template ne la déclare.

## Accessibilité

Boutons natifs, focus visible (`gx-toolbar-button:focus-visible`), activation
Entrée et Espace (Chromium), ordre de tabulation (Chromium et Firefox), pan
Maj + flèches, sélection clavier inchangée. Le défilement de la page reste
disponible.

## Sélection avec transformation

Clic réel au centre d'un nœud après plusieurs zooms : bon nœud sélectionné,
voisins corrects (Route et Entity, deux navigateurs). Échap après pan efface la
sélection et rend le focus au nœud.

## Route Explorer

Fit initial : scène 2120 × 1306 entière à 34 % dans une zone de 796 × 478, sans
défilement interne, repli masqué ; zoom +/−/Ajuster, Ctrl + molette, pan,
sélection après zoom et pan, Échap, resize : réussis. Aucune modification
métier (graphe, layout, adaptateur, panneau, filtres, diagnostics).

## Entity Explorer

Même parcours, mêmes modules et même barre d'outils ; aucun code viewport dans
le client (test statique : ni `viewBox`, `zoom`, `panBy`, `fit(`, `home(`,
`resize(`, `wheel`, `pointer`).

## Isolation des instances

Node : zoom, pan et boutons dans A, B inchangé. Navigateur : scène Route montée
sur la page Entity, zoom et pan de l'une sans effet sur le viewBox de l'autre.

## Fallback sans JavaScript

L'hôte du moteur sort du conteneur défilant, qui devient le repli
(`data-graphic-fallback`) : sans JavaScript, SVG serveur complet et défilable
comme avant ; avec JavaScript, le conteneur défilant est masqué. Vérifié dans
Chromium (exécution désactivée) et Firefox (profil `javascript.enabled=false`).

## Forge MVC

Le viewport est entièrement client ; seul `viewport.js` rejoint la liste
fermée `GRAPHICS_MODULES` enregistrée par le Router Forge dans
`create_application()` ; aucune route métier, aucun point d'accès JSON, aucun
serveur parallèle (test de frontière mis à jour).

## CSP

Inchangée (`script-src 'self'`, `style-src 'self'`) ; aucun style ni script en
ligne (le viewBox est un attribut SVG) ; aucune violation dans les deux
navigateurs ; aucun stockage navigateur ni cookie (vérifié).

## Tests Node

51 (29 + 22) : `viewport.test.mjs` (11 : fit tous ratios, bornes, zone nulle,
invariant du zoom, bornes de zoom, pan exact, resize, politique d'instance,
valeurs invalides, molette, 1000 opérations) ; `engine-viewport.test.mjs`
(11 : barre d'outils, avant/après mesure, boutons et scène inchangée, molette,
pan sur fond / nœud / bouton du milieu / droit, Maj + flèches, isolation,
resize, ResizeObserver, destroy, home = fit quelle que soit la scène) ;
contrats statiques des clients étendus au viewport.

## Tests Python

Liste fermée des modules (`test_route_graph_script.py`,
`test_graphics_forge_boundary.py`, `test_web_inspector.py` : `/graphics/viewport.js`
servi), suites Node pilotées par pytest (7 suites). Route, Web, Entity,
Graphics : 1061 réussis.

## Tests Chromium

Chromium 154.0.8037.92 (CDP, événements souris, molette et clavier natifs) :
25 vérifications réussies — par page (Route, Entity) : fit initial sans
défilement interne, + / − / Ajuster au clavier, molette seule = défilement,
Ctrl + molette sous le pointeur, sélection après zoom, pan au glisser avec
sélection conservée, Maj + flèche, Échap après pan, resize après interaction,
resize avant interaction ; deux viewports indépendants ; aucune erreur ni
violation CSP (seul 404 : favicon, connu) ; aucun stockage ; sans JavaScript
sur les deux pages.

## Tests Firefox

Firefox 153.4.0 (WebDriver BiDi) : même parcours, 23 vérifications réussies ;
sans JavaScript : 2 réussies (profil dédié). Limite du harnais constatée :
l'injection de touches BiDi n'active pas les boutons natifs (reproduit sur un
bouton ordinaire hors moteur) ; dans Firefox, l'ordre de tabulation est vérifié
au clavier et l'activation par de vrais clics ; l'activation clavier est
prouvée dans Chromium.

## Mutations

11 sabotages, tous détectés par les suites Node :

| Sabotage | Détecté par |
|---|---|
| Fit ignore la marge | `fit : scène large…, marge respectée` |
| Fit dépasse le plafond | `fit : très large, très haute, carrée, petite` |
| Zoom hors MIN/MAX | `fit : bornes…` et tests de zoom |
| zoomAt dérive du point cible | Ctrl + molette sous le pointeur |
| Pan déplace le rendu au lieu du viewport | pan au glisser |
| Viewport global partagé (état de module) | deux instances indépendantes |
| destroy laisse les écouteurs | destroy |
| Molette bloque le défilement partout | molette seule non interceptée |
| Route possède une logique viewport | contrat statique du client Route |
| Entity possède une logique viewport | contrat statique du client Entity |
| home dépend du contenu de la scène | home = fit quelle que soit la scène |

Le premier mutant « viewport global » ne partageait que l'état initial et
survivait ; reconstruit en vrai état de module, il est tué.

## Performance

Chaque opération de viewport est O(1) et ne réécrit qu'un attribut ; aucun
re-rendu de nœuds ou d'arêtes ; pan et zoom fluides sur les deux scènes ; aucun
benchmark.

## Packaging

`pyproject.toml` : `static/graphics/viewport.js` ajouté. Wheel : module présent.

## Installation wheel

Installée isolément : `/routes`, `/entities`, `/route-graph.js`,
`/entity-graph.js` et les six modules (dont `viewport.js`) servis en
`text/javascript; charset=utf-8`, CSP inchangée.

## Limites restantes

- **Lisibilité au fit** : la scène Route entière tient à 34 %, mais ses textes
  de 12 unités passent à ~4 px, illisibles ; la vue d'ensemble montre la
  structure, pas les libellés.
- Bande vide au-dessus des nœuds : les deux layouts réservent un couloir par
  arête (24–26 unités) au sommet de la scène ; au fit, une grande partie de la
  zone est occupée par ces couloirs.
- Focus clavier sur un nœud hors zone : pas de recentrage automatique.
- Activation clavier des boutons non vérifiable dans Firefox via BiDi.

## Roadmap

Graphics avant extension métier ; Circuit inchangé. FD-GRAPHICS-004 fait.

### Décisions obligatoires

| | Question | Réponse |
|---|---|---|
| A | viewBox ou transformation ? | **viewBox** : une seule autorité, pas de style en ligne, calculs directs, zoom au point exact, hit-testing natif |
| B | ViewportState ? | `{ scale, x, y }` + taille de zone mesurée |
| C | Bornes ? | `MIN_SCALE = 0,02`, `MAX_SCALE = 4`, fit plafonné à 1 |
| D | Facteur ? | 1,25 symétrique ; molette normalisée, un pas au plus par événement |
| E | Molette ? | Seule : défilement de page ; Ctrl/Cmd (et pincement) : zoom sous le pointeur |
| F | Pan ? | Glisser au bouton principal sur le fond ou au bouton du milieu ; Maj + flèches |
| G | Resize ? | Fit suivi avant interaction ; échelle et centre conservés après |
| H | home == fit ? | **Oui** |
| I | Le viewport modifie-t-il la GraphicScene ? | **Non** |
| J | Même viewport pour Route et Entity ? | **Oui**, sans code client |
| K | Capitalisation DrawCiel ? | Formule du zoom autour d'un point (ADAPT) et geste du bouton du milieu ; fit et conversions réécrits ; rien d'autre |
| L | Forge MVC unique backend Web ? | **Oui** |
| M | Prochaine limitation concrète ? | **La lisibilité au fit** : sur la scène réelle de 2120 × 1306, la vue d'ensemble à 34 % rend les libellés illisibles, et une large bande de couloirs d'arêtes occupe le haut de la zone. Les deux pistes observées — compacité des layouts clients (couloirs) et niveaux de détail du rendu — sont à arbitrer par le porteur ; aucune n'est décidée ici |

## Fichiers créés

- `forge_design/web/static/graphics/viewport.js`
- `tests/js/graphics/viewport.test.mjs`, `tests/js/graphics/engine-viewport.test.mjs`
- `docs/rapports/FD-GRAPHICS-004.md`

## Fichiers modifiés

- `forge_design/web/static/graphics/engine.js` (viewport, barre d'outils,
  interactions), `graphics/svg-renderer.js` (taille par CSS),
  `static/shell.css` (`gx-frame`, `gx-toolbar-*`, `gx-viewport`),
  `templates/routes.html` et `templates/entities.html` (hôte hors du conteneur
  défilant, conteneur = repli), `server.py` (`viewport` dans
  `GRAPHICS_MODULES`), `pyproject.toml`
- `tests/js/graphics/fake-dom.mjs`, `engine.test.mjs`, `route-client.test.mjs`,
  `entity-client.test.mjs`, `tests/test_route_graph_script.py`,
  `tests/test_graphics_forge_boundary.py`, `tests/test_web_inspector.py`
- `docs/graphics/graphics-engine.md`, `docs/graphics/graphics-core-contract.md`,
  `docs/graphics/drawciel-reference.md`, `docs/02-architecture.md`,
  `docs/03-roadmap.md`

## Validation globale finale

| Contrôle | Résultat |
|---|---|
| `python -m compileall -q forge_design` | Réussi |
| `ruff check forge_design tests` | Réussi |
| `ruff format --check .` | 377 fichiers conformes |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Réussi |
| `node --check` (6 modules, 2 clients, 9 fichiers de test) | Réussi |
| Suites Node `tests/js/graphics` | 51 réussis |
| Route, Web, Entity, Graphics ciblés | 1061 réussis |
| Suite globale `pytest` (hors du dépôt, `--basetemp` sous `tmp/`) | **4547 réussis**, relancée après insertion de ces résultats |
| `python -m pip check` | Aucune dépendance cassée |
| Chromium 154 / Firefox 153 | 25 / 23 vérifications réussies, plus 2 sans JavaScript dans Firefox |
| Wheel installée isolément | `/routes`, `/entities`, `viewport.js` et assets servis |

## État Git final

Commit unique `feat: ajouter le viewport au Graphic Core (FD-GRAPHICS-004)`,
au-dessus de `106a53e`. `docs/rapports/FD-CONTRACT-001.md` reste modifié
localement, hors commit. Aucun push.
