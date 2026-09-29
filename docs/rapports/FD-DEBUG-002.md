# Rapport — FD-DEBUG-002

## Ticket et objectif

Ajouter recherche, filtres niveau/catégorie, tri temporel et compteurs à la liste
Debug Center, par projection pure du résultat existant. Préparer id et ligne dans
le DOM, sans détail, navigation source ou temps réel.

## État Git initial

main propre et synchronisée avec origin/main à `90ed6a6` — FD-DEBUG-001.
État Git et huit derniers commits inspectés avant modification.
Le contrat Forge v1.0 vérifié au ticket précédent est conservé.

## Modèle DebugFilter

Dataclass gelée : query=None, level=all, category=all, order=newest par défaut.
Validation explicite des catégories admises au constructeur. Réutilisation de
MAX_FILTER_QUERY_LENGTH=256, contrôle avant et après strip/casefold ; vide → None.
Les listes de choix niveau/catégorie servent également au formulaire.

## Parsing GET

Module Web dédié parse_debug_filters(Request), utilisant params/query. Paramètres :
q, level, category, order. Clés inconnues présentes, valeurs invalides et répétitions
non vides : 400 avant tout appel Tool, même sans projet.
Convention Forge inchangée : valeurs vides éliminées, donc q=&q=users équivaut à
q=users ; q=&q= équivaut à une absence. Une clé inconnue entièrement vide disparaît
également avant cette frontière, comme pour Entity Explorer. Convention documentée.

## Recherche textuelle

Sous-chaîne simple casefold dans id, exception_type, message, route, controller,
template, request.method, request.path, hint et correlation_id. AND avec les filtres
exacts. Aucune recherche dans SQL, traceback, request.query, niveau ou catégorie.
Seuls les textes du modèle déjà masqué sont utilisés. Aucun JSON relu, regex
utilisateur ou récupération de la valeur brute. Recherche normalisée réaffichée.
128 ß donnent 256 caractères ; 129 sont refusés après expansion Unicode.

## Filtre niveau

all/ERROR/WARNING/INFO/CRITICAL, égalité exacte. CRITICAL ne sélectionne pas ERROR.
Valeurs originales du contrat Forge, sans hiérarchie métier implicite.

## Filtre catégorie

all/runtime/controller/routing/template/database/configuration/http/unknown.
Égalité exacte, sans classification à partir du message ou du type d’exception.

## Tri temporel

Parseur pur datetime.fromisoformat ; seules les dates avec utcoffset non None
participent au tri. Les offsets sont pris en compte pour l’instant réel.
newest décroissant par défaut, oldest croissant. Tri stable : égalités et offsets
représentant le même instant conservent l’ordre physique relatif dans les deux sens.
Les chaînes originales sont affichées ; pas de conversion de présentation.

## Timestamps invalides

Dates non parsables ou sans timezone placées après les dates interprétables,
dans leur ordre physique, pour les deux directions. Aucun diagnostic Bridge ajouté,
aucun rejet de ligne et aucun repli lexicographique silencieux.

## Vue filtrée

DebugFilteredView gelée : events et issues en tuples, total_events original.
Les issues sont conservées intégralement et indépendamment des critères événement.
Le résultat d’entrée reste intact, avec ses identités d’événement et doublons d’id.
La fonction pure n’accède ni au filesystem, JSON, registre, contexte ou Request.
Coût : parcours de recherche puis tri O(n log n) des événements retenus.

## Intégration Web

Parsing puis unique appel du Tool, puis projection. Formulaire GET avec labels,
recherche maxlength issue de la constante, trois selects et Réinitialiser /debug.
Valeurs actives conservées. Compteur affiché/total et anomalies de lecture.
État explicite « Lecture partielle du journal. » si result.truncated.
Absence/vide conserve le message historique ; aucun résultat filtré utilise un
message distinct. Les anomalies restent visibles même lorsque la liste est vide.

Colonnes Date/Niveau/Catégorie/Type/Route/Message. Route préfère event.route puis
request.path, sinon tiret ; les chaînes vides utilisent le même repli. Messages
complets, niveaux textuels, styles existants réutilisés. Aucune modification CSS.
Chaque ligne expose data-event-id et data-event-line échappés. Les id peuvent être
dupliqués ; line_number distingue les occurrences de la lecture actuelle seulement.
Aucun lien de détail, script, route supplémentaire, SQL ou traceback affiché.

## Stateless

L’URL porte tous les critères. Aucun filtre dans contexte/session/cookie/stockage.
Chaque GET valide avec projet relit le journal ; retour /debug rétablit les défauts.
Les quatre Tools, Bridge JSONL, masquage et DebugCenterTool restent inchangés.
Route Explorer et Entity Explorer n’ont aucune modification fonctionnelle.

## Sécurité

Jinja échappe messages, routes, types, ids et query réaffichée. Fixtures hostiles
avec balises/guillemets/esperluette contrôlées par parsing HTML, aucun script injecté.
Le secret masqué par le Bridge ne peut pas produire une correspondance de recherche.
Le formulaire reflète la query saisie par l’utilisateur, sans révéler une valeur
brute extraite du journal. 200/400 no-store ; POST toujours 405.

## Non-écriture

Tests HTTP : comparaison des octets, tailles et mtime de tous les fichiers de la
fixture projet et de sa configuration avant/après GET filtré.
Scénario installé : mêmes snapshots autour de chaque GET valide ou invalide,
avec identité CurrentProjectContext.inspection inchangée. L’ajout volontaire entre
deux consultations est réalisé par le script de fixture uniquement.

## Fichiers créés

- forge_design/tools/debug_filters.py
- forge_design/web/debug_filters.py
- tests/test_debug_filters.py
- tests/test_web_debug_filters.py
- docs/rapports/FD-DEBUG-002.md

## Fichiers modifiés

- forge_design/web/debug.py : parsing avant Tool, projection et contexte template.
- forge_design/web/templates/debug.html : formulaire, compteur, route, attributs DOM.
- tests/test_web_debug.py : compteur historique actualisé.
- docs/tools/debug-center.md : contrat utilisateur, filtres et tri.
- docs/02-architecture.md : projection pure et flux exact.

Bridge, Tool, registre, contexte, serveur, limites, package-data, CSS et JS inchangés.

## Tests ajoutés

92 nouveaux cas : 70 unitaires et 22 HTTP.
Unitaires : défauts, normalisation, Unicode/bornes, valeurs invalides, matrice des
niveaux et catégories, dix champs de recherche, champs exclus, tri dans les deux
sens avec fuseaux/égalités/dates invalides ou naïves, stabilité, vide, immutabilité,
déterminisme, entrée inchangée, conservation intégrale des issues.
Pureté : blocage de open, os.open/stat/listdir/scandir, Path.open/read_text/read_bytes/
stat/iterdir, json.loads/load, ToolRegistry.get et read_debug_errors pendant projection.

HTTP : dix projections incluant combinaisons, vide, paramètres vides et retour sans
filtre ; onze queries invalides testées avec et sans projet, avant Tool ; scénario
DOM/XSS/troncature/relecture. Contrôles compteurs, lignes physiques, unique appel,
issues, no-store, valeurs actives, route de repli, formulaire GET, secret non retrouvé,
absence JS et POST refusé. Les suites historiques restent actives.

## Test réel

Copie temporaire du squelette Forge, événements construits avec ses helpers :
ERROR template, ERROR database, WARNING runtime, INFO http, CRITICAL configuration.
Timestamps volontairement désordonnés ; ligne 2 JSON invalide ; secret Authorization
synthétique. Aucun collecteur ni DB exécuté.

Wheel installée --no-deps --no-index --target, processus Python -I dont la provenance
serveur/module de filtres installés est vérifiée. Quatre Tools confirmés.

| GET | Lignes physiques affichées |
|---|---|
| /debug | 5, 3, 6, 1, 4 |
| ?level=ERROR | 3, 1 |
| ?category=template | 1 |
| ?q=users | 1 |
| ?level=ERROR&category=database&q=column | 3 |
| ?order=oldest | 4, 1, 6, 3, 5 |
| ?q=absent | aucune |

Chaque GET valide appelle une seule fois le Tool ; level=FATAL retourne 400 sans
appel. L’anomalie reste visible partout. Ajout externe d’un ERROR database plus
récent : combinaison → lignes 7,3 et compteur 2 sur 6 ; défaut → 7,5,3,6,1,4.
Aucun secret dans les rendus des scénarios ; no-store/navigation vérifiés.
/routes et /entities restent accessibles. Snapshots projet/XDG et contexte stables.
Serveur arrêté, thread terminé, socket fermé, port réutilisable.
Script et journal ignorés : tmp/verify_fd_debug_002.py et .log.

## Packaging

Wheel reconstruite : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `ae7eaec756df95f8d7f251397917b86135a46e34de6ce55e74210757e96a6bd7`.
Modules Bridge/Tool/filtres/Web, templates et assets inspectés : octets identiques
aux sources, aucun tests/ ou tmp/ distribué. Installation et scénario HTTP réussis.
Aucune nouvelle dépendance.

## Commandes exécutées et résultats

| Contrôle | Résultat |
|---|---|
| Git initial et huit commits | Baseline conforme |
| pytest -q --tb=short | 1098 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Installation temporaire et scénario HTTP | Succès |

Outils .venv ; suite HTTP et scénario installé hors sandbox pour les sockets locaux,
build isolé autorisé pour ses dépendances. Annotations de tests et style corrigés
avant validation finale. Journal : tmp/pytest_fd_debug_002.log. Diff et fichiers
nouveaux relus avant commit.

## Tests sautés

Aucun test pytest sauté. Scripts Node historiques vérifiés. Aucun navigateur ou
lecteur d’écran réel revendiqué ; contrôles HTTP et parsing DOM.

## Limites restantes

La liste trie seulement les premiers événements acquis sous les bornes du Bridge,
pas nécessairement les événements les plus récents du journal entier. Masquage et
lecture concurrente conservent leurs limites historiques. Timestamps sans timezone
non interprétés ; pas de conversion locale d’affichage. IDs potentiellement dupliqués,
numéros physiques sans stabilité entre réécritures. Aucun détail, pagination ou temps
réel. Recherche limitée aux champs documentés, sans SQL/traceback/query.

## État Git final

Un seul commit local sur main, rapport inclus, sans push conformément au ticket.
Message : `feat: ajouter la liste filtrable Debug Center (FD-DEBUG-002)`.
Le hash et l’état Git final sont communiqués dans la réponse de livraison.
