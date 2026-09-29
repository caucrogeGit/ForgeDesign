# Rapport — FD-DEBUG-005

## Ticket et objectif

Stabiliser Bridge JSONL, masquage, filtres, sélection, flux, layout et Web sans nouvelle
fonctionnalité. Corriger les bornes et contrats réellement incohérents, préserver les
APIs et vérifier la lecture seule sur une installation réelle.

## État Git initial

main propre et synchronisée avec origin/main à `74a952f` — FD-DEBUG-004.
État Git et dix derniers commits inspectés. Aucun AGENTS.md trouvé dans le dépôt.

## Baseline Forge vérifiée

`git -C ../Forge ls-remote origin refs/heads/main` confirme
`73a956e587e5f169c028415e0e540c149cbaff56`, identique au checkout local propre et à la
baseline précédemment examinée. Schéma runtime-errors-schema.md, runtime_errors.py,
runtime_error_logger.py et tests/test_runtime_errors_jsonl.py comparés au contrat
consommé : version 1.0, quatre niveaux, huit catégories, noms POST/headers seulement.
Même producteur que FD-DEBUG-001 ; aucune modification du dépôt Forge.

## APIs stabilisées

Signatures inchangées et verrouillées par tests : read_debug_errors(root),
redact_debug_text(value), filter_debug_events(result, filters),
find_debug_event(result, *, line_number, event_id), build_debug_flow(event),
layout_debug_flow(flow). Modèles publics gelés, champs et tuples inchangés.
Aucun état caché, cache, index persistant ou nouvelle donnée runtime.
Le helper Web debug_event_url peut désormais retourner None pour un ID non ouvrable,
afin que la liste ne produise pas de lien que son propre parser refuserait.

## Contrat niveaux/catégories

Duplication confirmée entre Bridge et projection. Nouveau module neutre
forge/debug_contract.py définissant DEBUG_SCHEMA_VERSION, DEBUG_LEVELS et
DEBUG_CATEGORIES. Bridge et filtres le consomment ; la projection conserve ses
symboles LEVELS/CATEGORIES en ajoutant all. Aucune dépendance inverse vers Web/Tools.

## Bridge JSONL

Parcours filesystem, ancrage, samestat, flux binaire et six codes historiques conservés.
Tests des lignes vides, UTF-8 invalide, JSON/structure invalide et drain : numéros
physiques maintenus. BOM spéciale uniquement au début ; BOM ultérieure donne une
anomalie JSON locale. NaN/Infinity/-Infinity et profondeur excessive sont contrôlés.
Les chaînes vides, contrôles ASCII/NUL et Unicode restent acceptés sous la borne
UTF-8 : aucune restriction supplémentaire faute de défaut de sécurité démontré.

## Bornes

| Limite | Valeur | Décision |
|---|---:|---|
| MAX_DEBUG_EVENTS | 2000 | Inchangée |
| MAX_DEBUG_LINE_BYTES | 64 Kio | Inchangée, terminateur inclus |
| MAX_DEBUG_SCAN_BYTES | 8 Mio | Inchangée |
| MAX_DEBUG_ISSUES | 2000 | Diagnostic final inclus |
| MAX_DEBUG_TRACEBACK_FRAMES | 256 | Nouvelle borne de collection |
| MAX_DEBUG_POST_KEYS | 256 | Nouvelle borne de collection |
| MAX_DEBUG_HEADERS | 128 | Nouvelle borne de collection |
| MAX_DEBUG_EVENT_ID_LENGTH | 256 caractères | Borne Web dédiée |

Risque de collections reproduit : 10000 noms vides occupent seulement 40000 octets
JSON, 800 frames minimales 34400 octets, donc passent sous 64 Kio tout en multipliant
les objets. Les nouveaux plafonds gardent des tailles adaptées à un détail synchrone.
Dépassement : ligne entière structure_invalid, lecture des suivantes poursuivie.
Pas de découpage silencieux ou traceback partielle. Le parseur décode toujours la
ligne bornée avant validation ; mémoire JSON temporaire et overhead Python subsistent.

Limites exactes événements/octets revues : sémantique conservatrice conservée,
truncated signifie « limite atteinte », pas « donnée omise prouvée ». À ce point
le lecteur n’a pas encore observé EOF ; aucun sondage supplémentaire hors budget
ni confiance dans une taille stat potentiellement concurrente. EOF observé avant
la borne reste non tronqué. Cette convention est documentée, tests historiques actifs.

## Diagnostics

Arrêt après MAX_DEBUG_ISSUES-1 diagnostics individuels pour réserver le dernier
emplacement à l’unique debug.analysis_truncated. Résultat toujours ≤2000 issues,
même si une erreur I/O survient pendant le drain après le dernier diagnostic.
Pas d’accumulation ultérieure. Les arrêts globaux bytes/events/issues marquent
truncated=True. Une collection rejetée est une ligne invalide, pas un événement
partiellement interprété ; elle ne déclenche pas à elle seule l’arrêt global.
Drain d’une ligne énorme sans newline : EOF et borne cumulée vérifiés séparément.

## Redaction

Deux contournements effectivement reproduits avant correction :
Authorization=Bearer synthetic-token laissait le token après Bearer ; une valeur
password citée non refermée restait intégralement visible. Le masquage header accepte
désormais : ou = et une clé citée ; les valeurs citées inachevées sont masquées
jusqu’à la fin physique de ligne. Multi-secrets, query, cookies, Unicode et
idempotence contrôlés, tokenizer failed conservé. Mécanisme défensif non exhaustif.

Politique structurante revue et conservée explicitement : schema_version, level,
category valides sont canoniques et inchangés ; timestamp ISO, environment et nom
d’exception usuels ne portent pas d’affectation sensible. Pour id et les autres
textes arbitraires, retirer le masquage exposerait potentiellement des secrets.
La collision token=secret-one/token=secret-two vers token=[masqué] est reproduite ;
le couple ligne + ID public distingue correctement les deux occurrences. Aucun
échec de sélection démontré avec ce contrat ; pas de nouvelle identité brute stockée.
La recherche ne retrouve pas le secret supprimé. Choix et limites documentés.

## Filtrage et tri

Algorithme inchangé : champs publics masqués seulement, égalités niveau/catégorie,
tri stable des dates zonées, invalides et naïves en fin. Tests supplémentaires Z,
offsets positifs/négatifs, microsecondes, années 1/9999 et offsets extrêmes, année
10000 invalide, même instant sous plusieurs offsets. Pas de comparaison naive/aware,
conversion UTC intermédiaire ou overflow reproduit. Issues indépendantes des filtres.

## Identité du détail

Correction de l’unité : 65536 octets de ligne JSONL ne constituent pas une bonne
borne de caractères URL. MAX_DEBUG_EVENT_ID_LENGTH=256, spécifique au Web ; pas de
regex arbitraire. Accents/emoji/réservés passent par urlencode sans normalisation.
Au pire, 256 emoji produisent 3072 caractères percent-encodés, plus préfixe court.
IDs vides ou trop longs conservés par le Bridge mais sans lien depuis la liste ;
paramètre correspondant refusé 400. L’API pure reste compatible avec leurs valeurs.
Identité volatile ligne + ID public, pas empreinte immuable de fichier ou contenu.

## Contrats HTTP

Projet disparu, non-dossier, non-résoluble ou non-Forge : 409 sur /debug et /debug/event,
au lieu de faux succès 200. Sans projet : liste de navigation 200, détail 409.
Paramètres invalides : 400 avant Tool ; occurrence absente après lecture valide : 404.
Les réponses contrôlées 200/400/404/409 sont no-store. Le contrôle de type du Tool
est conservé et renforcé sur la liste pour refuser également None.
Pas de nouvelle gestion 5xx : erreurs de programmation inattendues gérées par Forge,
sans garantie ajoutée de no-store pour ces erreurs hors contrat contrôlé.

Parsers liste/détail comparés : mêmes règles pour clés inconnues présentes,
répétitions non vides et élimination des valeurs vides par Request. Messages adaptés
à leur contexte ; pas de factorisation supplémentaire de ces quelques lignes.

## Flux graphique

Aucun changement requis. SQL complet et request.query restent hors modèle/SVG.
Model/Response conservés comme types réservés, explicitement non produits avec
DebugError v1.0. Aucun nœud inféré de catégorie, exception ou traceback.
Troncature à 24 caractères revue avec emoji/caractères combinés et très long label :
coordonnées finies et déterministes. Pas de moteur typographique introduit.

## SVG et XSS

Fixtures </text><script>, url(javascript:...), guillemet/foreignObject en contexte,
chemin et template. Valeurs textuelles échappées, aucun script/foreignObject réel,
style ou gestionnaire d’événement provenant des données. IDs DOM uniques, marker
et aria-labelledby fixes sans collision dans la page. Pas d’URL externe issue des
données. CSP script-src 'self' confirmée inchangée ; SVG statique sans dépendance JS.
Vérification HTTP/DOM, pas de revendication de test navigateur/lecteur d’écran réel.

## Performance

Revue des parcours : Bridge linéaire dans le budget lu ; filtres O(n log n) pour le
tri ; sélection O(n) ; flow au plus cinq étapes ; layout linéaire. Aucun index cache.
Mesure indicative depuis la wheel : lecture de 2000 événements en 0,0375 s ;
20 projections de 2000 événements avec sélection/flow/layout en 0,0604 s.
Mesures locales sans seuil de test ni promesse de latence universelle.

## Non-écriture

Snapshots projet/journal/XDG octets, tailles et mtime autour des GET liste, filtres,
détail et erreurs. Identité inspection du contexte inchangée dans le scénario installé.
Seul le script de fixture append/réécrit explicitement entre consultations.
Symlinks storage/logs/journal, FIFO/dossier et races journal/logs rejoués par les
tests historiques actifs ; aucune régression du confinement trouvée.

## Non-exécution

Fixtures app.py/config.py/controller levant immédiatement si exécutés ; liste,
filtres, détail et SVG continuent à fonctionner. Aucun import cible, commande Forge,
DB ou SQL exécuté. Helpers Forge utilisés uniquement par le script pour les fixtures.

## Compatibilité autres Tools

Registre exact de quatre Tools, ordre inspector/routes/entities/debug-center.
Tous les tests historiques restent actifs ; /routes et /entities consultés depuis
la wheel installée. Aucun cinquième Tool, nouvelle route ou fonctionnalité.

## Défauts concrets trouvés

| Défaut observé | Correction |
|---|---|
| Multiplication d’issues sur petites lignes invalides | Plafond total avec emplacement final réservé |
| Nombreuses collections sous 64 Kio | Limites internes, rejet de ligne sans découpage |
| Ensembles niveau/catégorie dupliqués | Module neutre unique |
| Authorization=Bearer et citation inachevée laissent le secret | Masquage défensif étendu |
| Borne ID Web en caractères empruntée à une borne d’octets | Limite dédiée et liens cohérents |
| Erreurs projet renvoyées sous 200 | 409 cohérent sur les deux pages |
| None retourné par le Tool accepté comme absence sur la liste | TypeError comme pour le détail |

Risques revus sans correction : masquage d’ID public (couple ligne/id correct),
dates extrêmes (pas de crash reproduit), fin exacte (convention conservatrice),
contrôles ASCII (aucune injection démontrée), SVG et confinement (tests conformes).
Pas de présentation de ces revues comme des bugs corrigés.

## Corrections apportées

Changements ciblés au contrat partagé, limites, validation des collections et issues,
regex de masquage, bornes et statuts Web. Algorithmes de tri/sélection/flow/layout,
modèles publics, routes, registre, CSS, JS et dépendances inchangés.

## Fichiers créés

- forge_design/forge/debug_contract.py
- tests/test_debug_center_stabilization.py
- docs/rapports/FD-DEBUG-005.md

## Fichiers modifiés

- forge_design/forge/debug_errors.py : contrat et plafonds.
- forge_design/forge/debug_redaction.py : formes sensibles corrigées.
- forge_design/limits.py : cinq nouvelles constantes.
- forge_design/tools/debug_filters.py : choix issus du contrat neutre.
- forge_design/web/debug.py : erreurs projet et type de retour.
- forge_design/web/debug_detail.py : ID Web et erreurs projet.
- forge_design/web/templates/debug.html : lien uniquement si ouvrable.
- tests/test_web_debug_detail.py : nouvelle limite et statut attendu.
- docs/tools/debug-center.md et docs/02-architecture.md : contrats stabilisés.

## Tests ajoutés

39 cas transversaux : signatures/contrat/registre/gel, plafond issues à plusieurs
volumes, limites exactes et surplus de chaque collection, texte vide/contrôles/Unicode,
NaN/Infinity/profondeur, numéros physiques/BOM/drain, sept formes de masquage,
collision d’IDs publics correctement distinguée, encodage d’IDs et dépassement,
dates extrêmes/volume/long labels, quatre erreurs projet et scénario HTTP hostile.
Tests historiques de bornes exactes events/bytes, symlinks/races et autres Tools
maintenus. Un test historique actualisé pour les nouveaux contrat ID et statut 409.

## Test réel

Copie temporaire Forge avec app/config/controller hostiles, événements complets,
ID Unicode dupliqué, timestamp invalide, ligne JSON cassée, request/location/traceback/
SQL/template/controller, secrets connus et balise hostile. Wheel installée dans un
dossier temporaire, provenance installée contrôlée dans un processus Python -I.

Liste, filtre ERROR, recherche sans résultat, liens détail des occurrences distinctes,
flow et sections vérifiés. Aucun secret/brut/HTML hostile interprété. Un seul Tool,
no-store et snapshots projet/XDG/contexte stables. Append visible puis réécriture
invalide l’ancien lien en 404. Journal à 2000 événements mesuré ; 2500 lignes invalides
produisent 1999 issues locales et une troncature, affichée dans liste et 404 détail.
Autres Tools accessibles. Serveur arrêté, thread terminé, port réutilisable.
Le POST refusé utilise le repli 405 historique du framework, journalisé sans échec.
Script/journal ignorés : tmp/verify_fd_debug_005.py et .log.

## Packaging

Wheel : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `b1db8e64e67f4432140002554ceae1e5720766074e0b798c8279e40c9a31ddf4`.
Nouveau contrat, limites, modules Bridge/Tools/Web/layout, templates, CSS et scripts
inspectés avec comparaison des octets source. Aucun tests/ ou tmp/ distribué ;
documentation non packagée par la configuration actuelle. Installation réelle
--no-deps --no-index --target, scénario Python -I réussi. Aucune dépendance ajoutée.

## Commandes exécutées et résultats

| Contrôle | Résultat |
|---|---|
| Git initial et dix commits | Baseline conforme |
| Forge ls-remote / HEAD / status | Même baseline, dépôt propre |
| Tests ciblés | 183 réussis |
| pytest -q --tb=short | 1210 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Installation réelle, scénario et mesures | Succès |
| mkdocs build --strict | Non applicable : aucune configuration MkDocs dans le dépôt |

Outils .venv ; tests HTTP et scénario hors sandbox pour les sockets locaux, build
isolé autorisé pour ses dépendances. Typage d’inspection des dataclasses ajusté avant
validation finale. Journaux : tmp/targeted_fd_debug_005.log et tmp/pytest_fd_debug_005.log.
Diff, nouveaux fichiers et documentation relus. Dépôt Forge inchangé à la fin.

## Tests sautés

Aucun test pytest sauté. Build MkDocs non applicable faute de configuration.
Pas de navigateur réel, lecteur d’écran ou benchmark à seuil rigide.

## Limites restantes

Premiers événements seulement, pas de tail ni temps réel. Truncated indique une
borne atteinte, sans preuve que des données suivent. Collections hors plafond
rejetées, mémoire de décodage JSON et overhead Python supplémentaires. Masquage
non exhaustif, parfois conservateur, IDs publics éventuellement identiques et
identité volatile ligne/id. ID trop long non ouvrable en détail. Dates non parsables
ou naïves après les valides. Contrôles Unicode pas normalisés typographiquement.
Model/Response non structurés, schéma conceptuel sans trace réelle ou navigation
source. Modifications concurrentes du journal toujours possibles.

## État Git final

Un seul commit local sur main, rapport inclus, sans push conformément au ticket.
Message : `refactor: stabiliser Debug Center (FD-DEBUG-005)`.
Hash et état Git final communiqués dans la réponse de livraison.
