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
Aucun chemin ou diagnostic n'est conservé entre requêtes, aucun cookie ni session
n'est créé ; un GET ultérieur affiche toujours un formulaire vierge.

Le CSRF Forge rc9 dépend d'une session. Pour cette seule route POST publique en
lecture seule, `csrf=False` est explicite : avant toute inspection, l'en-tête
`Origin` doit être exactement `http://` suivi du `Host` local `127.0.0.1[:port]`.
Les origines absentes, nulles ou étrangères sont refusées (403), ainsi qu'un
`Sec-Fetch-Site` autre que `same-origin` lorsqu'il est présent.
Seul `application/x-www-form-urlencoded` est accepté (415 sinon).
Ce contrôle navigateur ne constitue pas une authentification des clients locaux.
Il ne modifie pas les middlewares ni la politique des autres routes.

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
C'est l'unique Tool intégré à ce stade. La fonction retourne le registre sans
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
