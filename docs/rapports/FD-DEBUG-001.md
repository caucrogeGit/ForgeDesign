# Rapport — FD-DEBUG-001

## Ticket et objectif

Créer un lecteur sécurisé et borné de errors.dev.jsonl, des événements typés et
masqués, des diagnostics de lecture et la première page serveur Debug Center.

## État Git initial

main propre et synchronisée avec origin/main à `ffad240` — FD-ENTITIES-008.
État Git et huit derniers commits inspectés. Aucun AGENTS.md dans le dépôt.

## Baseline Forge vérifiée

`git -C ../Forge ls-remote origin refs/heads/main` confirme
`73a956e587e5f169c028415e0e540c149cbaff56`, identique au HEAD local propre.
Documentation runtime-errors-schema.md, runtime_errors.py, runtime_error_logger.py
et tests/test_runtime_errors_jsonl.py examinés. Aucun changement du dépôt Forge.
Le producteur actuel masque toutes les valeurs de query dans safe_request_info ;
le lecteur conserve néanmoins sa propre protection contre un journal hostile.

## Source canonique

Uniquement `<root>/storage/logs/errors.dev.jsonl`. Racine résolue et détectée comme
projet Forge. Aucun Markdown, log console, chemin utilisateur ou création implicite.
Storage/logs/fichier absent donne un résultat vide, source_present=False.
Un fichier vide ouvert donne source_present=True sans anomalie.

## Schéma Forge v1.0

Neuf champs requis sans défaut inventé. Version inconnue signalée, propriétés
inconnues ignorées. Les quatre niveaux et huit catégories du contrat sont conservés,
sans reclassement. Un champ connu présent mal typé invalide la ligne entière.
Timestamp conservé comme chaîne, sans conversion de date.

## Modèle DebugError

Dataclass gelée, numéro physique line_number, structures optionnelles typées.
DebugErrorsResult contient tuples events/issues et booléens source_present/truncated.
Ordre physique et doublons d’id conservés. Aucune copie brute des messages masqués.

## Request

Method/path/query optionnels textuels, post_keys/headers convertis en tuples de
noms. Un dictionnaire de valeurs ne satisfait pas le schéma. Aucun POST reconstitué.
Query et textes des noms passent par le masquage défensif.

## Location et traceback

DebugLocation et DebugFrame gelés : file, entier line positif hors booléen, function.
Traceback en tuple. Aucun parsing de traceback textuelle ni ouverture des fichiers.
File/function restent inchangés, avec contrôle texte UTF-8 et longueur bornée.

## Diagnostics de lecture

Codes stables : debug.unreadable, debug.line_too_long, debug.json_invalid,
debug.schema_version_unsupported, debug.structure_invalid, debug.analysis_truncated.
Messages fixes sans contenu JSON brut ; numéros physiques pour les erreurs locales.
Les événements valides survivent aux lignes invalides et à une interruption OSError.

## Redaction

Fonction pure dédiée, indépendante du filesystem : affectations avec = ou :,
valeurs citées ou simples, casse ignorée. Familles password/passwd/pwd/secret,
token/access_token/refresh_token/api_key/apikey, authorization/cookie/set-cookie.
Authorization: Bearer et cookies masqués jusqu’à la fin de ligne ; query sélective.
Message/hint/sql/query et autres textes exposés sont masqués avant le modèle public.
Aucune analyse SQL. safe_for_display=False conserve le message développeur masqué.
Tokenizer failed reste intact. Aucune prétention de détection exhaustive.

## Bornes

MAX_DEBUG_EVENTS=2000, MAX_DEBUG_LINE_BYTES=64 Kio et MAX_DEBUG_SCAN_BYTES=8 Mio,
centralisés dans limits.py. Tableau synchrone borné, place pour les traces courantes,
budget total limitant aussi un fichier de lignes invalides ou vides.
Atteindre exactement événements/octets déclenche truncated et le diagnostic global.
La borne de ligne inclut terminateur et BOM éventuels. Une ligne trop longue est
signalée et drainée par fragments, puis la lecture reprend si le budget le permet.

## Lecture streaming

Lecture binaire readline avec taille maximale et budget restant explicites.
Pas de lecture intégrale. UTF-8, BOM initial accepté, blancs ignorés, dernière ligne
sans newline acceptée. Fragment sans terminateur au plafond global non interprété.
La documentation distingue octets consommés, buffer Python et mémoire des objets.

## Confinement filesystem

Primitive open_directory extraite à comportement inchangé depuis Entity Explorer
vers forge/filesystem.py et réutilisée. Parcours ancré de la racine par segments,
dir_fd/O_DIRECTORY/O_NOFOLLOW ; stat/fstat/samestat sur storage, logs et le journal.
Fichier régulier exigé, O_NONBLOCK à l’ouverture : FIFO/socket/device/dossier refusés.
Descripteurs fermés par context managers et ExitStack, y compris après erreur.
Tests de remplacement par un autre fichier ou dossier réel entre stat et open.

## DebugCenterTool

Tool gelé, id debug-center, nom Debug Center et description prescrite.
run(Path) délègue directement à read_debug_errors et retourne DebugErrorsResult.

## Intégration ToolRegistry

Quatre Tools explicites, dans l’ordre : project-inspector, route-explorer,
entity-explorer, debug-center. Aucun appel du lecteur à la création de l’application.
Tests de composition existants actualisés pour ce quatrième Tool seulement.

## Intégration Web minimale

GET /debug, un appel Tool avec projet, aucun sans projet. Tableau date/niveau/
catégorie/type/message, compteurs et anomalies de lecture. Navigation active après
Entity Explorer, aria-current, no-store et POST refusé. Absence normale expliquée.
Template packagé, échappement Jinja. Aucun détail, filtre, tri, JSON brut ou JS.

## Sécurité

Pas d’exécution projet, subprocess, eval/exec, DB ou génération dans le Bridge.
Fixtures projet contenant des instructions qui échoueraient si exécutées ; contrôle
AST de l’absence des primitives d’exécution dans le lecteur. /source refuse le log.
XSS échappée et secret synthétique absent du HTML, sans changement de CSP.

## Non-écriture

Tests octets/taille/mtime du journal avant/après lecture et HTTP. Scénario installé :
snapshot de tous les fichiers projet et configuration XDG autour de chaque GET ;
identité du contexte inspection inchangée. Seul le script de fixture ajoute
volontairement un événement entre les consultations. Dépôt Forge toujours propre.

## Fichiers créés

- forge_design/forge/debug_errors.py
- forge_design/forge/debug_redaction.py
- forge_design/forge/filesystem.py
- forge_design/tools/debug_center.py
- forge_design/web/debug.py
- forge_design/web/templates/debug.html
- tests/test_debug_errors.py
- tests/test_debug_center.py
- tests/test_web_debug.py
- docs/tools/debug-center.md
- docs/rapports/FD-DEBUG-001.md

## Fichiers modifiés

- forge_design/forge/entities.py : réutilisation de la primitive extraite.
- forge_design/limits.py : trois bornes.
- forge_design/app.py : quatrième Tool.
- forge_design/web/server.py : GET /debug.
- forge_design/web/templates/layout.html : navigation.
- pyproject.toml : template packagé.
- tests/test_app.py et tests/test_entity_explorer_stabilization.py : composition.
- docs/02-architecture.md : nouvelle verticale.

## Tests ajoutés

129 cas : 127 Bridge/redaction, un Tool, un parcours HTTP couvrant plusieurs états.
Familles sensibles et valeurs citées, false positive, toutes combinaisons niveaux/
catégories, chaque champ obligatoire absent ou mal typé, options invalides,
immutabilité imbriquée, doublons, BOM, EOF, UTF-8, lignes vides et continuation.
Bornes exactes/surplus, longue ligne drainée, millions de lignes vides bornées,
liens à chaque niveau, FIFO/dossier, races fichier/dossiers, interruption de lecture.
HTTP : absence projet/fichier, XSS, secret, événements/anomalies, unique appel,
relecture après ajout externe, no-store, navigation, POST et /source refusés.
Les suites Entity Explorer, Route Explorer et source restent actives.

## Test réel

Copie temporaire du squelette Forge. Helpers build_error_event/serialize_event du
checkout utilisés uniquement pour fabriquer runtime/template/database. Aucun appel
au collecteur ni DB. Secret Authorization: Bearer very-secret et JSON cassé insérés.
Wheel installée --no-deps --no-index --target ; processus Python -I, origine du
serveur et Bridge installés vérifiée, quatre Tools confirmés.

GET /debug affiche trois événements et une anomalie ligne 2, niveaux/catégories,
message masqué, navigation active, no-store. Ajout externe d’un quatrième événement,
visible au GET suivant. /routes et /entities restent accessibles ; /source refuse
le journal. Contexte et snapshots inchangés autour de chaque consultation.
Serveur arrêté, thread terminé, socket fermé et port réutilisable.
Script et journal ignorés : tmp/verify_fd_debug_001.py et .log.

## Packaging

Wheel : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `e2173099f33c8f440fae58fddc37d0c13510105ff79f13aa41038384d8fcf339`.
Nouveaux modules, templates, CSS et scripts inspectés avec comparaison aux sources.
Aucun tests/ ou tmp/ distribué. Installation réelle et HTTP réussis.
Aucune dépendance nouvelle.

## Commandes exécutées et résultats

| Contrôle | Résultat |
|---|---|
| Git initial et huit commits | Baseline conforme |
| Forge ls-remote et HEAD/status | Même baseline, propre |
| pytest -q --tb=short | 1006 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Installation temporaire et scénario HTTP | Succès |

Outils .venv, Python 3.13.5. Suite HTTP et scénario installé exécutés hors sandbox
pour les sockets locaux ; build isolé autorisé pour les dépendances de build.
Une annotation de fixture paramétrée signalée par pyright a été corrigée.
Journal final : tmp/pytest_fd_debug_001.log. Diff et nouveaux fichiers relus.

## Tests sautés

Aucun test pytest sauté. Scripts historiques Node vérifiés. Pas de navigateur ou
lecteur d’écran réel revendiqué ; page serveur contrôlée par HTTP.

## Limites restantes

Masquage de formes explicites seulement : secrets isolés/encodés non garantis,
masquage parfois plus large pour les headers. Lecture des premiers événements,
sans tail, instantané atomique, filtre ou temps réel. Un fichier ouvert peut être
modifié concurremment. Diagnostics eux-mêmes limités par le budget d’octets, sans
plafond de nombre dédié : leur mémoire Python peut dépasser nettement le JSON lu.
Dates et environment restent des chaînes sans validation métier supplémentaire.
Les chemins des traces ne sont ni ouverts ni navigables dans ce ticket.

## État Git final

Un seul commit local sur main, rapport inclus, sans push conformément au ticket.
Message : `feat: ajouter le lecteur Debug Center (FD-DEBUG-001)`.
Hash et état Git après commit communiqués dans la réponse de livraison.
