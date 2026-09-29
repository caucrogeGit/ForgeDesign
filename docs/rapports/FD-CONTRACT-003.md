# Rapport — FD-CONTRACT-003

## Ticket et objectif

Lire les contrats de vue d'un projet Forge : inventaire sécurisé de métadonnées,
lecture bornée d'un fichier, JSON strict, validation Pydantic et diagnostics.
Aucun écran, Tool, association automatique ou validation croisée métier.

## État Git initial

main synchronisée avec origin/main à `337b901`. État Git et dix derniers commits
inspectés. Modification utilisateur préexistante du rapport FD-CONTRACT-001.md
(« État Git initiala ») conservée sans modification et exclue du commit.
Aucun AGENTS.md trouvé. Baseline 1568 tests.

## Baseline Forge

Vérification distante en lecture seule : origin/main de ../Forge reste
`73a956e587e5f169c028415e0e540c149cbaff56`. Le renderer Jinja confirme mvc/views
comme racine projet prioritaire, avant les opt-ins. Dépôt Forge propre, aucun
fichier modifié, aucun checkout/fetch. Squelette copié pour le scénario installé.

## Source canonique

mvc/views/**/*.view.json uniquement, suffixe exact sensible à la casse.
Exclusion de .view.json seul par la politique des noms cachés ; .view.JSON,
.view.json.bak, .design.json et .json ordinaires ignorés. Aucun scan mvc/templates.
Le contrat reste associé déclarativement via template ; aucun .html voisin déduit.

## API d’inventaire

read_view_contracts(root: Path) retourne ViewContractsResult après résolution et
reconnaissance Forge. Collecte seulement path relatif à views, size et modified_ns,
sans lire ni parser le contenu. Tri lexical Unicode final ; contrats invalides,
non UTF-8 ou trop gros peuvent être inventoriés, leur détail les diagnostiquera.
source_present=False pour views absent, True dès que son entrée est observée,
même vide ou inaccessible. Parents inaccessibles : False avec diagnostic si
l'inspection ne peut atteindre views ; projet non reconnu : exception projet.

## API de lecture

read_view_contract(root, contract_path) lit un seul fichier, sans inventaire.
view_contract_source(reference) combine suffixe et politique template_source/source_parts.
Refus lexical : SourceReadError avant ouverture du projet. Racine invalide : exceptions
projet existantes. Fichier disparu : FileNotFoundError. Autres erreurs individuelles :
résultat avec issues, aucun ValidationError brut et aucun contrat partiel.

## Modèles de résultat

Quatre dataclasses frozen : ViewContractInfo, ViewContractIssue, ViewContractsResult,
ViewContractReadResult. Collections en tuples. Issue : code, message, path éventuel,
location tuple de str/int. Détail : path, size, modified_ns, contract optionnel, issues.
Choix explicite : size/modified_ns sont optionnels et valent None si aucune lecture
sûre n'a abouti, plutôt que de fabriquer zéro ou réutiliser un ancien inventaire.
Le ViewContract embarqué conserve son gel superficiel et ses dicts mutables du ticket 002.

## Confinement filesystem

Inventaire via open_directory, scandir sur descripteur, stat sans suivi, open avec
O_NOFOLLOW/O_NONBLOCK, fstat et samestat. Racine ouverte segment par segment ;
parents et fichiers liés jamais suivis. Fichiers spéciaux exclus ; les dossiers,
même nommés *.view.json, peuvent être parcourus mais ne sont pas des contrats.
Détail délégué à read_project_source_details, sans modifier source.py.
Politique lexicale unique : traversal, chemins absolus, noms cachés/sensibles,
backslash, deux-points, NUL et longueurs refusés selon source_parts.
foo.key.view.json reste autorisé par cette politique réelle (suffixe .json), tandis
que private.key/a.view.json est refusé. Aucune règle dupliquée ou élargie.

## Bornes

| Constante | Valeur |
|---|---:|
| MAX_VIEW_CONTRACT_FILES | 512 fichiers conservés |
| MAX_VIEW_CONTRACT_DIRECTORY_ENTRIES | 4096 noms globaux, exclus compris |
| MAX_VIEW_CONTRACT_SCAN_DEPTH | 32, views à zéro |
| MAX_VIEW_CONTRACT_ISSUES | 512 issues inventaire, marqueur compris |
| MAX_VIEW_CONTRACT_VALIDATION_ISSUES | 256 issues détail, marqueur compris |
| MAX_SOURCE_BYTES | 1 Mio, réutilisé pour la lecture |

Limites distinctes de Template Viewer. Exact-limit sans surplus ne tronque pas.
513e fichier : truncated et marqueur ; découverte : au plus 4097 noms, dernier
sentinelle. Un dossier au-delà de profondeur 32 n'est pas parcouru, même vide.
Le marqueur final remplace la dernière issue si nécessaire ; unique et terminal.
Au-delà du budget de découverte, sous-ensemble dépendant de l'ordre filesystem
avant tri, sans promesse de sélection globale lexicale.
Inventaire O(D log D), lecture O(taille), JSON/Pydantic linéaires attendus dans les
données. Les erreurs Pydantic sont construites avant réduction : la borne limite
l'exposition, pas tout le coût mémoire interne. MemoryError non intercepté.

## JSON strict

UTF-8 strict via lecteur commun, BOM initial accepté. Aucun auto-décodage UTF-16/32.
json.loads après lecture, parse_constant refuse NaN/Infinity/-Infinity.
Commentaires, virgules finales, JSON incomplet, entier de 10000 chiffres et profondeur
10000 diagnostiqués comme contract.json_invalid. ValueError (dont JSONDecodeError)
et RecursionError capturés ; aucune récupération permissive.
Une racine JSON liste/chaîne/nombre se parse puis donne une erreur de validation.

## Clés dupliquées

object_pairs_hook construit chaque objet en refusant une clé déjà rencontrée,
y compris context, fields, actions et objets action imbriqués. Diagnostic JSON,
jamais stratégie silencieuse de dernière valeur gagnante. Pas de contrat produit.

## Validation Pydantic

ViewContract.model_validate(data) après parsing réussi. Modèles inchangés, stricts,
propriétés inconnues et null explicite refusés. Aucun model_construct, correction
de method, ajout de context ou conversion csrf. Template/entity/actions restent
textuels et ne déclenchent aucun accès aux cibles ni appel à un autre explorateur.

## Diagnostics

Codes : contract.unreadable, contract.json_invalid, contract.validation_error et
contract.analysis_truncated. Messages courts contrôlés, sans données input ou
contexte Pydantic bruts. Les loc gardent les clés/indices et l'ordre Pydantic.
Plusieurs défauts indépendants donnent plusieurs issues sous la borne. La réduction
ajoute le marqueur final sans exposer de modèle partiellement valide.
Les échecs locaux d'inventaire gardent le path et la collecte des autres fichiers.

## Métadonnées

Inventaire : descripteur réellement ouvert, pas seulement le stat initial.
Détail : size et modified_ns de la lecture actuelle réussie, y compris si son JSON
ou modèle est invalide. Métadonnées absentes pour lecture refusée/UTF-8 invalide.
Aucun état global ni cache entre appels.

## Races filesystem

Tests de remplacement stat/open : fichier, sous-dossier et views ; samestat refuse
la nouvelle identité. Détail : remplacement du fichier entre stat/open, modification
de contenu de même taille pendant la lecture avec changement mtime, puis symlink
après une lecture/inventaire. Contrôles size/mtime/ctime/len du lecteur partagé.
Descripteurs fermés même après échecs, comparaison /proc/self/fd avant/après.
Pas de verrou ni d'instantané atomique ; un dossier déjà ouvert peut être renommé.

## Unicode

NFC é, NFD e + accent, emoji, ß, espaces, +, &, %, # et ? conservés dans les chemins.
NFC/NFD restent distincts sur le filesystem courant ; aucun trim/normalisation.
Les métadonnées et paths restent exacts ; politique de chemin commune inchangée.

## Non-exécution

Fixtures Forge avec app.py, config.py et controller levant à l'import ; inventaire
et lecture fonctionnent. Aucun import projet, rendu Jinja ou exécution de chaînes,
aucune commande Forge. Les actions et références ne sont pas interprétées.

## Non-écriture

Tests de snapshots octets/taille/mtime du projet et XDG ; scénario installé vérifie
ces snapshots autour de chaque appel, y compris les échecs. Identité de
CurrentProjectContext.inspection et racine inchangées après ouverture initiale.
Modifications de fixtures effectuées explicitement par le scénario entre appels,
jamais par le lecteur. Aucun fichier créé dans le dépôt Forge.

## Séparation inventaire / détail

Tests instrumentés : inventaire avec json.loads, model_validate et fdopen interdits ;
détail avec read_view_contracts et scandir interdits. Les deux parcours réussissent.
Reconnaissance projet commune, aucune analyse de contrat pendant la découverte.

## Compatibilité contrats 001/002

Schéma, modèles Pydantic, fixtures officielles et leurs tests inchangés.
Exports publics complétés avec les quatre résultats, deux lecteurs et la primitive
view_contract_source. Aucune nouvelle dépendance. Pydantic<3,>=2 reste runtime.

## Compatibilité Template Viewer

Inventaire générique inchangé, .view.json toujours visible. Vérification depuis la
wheel et suite historique active. Aucun filtrage, lien ou endpoint ajouté.
Registre toujours exactement cinq Tools.

## Compatibilité Source Viewer

source.py inchangé ; lecture installée de contacts-list.view.json par l'API source
historique égale au fichier brut. Suites Source et sécurité historiques actives.
Politique, taille, décodage et refus des fichiers spéciaux réutilisés directement.

## Fichiers créés

- forge_design/contracts/reader.py
- tests/test_view_contract_reader.py
- docs/rapports/FD-CONTRACT-003.md

## Fichiers modifiés

- forge_design/contracts/__init__.py : exports.
- forge_design/limits.py : bornes propres aux contrats.
- docs/contracts/view-contract.md : API lecteur et limites.
- docs/02-architecture.md : chaîne de lecture.

Le diff utilisateur préexistant du rapport 001 reste hors ticket et hors commit.
Aucun changement app, Tools, Web, scripts, modèles Pydantic ou schéma.

## Tests ajoutés

62 cas : racines/vide, inventaire/noms/tri/métadonnées, séparation des parcours,
fixtures officielles, BOM/taille exacte et dépassée, UTF-8 refusé, JSON invalides,
doublons à plusieurs niveaux, exceptions pathologiques, cas Pydantic représentatifs,
locations/ordre/bornes, chemins refusés, Unicode/refresh/suppression/non-écriture,
512 fichiers réels et 4096 noms, profondeur exacte/+1, avalanche d'issues,
symlinks mvc/views/parent/fichier, FIFO/socket/dossier, races et descripteurs.
Aucun seuil temporel rigide. Tous les tests historiques restent inchangés.

## Test réel

Wheel installée dans un répertoire temporaire, copie du squelette Forge et des deux
fixtures officielles sous mvc/views. Processus Python -I : provenance forge_design,
contracts et reader sous l'installation vérifiée, schéma identique.
Inventaire puis lectures minimal/contacts ; ajout JSON invalide, modèle invalide et
symlink ; modification puis relecture et suppression puis FileNotFoundError.
Inventaire actualisé, source brute et Template Viewer compatibles, cinq Tools.
Projet/XDG/contexte inchangés autour de chaque appel. Aucun serveur Web requis.
Script et journal ignorés : tmp/verify_fd_contract_003.py et .log.

## Packaging

Wheel : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `be914d184c658e961161bcaf22b73ec216e5919a2371b2ec4e82516a90bd4711`.
Models, reader, __init__, limits et schéma comparés aux octets sources ; aucun tests/
ou tmp/ distribué. METADATA conserve Requires-Dist pydantic<3,>=2.
Installation --no-deps --no-index --target et processus isolé réussis ; dépendances
fournies par .venv, déclaration vérifiée séparément, aucune nouvelle dépendance.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| git status ; git log --oneline --decorate -10 | Baseline conforme, diff utilisateur conservé |
| git -C ../Forge ls-remote origin refs/heads/main | Baseline distante identique |
| pytest ciblé schema/models/reader | 221 réussis |
| pytest -q --tb=short | 1630 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Inspection wheel, installation et scénario Python -I | Succès |

Outils .venv, Python 3.13.5. Premier test socket Unix refusé en sandbox ; tests ciblés
et suite complète réussis hors sandbox avec autorisation. Typage/format des nouveaux
tests corrigés avant contrôle final. Build isolé autorisé hors sandbox ; installation
et scénario sans réseau. Journal complet : tmp/pytest_fd_contract_003.log.
Diff du ticket et nouveaux fichiers relus ; modification utilisateur préservée.

## Tests sautés

Aucun pytest sauté. Node exécuté. MkDocs build --strict non applicable : aucune
configuration MkDocs. Aucun nouveau parcours Web ou navigateur à revendiquer.

## Limites restantes

Confinement POSIX sans instantané atomique. Un fichier peut changer après lecture,
un dossier ouvert être renommé. Au-delà de la découverte, sous-ensemble dépendant
du filesystem. Inventaire sans validation de contenu ; détail borné à 1 Mio mais
structures JSON/Pydantic et erreurs intermédiaires plus coûteuses en mémoire.
Diagnostics exposés bornés, MemoryError non intercepté. Aucun croisement template,
entités/routes, protection CSRF effective, génération, écriture ou interface.
Dicts du modèle Pydantic toujours mutables selon le contrat documenté du ticket 002.

## État Git final

Un seul commit local sur main, rapport inclus, aucun push.
Message : `feat: lire les contrats de vue (FD-CONTRACT-003)`.
Modification préexistante du rapport 001 conservée non commitée. Hash et état Git
après commit communiqués dans la réponse de livraison.
