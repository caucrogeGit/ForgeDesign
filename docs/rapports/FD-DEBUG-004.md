# Rapport — FD-DEBUG-004

## Ticket et objectif

Ajouter au détail un flux SVG statique des étapes runtime structurées connues :
DebugError → DebugFlow → layout → SVG Jinja. Aucune nouvelle lecture ou interaction.
La pièce jointe s’arrête dans les rubriques du rapport à « Command » ; validations,
packaging et livraison locale suivent les conventions des tickets précédents.

## État Git initial

main propre et synchronisée avec origin/main à `3c693ef` — FD-DEBUG-003.
État Git et huit derniers commits inspectés avant modification.

## Modèle DebugFlow

DebugFlowNode, DebugFlowEdge et DebugFlow gelés, collections en tuples.
Types prévus request/router/controller/model/sql/template/response ; le constructeur
ne produit que les cinq types représentés par le contrat actuel.
IDs fixes debug-node-[kind], une occurrence par type. Arêtes entre chaque paire
successive d’étapes présentes, sans intermédiaire invisible ni diagnostic nouveau.

## Règle de non-invention

Source unique : l’événement public déjà acquis et masqué. Aucun accès filesystem,
JSON, registre, Request ou contexte. Ordre conceptuel explicite ; le texte de page
précise que ce n’est pas une trace d’exécution. Message, catégorie, exception,
hint, localisation et traceback ne déterminent aucune étape.
Les propriétés textuelles None ou vides ne créent pas de nœud.

## Request

Un objet request présent crée Requête. Détail : méthode et chemin disponibles,
séparés par un espace. Aucun GET ou / par défaut ; un objet vide garde uniquement
le type Requête. La query, les noms POST et headers ne sont pas copiés dans le flux.

## Router

Uniquement event.route renseigné, label Route et valeur exacte du modèle public.
Aucune analyse dynamique ou résolution de route.

## Controller

Uniquement event.controller renseigné, label Contrôleur. Chaîne conservée dans le
modèle logique ; seule sa représentation visuelle peut être raccourcie.

## Model

Aucun nœud : DebugError ne garantit pas de propriété model. Une frame
mvc/models/user.py ne permet aucune inférence, pas plus que le SQL ou le contrôleur.

## SQL

Uniquement event.sql renseigné. Label SQL et « Requête disponible ».
La requête intégrale n’est pas copiée dans DebugFlow et ne figure pas dans le SVG,
y compris dans title. La section SQL textuelle existante conserve sa valeur masquée.

## Template

Uniquement event.template renseigné, label Template. Chemin logique conservé,
détail graphique borné et valeur complète dans le title et la section textuelle.
La catégorie template seule ne crée pas cette étape.

## Response

Aucun nœud : aucune donnée structurée response/status_code dans le contrat actuel.
Aucun statut HTTP déduit du niveau, de la catégorie ou de l’exception.

## Layout

Fonction pure layout_debug_flow, modèles géométriques gelés et tuples.
Disposition horizontale : rectangles 220 × 90, marges 20, espace 80, hauteur 130.
Coordonnées X : 20 + 300 × index. Flèches horizontales entre centres des bords.
Dimensions positives même pour la projection vide, qui n’est jamais rendue en SVG.
Lookup des extrémités par map, parcours linéaire des nœuds/arêtes.
Détails visuels limités à 24 caractères, ellipse incluse. Modèles d’entrée intacts.

## SVG

Rendu serveur Jinja, viewBox/width/height issus du layout. Marker de flèche local.
Classes debug-flow/node/edge et classes de type explicites. Pas d’asset externe,
HTML généré en Python, script ou dépendance frontend. Conteneur horizontal défilant.
Sans étape : message « Aucun flux structuré disponible pour cet événement. »,
aucun SVG. Les 400/404/409 ne construisent ni modèle ni layout.

## Accessibilité

SVG role=img, aria-labelledby référençant title et desc. Types écrits en texte,
sans distinction par couleur seule. Title par nœud, sections textuelles complètes
conservées. Conteneur défilant focusable avec contour visible pour accès clavier.
Aucune sélection, action métier, zoom ou pan scripté.

## Intégration détail

Flux runtime placé entre Résumé et Requête HTTP. Le même événement sélectionné
alimente texte et graphe indépendamment, après l’unique appel debug-center.
Toutes les sections FD-DEBUG-003 conservées. Aucune route, nouveau Tool ou paramètre.
Bridge, redaction, Tool, filtres, sélection pure, registre et contexte inchangés.

## Sécurité

Valeurs déjà masquées exclusivement, échappement Jinja des textes et title SVG.
Fixtures hostiles route/controller/template/request.path : pas de script interprété,
secrets synthétiques absents. SQL et request.query absents du SVG.
Pas d’ouverture des fichiers cités, navigation source, exécution cible ou DB.
CSP et politiques HTTP existantes conservées.

## Déterminisme

Même événement → mêmes nœuds/IDs/arêtes et coordonnées. Pas de UUID, random ou hash.
Toutes les combinaisons des cinq étapes disponibles sont testées. Aucun cycle à
analyser dans ce schéma séquentiel. Construction et layout ne modifient pas l’entrée.

## Non-écriture

Tests HTTP : octets et mtime du journal conservés après détail. Scénario installé :
snapshot octets/taille/mtime de tous les fichiers projet et configuration XDG avant
et après chaque GET, avec identité inspection du contexte stable.
Seul le script de fixture ajoute volontairement une ligne entre consultations.

## Fichiers créés

- forge_design/tools/debug_flow.py
- forge_design/web/debug_flow_layout.py
- tests/test_debug_flow.py
- tests/test_debug_flow_layout.py
- tests/test_web_debug_flow.py
- docs/rapports/FD-DEBUG-004.md

## Fichiers modifiés

- forge_design/web/debug_detail.py : deux projections pures après sélection.
- forge_design/web/templates/debug_detail.html : section SVG et état vide.
- forge_design/web/static/shell.css : styles locaux du flux.
- docs/tools/debug-center.md : fonctionnement et limites du schéma.
- docs/02-architecture.md : chaîne logique/layout/rendu.

Aucun fichier de test historique modifié ; package-data existant suffit.

## Tests ajoutés

49 nouveaux cas : 38 logique, sept layout, quatre HTTP.
Logique : 32 sous-ensembles, trois requests partielles, catégories database/template
sans propriété correspondante, absence Model/Response, IDs/arêtes/déterminisme,
immutabilité, détails complets et pureté. Blocage open/os/Path/JSON/registre/Bridge.
Layout : zéro à cinq nœuds, dimensions, coordonnées, absence de chevauchement nominal,
extrémités dans le viewBox, immutabilité, déterminisme et troncature visuelle seule.
HTTP : complet/partiel/unique/vide, ordre X, marker/title/desc/ARIA, XSS/secrets,
sections existantes, aucun JS, no-store, un seul Tool, 400/404/409 sans SVG.

## Test réel

Copie temporaire du squelette Forge, fixtures fabriquées avec ses helpers :
A request/route/controller/template ; B request/controller/sql avec une frame
mvc/models/user.py ; C message seulement. Aucun collecteur ni application exécutée.
Wheel installée --no-deps --no-index --target ; processus Python -I dont la provenance
du serveur et du layout installés est vérifiée, quatre Tools confirmés.
Liens extraits de la liste puis suivis :

| Événement | Types de nœuds | Arêtes | Coordonnées X |
|---|---|---:|---|
| A | request, router, controller, template | 3 | 20, 320, 620, 920 |
| B | request, controller, sql | 2 | 20, 320, 620 |
| C | aucun | 0 | aucune |

B ne crée ni Model, Router, Template ou Response. C affiche l’état vide sans SVG.
SQL/query/traceback ne sont pas copiés dans le SVG ; secret synthétique absent.
Sections textuelles, ARIA, absence JS et unique appel Tool vérifiés.
Append d’un événement : liste 4 sur 4 et anciens détails toujours consultables.
/routes et /entities accessibles. Snapshots projet/XDG et contexte inchangés.
Serveur arrêté, thread terminé, socket fermé, port réutilisable.
Script et journal ignorés : tmp/verify_fd_debug_004.py et .log.

## Packaging

Wheel : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `a35b727057ec616a402832d66976d07419d88fe6d168d01100c794d49b0a90f7`.
Modules logique/layout/Web, template et CSS inspectés et comparés aux sources,
ainsi que Bridge/Tool/filtres et scripts historiques. Aucun tests/ ou tmp/ distribué.
Installation réelle et scénario HTTP réussis. Aucune nouvelle dépendance.

## Commandes exécutées et résultats

| Contrôle | Résultat |
|---|---|
| Git initial et huit commits | Baseline conforme |
| pytest -q --tb=short | 1171 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Installation temporaire et scénario HTTP | Succès |

Outils .venv. Suite HTTP et scénario installé hors sandbox pour les sockets locaux ;
build isolé autorisé pour ses dépendances. Typage Literal des étapes et traitement
du détail optionnel corrigés avant validation. Journal : tmp/pytest_fd_debug_004.log.
Diff complet, nouveaux fichiers, documentation et rapport relus avant commit.

## Tests sautés

Aucun pytest sauté. Scripts Node historiques vérifiés. Pas de navigateur réel ou
lecteur d’écran testé ; vérifications structurelles HTTP/DOM et géométrie nominale.

## Limites restantes

Schéma conceptuel de métadonnées, pas une trace d’exécution. Model/Response absents
faute de données structurées. Textes longs raccourcis par caractères sans mesure
typographique ni segmentation en graphèmes ; valeurs complètes disponibles dans
le détail. Défilement horizontal pour plusieurs étapes, aucune interaction métier.
Bornes de lecture, identité ligne/id et limites du masquage restent celles des
précédents tickets. Aucune donnée runtime supplémentaire acquise.

## État Git final

Un seul commit local sur main, rapport inclus, sans push, selon la convention de
livraison des tickets précédents. Message :
`feat: ajouter le flux graphique Debug Center (FD-DEBUG-004)`.
Hash et état Git final communiqués dans la réponse de livraison.
