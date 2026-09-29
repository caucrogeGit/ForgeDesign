# Rapport — FD-TEMPLATE-001

## Ticket et objectif

Créer Template Viewer : inventaire des templates physiques locaux, métadonnées,
lecture brute sécurisée et deux pages Web. Aucun parsing/rendu Jinja, édition,
prévisualisation, génération, loader d'opt-in ou JavaScript.

## État Git initial

`main` propre et synchronisée avec `origin/main` à `6af6f44`, FD-DEBUG-005.
`git status` et les dix derniers commits inspectés avant modification.
Aucun AGENTS.md dans le dépôt.

## Baseline Forge vérifiée

`git -C ../Forge ls-remote origin refs/heads/main` donne
`73a956e587e5f169c028415e0e540c149cbaff56`, identique au HEAD local propre.
Lecture de `integrations/jinja2/renderer.py`, `integrations/jinja2/docs/renderer.md`
et inventaire de `skeleton/data/mvc/views/`. La recherche Forge utilise d'abord
le filesystem projet, puis les loaders enregistrés par les opt-ins.
Aucun fichier Forge modifié, aucun fetch ou checkout.

## Source canonique mvc/views

Seule racine : `<projet>/mvc/views/`. Validation par resolve_project_root et
detect_forge_project. Un dossier absent donne templates=(), source_present=False ;
un dossier vide donne True. Une source inaccessible ou liée produit une issue.
Aucune recherche dans mvc/templates, packages, opt-ins ou chemins arbitraires.

## Inventaire

Parcours de descripteurs de dossiers ancrés, noms triés à chaque niveau puis
résultat trié lexicalement par chemin Unicode. Fichiers ordinaires indépendamment
du suffixe : HTML, XML, Jinja, noms sans extension. Noms cachés/sensibles exclus par
la politique source commune ; symlinks et fichiers spéciaux jamais suivis.
Le scan ouvre les fichiers admissibles pour vérifier leur identité et leurs
métadonnées, sans lire leur contenu. Une erreur locale conserve les autres entrées.

## Modèle TemplateInfo

Dataclass gelée `TemplateInfo(path, size, modified_ns)`, path relatif à mvc/views.
`TemplateIssue(code, message, path=None)` et
`TemplatesResult(templates, issues, source_present, truncated)` gelés ; collections
en tuples. Codes template.unreadable et template.analysis_truncated uniquement.
`TemplateSource(path, size, modified_ns, text)` est également gelée.

## Métadonnées

st_size et st_mtime_ns issus de fstat du fichier ouvert/vérifié. La taille n'est
jamais calculée depuis la chaîne décodée. Conversion UTC à la seconde dans le Web,
valeurs brutes conservées dans data-size/data-modified-ns. Date hors plage contrôlée.
Le détail utilise exclusivement les métadonnées de son descripteur courant ; un
contrôle après lecture refuse les changements de size/mtime/ctime ou longueur.

## Lecture brute

`read_template_source(root, template_path)` valide lexicalement, valide le projet
puis appelle `read_project_source_details`. Petite extraction du lecteur commun :
`SourceContent(text, size, modified_ns)` ; `read_project_source` conserve son API
retournant une chaîne et la politique de chemins existante. Aucun second lecteur
indépendant. UTF-8 strict avec BOM initial admis, limite historique de 1 Mio.
Source vide, accents/emoji, dernière ligne sans newline et syntaxe Jinja incomplète
restent lisibles. Pas de normalisation du contenu.

## Confinement filesystem

Scan avec `forge/filesystem.open_directory`, ouverture segment par segment sans
symlink. Dossiers découverts comparés par samestat après ouverture ; fichiers :
stat sans suivi, open O_NOFOLLOW/O_NONBLOCK, fstat régulier et samestat.
Tous les descripteurs sont fermés par context managers/finally. Le lecteur source
commun conserve l'ancrage de chaque segment jusqu'au fichier. Aucun repli permissif.

## Bornes

| Constante | Valeur | Justification |
|---|---:|---|
| MAX_TEMPLATE_FILES | 512 | Liste synchrone de taille raisonnable |
| MAX_TEMPLATE_DIRECTORY_ENTRIES | 4096 | Borne globale, y compris noms exclus |
| MAX_TEMPLATE_SCAN_DEPTH | 32 | Arborescence profonde mais récursion bornée |
| MAX_SOURCE_BYTES | 1 Mio | Contrat historique du lecteur source |
| MAX_SOURCE_PATH_LENGTH | 4096 caractères | Contrat lexical commun |

MAX_TEMPLATE_DEPTH de Route Explorer reste distinct et inchangé. Un surplus
produit truncated=True et une seule issue template.analysis_truncated. Limite
exacte sans surplus : pas de troncature. Au plus 4097 noms consommés, dernier
uniquement pour détecter le dépassement. Un dossier trop profond est signalé sans
être parcouru, même s'il serait vide. Au-delà du budget de découverte, le
sous-ensemble dépend de l'énumération filesystem ; le résultat retenu reste trié.
Les tentatives échouées et diagnostics locaux restent bornés par les entrées.

## TemplateViewerTool

Cinquième Tool : id template-viewer, nom Template Viewer, description
« Lire les templates locaux d’un projet Forge. ».
run(project_root: Path) -> TemplatesResult délègue directement à read_templates.
Aucun état, cache, parsing ou lecture au démarrage.

## ToolRegistry

Enregistrement explicite dans l'ordre project-inspector, route-explorer,
entity-explorer, debug-center, template-viewer. Exactement cinq Tools.
Les assertions de composition historiques sont adaptées ; les autres contrats
restent inchangés. Aucun mécanisme de découverte automatique.

## Intégration Web

GET /templates : un appel Tool avec projet, zéro sans projet. Tableau accessible
avec caption, en-têtes Template/Taille/Modification/Action, lien Voir nommé par
chemin. GET /templates/view : lecture brute et retour fixe à la liste. Navigation
Template Viewer après Debug Center, active_page=templates pour les deux pages.
Texte source dans pre/code, chemins relatifs et métadonnées échappés.

Liens construits avec urlencode. Paramètre path unique parmi les valeurs non vides,
politique source_parts et borne du chemin complet mvc/views/<path>. Comme les autres
parsers utilisant Request, les valeurs vides sont éliminées par Forge avant accès :
path=&path=page est une seule valeur disponible. Deux valeurs non vides refusées ;
clés inconnues non vides refusées. Aucun double décodage ni normalisation de chemin.

Toutes les réponses contrôlées portent no-store. POST refusé : 405.
Sans projet : liste 200, détail 409. Projet devenu absent/non dossier/non Forge/non
résoluble : 409. Chemin refusé avant accès : 400. Fichier absent : 404. Source liée,
remplacée, inaccessible, trop grosse ou non UTF-8 : 409. /source garde ses statuts.

## Sécurité

Politique lexicale source unique : traversal, absolus, segments cachés/vides,
backslash, deux-points, NUL et noms sensibles refusés. Aucune extension utilisée
comme frontière de sécurité. HTML/Jinja cible passé comme texte à Jinja, jamais
comme template : scripts, attributs hostiles, cycler.__init__.__globals__, include,
raise_exception et syntaxe incomplète affichés littéralement. Aucun JavaScript,
changement de CSP, URL libre, téléchargement, écriture ou exécution cible.

## Non-exécution

Bridge sans import Jinja, Environment, get_template, rendu, import projet,
subprocess ou loader. Tests avec app.py/config.py/bootstrap.py et contrôleur
levant immédiatement s'ils étaient exécutés. Ils n'empêchent pas la consultation.
L'inventaire fonctionne même lorsque les primitives de lecture du contenu sont
bloquées par le test. Aucun appel métier Forge cible.

## Non-écriture

Tests HTTP et scénario installé comparent octets/taille/mtime des fichiers projet
et configuration avant/après GET. L'identité CurrentProjectContext.inspection est
stable dans le scénario installé. L'ouverture POST initiale est la seule opération
qui alimente l'historique temporaire. Aucun fichier .forge-design ou cache ajouté.
Le dépôt Forge reste propre.

## Opt-ins

Template Viewer v1 liste uniquement mvc/views/ du projet. Les templates fournis
exclusivement par les loaders d'opt-in ne sont pas inclus. Les surcharges physiques
locales apparaissent naturellement sans analyse des relations avec les opt-ins.

## Fichiers créés

- forge_design/forge/templates.py
- forge_design/tools/template_viewer.py
- forge_design/web/template_viewer.py
- forge_design/web/templates/templates.html
- forge_design/web/templates/template_view.html
- tests/test_templates.py
- tests/test_template_viewer.py
- tests/test_web_templates.py
- docs/tools/template-viewer.md
- docs/rapports/FD-TEMPLATE-001.md

## Fichiers modifiés

- forge_design/forge/source.py : lecteur commun avec métadonnées courantes.
- forge_design/limits.py : trois limites d'inventaire.
- forge_design/app.py : cinquième Tool.
- forge_design/web/server.py : deux routes GET.
- forge_design/web/templates/layout.html : navigation.
- pyproject.toml : deux templates dans package-data.
- tests/test_app.py, tests/test_debug_center.py,
  tests/test_debug_center_stabilization.py,
  tests/test_entity_explorer_stabilization.py : composition à cinq Tools.
- docs/02-architecture.md : flux et responsabilités Template Viewer.

CSS, JavaScript, roadmap et dépôt Forge inchangés. Aucune dépendance ajoutée.

## Tests ajoutés

69 nouveaux cas, Bridge/Tool/Web. Racines invalides, absence/vide, arborescence,
tri Unicode et métadonnées précises ; noms sensibles/cachés, symlinks mvc/views/
sous-dossier/fichier, FIFO et socket Unix. Bornes exactes/surplus, profondeur,
budget global et noms ignorés ; valeurs de production 512 fichiers et 32 niveaux.
Erreurs locales préservant les autres fichiers, races fichier/dossier/views,
remplacement à l'ouverture source et mutation pendant lecture.

UTF-8/BOM/emoji/vide/1 Mio exact/surplus/non UTF-8/sans newline, texte Jinja brut,
immutabilité, lecture lexicale refusée avant validation de racine, absence de
lecture de contenu à l'inventaire. Tool : délégation et absence de scan au démarrage.

HTTP : liste/détail, un appel Tool par liste, metadata et date, encodage URL,
nom/source hostiles, navigation, no-store, POST 405, 400/404/409, projet devenu
invalide, ajout/modification/suppression et non-écriture. Les tests historiques de
/source et des quatre autres Tools restent actifs. Contrôles JS historiques exécutés.

## Test réel

Copie temporaire du squelette Forge actuel ; wheel installée avec
--no-deps --no-index --target. Processus Python -I utilisant les dépendances .venv,
origine installée vérifiée pour serveur, Web et Bridge. Cinq Tools exactement.

Ouverture projet ; /templates inventorie layouts/base.html, home/index.html,
partials/nav.html, components et errors. Lien encodé de layouts/base.html suivi,
contenu complet et blocs Jinja retrouvés comme texte. Ajout extérieur d'un nom
Unicode avec espace/&/+ : inventaire actualisé puis source HTML/Jinja hostile brute.
Modification extérieure du contenu/taille/mtime : détail actualisé. Suppression :
ancien lien 404. Traversal 400, retour liste puis /routes, /entities et /debug réussis.

Snapshots projet et XDG, contexte inchangé autour de chaque GET ; zéro Tool sans
projet, exactement un par liste ouverte, aucun scan de liste sur détail. Serveur
arrêté, thread terminé, socket fermé et port réutilisable. Dépôt Forge intact.
Script/journal ignorés : tmp/verify_fd_template_001.py et .log.

## Packaging

Wheel reconstruite : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `b9f4ddecd90daa14eb627f75c92384b06f732f44815151563847e8cceca7b7e3`.
Archive inspectée : nouveaux modules, lecteur source commun, primitives filesystem,
limites, composition, serveur, deux templates et layout, CSS et scripts présents
avec octets identiques aux sources. Aucun tests/ ou tmp/ distribué. Installation
réelle et scénario HTTP réussis.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| git status ; git log --oneline --decorate -10 | Baseline conforme |
| git -C ../Forge ls-remote origin refs/heads/main | Baseline Forge identique |
| pytest -q --tb=short | 1279 réussis, 69 nouveaux cas |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Wheel inspectée/installée et scénario HTTP isolé | Succès |
| git -C ../Forge status --short | Propre |

Outils .venv, Python 3.13.5, Node disponible. Le premier test socket Unix a été
bloqué en sandbox ; tests sockets/HTTP exécutés ensuite hors sandbox avec succès.
Construction isolée et scénario HTTP autorisés hors sandbox. Corrections de typage
des tuples utime et d'une valeur HTML optionnelle avant validation complète.
Journal suite : tmp/pytest_fd_template_001.log. Diff complet et nouveaux fichiers
relus avant commit, rapport inclus.

## Tests sautés

Aucun test pytest sauté. Aucun navigateur réel ou lecteur d'écran revendiqué :
validation HTTP et parsing DOM. Aucun MkDocs configuré dans Forge Design ;
mkdocs build --strict non applicable.

## Limites restantes

Inventaire filesystem, sans analyse Jinja/HTML, résolution d'opt-in ou prévisualisation.
Coloration reportée. Budget global : sous-ensemble dépendant du filesystem au-delà
de 4096 noms. Lecture POSIX sécurisée requise. Pas d'instantané atomique : dossier
ouvert pouvant être renommé et contenu concurrent pouvant changer. Contrôles de
size/mtime/ctime ne constituent pas un verrou. Aucun cache entre GET.
Source inventoriée pouvant ensuite devenir absente/illisible ; métadonnées d'une
lecture courante seulement. Les valeurs vides de query suivent le parseur Forge.

## État Git final

Un seul commit local sur main, rapport inclus, sans push conformément au ticket.
Message : `feat: ajouter le lecteur Template Viewer (FD-TEMPLATE-001)`.
Le hash et l'état Git final vérifiés sont communiqués dans la réponse de livraison.
