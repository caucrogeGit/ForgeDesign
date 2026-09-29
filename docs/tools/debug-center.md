# Debug Center

`GET /debug` présente les erreurs runtime du projet ouvert : date, niveau,
catégorie Forge, type et message. Sans projet, aucun Tool n’est exécuté.
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
s’ajoute aux octets JSON ; les lignes invalides peuvent produire de nombreux diagnostics.

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
Authorization: Bearer et les headers Cookie/Set-Cookie sont masqués jusqu’à la fin
de ligne ; une query masque les paramètres sensibles et conserve les autres.
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

La page utilise uniquement le modèle masqué, échappé par Jinja. Elle n’affiche ni
JSON brut, requête, SQL, traceback, détail, filtre, ni tri utilisateur. Aucun JS,
polling, surveillance filesystem, SSE ou WebSocket. Une modification externe est
visible lors du prochain GET, dans les bornes ci-dessus.
