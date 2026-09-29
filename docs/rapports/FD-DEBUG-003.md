# Rapport — FD-DEBUG-003

## Ticket et objectif

Ouvrir une occurrence runtime depuis la liste Debug Center et afficher explicitement
ses propriétés publiques déjà masquées. Sélection par ligne physique et ID, sans
lecture JSONL indépendante, nouvelle navigation source, écriture ou temps réel.

## État Git initial

main propre et synchronisée avec origin/main à `07c6ee8` — FD-DEBUG-002.
État Git et huit derniers commits inspectés avant modification.
Contrats du Bridge, de la liste, du lecteur source et limites existantes examinés.

## Sélection événement

find_debug_event(result, *, line_number, event_id) parcourt uniquement les événements
acquis et retourne l’objet existant ou None. Coût O(n), aucun index ni copie persistée.
Fonction pure indépendante du filesystem, JSON, registre, Request et contexte.
Identité des objets, déterminisme et résultat inchangé vérifiés.

## Identité ligne + id

Comparaison exacte des deux propriétés, jamais par ID seul. Les doublons ouvrent
des occurrences distinctes. Ligne réutilisée avec un autre ID, couple croisé,
événement déplacé ou hors fenêtre du Bridge : 404 après lecture via Tool.
Si les deux valeurs sont réutilisées après réécriture, les données actuelles sont
affichées : le couple n’est pas un identifiant immuable de contenu.

## Parsing HTTP

GET /debug/event avec line/id seulement. Validation avant Tool. Line : ASCII,
décimal, positif, neuf caractères maximum, comme /source. ID non vide conservé
exactement, sans regex, strip ou casefold ; longueur maximale 65536 caractères
par réutilisation de MAX_DEBUG_LINE_BYTES, sans nouvelle constante.
Les limites d’URL du serveur/navigateur peuvent être plus basses après encodage.

Paramètres manquants/invalides, clés inconnues présentes et répétitions non vides :
400. Convention Request conservée : valeurs vides éliminées ; line=&line=1&id=&id=x
équivaut à line=1&id=x. Aucun projet avec paramètres valides : 409.
Un ID vide accepté historiquement par le Bridge reste affiché dans la liste sans
lien, puisque le contrat du détail exige un ID non vide.

## Résumé

Titre « Détail de l’erreur — Debug Center ». Niveau, catégorie, exception, message,
timestamp, ID, ligne et environment explicitement rendus. safe_for_display affiché
comme information Oui/Non avec explication du contrat Forge ; false ne cache rien
au développeur. Conteneur article avec data-event-id et data-event-line.

## Requête

Section Requête HTTP : méthode, chemin, query du modèle masqué et listes des seuls
noms POST/headers. Aucun objet privé ni reconstruction de valeurs. État explicite
si requête absente, tiret pour une valeur absente ou vide.

## Contexte Forge

Route, contrôleur, template et correlation_id, sans navigation ou déduction.
Valeurs absentes représentées par un tiret ; propriétés échappées par Jinja.

## Localisation

Fichier, ligne et fonction de DebugLocation en texte. État explicite en absence.
Aucune ouverture ou lien vers les fichiers cités, /source inchangé.

## Traceback

Tableau numéroté #/Fichier/Ligne/Fonction, strictement dans l’ordre fourni par Forge.
Aucune inversion ou interprétation de traceback textuelle. État explicite en absence.

## Hint

Section Piste Forge uniquement lorsque hint est présent. Texte public masqué,
sans conseil généré ou analyse d’exception supplémentaire.

## SQL

Section SQL uniquement lorsque sql est présent. pre/code échappé, style source-code
existant permettant le défilement. Aucun parseur SQL, accès DB ou exécution.

## Redaction

Le Web ne refait aucun masquage : Bridge → DebugError public → template explicite.
Aucune copie brute, asdict, repr, __dict__ ou vue JSON originale. Fixtures contenant
Authorization: Bearer super-secret et password=secret123 dans les textes concernés :
aucune de ces valeurs n’apparaît dans le HTML du détail.

## Intégration liste

Colonne Détail avec lien Voir et aria-label « Voir le détail de [type] ».
Helper debug_event_url utilisant urllib.parse.urlencode pour line/id ; guillemets,
espaces, accents et caractères réservés ne sont pas concaténés directement.
Filtres, compteur, tri et attributs DOM historiques conservés. Le test XSS de liste
compte désormais aussi le type échappé dans le libellé accessible du lien.

## Intégration Web

Route GET dédiée et template packagé. Un seul appel registry.get(debug-center).run
pour un détail syntaxiquement valide avec projet, y compris une 404 métier.
Aucun appel pour 400 ou absence de projet. Type incorrect : TypeError explicite.
Erreurs de racine/projet conservant la politique de liste : message sous 200,
jamais converties en événement absent. Les réponses 200/400/404/409 sont no-store.
POST refusé avec 405. Navigation globale Debug Center active, retour fixe /debug.

Lecture partielle signalée si result.truncated, même sur une 404. Pas de duplication
des anomalies globales ni dépassement de fenêtre pour retrouver l’événement.
Aucun filtre dans le détail, JavaScript, nouvelle entrée de navigation ou Tool.

## Stateless

URL seule source de sélection ; retour liste sans filtres ni return_to utilisateur.
Chaque GET relit via le Tool, sans cache DebugError. Append : ancien couple encore
accessible. Réécriture/déplacement : ancienne URL potentiellement 404, documenté.
Bridge, redaction, DebugCenterTool, filtres et registre restent inchangés.

## Sécurité

Jinja échappe ID, message, contexte, query/path, frames, hint et SQL. Fixtures hostiles
avec script/guillemets/esperluette, attributs DOM vérifiés par parsing HTML.
Sentinelle AST sur la route : absence d’import json/read_debug_errors/redact_debug_text
et d’appel direct open/asdict/repr. Sélection pure sous blocage filesystem/JSON/registre/
Bridge. Chemins uniquement textuels, pas d’élargissement /source ou CSP.

## Non-écriture

Tests HTTP : snapshots des octets, tailles et mtime du projet et configuration autour
des détails. Scénario installé : mêmes snapshots pour chaque GET 200/400/404/409,
avec identité CurrentProjectContext.inspection inchangée. Seul le script de fixture
ajoute puis réécrit volontairement le journal entre consultations.

## Fichiers créés

- forge_design/tools/debug_detail.py
- forge_design/web/debug_detail.py
- forge_design/web/templates/debug_detail.html
- tests/test_debug_detail.py
- tests/test_web_debug_detail.py
- docs/rapports/FD-DEBUG-003.md

## Fichiers modifiés

- forge_design/web/debug.py : helper de lien dans le contexte liste.
- forge_design/web/templates/debug.html : colonne et liens accessibles.
- forge_design/web/server.py : GET /debug/event.
- pyproject.toml : nouveau template distribué.
- tests/test_web_debug_filters.py : assertion XSS du nouveau libellé accessible.
- docs/tools/debug-center.md : détail et identité d’occurrence.
- docs/02-architecture.md : sélection pure et rendu explicite.

Aucune modification Bridge, redaction, Tool, filtre, registre, limites, CSS ou JS.

## Tests ajoutés

24 cas nouveaux : sept sélections pures et dix-sept tests du parsing/Web.
Sélection : première/dernière ligne, ID incorrect, mauvaise ligne, couples croisés,
doublons, vide, identité des objets, déterminisme et absence de mutation/I/O.
Treize queries invalides testées avant Tool avec et sans projet : valeurs manquantes,
vides, zéro/négatif, lettres, taille, signe, chiffres non ASCII, clé et répétitions.
Frontières du parseur : neuf chiffres, ID à 65536 et au-delà, ID conservé exactement,
valeurs vides répétées. Limites ID testées directement avec Request, sans dépendre
de la taille maximale d’une ligne de requête du serveur HTTP.

Parcours liste/détail : URLs encodées distinctes pour IDs égaux, compteurs inchangés,
unique appel Tool, absence projet, résumé true/false, requête et trace absentes,
append, réécriture, couple croisé, no-store/navigation/retour et POST 405.
Fixture complète hostile : toutes sections, masquage, échappement, absence de brut
et source, troncature et 404 hors fenêtre. Erreur projet et type incorrect testés.
Toutes les suites FD-DEBUG-001/002, Entity Explorer, Route Explorer et source actives.

## Test réel

Copie temporaire du squelette Forge ; helpers build_error_event/serialize_event
pour deux événements complets avec le même ID `same &/?+`. Request, location, deux
frames, hint, route, controller, template, sql et correlation_id présents. Secrets
volontaires dans message/hint/sql/query. Aucun collecteur, DB ou application cible.

Wheel installée --no-deps --no-index --target ; processus Python -I, provenance
installée du serveur et module détail vérifiée. Quatre Tools confirmés. GET liste,
extraction des deux liens puis navigation : événements distincts lignes 2 et 1,
toutes sections, ordre des frames, secret absent, pas de JSON original/source/JS.
Un seul appel Tool par détail ; aucun pour paramètre invalide ou absence projet.

Append d’un troisième événement : liste 3 sur 3, ancien détail encore 200 et nouveau
détail accessible. Réécriture : ancienne URL 404. 200/400/404/409 no-store ; POST 405.
Le framework journalise son repli 405 minimal faute de template d’erreur enregistré ;
le statut attendu est confirmé, sans modification de cette politique historique.
/routes et /entities toujours accessibles. Projet/XDG/contexte inchangés autour des
GET. Serveur arrêté, thread terminé, socket fermé et port réutilisable.
Script/journal ignorés : tmp/verify_fd_debug_003.py et .log.

## Packaging

Wheel : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `f93518fbd5414b03c41db7d3d4f999858ea68e925c0f2c30176172ab45e75961`.
Modules Bridge/Tool/filtres/détail/Web, templates et assets inspectés : octets
identiques aux sources, aucun tests/ ou tmp/ distribué. Installation réelle et
scénario HTTP réussis. Aucune dépendance ajoutée.

## Commandes exécutées et résultats

| Contrôle | Résultat |
|---|---|
| Git initial et huit commits | Baseline conforme |
| Tests ciblés détail | 24 réussis |
| pytest -q --tb=short | 1122 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Installation temporaire et scénario HTTP | Succès |

Outils .venv. Tests HTTP/scénario installé hors sandbox pour les sockets locaux ;
build isolé autorisé pour ses dépendances. Annotation des liens HTMLParser corrigée
avant validation finale. Journal complet : tmp/pytest_fd_debug_003.log.
Diff, nouveaux fichiers, documentation et rapport relus avant commit.

## Tests sautés

Aucun test pytest sauté. Node historique vérifié. Aucun navigateur réel ou lecteur
d’écran revendiqué ; contrôles HTTP et DOM par parsing HTML.

## Limites restantes

Identité ligne/id limitée à la lecture actuelle, sans empreinte de fichier/contenu.
ID vide non ouvrable ; IDs extrêmes soumis également aux limites d’URL HTTP.
Événement hors fenêtre : 404 sans contournement. Masquage non exhaustif et lecture
concurrente conservent les limites FD-DEBUG-001. Aucun détail JSON original,
navigation source, édition, pagination ou temps réel. Les erreurs projet suivent
encore le statut historique de la liste.

## État Git final

Un seul commit local sur main, rapport inclus, sans push conformément au ticket.
Message : `feat: ajouter le détail Debug Center (FD-DEBUG-003)`.
Le hash et l’état Git final sont communiqués dans la réponse de livraison.
