# Rapport — FD-ROUTES-001

## Ticket et objectif

Ajouter Route Explorer comme deuxième Tool intégré et afficher les déclarations de routes lisibles sans exécuter le projet courant.

## État Git initial

- Branche `main`, propre et synchronisée avec `origin/main`.
- HEAD `6dc7244` — `feat: actualiser le projet courant (FD-PROJECT-002)`.
- État et cinq derniers commits inspectés avant modification.

## Source des routes Forge

`git ls-remote https://github.com/caucrogeGit/Forge.git refs/heads/main` confirme `73a956e587e5f169c028415e0e540c149cbaff56`, identique au checkout inspecté.
`forge.py:cmd_routes_list` existe : il charge la configuration puis importe le module de routes cible avant d'appeler `router.iter_routes()`.
Cette commande et l'API d'inventaire du routeur nécessitent donc l'exécution du projet ; elles ne sont pas utilisées.
Aucune API d'inventaire statique sûre n'a été identifiée dans cette inspection.

Le squelette officiel `mvc/routes/__init__.py` déclare deux routes dans un groupe public : `/` et `/charte`, puis appelle `register_optins(router)`.
La première livraison ne lisait que `mvc/routes/__init__.py` et manquait les routes applicatives branchées.
La correction suit désormais aussi les fichiers directement sous `mvc/routes/` associés aux imports explicites `from mvc.routes.module import register_x_routes` et aux appels inconditionnels `register_x_routes(router)` depuis la racine.
Un import sans appel n'active aucune lecture. Seul le corps de la fonction nommée est analysé, jamais exécuté ; les instructions globales du module ne sont pas exécutées ni utilisées pour découvrir d'autres modules.
Les alias, imports relatifs, sous-paquets, boucles et branchements dynamiques restent non résolus.
Un branchement absent ou invalide produit un warning afin de conserver les routes des autres sources, sans annoncer une liste complète.
Un AST de la bibliothèque standard Python permet une lecture syntaxique limitée des appels littéraux, sans import ni évaluation ; une recherche textuelle seule ne traiterait pas correctement les groupes et expressions multilignes.
Cette solution n'est pas un interpréteur du routage Forge : la page signale systématiquement son caractère potentiellement partiel.

Références inspectées : [commande Forge](https://github.com/caucrogeGit/Forge/blob/73a956e587e5f169c028415e0e540c149cbaff56/forge.py), [routeur](https://github.com/caucrogeGit/Forge/blob/73a956e587e5f169c028415e0e540c149cbaff56/core/http/router.py), [squelette](https://github.com/caucrogeGit/Forge/blob/73a956e587e5f169c028415e0e540c149cbaff56/skeleton/data/mvc/routes/__init__.py).

## Contrat du Bridge

`read_routes(root: str | PathLike[str]) -> RoutesResult` utilise `resolve_project_root` puis le détecteur structurel, sans appel à Project Inspector.
Le résultat immuable expose `routes`, `warnings` et `source`.
Ordre corrigé : routes directes de la racine, puis fonctions explicitement branchées dans l’ordre des appels. Dans chaque source, l’ordre des déclarations et des méthodes est conservé.
Les déclarations reconnues sont `router = Router()`, les appels `add` à trois arguments positionnels et les groupes `with router.group(...) as ...` contenant de tels appels.
Méthodes, chemins, noms et indicateurs public doivent être littéraux ; le handler n'est jamais évalué.
Les expressions ou instructions non interprétées produisent un avertissement avec numéro de ligne, sans recopier le code.

Erreurs distinctes : `NotForgeProjectError`, `RoutesSourceMissingError` et `RoutesSourceUnreadableError`.
Les exceptions de racine restent propagées.
L'indisponibilité d'une API officielle utilisable sans exécution est un choix de stratégie documenté, pas une dépendance runtime à une commande absente.
Aucune sortie de commande n'est donc parsée.

## Modèle RouteInfo

Dataclass gelée : `method: str`, `path: str`, `name: str | None`, `public: bool`.
Aucun contrôleur, template ou permission déduit.
Les méthodes sont présentées en majuscules et les préfixes littéraux des groupes sont appliqués selon l'API inspectée.

## RouteExplorerTool

`RouteExplorerTool.run(project_root: Path) -> RoutesResult` délègue uniquement au Bridge.
Identité gelée : `route-explorer`, nom `Route Explorer`, description « Lister les routes déclarées d’un projet Forge. ».
La conformité à `Tool[RoutesResult]` est vérifiée statiquement par Pyright.

## Intégration registre

Le point de composition enregistre explicitement, dans cet ordre, `project-inspector` puis `route-explorer`.
Aucun enregistrement dynamique et aucune exécution au démarrage.
Les tests du registre intégré sont adaptés aux deux Tools.

## Intégration Web

`GET /routes` consulte le contexte existant et récupère le Tool via le registre.
Sans projet, la page affiche l'état vide sans lecture de routes.
Avec projet, elle affiche méthode, chemin, nom optionnel et public dans un tableau Jinja échappé, ainsi que la source et les avertissements de lecture partielle.
Les erreurs attendues sont affichées ; aucun diagnostic courant n'est modifié ou actualisé par cette page.
Chaque GET relit les routes ; aucune mise en cache dans le contexte.
Navigation fixe avec état actif, réponse `Cache-Control: no-store`, aucun nouveau POST.

## Sécurité

Chaque source autorisée est limitée à 1 Mio et décodée UTF-8 avec BOM accepté. Au plus 64 branchements sont suivis, avec warning au-delà.
Les noms de modules doivent être un identifiant Python simple après `mvc.routes.` ; aucun chemin libre, sous-répertoire ou import hors de cette zone n’est suivi. Aucun suivi récursif des imports de modules branchés.
Les liens symboliques et fichiers spéciaux sont refusés ; le descripteur ouvert est comparé aux métadonnées préalables, avec `O_NOFOLLOW` et `O_NONBLOCK` lorsqu'ils sont disponibles.
Les parents sont validés par le détecteur existant.
Aucun contenu de config, contrôleur, secret ou module hors de ce contrat de routes n’est lu.
Aucun sous-processus, import cible, compilation ou exécution AST, aucune écriture projet.

## Fichiers créés

- [forge_design/forge/routes.py](../../forge_design/forge/routes.py)
- [forge_design/tools/route_explorer.py](../../forge_design/tools/route_explorer.py)
- [forge_design/web/routes.py](../../forge_design/web/routes.py)
- [forge_design/web/templates/routes.html](../../forge_design/web/templates/routes.html)
- [tests/test_routes.py](../../tests/test_routes.py)
- [docs/rapports/FD-ROUTES-001.md](FD-ROUTES-001.md)

## Fichiers modifiés

- [forge_design/app.py](../../forge_design/app.py)
- [forge_design/web/server.py](../../forge_design/web/server.py)
- [forge_design/web/templates/layout.html](../../forge_design/web/templates/layout.html)
- [pyproject.toml](../../pyproject.toml) : template distribué, aucune dépendance ajoutée.
- [tests/test_app.py](../../tests/test_app.py)
- [tests/test_web_inspector.py](../../tests/test_web_inspector.py)
- [docs/02-architecture.md](../02-architecture.md)

## Tests ajoutés

Neuf cas de première livraison : représentation, groupe public, méthodes multiples, ordre déterministe, Tool typé, source absente, projet non reconnu, syntaxe invalide, encodage invalide, taille excessive, lien refusé, expressions dynamiques non inventées et page HTTP (certains cas regroupent plusieurs assertions).
Les tests vérifient la non-évaluation du handler, l'absence de modification de source, le tableau, les liens, l'état actif, le nom optionnel, les valeurs public, l'échappement et `no-store`.
Les tests de composition vérifient exactement deux Tools et interdisent leur exécution au démarrage.

Six cas supplémentaires de correction couvrent route directe et deux modules ordonnés, module importé non appelé, fonction sans import résoluble, fichier absent, syntaxe invalide, symlink, import extérieur et appel dynamique.
Une sentinelle sur `os.open` vérifie les seuls fichiers effectivement ouverts ; les octets et dates de modification sont comparés avant et après. Les fixtures contiennent du code qui échouerait s'il était exécuté.

## Test réel

Wheel construite puis inspectée : quatre templates et CSS présents.
Installation temporaire sans dépendances, puis processus Python isolé important Forge Design depuis cette installation avec les dépendances de `.venv`.
Une copie temporaire du squelette officiel est ouverte via Inspector ; `GET /routes` affiche `home-index` et `home-charte`, avec navigation active.
Pour la correction, la copie temporaire reçoit `contact_routes.py` et son import/appel explicite ; la page affiche également `/contact/list`. Le handler référencé n’a pas besoin d’exister puisque rien n’est exécuté.
Le contrôle couvre également shell, CSS, actualisation, fermeture, arrêt du serveur et port libéré.
Le dépôt Forge de référence n'est pas modifié.

Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `3043907514d38e1b032a86d7d1a220436070f15e537e8c4d269879a5f86faa4c`.
Script ignoré par Git : `tmp/verify_fd_routes_correction.py`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| État Git et historique | Inspectés |
| `git ls-remote` Forge main | Référence confirmée |
| `pytest` | 235 tests réussis, dont 6 cas supplémentaires de correction |
| `pytest tests/test_app.py` après ajout de sentinelle Route Explorer | 4 tests réussis |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| Construction wheel et HTTP depuis installation | Succès |

Outils de `.venv`, Python 3.13.5 ; HTTP avec autorisation de sockets locaux hors sandbox.
Des diagnostics initiaux Pyright sur une liste de valeurs AST ont été corrigés par une extraction explicitement typée ; imports et formatage Ruff corrigés avant validations finales.
Le diff complet est relu avant commit, rapport compris.

## Tests sautés

Aucun test pytest sauté. Aucune exécution de `forge routes:list` sur un projet cible, aucun test visuel navigateur revendiqué.

## Limites restantes

- Inventaire statique de la racine et des branchements directs reconnus, pas des routes réellement enregistrées à l’exécution.
- Seules les fonctions explicitement branchées depuis la racine sont suivies ; signatures complexes, décorateurs, alias, configuration alternative, opt-ins et constructions dynamiques restent exclus.
- Les appels ressemblant syntaxiquement à l'API Forge ne prouvent pas l'identité runtime du routeur ; le lecteur n'exécute pas le code pour le vérifier.
- Le filesystem doit rester stable pendant la lecture, comme pour les autres API Bridge.
- Aucun graphe, édition ou lien aux contrôleurs ajouté.

## État Git final

Le commit original `2b015fd` est amendé localement avec la correction et ce rapport, sans push.
Au début de la correction, `origin/main` référençait déjà ce commit original. L’amendement crée donc une divergence locale avec cette référence distante ; aucun push forcé n’est effectué.
Message : `feat: ajouter Route Explorer minimal (FD-ROUTES-001)`.
Le hash et l'état final sont communiqués dans la réponse de livraison.

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-ROUTES-001.md
```
