# Rapport — FD-UI-002

## Ticket et objectif

Relier le formulaire Web à Project Inspector via le registre existant, en lecture seule et sans conserver de projet entre requêtes.

## État Git initial

- Branche `main`, propre et synchronisée avec `origin/main`.
- HEAD `9b31522` — `refactor: utiliser Forge pour le Web (FD-WEB-002)`.
- État et historique Git inspectés avant modification.

## Routes ajoutées

- `GET /inspector` : formulaire vierge, statut 200.
- `POST /inspector` : validation HTTP, appel au Tool et diagnostic HTML.
- L'accueil propose un lien vers Inspector ; `/shell.css` reste la ressource de styles commune.

## Flux Web → Tool → Bridge

Chaque `create_application()` appelle `create_tool_registry()` une fois.
Le POST utilise `registry.get("project-inspector").run(Path(path))`.
Le registre conserve son contrat hétérogène : le consommateur Web vérifie que le résultat est un `ProjectInspection` avant rendu.
Aucune résolution, détection ou lecture de version n'est dupliquée dans le Web.
Le registre appartient à l'application ; le chemin et le résultat restent locaux à la requête.

## Renderer et templates

`Jinja2Renderer` public de Forge rend `templates/inspector.html` avec son échappement automatique.
`importlib.resources.files` et `as_file` fournissent le dossier des templates du paquet au renderer.
Aucune interpolation HTML manuelle, aucun filtre `safe`, aucune modification du registre global de renderers Forge.
Le shell d'accueil demeure statique. Jinja2 est déjà une dépendance transitive de Forge ; aucune dépendance ajoutée.
Une suppression Pyright ciblée concerne uniquement l'absence de stubs déclarés pour le paquet public `integrations.jinja2.renderer` de Forge rc9.

## Gestion du formulaire

Le champ `path` est obligatoire, limité à 4096 caractères côté HTML et serveur.
Un champ absent, vide, composé uniquement d'espaces ou trop long retourne 400.
Le texte n'est ni tronqué, ni nettoyé avec `strip`, ni développé avec `expanduser`.
`Path` adapte le type attendu par le Tool ; la résolution canonique appartient au Bridge.
Seul le format `application/x-www-form-urlencoded` est accepté (415 sinon).
Aucun cookie, session, configuration, fichier de préférences ou projet courant persistant n'est ajouté.
Un nouveau GET reste vierge après une inspection ; les réponses Inspector portent `Cache-Control: no-store`.

## Gestion des erreurs

Les exceptions `ProjectRootNotFoundError`, `ProjectRootNotDirectoryError` et `ProjectRootResolutionError` sont affichées avec statut 400, sans traceback.
Un projet structurellement invalide est un diagnostic 200 avec ses erreurs, pas une exception HTTP.
Version et source absentes sont affichées comme indéterminées ; les avertissements du Tool expliquent les versions absentes, illisibles ou contradictoires.
Les erreurs inattendues ne sont pas interceptées par cette couche ; elles restent confiées à Forge.

## Sécurité

L'écoute reste limitée à `127.0.0.1`, avec les paramètres et protections Forge existants.
Les valeurs saisies, chemins et diagnostics passent par l'échappement Jinja.
La couche Web ne lit que ses ressources packagées ; l'accès au projet passe par le Tool et le Bridge existants.
Aucune exécution de code cible ni écriture de projet n'est ajoutée.
La limite de champ intervient après le parsing HTTP Forge : ce n'est pas une limite globale de taille de requête.

## CSRF

Inspection du code installé de Forge rc9 : `CsrfMiddleware.check` recherche un jeton dans une session, même pour un POST public.
Utiliser ce mécanisme imposerait ici la session interdite par le ticket.
La seule route POST Inspector déclare donc explicitement `csrf=False`, sans modifier les middlewares globaux.
Avant tout appel au Tool, elle exige une origine exactement égale à `http://` suivi du Host local `127.0.0.1[:port]`.
Les origines absentes, nulles ou étrangères sont refusées avec 403.
`Sec-Fetch-Site`, lorsqu'il est présent, doit valoir `same-origin`.
Ce compromis est limité à cette opération locale en lecture seule et sans session ; il ne constitue pas une authentification des clients locaux capables de fournir leurs propres en-têtes.
Les clients HTTP doivent envoyer l'origine locale exacte. Aucun jeton maison n'est créé.

## Fichiers créés

- [forge_design/web/inspector.py](../../forge_design/web/inspector.py)
- [forge_design/web/templates/inspector.html](../../forge_design/web/templates/inspector.html)
- [tests/test_web_inspector.py](../../tests/test_web_inspector.py)
- [docs/rapports/FD-UI-002.md](FD-UI-002.md)

## Fichiers modifiés

- [forge_design/web/server.py](../../forge_design/web/server.py) : composition et routes explicites.
- [forge_design/web/templates/index.html](../../forge_design/web/templates/index.html) : lien Inspector.
- [forge_design/web/static/shell.css](../../forge_design/web/static/shell.css) : formulaire et diagnostics.
- [pyproject.toml](../../pyproject.toml) : template distribué.
- [docs/02-architecture.md](../02-architecture.md) : flux et contrats réellement disponibles.

Le Bridge, les Tools, le registre et Forge Core sont inchangés.

## Tests ajoutés

21 cas HTTP couvrent le formulaire, l'inspection valide et invalide, la racine canonique, les trois erreurs attendues de racine, les versions indéterminables, les avertissements, les champs invalides, les origines refusées, le type de contenu, l'absence de cookie et de conservation de résultat, ainsi que l'absence de modification du projet.
Un faux Tool enregistré via une composition instrumentée vérifie l'appel unique au registre et au Tool, sans accès direct au chemin cible par le Web, ainsi que l'échappement du chemin et d'un diagnostic contenant du HTML.
Les suites Bridge et Inspector existantes restent actives.

## Test réel

Depuis la wheel installée temporairement, un processus Python isolé (`-I`) importe le serveur depuis le répertoire installé et effectue de vrais GET et POST locaux.
Le POST cible `../Forge/skeleton/data`, référence locale utilisée dans les tickets précédents (`73a956e587e5f169c028415e0e540c149cbaff56`).
Résultat 200 : version `1.0.0rc9`, source `requirements.txt` ; aucun cookie et formulaire vierge au GET suivant.
Le contrôle vérifie aussi l'accueil, le CSS, la CSP, l'arrêt du thread, la fermeture du socket et la réutilisation du port.
Ce contrôle porte sur le squelette officiel local, pas sur une nouvelle génération par `forge new`.
Script de travail ignoré par Git : `tmp/verify_fd_ui_002.py`.

## Packaging

Wheel construite avec `python -m pip wheel --no-deps --wheel-dir tmp/wheels .`.
Inspection ZIP : présence des deux fichiers HTML et du CSS, ainsi que de la dépendance Forge dans les métadonnées.
Installation temporaire avec `pip --no-deps --no-index --target`, puis rendu Jinja réel depuis cette installation, sans import de Forge Design depuis le checkout.
Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `276e16c39251a8b9670a7978277445e2bd09f49e6482512e933f93508b7570a3`.
Les dépendances runtime proviennent de `.venv` ; aucun environnement entièrement vierge de dépendances n'est revendiqué.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| `git status`, historique Git | État initial inspecté |
| `pytest` | 186 tests réussis, dont 21 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| `python -m pip wheel --no-deps --wheel-dir tmp/wheels .` | Succès |
| Installation temporaire et HTTP depuis la wheel | Succès |

Outils de `.venv`, Python 3.13.5. Les tests HTTP ont été exécutés avec autorisation de sockets locaux hors sandbox.
Les diagnostics initiaux d'import Ruff et de signature du faux Tool Pyright ont été corrigés avant validation finale.
Une commande préparatoire utilisant `python` sans préfixe a échoué car cet alias n'existe pas ; les validations utilisent bien l'interpréteur de `.venv`.
Le diff complet, rapport compris, est relu avant commit.

## Tests sautés

Aucun test pytest sauté.
Aucun contrôle visuel navigateur ni nouvelle génération Forge n'est revendiqué.

## Limites restantes

- Transport local synchrone et limites internes Forge inchangés.
- Aucun état de projet persistant, sélecteur natif de dossiers ou contrôle de compatibilité ajouté.
- Les chemins relatifs sont interprétés par le Bridge dans le répertoire courant du serveur.
- Protection d'origine destinée aux navigateurs, sans authentification locale.
- Les garanties de lecture seule et de stabilité du système de fichiers restent celles du Bridge.

## État Git final

Un seul commit local sur `main`, rapport inclus, sans push.
Message : `feat: afficher Project Inspector dans le Web (FD-UI-002)`.
Le hash et l'état final vérifié sont communiqués dans la réponse de livraison.

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-UI-002.md
```
