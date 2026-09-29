# Rapport — FD-TEMPLATE-005

## Ticket et objectif

Stabiliser la verticale Template Viewer 001–004, de l'inventaire à la navigation
locale, sans nouvelle fonction utilisateur. Revue des contrats, bornes, parsers,
filesystem, HTTP et packaging ; corrections limitées aux défauts constatés.

## État Git initial

main propre et synchronisée avec origin/main à `fa24096` — FD-TEMPLATE-004.
État Git et dix derniers commits inspectés avant modification. Aucun AGENTS.md.

## Baseline Forge vérifiée

`git -C ../Forge ls-remote origin refs/heads/main` confirme
`73a956e587e5f169c028415e0e540c149cbaff56`, identique au HEAD local propre.
Le renderer Jinja conserve son FileSystemLoader projet prioritaire sur mvc/views,
puis les loaders opt-in. Squelette mvc/views inspecté et copié pour le test réel.
Aucun fichier Forge modifié, aucun checkout ou fetch effectué.

## APIs stabilisées

Signatures inchangées et verrouillées par test : read_templates(root),
read_template_source(root, template_path), analyze_template_structure(source),
build_template_tree(structure), flatten_template_tree(tree),
reference_rejection(reference), resolve_template_references(root, references).
Aucune nouvelle responsabilité du Tool, du Web ou du registre.

## Modèles stabilisés

Quatorze dataclasses gelées conservées : TemplateInfo, TemplateIssue,
TemplatesResult, TemplateSource, TemplateSyntaxInfo, TemplateReference,
TemplateBlock, HtmlElement, TemplateStructureIssue, TemplateStructure,
TemplateHtmlNode, TemplateTree, TemplateTreeRow et TemplateNavigation.
Collections en tuples, aucun état caché ajouté. Test transversal du gel et des API,
suites historiques d'immuabilité et de pureté maintenues.

## Bornes

| Constante | Valeur et unité |
|---|---|
| MAX_TEMPLATE_FILES | 512 fichiers retenus |
| MAX_TEMPLATE_DIRECTORY_ENTRIES | 4096 noms découverts, exclus compris |
| MAX_TEMPLATE_SCAN_DEPTH | 32 sous-dossiers, views à profondeur zéro |
| MAX_SOURCE_BYTES | 1 048 576 octets source |
| MAX_SOURCE_PATH_LENGTH | 4096 caractères du chemin complet relatif |
| MAX_TEMPLATE_STRUCTURE_CHARS | 1 048 576 caractères Python analysés |
| MAX_TEMPLATE_STRUCTURE_NODES | 4096 éléments HTML |
| MAX_TEMPLATE_REFERENCES | 512 déclarations |
| MAX_TEMPLATE_BLOCKS | 512 blocks |
| MAX_TEMPLATE_JINJA_TOKENS | 32768 tokens avant AST |
| MAX_SYNTAX_MESSAGE_LENGTH | 240 caractères |

La borne de caractères remplace l'usage de MAX_SOURCE_BYTES pour len(str), sans
changer la valeur ou le comportement admis. Frontière Unicode testée séparément.
Tests exact/+1 existants conservés pour fichiers, découverte, profondeur, octets,
références, blocks et HTML ; ajout d'une frontière exacte de tokens par injection
du budget et d'un inventaire réel de 512 fichiers parmi 4096 noms.

## Inventaire

512 fichiers à EOF ne tronquent pas ; un candidat régulier supplémentaire le fait.
Les noms ignorés consomment volontairement le budget global de découverte. Au plus
4097 noms sont consommés, le dernier servant de sentinelle de dépassement.
Les issues locales restent bornées par les entrées découvertes, plus les issues
globales ; aucune raison démontrée d'ajouter un plafond séparé.
Le résultat est trié, mais au-delà de 4096 entrées le sous-ensemble dépend de
l'énumération filesystem avant tri. Aucun changement requis au lecteur.

## Lecture brute

Source UTF-8 avec BOM initial accepté, limite en octets, texte et newlines conservés.
Métadonnées issues de la lecture courante ; contrôle size/mtime/ctime/longueur après
lecture. Une mutation de quatre octets vers quatre autres est détectée dans le
nouveau test. Une inspection de métadonnées ne lit pas le contenu cible.

## Parser Jinja partagé

parse_template, iter_template_nodes et iter_template_references sont inchangés.
Comparaison explicite des références Routes/Viewer : include liste littérale,
liste mixte dynamique et extends dynamique. Ordre, erreurs, récursion et limites
historiques rejoués avec toutes les suites Routes. Aucun loader ni rendu.

## Masque Jinja

Scanner relu sans correction nécessaire. Nouveaux cas : double endraw, endraw dans
le texte littéral d'un raw, quote échappée contenant un faux délimiteur, commentaire,
série de raw et expression inachevée. Longueur et lignes du masque conservées.
Les tests historiques couvrent aussi quotes, backslashes, expressions multilignes,
CRLF et délimiteurs imbriqués. Le masque reste lexical, sans prétendre valider Jinja.

## Analyse HTML

Deux défauts reproduits : fermeture inconnue parcourant toute la pile, et ligne
erronée après CR seul. Un index des positions par tag remplace la recherche inverse ;
chaque ouverture est dépilée au plus une fois. Fermetures mal ordonnées, éléments
vides et autofermants gardent leurs règles historiques.
La copie masquée transmise à HTMLParser normalise CRLF/CR vers LF comme Jinja ;
la source et le masque public restent intacts. Scripts/styles restent des éléments,
sans analyse de leur contenu. Structure source détectée, jamais DOM HTML5 rendu.

## partial / truncated

partial est désormais calculé explicitement depuis syntaxe, masque et troncature,
indépendamment du nombre d'issues. Cela préserve les résultats actuels sans coupler
le contrat à toute future issue informative.
truncated indique une interruption par une limite de collecte ou de ressources
du parser : longueur, tokens, références, blocks, HTML, récursion/conversion Python.
Erreur syntaxique ou erreur HTML contrôlée : partial peut être vrai sans truncated.
Jinja unreadable après interruption produit html_partial et structure_truncated,
chacun une fois ; refus initial de longueur : structure_truncated uniquement.

## TemplateTree

Construction et aplatissement itératifs inchangés, sans macro récursive ni égalité
ou repr profonde dans le Web. Tests de sauts, profondeur initiale positive, frères,
retour à zéro et 4096 niveaux ; close_levels final vaut 4095. Les suites historiques
contrôlent l'équilibre ul/li, les 10000 niveaux synthétiques et la profondeur négative.
Celle-ci reste un ValueError du contrat pur, impossible depuis HTMLParser.

## Navigation locale

Cinq états conservés. available/« Local » signifie fichier régulier local ouvrable,
non lié et de taille admise ; ne garantit ni UTF-8 ni syntaxe. Cas binaire : lien
available puis 409 à la lecture, testé sur brut et arbre. Aucun préchargement ajouté.
Les doublons restent visibles et ordonnés. Cache par chemin pendant un seul appel :
instantané logique du contrôle, sans atomicité filesystem ni cache global.
Aucun suivi transitif, cycle, résolution opt-in ou fusion des occurrences.

## Inspection filesystem

Ouverture commune revue : racine et parents ancrés, O_NOFOLLOW/O_NONBLOCK, fichier
régulier, stat/open/fstat/samestat, contrôle de taille, fermeture dans finally.
Tests historiques symlinks mvc/views/parents/fichiers, FIFO, sockets, dossiers et
remplacements rejoués. Nouveau contrôle des descripteurs via /proc/self/fd après
mutation refusée, vingt inspections réussies et vingt absences : aucun descripteur
perdu. Lecture et inspection partagent toujours la même politique.

## Contrats HTTP

Liste sans projet 200 sans Tool ; brut/arbre sans projet 409 pour path valide.
Chemin invalide 400 avant lecture, absence 404, projet invalide/source illisible 409.
no-store sur 200/400/404/409 ; POST des trois routes refusé 405.
Parser strict sur valeurs non vides : path manquant/vide/répété ou clé inconnue
refusés ; les valeurs vides éliminées par Forge gardent leur convention existante.
Tests historiques d'un seul read/analyze principal et d'inspections par cible unique
rejoués ; une seule invocation Tool par liste avec projet. Cinq Tools seulement.

## URLs et Unicode

NFC é et NFD e + accent combinant restent deux fichiers distincts, sans normalisation.
Accents, ß, emoji, espace, +, &, %, #, ? et nom littéral %2e%2e testés via les URLs
encodées et les liens brut/arbre. Aucun second unquote. Politique source commune.

## Sécurité / XSS

Sources script/img/onerror et expressions Jinja dangereuses restent du texte.
Échappement du brut, de la structure, des liens et aria-label contrôlé par les suites
historiques et le parsing HTML réel installé. Aucun safe/Markup source, aucun script
Viewer, aucune modification CSP. Noms env, ENV, Private.KEY, private.pem, ID_RSA_backup,
id_dsa, id_ecdsa.pub et ID_ED25519 exclus à plusieurs profondeurs par la même politique.

## Performance

Cas reproduit : 2000 ouvertures puis 20000 fermetures inconnues, 210000 caractères.
Mesure locale indicative : environ 1,254 s avant, 0,091 s après ; 2000 éléments conservés.
La non-régression compte les événements de trace Python selon la profondeur,
sans seuil temporel fragile. Inventaire réel : 512 fichiers et 4096 noms.
Depuis la wheel, source de 1 048 576 caractères/octets et 4096 niveaux : analyse
0,222 s, construction/aplatissement 0,011 s, navigation de 512 occurrences vers une
cible unique 0,002 s. Ces chiffres ne constituent pas un engagement de latence.
Inventaire avec tri : O(D log D), pas O(D) strict. Pile HTML amortie linéaire ; arbre
O(n), navigation O(références) hors filesystem. Coût interne Jinja non réimplémenté.

## Non-exécution

Copie de squelette avec app.py, config.py et controller levant immédiatement si
importés. Inventaire, brut, arbre et navigation fonctionnent. Expressions
cycler.__init__.__globals__, raise_exception() et include dynamique non évaluées.
Aucun import projet, rendu, subprocess Forge ou loader opt-in dans le parcours.

## Non-écriture

Avant/après chaque GET installé : comparaison octets, taille et mtime de tout le
projet et de XDG ; identité de CurrentProjectContext.inspection inchangée.
Le POST initial ouvre seulement la fixture temporaire. Mutations de fixture
volontaires entre GET, jamais par l'application. Aucun cache persistant.

## Compatibilité Route Explorer

Toutes les suites Routes, dépendances, graphes, cycles, erreurs et limites passent.
Primitives communes inchangées ; /routes fonctionne aussi depuis la wheel.

## Compatibilité Source Viewer

source.py et handler /source inchangés. Suites historiques et consultation installée
du template hostile via /source réussies. Même politique lexicale, mêmes garanties
de lecture et contrats historiques de paramètres.

## Compatibilité autres Tools

Project Inspector ouvre le projet temporaire. /entities et /debug restent accessibles.
Suite complète active, registre exactement project-inspector, route-explorer,
entity-explorer, debug-center et template-viewer. Aucun sixième Tool.

## Défauts concrets trouvés

| Constat | Correction |
|---|---|
| Fermetures HTML inconnues × profondeur : coût quadratique | Index des ouvertures, dépilement amorti |
| CR seul : ligne HTML différente de Jinja | Normalisation de la copie HTML |
| Constante d'octets réutilisée pour len(str) | Borne dédiée en caractères |
| partial couplé mécaniquement aux issues | Calcul explicite depuis les états |
| Descriptions anciennes excluant la navigation actuelle | Documentation alignée sur 001–004 |

Les deux premiers sont des défauts de comportement reproduits. Les deux suivants
corrigent des contrats de code observables, sans changement de valeurs admises.

## Corrections apportées

Deux fichiers produit seulement : forge/template_structure.py et limits.py.
Aucune modification des signatures, modèles, lecteurs, Tool, navigation, arbre,
handlers, templates Web, CSS, JavaScript, registre ou dépendances.

## Risques revus sans correction

Inventaire exact/+1, quantité d'issues, confinement, fermeture des descripteurs,
lecture concurrente, raw/endraw, tolérance HTML, arbre profond, cache et états
navigation : aucun autre défaut démontré exigeant une correction.
« Local » demeure cohérent avec le contrôle léger, documenté sans promesse UTF-8.
Les races résiduelles et les limites de rendu navigateur sont conservées explicitement.

## Fichiers créés

- tests/test_template_viewer_stabilization.py
- docs/rapports/FD-TEMPLATE-005.md

## Fichiers modifiés

- forge_design/forge/template_structure.py
- forge_design/limits.py
- docs/tools/template-viewer.md
- docs/02-architecture.md

## Tests ajoutés

28 cas : contrats, modèles, registre et bornes ; inventaire réel exact/+1 ; frontière
de tokens ; trois fins de ligne ; coût des fermetures ; six cas de masque ; échec HTML
partiel ; unités Unicode ; huit noms sensibles ; mutation de même taille et descripteurs ;
compatibilité du parser Routes ; sauts/arbre profond ; parcours HTTP Unicode/binaire.
Les 1381 cas historiques restent inchangés et actifs.

## Test réel

Wheel inspectée puis installée --no-deps --no-index --target, processus Python -I
avec origine des modules installés vérifiée. Copie temporaire du squelette Forge.
Liste → brut → arbre → dépendance locale → brut cible, puis retour et autres Tools.
Templates locaux, dynamiques, absents, interdits, invalides, hostiles, Unicode,
doublons et arbre de 4096 niveaux. Ajout, modification, suppression et remplacement
par symlink d'une cible ; modification puis suppression du template principal.
États actualisés à chaque GET. Sources comparées au texte réellement présent.
Serveur arrêté, thread terminé, socket fermé, port réutilisable.
Script et journal ignorés : tmp/verify_fd_template_005.py et .log.

## Packaging

Wheel : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `36cd5d748b37debd3b7477e86abcbd3cf91a7c0cca43cabf27eb826b8d48589e`.
Modules Viewer, parser partagé, lecteurs source/filesystem, routes, limites,
templates Web, CSS et scripts comparés octet par octet aux sources.
Aucun tests/ ou tmp/ distribué. Installation et scénario HTTP réussis.
Aucune dépendance nouvelle.

## Commandes exécutées et résultats

| Commande | Résultat final |
|---|---|
| git status ; git log --oneline --decorate -10 | Baseline conforme |
| git -C ../Forge ls-remote origin refs/heads/main | Baseline identique |
| pytest -q --tb=short | 1409 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Installation temporaire et parcours HTTP isolé | Succès |

Outils .venv, Python 3.13.5 ; suite HTTP, build isolé et test réel avec autorisation
hors sandbox. Erreurs de typage du nouveau test de trace/dataclasses corrigées avant
validation. Tests de régression exécutés avant correction reproduisant les défauts.
Journal de suite : tmp/pytest_fd_template_005.log. Diff complet et fichiers nouveaux relus.

## Tests sautés

Aucun test pytest sauté. Node exécuté. mkdocs build --strict non applicable : aucune
configuration MkDocs. Aucun navigateur réel ni lecteur d'écran revendiqué.

## Limites restantes

mvc/views seulement ; aucun opt-in inspecté, rendu, édition ou génération.
Jinja statique et HTML approximatif, sans DOM HTML5 ni validation métier. Références
dynamiques non résolues, navigation directe uniquement. available ne garantit ni
UTF-8 ni syntaxe. Filesystem non atomique, état pouvant changer avant clic ; les
contrôles de métadonnées ne verrouillent pas les fichiers. Sous-ensemble dépendant
du filesystem au-delà du budget. Bornes de volume et coûts internes du parser,
profondeur/affichage navigateur inchangés. Support POSIX sécurisé requis.

## État Git final

Un seul commit local sur main, rapport inclus, sans push conformément au ticket.
Message : `refactor: stabiliser Template Viewer (FD-TEMPLATE-005)`.
Hash et état Git après commit communiqués dans la réponse de livraison.
