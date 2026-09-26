# Rapport — FD-ROUTES-006

## Ticket et objectif

Vérifier la présence des templates statiquement identifiés dans l’espace conventionnel des vues Forge, sans ouvrir leur contenu ni rendre ou analyser Jinja.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `b9a3234` — FD-ROUTES-005.
`git status` et `git log --oneline --decorate -5` exécutés avant modification.

## Convention Forge des vues

`git ls-remote https://github.com/caucrogeGit/Forge.git refs/heads/main` confirme `73a956e587e5f169c028415e0e540c149cbaff56`, référence locale inspectée.
Le squelette configure `VIEWS_DIR` avec la valeur par défaut `mvc/views`, modifiable par environnement.
`BaseController.render` transmet la référence au mécanisme de rendu ; `core/app/app_factory.py` enregistre `Jinja2Renderer(config.VIEWS_DIR)`.
Le renderer utilise un loader filesystem pour ce dossier et peut également chercher dans les loaders d’opt-ins.
Les générateurs CRUD et auth écrivent sous `mvc/views`, avec un éventuel namespace de vues inclus dans le chemin de rendu.

Sources inspectées : `skeleton/data/config.py`, `skeleton/data/bootstrap.py`, `core/mvc/controller/base_controller.py`, `core/app/app_factory.py`, `integrations/jinja2/renderer.py`, `cli/security/make_auth.py` et `packages/forge-mvc-entities/forge_mvc_entities/make_crud.py` du dépôt Forge de référence.

Le contrat retenu vérifie uniquement `<racine>/mvc/views`. Il ne prétend pas reproduire la configuration runtime : aucun chargement de config, d’environnement cible ou de loader d’opt-in. « Absent » signifie absent de cet espace conventionnel, pas nécessairement introuvable par un renderer personnalisé.

## Modèle de présence template

`TemplateResolution` reste gelée et ajoute `presence: TemplatePresenceStatus = "not-applicable"` après ses champs existants.
Les valeurs sont `present`, `missing`, `invalid-path`, `unreadable`, `not-applicable`.
Seul `status == "found"` avec un chemin déclenche la vérification. Les résolutions dynamiques, ambiguës, absentes ou non applicables restent non applicables pour la présence.
La référence source et le statut de résolution sont conservés.

## Résolution du chemin

La référence est décomposée sur `/` et ajoutée à `mvc/views` composante par composante.
La politique portable refuse une chaîne vide, les segments vides, `.` et `..`, les antislashs, deux-points et caractères NUL.
Les chemins absolus Unix ou Windows sont ainsi refusés avant accès. Aucun nettoyage silencieux ni transformation de la référence affichée.
Cette politique est volontairement plus stricte que les noms acceptés par certains filesystems.

## Confinement

Aucun segment ne permet de quitter la racine conventionnelle et aucun chemin libre n’est résolu ailleurs.
Pas de scan, recherche alternative ou fallback. Les traversals restent refusés même s’ils pourraient être normalisés vers un chemin interne.

## Gestion des symlinks

`lstat` vérifie successivement `mvc`, `views`, les sous-dossiers et la cible.
Chaque parent doit être un dossier ordinaire, la cible un fichier ordinaire.
Un lien interne ou externe, y compris un lien cassé, donne `invalid-path`. Le lecteur s’arrête avant de descendre dans un parent refusé.

## Vérification filesystem

Seules les métadonnées sont consultées, sans `open` ni lecture du contenu de la vue.
Une composante absente donne `missing` ; un mauvais type donne `invalid-path` ; les autres `OSError`, dont `PermissionError`, donnent `unreadable`.
Les exceptions hors de ce contrat ne sont pas interceptées.
Aucune limite de taille ajoutée : un fichier de contenu invalide reste présent s’il est ordinaire.

## Cache local

Un dictionnaire local à `read_routes` mémorise le statut par référence exacte, y compris les échecs.
Il est partagé par toutes les routes agrégées et abandonné au retour. Deux routes utilisant le même template n’entraînent qu’une vérification ; une nouvelle requête vérifie de nouveau.

## Intégration Bridge

`read_routes(...) -> RoutesResult` reste inchangé.
L’enrichissement des résultats agrégés utilise `dataclasses.replace`, sans mutation des objets gelés, sans nouveau parcours de sources ni analyse AST supplémentaire.
Tous les champs antérieurs, l’ordre et les warnings sont conservés. La présence ne crée aucun warning systématique.
Le registre, les Tools, Inspector et le contexte projet restent inchangés.

## Intégration Web

Colonne Présence après Template : « Présent », « Absent », « Chemin refusé », « Non vérifiable » ou « — ».
Les templates dynamiques et ambigus affichent « — » pour la présence.
Échappement Jinja et `Cache-Control: no-store` conservés ; aucun lien ou route HTTP ajouté.

## Sécurité

Aucun contenu de template lu, importé ou exécuté ; aucune analyse Jinja ni suivi des includes ou extends.
Les chemins proviennent uniquement de références statiques déjà identifiées. Aucune écriture, création ou correction du projet.
Comme les contrôles de métadonnées existants, cette vérification suppose des parents stables pendant l’appel ; elle ne constitue pas une protection générale contre les remplacements concurrents du filesystem.

## Fichiers créés

- [docs/rapports/FD-ROUTES-006.md](FD-ROUTES-006.md).

## Fichiers modifiés

- [forge_design/forge/routes.py](../../forge_design/forge/routes.py) : statut, confinement et cache de présence.
- [forge_design/web/templates/routes.html](../../forge_design/web/templates/routes.html) : colonne Présence.
- [tests/test_routes.py](../../tests/test_routes.py) : statuts, confinement et non-lecture.
- [tests/test_web_inspector.py](../../tests/test_web_inspector.py) : affichage HTTP.
- [docs/02-architecture.md](../02-architecture.md) : nouveau contrat et limites de la racine conventionnelle.

Aucune dépendance ou métadonnée de distribution modifiée.

## Tests ajoutés

16 nouveaux cas : 12 scénarios de présence, un test de cache/non-lecture et trois tests HTTP.
Ils couvrent présence, absence, sous-dossier, traversals, chemins absolus Unix et Windows, chaîne vide, segment point, fichier lié, parent lié, répertoire à la place du fichier et permission refusée simulée.
Les assertions existantes vérifient la présence non applicable pour les autres résolutions et les méthodes non vérifiées.
Le test de cache contrôle une seule vérification de cible pour deux routes, puis une nouvelle vérification au prochain appel. Il interdit les ouvertures autres que les sources de routes/contrôleurs ainsi que `Path.open`, `iterdir`, `glob` et `rglob`.
Octets et dates de modification sont comparés avant/après. Un contenu non UTF-8 et Jinja invalide n’empêche pas `present`.
Les tests HTTP vérifient Présent, Absent, Chemin refusé, l’échappement et `no-store`. Les suites Inspector et registre existantes restent actives.

## Test réel

Wheel reconstruite, archive inspectée puis installation temporaire `pip --no-deps --no-index --target`.
Un processus Python isolé (`-I`) vérifie l’origine de l’import et utilise les dépendances runtime de `.venv`.
Une copie temporaire du squelette reçoit un contrôleur contact, son branchement et `mvc/views/contacts/list.html` avec un contenu quelconque.
Le GET `/routes` affiche `contacts/list.html` avec « Présent ». Après suppression de cette seule vue dans la copie, le GET suivant conserve la référence et affiche « Absent ».
Le dépôt Forge de référence reste intact ; thread arrêté, socket fermé et port réutilisable.

Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `3c1f3852630b755ec72178754b968de4c0615acb7086323b0e3f07a48d39303b`.
Script ignoré par Git : `tmp/verify_fd_routes_006.py`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat |
|---|---|
| État Git, historique et référence Forge main | Vérifiés |
| `pytest` | 315 tests réussis, dont 16 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| `python -m pip wheel --no-deps --wheel-dir tmp/wheels .` | Succès |
| Wheel installée, HTTP Présent puis Absent | Succès |

Outils de `.venv`, Python 3.13.5 ; sockets locaux autorisés hors sandbox.
Pip a désactivé son cache utilisateur inaccessible dans le sandbox, sans erreur de dépendances.
Le diff complet est relu avant commit, rapport compris.

## Tests sautés

Aucun test pytest sauté. Aucun rendu du template cible, contrôle visuel navigateur ou nouvelle génération Forge revendiqué.

## Limites restantes

Racine conventionnelle uniquement : les personnalisations `VIEWS_DIR` et opt-ins restent hors contrat.
Présence ne signifie ni validité Jinja ni rendu effectif. Aucun contenu, héritage ou dépendance de vue analysé.
Le résultat est un instantané et hérite des limites de stabilité filesystem du Bridge.

## État Git final

Un seul commit local sur `main`, rapport inclus, sans push.
Message : `feat: vérifier la présence des templates (FD-ROUTES-006)`.
Le hash et l’état Git après commit sont communiqués dans la réponse de livraison.
