# Rapport — FD-ROUTES-018

## Ticket et objectif

Rechercher et filtrer les résultats déjà calculés de Route Explorer, avec un formulaire GET et une sélection cohérente du tableau, des diagnostics et du graphe.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `ba63483` — FD-ROUTES-017.
État Git et cinq derniers commits inspectés avant modification.

## Modèle RouteFilter

Dataclass gelée : query, method, visibility (all/public/protected), severity (all/error/warning/info), diagnostics_only.
La construction vérifie la taille de recherche et les valeurs de visibilité/sévérité ; recherche vide ou espaces seuls devient None, méthode non vide devient majuscule.
`FilteredRouteExplorer` gelé contient le tuple de routes retenues, RouteDiagnostics filtré et total_routes issu de l'inventaire complet.

## Parsing des critères HTTP

Module Web séparé `parse_route_filter(request)` ; le moteur pur ne connaît pas Request ou la query string.
Paramètres : q, method, visibility, severity, diagnostics (all/only). La checkbox envoie only ; son absence vaut all.
Paramètre reconnu invalide ou recherche trop longue : 400 avant appel au Tool.
La méthode est ensuite validée contre les méthodes réellement présentes dans l'inventaire complet, dans leur ordre de première occurrence pour le select. GTE et une méthode absente, même HTTP standard, donnent 400 ; get devient GET.
Sans inventaire disponible, aucune méthode spécifique ne peut être sélectionnée.
Les clés inconnues sont ignorées. L'API Forge Request.query utilise la première valeur non vide d'une clé répétée ; les valeurs vides sont traitées comme absentes.

## Recherche textuelle

Sous-chaîne insensible à la casse par casefold, sur méthode, chemin, nom de route, référence handler, fichier contrôleur connu ou attendu absent, template principal.
Limite de 256 caractères avant suppression des espaces périphériques ; aucune troncature silencieuse.
Aucune regex utilisateur, fuzzy matching ou recherche dans le contenu des fichiers, les sources ou les dépendances Jinja.
Les champs affichent la recherche normalisée en conservant sa casse saisie.

## Filtres route

Méthode exacte après mise en majuscules ; public correspond à public=True, protected à False.
L'ordre original est conservé, les routes et leurs enrichissements sont réutilisés sans mutation.
Aucun stockage dans CurrentProjectContext, session, cookie ou fichier ; GET /routes sans paramètres revient à la vue complète.

## Filtres diagnostics

`Diagnostic.route_indices` est ajouté en fin de modèle avec un tuple vide par défaut : indices dans le RoutesResult original.
La consolidation mémorise ces associations au moment où elle traite chaque route, sans découverte ni rapprochement par message, nom de handler ou chemin ambigu.
La déduplication cumule tous les propriétaires ; une fermeture partagée restitue ses associations aux routes suivantes sans reparcourir ses nœuds.
Les diagnostics sans association sont globaux. Cycles, troncature et route.partial restent volontairement globaux : visibles s'ils passent la sévérité, mais n'activent jamais diagnostics_only.
Les diagnostics associés ne restent affichés que si au moins une de leurs routes est retenue. Tous les codes, sévérités et messages de FD-ROUTES-017 restent conservés.

## Combinaisons

Les critères route se combinent par ET. Une recherche correspond à n'importe lequel des champs autorisés.
severity seul agit sur la section Diagnostics, sans enlever de route.
diagnostics_only exige au moins un diagnostic associé ; combiné avec severity=error, il exige au moins une erreur associée.
Les diagnostics globaux peuvent donc rester visibles lorsque la sélection de routes est vide, sans contradiction avec ce mode.

## Vue filtrée

Le filtre effectue des parcours linéaires des routes, diagnostics et associations, plus les chaînes comparées ; aucune recherche routes × diagnostics.
Les compteurs d'erreurs, avertissements et informations sont ceux des diagnostics retenus. Le compteur de routes indique X affichées sur Y de l'inventaire original.
Les warnings historiques restent ceux du résultat complet, car ils ne sont pas tous attribuables à une route.
Une sélection vide affiche « Aucune route ne correspond aux filtres. » et conserve le projet ouvert.

## Graphe filtré

Le Web crée une copie de RoutesResult dont seul le tuple routes est remplacé, puis appelle les builders existants RouteGraph et layout.
Aucun nœud n'est masqué après génération du SVG. Les dépendances partagées et transitives des routes retenues restent dans leurs fermetures connues.
La section Cycles agrège uniquement les cycles déjà fournis par ces routes, sans nouvelle détection.
Le diagnostic global de cycle peut rester visible alors que la section Cycles et le SVG n'affichent pas les routes écartées : les deux périmètres sont explicitement distincts.
Sans route, aucun SVG vide n'est généré. Aucun changement du builder métier ou du layout.

## Pureté et isolation

`filter_route_explorer(result, diagnostics, filters)` ne lit aucun fichier et n'appelle ni Bridge, registre, parsing Python/Jinja, consolidation ou détection de cycle.
Sentinelles sur ces opérations pendant le filtre, puis construction du graphe et du layout. Entrées inchangées, sorties gelées, mêmes critères donnant le même résultat.
Un GET valide conserve l'analyse habituelle unique via le Tool ; tous les critères s'appliquent ensuite en mémoire. Un nouveau GET relit normalement l'état courant, sans cache persistant ajouté.
Les tests HTTP comptent un appel au Tool par GET valide et aucun pour les critères invalides vérifiables avant inventaire.

## Intégration Web

Formulaire GET /routes au-dessus des résultats, recherche, selects méthode/visibilité/sévérité, checkbox native et bouton Filtrer.
Réinitialiser est un lien vers /routes sans query string. Les valeurs normalisées restent affichées après soumission.
Tableau, Diagnostics, compteur, Cycles et SVG utilisent la sélection définie ; liens /source existants conservés et testés.
No-store reste déclaré sur la route et couvre les réponses 400. Aucun nouveau POST, JavaScript, HTMX, Alpine, tri ou pagination.

## Accessibilité

Labels explicites liés aux champs natifs, nom du formulaire, boutons textuels et focus visible, y compris sur select.
Grille CSS légère avec retour à la ligne ; checkbox adaptée au style input existant.
Le compteur de routes utilise role=status. Aucun changement dépendant uniquement de la couleur.

## Sécurité

Les paramètres sont uniquement normalisés, validés et comparés aux données existantes.
Aucun usage dans un chemin filesystem, import, nom de template ou commande. Les noms de templates de rendu restent internes.
Les valeurs du formulaire, messages et liens sont échappés par Jinja ; aucune balise script ajoutée.
La navigation source conserve le confinement existant et l'analyse du projet reste en lecture seule.

## Fichiers créés

- [forge_design/tools/route_filters.py](../../forge_design/tools/route_filters.py).
- [forge_design/web/route_filters.py](../../forge_design/web/route_filters.py).
- [tests/test_route_filters.py](../../tests/test_route_filters.py).
- [docs/rapports/FD-ROUTES-018.md](FD-ROUTES-018.md).

## Fichiers modifiés

- [forge_design/tools/route_diagnostics.py](../../forge_design/tools/route_diagnostics.py) : associations cumulées aux routes et diagnostics globaux.
- [forge_design/web/routes.py](../../forge_design/web/routes.py) : parsing, sélection et présentation cohérente.
- [forge_design/web/server.py](../../forge_design/web/server.py) : transmission de Request au handler existant.
- [forge_design/web/templates/routes.html](../../forge_design/web/templates/routes.html) : formulaire, compteur et état vide.
- [forge_design/web/static/shell.css](../../forge_design/web/static/shell.css) : formulaire et focus.
- [tests/test_web_inspector.py](../../tests/test_web_inspector.py) : critères HTTP, erreurs et reset.
- [docs/02-architecture.md](../02-architecture.md) : contrat stateless et associations.

Aucune dépendance ni métadonnée de distribution modifiée.

## Tests ajoutés

48 nouveaux cas : 29 contrôles purs et 19 scénarios HTTP.
Recherche sur tous les champs, casse/espaces/vide/absence, limite 256, méthodes, visibilité, sévérités et combinaisons ; ordre, déterminisme, immutabilité et isolation.
Les tests vérifient les associations d'une dépendance transitive partagée, l'absence d'association abusive pour un handler homonyme, le caractère global des cycles et de la troncature.
Le graphe filtré conserve handler/template partagés et dépendances transitives, exclut les autres routes, conserve les cycles pertinents et peut être vide.
HTTP : valeurs retenues, reset, compteurs exacts, tableau/diagnostics/graphe, absence de résultat, liens source suivis, échappement HTML, absence de script, 400 et no-store.
Toutes les suites antérieures restent actives.

## Test réel

Wheel reconstruite, archive inspectée pour les modules, formulaire et CSS, puis installation temporaire sans dépendances.
Processus Python isolé (-I), origine importée vérifiée, dépendances runtime de `.venv`.
Une copie du squelette reçoit un inventaire explicite de trois routes : GET /contact/list, POST /contact/create et GET /users. Le template de création manque ; celui de liste atteint le cycle contacts/base.html → contacts/layout.html → contacts/base.html.
GET /routes?q=contact retient les deux routes contact ; method=POST et severity=error&diagnostics=only retiennent seulement la création. Chaque graphe contient exactement les routes attendues.
Le contrôle vérifie également diagnostics globaux, état vide sans SVG, reset, CSS packagé et lien source avec ligne ciblée.
Octets et dates des fichiers de la copie sont comparés avant/après. Serveur arrêté, socket fermé et port réutilisable ; dépôt Forge de référence inchangé.

Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `af5bdbb01ff88d447c47ac60626628e5aafd35063a5c8be586c30ba46a8531f6`.
Script ignoré : `tmp/verify_fd_routes_018.py`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| État Git et historique | Vérifiés |
| `pytest` | 518 tests réussis, dont 48 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| `python -m pip wheel --no-deps --wheel-dir tmp/wheels .` | Succès |
| Wheel installée et filtres HTTP réels | Succès |

Outils de `.venv`, Python 3.13.5 ; sockets locaux autorisés hors sandbox.
Une fixture utilisait initialement Contact pour /users : la recherche /contact correspondait correctement à son fichier contrôleur. La fixture sépare désormais les contrôleurs pour tester la sélection voulue. Lignes Ruff trop longues corrigées avant validation finale.
Pip a désactivé son cache utilisateur inaccessible sans erreur de dépendances.
Le diff complet, nouveaux fichiers et rapport compris, est relu avant commit.

## Tests sautés

Aucun test pytest sauté. Aucun contrôle visuel navigateur, rendu cible ou nouvelle génération Forge revendiqué.

## Limites restantes

Les indices diagnostiques concernent uniquement le RoutesResult original associé ; ils ne sont pas des identifiants persistants.
Les diagnostics partagés conservent la première source choisie par la consolidation, même si une autre route propriétaire est seule affichée.
Les filtres portent sur les données statiques disponibles et héritent des limites de l'analyse. Une URL ne fige pas le projet : les résultats peuvent changer entre GET.
Aucune recherche dans les sources ou dépendances, aucun tri, pagination ou préférence persistante.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `feat: ajouter les filtres de Route Explorer (FD-ROUTES-018)`.
Le hash et l'état Git après commit sont communiqués dans la réponse de livraison.
