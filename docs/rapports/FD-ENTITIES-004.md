# Rapport — FD-ENTITIES-004

## Ticket et objectif

Ajouter la sélection locale d’une entité ou d’un pivot, ses relations et voisins directs, un panneau de détails et les commandes clavier, sans modification de l’analyse ou du layout.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `af2b6b3` — FD-ENTITIES-003.
État Git et cinq derniers commits inspectés avant modification.

## Interaction progressive

Le serveur conserve SVG, entités, pivots, tableaux et anomalies. Un script natif local chargé avec defer améliore uniquement le graphe présent.
La section porte data-entity-graph ; tous les sélecteurs et événements de sélection sont bornés à son conteneur. Aucun framework ni factorisation du script Route Explorer.

## Sélection des nœuds

Une référence selected par conteneur ; clic ou activation clavier sélectionne, une deuxième activation du même nœud désélectionne. Un autre nœud remplace la sélection.
Classes is-selected et is-related, aria-pressed et épaisseurs de bordure distinguent choix et voisinage. Aucun élément n’est masqué ou atténué.
Les IDs et métadonnées viennent directement des attributs data-node-id/kind/label/table/field-count déjà rendus. Les IDs ne sont jamais interpolés dans des sélecteurs CSS.

## Relations directes

Les arêtes exposent data-source-id/target-id/edge-kind/edge-label. Un parcours des arêtes repère les extrémités égales au nœud choisi ; un Set marque les voisins sans duplication.
Distance 1 exclusivement : Article sélectionne article_tag mais pas Tag ; le pivot sélectionne Article et Tag. Les arêtes entrantes et sortantes sont traitées de la même façon.
Chaque arête incidente apparaît une fois dans le panneau, sans fusion des parallèles. Une boucle User → User compte une fois ; le nœud sélectionné ne reçoit pas aussi la classe de voisin.
Coût linéaire dans les nœuds et arêtes du DOM, sans récursion ni analyse métier.

## Panneau de détails

État initial annoncé : « Sélectionnez une entité ou un pivot dans le graphe. ».
Après sélection : type, nom complet, table, nombre de champs et nombre d’arêtes directes. Pour un pivot, le libellé devient « Champs supplémentaires ».
Une liste orientée source → cible conserve les noms métier disponibles, sinon le type d’arête. Ses li sont créés via createElement et remplis avec textContent. Aucun HTML projet interprété.
Détails, liste et bouton Désélectionner sont cachés sans sélection. Le panneau ne change ni tableaux ni coordonnées.

## Navigation clavier

Entrée et Espace activent le nœud, avec preventDefault. Échap dans le conteneur réinitialise la sélection ; le bouton fait de même. Ces deux actions rendent le focus au nœud précédent.
Aucune interception clavier globale. Les autres touches gardent leur comportement. Aucun zoom, déplacement, filtre ou navigation transitive.

## Accessibilité

Nœuds avec role=button, tabindex=0, aria-pressed=false initial et aria-label comprenant le type et le nom complet.
Le SVG passe de role=img à role=group pour exposer ses boutons descendants ; titre et description restent référencés. Le statut utilise role=status et aria-live=polite.
Focus visible par trait discontinu, sélection par bordure renforcée et couleur complémentaire, voisins par bordure renforcée. Conteneur défilant inchangé ; détails avec retour à la ligne des noms longs.

## JavaScript

Fichier dédié entity-graph.js, IIFE stricte, aucune variable globale ni dépendance.
Map locale des nœuds DOM et Set de voisins seulement, aucun modèle métier supplémentaire ou JSON embarqué. Réinitialisation à chaque chargement, sans URL, stockage ni persistance.
Absence de graphe, nœuds vides ou panneau incomplet : sortie sans exception. Une arête partielle dont une extrémité est absente n’invente pas de ligne de détail.
Plusieurs conteneurs restent indépendants. route-graph.js reste inchangé.

## CSP

GET /entity-graph.js sert exclusivement le fichier packagé fixe, avec text/javascript; charset=utf-8, suivant le contrat de route-graph.js. POST refusé, aucune politique générale de cache modifiée.
Script externe de même origine et defer, sans contenu inline. La réponse HTTP confirme script-src 'self' sans unsafe-inline. Aucun changement de CSP ou middleware.

## Intégration Entity Explorer

Seule nouvelle route : l’asset GET /entity-graph.js. Le script est référencé uniquement lorsqu’un graphe est présent ; aucun asset référencé sans projet ou sans entité.
Bridge, EntityExplorerTool, EntityGraph, layout_entity_graph, registre et contexte restent inchangés. Trois Tools toujours enregistrés. /entities conserve no-store.

## Sécurité

Labels, tables et attributs échappés par Jinja. Le script utilise textContent, hidden, classList et setAttribute ; pas d’innerHTML/outerHTML/insertAdjacentHTML, eval ou new Function.
Sentinelle source interdisant réseau, stockage, cookies, modification d’URL, styles dynamiques et parsing JSON. Aucun SQL, exécution cible ou écriture projet.
Les fixtures hostiles vérifient le texte HTML échappé, les valeurs DOM exactes, puis leur insertion en texte dans le double DOM Node.

## Fallback sans JavaScript

Le SVG serveur et les tableaux restent visibles et complets. Noscript précise que seule la sélection nécessite JavaScript. Aucun tableau modifié par le script.
Le panneau reste à son état initial ; aucune sélection ne persiste au rechargement.

## Fichiers créés

- forge_design/web/static/entity-graph.js
- tests/js/entity_graph_dom.cjs
- tests/test_web_entity_graph_interaction.py
- docs/rapports/FD-ENTITIES-004.md

## Fichiers modifiés

- forge_design/web/templates/entities.html : contrat DOM, ARIA, panneau et script.
- forge_design/web/static/shell.css : états de sélection et focus.
- forge_design/web/server.py : ressource GET fixe.
- pyproject.toml : package-data du script.
- tests/test_web_entity_graph.py : contrat accessible interactif et seul script autorisé.
- docs/tools/entity-explorer.md : usage et clavier.
- docs/02-architecture.md : amélioration DOM locale et séparation inchangée.

## Tests ajoutés

Trois nouveaux tests pytest : contrat statique JS, exécution Node et contrat HTTP/asset. Les cinq scénarios HTTP du graphe existant sont adaptés aux boutons et au script externe uniquement lorsque le graphe existe.
Le double DOM Node couvre clic/toggle/remplacement, Entrée/Espace/Échap, bouton et retour du focus, aria-pressed, pivot, voisins directs sans transitivité, parallèles, auto-relation comptée une fois, texte hostile, conteneurs isolés, absence de graphe, panneau incomplet, arête partielle et réinitialisation.
HTTP : MIME et contenu exact de l’asset, POST refusé, CSP, defer sans inline, attributs et extrémités réelles, types de nœuds, labels complets, panneau, noscript, tableaux et no-store. XSS sur nom d’entité, table et relation ; valeurs récupérées intactes par HTMLParser.
Les tests de graphe, layout, registre et Route Explorer restent actifs.

## Test réel

Wheel installée dans un répertoire temporaire, processus Python -I vérifiant l’origine importée avec runtime .venv. Copie du squelette Forge avec Article, Tag, Comment et User ; Comment → Article, Article → article_tag → Tag et User → User.
Le DOM installé contient cinq nœuds, quatre chemins, les attributs de sélection, aria-pressed=false, panneau, bouton, noscript et l’unique script externe defer. GET /entity-graph.js retourne les mêmes octets que le fichier distribué et le MIME attendu.
Le contrôle conserve relecture après changement volontaire du JSON, anomalies, Route Explorer et comparaison des fichiers/mtime avant/après consultations. XDG temporaire, dépôt Forge intact ; serveur arrêté, thread terminé, socket fermé et port réutilisable.
Script/journal ignorés : tmp/verify_fd_entities_004.py et tmp/verify_fd_entities_004.log.

## Packaging

Wheel reconstruite et archive inspectée : entity-graph.js, template, CSS et modules présents, aucun tests/ ou tmp/ distribué. Installation --no-deps --no-index --target réelle.
Aucune nouvelle dépendance ou étape de build frontend.
Artefact : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `af49ab1641600179d17279788f78b51d22258158106aa3d1271ff107b1e09e58`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| Git initial et cinq derniers commits | Vérifiés |
| pytest | 686 réussis, dont 3 nouveaux tests |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip check | No broken requirements found |
| git diff --check | Succès |
| node --check forge_design/web/static/entity-graph.js | Succès |
| Double DOM Node | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Wheel installée, HTTP/DOM et asset exact | Succès |

Python 3.13.5, Node v24.18.0, outils .venv ; sockets locaux et construction wheel avec autorisation hors sandbox. Pip check désactive son cache utilisateur inaccessible, sans erreur de dépendances.
Diff complet, fichiers nouveaux, documentation et rapport relus avant commit.

## Tests sautés

Aucun test pytest sauté ; Node disponible et exécuté. Le test Node prévoit un saut explicite si cet outil manque.
Interaction vérifiée structurellement et syntaxiquement, et exécutée sur double DOM. Aucun test navigateur réel revendiqué : ce double ne remplace pas un moteur SVG ou les technologies d’assistance.

## Limites restantes

Focus visuel SVG et annonces réelles des lecteurs d’écran non vérifiés dans un navigateur. Sélection et voisinage direct uniquement ; aucune modification des limites du layout ou de l’analyse Forge.
La liste compte les arêtes DOM, notamment les deux segments d’un pivot ; elle ne reconstruit aucune relation métier supplémentaire. Aucun stockage, zoom, édition ou requête de données.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `feat: ajouter l’interaction du graphe Entity Explorer (FD-ENTITIES-004)`.
Le hash et l’état Git final vérifiés sont communiqués dans la réponse de livraison.
