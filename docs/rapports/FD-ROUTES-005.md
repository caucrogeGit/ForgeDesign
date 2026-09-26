# Rapport — FD-ROUTES-005

## Ticket et objectif

Identifier une référence littérale de template dans la méthode contrôleur déjà vérifiée, sans exécuter le projet ni ouvrir les vues.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `9ea0df2` — FD-ROUTES-004.
État Git et cinq derniers commits inspectés avant modification.

## API de rendu Forge vérifiée

`git ls-remote https://github.com/caucrogeGit/Forge.git refs/heads/main` confirme `73a956e587e5f169c028415e0e540c149cbaff56`, référence locale inspectée.

- Le [HomeController du squelette](https://github.com/caucrogeGit/Forge/blob/73a956e587e5f169c028415e0e540c149cbaff56/skeleton/data/mvc/controllers/home_controller.py) appelle `BaseController.render("home/index.html", request=request)` et `BaseController.render("pages/charte.html", request=request)`.
- Le générateur CRUD `packages/forge-mvc-entities/forge_mvc_entities/crud/controller_builder.py` émet des appels à `BaseController.render` avec des chemins littéraux de formulaire, détail et confirmation. Sa méthode `index` utilise au contraire une variable `template`, choisie entre résultats partiels et index : ce cas reste dynamique.
- Le générateur auth `cli/security/make_auth.py` utilise `BaseController.render("auth/login.html", context=...)`, notamment dans une affectation de réponse.
- La signature de `core/mvc/controller/base_controller.py` confirme `render(template: str, status=200, context=None, base=..., *, request=None, raw=False)`.

La forme reconnue est précisément `BaseController.render`, avec premier argument ou mot-clé `template`. `Response.html`, les fonctions nommées simplement `render`, les alias et les appels via `self` ne sont pas assimilés à cette API. L'identité runtime du nom n'est pas prouvée.

## Modèle de résolution template

Dataclass gelée `TemplateResolution(status, path=None)`, avec les statuts `found`, `none`, `dynamic`, `ambiguous`, `not-applicable`.
`HandlerInfo` ajoute `template: TemplateResolution = TemplateResolution()` après ses champs existants. Les constructions antérieures restent valides.
Seul `found` produit un chemin dans le lecteur ; la valeur par défaut est `not-applicable`.

## Analyse AST de la méthode

Après vérification de la classe et de la méthode, le même nœud de fonction fournit son corps à un parcours syntaxique itératif.
Les conditions, boucles, `try`, `match` et `with` sont parcourus sans évaluation des branches.
Les fonctions synchrones ou asynchrones, lambdas et classes imbriquées sont ignorées, ainsi que les décorateurs et annotations de la méthode principale.
Aucune autre méthode n'est inspectée pour comprendre un appel. Une méthode sans rendu reconnu donne `none`.

## Templates statiques

Une chaîne `ast.Constant` est conservée exactement comme valeur Python du littéral, sans normalisation de chemin ni vérification d'existence.
Les échappements de chaîne sont ceux décodés par le parseur Python ; les guillemets ne font pas partie du chemin.
Les références identiques sont dédupliquées et donnent un seul résultat `found`.

## Templates dynamiques

Variable, constante nommée, f-string, appel de fonction ou argument non littéral donnent `dynamic`.
Les expansions `*args` et `**kwargs`, l'absence d'argument et les arguments de template concurrents sont également non résolus.
Un rendu dynamique prend priorité sur tous les chemins statiques détectés. Aucune variable n'est évaluée.

## Ambiguïtés

Plusieurs chemins statiques distincts donnent `ambiguous`, sans choisir un chemin ni exposer une liste supplémentaire.
Les statuts suffisent : aucun warning template n'est ajouté. Une méthode non vérifiée conserve `not-applicable` et ses warnings antérieurs uniquement.

## Cache AST

Le dictionnaire local de FD-ROUTES-004 reste partagé entre les sources de routes d'un appel.
La vérification et l'analyse template utilisent le même AST ; aucune seconde lecture ni nouveau parsing du contrôleur.
Le cache n'est pas conservé entre requêtes. Le contrôle HTTP réel confirme la prise en compte d'une modification au GET suivant.

## Intégration Bridge

`read_routes` et `RoutesResult` conservent leurs API. L'enrichissement est ajouté lors de la vérification existante.
Méthode HTTP, chemin, référence du handler, contrôleur, vérification, nom, public, ordre et warnings antérieurs sont conservés.
Aucun changement de Tool, registre ou contexte projet.

## Intégration Web

La colonne Template suit Vérification et précède Nom.
Elle affiche le chemin littéral, « Dynamique », « Plusieurs » ou « — ».
L'échappement Jinja et `Cache-Control: no-store` restent actifs ; aucun lien ni nouvelle route HTTP.

## Sécurité

Aucun fichier supplémentaire n'est ouvert. Aucun scan de `mvc/views`, import cible, rendu, évaluation ou écriture.
Un chemin tel que `../secret.html` reste du texte ; il n'est jamais suivi.
Les contrôles de fichiers et les limites de taille existants restent inchangés.

## Fichiers créés

- [docs/rapports/FD-ROUTES-005.md](FD-ROUTES-005.md).

## Fichiers modifiés

- [forge_design/forge/routes.py](../../forge_design/forge/routes.py) : modèle et analyse AST.
- [forge_design/web/templates/routes.html](../../forge_design/web/templates/routes.html) : colonne Template.
- [tests/test_routes.py](../../tests/test_routes.py) : statuts, branches et confinement.
- [tests/test_web_inspector.py](../../tests/test_web_inspector.py) : affichage HTTP.
- [docs/02-architecture.md](../02-architecture.md) : contrat et limites.

Aucune dépendance ou métadonnée de packaging modifiée.

## Tests ajoutés

26 nouveaux cas : 22 formes de corps de méthode, un contrôle de cache/confinement et trois affichages HTTP.
Ils couvrent les formes Forge du squelette et du CRUD, le mot-clé `template`, les chemins inchangés, l'absence de rendu, les expressions dynamiques, les doublons, les ambiguïtés, la priorité dynamique, les blocs de contrôle et l'exclusion des portées imbriquées.
Les tests de vérification existants confirment désormais `not-applicable` sur échec.
La sentinelle `os.open` n'autorise que la source de routes et son contrôleur, avec une seule lecture pour trois routes ; `Path.open` et `iterdir` sont interdits pendant le contrôle. Les octets et dates de modification sont comparés.
Du code qui lèverait une exception à l'import reste inerte. Les tests HTTP vérifient le chemin échappé, les deux statuts textuels et `no-store`.

## Test réel

Wheel reconstruite et archive inspectée : quatre templates, CSS et dépendance Forge présents.
Installation temporaire par `pip --no-deps --no-index --target`, puis processus Python isolé (`-I`) avec origine des imports vérifiée et dépendances runtime de `.venv`.
Une copie du squelette reçoit un contrôleur contact et un branchement explicite. `/routes` affiche `ContactController.list`, son fichier, « Trouvée » et `contacts/list.html`, ainsi que `home/index.html` du squelette.
Le contrôleur temporaire est ensuite remplacé par une méthode passant une variable à `BaseController.render` : le GET suivant affiche « Dynamique » et ne conserve pas l'ancien chemin.
Le dépôt Forge de référence reste intact. Arrêt du thread, fermeture du socket et réutilisation du port vérifiés.

Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `f74ba8f757345b5bd8a6c0e8d66459879b8debc71b0f2c7acad04abe8d8d2cee`.
Script ignoré par Git : `tmp/verify_fd_routes_005.py`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat |
|---|---|
| État Git, historique et `git ls-remote` Forge main | Vérifiés |
| `pytest` | 299 tests réussis, dont 26 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| `python -m pip wheel --no-deps --wheel-dir tmp/wheels .` | Succès |
| Wheel installée et cycle HTTP statique puis dynamique | Succès |

Outils de `.venv`, Python 3.13.5 ; sockets locaux autorisés hors sandbox.
Les lignes trop longues signalées initialement par Ruff ont été corrigées avant validation finale.
Pip a signalé son cache utilisateur non accessible dans le sandbox et l'a désactivé, sans erreur de dépendances.
Le diff complet est relu avant commit, rapport compris.

## Tests sautés

Aucun test pytest sauté. Aucun contrôle visuel navigateur, génération complète par Forge ou rendu du template cible revendiqué.

## Limites restantes

Reconnaissance syntaxique de `BaseController.render` uniquement, sans preuve de son identité runtime, analyse de flot ni résolution des alias.
Les appels indirects et helpers ne sont pas suivis. Un appel présent dans une branche inaccessible reste collecté.
Le résultat ne garantit ni le rendu effectif, ni l'existence du fichier, ni la validité Jinja.
Les limites de stabilité filesystem et de lecture partielle du Bridge restent applicables.

## État Git final

Un seul commit local sur `main`, rapport inclus, sans push.
Message : `feat: identifier les templates des routes (FD-ROUTES-005)`.
Le hash et l'état Git après commit sont communiqués dans la réponse de livraison.
