# Rapport — FD-ROUTES-011

## Ticket et objectif

Construire une représentation immuable des relations déjà établies par Route Explorer, puis l’afficher sans nouvelle découverte ni analyse du projet.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `47377b9` — FD-ROUTES-010.
État Git et cinq derniers commits inspectés avant modification.

## Modèle RouteGraph

Dataclass gelée contenant deux tuples : `nodes` et `edges`.
`build_route_graph(result: RoutesResult) -> RouteGraph` ne transforme que ses données d’entrée. Une entrée vide donne deux tuples vides.

## Modèle des nœuds

`GraphNode` gelé : `id`, `kind`, `label`, `presence` typée avec le contrat existant et non applicable par défaut.
Quatre types : route, handler, controller, template. Les dépendances statiques utilisent aussi template.
Les références absentes ou refusées restent représentées avec leur présence connue. Aucun nœud n’est inventé pour une dépendance dynamique.

## Modèle des arêtes

`GraphEdge` gelé : `source`, `target`, `kind`.
Relations : handles, defined-in, renders, extends, includes, imports, from-imports.
Un contrôleur n’est lié que si son chemin existe dans le résultat. Un template principal est lié quand sa résolution vaut found avec chemin, indépendamment de présence et syntaxe.

## Identifiants déterministes

Les IDs sont des tuples encodés en JSON compact : type et identité syntaxique, avec méthode et chemin séparés pour les routes.
Exemple : `["route","GET","/contact"]`.
Cet encodage évite les collisions de séparateurs. Aucun hash Python, UUID ou identité mémoire n’est utilisé pour produire un ID.
GET et POST sur le même chemin restent distincts.

## Construction du graphe

Le constructeur parcourt chaque route, son handler, son contrôleur éventuel, son template statique et ses dépendances déjà fournies.
Il ne consulte pas les dépendances d’un autre nœud et ne suit aucune arête. Une cible également principale peut avoir ses propres relations uniquement parce qu’une autre route les fournit déjà.

## Mutualisation

Identité : méthode/chemin pour route, référence pour handler, chemin pour contrôleur ou template.
Les nœuds identiques et les arêtes strictement identiques sont mutualisés. Deux routes distinctes vers un handler commun gardent deux arêtes.
Les occurrences de route identiques sont fusionnées, même si leurs noms diffèrent. Toutes les relations distinctes restent conservées.
Si des métadonnées contradictoires sont fournies, la première occurrence prévaut ; aucune nouvelle résolution n’est tentée.

## Ordre

Les dictionnaires locaux conservent la première découverte : route, enrichissements associés, dépendances dans leur ordre d’entrée.
Les tuples produits sont reproductibles pour un même résultat, sans tri alphabétique ni état persistant.

## Pureté et isolation

Aucun accès filesystem, parsing Python/Jinja, appel au Bridge ou au registre dans le builder.
Les tests bloquent open, stat, lstat, scan, ast.parse, Environment.parse, ToolRegistry.get/list et read_routes pendant la construction.
Les modèles d’entrée ne sont pas mutés. Les structures de sortie sont gelées et contiennent uniquement des valeurs immuables.

## Intégration Route Explorer

Module dédié `forge_design/tools/route_graph.py`, après le Bridge : `RoutesResult → RouteGraph`.
Aucun nouveau Tool, aucune modification de RouteExplorerTool, du registre ou du contexte projet.

## Intégration Web

`/routes` construit le graphe depuis le résultat déjà reçu et transmet les nœuds et arêtes au template.
Un index par ID sert seulement à afficher les labels des extrémités.
La section « Vue des relations » suit le tableau existant : blocs des nœuds avec présence textuelle, puis liste des relations orientées.
HTML/CSS uniquement, libellés échappés, aucun lien interactif ni JavaScript. `Cache-Control: no-store` conservé.

## Fichiers créés

- [forge_design/tools/route_graph.py](../../forge_design/tools/route_graph.py).
- [tests/test_route_graph.py](../../tests/test_route_graph.py).
- [docs/rapports/FD-ROUTES-011.md](FD-ROUTES-011.md).

## Fichiers modifiés

- [forge_design/web/routes.py](../../forge_design/web/routes.py) : appel du builder et contexte d’affichage.
- [forge_design/web/templates/routes.html](../../forge_design/web/templates/routes.html) : section des relations.
- [forge_design/web/static/shell.css](../../forge_design/web/static/shell.css) : blocs et espacement.
- [tests/test_web_inspector.py](../../tests/test_web_inspector.py) : assertions HTTP sur le graphe.
- [docs/02-architecture.md](../02-architecture.md) : contrat de représentation pure.

Aucune dépendance ou métadonnée de distribution modifiée.

## Tests ajoutés

Sept nouveaux cas couvrent entrée vide, route seule, enrichissements optionnels, quatre relations de dépendances, présence absente, exclusion du dynamique, partage des handlers/contrôleurs/templates, déduplication, méthodes distinctes, ordre, IDs déterministes, immutabilité et isolation.
Le test HTTP existant est enrichi pour vérifier la section, les labels, extends/includes, template absent, échappement HTML, absence de nœud dynamique, tableau conservé et no-store.

## Test réel

Wheel construite, ressources inspectées et installation temporaire sans dépendances. Un processus Python isolé vérifie l’origine importée ; les dépendances runtime viennent de `.venv`.
Une copie du squelette reçoit ContactController.list, sa route et contacts/list.html déclarant extends base.html et include contacts/_table.html.
Le GET `/routes` affiche ces nœuds et relations ainsi que les routes du squelette. Le contrôle conserve également le cycle de diagnostic valide/invalide d’une dépendance, l’actualisation et la fermeture du projet.
Le serveur est arrêté et le port réutilisable. Le dépôt Forge de référence reste intact. L’absence d’accès projet pendant le builder est instrumentée dans les tests unitaires.

Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `3c35decb43fb87f9b0fa6815f9fb7044d528776a14171921099f2abfb1d10abe`.
Script ignoré : `tmp/verify_fd_routes_011.py`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat |
|---|---|
| État Git et historique | Vérifiés |
| `pytest` | 374 tests réussis, dont 7 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| `python -m pip wheel --no-deps --wheel-dir tmp/wheels .` | Succès |
| Wheel installée et HTTP réel | Succès |

Outils de `.venv`, Python 3.13.5 ; sockets locaux autorisés hors sandbox.
Les premières lignes trop longues signalées par Ruff ont été formatées avant validation finale.
Pip a désactivé son cache utilisateur inaccessible, sans erreur de dépendances.
Le diff complet, nouveaux fichiers et rapport compris, est relu avant commit.

## Tests sautés

Aucun test pytest sauté. Aucun contrôle visuel navigateur, rendu cible ou génération complète Forge revendiqué.

## Limites restantes

Identités syntaxiques uniquement : une même référence de handler peut désigner des symboles runtime différents selon les sources ; le graphe ne les distingue pas.
Les métadonnées de première occurrence sont conservées sans arbitrage de contradictions.
Aucune nouvelle découverte, fermeture transitive, détection de cycles ou interaction graphique. Les limites du Bridge restent applicables.

## État Git final

Un seul commit local sur `main`, rapport inclus, sans push.
Message : `feat: construire le graphe direct des routes (FD-ROUTES-011)`.
Le hash et l’état Git après commit sont communiqués dans la réponse de livraison.
