# Template Viewer

Template Viewer liste uniquement les fichiers physiques de `mvc/views/` du
projet Forge ouvert. Il expose leur chemin relatif, taille en octets et date de
modification, puis leur contenu brut et une analyse structurelle légère en lecture
seule. Aucun import du projet, rendu, prévisualisation, édition ou génération
n'est effectué.
La coloration est reportée ; aucun JavaScript ni dépendance n'est ajouté.

## Utilisation

Ouvrir un projet puis choisir **Template Viewer**. `/templates` rescane à chaque
GET ; **Voir** ouvre `/templates/view?path=layouts%2Fbase.html`. Le détail relit le
fichier à chaque consultation, même s'il ne figurait pas dans un inventaire tronqué.
Les deux pages gardent la navigation active et `Cache-Control: no-store`.
POST est refusé (405). Sans projet, la liste affiche « Aucun projet ouvert. » et
ne lance aucun Tool ; le détail retourne 409.

Le tableau est trié lexicalement selon les chemins Unicode. Tous les suffixes
sont admis, y compris `.html`, `.xml`, `.jinja` et les noms sans extension. Un fichier
non UTF-8 ou trop gros peut figurer dans l'inventaire mais sa lecture est refusée.
Un `mvc/views/` absent est un inventaire normal vide avec `source_present=False` ;
un dossier vide donne `True`. Un dossier inaccessible produit un diagnostic.

Les dates sont affichées en UTC, à la seconde, sans servir d'identifiant. Les
attributs `data-size` et `data-modified-ns` conservent les valeurs brutes. Le détail
utilise taille et mtime du descripteur de sa lecture courante, jamais d'un ancien
inventaire. Une modification détectée pendant la lecture fait refuser celle-ci.

## API et responsabilités

- `read_templates(root: Path) -> TemplatesResult` valide le projet et inventorie.
- `TemplateViewerTool.run(project_root)` délègue directement à ce Bridge ; la
  liste Web appelle le Tool une fois. Aucun scan au démarrage du registre.
- `TemplateInfo(path, size, modified_ns)` utilise `st_size` et `st_mtime_ns`.
- `TemplateIssue(code, message, path=None)` décrit un refus local ou une troncature.
- `TemplatesResult(templates, issues, source_present, truncated)` utilise des tuples.
- `read_template_source(root, template_path) -> TemplateSource` retourne chemin,
  taille, mtime et texte. Les modèles sont des dataclasses gelées.

La lecture brute réutilise `source_parts` et `read_project_source_details`.
`read_project_source` conserve son API historique retournant une chaîne. Le Web
convertit seulement la date, encode les liens avec `urlencode` et échappe le texte
par Jinja dans `<pre><code>`. Même un `{% if` incomplet reste du texte lisible.

## Confinement et erreurs

Le scan ouvre les dossiers segment par segment avec `open_directory` et
`O_NOFOLLOW`. Fichiers cachés, dossiers cachés, symlinks, FIFO, sockets, devices et
noms sensibles de la politique source sont exclus. Aucun suffixe supplémentaire
n'est utilisé comme barrière de sécurité. Les fichiers ordinaires sont ouverts
sans lecture de contenu pour vérifier leur identité et obtenir leurs métadonnées
(`stat/open/fstat/samestat`). Les dossiers découverts sont aussi vérifiés à l'ouverture.

La source exige UTF-8, accepte le BOM initial et conserve les caractères/newlines.
Traversal, chemin absolu, segments vides/cachés, backslash, deux-points, NUL et noms
sensibles sont refusés. La longueur maximale du chemin **complet relatif**
`mvc/views/<path>` est 4096 caractères. `path` doit avoir une seule valeur non vide ;
les autres paramètres non vides sont refusés. Comme les autres parsers Web Forge,
`Request.params` élimine les valeurs vides : `path=&path=page` fournit une valeur,
`path=&path=` aucune, `path=page&path=page` est refusé. Pas de double décodage URL.

| Situation | Statut du détail |
|---|---:|
| Refus lexical / paramètre absent ou répété | 400 |
| Template absent | 404 |
| Projet disparu, invalide, non dossier ou non résoluble | 409 |
| Source liée, remplacée, inaccessible, trop grosse ou non UTF-8 | 409 |

L'inventaire garde les autres fichiers après un échec local
(`template.unreadable`). Aucune politique de `/source` n'est élargie et ses statuts
historiques ne changent pas. L'état du projet ouvert et la configuration XDG ne
sont pas modifiés par les GET ; aucun cache, fichier `.forge-design` ou stockage.

## Bornes et limites

| Constante | Valeur | Portée |
|---|---:|---|
| `MAX_TEMPLATE_FILES` | 512 | Fichiers retenus |
| `MAX_TEMPLATE_DIRECTORY_ENTRIES` | 4096 | Noms découverts au total, même exclus |
| `MAX_TEMPLATE_SCAN_DEPTH` | 32 | Sous-dossiers sous views (racine à zéro) |
| `MAX_SOURCE_BYTES` | 1 Mio | Octets ouverts en lecture brute |

Un surplus détecté donne `truncated=True` et une seule issue
`template.analysis_truncated`. Une limite exactement remplie sans surplus ne
tronque pas. Un dossier au-delà de la profondeur autorisée suffit à signaler une
troncature, même vide, car il n'est pas parcouru. La découverte consomme au plus
4097 noms, le dernier uniquement pour détecter le dépassement. Au-delà de 4096,
le sous-ensemble dépend de l'ordre du filesystem ; le résultat retenu reste trié.
Le plafond de fichiers porte sur les fichiers vérifiés conservés ; les essais
infructueux restent bornés par le budget de découverte.

Ce n'est pas un instantané atomique : un dossier déjà ouvert peut être renommé ou
son contenu changé. Le contrôle avant/après lecture détecte les changements de
size/mtime/ctime ordinaires, sans constituer un verrou filesystem. Les dates
sortant de la plage Web sont affichées « Date hors plage ». Le support POSIX des
descripteurs et `O_NOFOLLOW` est requis. L'accessibilité est vérifiée structurellement,
sans revendiquer un essai navigateur ou lecteur d'écran.

## Opt-ins

Les templates fournis exclusivement par les loaders d'opt-in ne sont pas inclus.
Aucun loader d'opt-in n'est instancié ou exécuté. Un template local surchargeant un
opt-in apparaît normalement parce qu'il existe dans `mvc/views/`, sans analyse de
cette relation. `mvc/templates/` n'est pas une source canonique Forge actuelle.


## Structure détectée (FD-TEMPLATE-002)

Le détail conserve la source intégrale et affiche en dessous une projection pure :
`TemplateSource.text → analyze_template_structure(source) → TemplateStructure`.
Une seule lecture de fichier par GET, puis analyse en mémoire. Aucun changement
au Tool d'inventaire, au registre de cinq Tools ou aux URLs.

`TemplateStructure` expose syntax, dependencies, blocks, html_elements, issues,
partial et truncated. Tous les modèles sont gelés et les collections sont des
tuples. Les numéros de ligne commencent à 1 ; la profondeur HTML commence à 0.

### Jinja

Le parser partagé avec Route Explorer est `Environment(loader=None).parse`.
Il ne compile ni ne rend le template, ne charge aucun opt-in et ne résout aucun
fichier. Les états sont `valid` (syntaxe analysable), `invalid` (ligne et message
borné à 240 caractères), `unreadable` (complexité dépassée). Il ne s'agit jamais
d'un verdict de validité du template ou du HTML.

Les références extends/include/import/from-import sont conservées par ligne et
ordre d'apparition. Les listes include entièrement littérales produisent une
référence par chemin ; liste vide ou mixte produit une seule référence dynamique,
comme Route Explorer. Variables et expressions ne sont pas évaluées. Un chemin
référencé absent reste une déclaration syntaxique, sans diagnostic de présence.
Les blocks imbriqués et doublons sont conservés ; macros et variables ne sont pas
inventoriées. Les balises écrites dans les macros peuvent apparaître dans le relevé
HTML, sans prédire où ni combien de fois la macro serait rendue.

### HTML léger

Un masque lexical remplace les zones `{{ ... }}`, `{% ... %}` et `{# ... #}` par
des espaces en conservant CR/LF et la longueur de la copie. Il reconnaît chaînes,
échappements et délimiteurs imbriqués ; les marqueurs raw/endraw sont masqués,
leur contenu reste littéral. Une zone Jinja non terminée masque le reste et donne
une analyse partielle. La source originale reste intacte.

HTMLParser relève seulement tag/line/depth. Il normalise les noms en minuscules,
ignore les attributs, commentaires et doctype. Les éléments vides HTML et les
balises XHTML autofermantes ne poussent pas durablement la pile. Une fermeture
correspondante dépile jusqu'à son ouverture ; une fermeture inconnue est ignorée.
Script et style sont des nœuds, leur contenu n'est pas analysé comme HTML.

Ce relevé tolérant n'est pas un DOM HTML5 et ne corrige pas les fermetures implicites.
Les branches Jinja sont simplement juxtaposées, sans logique métier ou simulation
du rendu. Les cas ambigus de mélange de langages peuvent donc donner une hiérarchie
approximative. La liste textuelle est indentée jusqu'à 32 niveaux pour borner sa
largeur, avec profondeur exacte toujours indiquée. Aucun arbre interactif, graphe,
pliage ou sélection. La navigation locale est décrite plus bas.

### Analyse partielle et bornes

| Constante | Valeur |
|---|---:|
| MAX_TEMPLATE_STRUCTURE_CHARS | 1 048 576 caractères Python |
| MAX_TEMPLATE_STRUCTURE_NODES | 4096 éléments HTML |
| MAX_TEMPLATE_REFERENCES | 512 références |
| MAX_TEMPLATE_BLOCKS | 512 blocks |
| MAX_TEMPLATE_JINJA_TOKENS | 32768 tokens lexicaux avant AST |

La source filesystem reste limitée à 1 Mio. L'API pure refuse également les chaînes
synthétiques dépassant 1 048 576 caractères. Le précontrôle lexical limite les
objets AST avant parsing ; il n'est pas un budget exact d'octets Python. Le lexer
et les valeurs textuelles restent proportionnels à la source. RecursionError et
les limites de conversion des littéraux numériques sont contrôlés dans le Viewer.

Une limite exactement remplie ne tronque pas ; le premier surplus interrompt
l'accumulation concernée et produit `template.structure_truncated`. Les autres
volets peuvent rester disponibles. Jinja invalide produit `template.syntax_invalid`
et un relevé HTML indépendant marqué `template.html_partial`. Un masque inachevé
ou une erreur HTML contrôlée marque également ce relevé partiel. `partial=True`
accompagne tout résultat incomplet. Les messages ne constituent pas une validation
HTML et aucun diagnostic de dépendance absente n'est produit.

Un fichier lisible avec Jinja invalide garde HTTP 200 et sa source brute visible.
Les valeurs de structure sont échappées dans l'UI. Aucun rendu, accès fichier
supplémentaire, écriture, cache, loader ou JavaScript n'est ajouté.

## Vue arbre (FD-TEMPLATE-003)

Depuis le fichier brut, **Voir l’arbre** ouvre `/templates/tree?path=...`.
**Voir le fichier brut** revient au même template et **Retour à Template Viewer**
revient à l'inventaire. La liste conserve son action Voir vers le brut. Les URLs
utilisent urlencode et le parser path commun ; aucune nouvelle politique de chemin.

La vue serveur distingue trois structures :

- **Dépendances Jinja** : déclarations en ordre source, type et ligne, puis chemin
  complet ou « Référence dynamique ». Depuis FD-TEMPLATE-004, les références
  statiques locales autorisées peuvent proposer Voir selon les états ci-dessous.
- **Blocks Jinja** : liste à un seul niveau, noms complets, lignes et doublons
  conservés. Aucune relation de parenté entre blocks ou avec les balises n'est
  déduite des seules lignes.
- **Structure HTML** : plusieurs racines possibles, hiérarchie reconstruite depuis
  l'ordre et depth des HtmlElement, sans relire le texte ni appliquer de règle HTML.

`build_template_tree(structure) -> TemplateTree` est une projection pure O(n).
TemplateTree conserve les tuples de références et blocks existants, des racines
TemplateHtmlNode(tag, line, children), partial et truncated. Tous les modèles sont
gelés et les enfants sont des tuples. Le modèle est construit de bas en haut sans
récursion. Une pile de profondeurs originales rattache un saut au parent disponible
le plus proche ; deux nœuds de même profondeur restent frères même après un saut.
Un premier nœud de profondeur positive devient une racine. Une profondeur négative
lève ValueError. Aucun faux nœud intermédiaire n'est fabriqué.

`flatten_template_tree(tree)` produit des TemplateTreeRow (tag, line, depth,
has_children, close_levels) par parcours itératif. Le template serveur émet ses
ul/li à partir des lignes et des nombres de fermetures, sans macro récursive ni
HTML assemblé depuis des valeurs source. La hiérarchie sémantique reste présente
sans CSS ; marges et bordures facilitent sa lecture, la zone HTML peut défiler.

La profondeur n'est pas plafonnée une seconde fois dans la projection : les bornes
restent celles de FD-TEMPLATE-002. Les arbres extrêmement profonds peuvent être
peu pratiques et soumis aux limites de correction/affichage propres au navigateur ;
le serveur ne dépend pas de la récursion pour les construire ou les émettre.
Tests serveur jusqu'à 4096 niveaux, projection synthétique jusqu'à 10000 niveaux.
Aucun essai navigateur réel ou lecteur d'écran n'est revendiqué.

Les états partial/truncated sont propagés tels quels et annoncés explicitement.
Jinja invalide garde HTTP 200 si la source est lisible ; l'arbre utilise les seules
informations disponibles. Les trois sections vides ont chacune un message explicite.
La page rappelle qu'il s'agit de structure source détectée, pas de DOM rendu/corrigé.

Une requête arbre effectue exactement une lecture de source, une analyse existante
et une projection. Pas de scan d'inventaire ou d'appel TemplateViewerTool.run, aucun
nouveau parsing. Métadonnées de la même source courante, sans cache. Les statuts
400/404/409, no-store et POST 405 sont ceux du détail brut. La navigation principale
reste Template Viewer et le registre conserve cinq Tools. Aucun rendu cible,
JavaScript, édition, résolution transitive, cycle ou écriture.


## Navigation locale des dépendances (FD-TEMPLATE-004)

La vue brute et l'arbre utilisent le même résultat `TemplateNavigation`, calculé
une fois par GET depuis `TemplateStructure.dependencies`. Aucun nouveau parsing.
Les références statiques extends/include/import/from-import peuvent proposer
**Voir**, avec un nom accessible précisant la cible, vers le fichier brut local.
Le fichier cible permet ensuite d'ouvrir son propre arbre. Le retour à l'arbre
précédent utilise le navigateur, sans paramètre return_to/next/from ni pile stockée.

| État | Texte affiché | Navigation |
|---|---|---|
| available | Local | Voir vers /templates/view |
| dynamic | Non résolue statiquement | Aucune |
| invalid-path | Chemin refusé | Aucune |
| missing | Non disponible dans mvc/views/ | Aucune |
| unreadable | Source locale inaccessible | Aucune |

`resolve_template_references(root, references)` prend la racine canonique courante
et les références déjà analysées. Le modèle gelé conserve reference, status et
un target_path seulement pour available ; le résultat est un tuple. Une référence
sans path est classée dynamic, même dans un modèle synthétique. Les rejets
lexicaux/dynamiques sont séparés du contrôle filesystem et n'ouvrent rien.

La politique commune template_source/source_parts refuse notamment traversal,
absolus, segments cachés, noms sensibles, backslash, deux-points et NUL, sans
normalisation permissive. L'inspection ouvre seulement mvc/views/<path> : ancrage
segment par segment, O_NOFOLLOW/O_NONBLOCK, fichier ordinaire, stat/fstat/samestat,
taille historique maximale de 1 Mio. `inspect_project_source` et la lecture brute
partagent la même primitive d'ouverture. Aucune lecture/décodage du contenu cible,
aucun parsing, loader ou recherche dans les opt-ins/packages.

available signifie ouverture locale permise au moment du contrôle. La syntaxe
Jinja n'est pas vérifiée : un template cassé reste navigable. L'UTF-8 n'est pas
prévalidé non plus ; un fichier non UTF-8 peut proposer Voir puis retourner 409
lors de sa lecture. Cette distinction permet de ne pas précharger les dépendances.
Un fichier trop gros, spécial, lié, remplacé ou inaccessible est unreadable.
Seul FileNotFoundError donne missing ; une absence locale ne prouve rien sur un
éventuel template fourni par un opt-in.

Les doublons gardent leurs occurrences/lignes. Un dictionnaire local à l'appel
évite les ouvertures répétées d'un même chemin ; aucun cache inter-requêtes. Au plus
512 références, limite déjà centralisée ; un appel synthétique dépassant ce contrat
lève ValueError avant I/O. Coût O(références) hors filesystem, sans transitivité.
Les listes include sont traitées selon le modèle existant ; une liste mixte reste
une référence dynamique, sans récupération de ses parties littérales.

L'état affiché est une observation du GET courant, pas une garantie persistante.
Ajout, suppression ou remplacement externe sont visibles au prochain GET. Un lien
peut devenir 404 si la cible disparaît avant le clic, ou 409 si elle devient liée
ou illisible. Aucune cohérence atomique entre toutes les cibles n'est revendiquée.
Les URL passent par template_url/urlencode, sans décodage manuel ni retour fourni
par le client. Espaces, accents, emoji, &, + et % sont conservés par ce parcours.

Une lecture/analyse de la source principale demeure, plus les inspections locales
directes. Aucun contenu cible dans la page appelante, aucun graphe/cycle Viewer,
Tool, route, JavaScript ou écriture supplémentaire. Le handler /source est inchangé.

## Contrats stabilisés (FD-TEMPLATE-005)

Les sept API publiques de lecture, analyse, arbre et navigation gardent leurs
signatures ; `reference_rejection(reference)` reste le contrôle lexical pur.
Les quatorze modèles restent gelés, avec collections en tuples, sans état caché.
La limite en caractères de l'analyse pure est distincte de `MAX_SOURCE_BYTES`,
qui compte les octets du fichier. `MAX_SYNTAX_MESSAGE_LENGTH` compte 240 caractères.
Les issues d'inventaire sont bornées par les 4096 entrées découvertes, plus les
éventuels diagnostics globaux ; aucune collecte illimitée séparée.

`partial` signifie résultat incomplet ou incertain ; il dérive des états de
l'analyse, indépendamment de la liste des issues. `truncated` signale une collecte
interrompue par une limite : volume configuré ou limite de ressources du parser
(récursion/conversion numérique Python). La syntaxe `unreadable` après interruption
Jinja s'accompagne de `template.html_partial` et `template.structure_truncated` ;
le refus initial de longueur donne seulement `template.structure_truncated`.
Une erreur syntaxique ou HTML contrôlée peut être partielle sans troncature.

Le masque garde les caractères CR/LF ; la copie transmise à HTMLParser normalise
CRLF et CR en LF pour partager les numéros de ligne Jinja. Les fermetures HTML
inconnues utilisent un index, sans parcourir la profondeur ; chaque ouverture
est empilée et dépilée au plus une fois. L'arbre et son rendu restent itératifs.
Une profondeur négative synthétique est une violation du contrat pur, impossible
avec le parser réel. Aucune égalité ou représentation récursive d'arbre profond
n'est utilisée dans le parcours Web.

Le cache de navigation représente un instantané logique du contrôle par chemin
pendant le GET, pas un instantané atomique du filesystem. Les occurrences restent
visibles. Les noms Unicode NFC/NFD restent distincts si le filesystem les distingue ;
aucune normalisation, aucun second décodage des séquences comme `%2e%2e`.

L'inventaire parcourt un nombre borné d'entrées et les trie : O(D log D) au pire,
et non O(D) strict. Masque et projection HTML évitent les recherches répétées dans
la pile ; arbre O(n), navigation O(références) hors coût filesystem. Le coût interne
du lexer/parser Jinja reste celui de cette dépendance, sous les bornes d'entrée.
