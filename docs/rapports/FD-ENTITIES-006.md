# Rapport — FD-ENTITIES-006

## Ticket et objectif

Ajouter des filtres GET stateless à la projection Web d’Entity Explorer : recherche,
type d’élément, type de relation, sévérité et présence de diagnostics.

## État Git initial

`git status` et `git log --oneline --decorate -5` inspectés avant modification.
main propre et synchronisée avec origin/main à `e96b8a9` — FD-ENTITIES-005.
Aucun AGENTS.md dans le dépôt.

## Modèle EntityFilter

Dataclass gelée : query, item_type, relation_type, severity et diagnostics_only.
Valeurs par défaut None/all/all/all/False. Types Literal et validation explicite
des catégories au constructeur ; limite centralisée MAX_FILTER_QUERY_LENGTH.

## Parsing GET

Module Web séparé utilisant Request.params et Request.query. Paramètres acceptés :
q, type, relation, severity et diagnostics. Valeurs invalides, clés inconnues,
recherche de plus de 256 caractères et répétitions non vides : HTTP 400 avant Tool.
diagnostics accepte only et all ; absence signifie all.

Le code public de Request Forge a été inspecté : parse_qs élimine les valeurs
vides. Elles sont donc traitées comme absentes, y compris dans une répétition :
q=&q=Article est une seule valeur disponible, q=&q= est une absence. Deux valeurs
non vides, même identiques, sont refusées pour chacun des cinq paramètres.
Cette convention est documentée et testée sans modification du parseur Forge.

## Recherche textuelle

Limite avant normalisation, sans troncature. strip puis casefold, vide devient None.
Sous-chaîne simple Unicode sans regex utilisateur. Entités : name, table,
field.name/type/references. Relations : from_entity, to_entity, name, inverse_name,
foreign_key, pivot_table, from_key, to_key et name/type/references des champs pivot.
Les valeurs normalisées sont réaffichées dans le formulaire.

## Filtre entités

Sélection directe par recherche et diagnostics_only éventuel. type=relation
supprime cette sélection des tableaux et détails. type=entity conserve des entités
isolées et exclut les relations. Le filtre de type de relation ne filtre pas les
entités directement retenues. Ordre et occurrences conservés.

## Filtre relations

Combinaison du type d’élément, type de relation, recherche et diagnostics_only.
Aucune réinterprétation ou suppression métier des relations. Une relation à cible
absente reste dans le tableau lorsqu’elle satisfait les filtres.

## Filtre sévérité

Seule EntityDiagnostics fournit la sévérité. La liste est filtrée uniquement par
severity, sans recherche textuelle ni restriction par visibilité des éléments.
Les compteurs error/warning/info reflètent cette liste. Les diagnostics globaux
restent affichables, même sans élément retenu. severity seul ne filtre pas les éléments.
build_entity_diagnostics et les diagnostics bruts sont inchangés.

## diagnostics_only

L’association d’entité repose sur l’égalité exacte diagnostic.source.path et
entity.source.path. L’association de relation repose exclusivement sur
relation_index == source_index, indépendamment de sa position dans le tuple filtré.
Seuls les diagnostics de la sévérité retenue sélectionnent des éléments.
Aucune association depuis code, message, nom ou contenu. Un diagnostic global
sans rattachement ne fait apparaître aucun élément arbitraire.

## Vue filtrée

EntityFilteredView gelée expose tuples entities, relations, graph_entities,
EntityDiagnostics et les totaux originaux. Les compteurs affichés comptent les
éléments des tableaux, pas les extrémités graphiques de support.
Aucun EntitiesResult filtré n’est construit. La transformation ne lit ni n’écrit,
ne consulte aucun registre/contexte/Web/JSON et conserve les entrées intactes.

## Graphe filtré

Extraction minimale de build_entity_graph_from_items(entities, relations).
L’API historique build_entity_graph(result) délègue à cette fonction ; l’algorithme,
les modèles, orientations et règles de pivots restent identiques.
Le Web lui transmet graph_entities et relations de la vue filtrée, jamais le graphe complet.

Les entités directement sélectionnées et les premières occurrences des extrémités
nécessaires sont conservées dans l’ordre original. Les homonymes de support ne sont
pas ajoutés arbitrairement. Les many_to_many gardent leurs extrémités et pivot ;
une extrémité absente n’est pas inventée. Le graphe peut montrer une extrémité
connue isolée pour une relation à référence manquante. Les IDs sont déterministes
localement à la vue, sans promesse de stabilité entre filtres.
Aucun masquage CSS/JS, changement du layout ou de entity-graph.js.

## Intégration Web

Formulaire GET avec labels, recherche, trois selects, checkbox et Réinitialiser.
Valeurs actives conservées, compteur affiché/total par type, états vides explicites.
Sans nœud, pas de SVG ni script ; sinon le DOM interactif existant est conservé.
Attributs data-diagnostic-code/severity/index inchangés. Sources toujours textuelles.
Un seul appel EntityExplorerTool.run(root) par GET valide avec projet.
Aucun nouveau Tool, route, POST ou JavaScript. POST /entities reste 405, réponses
200 et 400 conservent no-store. Styles existants du formulaire réutilisés, CSS inchangé.

## Stateless

L’URL contient tous les critères. Aucun filtre dans CurrentProjectContext,
RecentProjects, session, cookie ou stockage navigateur. Un GET /entities suivant
revient à l’inventaire complet. Le Tool reçoit seulement la racine du projet.
Les trois Tools enregistrés restent inchangés ; Route Explorer reste inchangé.

## Sécurité

Jinja échappe la recherche réaffichée : fixture guillemet/balise script vérifiée
par parsing HTML. Aucune regex utilisateur, SQL, accès supplémentaire au projet
ou validation Forge. Les erreurs de parsing sont affichées en texte avec role=alert.
Les tests de pureté bloquent open, os.open/stat/listdir, Path.open/read_text/read_bytes,
json.loads, ToolRegistry.get et read_entities pendant filter_entities.

## Non-écriture

Scénario installé : comparaison octets, taille et mtime de chaque fichier projet
et configuration XDG avant/après chaque GET, valide ou invalide. Aucune différence.
Le POST initial ouvre seulement la copie temporaire ; la configuration reste isolée.
Les tests HTTP vérifient également les octets et mtime de l’historique après filtrage.

## Fichiers créés

- forge_design/tools/entity_filters.py
- forge_design/web/entity_filters.py
- tests/test_entity_filters.py
- tests/test_web_entity_filters.py
- docs/rapports/FD-ENTITIES-006.md

## Fichiers modifiés

- forge_design/tools/entity_graph.py : entrée par tuples, algorithme inchangé.
- forge_design/web/entities.py : parsing puis projection et graphe filtrés.
- forge_design/web/templates/entities.html : formulaire, compteurs et sélections.
- docs/tools/entity-explorer.md : paramètres et conventions.
- docs/02-architecture.md : flux exact et séparation des responsabilités.

Bridge, EntityExplorerTool, EntitiesResult, diagnostics bruts, registre, layout,
CSS et scripts inchangés. Tous les fichiers de tests historiques sont inchangés.

## Tests ajoutés

67 nouveaux cas : 40 unitaires et 27 HTTP.
Unitaires : défauts, vide/strip/casefold Unicode, tous les champs de recherche,
combinaisons type/relation, chaque sévérité avec et sans diagnostics_only,
rattachements exacts, diagnostic global, homonymes, conservation des ordres,
limite/valeurs invalides, immutabilité, déterminisme, absence de mutation et pureté.
Graphe : entité isolée, extrémités many_to_one et many_to_many, pivot, suppression
des relations/nœuds inutiles, IDs déterministes dans la vue.

HTTP : matrice de 15 projections avec compteurs et nombres de nœuds/arêtes,
formulaire GET, valeurs actives, réinitialisation, tableaux cohérents, script
conditionnel, no-store, un appel Tool, retour sans filtre, POST refusé et Route Explorer.
Onze cas invalides couvrent catégories, limite, clé inconnue et cinq répétitions.
Un test couvre XSS, absence de projet, valeurs vides et frontière de 256 caractères.
Les suites Bridge, diagnostics et interaction historique restent actives.

## Test réel

Wheel installée dans un dossier temporaire avec --no-deps --no-index --target.
Processus Python -I utilisant les dépendances .venv, origine installée du serveur
et du module de filtrage vérifiée. Copie de ../Forge/skeleton/data, quatre entités
créées avec le constructeur canonique Forge : Article, Tag, Comment et User.
Relations : Comment → Article, Article → Tag via article_tag, User → User et
User → Missing produisant relation.entity_missing à l’index 3.

| GET | Entités tableau | Relations | Nœuds | Arêtes |
|---|---:|---:|---:|---:|
| /entities | 4 | 4 | 5 | 4 |
| ?q=article | 1 | 2 | 4 | 3 |
| ?relation=many_to_many | 4 | 1 | 5 | 2 |
| ?severity=error&diagnostics=only | 0 | 1 | 1 | 0 |
| ?type=relation&relation=many_to_many | 0 | 1 | 3 | 2 |
| ?q=position_missing | 0 | 0 | 0 | 0 |

Le diagnostic reste affiché dans ces scénarios, uniquement filtrable par severity.
La ligne User → Missing reste présente avec diagnostics_only. severity=critical
retourne 400 sans écriture. Retour à /entities complet et GET /routes réussis.
Serveur arrêté, thread terminé, socket fermé et port réutilisable. Dépôt Forge intact.
Script et journal ignorés : tmp/verify_fd_entities_006.py et .log.

## Packaging

Wheel reconstruite : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `ddabd24eaa40324ef57c3f41d8ff2ce01725267c0bef59f4d0dd98f3305ed422`.
Archive inspectée : modules tools/web de filtres, graphe, template, CSS et JS,
avec octets identiques aux sources. Aucun tests/ ou tmp/ dans la wheel.
Installation réelle et scénario HTTP réussis. Aucune dépendance ajoutée.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat |
|---|---|
| git status ; git log --oneline --decorate -5 | Baseline conforme |
| pytest -q --tb=short | 779 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check forge_design/web/static/entity-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Installation temporaire et scénarios HTTP | Succès |

Outils .venv, Python 3.13.5, Node disponible. Tests HTTP et scénario réel exécutés
hors sandbox pour les sockets locaux ; build isolé autorisé hors sandbox pour ses
dépendances. Journal complet de suite : tmp/pytest_fd_entities_006.log (ignoré).
Diff complet, nouveaux fichiers et rapport relus avant commit.

## Tests sautés

Aucun test pytest sauté. Interaction historique exécutée sur double DOM Node,
syntaxe du script vérifiée. Aucun navigateur ou lecteur d’écran réel revendiqué.

## Limites restantes

Les diagnostics peuvent concerner un élément masqué ; seul severity filtre leur
liste. Les sources/index sont les seules associations fiables. Les supports du
graphe peuvent être sans diagnostic ou hors recherche et ne comptent pas comme
entités de tableau. Homonymes : première occurrence utilisée comme extrémité.
Répétitions avec valeurs vides soumises à la convention du parseur Forge décrite.
Aucune stabilité des IDs entre vues, validation exhaustive, score ou filtre persistant.

## État Git final

Un seul commit local sur main, rapport inclus, sans push conformément au ticket.
Message : `feat: ajouter les filtres Entity Explorer (FD-ENTITIES-006)`.
Le hash et l’état Git final sont communiqués dans la réponse de livraison.
