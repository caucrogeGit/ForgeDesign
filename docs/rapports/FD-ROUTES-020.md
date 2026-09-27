# Rapport — FD-ROUTES-020

## Ticket et objectif

Stabiliser la verticale Route Explorer par une revue des contrats, une correction de politique de chemins et des tests complets. Aucun nouveau type d’analyse, Tool ou comportement interactif.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `46fcc1d` — FD-ROUTES-019.
État Git et cinq derniers commits inspectés avant modification.

## Revue d’architecture

Le Bridge découvre les faits statiques ; RouteExplorerTool délègue au Bridge.
Diagnostics, filtres, RouteGraph et layout restent des transformations pures. Le Web orchestre une analyse par GET puis les transformations ; le JavaScript ne consulte que le DOM rendu.
Aucune dépendance inverse ajoutée. Le détecteur de cycles utilise les types du Bridge sous TYPE_CHECKING, sans import circulaire runtime.
Les tests historiques d’isolation de chaque couche restent actifs.

## Revue du Bridge

Le module routes reste conséquent (environ 830 lignes), mais ses phases route/contrôleur/template, caches et transformations sont identifiables. Une dispersion générale des modèles aurait ajouté des imports et du risque sans corriger un défaut constaté ; elle n’est pas réalisée.
La duplication concrète de politique de chemin entre présence template et vue source est supprimée. Les constantes de bornes sont extraites dans `forge_design/limits.py` : 1 Mio, 4096 caractères, recherche 256, 64 branchements, diagnostic Jinja 240, profondeur 8, références 128.
Les symboles de limites importés dans routes restent disponibles pour les tests existants.
Les lecteurs restent distincts : analyse sur sources déjà déterminées et vue source recevant un paramètre HTTP non fiable. Le second exige le parcours par descripteurs sans repli ; ils partagent les bornes mais ne sont pas fusionnés au prix d’un affaiblissement.

## Revue des modèles

Modèles gelés et tuples conservés, valeurs par défaut inchangées, aucune migration d’API.
Les tests complets vérifient les résultats du producteur : référence source relative, absence de chemin résolu pour un statut autre que found, syntaxe non applicable si absent, arêtes de cycle réellement connues et extrémités de graphe existantes.
Les dataclasses demeurent des conteneurs typés, pas des validateurs universels de constructions manuelles. Cette limite et le contrat des consommateurs sont documentés ; aucune validation intrusive ne casse les constructions historiques.
Les API examinées et stabilisées sont listées dans la documentation utilisateur : read_routes, RoutesResult, RouteInfo, HandlerInfo, TemplateResolution, TemplateDependencyGraph, RouteExplorerTool, build_route_diagnostics, build_route_graph et layout_route_graph.

## Revue sécurité

Racine canonicalisée par le résolveur existant ; détecteur structurel sans lecture de config/bootstrap. Les sources de routes restent explicitement branchées, les contrôleurs directement importés, les templates confinés à mvc/views.
La politique lexicale commune refuse avant consultation des cibles : traversal, absolu, segments vides/cachés, antislash, deux-points, NUL, longueur excessive, segment env, suffixes .pem/.key et préfixes de clés SSH id_rsa/id_dsa/id_ecdsa/id_ed25519. Les catégories sensibles ajoutées sont comparées sans tenir compte de la casse.
Les tests placent des secrets à la racine et sous les vues. Les derniers sont volontairement référencés comme principaux et dépendances : aucun contrôle de leurs métadonnées ni ouverture n’est permis, et /source les refuse également.
Les noms ordinaires ne permettent pas de reconnaître sémantiquement un secret : aucun scanner de contenu n’est revendiqué.
Liens et fichiers spéciaux restent refusés, lecture bornée UTF-8/BOM et identité du descripteur contrôlée. L’analyse conserve sa limite de parents stables ; /source les ancre par descripteurs. Pas de promesse d’instantané atomique.
Les sentinelles du test global bloquent exec, eval, import dynamique, sous-processus et scan pendant le pipeline. Seules les ouvertures explicites autorisées passent. Le module de diagnostic Jinja est préchargé avant ces sentinelles pour ne pas confondre l’import de la bibliothèque installée avec l’exécution du projet.
Ensemble des fichiers, tailles, octets et mtime sont comparés sur les fixtures et dans le contrôle HTTP installé.

## Revue diagnostics

Codes, sévérités, ordre, sources et associations de routes inchangés. Les tests existants vérifient leur déduplication et les nouveaux scénarios cassés vérifient les codes réellement produits par le Bridge.
Les warnings historiques et route.partial restent conservés : le résumé global ne remplace pas les détails non structurés. Les répétitions entre tableau, diagnostics et cycles sont contextuelles ; aucune suppression de faits ni migration implicite.

## Revue graphe et layout

Constructeurs purs inchangés, graphe transitif et marquage des cycles issus des seules données connues.
Les tests existants couvrent vide, troncature, partage, ordre, déduplication et cycles. Les tests complets ajoutent les invariants d’extrémités et le graphe réellement produit.
Trois scénarios de 10, 20 et 100 routes partagent un handler, un contrôleur et huit templates, avec retour cyclique. Déterminisme, terminaison, rectangles disjoints, coordonnées dans le viewBox et dimensions inférieures à 5000 × 20000 sont vérifiés. Ce n’est pas un jugement esthétique ni un benchmark.

## Revue Web

Quatre projets consultés sans exécuter JavaScript : tableau, diagnostics, SVG et relations textuelles. Filtres combinés vérifiés sur les trois variantes applicatives. Sources suivies, fermeture puis refus de source sans projet vérifiés.
La suite existante conserve les assertions d’analyse unique par GET et de filtrage pur. Les tests source historiques couvrent suppression, ligne périmée, traversal et HTML hostile ; cinq nouveaux cas HTTP complètent liens fichier/parent, taille excessive, encodage invalide et fichier .key.
Les réponses restent explicites, sans traceback ni contenu sensible, avec no-store.

## Revue JavaScript

Script inchangé : sélection et voisinage directs dans le DOM, textContent, aucune requête, stockage, innerHTML ou eval. Les contrats statiques et le double DOM Node restent exécutés.
CSP HTTP vérifiée : script-src 'self', aucun unsafe-inline. CSS/JS locaux distribués ; sans script, les informations essentielles restent dans l’HTML.
Aucun navigateur réel utilisé ; focus SVG et annonces d’assistance conservent cette limite de validation.

## Compatibilité Forge vérifiée

`git ls-remote https://github.com/caucrogeGit/Forge.git refs/heads/main` confirme `73a956e587e5f169c028415e0e540c149cbaff56`, identique au checkout local inspecté.
Sources revues : squelette mvc/routes/__init__.py et HomeController, core/http/router.py (add/group), core/mvc/controller/base_controller.py (render), config.py et app_factory.py (VIEWS_DIR et renderer), integrations/jinja2/renderer.py et pyproject.toml.
Jinja2 3.1.6, environnement sans extension syntaxique spécifique ni StrictUndefined ; globals Forge et autoescape relèvent du rendu. Le parser sans loader reste compatible avec cette baseline.
Le squelette fournit / et /charte, HomeController.index/charte et les références home/index.html et pages/charte.html.
Opt-ins non résolus, sous-paquets contrôleurs dont pivot non suivis, VIEWS_DIR personnalisé non chargé : limites testées ou maintenues et documentées. Aucune adaptation à une version hypothétique.

## Bugs identifiés

La présence template utilisait une politique différente de la vue source. Un chemin caché ou un fichier de clé placé sous mvc/views pouvait être accepté pour parsing ; la vue source autorisait aussi les extensions de clés non cachées. Les templates ne partageaient pas la limite lexicale de chemin de 4096 caractères.

## Bugs corrigés

La présence des templates appelle désormais source_parts, comme la navigation source. Les noms sensibles sont refusés par cette politique commune avant accès ; présence invalid-path et syntaxe not-applicable, sans lien source ouvrable. Références et diagnostics existants restent disponibles.
Neuf cas de régression vérifient le refus de références principales et dépendantes, y compris fichier .KEY, .env.prod, .git, .ssh, env et clés SSH non cachées. Le refus HTTP d’un fichier .key présent est également vérifié.

## Refactorisations réalisées

Extraction des bornes dans un module indépendant et réutilisation du validateur lexical existant. Ces modifications répondent à une duplication réelle et à un défaut de sécurité, sans déplacement massif de code ni changement de signatures publiques.
Aucune nouvelle dépendance, ressource frontend ou métadonnée de distribution.

## Tests de consolidation ajoutés

25 nouveaux cas : quatre pipelines complets, neuf refus de secrets référencés, trois tailles de layout, quatre parcours HTTP des projets et cinq refus source HTTP.
La fabrique contrôlée dans tests/test_route_explorer_stability.py est réutilisée par les tests HTTP et la préparation des projets du contrôle installé. Les tests historiques restent tous actifs.
Les constructions non prises en charge comprennent import dynamique, alias de branchement, sous-paquet de routes et contrôleurs, handler factory, template calculé, route conditionnelle et opt-ins. Les routes non interprétées ne sont pas inventées.

## Test sur squelette Forge

La fixture minimale reprend les formes de la baseline, avec sentinelles d’exécution et deux templates simples.
Le contrôle installé copie également le véritable skeleton/data de Forge dans un répertoire temporaire : /, /charte, références HomeController et templates sont affichés. Ses liens source réels sont extraits de l’HTML et suivis.
Le dépôt Forge de référence reste inchangé.

## Test sur projet représentatif

Plusieurs modules de routes et contrôleurs, GET/POST, public/protégé, dépendances partagées, chaîne transitive et cycle, handler et template dynamiques.
Les filtres q=contact, method=GET et visibility=public ne gardent que /contact/list, avec cohérence tableau/graphe ; le graphe non filtré contient macros/forms.html atteint transitivement.
Les sentinelles rendent impossible une exécution de routes/contrôleurs/config/bootstrap ; les expressions de templates restent inertes.

## Test sur projet dégradé

Le projet produit controller.missing, controller.method_missing, template.missing, template.syntax_invalid, template.dependency_missing et template.cycle, avec les faits dynamiques conservés.
Bridge et HTTP terminent normalement, sans traceback utilisateur ni modification de fichiers. Les liens source réellement proposés restent consultables.

## Packaging

Wheel finale construite et inspectée : cinq templates, CSS, route-graph.js et modules Python, dont limits.py. Aucun fichier tmp/ ou tests/ dans l’archive.
Installation --no-deps --no-index --target dans un répertoire temporaire ; processus Python -I avec origine de Forge Design vérifiée, dépendances runtime fournies par .venv.
Artefact : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `5e85fc96086d78dcad1fefb4ac60cee0db034d821456c3ada43991041fe049f5`.

## Test HTTP complet

Depuis la wheel : démarrage sur port local éphémère ; pour chaque variante ouverture, /routes, diagnostics, graphe, cycles, filtres applicables, sources extraites de l’HTML, état vide, JS, CSS, fermeture et refus de source sans projet.
No-store, CSP, MIME JavaScript, absence de script inline et instantané de fichiers identique vérifiés. Arrêt du thread, fermeture du socket et réutilisation du port vérifiés.
Script et journal ignorés par Git : tmp/verify_fd_routes_020.py et tmp/verify_fd_routes_020.log.

## Documentation

Création de [docs/tools/route-explorer.md](../tools/route-explorer.md) : usage, tableau, diagnostics, graphe, filtres, sources, baseline, bornes, API stables et limites.
[docs/02-architecture.md](../02-architecture.md) est corrigé uniquement sur le contrat de chemins désormais partagé et les bornes centralisées.
Fichiers de production modifiés : forge/routes.py, forge/source.py, tools/route_filters.py ; nouveau limits.py. Tests ajoutés ou enrichis : test_route_explorer_stability.py, test_route_graph_layout.py et test_web_inspector.py.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| État Git, historique, Forge main et sources de référence | Vérifiés |
| pytest | 546 réussis, dont 25 nouveaux cas |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip check | No broken requirements found |
| node --check forge_design/web/static/route-graph.js | Succès |
| Double DOM Node via pytest | Succès |
| git diff --check | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Installation isolée et quatre parcours HTTP | Succès |

Outils de .venv, Python 3.13.5, Node v24.18.0 ; sockets locaux autorisés hors sandbox.
Les premiers contrôles des nouveaux tests ont révélé un nom de fonction de filtre erroné, le chargement paresseux de jinja2.debug sous sentinelle et une mauvaise URL de fermeture ; les fixtures/tests ont été corrigés avant validation finale. Imports et formatage ont été corrigés avec Ruff. Pip a désactivé son cache utilisateur inaccessible sans erreur de dépendances.
Diff complet, nouveaux fichiers et documentation relus avant commit.

## Tests sautés

Aucun test pytest sauté. Aucun contrôle visuel navigateur, rendu de template cible ou nouvelle génération Forge revendiqué. Les tests JS utilisent le double DOM existant, pas un moteur SVG.

## Limites finales de Route Explorer

Analyse syntaxique structurelle, pas preuve runtime. Portées/réaffectations dynamiques, routes conditionnelles, opt-ins, sous-paquets et configuration alternative ne sont pas interprétés. Bornes 8/128 et 64 branchements, fichiers 1 Mio ; résultats potentiellement partiels.
Cycles témoins et identités syntaxiques ; handlers homonymes potentiellement mutualisés et métadonnées de première occurrence. Layout déterministe mais croisements possibles.
La politique de noms sensibles ne détecte pas un secret déguisé sous un nom de vue ordinaire. Les parents d’analyse doivent rester stables et les liens source peuvent devenir périmés. Aucun verdict de validité runtime, écriture ou correction automatique.

## Tickets futurs identifiés

Durcissement des lecteurs d’analyse contre les remplacements concurrents de parents ; portée d’identité des handlers homonymes ; prise en charge de conventions Forge supplémentaires ; revue visuelle et accessibilité SVG dans un navigateur réel. Aucune de ces extensions n’est implémentée opportunément ici.

## État Git final

Un seul commit local sur main, rapport et documentation inclus, sans push.
Message : `refactor: stabiliser Route Explorer (FD-ROUTES-020)`.
Le hash et l’état final vérifiés sont communiqués dans la réponse de livraison.
