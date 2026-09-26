# Rapport — FD-ROUTES-002

## Ticket et objectif

Enrichir les routes avec leur référence syntaxique de handler, sans importer ni exécuter le projet ou lire ses contrôleurs.

## État Git initial

- Branche `main`, propre et synchronisée avec `origin/main`.
- HEAD `48bda6f` — `feat: ajouter Route Explorer minimal (FD-ROUTES-001)`.
- État et historique inspectés avant modification.

## Vérification Forge

`git ls-remote https://github.com/caucrogeGit/Forge.git refs/heads/main` confirme `73a956e587e5f169c028415e0e540c149cbaff56`, référence locale inspectée.
Formes observées :

- Squelette `skeleton/data/mvc/routes/__init__.py` : `HomeController.index` et `HomeController.charte`, dans un groupe public.
- Générateur CRUD du paquet `forge-mvc-entities`, module `crud/routes*` : référence du contrôleur généré à `show_by_slug` dans `public.add`.
- Générateur auth `cli/security/make_auth.py` : `AuthController.login_form`, `AuthController.login`, `AuthController.logout`.
- Tests `tests/test_router_static_index_001.py` : handler fonction simple `_handler`, sans contrôleur obligatoire.

Le contrat est donc syntaxique : noms et attributs peuvent être lus sans import ni introspection runtime.

## Modèle et contrat du Bridge

Nouvelle dataclass gelée `HandlerInfo(reference: str)`.
`RouteInfo` conserve tous ses champs et ajoute `handler: HandlerInfo | None = None` ; la valeur par défaut préserve les constructions Python à quatre arguments.
`read_routes` conserve son type `RoutesResult`, ses sources, leur ordre, ses limites et ses contrôles.

La lecture du troisième argument est effectuée uniquement sur l'AST déjà chargé.
Un `ast.Name` devient sa référence littérale (`health`). Une chaîne de `ast.Attribute` ancrée sur un nom devient sa référence pointée (`ContactController.list`).
Les alias sont conservés tels qu'écrits (`Contact.list`) ; aucune réécriture vers le nom importé ni ouverture du module importé.
Les imports explicites n'ont pas besoin d'être résolus pour reproduire une référence syntaxique. L'existence ou la provenance runtime du symbole n'est pas affirmée.

## Expressions dynamiques et avertissements

Appels, attributs issus d'un appel, indexations, lambdas, `partial` et `getattr` retournent un handler absent.
La route reste présente avec les mêmes méthode, chemin, nom et public.
Un warning de ligne indique « handler dynamique non résolu », sans recopier l'expression.
Pour une fonction branchée, le nom de fichier est ajouté par le mécanisme existant.
Les warnings antérieurs restent conservés ; seuls les avertissements supplémentaires de handler sont ajoutés.

## Intégration Web

La page existante `/routes` reçoit une colonne Handler entre Chemin et Nom.
Elle affiche la référence échappée ou « — », sans lien et sans nouvelle page.
Le Tool, le registre, le contexte projet, les routes HTTP et les protections réseau restent inchangés.

## Sécurité

Aucune lecture supplémentaire de fichier, aucun import cible, sous-processus, eval ou exec.
Aucun corps de contrôleur analysé. Les références à des handlers n'ont pas besoin d'être exécutables pour être affichées.
Les limites de lecture confinée de FD-ROUTES-001 restent applicables.

## Fichiers créés

- [docs/rapports/FD-ROUTES-002.md](FD-ROUTES-002.md)

## Fichiers modifiés

- [forge_design/forge/routes.py](../../forge_design/forge/routes.py) : modèle et extraction syntaxique.
- [forge_design/web/templates/routes.html](../../forge_design/web/templates/routes.html) : colonne Handler.
- [tests/test_routes.py](../../tests/test_routes.py) : handlers statiques et dynamiques.
- [tests/test_web_inspector.py](../../tests/test_web_inspector.py) : affichage HTTP.
- [docs/02-architecture.md](../02-architecture.md) : contrat de référence syntaxique.

## Tests ajoutés

14 nouveaux cas : quatre références (`ContactController.list`, `HomeController.index`, `health`, `Contact.list`) dans la racine et dans une fonction branchée, toutes dans un groupe ; six constructions dynamiques conservant la route avec warning.
Les assertions de modèle existantes sont adaptées au champ handler ; le nombre de warnings de la fixture contenant trois appels dynamiques passe de deux à cinq, sans suppression des warnings préexistants.
Le test HTTP vérifie la colonne et la référence affichée.
Les tests existants de confinement, non-exécution, non-écriture et ordre restent actifs.

## Test réel et packaging

Wheel reconstruite, ressources inspectées puis installation temporaire avec `pip --no-deps --no-index --target`.
Un processus Python isolé utilise l'installation et les dépendances runtime de `.venv`.
La copie temporaire du squelette officiel avec un fichier contact branché affiche les routes directes et branchées, la colonne Handler et `HomeController.index`.
Le dépôt Forge de référence reste intact ; le serveur est arrêté et le port libéré.

Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `ca0d87f8aded9cd8e7f9fba7075bd6155ba0ec60da2410b93515b8858f91b485`.
Script ignoré par Git : `tmp/verify_fd_routes_002.py`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat |
|---|---|
| État Git et historique | Inspectés |
| `git ls-remote` Forge main | Référence confirmée |
| `pytest` | 249 tests réussis, dont 14 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| Construction wheel et HTTP depuis installation | Succès |

Outils de `.venv`, Python 3.13.5 ; HTTP avec autorisation de sockets locaux hors sandbox.
Deux lignes de fixtures trop longues ont été corrigées après le premier passage Ruff.
Le diff complet est relu avant commit, rapport compris.

## Tests sautés

Aucun test pytest sauté. Aucun contrôle visuel navigateur ou exécution de contrôleur revendiqué.

## Limites restantes

- La référence syntaxique ne garantit pas l'existence ni l'identité runtime du handler.
- Les expressions dynamiques ne sont pas résolues.
- Le périmètre de lecture statique partielle des routes reste celui de FD-ROUTES-001.
- Aucun lien vers contrôleur, template, signature ou graphe.

## État Git final

Un seul commit local sur `main`, rapport inclus, sans push.
Message : `feat: afficher les handlers des routes (FD-ROUTES-002)`.
Le hash et l'état final vérifié sont communiqués dans la réponse de livraison.
