# Debug Center

`GET /debug` présente les erreurs runtime du projet ouvert : date, niveau,
catégorie Forge, type, route et message. Sans projet, aucun Tool n’est exécuté.
Chaque consultation appelle une fois `debug-center`, sans cache (`no-store`).

## Organisation de la page (FD-UX-007)

Les mêmes informations et les mêmes actions sont réorganisées :

- sous le titre, des **compteurs** du journal : événements, erreurs et
  avertissements affichés, anomalies de lecture ;
- chaque **commande** Forge (`forge doctor`, `forge project:audit`,
  `forge project:check`) est une carte :
  - un en-tête donne le titre, la commande, son niveau de confiance
    (Configuration, Lecture seule, Exécute le projet) et le bouton de
    lancement ;
  - l'**avertissement** reste toujours visible avant le clic ;
  - la description et les limites (durée, taille des sorties) se déplient sous
    « À propos de cette commande » ;
  - l'état et les sorties suivent ;
- le **journal** forme sa propre section (filtres, compte, tableau), avec le
  niveau en pastille. Les anomalies de lecture suivent.

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

`redact_debug_text` masque les affectations dont le **dernier composant** de la
clé est password/passwd/pwd/secret/token/api_key/apikey/secret_key/private_key
(donc aussi `DB_PASSWORD`, `SERVICE_TOKEN`, `OPENAI_API_KEY`, `access_token`…),
ainsi que authorization/cookie/set-cookie, sans distinction de casse ASCII, avec
`=` ou `:` et valeurs éventuellement citées, et le mot de passe des URL
`schéma://utilisateur:mot-de-passe@hôte` (FD-DEBUG-006, détaillé plus bas).
Authorization, éventuellement préfixé (`Proxy-Authorization`, `HTTP_AUTHORIZATION`),
avec : ou = (y compris Bearer) et les headers Cookie/Set-Cookie sont masqués jusqu’à la fin
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

## Diagnostic Forge à la demande (FD-RUNTIME-001)

La page `/debug` propose, au-dessus du journal, une section « Diagnostic Forge ».
Elle lance la commande officielle `forge doctor` du projet ouvert, **uniquement**
sur un clic explicite. Forge Design ne réimplémente aucun contrôle et
n’interprète pas le texte produit. Le résultat se limite au code retour, à la
durée, à la sortie standard et à la sortie d’erreur.

### Action

| Requête | Effet |
|---|---|
| `GET /debug` (avec ou sans projet, filtres compris) | Ne lance jamais rien ; état « non exécuté » |
| `POST /debug/forge-diagnostic` | Lance le diagnostic une fois et rend la page avec le résultat (`no-store`) |
| `GET /debug/forge-diagnostic` | 405 : aucune route GET |

Le POST est une action locale (`is_local_action` : hôte `127.0.0.1`, `Origin`
exacte, `Sec-Fetch-Site`), sinon 403. Il exige un formulaire encodé, sinon 415.
Il n’accepte **aucun paramètre** (corps ou query non vides → 400) : ni commande,
ni chemin, ni exécutable, ni environnement, ni délai. Sans projet ouvert, la
réponse est 409 « Aucun projet sélectionné : diagnostic non lancé. ». Si la
racine n’est plus un projet Forge valide (supprimée, déplacée, marqueurs
absents), la réponse est 409 « Diagnostic non lancé : … ». Dans ces deux cas,
aucun processus n’est créé.

Le résultat appartient à la réponse du POST : il n’est ni stocké dans le
contexte, ni dans `.forge-design/`, ni en session. Le GET suivant revient à
« non exécuté ». Le journal des erreurs runtime reste une section distincte. Les
cinq Tools sont inchangés : le diagnostic n’est pas un Tool.

### Commande

```text
<racine>/.venv/bin/python -s -B -P -u -m forge doctor      cwd = racine Forge vérifiée
```

- **Interpréteur** : toujours `<racine>/.venv/bin/python`, déterminé par Forge
  Design (`forge/project_python.py`, partagé avec la preview réelle). Les
  dossiers `.venv` et `bin` ne doivent pas être des liens ; la cible doit être
  un fichier exécutable. Il n’y a ni recherche dans `PATH`, ni repli sur
  l’interpréteur de Forge Design, ni chemin reçu par HTTP. Absent ou
  inutilisable : « Interpréteur du projet introuvable ou inutilisable
  (.venv/bin/python) : diagnostic non lancé. ».
- **`-s`** : sans le site-packages de l’utilisateur.
- **`-B`** : aucun bytecode n’est écrit. Lancé sans cette option, le diagnostic
  crée `__pycache__/config.cpython-*.pyc` dans le projet (constaté).
- **`-P`** : `-m` n’insère pas le dossier courant en tête de `sys.path`. Sans
  cette option, un `forge.py` présent à la racine du projet s’exécuterait à la
  place du CLI officiel (constaté). Le diagnostic ajoute lui-même la racine au
  chargement de `config.py` : les imports locaux de la configuration
  fonctionnent comme en terminal.
- `subprocess.Popen` avec une liste d’arguments, `shell=False`, nouvelle
  session (`start_new_session=True`) et entrée standard fermée. Le code n’utilise
  ni shell, ni concaténation, ni `os.system`, ni `eval`, ni `exec`.

L’environnement est une liste blanche construite positivement : `PATH`, `HOME`,
`LANG`, `LC_ALL`, `LC_CTYPE`, `TZ` et `TMPDIR`, si présentes. Aucune autre
variable n’est transmise, en particulier ni `PYTHON*`, ni `VIRTUAL_ENV`, ni
jeton, ni mot de passe. `APP_ENV` n’est pas fixé : le diagnostic suit son
défaut (`dev`, donc `env/example` puis `env/dev`), comme en terminal.
L’environnement n’est jamais affiché.

### Ce que le diagnostic exécute (forge-mvc 1.0.0rc9)

`forge doctor` lance seize contrôles et imprime une ligne `[OK]`, `[WARN]`,
`[FAIL]` ou `[SKIP]` par contrôle. Il :

- **exécute `config.py`** du projet, donc le code qu’il importe, et charge
  `env/` ;
- importe le module d’entités de Forge (`forge_mvc_entities`) pour valider
  `mvc/entities` ;
- **ouvre une connexion à la base configurée** via le backend installé. SQLite
  ne crée pas de base absente : le contrôle rapporte un avertissement ;
- cherche `npm` dans `PATH` ;
- lit la structure, les templates, les migrations, les modules et les
  certificats, et parcourt les sources `.py` en texte (indices MFA et RBAC)
  sans les importer.

Il n’importe ni `app.py` ni les contrôleurs, et ne démarre aucun serveur. Ce
n’est pas un bac à sable : la séparation tient à la frontière de processus.
L’avertissement de la page le dit avant le bouton.

### Bornes et arrêt

| Borne | Valeur | Effet |
|---|---:|---|
| `FORGE_DIAGNOSTIC_TIMEOUT_SECONDS` | 10 s | Au-delà : « Diagnostic interrompu : délai dépassé. » |
| `MAX_FORGE_DIAGNOSTIC_OUTPUT_BYTES` | 256 Kio par flux | Le surplus est lu et jeté, puis compté et signalé |

Les deux flux sont lus en continu par un sélecteur. Au-delà de la borne,
l’excédent est jeté sans arrêter la lecture : un tube plein ne bloque jamais
l’enfant. Dans tous les cas, y compris après une sortie normale, le **groupe
de processus entier** reçoit `SIGKILL`, puis le processus est attendu. Aucun
petit-enfant ne survit, même s’il garde les tubes ouverts.

### Codes retour et affichage

| Code | État affiché |
|---|---|
| 0 | Réussi (code 0) |
| 1 | Terminé avec le code 1 : au moins un contrôle en échec, ou erreur de la commande |
| autre | Terminé avec un autre code retour |
| — | Échec du lancement, ou délai dépassé |

Les sorties sont décodées en UTF-8 (octets invalides remplacés). Les séquences
ANSI (CSI, OSC bornée, échappements courts) sont retirées et les autres
contrôles remplacés par `�`. Le masquage textuel de Debug Center
(`redact_debug_text`) s’applique ensuite, car le diagnostic recopie les messages
d’exception des pilotes de base de données. Depuis FD-DEBUG-006, il reconnaît
aussi les clés suffixées (`DB_PASSWORD=`) et le mot de passe des URL de
connexion (`mysql://roger:[masqué]@db.local/app`), avec les limites décrites
plus bas. Le texte est rendu échappé par Jinja dans un `<pre>`, sans `| safe`.
Le formulaire n’a aucun champ et fonctionne sans JavaScript (POST natif).

## Audit Forge à la demande (FD-RUNTIME-002)

Sous le diagnostic, la section « Audit du projet Forge » lance la commande
officielle `forge project:audit`, elle aussi **uniquement** sur un clic explicite
(« Exécuter l’audit Forge »). Les deux commandes restent séparées : chacune a son
formulaire, son POST, son résultat et son message d’erreur, et aucune ne lance
l’autre ni n’affiche le résultat de l’autre. L’ordre de la page est : Diagnostic
Forge, Audit du projet Forge, Journal des erreurs runtime.

| Requête | Effet |
|---|---|
| `GET /debug` | Ne lance rien ; les deux sections sont « non exécutées » |
| `POST /debug/forge-audit` | Lance l’audit une fois ; résultat dans la seule section Audit |
| `GET /debug/forge-audit` | 405 |

Les gardes sont celles du diagnostic (403, 415, 400 pour tout champ ou paramètre,
409 sans projet ou hors projet Forge, sans aucun processus). Les messages sont
« Aucun projet sélectionné : audit non lancé. », « Audit non lancé : … » et
« Interpréteur du projet introuvable ou inutilisable (.venv/bin/python) : audit
non lancé. ». Rien n’est persisté.

### Commande et runner

```text
<racine>/.venv/bin/python -s -B -P -u -m forge project:audit      cwd = racine Forge vérifiée
```

Même interpréteur, mêmes options, même liste blanche d’environnement que le
diagnostic. `APP_ENV` n’est pas fixé : l’audit ne le lit pas. Les deux commandes
partagent un runner privé, `_run_forge_command`, qui reçoit un **nom** parmi une
liste fermée (`doctor`, `project:audit`, table immuable) et construit l’argv
depuis cette table ; tout autre nom lève une erreur avant lancement. L’API
publique se limite à `run_forge_diagnostic` et `run_forge_project_audit` ; il
n’existe aucune fonction « exécuter une commande Forge quelconque ». Le résultat
est le même `ForgeDiagnosticRun` ; délai (10 s), bornes (256 Kio par flux),
arrêt du groupe, nettoyage ANSI et masquage (FD-DEBUG-006) sont communs.

`-s` a un effet concret : dans un venv créé avec `--system-site-packages`, un
`.pth` du site utilisateur serait exécuté au démarrage ; il ne l’est pas.

### Ce que fait l’audit (forge-mvc 1.0.0rc9)

Vérifié par lecture du code et par audit hooks Python sur un projet réel :

- **lit** la structure, `env/example` puis `env/dev` (`dotenv_values`, pour
  vérifier quatre clés : seuls les **noms** des clés vides sont imprimés, jamais
  les valeurs ; `os.environ` reste inchangé), `relations.json` et les JSON
  d’entités, `mvc/routes/__init__.py` (analysé par `ast.parse`, jamais importé),
  les templates, `forge_modules.json`, les noms et tailles des migrations, le
  README et la liste de `tests/` ;
- **n’exécute** ni `config.py`, ni `app.py`, ni les contrôleurs, ni les tests :
  aucun code du projet n’est exécuté ;
- **ne contacte** aucune base, aucun réseau, ne lance aucun sous-processus et
  n’écrit aucun fichier.

Le CLI Forge et les paquets du `.venv` (forge-mvc, python-dotenv) s’exécutent :
ces garanties valent pour forge-mvc 1.0.0rc9, et l’avertissement de la page le
dit. Forge suit les liens symboliques du projet. Les noms de fichiers et de
dossiers du projet apparaissent dans la sortie : ils passent par le masquage.

| Code | État affiché |
|---|---|
| 0 | Terminé avec le code 0 : aucun constat FAIL (des avertissements restent possibles) |
| 1 | Terminé avec le code 1 : au moins un constat FAIL, ou erreur de la commande |
| autre | Terminé avec un autre code retour |
| — | Échec du lancement, ou « Audit interrompu : délai dépassé » |

Le texte (`[OK]`, `[WARN]`, `[FAIL]`, `[INFO]`, résumé) n’est jamais interprété.
`forge project:check`, qui importe réellement les routes du projet, n’est pas
proposé.

## Vérification Forge à la demande (FD-RUNTIME-003)

Sous l’audit, la section « Vérification du projet Forge » lance la commande
officielle `forge project:check` sur clic explicite (« Exécuter la vérification
Forge »). Contrairement à l’audit, **cette commande exécute du code du projet** :
l’avertissement est affiché avant le bouton, et le clic vaut action volontaire
(pas de confirmation JavaScript : la page fonctionne sans script).

### Trois niveaux de confiance

| Commande | Code projet exécuté | Services externes possibles | Niveau |
|---|---|---|---|
| `project:audit` | Non constaté | Non constaté | Analyse officielle essentiellement statique |
| `doctor` | `config.py` et ses imports | Base configurée possible | Diagnostic avec configuration exécutée |
| `project:check` | Routes, contrôleurs et imports transitifs | Tout effet produit par ce code est possible | Exécution applicative explicite |

Constats sur forge-mvc 1.0.0rc9 (lecture du code, audit hooks Python, sentinelles) :
`project:check` vérifie structure, configuration (`dotenv_values`, valeurs jamais
affichées), entités, templates, modules et migrations comme l’audit, mais pour
les routes il insère la racine en tête de `sys.path` et **importe réellement**
`mvc.routes`. Sur le squelette Forge, cela exécute `mvc/routes/__init__.py`,
`mvc/controllers/home_controller.py`, `optins/__init__.py` et
`optins/registry.py`. Un contrôleur que les routes n’importent pas n’est pas
exécuté ; `config.py` n’est pas chargé par la commande (le cœur ne l’importe
que pour créer l’application), mais le serait si le code importé l’importait.
La commande elle-même n’écrit rien (sans `-B`, les imports écriraient des
`__pycache__` dans `mvc/routes`, `mvc/controllers` et `optins`), ne lance aucun
processus et ne contacte aucun service : tout effet vient du code importé.

Lecture seule : Forge Design n’écrit aucun fichier. `project:check` peut exécuter
du code importé du projet ; ce code conserve les droits de l’utilisateur et peut
donc produire ses propres effets de bord (fichier écrit, processus lancé, service
contacté). Ce n’est pas une violation de la lecture seule de Forge Design : la
commande est explicitement demandée, et la page le dit avant le clic.

### Commande, frontière et arrêt

```text
<racine>/.venv/bin/python -s -B -P -u -m forge project:check      cwd = racine Forge vérifiée
```

Troisième et dernière entrée de la liste fermée du runner privé (`doctor`,
`project:audit`, `project:check`) ; API publique `run_forge_project_check`.
Même environnement en liste blanche, sans `APP_ENV` ; mêmes bornes (10 s,
256 Kio par flux), même nettoyage et même masquage : les secrets imprimés par le
code importé (`DB_PASSWORD=…`, `SERVICE_TOKEN=…`, URL de connexion) sont masqués.

Le runner arrête **le groupe de processus qu’il a lancé**, après une sortie
normale comme au délai : un enfant lancé par le code importé ne survit pas. Un
processus que le code projet détacherait volontairement dans une nouvelle
session sort de ce groupe (limite testée) : d’où la formulation exacte de
l’avertissement.

Comportements du code importé à connaître :

- `sys.exit(n)` dans les routes termine la commande avec ce code, **sans
  rapport** (`SystemExit` échappe aux contrôles de Forge) : « Terminé avec un
  autre code retour : le code importé du projet a pu terminer le processus » ;
- un thread non démon garde le processus vivant : la vérification est
  interrompue au délai ; grâce à `-u` (FD-RUNTIME-004), le rapport et tout ce
  qui a déjà été imprimé restent visibles (ils étaient perdus auparavant) ;
- tout ce que ce code imprime précède le rapport dans la sortie.

| Code | État affiché |
|---|---|
| 0 | Terminé avec le code 0 : aucun contrôle en échec (des avertissements restent possibles) |
| 1 | Terminé avec le code 1 : au moins un contrôle en échec, ou erreur de la commande |
| autre | Terminé avec un autre code retour : le code importé du projet a pu terminer le processus |
| — | Échec du lancement, ou « Vérification interrompue : délai dépassé » |

`POST /debug/forge-project-check` (même gardes 403/415/400/409, `no-store`,
aucun paramètre ; `GET` : 405). Résultat non persisté, aucun « dernier check ».
Aucune des trois commandes n’en déclenche une autre, et aucune n’est intégrée à
Project Inspector : une commande qui exécute du code ne doit jamais être
déclenchée indirectement par le cockpit.

## Sorties conservées avant un délai dépassé (FD-RUNTIME-004)

Les trois commandes sont lancées avec `-u`, placé **avant** `-m` (après, ce
serait un argument de Forge et non de Python) :

```text
<racine>/.venv/bin/python -s -B -P -u -m forge doctor | project:audit | project:check
```

Les sorties du processus Python principal sont ainsi non tamponnées : ce qu’il a
déjà écrit sur stdout ou stderr, y compris un fragment sans saut de ligne, est
dans le tube, lu en continu par le runner, et **reste disponible** si la commande
est ensuite interrompue au délai. Sans `-u`, un stdout tamponné jamais vidé était
perdu, et stderr (vidé par ligne) perdait sa dernière ligne incomplète.

Le pipeline ne change pas : octets lus → UTF-8 avec remplacement →
`clean_output` → masquage FD-DEBUG-006 → Jinja. Une valeur sensible émise avant
le délai est donc masquée comme les autres. Le runner, le délai (10 s), les
bornes (256 Kio par flux, surplus compté), l’arrêt du groupe, l’environnement
(`PYTHONUNBUFFERED` n’est ni utilisé ni transmis) et les messages sont
inchangés ; en exécution normale, les sorties des trois commandes sont
identiques à l’octet près avec et sans `-u`, au même coût.

Ce n’est **pas** du streaming : la page affiche toujours le résultat final d’un
POST synchrone, sans rafraîchissement ni polling. `-u` ne vaut que pour le
Python principal : un sous-processus lancé par le code du projet (par exemple
`python enfant.py`) garde sa propre mise en tampon, de même qu’une bibliothèque
native ; ce qu’il a écrit dans le tube avant l’arrêt du groupe est conservé. Un
processus détaché par le projet dans une nouvelle session reste hors de la
garantie d’arrêt (FD-RUNTIME-003). L’ordre entre stdout et stderr n’est pas
garanti (deux tubes) ; l’ordre au sein d’un flux est celui reçu.

## Masquage renforcé (FD-DEBUG-006)

Le masqueur reste une fonction pure `str → str`, déterministe et idempotente,
sans lecture de fichier, d’environnement ni de secret réel : il cherche des
**formes**, jamais des valeurs connues. Le marqueur reste `[masqué]`. Il protège
tous les textes du modèle public (id, message, hint, route, controller, template,
SQL, correlation_id, request.query, noms de post_keys et headers), donc la liste,
le détail, la recherche, les liens de détail et la synthèse de Project Inspector,
ainsi que la sortie du diagnostic Forge. Les frames et `location` (fichier,
fonction) restent hors masquage, comme avant.

Trois passes, dans cet ordre ; chacune ne fait que remplacer par le marqueur,
qui est ensuite traité comme une valeur atomique, si bien qu’aucune passe ne
réexpose ce qu’une autre a masqué :

1. **En-têtes** : `…authorization` (dernier composant : `Authorization`,
   `Proxy-Authorization`, `HTTP_AUTHORIZATION`, `X.Authorization`, mais pas
   `Authorization_Mode`) jusqu’à la fin de ligne ; `Cookie` et `Set-Cookie`
   selon la politique historique.
2. **Affectations** : la clé se termine par un composant sensible, précédé du
   début du texte ou d’un caractère non alphanumérique (`_`, `-`, `.` compris).

   | Masqué | Conservé |
   |---|---|
   | `DB_PASSWORD=`, `mysql-password=`, `app.secret=`, `--password=` | `password_policy=`, `DB_PASSWORD_EXTRA=` |
   | `API_TOKEN=`, `GITHUB_TOKEN=`, `access_token=`, `?service_token=` | `token_count=`, `tokenizer=`, `mytoken=` |
   | `SECRET_KEY=`, `JWT_SECRET=`, `client_secret=` | `secretary=` |
   | `OPENAI_API_KEY=`, `X-Api-Key:`, `JWT_PRIVATE_KEY=`, `app.private.key=` | `api_keys_count=`, `PRIVATE_KEY_PATH=`, `monkey=`, `key=` |

   Les mots-clés sont ASCII : `ſ`, `ı` ou le signe kelvin n’en tiennent pas lieu.
3. **URL** : `schéma://utilisateur:mot-de-passe@hôte` devient
   `schéma://utilisateur:[masqué]@hôte`. Schéma, utilisateur, hôte, port (IPv6
   compris), chemin et query sont conservés ; toutes les URL d’une ligne sont
   traitées ; un mot de passe encodé (`p%40ss`) est masqué sans décodage ; un
   `@` non encodé est masqué jusqu’au dernier `@` de l’autorité. Sans mot de
   passe (`user@host`, `user:@host`), rien n’est modifié. Le traitement est
   **syntaxique**, sans décodage ni réparation d’URL : `u:pa%2Fss@h` est
   masqué, mais `u:pa/ss@h` sort du contrat, puisque `/` termine l’autorité.

Les sauts de ligne (LF, CRLF, CR), l’Unicode des valeurs et la politique des
caractères de contrôle sont inchangés. La sortie grandit d’au plus la longueur du
marqueur par valeur remplacée : la croissance est proportionnelle au nombre de
secrets masqués, jamais incontrôlée.

Chaque passe n’est tentée que si son indice littéral figure dans le texte
(`authorization`/`cookie`, un fragment de mot-clé, `://`) ; le résultat est
identique, vérifié par un test d’équivalence. Toutes les expressions sont linéaires :
lookbehind de largeur fixe, aucun motif imbriqué non borné, un schéma d’URL ne
démarre qu’en début de mot. Sur 256 Kio, 1 ms pour un texte ordinaire et 30 ms
au pire pour un texte saturé de mots-clés.

Un ID d’événement qui contient une forme nouvellement reconnue change d’ID
public : un ancien lien `/debug/event?line=…&id=…` peut alors répondre 404, ce
qui est conforme au contrat (le couple désigne une occurrence de la lecture
courante). Un secret nouvellement masqué n’est plus retrouvable par la recherche.

Limites conservées : secret isolé sans nom de clé, clé métier inconnue, valeur
encodée arbitrairement (base64, chiffrée) sans contexte, valeur répartie sur
plusieurs lignes, caractère réservé non encodé dans un mot de passe d’URL,
frames et localisation. Ce n’est ni un détecteur de secrets ni un outil DLP.
