# Route Explorer

Route Explorer analyse statiquement les routes d’un projet Forge, sans exécuter
le projet. Il relie les routes aux handlers, contrôleurs, méthodes et templates,
puis examine leurs dépendances Jinja. Il expose diagnostics, graphe, cycles,
sources, filtres et sélection locale dans le graphe.

## Utilisation

Ouvrir le projet avec Project Inspector, puis choisir **Route Explorer**.
Chaque GET relit le projet courant ; les résultats ne sont pas persistés.
Les fichiers du projet ne sont jamais modifiés.

Le tableau présente méthode et chemin HTTP, référence syntaxique du handler,
fichier contrôleur, vérification de méthode, template, présence, syntaxe Jinja,
nom et caractère public. « — » signifie non applicable ou non résolu, pas
nécessairement absent. « Trouvée » désigne une définition directe de méthode :
l’héritage et les effets des décorateurs ne sont pas évalués.

« Présent » confirme un fichier ordinaire dans l’espace conventionnel des vues.
« Valide » confirme seulement son parsing Jinja, sans rendu ni validation HTML.
Une variable ou un filtre inconnu peut donc être syntaxiquement valide.

## Diagnostics et cycles

Les erreurs signalent des relations statiques cassées, chemins refusés, erreurs
Jinja ou cycles connus. Les avertissements décrivent une incertitude ou une limite.
Les compteurs ne constituent ni un score ni un verdict sur le projet.

Les avertissements historiques conservent leurs détails ; le diagnostic
`route.partial` rappelle leur présence sans les reclassifier. Une information
peut apparaître dans le tableau, les diagnostics et la section des cycles pour
permettre sa lecture dans chaque contexte.

Les cycles sont des témoins orientés trouvés dans les relations connues, pas
l’énumération de tous les cycles possibles. Une analyse tronquée peut masquer
d’autres cycles.

## Recherche et filtres

La recherche textuelle, insensible à la casse, porte sur méthode, chemin, nom,
handler, contrôleur et template principal. Elle ne recherche pas dans le contenu
des fichiers ou les dépendances. Méthode, visibilité, sévérité et présence de
diagnostics peuvent être combinées. Le bouton de réinitialisation enlève les
critères. Les paramètres sont dans l’URL GET.

Le tableau et le graphe utilisent les routes retenues. Les diagnostics globaux
(cycles, limites, analyse partielle) peuvent rester visibles même sans route
correspondante. Une analyse unique du projet alimente chaque GET ; filtrer ne
relance pas une seconde analyse dans cette requête.

## Graphe

Le SVG représente les relations connues, y compris les dépendances transitives.
Les nœuds partagés sont mutualisés et les arêtes de cycles connues sont signalées.
Les labels longs sont abrégés ; leur texte complet reste accessible.

Cliquer sur un nœud ou utiliser Entrée/Espace affiche ses détails et souligne
ses relations directes. Échap ou Désélectionner efface ce choix. Cette interaction
locale n’émet aucune requête et n’enregistre rien. Sans JavaScript, tableau,
diagnostics, sources, SVG et relations textuelles restent disponibles.
Il n’y a ni zoom, ni déplacement, ni édition.

## Sources

Le détail **Sources** ouvre une page interne en lecture seule. Une ligne connue
est montrée avec vingt lignes de contexte de chaque côté. Si elle n’existe plus,
le fichier borné est affiché avec un message. Le fichier est relu à l’ouverture :
un lien peut donc devenir périmé ou concerner le nouveau projet courant.

Seuls les fichiers Python directement sous `mvc/routes` et `mvc/controllers`,
et les fichiers autorisés sous `mvc/views`, sont consultables. Aucun explorateur
général, scan ou lancement d’éditeur n’est proposé. Les traversals, liens,
fichiers spéciaux, chemins cachés, segments `env`, extensions `.pem`/`.key`
et noms commençant par `id_rsa`, `id_dsa`, `id_ecdsa`, `id_ed25519`
sont refusés. Cette politique lexicale est aussi appliquée aux templates analysés.
Elle ne reconnaît pas un secret caché sous un nom de template ordinaire.

## Compatibilité et limites

Baseline vérifiée : Forge main
[`73a956e587e5f169c028415e0e540c149cbaff56`](https://github.com/caucrogeGit/Forge/tree/73a956e587e5f169c028415e0e540c149cbaff56),
Jinja2 3.1.6, dépendance Forge Design `forge-mvc==1.0.0rc9`.
C’est une compatibilité structurelle vérifiée, pas une matrice de versions.

- Racine `mvc/routes/__init__.py`, déclarations littérales `add` et `group`.
  Les modules directs importés par `from mvc.routes.module import register_x_routes`
  et appelés explicitement sont suivis ; un import seul ne suffit pas.
- Les routes conditionnelles ou dynamiques peuvent manquer. Les alias de
  branchements, imports relatifs et sous-paquets ne sont pas résolus.
  `register_optins(router)` reste non résolu et signalé.
- Les imports de contrôleurs directs peuvent avoir un alias. Les sous-paquets
  comme `mvc.controllers.pivot.*` ne sont pas suivis. Les références syntaxiques
  ne prouvent pas l’identité runtime des symboles ; les portées et réaffectations
  dynamiques ne sont pas interprétées.
- Seul `BaseController.render` avec chemin littéral est reconnu.
  `VIEWS_DIR` personnalisé, configuration, environnement cible, extensions Jinja
  personnalisées et loaders d’opt-ins ne sont pas chargés.
- Les dépendances statiques sont analysées sous `mvc/views`, sans rendu.
  Les expressions dynamiques restent non résolues. Les branches non exécutables
  à l’exécution peuvent néanmoins fournir des déclarations syntaxiques.
- Les contrôles d’analyse supposent les parents filesystem stables. La vue
  source ancre son parcours dans des descripteurs et exige `dir_fd/O_NOFOLLOW`,
  sans repli moins sûr. Aucun lecteur ne garantit un instantané atomique du contenu.
- Les identités du graphe sont syntaxiques ; deux handlers homonymes peuvent être
  fusionnés. Les premières métadonnées prévalent. Les grands graphes nécessitent
  du défilement ; croisements et segments partagés restent possibles.

### Bornes internes

| Contrôle | Limite |
|---|---|
| Chaque source route, contrôleur, template ou vue source | 1 Mio, UTF-8/BOM |
| Branchements directs de routes | 64 |
| Profondeur template, principal à 0 | 8 |
| Références templates distinctes par analyse, échecs inclus | 128 |
| Recherche `q` | 256 caractères |
| Chemin source complet, templates compris | 4096 caractères |
| Message syntaxique Jinja | 240 caractères, une ligne |

Ces valeurs sont centralisées dans `forge_design/limits.py`. Les caches sont
locaux à l’appel. Les bornes produisent une analyse explicitement partielle ;
un statut non applicable à la limite ne signifie pas absence.

## Contrats Python stabilisés

| API | Contrat maintenu |
|---|---|
| `read_routes(root) -> RoutesResult` | Analyse statique bornée ; racine invalide, source principale absente/illisible : exceptions explicites |
| `RoutesResult`, `RouteInfo`, `HandlerInfo`, `TemplateResolution`, `TemplateDependencyGraph` | Dataclasses gelées, tuples immuables, champs optionnels avec valeurs par défaut compatibles |
| `RouteExplorerTool.run(Path)` | Façade du Bridge, aucun état ou cache persistant |
| `build_route_diagnostics(result)` | Transformation pure, codes et ordre déterministes |
| `build_route_graph(result)` | Transformation pure des relations déjà connues, extrémités présentes |
| `layout_route_graph(graph)` | Présentation pure, identifiants uniques et extrémités existantes exigés |

Les fonctions de production maintiennent les invariants de statuts et de chemins.
Les dataclasses restent des conteneurs typés : elles ne valident pas toute
construction manuelle contradictoire. Les consommateurs doivent recevoir les
résultats cohérents du Bridge, et les filtres les diagnostics du même résultat.
Les helpers préfixés `_`, coordonnées et détails DOM restent internes.
Aucun engagement de validité runtime n’est attaché à ces contrats.

## Suites possibles

La prise en charge d’autres conventions Forge, la distinction des handlers
homonymes, un lecteur d’analyse résistant aux remplacements concurrents des
parents et la validation visuelle/accessibilité dans un navigateur réel relèvent
de tickets distincts. Ils ne sont pas implicitement couverts par cette version.
