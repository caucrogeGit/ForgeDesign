# Debug Center

`GET /debug` présente les erreurs runtime du projet ouvert : date, niveau,
catégorie Forge, type, route et message. Sans projet, aucun Tool n’est exécuté.
Chaque consultation appelle une fois `debug-center`, sans cache (`no-store`).

## Source et contrat

Le seul fichier lu est `storage/logs/errors.dev.jsonl`, relatif à la racine Forge
validée. Le Markdown dérivé n’est jamais lu. Aucun dossier ni fichier n’est créé,
aucune application cible exécutée. Un journal absent ou vide est un état normal :
« Aucune erreur runtime enregistrée. »

Le Bridge `read_debug_errors(root)` retourne un `DebugErrorsResult` gelé : tuples
`events` et `issues`, `source_present`, `truncated`. Les événements `DebugError`
conservent les neuf champs obligatoires du schéma Forge 1.0 et leur numéro physique
`line_number`. Les niveaux ERROR/WARNING/INFO/CRITICAL et les catégories
runtime/controller/routing/template/database/configuration/http/unknown restent
ceux du producteur. Le timestamp reste une chaîne ; aucun reclassement ni tri.
Les doublons d’identifiant restent présents.

Les structures optionnelles request, location et traceback sont typées et gelées ;
les collections deviennent des tuples. Request contient method/path/query et les
seuls noms post_keys/headers. Les dictionnaires de valeurs POST ou headers sont
refusés. Les frames conservent file/line/function, sans ouvrir ces fichiers.
Hint, route, controller, template, sql et correlation_id sont conservés si présents.
Un champ connu mal typé invalide toute la ligne ; les propriétés inconnues sont
ignorées. Les champs obligatoires manquants ne reçoivent pas de valeur inventée.

## Lecture et limites

| Borne | Valeur | Raison |
|---|---:|---|
| MAX_DEBUG_EVENTS | 2000 | Tableau synchrone de taille bornée |
| MAX_DEBUG_LINE_BYTES | 64 Kio | Événement avec traceback, sans accumulation illimitée |
| MAX_DEBUG_SCAN_BYTES | 8 Mio | Arrêt même avec uniquement des lignes invalides ou vides |
| MAX_DEBUG_ISSUES | 2000 | Plafond total, diagnostic final inclus |
| MAX_DEBUG_TRACEBACK_FRAMES | 256 | Pile structurée raisonnable par événement |
| MAX_DEBUG_POST_KEYS | 256 | Noms de formulaire par événement |
| MAX_DEBUG_HEADERS | 128 | Noms d’en-têtes par événement |

La lecture binaire commence au début, dans l’ordre physique. La taille d’une ligne
inclut son éventuel terminateur et le BOM initial. Les lignes vides sont ignorées,
mais comptent dans le budget et les numéros physiques. UTF-8 est requis ; le BOM
initial et une dernière ligne sans saut final sont acceptés. Une ligne trop longue
est consommée par fragments bornés pour reprendre à la suivante.

Atteindre exactement le plafond d’événements ou d’octets suffit à signaler
`truncated=True` et `debug.analysis_truncated`, sans sonder au-delà pour savoir
si d’autres événements existent. Un fragment sans terminateur au plafond d’octets
n’est pas interprété : sa fin ne peut pas être établie dans ce budget.
Les premiers événements seulement sont donc disponibles pour un gros journal.
Le budget porte sur les octets consommés par le lecteur ; le flux utilise le petit
buffer binaire standard de Python. La mémoire des objets Python et diagnostics
s’ajoute aux octets JSON. Le lecteur s’arrête après 1999 diagnostics individuels,
réservant la dernière place de MAX_DEBUG_ISSUES à un unique analysis_truncated.
Le résultat ne dépasse donc jamais 2000 issues, diagnostic global compris.
Une collection interne trop grande invalide la ligne (structure_invalid), puis
la lecture continue : aucun événement partiel n’est fabriqué, truncated reste
réservé aux arrêts globaux par borne. Le décodage JSON reste borné par 64 Kio.

Codes : `debug.unreadable`, `debug.line_too_long`, `debug.json_invalid`,
`debug.schema_version_unsupported`, `debug.structure_invalid`,
`debug.analysis_truncated`. Les diagnostics locaux portent leur ligne et ne
contiennent jamais le JSON brut. Les événements déjà acquis sont conservés lors
d’une erreur de lecture. Les lignes valides suivantes restent interprétées après
une erreur locale.

## Masquage et confinement

`redact_debug_text` masque les affectations explicites password/passwd/pwd/secret,
token/access_token/refresh_token/api_key/apikey, authorization/cookie/set-cookie,
sans distinction de casse, avec `=` ou `:` et valeurs éventuellement citées.
Authorization avec : ou = (y compris Bearer) et les headers Cookie/Set-Cookie sont masqués jusqu’à la fin
de ligne ; les valeurs citées inachevées sont également masquées jusqu’à la fin
physique de ligne. Une query ordinaire masque les paramètres sensibles et conserve
les autres ; la forme header peut masquer conservativement tout le reste.
Le SQL reçoit ce masquage textuel, sans analyse SQL. Aucun double brut des textes
masqués n’est conservé dans le modèle public. Les chemins et fonctions des frames
restent des textes bornés sans masquage générique.

Ce mécanisme ne détecte pas tous les secrets : valeurs isolées, encodées ou formes
non reconnues peuvent subsister. Les en-têtes textuels peuvent être masqués plus
largement que leur seule valeur. `safe_for_display=False` concerne le visiteur de
l’application Forge ; il ne supprime pas le message dans cet outil développeur
local, où le masquage reste systématique.

Le parcours est ancré par descripteurs, sans suivre les liens. storage, logs et
le journal doivent être des dossiers/fichier ordinaires, avec comparaison d’identité
stat/fstat après ouverture. Les FIFO, sockets, devices et symlinks sont refusés.
Aucun instantané global n’est garanti : un fichier ouvert peut encore être modifié
par un autre processus. `/source` n’autorise pas le journal.

La page utilise uniquement le modèle masqué, échappé par Jinja. Elle n’affiche pas
le JSONL original brut. Le détail explicite les propriétés du modèle masqué. Aucun
polling, surveillance filesystem, SSE ou WebSocket ; le seul JavaScript est le client
du Graphic Core du flux runtime (FD-GRAPHICS-008), sans requête réseau. Une modification externe est
visible lors du prochain GET, dans les bornes ci-dessus.


## Liste filtrable (FD-DEBUG-002)

Le formulaire GET conserve les valeurs actives et propose Réinitialiser vers
`/debug`. L’URL est le seul état : aucune session, cookie, persistance dans le
contexte ou stockage navigateur. Chaque GET valide avec projet relit le journal
par un seul appel Tool ; une query invalide retourne 400 avant cet appel.
Les réponses 200 et 400 conservent no-store. POST reste refusé.

| Paramètre | Valeurs | Défaut |
|---|---|---|
| q | Sous-chaîne simple, 256 caractères maximum | Absente |
| level | all, ERROR, WARNING, INFO, CRITICAL | all |
| category | all et les huit catégories Forge ci-dessus | all |
| order | newest, oldest | newest |

Les filtres actifs sont combinés par AND. Niveau et catégorie utilisent l’égalité
exacte, sans hiérarchie implicite entre ERROR et CRITICAL. Clés inconnues présentes,
valeurs invalides et répétitions non vides retournent 400. Comme Entity Explorer,
le parsing Forge élimine les valeurs vides : `q=&q=users` équivaut à `q=users`,
`q=&q=` équivaut à l’absence. Une clé inconnue avec seulement une valeur vide est
également éliminée avant validation ; aucune modification du parseur Forge.

La recherche applique strip puis casefold. La limite est vérifiée avant et après
normalisation (128 ß deviennent 256 caractères ; 129 sont refusés). Elle examine
uniquement les textes déjà masqués : id, exception_type, message, route, controller,
template, request.method, request.path, hint et correlation_id. Elle ne recherche
ni niveau/catégorie, ni SQL, traceback, request.query, headers ou post_keys.
Aucune regex utilisateur, nouvelle lecture ou restauration des secrets masqués.

Le tri est une projection pure, indépendante du Bridge et du Tool. Les timestamps
sont interprétés par datetime.fromisoformat ; seules les dates munies d’un fuseau
sont comparées. Les offsets sont pris en compte pour comparer les instants réels.
newest trie du plus récent au plus ancien ; oldest fait l’inverse. Les égalités
conservent l’ordre physique dans les deux sens. Les dates invalides ou sans fuseau
viennent ensuite dans leur ordre physique, sans nouvelle anomalie Bridge.
Les chaînes originales restent affichées, sans conversion de présentation.

Le compteur indique les événements affichés sur le total acquis par le Bridge,
qui peut être partiel : « Lecture partielle du journal. » reste alors visible.
Les anomalies de lecture ne sont jamais filtrées. Aucun résultat avec un journal
contenant des événements affiche « Aucun événement ne correspond aux filtres. ».
Un journal absent ou vide conserve « Aucune erreur runtime enregistrée. ».

La colonne Route préfère event.route, puis request.path, puis « — » lorsque le
texte est absent ou vide. Messages complets, niveaux textuels et labels explicites
réutilisent le style existant. Les lignes portent data-event-id et data-event-line,
échappés par Jinja. L’id peut être dupliqué ; le numéro physique identifie seulement
une occurrence dans la lecture courante, sans promesse de stabilité après rotation
ou réécriture du journal. La colonne Détail donne accès à l’occurrence courante.


## Détail d’une occurrence (FD-DEBUG-003)

La colonne Détail propose « Voir », avec un libellé accessible comprenant le type
d’exception. L’URL `/debug/event?line=42&id=...` est construite par urlencode.
Le serveur relit le journal une seule fois via DebugCenterTool, puis sélectionne
l’égalité exacte de line_number **et** id dans le résultat. Aucun accès direct au
JSONL, lecture hors borne, cache ou nouveau Tool. Les doublons d’id sont conservés
et ouvrables distinctement par leur numéro de ligne.

Le détail présente résumé (identité, niveau, catégorie, type, message, timestamp,
environment), requête HTTP (méthode/chemin/query masquée, noms POST et headers),
contexte Forge (route/contrôleur/template/correlation_id), localisation, traceback
dans l’ordre Forge, piste fournie par Forge et SQL masqué. Les absences sont
explicites ; aucun conseil n’est généré. safe_for_display est informatif et ne
masque pas le message développeur. Les propriétés sont rendues explicitement par
Jinja, sans repr/asdict/JSON original et sans second masquage dans le Web.
Les chemins restent textuels ; aucune nouvelle navigation source.

Les paramètres sont validés avant le Tool : line est décimal ASCII positif sur
au plus neuf chiffres, comme /source ; id est non vide, conservé exactement, au
plus MAX_DEBUG_EVENT_ID_LENGTH (256) caractères Unicode. Cette borne Web est
indépendante des octets du JSONL : au pire 3072 caractères percent-encodés pour
256 emoji, plus le petit préfixe et le numéro de ligne. Aucun format d’ID imposé.
Le Bridge conserve les IDs plus longs ; la liste n’offre pas de lien pour ceux-ci,
puisque le parser les refuserait. La limite n’est pas une promesse universelle
sur les restrictions des intermédiaires HTTP.
Un ID vide, accepté historiquement par le Bridge, reste visible dans la liste
mais n’a pas de lien de détail, puisque l’URL exige un ID non vide.

Clés inconnues présentes et répétitions non vides donnent 400. Les valeurs vides
sont éliminées par Request, comme pour la liste. Paramètres invalides : 400 sans
Tool ; paramètres valides sans projet : 409 ; couple absent après lecture : 404.
Les erreurs de racine/projet suivent la même politique sur liste et détail (message
d’erreur sous 409 sur les deux pages), sans être requalifiées en événement absent. Type de retour
Tool incorrect : erreur de programmation explicite. 200/400/404/409 sont no-store,
POST reste 405. Une lecture partielle est signalée même sur une 404 ; le détail
ne contourne jamais la fenêtre du Bridge pour chercher une ligne plus loin.

Le lien « Retour au Debug Center » revient à /debug, sans conserver les filtres
et sans return_to client. Aucun formulaire de filtre dans le détail.
L’URL est le seul état de sélection. Un append conserve normalement le couple ;
une rotation/réécriture peut rendre le lien obsolète et produire 404. Si le même
couple ligne/id est réutilisé, le détail montre les données de la lecture actuelle :
ce couple n’est pas un identifiant immuable de contenu ou de fichier.

## Flux runtime statique (FD-DEBUG-004)

Le détail affiche après le résumé un SVG des étapes structurées connues, dans
l’ordre conceptuel request → router → controller → sql → template. Les étapes
absentes sont sautées ; chaque étape présente est reliée à la suivante. Ce schéma
n’est pas une trace d’exécution ni une preuve d’appel entre ces composants.

Une request présente crée Requête, avec seulement méthode et chemin disponibles.
Une request vide reste un nœud Requête sans détail, sans inventer GET ou /.
Route, Contrôleur, SQL et Template exigent leur propriété textuelle renseignée ;
None et chaîne vide ne créent pas ces étapes. SQL indique seulement « Requête
disponible », jamais la requête intégrale, même dans le title. La query HTTP ne
figure pas dans le graphe. Model et Response ne sont pas créés : le contrat actuel
ne les décrit pas. Category, exception, hint, location et frames ne permettent
aucune inférence, même si une frame mentionne mvc/models.

Les rectangles 220 × 90 sont espacés de 80 pixels, dans un conteneur défilant.
Les détails visuels sont limités à 24 caractères avec ellipse ; les textes complets
restent dans les sections existantes et dans les title des nœuds hors SQL.
Le modèle logique et les données d’origine ne sont pas tronqués. Le SVG porte
role=img, titre et description référencés ; les types sont explicitement écrits.
Les flèches ont un marker local. Sans étape, aucun SVG : « Aucun flux structuré
disponible pour cet événement. »

Aucune interaction métier ni nouvelle lecture.

## Flux runtime sur le Graphic Core (FD-GRAPHICS-008)

Avec JavaScript, le même `DebugFlowLayout` est projeté par
`web/debug_flow_scene.build_debug_graphic_scene` en GraphicScene (identités
`debug-node-<type>`, arêtes `["debug-flow", source, cible]`, catégories génériques
1 à 5), transportée en JSON inerte et rendue par le Graphic Core via `/debug-flow.js`.
Le SVG serveur ci-dessus devient le repli statique sans JavaScript. Sélection d'une
étape (clic, Entrée, Espace, Échap) annoncée par un statut accessible, viewport,
niveaux de détail et minicarte du moteur ; aucun panneau, les sections de la page
détaillent l'événement. L'adaptateur ne reçoit que le layout, jamais le DebugError ;
la scène ne contient ni SQL, ni traceback, ni query, et le nom accessible est borné
à 256 caractères (valeurs complètes dans les sections). Le schéma reste un ordre
conceptuel des étapes connues, jamais une trace d'exécution.
La construction et le layout sont des fonctions pures déterministes depuis le
DebugError sélectionné. Les détails textuels restent tous accessibles ; les pages
400/404/409 ne construisent aucun graphe. Les limites du masquage du Bridge restent
applicables ; aucune valeur brute supplémentaire n’est récupérée.


## Contrats stabilisés (FD-DEBUG-005)

Les APIs read_debug_errors, redact_debug_text, filter_debug_events,
find_debug_event (line_number/event_id nommés), build_debug_flow et
layout_debug_flow conservent leurs signatures. Modèles gelés et tuples inchangés.
DEBUG_SCHEMA_VERSION, DEBUG_LEVELS et DEBUG_CATEGORIES sont définis dans le module
neutre forge/debug_contract.py ; la projection ajoute seulement le choix all.
Les six codes d’issue restent inchangés. Les types de flux model/response sont
réservés dans le modèle, jamais produits avec DebugError v1.0.

Le masquage des textes requis est conservé après revue : schema_version, level et
category canoniques sont inchangés ; timestamp ISO, environment et exception_type
canoniques ne contiennent pas d’affectation sensible. Les textes arbitraires dans
ces champs et id restent protégés. Deux IDs contenant des secrets différents
peuvent devenir identiques après masquage ; la sélection porte sur l’ID **public
masqué** et la ligne, ce qui conserve la distinction entre occurrences. Aucune
identité brute parallèle n’est stockée ou exposée. La recherche ne retrouve pas
les secrets retirés. Les dates arbitraires restent non interprétables pour le tri.

Chaînes vides, NUL et contrôles ASCII restent acceptés par le Bridge sous sa borne
UTF-8 : aucune nouvelle restriction arbitraire. Ces textes ne constituent pas du
HTML, et les liens sont encodés. Leur affichage peut varier selon le navigateur.
Le graphe n’effectue aucune interprétation d’URL ou de style depuis ces valeurs.

Sans projet, la liste reste une page de navigation 200 et le détail une ressource
nécessitant un projet (409). Un projet devenu invalide/disparu/non résoluble donne
409 sur les deux pages. Un couple absent après lecture valide donne 404. Erreurs
GET contrôlées 200/400/404/409 : no-store. Les erreurs de programmation inattendues
restent gérées par Forge, sans nouveau contrat 5xx spécifique au Debug Center.
