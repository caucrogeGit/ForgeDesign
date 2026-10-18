# Route Explorer

Route Explorer analyse statiquement les routes d’un projet Forge, sans exécuter
le projet. Il relie les routes aux handlers, contrôleurs, méthodes et templates,
puis examine leurs dépendances Jinja. Il expose diagnostics, graphe, cycles,
sources, filtres et sélection locale dans le graphe. Seule l’action explicite
« Prévisualiser réellement » d’une route éligible exécute le projet, par la
preview réelle (FD-REALPREVIEW-008, voir plus bas).

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

## Chaînes des routes

FD-ROUTES-021 : la section « Chaînes des routes » relie, pour chaque route
affichée, ce que l’analyse statique connaît déjà : route → handler → contrôleur
et méthode → template(s) → contrat(s) de vue → diagnostics. Chaque route est un
élément `<details>` : le résumé donne la chaîne compacte et son état, le détail
les faits, sources, liens et diagnostics. Tout est lisible sans JavaScript ; les
filtres de la page s’y appliquent.

| Élément | Valeurs |
|---|---|
| Handler | Méthode de contrôleur, fonction (non analysée), référence non résolue (aucun import de contrôleur), handler dynamique |
| Contrôleur | Résolu, fichier absent, classe absente, méthode absente, ambigu, non vérifiable, non applicable |
| Template | **Exact** (un seul `render` littéral), **plusieurs possibles** (plusieurs littéraux), **partiel** (des littéraux et au moins un rendu non déterminable), **non déterminable statiquement**, **aucun rendu détecté** (ce n’est pas une preuve d’absence de template), non applicable (méthode non résolue) |
| Contrat de vue | Contrat associé, plusieurs contrats (ambigu), aucun contrat (optionnel), liaison inconnue, non applicable (template non présent) |
| État de la chaîne | **Complète** : méthode résolue, template exact présent, aucune erreur ; **problématique** : au moins une erreur démontrée ; **partielle** : tous les autres cas |

Les littéraux de `render` sont conservés comme candidats, dans l’ordre de la
source, avec leur présence ; syntaxe et dépendances ne sont analysées que pour un
template exact. Aucune convention de nom n’est utilisée : une route n’atteint un
contrat que par un template qu’elle rend. Un contrat invalide n’a pas de cible
lisible : il figure dans la section « Contrats de vue » de la page, jamais dans
la chaîne d’une route ; une route sans contrat le signale seulement par une
mention contextuelle.

Chaque diagnostic d’une chaîne garde son code, sa sévérité, son message et son
origine (route, handler, contrôleur, template, dépendance, contrat), dérivée du
code. Ce sont les diagnostics existants de la page, plus les anomalies de liaison
des contrats des templates de la route (avertissements). Une incertitude
statique reste un avertissement, jamais une erreur.

Liens : contrôleur, classe, méthode et contrat vers la vue source en lecture
seule ; template présent vers Template Viewer (`/templates/view?path=…`).

Par affichage, l’inventaire des templates (Template Viewer) et l’analyse des
liens contrats ↔ templates sont faits une fois, puis indexés par chemin : aucune
relecture par route. L’analyse des contrats vérifie la racine Forge une seule fois
et la transmet à ses lecteurs (FD-PERF-001) ; chaque fichier de contrat reste
ouvert de façon confinée.

## Preview réelle depuis une route

FD-REALPREVIEW-008 : Route Explorer est le second point d'entrée de la preview
réelle, **sans Design ni contrat de vue**. Le contrat complet, avec les deux
parcours, les protections et les raisons, est dans
[Preview réelle — contrat](../preview/real-preview-contract.md#deux-parcours-daccès-fd-realpreview-008).

- Chaque chaîne porte `data-real-preview="available|unavailable"`. Une route
  éligible est marquée « prévisualisable » dans son résumé et offre, dans son
  détail, l'avertissement d'exécution réelle et le bouton **Prévisualiser
  réellement**. Une route non éligible n'a aucune action, seulement sa raison.
- Une route est éligible si elle satisfait toutes ces conditions :
  - GET, chemin statique, publique ;
  - méthode de contrôleur vérifiée, handler non dynamique ;
  - template **exact** et présent sur disque ;
  - identité `GET <chemin>` non ambiguë.

  Une route de chaîne « partielle » faute de présence vérifiée (borne de
  templates) n'est pas éligible.
- L'action est un `POST` explicite. Le serveur relit l'inventaire, retrouve la
  route par égalité exacte et recalcule son éligibilité avant tout démarrage.
  La page `/routes/real-preview?route=…` montre l'état, l'iframe et Stop.
- **Ce n'est plus de la lecture seule** : démarrer exécute réellement
  l'application du projet, comme depuis l'éditeur. Tout le reste de Route
  Explorer reste statique : les GET ne démarrent jamais rien.

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
  `register_optins(router)` est reconnu uniquement pour le registre vide
  conventionnel : `BACKEND = None`, `ENABLED_OPTINS = {}` et fonction sans
  effet (`return None`), selon la structure typée du squelette Forge 1.0.0rc9.
  L'import direct, la création du routeur et l'appel inconditionnel unique
  doivent être non ambigus et dans l'ordre. Le registre est lu sans import,
  avec une taille bornée et sans suivre les liens symboliques.
  Un registre actif, personnalisé, illisible, absent malgré une référence,
  ou un branchement manquant/incorrect reste signalé. Les projets historiques
  sans registre ni référence aux opt-ins gardent leur diagnostic antérieur.
  La reconnaissance syntaxique ne garantit ni l'installation des paquets,
  ni leur identité à l'exécution ; la limite générale de lecture statique reste
  affichée. Voir [FD-ACC-002](../rapports/FD-ACC-002-RAPPORT.md).
- Les imports de contrôleurs directs peuvent avoir un alias. Les sous-paquets
  comme `mvc.controllers.pivot.*` ne sont pas suivis. Les références syntaxiques
  ne prouvent pas l’identité runtime des symboles ; les portées et réaffectations
  dynamiques ne sont pas interprétées.
- Seul `BaseController.render` avec chemin littéral est reconnu ; plusieurs
  littéraux dans une méthode sont tous gardés comme candidats, sans interpréter
  les branches.
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
| `TemplateResolution.candidates`, `TemplateCandidate` | Littéraux de `render` dans l’ordre de la source, avec présence ; ajout compatible (statut inchangé) |
| `build_route_linkage(result, diagnostics, links)` | Transformation pure : chaîne, confiance, contrats par template, diagnostics avec origine, état |
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
