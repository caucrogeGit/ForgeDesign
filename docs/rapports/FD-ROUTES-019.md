# Rapport — FD-ROUTES-019

## Ticket et objectif

Permettre de sélectionner un nœud du SVG existant, consulter ses détails et mettre en évidence ses relations directes, uniquement dans le DOM déjà rendu.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `c1493a8` — FD-ROUTES-018.
État Git et cinq derniers commits inspectés avant modification.

## Choix d’interaction

JavaScript natif local, sans dépendance, requête ou logique métier supplémentaire.
Clic, Entrée et Espace basculent la sélection : une deuxième activation du même nœud désélectionne ; un autre nœud remplace le précédent.
Aucun zoom/pan, déplacement, recalcul de layout ou persistance.

## Contrat DOM

Conteneur explicite data-route-graph. Chaque nœud porte data-node-id, data-node-kind, data-node-label et data-node-presence ; chaque arête porte data-source-id et data-target-id.
Les IDs sont ceux de RouteGraph, échappés par Jinja puis lus directement depuis dataset ; ils ne sont jamais interpolés dans un sélecteur CSS.
Aucun JSON de RoutesResult envoyé au navigateur. Les relations, coordonnées et modèles Python restent inchangés.

## Sélection de nœud

Une seule référence DOM selected par conteneur. La classe is-selected et aria-pressed=true indiquent le choix.
Les autres nœuds reviennent à aria-pressed=false. Le statut textuel mentionne « Élément sélectionné » et le nom complet.
L'épaisseur de bordure distingue la sélection sans dépendre uniquement de la couleur. Aucun élément n'est atténué.

## Relations directes

Un parcours des arêtes compare uniquement leur source/cible à l'ID choisi.
Les arêtes entrantes et sortantes reçoivent is-related ; leurs voisins directs sont marqués, sans suivre les voisins des voisins.
Complexité linéaire en nœuds/arêtes du DOM à chaque activation. Les classes de cycle existantes restent conservées.

## Navigation clavier

Nœuds avec tabindex=0 et role=button ; aria-label conserve le libellé complet et aria-pressed expose l'état.
Le SVG utilise role=group avec titre/description existants, afin de ne pas masquer les boutons descendants dans une image atomique.
Entrée et Espace activent, avec preventDefault pour éviter notamment le défilement dû à Espace.
Échap lorsque le focus est dans le conteneur ou le bouton Désélectionner réinitialise l'état et rend le focus au nœud précédent.
Focus visible en pointillés ; aucune interception clavier globale hors du graphe.

## Panneau de détails

État initial : « Sélectionnez un élément du graphe. ».
Après sélection : Type (Route/Handler/Contrôleur/Template), Nom complet, Présence (Présent/Absent/Chemin refusé/Non vérifiable/—).
La zone de statut est annoncée poliment ; détails et bouton sont cachés sans sélection.
Aucune source n'est ajoutée au GraphNode : les liens /source existants restent dans le tableau. Aucune nouvelle association ni indication de cycle calculée dans le panneau.

## JavaScript

Fichier dédié route-graph.js, chargé avec defer. Tous les sélecteurs de nœuds, arêtes et champs sont bornés au conteneur.
Classes CSS, attribut aria-pressed, hidden et textContent uniquement ; aucune réécriture du SVG.
Un conteneur absent ou vide ne provoque pas d'action. L'initialisation remet l'état à zéro et ne modifie ni URL, historique, hash ou stockage.

## CSP

Inspection de core/security/csp.py installé : script-src 'self', avec nonce optionnel selon Forge.
La ressource locale de même origine est compatible ; aucun changement de middleware ou de politique, aucun unsafe-inline.
GET /route-graph.js sert exclusivement le fichier packagé fixe avec text/javascript; charset=utf-8, sur le même modèle que shell.css. Aucun POST ajouté.
Les réponses Route Explorer conservent no-store.

## Sécurité XSS

Labels et IDs échappés par Jinja dans les attributs et le SVG. Le script utilise textContent pour les données projet et n'interprète jamais leurs caractères comme HTML.
Contrats statiques interdisant fetch, XMLHttpRequest, localStorage, sessionStorage, innerHTML, CDN, eval, modification d'URL, cookies et styles inline.
Un ID et un label contenant caractères HTML, guillemet et antislash sont exercés dans le double DOM sans erreur ni interprétation.

## Progressive enhancement

Le serveur fournit toujours tableau, diagnostics, graphe et liste textuelle des relations. Les liens source et le formulaire GET ne dépendent pas du script.
Un message noscript explique que seule la sélection nécessite JavaScript.
Sans graphe après filtrage, aucun script n'est référencé. Le script tolère également un conteneur vide.
Le défilement du SVG reste inchangé ; le panneau autorise le retour à la ligne des noms longs.

## Intégration avec les filtres

Le script reçoit uniquement les nœuds et arêtes déjà filtrés par le serveur. Il ne connaît ni critères de filtre, RoutesResult, Bridge ou registre.
Un nouveau GET produit un nouveau DOM et une sélection neutre. Aucune requête n'est émise par la sélection.

## Packaging

route-graph.js ajouté explicitement au package-data de pyproject.toml ; aucune dépendance npm/Python ou étape de build frontend.
Wheel reconstruite et archive inspectée, puis installation temporaire et contrôle HTTP du script réellement distribué.

## Fichiers créés

- [forge_design/web/static/route-graph.js](../../forge_design/web/static/route-graph.js).
- [tests/test_route_graph_script.py](../../tests/test_route_graph_script.py).
- [tests/js/route_graph_dom.cjs](../../tests/js/route_graph_dom.cjs).
- [docs/rapports/FD-ROUTES-019.md](FD-ROUTES-019.md).

## Fichiers modifiés

- [forge_design/web/server.py](../../forge_design/web/server.py) : ressource GET fixe.
- [forge_design/web/templates/routes.html](../../forge_design/web/templates/routes.html) : attributs, boutons SVG, panneau et script defer.
- [forge_design/web/static/shell.css](../../forge_design/web/static/shell.css) : sélection, relations, focus et panneau.
- [pyproject.toml](../../pyproject.toml) : ressource distribuée.
- [tests/test_web_inspector.py](../../tests/test_web_inspector.py) : contrats DOM, CSP et ressource.
- [docs/02-architecture.md](../02-architecture.md) : interaction locale et progressive enhancement.

## Tests ajoutés

Trois nouveaux tests pytest regroupent contrats statiques, exécution JavaScript et contrat HTTP/DOM.
Node déjà installé (v24.18.0) exécute le script livré dans un contexte isolé avec un double DOM minimal : clic, Entrée, Espace, Échap, bouton, aria-pressed, relations entrantes/sortantes sans transitivité, texte sûr, focus, conteneurs isolés et réinitialisation.
Aucune bibliothèque DOM, npm ou infrastructure navigateur ajoutée. Le test Node est sauté explicitement si Node n'est pas disponible ; il a bien été exécuté ici.
Le test HTTP inspecte les tags avec HTMLParser, vérifie les IDs et extrémités, rôles/tabindex, panneau neutre, script externe unique sans contenu inline, CSP, MIME, refus de POST et absence de script sur sélection vide.
Les tests existants avec labels HTML vérifient désormais aussi l'attribut data-node-label échappé. Les anciennes interdictions générales de script sont adaptées au seul script externe autorisé ; aucune protection contre le HTML projet n'est retirée.

## Test réel

Wheel installée sans dépendances dans un répertoire temporaire ; processus Python isolé (-I), origine importée vérifiée et runtime de `.venv`.
Une copie du squelette conserve les trois routes, le template absent et le cycle du contrôle précédent. GET /routes et les GET filtrés retournent le SVG enrichi, le panneau et la référence defer ; CSP vérifiée sans unsafe-inline.
GET /route-graph.js retourne 200 et le MIME JavaScript attendu. Les liens source, état vide, reset, CSS et absence de modification des fichiers restent contrôlés.
Serveur arrêté, socket fermé et port réutilisable ; dépôt Forge de référence intact.

Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `4d00b040966b62c33e97e5571d40f955f798253ddc99efff919271c064fb88b4`.
Script ignoré : `tmp/verify_fd_routes_019.py`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| État Git et historique | Vérifiés |
| Inspection CSP Forge et disponibilité JS/navigateur | self confirmé, Node disponible, aucun navigateur automatisable trouvé |
| `pytest` | 521 tests réussis, dont 3 nouveaux tests |
| `node --check forge_design/web/static/route-graph.js` | Succès |
| Exécution JS sur double DOM via pytest | Succès |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| `python -m pip wheel --no-deps --wheel-dir tmp/wheels .` | Succès |
| Wheel installée, HTTP SVG/JS/CSP et filtres | Succès |

Outils de `.venv`, Python 3.13.5 ; sockets locaux autorisés hors sandbox.
Une ligne trop longue et deux variables inutilisées du test HTML signalées par les validateurs sont corrigées avant validation finale.
Pip a désactivé son cache utilisateur inaccessible sans erreur de dépendances. Le diff complet, nouveaux fichiers et rapport compris, est relu avant commit.

## Tests sautés

Aucun test pytest sauté sur cet environnement.
Pas de contrôle visuel navigateur : aucun outil navigateur, Chromium/Firefox ou installation Playwright utilisable n'a été trouvé dans les emplacements vérifiés. Les tests Node utilisent un double DOM, pas un moteur SVG ou une technologie d'assistance.
Aucun rendu de template cible ou nouvelle génération Forge revendiqué.

## Limites restantes

Le comportement visuel du focus SVG et les annonces des lecteurs d'écran ne sont pas validés dans un navigateur réel.
Sélection et voisinage directs uniquement, sans déplacement ni zoom. Pas de lien source dans le panneau puisque GraphNode n'en porte pas.
Les limites d'analyse, de taille et de layout du graphe existant restent applicables. Aucune interaction ne les modifie.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `feat: ajouter l'interaction du graphe Route Explorer (FD-ROUTES-019)`.
Le hash et l'état Git après commit sont communiqués dans la réponse de livraison.
