# Rapport — FD-ROUTES-003

## Ticket et objectif

Relier une référence de handler à un fichier contrôleur explicitement importé par sa source de routes, sans lecture du contenu ni exécution du contrôleur.

## État Git initial

- Branche `main`, propre et synchronisée avec `origin/main`.
- HEAD `6a80884` — `feat: afficher les handlers des routes (FD-ROUTES-002)`.
- État Git et cinq derniers commits inspectés avant modification.

## Conventions Forge vérifiées

`git ls-remote https://github.com/caucrogeGit/Forge.git refs/heads/main` confirme `73a956e587e5f169c028415e0e540c149cbaff56`, identique au checkout inspecté.
Le squelette importe `HomeController` depuis `mvc.controllers.home_controller`.
Le générateur CRUD `packages/forge-mvc-entities/forge_mvc_entities/make_crud.py` génère `mvc/controllers/{snake}_controller.py` et l'import `from mvc.controllers.{snake}_controller import {ctrl}`.
Le générateur auth `cli/security/make_auth.py` écrit `mvc/controllers/auth_controller.py` et importe `AuthController` depuis ce module dans les routes.
Le générateur pivot utilise un sous-paquet `mvc.controllers.pivot.*`, observé mais explicitement hors périmètre de ce ticket.

## Résolution des imports contrôleurs

Seuls les imports absolus `from mvc.controllers.<identifiant_simple> import Symbole` sont associés à un chemin relatif `mvc/controllers/<identifiant_simple>.py`.
`as Alias` est accepté : la référence affichée demeure `Alias.method`.
Aucune recherche globale par classe, aucune résolution Python dynamique.
Les imports concurrents et réaffectations explicites au niveau module rendent l'association ambiguë et sont écartés conservativement.

## Modèle de données

`HandlerInfo` reste gelée et ajoute `controller_file: str | None = None`.
La référence syntaxique et tous les champs de `RouteInfo` restent inchangés ; le nouveau champ est uniquement un enrichissement.
Un handler simple comme `health` conserve un contrôleur absent.

## Résolution par fichier de routes

Chaque AST source fournit sa propre table d'imports.
Pour un fichier branché, les imports de ce module sont transmis lors de l'analyse du corps de sa fonction ; ceux de la racine ne sont pas réutilisés.
Les imports reconnus sont ceux du niveau module, sans analyse dynamique des portées Python.
La résolution se fait à partir du premier nom de la référence pointée, uniquement si un import autorisé existe dans cette table.

## Cas non résolus

Fonction simple, handler dynamique, import extérieur, relatif, sous-paquet ou absence d'import identifiable : aucun contrôleur inventé.
Un import autorisé dont le fichier manque conserve la route et le handler et produit un warning explicite.
Un lien symbolique, un type incorrect ou un accès impossible produit également un warning ; le champ reste `None`.
Les warnings existants restent conservés.

## Vérification filesystem

`lstat` vérifie les parents `mvc` et `mvc/controllers`, puis le fichier attendu.
Les parents doivent être des dossiers ordinaires et le fichier un fichier ordinaire : les liens sont refusés, internes comme externes.
Aucun `open`, `read_text`, `iterdir` ou scan du dossier contrôleurs pour cette résolution.
Le chemin rendu reste relatif au projet.

## Intégration Bridge

`read_routes` conserve son API et effectue cet enrichissement dans le parcours AST existant.
Aucun deuxième parcours de fichiers ni cache dans le contexte projet.
La lecture et les limites des sources de routes restent celles de FD-ROUTES-001.

## Intégration Web

La page `/routes` ajoute la colonne Contrôleur après Handler, avec chemin relatif ou « — ».
Aucun lien cliquable, nouvelle page ou nouveau Tool.
Échappement Jinja conservé, sans `safe`, et `Cache-Control: no-store` inchangé.

## Sécurité

Le contenu d'un contrôleur n'est ni lu, ni parsé, ni importé, ni exécuté.
Aucune classe ou méthode n'est validée. Un fichier contenant du Python invalide peut être associé : seule sa présence comme fichier ordinaire est confirmée.
Les noms de module stricts interdisent les sous-répertoires et chemins arbitraires.
Comme les contrôles existants du Bridge, ces vérifications supposent des parents stables durant l'opération ; elles ne garantissent pas l'absence de modifications concurrentes.

## Fichiers créés

- [docs/rapports/FD-ROUTES-003.md](FD-ROUTES-003.md)

## Fichiers modifiés

- [forge_design/forge/routes.py](../../forge_design/forge/routes.py) : table par source, métadonnées et enrichissement.
- [forge_design/web/templates/routes.html](../../forge_design/web/templates/routes.html) : colonne Contrôleur.
- [tests/test_routes.py](../../tests/test_routes.py) : résolution et cas refusés.
- [tests/test_web_inspector.py](../../tests/test_web_inspector.py) : affichage HTTP.
- [docs/02-architecture.md](../02-architecture.md) : contrat réellement disponible.

## Tests ajoutés

13 nouveaux cas : import direct et alias dans la racine et un module branché ; fichier absent, lien fichier, lien parent, import extérieur, sous-paquet, import relatif, fonction simple, handler dynamique et isolation des imports entre sources.
Des sentinelles interdisent le scan et limitent les ouvertures bas niveau aux fichiers de routes ; les contrôleurs ont un contenu invalide et leur contenu/date de modification restent identiques après lecture.
Le test HTTP vérifie le chemin et la colonne Contrôleur avec les assertions existantes de tableau, absence, échappement et no-store.
Les suites de registre, Inspector, confinement et ordre restent actives.

## Test réel

Wheel construite, ressources inspectées et installation temporaire `pip --no-deps --no-index --target`.
Un processus Python isolé importe cette installation avec les dépendances de `.venv`.
Une copie temporaire du squelette reçoit `mvc/controllers/contact_controller.py` avec contenu invalide et `contact_routes.py` avec import explicite et branchement.
`GET /routes` affiche `/contact/list`, `ContactController.list` et `mvc/controllers/contact_controller.py`, sans interpréter le contrôleur.
Le dépôt Forge de référence reste inchangé ; le contrôle arrête le serveur et libère le port.

Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `54f03d06db3352948c5e3e4c6492224b5f17079bd6d60636a41a5460d09b58e2`.
Script ignoré par Git : `tmp/verify_fd_routes_003.py`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| État Git et historique | Inspectés |
| `git ls-remote` Forge main | Référence confirmée |
| `pytest` | 262 tests réussis, dont 13 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| Construction wheel et HTTP depuis installation | Succès |

Outils de `.venv`, Python 3.13.5 ; échanges HTTP avec autorisation de sockets locaux hors sandbox.
Les lignes de fixtures signalées trop longues par Ruff ont été corrigées avant validation finale.
Le diff complet est relu avant commit, rapport compris.

## Tests sautés

Aucun test pytest sauté. Aucun contrôle visuel navigateur ou exécution de contrôleur revendiqué.

## Limites restantes

- Association syntaxique à un fichier existant, sans preuve d'identité runtime du symbole.
- Pas d'analyse complète des portées, imports conditionnels ou réaffectations dynamiques.
- Imports de sous-paquets, relatifs et imports locaux aux fonctions non résolus.
- Aucune classe, méthode, signature, docstring ou template vérifié.

## État Git final

Un seul commit local sur `main`, rapport inclus, sans push.
Message : `feat: relier les handlers aux contrôleurs (FD-ROUTES-003)`.
Le hash et l'état Git final sont communiqués dans la réponse de livraison.
