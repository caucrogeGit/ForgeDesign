# Rapport — FD-TEMPLATE-002

## Ticket et objectif

Ajouter une analyse structurelle HTML/Jinja légère en mémoire à la source brute :
syntaxe, extends/include/import/from-import, blocks et balises HTML avec ligne et
profondeur. Affichage textuel sous la source, sans UI arbre, navigation transitive,
rendu, édition, loader ou nouveau Tool.

## État Git initial

main propre et synchronisée avec origin/main à `7808192`, FD-TEMPLATE-001.
État Git et dix derniers commits inspectés avant modification. Aucun AGENTS.md.

## Baseline Forge vérifiée

Lecture distante de Forge/main via ls-remote :
`73a956e587e5f169c028415e0e540c149cbaff56`, identique au HEAD local propre.
Renderer Jinja, layouts/base.html, home/index.html, components et partials examinés.
Le squelette utilise extends, include ignore missing, from-import, blocks, macros,
call, chaînes et expressions multilignes. Aucun fichier Forge modifié.

## Réutilisation de l’analyse Route Explorer

Primitives génériques déplacées dans forge/template_structure.py : parse_template,
itération AST et références. routes.py conserve ses adaptateurs privés, modèles et
APIs publics. Le parsing et le décodage des références ne sont plus dupliqués.
Aucune modification de lecture Routes, présence, caches locaux, graphe ou cycles.
La garde lexicale supplémentaire du Viewer n'est pas appliquée à Route Explorer.

## Modèle TemplateStructure

Dataclasses gelées : TemplateSyntaxInfo(status, line, message),
TemplateReference(kind, path, dynamic, line), TemplateBlock(name, line),
HtmlElement(tag, line, depth), TemplateStructureIssue(code, message).
TemplateStructure contient syntax, dependencies, blocks, html_elements, issues,
partial et truncated. Collections en tuples, lignes à partir de 1, profondeur à 0.
Aucun chemin filesystem ni objet mutable exposé par la projection.

## Parser Jinja

Environment(loader=None).parse(source), sans extension projet, compilation ou
rendu. valid signifie « Syntaxe Jinja analysable », jamais « Template valide ».
TemplateSyntaxError donne invalid avec ligne et message normalisé/borné par
MAX_SYNTAX_MESSAGE_LENGTH=240. RecursionError donne unreadable, comme historiquement.
Le Viewer contrôle aussi les limites de conversion numérique Python : un entier
Jinja de 5000 chiffres levait ValueError ; il donne désormais un résultat partiel
unreadable, sans modifier le contrat historique du parser utilisé par Routes.

## Extends/includes/imports

Quatre types : extends, include, import, from-import. Référence littérale conservée,
variable/expression marquée dynamic avec path=None. Include liste entièrement
littérale produit une référence par entrée ; liste mixte ou vide produit une
référence dynamique, conformément à Route Explorer. ignore missing et les imports
multiples sont compris par l'AST sans résolution filesystem. Ordre stable par ligne
puis apparition sur une même ligne ; doublons préservés, pas de tri par type/chemin.

## Blocks

Relevé AST des blocks, y compris imbriqués et déclarations homonymes acceptées au
parsing. Ordre d'apparition conservé. Pas de hiérarchie Jinja reconstruite, macros
et variables non inventoriées. Aucun calcul de conditions/boucles ou de bindings.

## Analyse HTML

HTMLParser standard : tag normalisé en minuscules, ligne et profondeur. Pas
d'attributs HTML exposés. Liste plate en ordre source. Les 14 éléments vides HTML
et les formes XHTML autofermantes ne gardent pas de niveau ouvert.
Une fermeture connue dépile jusqu'à son ouverture, une fermeture inconnue est
ignorée. Commentaires/doctype ignorés. Script/style peuvent être des éléments ;
leur contenu reste opaque. Aucun verdict de validité HTML ni correction HTML5.

## Masquage lexical Jinja

Copie de travail de même longueur : zones {{ }}, {% %}, {# #} remplacées par des
espaces en conservant CR et LF. Scanner séquentiel tenant compte des chaînes,
échappements et délimiteurs imbriqués. Le lexer Jinja normalise/retire certains
espaces et retours avec les options de trimming ; un masque à positions originales
évite de reconstruire ces offsets à partir de tokens transformés.

Raw/endraw : seuls les marqueurs sont masqués, le contenu reste littéral. Une
recherche dédiée du marqueur endraw évite de reparcourir des pseudo-directives
Jinja présentes dans raw. Aucun usage d'une regex unique pour parser les expressions.
Zone non terminée : reste masqué et analyse partielle, sans faux tags issus de
l'expression incomplète. Le texte source exposé au Web reste inchangé.

## Tolérance

Jinja invalide n'empêche pas une tentative HTML indépendante. Les issues
syntax_invalid/html_partial rendent la limite explicite. Masque incomplet ou
exception contrôlée du parser HTML donne html_partial. HTML imparfait est toléré,
sans diagnostics de validation. Des balises après une zone Jinja non terminée
peuvent être absentes du relevé ; la source brute reste complète.

## Bornes

| Limite | Valeur | Raison |
|---|---:|---|
| MAX_TEMPLATE_STRUCTURE_NODES | 4096 | Relevé HTML et pile bornés |
| MAX_TEMPLATE_REFERENCES | 512 | Liste de déclarations raisonnable |
| MAX_TEMPLATE_BLOCKS | 512 | Liste de blocks raisonnable |
| MAX_TEMPLATE_JINJA_TOKENS | 32768 | Garde lexicale avant allocation de l'AST |
| MAX_SYNTAX_MESSAGE_LENGTH | 240 | Contrat syntaxe déjà partagé |

Source réelle toujours limitée à 1 Mio par le lecteur. API pure : refus au-delà de
1 048 576 caractères pour les appels synthétiques. Précontrôle lexical en flux,
sans accumuler les tokens ; premier surplus empêche le parse AST. Ce budget n'est
pas une borne exacte de mémoire Python : lexer et chaînes restent liés au volume
source. RecursionError reste contrôlé même sous le budget de tokens.

Exactement à la limite sans surplus : pas de troncature. Premier surplus de
référence, block ou balise : arrêt de l'accumulation concernée et une issue
`template.structure_truncated`, partial=True/truncated=True. Les autres volets
peuvent être conservés. Pile d'itérateurs AST sans parcours récursif ni copies de
fratries. Le masque et HTMLParser restent bornés par le texte source.

## Intégration Template Viewer

GET /templates/view conserve une seule lecture read_template_source puis appelle
analyze_template_structure(source.text). Pas de second accès fichier ni analyse
sur /templates. Source brute intégrale suivie de « Structure détectée », état
syntaxique, issues, tableau de références, liste de blocks, liste HTML indentée.
Référence dynamique explicitement affichée. Pas de lien vers les dépendances.

Indentation visuelle plafonnée à 32 niveaux pour éviter une largeur excessive ;
profondeur exacte et ligne toujours affichées. Pas de CSS dynamique, arbre,
interaction ou JavaScript. Syntaxe invalide : HTTP 200 si la source est lisible.
Navigation, no-store, erreurs de lecture et méthodes restent FD-TEMPLATE-001.
Tool d'inventaire et registre restent inchangés : exactement cinq Tools.

## Sécurité

Toutes les valeurs source/structure passent par l'échappement Jinja du template
packagé : chemin, références, blocks, tags et messages. Fixtures hostiles et test
défensif de modèle synthétique vérifient l'absence d'élément HTML injecté.
Aucune source passée à un renderer, get_template, compile ou loader. Les expressions
arbitraires restent syntaxiques. Aucun lien, accès ou diagnostic de présence pour
les fichiers déclarés dans les dépendances.

## Pureté

analyze_template_structure(source: str) ne reçoit que le texte. Module sans import
os, Path, filesystem, source, Routes, contrôleur ou Web. Tests bloquant open,
os.open/stat/listdir/scandir, Path.open/read_text/read_bytes/stat/iterdir,
ToolRegistry.get, read_template_source, Environment.get_template/from_string/compile
et Template.render/generate/stream. Parsing syntaxique seul autorisé.
Déterminisme et modèles gelés testés.

## Compatibilité Route Explorer

Dataclasses publiques, signatures et résultats Routes inchangés. La conversion des
références communes vers TemplateDependency reste locale à routes.py. Comportement
historique des listes include, tri stable, messages et états syntaxiques conservé.
Les tests existants des dépendances directes, syntaxe invalide, dynamique, graphe
transitif, cycles, limites, filtres et graphes passent sans modification.
Aucun changement de layout, CSS, scripts ou navigation Routes.

## Non-exécution

Aucun rendu de template cible, compilation, import projet ou loader d'opt-in.
Les fixtures unknown(), raise_exception() et références absentes restent analysables.
Le squelette réel contient macros/call/helpers qui ne sont jamais appelés.
Tests historiques de projet hostile conservés et scénario installé avec fichiers
app.py/config.py/contrôleur levant s'ils étaient exécutés.

## Non-écriture

Tests HTTP : source et historique restent identiques en octets/mtime.
Scénario installé : snapshots octets/taille/mtime projet et configuration XDG,
identité CurrentProjectContext.inspection autour de chaque GET. Aucun changement.
Les mutations de fixtures sont explicites et extérieures entre requêtes.
Dépôt Forge propre après les validations.

## Fichiers créés

- forge_design/forge/template_structure.py
- tests/test_template_structure.py
- tests/test_web_template_structure.py
- docs/rapports/FD-TEMPLATE-002.md

## Fichiers modifiés

- forge_design/forge/routes.py : adaptateurs du parsing et des références communes.
- forge_design/limits.py : quatre bornes structurelles.
- forge_design/web/template_viewer.py : projection mémoire après lecture.
- forge_design/web/templates/template_view.html : section textuelle.
- docs/tools/template-viewer.md : analyse et limites.
- docs/02-architecture.md : flux TemplateSource → TemplateStructure.

Bridge d'inventaire, Tool, app, registre, routes HTTP, source reader, packaging,
CSS, JavaScript, tests historiques et roadmap inchangés. Aucune dépendance ajoutée.

## Tests ajoutés

36 nouveaux cas : 30 unitaires et 6 HTTP. Vide/texte, quatre dépendances,
listes/dynamique, blocks imbriqués/doublons et ordres ; HTML complet/fragment,
void/XHTML/fermetures imparfaites/commentaires/doctype/script/style. Attributs Jinja,
masquage de faux HTML dans chaînes/expressions/commentaires, quotes échappées,
multiligne, CRLF, raw et séries de raw.

Syntaxe invalide, message long borné, profondeur pathologique, RecursionError
simulé, budget tokens, entier pathologique et source trop longue. Bornes exactes
et +1 des références/blocks/HTML, include liste de 513 références. Déterminisme,
immutabilité, pureté. HTTP : une lecture, source conservée, valeurs échappées,
référence dynamique, HTML partiel, troncature, no-store, modification puis suppression.
Les 1279 tests historiques restent actifs ; aucun modifié.

## Test réel

Wheel installée avec --no-deps --no-index --target dans un dossier temporaire.
Processus Python -I avec origine installée vérifiée pour serveur, Web, Bridge et
module structure. Copie du squelette Forge, cinq Tools exactement.

/templates puis liens vers layouts/base.html, home/index.html, partials/nav.html et
components/ui.html. Source complète conservée et syntaxe analysable sur les quatre.
Base : blocks, include partials/nav.html, html/head/body. Home : extends base,
from-import components/ui.html, blocks et section relevés sans figer la décoration.

Ajout externe d'un template avec include selected_template : référence dynamique.
Modification : analyse et métadonnées actualisées. Remplacement par `{% if\n<div>` :
HTTP 200, source visible et syntaxe invalide. Suppression : 404. Traversal : 400.
Retour liste et visites /routes, /entities, /debug réussies. Snapshots inchangés et
contexte identique à chaque GET ; serveur/thread/socket fermés, port réutilisable.
Script/journal ignorés : tmp/verify_fd_template_002.py et .log.

## Packaging

Wheel : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `7186b40b93b8f33e23dc959dbd0d33928325a4ddff6fd9c10d878abda3afde71`.
Archive inspectée : nouveau module structure, Routes, modules d'inventaire/source,
Tool/Web, limites/composition/serveur, templates et assets comparés aux sources.
Aucun tests/ ou tmp/ distribué. Installation réelle et parcours HTTP réussis.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| git status ; git log --oneline --decorate -10 | Baseline conforme |
| git -C ../Forge ls-remote origin refs/heads/main | Baseline identique |
| Tests structure + Routes/transitif ciblés | Succès |
| pytest -q --tb=short | 1315 réussis, 36 nouveaux cas |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Wheel inspectée/installée et scénario HTTP | Succès |
| git -C ../Forge status --short | Propre |

Outils .venv, Python 3.13.5, Node disponible. Tests HTTP, build isolé et scénario
installé exécutés avec autorisation hors sandbox. Un probe numérique a révélé
ValueError avant la garde ajoutée ; couverture de non-régression incluse.
Corrections de typage de test (href optionnel/fonction de substitution) avant la
validation complète. Journal suite : tmp/pytest_fd_template_002.log.
Diff complet, nouveaux fichiers et documentation relus avant commit.

## Tests sautés

Aucun test pytest sauté. Aucun navigateur réel ou lecteur d'écran revendiqué :
contrôles HTTP/DOM uniquement. Aucune configuration MkDocs ; mkdocs build --strict
non applicable.

## Limites restantes

HTMLParser n'est pas un validateur ou constructeur DOM HTML5. Fermetures implicites,
branches Jinja et macros peuvent produire une hiérarchie approximative du texte
source, jamais un arbre de rendu. Le masque reconnaît les constructions décrites,
sans devenir une grammaire Jinja exhaustive ; les cas incomplets sont signalés.
Le précontrôle lexical borne l'AST raisonnablement, pas exactement sa mémoire.
Pas de macros/variables inventoriées, bindings, contexte contrôleur, présence des
dépendances, navigation, graphe, transitivité, cycles Viewer ou UI arbre.
Aucun rendu, édition, cache ou modification projet.

## État Git final

Un seul commit local sur main, rapport inclus, sans push conformément au ticket.
Message : `feat: analyser la structure des templates (FD-TEMPLATE-002)`.
Hash et état Git final vérifiés communiqués dans la réponse de livraison.
