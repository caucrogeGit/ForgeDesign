# Rapport — FD-TEMPLATE-003

## Ticket et objectif

Projeter TemplateStructure vers une vue arbre serveur distincte de la source brute.
Aucun nouveau parsing, résolution de dépendance, rendu cible, JavaScript ou Tool.

## État Git initial

main propre et synchronisée avec origin/main à `dba6e79`, FD-TEMPLATE-002.
État Git et dix derniers commits inspectés. Aucun AGENTS.md dans le dépôt.
Squelette Forge local à `73a956e587e5f169c028415e0e540c149cbaff56`, propre ;
constructions layouts/base.html et home/index.html relues pour le scénario réel.
Aucun fichier Forge modifié.

## Modèle TemplateTree

TemplateTree gelé : dependencies et blocks réutilisent les tuples immuables de la
structure ; html contient des TemplateHtmlNode(tag, line, children) gelés avec
children en tuple. partial et truncated sont propagés exactement.
TemplateTreeRow gelé : tag, line, depth, has_children, close_levels pour le rendu.

## Séparation Jinja / HTML

Trois sections explicites : Dépendances Jinja, Blocks Jinja, Structure HTML.
Aucune relation block/balise ni hiérarchie de blocks inventée depuis les lignes.
Le modèle HTML représente uniquement la profondeur produite par FD-TEMPLATE-002.

## Dépendances

Ordre, types extends/include/import/from-import, doublons, chemins complets et
lignes conservés. Le type et la ligne portent un enfant textuel chemin ou
« Référence dynamique ». Aucun lien, contrôle de présence, qualificatif
présent/absent ou consultation filesystem des dépendances.

## Blocks

Liste à un niveau avec noms complets et lignes. Homonymes et ordre conservés,
sans déduction de parenté. Message explicite si aucun block détecté.

## Arbre HTML

build_template_tree(structure) parcourt les éléments dans leur ordre. Une pile de
profondeurs originales trouve le dernier parent disponible de profondeur inférieure.
Indices d'enfants accumulés localement, puis nœuds gelés en ordre inverse.
Plusieurs racines admises ; aucune règle spéciale pour void ou HTML imparfait.
Construction O(n), mémoire O(n), aucun parser, regex ou recherche quadratique.

## Profondeur et robustesse

Un saut rejoint le parent disponible le plus proche sans fabriquer de nœud.
Deux éléments de même profondeur restent frères, même après un saut. Un premier
élément de profondeur positive devient racine. Profondeur négative : ValueError.
Aucun nouveau plafond dupliquant ceux du parser. Projection testée à 4096 et 10000
niveaux, sans récursion. flatten_template_tree parcourt aussi itérativement et
calcule les fermetures nécessaires en O(n).

## Vue arbre

GET /templates/tree?path=... utilise une lecture source, une analyse mémoire
existante et build_template_tree. Les lignes aplaties rendent de véritables ul/li
imbriqués par boucles, sans macro récursive ou construction de chaînes HTML.
Métadonnées de la même TemplateSource courante ; titre avec chemin relatif.

Bannières exactes pour analyse partielle et structure tronquée. Syntaxe Jinja
invalide affichée, HTTP 200 conservé. Trois messages de sections vides ; source
vide fonctionne. La page précise arbre source détecté, pas DOM rendu/corrigé.

## Navigation brut / arbre

Le brut conserve sa source et toute la section textuelle FD-TEMPLATE-002, avec
« Voir l’arbre » près du titre. L'arbre fournit « Voir le fichier brut » vers le
même path et « Retour à Template Viewer ». URLs construites avec urlencode.
La liste garde Voir vers le brut ; aucun nouvel item global.

## Statuts HTTP

Détail commun dans web/template_viewer.py pour ne pas dupliquer parsing/lecture/
erreurs : parse_template_path inchangé. Chemin refusé 400, template absent 404,
aucun projet ou projet devenu invalide 409, source liée/inaccessible/trop grosse/
non UTF-8 409, source lisible 200 même si Jinja invalide. no-store conservé sur
les réponses contrôlées ; POST /templates/tree refusé 405.
Aucun scan d'inventaire, aucun appel TemplateViewerTool.run sur l'arbre.

## Accessibilité

Sections nommées par aria-labelledby, titres, listes ul/li et lignes lisibles sans
CSS. Hiérarchie sémantique réelle, bordures et indentation en complément visuel,
retour à la ligne des longs labels et zone HTML défilante. Navigation globale
active_page=templates. Pas de rôle tree interactif, sélection ou raccourci ajouté.
Pas de test navigateur réel ou lecteur d'écran revendiqué.

## Sécurité

Labels issus du modèle échappés par Jinja. Fixtures synthétiques dependency.path,
block.name et HtmlElement.tag hostiles vérifiées en HTTP : texte retrouvé intact,
aucun élément img/script injecté. Aucun Markup, filtre safe ou HTML concaténé depuis
les valeurs. Les balises de structure de page sont fixes dans le template packagé.
Politique source/confinement/CSP inchangée, dépendances textuelles uniquement.

## Pureté

Module tools/template_tree.py limité à dataclasses et modèles de structure.
Tests bloquant open, os.open/stat/scandir/listdir, Path.open/read_text/read_bytes/
stat/iterdir, ToolRegistry.get, read_template_source, analyze_template_structure,
mask_jinja, construction Environment et HTMLParser. Projection/aplatissement
restent fonctionnels. Entrée intacte, aucun contexte, Request ou accès filesystem.

## Déterminisme

Ordres d'entrée et doublons préservés ; modèle et aplatissement déterministes.
Tests de hiérarchie 0/1/2/1/0, racines multiples, sauts répétés et début décalé.
Modèles gelés vérifiés, tuples uniquement dans les résultats publics.

## Compatibilité Template Viewer

Inventaire, lecteur sécurisé, parser structurel et TemplateViewerTool inchangés.
La factorisation Web conserve le contrat brut ; une seule analyse par GET valide.
Les tests instrumentent read_template_source/analyze_template_structure : un appel
chacun, dans l'ordre ; le Tool d'inventaire est interdit durant ces GET.
Les tests historiques FD-TEMPLATE-001/002 passent sans modification.

## Compatibilité Route Explorer

forge/routes.py, graphes, layout et scripts inchangés. Toutes les suites Routes,
dépendances, syntaxe, cycles, filtres et transitivité restent actives et vertes.
Toujours exactement cinq Tools, composition et registre inchangés.

## Non-exécution

Aucun parser supplémentaire, parcours AST, loader, rendu du template cible,
compilation ou import projet. Seul le template d'interface packagé est rendu.
Fixtures hostiles historiques actives ; scénario installé avec app/config/contrôleur
levant s'ils étaient exécutés. Aucun nouvel accès aux fichiers dépendants.

## Non-écriture

Tests HTTP : source et historique comparés en octets/mtime avant/après consultation.
Scénario installé : snapshots projet et XDG (octets, taille, mtime) et identité
CurrentProjectContext.inspection avant/après chaque GET, aucune différence.
Les changements de fixture entre GET sont externes et explicites. Forge reste propre.

## Fichiers créés

- forge_design/tools/template_tree.py
- forge_design/web/templates/template_tree.html
- tests/test_template_tree.py
- tests/test_web_template_tree.py
- docs/rapports/FD-TEMPLATE-003.md

## Fichiers modifiés

- forge_design/web/template_viewer.py : détail commun, URL arbre et projection.
- forge_design/web/templates/template_view.html : lien Voir l'arbre.
- forge_design/web/server.py : route GET arbre.
- forge_design/web/static/shell.css : lisibilité des listes et défilement.
- pyproject.toml : template arbre packagé.
- docs/tools/template-viewer.md : usage, modèles et limites.
- docs/02-architecture.md : projection et rendu serveur itératifs.

Aucune modification des parsers, lecteurs, Tool, app/registre, JavaScript,
roadmap ou dépôt Forge. Aucune dépendance ajoutée.

## Tests ajoutés

40 cas : 13 unitaires et 27 HTTP. Dépendances de chaque type/dynamique/doublons,
blocks ordonnés, vide, quatre combinaisons partial/truncated, immutabilité,
pureté, hiérarchie/plusieurs racines/sauts/profondeur négative, 4096/10000 niveaux.

HTTP : vide, structure réaliste, dynamique, blocks homonymes, syntaxe invalide,
troncature à 4096 éléments, source brute préservée, navigation encodée bidirectionnelle,
absence de liens de dépendances, métadonnées, no-store, POST 405, XSS synthétique,
13 requêtes invalides, sources absentes/liées/grosses/binaires/dossiers, projet
absent/non dossier/non Forge/boucle. Relecture après modification puis suppression.
Le parseur HTML de test vérifie pile ul/li équilibrée et profondeur de chaque nœud,
y compris un document de 4096 niveaux, sans RecursionError serveur.

## Test réel

Wheel installée --no-deps --no-index --target dans un dossier temporaire ; processus
Python -I avec origines installées contrôlées, cinq Tools. Copie du squelette Forge.
Parcours inventaire → brut → arbre → même brut sur layouts/base.html, home/index.html,
partials/nav.html, components/ui.html. Base : header/nav/content/footer et include
partials/nav.html ; home : extends layouts/base.html, from-import components/ui.html,
blocks et balises. Les seuls liens de détail de l'arbre sont vers son propre brut.

Template externe dynamique puis modifié : nouvelle dépendance changed, block newblock,
article/aside visibles au GET suivant avec métadonnées actuelles. Source cassée :
200 et arbre partiel. Suppression : anciennes URLs brut/arbre 404. Retour liste puis
/routes, /entities et /debug réussis. Snapshots et contexte inchangés, serveur arrêté,
thread terminé, socket fermé et port réutilisable. Aucun fichier Forge changé.
Script/journal ignorés : tmp/verify_fd_template_003.py et .log.

## Packaging

Wheel : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `0ed274c4e87b411c09df24b36b803b33f3343c87cf2399106cf1b22a922fbac8`.
Archive inspectée : projection arbre, template arbre/brut/liste/layout, CSS,
Bridge/structure/Routes/source, Tool/Web, composition/limites/serveur et scripts
comparés aux sources. Aucun tests/ ou tmp/ distribué. Installation réelle et
parcours HTTP réussis.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| git status ; git log --oneline --decorate -10 | Baseline conforme |
| Tests arbre unitaires | 13 réussis |
| Tests HTTP arbre + brut/structure historiques | 57 réussis |
| pytest -q --tb=short | 1355 réussis, 40 nouveaux cas |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Wheel inspectée/installée et scénario HTTP | Succès |
| git -C ../Forge status --short | Propre |

Outils .venv, Python 3.13.5, Node disponible. Tests HTTP, construction isolée et
scénario installé autorisés hors sandbox. Ruff a signalé des lignes trop longues
avant formatage ; contrôles finaux réussis. Journal : tmp/pytest_fd_template_003.log.
Diff complet, nouveaux fichiers et rapport relus avant commit.

## Tests sautés

Aucun test pytest sauté. Aucun navigateur réel/lecteur d'écran testé. Aucun MkDocs
configuré : mkdocs build --strict non applicable.

## Limites restantes

Arbre source détecté, pas DOM rendu ou corrigé. Dépendances non résolues et non
cliquables. Blocks sans parenté connue. Les limites d'analyse FD-TEMPLATE-002 restent
inchangées ; la projection ne rajoute pas de plafonds. Les très fortes profondeurs
peuvent être peu lisibles ou corrigées par les moteurs de navigateur ; seule la
construction et l'émission serveur itératives sont vérifiées à 4096 niveaux.
Les opérations automatiques repr/égalité des dataclasses profondément imbriquées
ne sont pas utilisées par le rendu ; les parcours profonds utilisent l'aplatissement.
Aucune interaction, navigation transitive, cycle Viewer, édition ou génération.

## État Git final

Un seul commit local sur main, rapport inclus, sans push conformément au ticket.
Message : `feat: ajouter la vue arbre des templates (FD-TEMPLATE-003)`.
Hash et état Git final vérifiés communiqués dans la réponse de livraison.
