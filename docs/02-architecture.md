# Forge Design — Architecture V2

## 1. Principe

Forge Design est une **application locale à interface Web**.

Le navigateur fournit l'interface graphique.
Le backend Python porte la Platform, assemble les Tools et contrôle tout accès au projet Forge.

Architecture logique :

```text
┌───────────────────────────────┐
│          Navigateur Web       │
│   http://127.0.0.1:<port>     │
└───────────────┬───────────────┘
                │ HTTP local
┌───────────────▼───────────────┐
│        Forge Design UI        │
└───────────────┬───────────────┘
                │
┌───────────────▼───────────────┐
│  Backend Python / composition │
│  assemble explicitement       │
│  Platform, Tools et Bridge    │
└───────┬───────────────┬───────┘
        │               │
        ▼               ▼
┌──────────────┐  ┌──────────────┐
│   Platform   │  │    Tools     │
└──────────────┘  └──────┬───────┘
                         │ reçoit
                         │ les services
                         ▼
                  ┌───────────────┐
                  │ Forge Bridge  │
                  └───────┬───────┘
                          ▼
                    Projet Forge
```

Forge Core ne dépend jamais de Forge Design.

Le navigateur ne lit ni n'écrit directement les fichiers du projet.
Toute opération passe par le backend Python.

## 2. Serveur Web local

Le serveur Forge Design est local-first.

Comportement par défaut :

```text
host = 127.0.0.1
exposition réseau = non
accès filesystem depuis navigateur = non
```

Une commande future pourra lancer le serveur et ouvrir automatiquement le navigateur.

Exemple cible, non contractuel tant que la CLI correspondante n'est pas implémentée :

```text
forge-design
→ démarre le backend local
→ affiche l'URL locale
→ ouvre éventuellement le navigateur
```

Une option telle que `--no-browser` pourra être étudiée dans un ticket CLI dédié.

Une écoute sur `0.0.0.0`, une connexion distante ou une exposition publique ne font pas partie du comportement par défaut.
Elles nécessitent une conception de sécurité dédiée.

### Backend Forge disponible (FD-WEB-002)

Forge Design est lui-même une application Web construite avec Forge.
`forge_design.web.server.create_application()` assemble les API publiques
`Application`, `Router` et `Response` de `forge-mvc`.
L'adaptateur officiel `create_wsgi_app` reçoit cette application ;
`wsgiref.simple_server` fournit uniquement le transport local WSGI.
C'est l'unique voie HTTP : l'ancien gestionnaire HTTP spécifique est supprimé.

`create_server(host="127.0.0.1", port=8765)` ouvre l'écoute sans lancer la boucle ;
`run_server` sert jusqu'à Ctrl+C puis ferme le socket.
Seul `127.0.0.1` est accepté ; le port `0` demande un port éphémère.
Les erreurs de port occupé restent des `OSError`, sans repli automatique.
Le cycle piloté reste `serve_forever` dans un thread, `shutdown` depuis un autre
thread, puis `join` et fermeture du serveur.
Le transport standard n'hérite pas du délai d'inactivité de l'ancien gestionnaire.

`GET /` conserve le shell HTML « Aucun projet ouvert. ».
`GET /shell.css` sert une unique ressource CSS explicitement nommée : les styles
ont été extraits du HTML pour respecter `style-src 'self'` de Forge, sans assouplir
sa CSP. Les ressources sont packagées et chargées via `importlib.resources`.
Les deux pages utilisent le renderer Jinja public de Forge et héritent de `layout.html`.
Ce layout partage le head, la navigation sémantique et le conteneur principal.
Les liens fixes Accueil et Project Inspector utilisent un état actif explicite
(`aria-current` et soulignement), sans consulter le registre pour la navigation.
Les erreurs et en-têtes de sécurité relèvent de Forge.
La sonde `/health` est fournie nativement par son adaptateur WSGI.
Les paramètres de requête suivent le parsing Forge ; ils ne sélectionnent aucun projet.

La dépendance runtime est épinglée à `forge-mvc==1.0.0rc9`, préversion publiée
vérifiée pour cette migration. Sa mise à jour devra être validée explicitement.
Cette version sert à exécuter Forge Design ; elle ne détermine pas la version
déclarée d'un projet cible, toujours lue indépendamment par le Bridge.
Forge Core ne dépend pas de Forge Design et n'est pas modifié.
Aucun `config.py`, `bootstrap.py` ou module `mvc` du répertoire courant n'est chargé
par la composition Web. Seul un POST explicite à `/inspector` exécute le Tool Inspector.
La CLI reste inchangée ; aucun navigateur n'est ouvert automatiquement.

### Project Inspector Web disponible (FD-UI-002)

`GET /inspector` affiche un formulaire vierge ; `POST /inspector` inspecte le
chemin soumis et affiche racine canonique, validité, version, source et diagnostics.
Chaque application construit son registre via `create_tool_registry()` ; le POST
appelle `registry.get("project-inspector").run(Path(path))`.
La couche Web ne résout pas le chemin et ne lit pas le projet directement.
Elle vérifie le résultat `ProjectInspection` après le retour typé `object` du registre.

Le champ est obligatoire, limité à 4096 caractères, sans suppression silencieuse
d'espaces ni expansion de chemin. Les trois erreurs attendues de racine sont
rendues en HTML avec statut 400 ; les erreurs inattendues restent confiées à Forge.
Le template packagé `inspector.html` est rendu avec `Jinja2Renderer` et son
échappement automatique. Les réponses Inspector portent `Cache-Control: no-store`.
### Contexte projet courant (FD-PROJECT-001)

Chaque `create_application()` crée son propre `CurrentProjectContext` et le fournit
explicitement aux routes. Il conserve uniquement le dernier `ProjectInspection`
valide ; sa propriété `root` dérive de ce diagnostic canonique, sans dupliquer la valeur.
`set_project` et `clear` encapsulent les mutations. Aucun état global ni stockage
dans le registre n'est ajouté.

Un POST Inspector valide active ou remplace le projet courant, même sans version
connue. Une inspection invalide ou une erreur conserve le projet précédent.
Le shell commun affiche la racine et la version connue sur les deux pages.
`POST /project/close` vide le contexte et affiche l'accueil ; il ne ferme pas le serveur.
Toutes les pages contenant cet état sont servies avec `Cache-Control: no-store`.
Le contexte appartient à l'instance serveur, partagé par ses onglets clients,
et disparaît avec elle : aucune persistance, aucun cookie ni session ajouté.
Une nouvelle application démarre vide. Le diagnostic n'est pas rafraîchi en arrière-plan.
`POST /project/refresh` (FD-PROJECT-002) réinspecte explicitement `context.root`
via `registry.get("project-inspector").run(root)`, sans chemin fourni par HTTP.
Un résultat valide remplace le diagnostic et affiche « Projet actualisé. ».
Un résultat invalide vide le contexte et affiche ses erreurs (200) ; une erreur
attendue de racine le vide également avec un message (400). Sans projet : 409.
Cette action applique le même contrôle d'origine et `no-store` que la fermeture.

Activation et fermeture modifient maintenant l'état runtime. La politique a été
réévaluée : le CSRF Forge rc9 dépend d'une session ; les POST de mutation utilisent ici
un contrôle strict d'origine sans session, avec `csrf=False` explicitement déclaré.
Avant toute mutation, `Origin` doit égaler exactement `http://` suivi du Host
local `127.0.0.1[:port]`, et `Sec-Fetch-Site`, s'il existe, doit valoir `same-origin`.
Les origines absentes, nulles ou étrangères sont refusées avec 403.
Ce contrôle protège contre les soumissions de pages étrangères dans un navigateur ;
il n'authentifie pas les programmes locaux capables de fabriquer leurs en-têtes.
Le GET ne ferme jamais le projet. Le formulaire Inspector conserve son contrôle de
contenu `application/x-www-form-urlencoded`. Aucun middleware global n'est désactivé.

Le frontend peut évoluer progressivement :

```text
socle
→ HTML / Jinja / Tailwind / HTMX / Alpine.js

Tools spécialisés, si nécessaire
→ SVG / Canvas / WebGL / Three.js / bibliothèque ciblée
```

Un choix frontend propre à Circuit, Network ou 3D ne doit pas devenir une dépendance obligatoire de tous les Tools.

## 3. Point de composition

Les implémentations concrètes sont assemblées explicitement par
`forge_design.app.create_tool_registry()`.

Un Tool ne doit pas aller rechercher lui-même un Bridge global, un singleton ou un service caché.

Principe :

```text
l'application construit
→ les services
→ le contexte
→ le Tool
```

Cela garde les dépendances visibles et facilite les tests.

Chaque appel crée un nouveau `ToolRegistry` et une nouvelle instance de
`ProjectInspectorTool`, enregistrée explicitement sous `project-inspector`.
`RouteExplorerTool` est également enregistré sous `route-explorer` ; ce sont les deux Tools intégrés. La fonction retourne le registre sans
exécuter le Tool ni accéder à un projet.

`forge_design/app.py` porte ce choix d'application, au-dessus de la Platform et
des Tools. Il n'existe pas d'instance globale de registre, de singleton ou de
découverte automatique. Modifier un registre retourné n'affecte pas les autres.
Ce point de composition ne démarre aucun serveur et n'est pas encore relié à la CLI.

## 4. Platform

Responsabilité :

> fournir uniquement le socle commun réellement partagé entre plusieurs capacités.

La Platform peut progressivement porter :

- configuration ;
- contexte local ;
- contrats communs ;
- registre des Tools ;
- erreurs communes.

Elle ne connaît pas :

- les détails électriques de Circuit ;
- les détails géométriques de 3D ;
- les règles métier de SéquenCiel ;
- les détails internes d'un moteur spécialisé.

## 5. Forge Bridge

Responsabilité :

> comprendre un projet Forge réel sans exécuter arbitrairement l'application cible.

Il fournit des opérations étroites et testables.

Exemples futurs :

```text
detect_project(root)
read_forge_version(root)
scan_project(root)
run_allowed_command(root, command)
```

Les noms définitifs sont décidés dans les tickets.

Le Bridge ne fournit pas un explorateur de fichiers générique incontrôlé.

## 6. Tools

Un Tool fournit une capacité utilisateur identifiable.

Un Tool dépend de contrats étroits ou de services qui lui sont fournis explicitement.

Le Tool ne dépend pas directement :

- d'un singleton global ;
- d'un moteur spécialisé non abstrait lorsque plusieurs implémentations sont possibles ;
- de l'état interne de l'UI.

### Contrat actuellement implémenté (FD-PLATFORM-001)

`forge_design.platform.tool.Tool[Result_co]` est un `Protocol` structurel minimal.
Il expose trois propriétés en lecture seule : `id` (stable, kebab-case), `name`
(nom affiché) et `description` (responsabilité courte), ainsi que
`run(project_root: Path) -> Result_co`, synchrone et en lecture seule.
Le résultat reste propre à chaque Tool ; aucune enveloppe universelle n'est imposée.
La validation de racine appartient à l'implémentation via le Bridge et les erreurs
métier restent propagées. Le protocole ne réalise aucun accès au projet.

`ProjectInspectorTool` fournit l'identifiant `project-inspector` et le nom
`Project Inspector`. Ses métadonnées sont gelées et non paramétrables à la
construction. Sa méthode `run` délègue directement à `inspect_project` et retourne
`ProjectInspection`, sans changer la logique métier.

La conformité est vérifiée statiquement par Pyright, sans héritage obligatoire ni
test `isinstance` du protocole. Le kebab-case, la stabilité des identifiants et la
lecture seule sont des obligations du contrat, pas un mécanisme de contrôle à
l'exécution. Le registre explicite est décrit en section 12 ; aucun chargement de plugins n'est implémenté.

## 7. Arborescence cible progressive

```text
ForgeDesign/
├── forge_design/
│   ├── __init__.py
│   ├── cli.py
│   ├── platform/
│   ├── forge/
│   ├── tools/
│   └── ui/
├── docs/
├── tests/
├── README.md
├── pyproject.toml
└── .gitignore
```

Cette arborescence est une cible.

Un dossier n'est créé que lorsqu'un ticket lui attribue une responsabilité réelle.

## 8. Conventions de nommage techniques

```text
Produit          Forge Design
Dépôt            ForgeDesign
Distribution     forge-design
Package Python   forge_design
CLI              forge-design
Tool ID          kebab-case stable
Module Python    snake_case
```

Exemple :

```text
Nom affiché : Project Inspector
Tool ID     : project-inspector
Module      : project_inspector
```

## 9. Sécurité filesystem

### 8.1 Racine canonique

Toute session de travail possède une racine projet résolue canoniquement.

Toute cible lue ou écrite doit pouvoir être ramenée à cette racine.

### 8.2 Symlinks

Le scanner de base ne suit pas un symlink permettant de sortir de la racine projet.

Un comportement différent nécessite un contrat explicite.

### 8.3 Secrets

Le scanner structurel travaille d'abord sur noms, types, présence et métadonnées.

Il ne lit pas par défaut le contenu :

- `env/` ;
- `.env*` ;
- clés privées ;
- certificats privés ;
- fichiers explicitement sensibles.

Un lecteur spécialisé ne lit que le minimum nécessaire à sa responsabilité.

## 10. Stockage

### État utilisateur local

Préférences, cache et état UI sont stockés hors du projet Forge, dans un emplacement utilisateur adapté au système.

### État partagé Forge Design

Le namespace projet réservé est :

```text
.forge-design/
```

Il n'est pas créé pendant Project Inspector en lecture seule.

Aucun format sous `.forge-design/` n'est considéré stable avant un ticket dédié.

### Sources Forge

Les sources Forge restent inchangées jusqu'à l'arrivée d'un service d'écriture contrôlée.

## 11. Compatibilité Forge

Le Bridge cible des contrats testés, pas une arborescence imaginée.

La compatibilité combine :

- tests unitaires sur fixtures minimales ;
- test d'intégration contre un projet réellement généré par une version Forge supportée ;
- documentation de la version testée.

Voir `04-compatibilite-forge.md`.

## 12. Registre des Tools

`forge_design.platform.tool_registry.ToolRegistry` conserve des instances
fournies explicitement via `register(tool)` ; aucun Tool n'est préenregistré.
`get(tool_id)` retrouve l'instance et `list()` retourne un tuple instantané dans
l'ordre d'enregistrement. La collection retournée ne permet pas de modifier le
registre ; les instances restent celles fournies par l'appelant.

Les identifiants suivent `[a-z][a-z0-9]*(?:-[a-z0-9]+)*` : minuscules ASCII,
chiffres après la première lettre et segments séparés par un seul tiret.
Un identifiant invalide lève `ValueError`, un doublon `DuplicateToolError`
(sous-classe de `ValueError`) et une recherche inconnue `UnknownToolError`
(sous-classe de `KeyError`). Aucun doublon ne remplace l'instance existante.

Le registre utilise `Tool[object]` grâce à la covariance du contrat.
Le résultat métier spécifique est donc volontairement effacé lors d'une recherche
par identifiant ; aucun `Any`, cast ou résultat universel n'est nécessaire.
La stabilité de l'identifiant demeure une obligation du Tool après enregistrement.
Le registre ne copie pas, n'exécute pas et ne découvre pas les Tools.
`forge_design.app.create_tool_registry()` choisit explicitement les instances intégrées à enregistrer (section 3).

## 13. Outils spécialisés futurs

Architecture de principe :

```text
Forge Design
    ↓
Tool Circuit
    ↓
adaptateur
    ↓
moteur électrique
```

et :

```text
Forge Design
    ↓
Tool 3D
    ↓
adaptateur
    ↓
moteur 3D
```

Les dépendances lourdes restent attachées au Tool ou à un extra dédié.

## 14. Écriture

Lorsqu'elle sera introduite :

```text
lecture
→ validation
→ changement en mémoire
→ diff
→ décision utilisateur
→ écriture atomique
→ journalisation
```

Une écriture doit vérifier une seconde fois la cible canonique juste avant l'opération.

## 15. Qualité et tests

Les frontières importantes sont testables indépendamment :

```text
Forge Bridge
Project Inspector
Platform extraite
registre
chaque Tool
services d'écriture
UI critique
```

Les tests privilégient les contrats observables plutôt que les détails internes.


## Route Explorer (FD-ROUTES-001)

`GET /routes` utilise le contexte courant et récupère `route-explorer` dans le
registre. Sans projet, aucun Tool n'est exécuté. Chaque GET avec projet relit les
routes, sans modifier le contexte et avec `Cache-Control: no-store`.
La navigation reste fixe et inclut Route Explorer.

Le Bridge `read_routes` vérifie la racine et la reconnaissance structurelle puis
lit `mvc/routes/__init__.py` puis les fichiers directement sous `mvc/routes/`
explicitement importés et branchés depuis cette racine, sans liens symboliques.
Chaque source est bornée à 1 Mio ; au plus 64 branchements sont suivis.
Les résultats immuables contiennent méthode, chemin, nom optionnel et public.
La lecture statique reconnaît `router = Router()`, les appels littéraux `add`
et les groupes `with router.group(...) as ...` ; elle conserve l'ordre source.
Les listes de méthodes produisent une ligne par méthode.
Le troisième argument handler n'est jamais évalué. FD-ROUTES-002 ajoute un
`HandlerInfo(reference)` immuable au résultat : les noms simples et chaînes
attributaires ancrées sur un nom sont reproduits tels quels, y compris les alias.
FD-ROUTES-003 ajoute `controller_file` optionnel au handler, depuis les imports
explicites du même fichier de routes : `mvc.controllers.<module_simple>`, avec alias
acceptés. Le chemin relatif est confirmé par métadonnées avant toute lecture. Fichiers ou parents liés, fichiers absents et types
incorrects ne sont pas résolus et produisent un avertissement. Les imports des
sources différentes ne sont jamais mélangés. Sous-paquets et imports relatifs
restent hors contrat. La vérification directe de classe et méthode est décrite ci-dessous.
La page ajoute la colonne Contrôleur, sans lien.
Une expression dynamique conserve la route avec handler absent et un avertissement
de ligne ; la colonne Handler affiche alors « — ». Aucun lien ou graphe ajouté.

Forge `routes:list` et `Router.iter_routes` nécessitent le chargement du code cible ;
ils sont donc inadaptés à ce contrat sans exécution. Un AST Python standard est
utilisé uniquement comme lecture syntaxique, sans compilation ni évaluation.
La page indique toujours que la liste peut être partielle : configuration,
opt-ins et branchements dynamiques ne sont pas suivis.
Les imports `from mvc.routes.module import register_x_routes` suivis d’un appel
`register_x_routes(router)` activent la lecture du corps de cette seule fonction.
Aucun import dans un module branché n’est suivi. Les routes directes précèdent
les fonctions branchées, dans l’ordre de leurs appels ; un import sans appel
ne déclenche aucune lecture. Une déclaration
non interprétée ajoute un avertissement de ligne. Aucun inventaire complet des
routes exécutables n'est promis par cette lecture minimale.
Une source absente ou illisible et un projet non reconnu restent des erreurs distinctes.


### Vérification de méthode (FD-ROUTES-004)

Le contrôleur résolu est désormais lu avec la primitive sécurisée des sources,
limite 1 Mio, UTF-8/BOM, fichier ordinaire sans lien et contrôle du descripteur.
Un cache AST local à `read_routes` évite plusieurs lectures du même fichier.
Le symbole original de l'import, même avec alias, identifie la classe de niveau
module ; seuls ses `FunctionDef` et `AsyncFunctionDef` directs sont recherchés.
Décorateurs et corps métier ne sont pas interprétés ; l'héritage n'est pas suivi.
`HandlerInfo.verification` distingue `found`, `class-missing`, `method-missing`,
`unreadable`, `ambiguous` et `not-applicable`. Une référence simple sans contrôleur
ou un handler dynamique n'entraîne aucune lecture supplémentaire.
La colonne Vérification affiche le résultat sans lien. « Trouvée » signifie
uniquement une définition syntaxique directe, pas une garantie d'exécutabilité.


### Référence de template du handler

Route Explorer prolonge le chemin route → handler → contrôleur → méthode par une
référence éventuelle de template. Dans le corps de la méthode déjà trouvée,
l’AST en cache collecte les appels explicites `BaseController.render(...)`,
forme utilisée par le squelette et les générateurs Forge. Le premier argument
ou le mot-clé `template` fournit une référence seulement s’il est une chaîne
littérale. Aucun alias de l’API de rendu ni appel indirect n’est résolu.

`HandlerInfo.template` contient un `TemplateResolution` immuable : `status`
(`found`, `none`, `dynamic`, `ambiguous`, `not-applicable`) et `path` optionnel.
Les chemins identiques sont dédupliqués ; plusieurs chemins différents donnent
`ambiguous`. Un argument dynamique prend priorité sur les chemins statiques.
Les branches sont parcourues syntaxiquement sans les évaluer ; les fonctions,
lambdas et classes imbriquées sont exclues. Une méthode non vérifiée conserve
`not-applicable`. Aucun warning supplémentaire n’est ajouté.

La colonne Template affiche la référence littérale, « Dynamique », « Plusieurs »
ou « — ». La colonne Présence vérifie désormais les métadonnées sous `mvc/views`, sans
ouvrir le fichier. `TemplateResolution.presence` distingue `present`, `missing`,
`invalid-path`, `unreadable` et `not-applicable`. Seule une résolution `found`
est vérifiée ; les autres statuts n’entraînent aucun contrôle de vue.

La référence affichée reste inchangée. Les chemins absolus, segments vides,
`.` ou `..`, antislashs, deux-points et caractères NUL sont refusés avant accès.
Chaque parent doit être un dossier ordinaire et la cible un fichier ordinaire ;
tous les symlinks sont refusés. Un cache local à `read_routes` évite les contrôles
répétés d’une même référence. Aucun scan ni fallback. La lecture des seules vues présentes est décrite ci-dessous.

Cette racine est la convention du squelette : le `VIEWS_DIR` configurable de
Forge et ses loaders d’opt-ins ne sont pas chargés. « Absent » signifie absent
dans cet espace conventionnel. Présence ne signifie ni validité Jinja ni rendu
effectif. Les parents doivent rester stables pendant ces contrôles, comme pour
les autres vérifications de métadonnées du Bridge.


### Syntaxe Jinja du template référencé

Route Explorer prolonge la présence par un parsing Jinja uniquement lorsque
la référence est statique et le fichier présent. `TemplateResolution.syntax`
vaut `valid`, `invalid`, `unreadable` ou `not-applicable` ; `syntax_line` et
`syntax_message` portent un diagnostic syntaxique éventuel, sans ligne source.
La colonne Jinja et les warnings affichent ces informations échappées.

Le lecteur existant limite la lecture à 1 Mio, accepte UTF-8 avec BOM et vérifie
le fichier ordinaire, les liens et les métadonnées du descripteur ouvert.
L'environnement Jinja 3.1.6 utilise `parse` sans loader, extension, compilation,
contexte ni rendu. Forge n'active pas d'extension syntaxique dans sa baseline ;
ses globals et son autoescape ne sont pas nécessaires à ce parsing.
Les dépendances `extends`, `include` et `import` ne sont jamais chargées.
Un cache local conserve présence et syntaxe, y compris les échecs, pour éviter
plusieurs lectures et parsings du même template dans un appel.

Syntaxe Jinja valide ne signifie ni rendu réussi, ni dépendances présentes,
ni filtres/globals runtime valides, ni HTML valide. Les configurations et
extensions personnalisées du projet ne sont pas chargées. Jinja2 est déclaré
explicitement au même pin que Forge car le Bridge utilise directement son API.


### Déclarations de dépendances Jinja directes

L'AST déjà produit par le parsing fournit les déclarations `extends`, `include`,
`import` et `from-import`. `TemplateResolution.dependencies` est un tuple de
`TemplateDependency(kind, path, dynamic, line)` immuables, vide lorsque l'analyse
n'est pas applicable ou qu'aucune déclaration n'existe.
Les chaînes littérales sont conservées sans validation filesystem ; les variables,
concaténations et appels restent dynamiques. Une liste d'include entièrement
littérale fournit une occurrence par élément ; une liste mixte ou vide reste
non résolue. Les occurrences, doublons et lignes suivent l'ordre source, y compris
dans les branches, macros et blocs, sans en interpréter le comportement.

Le cache existant conserve ce résultat après une seule lecture, un seul parsing
et une seule extraction par template et par appel. Le résumé s'affiche sous la
référence du template avec échappement, sans warning pour les cas dynamiques.
Les dépendances statiques reçoivent désormais une `presence`, avec les mêmes
statuts et la même primitive de confinement sous `mvc/views` que le template
principal. Un cache de présence commun aux deux usages évite les contrôles
répétés pendant l'appel. Les références dynamiques restent non applicables.
Le résumé affiche Présent, Absent, Chemin refusé ou Non vérifiable à côté de
chaque référence, sans warning systématique.

Les dépendances directes statiques présentes sont désormais lues par la même
primitive sécurisée (1 Mio, UTF-8 avec BOM) et parsées sans loader ni rendu.
`TemplateDependency` ajoute `syntax`, `syntax_line` et `syntax_message`, avec les
mêmes statuts et diagnostics que le template principal. Les autres dépendances
restent non applicables. Le résumé affiche le statut Jinja uniquement lorsqu'il
est applicable ; les erreurs donnent un warning unique par fichier.

Le cache local partage présence, résultat de syntaxe et AST entre les usages.
L'extraction de déclarations n'est appelée que pour les templates principaux :
les includes/extends internes d'une dépendance ne sont ni extraits, ni vérifiés,
ni ouverts. La profondeur reste 1. Syntaxe valide ne signifie ni dépendances
internes valides, ni rendu réussi, ni graphe transitif. Une cible qui est aussi le template principal d'une
autre route peut être analysée à ce titre, indépendamment de sa déclaration comme
dépendance. Les configurations `VIEWS_DIR` et opt-ins restent hors contrat.

### Graphe direct de Route Explorer

`RoutesResult → build_route_graph → RouteGraph → représentation Web` : le module
`forge_design.tools.route_graph` transforme uniquement les modèles déjà produits
par le Bridge. Il ne découvre aucune donnée, ne consulte aucun fichier et ne
parse aucune source. Aucun nouveau Tool n’est enregistré.

Les nœuds immuables route, handler, contrôleur et template sont mutualisés par
identité syntaxique (méthode et chemin pour une route). Les arêtes représentent
handles, defined-in, renders et les quatre déclarations de dépendances directes.
Les références statiques absentes restent visibles ; les dépendances dynamiques
restent dans le tableau sans nœud artificiel. Les IDs encodent des tuples JSON,
sans identifiant aléatoire. L’ordre de première découverte est conservé, ainsi
que les métadonnées de première occurrence si une entrée contradictoire est fournie.
Aucune identité runtime des handlers ni analyse transitive n’est déduite.

La page `/routes` conserve le tableau diagnostique et ajoute « Vue des relations » :
blocs de nœuds et liste de relations en HTML/CSS, avec libellés échappés et présence
textuelle. Le Web ne construit pas les relations et conserve `no-store`.

### Layout graphique statique

`RouteGraph → layout_route_graph → RouteGraphLayout → SVG statique` prolonge
la représentation. Le module `web/route_graph_layout.py` est pur et ne découvre
aucune information. Les coordonnées restent séparées du graphe métier.
Cinq colonnes fixes accueillent routes, handlers, contrôleurs, templates principaux
(cibles de renders) et autres templates. Un template à double rôle reste principal.
L’ordre des nœuds et des arêtes est conservé ; aucun parcours transitif n’intervient.
Des couloirs au-dessus des nœuds portent les flèches et leurs types. Le tableau
et la liste textuelle restent accessibles, les labels longs sont tronqués dans
le SVG avec titre complet. Aucune interaction graphique n’est disponible.

### Analyse transitive Jinja bornée

Le Bridge enrichit `TemplateResolution.dependency_graph` avec une
`TemplateDependencyGraph` gelée par template principal : racine, tuple plat de
`TemplateNodeInfo` et indicateur `truncated`. Chaque nœud conserve son chemin,
présence, syntaxe et déclarations locales (kind, cible, ligne, dynamic) ; son chemin
constitue la source de ces relations. Aucun objet récursif n’est construit.

Les données directes des routes sont vérifiées en premier. Le parcours en largeur
suit ensuite les seules références statiques, avec extraction uniquement après
parsing valide. Les cibles absentes, refusées ou invalides sont des nœuds terminaux.
L’ordre source et l’ordre de première découverte sont conservés. Une file et un
ensemble local par racine empêchent les boucles, sans diagnostic métier de cycle.

La profondeur principale vaut 0, la limite 8. Les déclarations du niveau 8 restent
visibles sans contrôle de leurs cibles au titre de ce parcours. Une autre route
principale peut analyser indépendamment la même cible. Au plus 128 références
exactes font l’objet d’un contrôle par `read_routes`, échecs compris : aucun accès
pour les nouvelles références au-delà. Elles restent déclarées avec statuts non
applicables. Un warning unique par type de limite indique le résultat partiel.
Cette borne globale prime aussi sur les données directes des projets très larges.

Présence, lecture, parsing et extraction sont mis en cache localement entre racines ;
les succès et échecs sont partagés, sans cache persistant. Chaque fermeture par
racine parcourt ses propres relations connues. Aucune lecture hors de la politique
`mvc/views`, aucun scan, loader ou rendu supplémentaire n’est autorisé.

L’analyse transitive ne constitue ni un rendu, ni une résolution dynamique, ni un
diagnostic de cycles. Le RouteGraph et le SVG restent fondés sur les seules données
directes ; leur intégration transitive n’est pas réalisée ici.

### Diagnostics de cycles Jinja

`TemplateDependencyGraph → detect_template_cycles → TemplateCycle` est une
analyse pure du graphe connu, dans `forge/template_cycles.py`. Elle ne relit et
ne parse aucun template et ne modifie pas le parcours borné de découverte.
Les cycles sont stockés dans le champ `cycles` de la fermeture finale.

La DFS itérative suit les états absent/en cours/terminé et produit un cycle témoin
par arête de retour vers la pile active. Elle ne cherche pas à énumérer tous les
cycles simples d’un graphe dense. Les auto-cycles et cycles indépendants ou
partageant une racine sont détectés. Les cibles hors de la table et les déclarations
dynamiques sont exclues. Les quatre types de dépendances statiques sont considérés.

Chaque cycle contient des arêtes gelées (source, cible, kind, line) et expose un
chemin explicitement fermé. Il est tourné vers sa plus petite source lexicographique,
sans inversion. Les déclarations de même source/cible/type sont mutualisées en
conservant la première ligne. L’identité de diagnostic ignore les lignes : mêmes
relations orientées, même cycle. L’ordre des témoins suit la découverte DFS.
Le parcours coûte O(V + E), auquel s’ajoute la taille des diagnostics produits.

Les warnings sont dédupliqués entre racines d’un même `read_routes`. La page affiche
une liste textuelle « Cycles de templates » issue de ces diagnostics déjà calculés,
avec lignes et types échappés. Le RouteGraph et le SVG restent directs.
En cas de troncature, « Analyse partielle. » reste visible, même si un cycle connu
est retourné. « Aucun cycle détecté dans l’analyse disponible. » n’est pas une
preuve d’absence dans le projet lorsque la fermeture est tronquée.

### RouteGraph transitif et cycles connus

`TemplateDependencyGraph + cycles → RouteGraph → RouteGraphLayout → SVG` : aucune
découverte n’est effectuée après le Bridge. Le builder conserve d’abord son préfixe
direct, puis parcourt une fois chaque fermeture principale dans l’ordre des routes.
Les nœuds de la table et leurs déclarations locales ajoutent uniquement des relations
connues. Templates et arêtes identiques sont mutualisés globalement ; références
absentes, refusées ou non contrôlées restent du texte avec leur statut connu.
Les dépendances dynamiques ne créent pas de cible graphique.

`GraphEdge.in_cycle` indique l’appartenance à une arête des diagnostics fournis,
sans nouvelle détection ni canonicalisation. Un marquage connu dans une fermeture
s’applique aussi à l’arête partagée dans les autres. `RouteGraph.transitive_truncated`
agrège les troncatures. Les champs sont ajoutés avec valeurs par défaut compatibles.
Le premier statut rencontré reste conservé selon la politique du builder existant.

Le layout calcule les distances minimales depuis toutes les cibles de renders par
une file multi-sources. Routes, handlers et contrôleurs restent aux niveaux 0/1/2 ;
les templates principaux au niveau 3, puis un niveau par distance minimale.
Chaque template est enfilé au plus une fois ; les cycles n’accroissent pas la distance
indéfiniment. Un template également principal reste au niveau 3. Les nœuds sont
empilés dans leur ordre d’entrée. Le placement et le parcours des arêtes restent
linéaires dans la taille du graphe. Les templates isolés éventuels restent au niveau 4.

Le SVG conserve le défilement, les dimensions déterministes et les chemins orthogonaux,
y compris les retours vers une colonne précédente. Les arêtes de cycle sont pointillées
et portent « (cycle) ». « Analyse partielle. » apparaît dans la section graphique si
nécessaire. Le tableau diagnostique et la section textuelle des cycles sont conservés.
Aucun JavaScript, interaction ou lecture supplémentaire du projet.

### Références et vue source en lecture seule

`SourceLocation(path, line=None)` est gelé et conserve un chemin relatif.
RouteInfo.source vient du fichier de routes effectivement analysé et de la ligne de
l’appel add. HandlerInfo.class_source/method_source viennent des nœuds AST déjà lus,
sans relecture ; aucune ligne n’est inventée pour une classe/méthode absente.
TemplateResolution et TemplateNodeInfo portent la référence sous mvc/views ; la
présence existante décide si le Web propose un lien. TemplateDependency.source
localise sa déclaration dans son propre template parent, y compris transitif.

Une colonne Sources dans le tableau expose ces liens textuels. Le RouteGraph et
son SVG ne changent pas et restent purs, sans nœuds cliquables.
`GET /source?path=...&line=...` utilise exclusivement le projet courant et la primitive
séparée read_project_source. Aucun appel Inspector/Route Explorer ni cache persistant.
Le diagnostic est un instantané ; la vue lit le fichier au moment de l’ouverture.

La politique stricte accepte seulement les fichiers .py directement sous mvc/routes
et mvc/controllers, et les fichiers sous mvc/views. Chemins absolus, segments vides,
segments commençant par un point, antislashs, deux-points et NUL sont refusés, ainsi
que les chemins dépassant 4096 caractères. Aucun scan ni catalogue de fichiers ;
Forge Design ne devient pas un explorateur général du projet. La route n’est pas
une allowlist d’instantané : un chemin manuel respectant cette politique peut être lu.

Le lecteur exige open avec dir_fd et O_NOFOLLOW. Il ouvre chaque dossier relativement
au descripteur parent avec O_DIRECTORY/O_NOFOLLOW, puis vérifie le fichier ordinaire
sans lien, compare ses métadonnées avec celles du descripteur et lit au plus 1 Mio
plus un octet de détection. UTF-8/BOM seulement. Aucune dégradation moins stricte
sur une plateforme sans ces primitives : erreur explicite. Tous les descripteurs
sont fermés. La racine canonique vient du contexte ; le contenu peut changer durant
une lecture concurrente, sans promesse d’instantané atomique.

La vue utilise du code échappé, numéros de lignes et marqueur textuel pour la cible.
Une ligne valide sélectionne ±20 lignes ; sans ligne ou si elle dépasse le fichier,
tout le fichier borné est affiché, avec diagnostic dans ce dernier cas. Les fins de
ligne CRLF/CR sont adaptées pour la numérotation. Projet absent : 409 sans lecture ;
source disparue : 404 ; refus/encodage/taille/ligne mal formée : 400. No-store pour
la route entière, aucun POST source, éditeur externe, JavaScript ou écriture.
