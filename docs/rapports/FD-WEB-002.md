# Rapport — FD-WEB-002

## Ticket et objectif

Migrer le shell Web vers Forge MVC en conservant son contenu et l'écoute locale, sans ajouter de fonctionnalité métier.
Forge Design est lui-même une application Web construite avec Forge.

## État Git initial

- Branche : `main`, propre, avec un commit local d'avance sur `origin/main`.
- HEAD : `a06199e` — FD-UI-001, non poussé au début du ticket.
- Référence distante : `4a2c7d0` — FD-WEB-001.
- `git status` et `git log --oneline --decorate -5` exécutés avant modification.

## API Forge vérifiée

`git ls-remote https://github.com/caucrogeGit/Forge.git refs/heads/main` a confirmé le commit `73a956e587e5f169c028415e0e540c149cbaff56`, identique au checkout inspecté.
Sa version déclarée est `1.0.0rc9`.
La distribution publiée a ensuite été installée dans `.venv` ; les signatures utilisées ont été revérifiées sur les modules de `site-packages`, sans import depuis le checkout voisin.

| Besoin | API réelle inspectée et décision |
|---|---|
| Application | `core.app.application.Application(router, ..., api_routes_module=None)` : construction explicite documentée |
| Fabrique configurée | `core.app.app_factory.build_application()` charge `config` et `bootstrap` ; non retenue pour éviter les imports implicites du cwd |
| Routage | `core.http.router.Router.add(method, pattern, handler, public=True)` |
| Réponse | `core.http.response.Response.html` et constructeur `Response` pour le CSS |
| Rendu Jinja | `integrations.jinja2.renderer.Jinja2Renderer(views_dir).render(template, context)` ; API vérifiée mais non nécessaire au shell statique |
| Adaptateur serveur | `core.app.wsgi.create_wsgi_app(application)` : requêtes, dispatch et protections Forge |
| Lancement Forge | `forge run` délègue au `app.py` du squelette et suppose une racine applicative ; non invoqué depuis Forge Design |
| Transport local | Le callable WSGI public de Forge est servi par `wsgiref.simple_server.make_server`, sans gestionnaire de routage maison |

Sources inspectées : [Application](https://github.com/caucrogeGit/Forge/blob/73a956e587e5f169c028415e0e540c149cbaff56/core/app/docs/application.md), [WSGI](https://github.com/caucrogeGit/Forge/blob/73a956e587e5f169c028415e0e540c149cbaff56/core/app/wsgi.py), [déploiement WSGI](https://github.com/caucrogeGit/Forge/blob/73a956e587e5f169c028415e0e540c149cbaff56/docs/deployment/wsgi-deployment.md), ainsi que les sources du routeur, des réponses, du renderer et de `cli/project/run.py`.

## Architecture retenue

```text
HTTP local → transport WSGI standard → adaptateur WSGI Forge
           → Application Forge → Router Forge → Response Forge
```

`create_application() -> Application` crée deux routes publiques explicites : `/` et `/shell.css`.
La configuration implicite des routes API est désactivée par le paramètre public `api_routes_module=None`.
Les middlewares de sécurité par défaut ne sont pas remplacés ; les routes du shell utilisent le drapeau public prévu par Forge.
Aucun service d'authentification, session, base de données ou Tool n'est ajouté par Forge Design.
Les détails de transport restent dans `create_server` et `run_server`, avec la même API d'écoute locale.

Le HTML reste une ressource du paquet ; `Response.html` le sert sans moteur de templates artificiel.
Les styles sont extraits à l'identique dans une ressource CSS pour respecter la CSP Forge.
Le contenu affiché reste « Forge Design » et « Aucun projet ouvert. ».

## Dépendance Forge ajoutée

`pyproject.toml` déclare `forge-mvc==1.0.0rc9` comme dépendance runtime.
Le paquet provient de l'index Python, pas du checkout voisin.
Les dépendances transitives de Forge sont installées normalement, dont Jinja2 ; aucune autre dépendance Web n'est ajoutée directement.
Aucun fichier Forge Core n'est modifié.

## Politique de version

Un pin exact est retenu parce que le backend est encore une préversion et qu'une seule baseline a été vérifiée.
Une plage ouverte aux futures RC annoncerait une compatibilité non testée.
Une évolution du pin nécessitera de rejouer les validations Web et de packaging ; ce choix n'établit pas une politique définitive pour Forge stable.

Ce pin concerne uniquement le moteur exécutant Forge Design.
`read_forge_version` reste inchangé et indépendant : un test confirme qu'un projet déclarant `99.0.0` retourne cette valeur alors que le runtime est `1.0.0rc9`.

## Migration depuis HTTPServer

Le gestionnaire `_Handler`, son `do_GET` et son routage conditionnel sont supprimés.
Forge Design n'importe plus `HTTPServer` ni `BaseHTTPRequestHandler`.
Il n'existe aucun chemin concurrent servant l'ancien shell.
Le transport `wsgiref` utilise des composants HTTP de la bibliothèque standard en interne, mais ne porte aucun routage applicatif Forge Design : toutes les requêtes passent par Forge.

Comportements natifs conservés : `/health` retourne la sonde de Forge ; les paramètres d'URL sont séparés du chemin par Forge.
Aucun filtre n'est ajouté pour supprimer ces comportements ou reproduire artificiellement l'ancien gestionnaire.
Les 404 sont produites par Forge, avec son repli texte quand aucun renderer d'erreur n'est enregistré.
Le transport WSGI journalise les requêtes sur stderr ; l'ancien silence des logs et son délai d'inactivité de deux secondes ne sont pas reproduits.

## Sécurité réseau

- `127.0.0.1` est le seul hôte accepté ; aucun repli sur `0.0.0.0`.
- Port par défaut `8765`, port éphémère `0` autorisé pour les tests.
- Les erreurs de paramètres et de port occupé restent explicites.
- Les en-têtes de sécurité sont ceux de Forge, dont CSP et `X-Content-Type-Options`.
- Aucun `unsafe-inline` ajouté : `/shell.css` respecte `style-src 'self'`.
- Aucune URL n'est transformée en chemin filesystem ; les ressources HTML et CSS sont nommées explicitement.
- Aucun import de code du projet cible ou du cwd dans la composition Web.

Le runtime Forge conserve ses comportements internes, notamment la sonde santé et la prise en charge éventuelle des opt-ins médias installés dans son environnement.
Aucun opt-in média n'est installé pour cette livraison ; un environnement runtime dédié reste préférable.

## Fichiers créés

- [forge_design/web/static/shell.css](../../forge_design/web/static/shell.css)
- [docs/rapports/FD-WEB-002.md](FD-WEB-002.md)

## Fichiers modifiés

- [forge_design/web/server.py](../../forge_design/web/server.py) : application, routes et adaptateur Forge ; transport WSGI unique.
- [forge_design/web/templates/index.html](../../forge_design/web/templates/index.html) : lien vers le CSS au lieu du bloc intégré.
- [pyproject.toml](../../pyproject.toml) : dépendance runtime et ressource CSS distribuée.
- [tests/test_web_server.py](../../tests/test_web_server.py) : types WSGI, réponses Forge et protections.
- [docs/02-architecture.md](../02-architecture.md) : architecture active et distinction runtime/cible.

Les anciens rapports restent des comptes rendus historiques ; leurs descriptions du serveur précédent ne sont pas réécrites.

## Fichiers supprimés

Aucun fichier entier supprimé ; l'ancien gestionnaire HTTP est supprimé dans `server.py`.

## Tests ajoutés/modifiés

28 cas Web passent, contre 25 avant migration.
Deux attentes propres au serveur expérimental sont retirées : `/health` en 404 et l'URL avec paramètres en 404.
Cinq cas ajoutés vérifient l'application Forge réelle, les headers/CSS/CSP, la sonde native, l'absence d'import de code depuis le cwd et l'indépendance de la version cible.
Les tests existants continuent de couvrir HTTP 200, HTML, contenu du shell, chemins inconnus et traversal, absence d'appel métier, cwd indépendant, arrêt, port libéré et écoute locale.
Une recherche du code confirme l'absence des imports `HTTPServer` et `BaseHTTPRequestHandler` dans Forge Design.

## Test d'intégration réel

Effectué sur la wheel construite : installation `pip --no-deps --no-index --target <temp>/installed`, dépendances runtime déjà présentes dans `.venv`.
Un sous-processus Python isolé (`-I`), lancé depuis un cwd temporaire, importe Forge Design depuis ce répertoire installé, et vérifie l'origine du module.
Il crée le serveur sur `127.0.0.1`, port `0`, démarre une boucle contrôlée, effectue `GET /` et `GET /shell.css`, vérifie HTML, état sans projet, CSS et CSP, puis arrête et joint le thread.
Le socket est fermé et le port réutilisable.
Résultat : succès, sans processus ni thread résiduel.

La wheel contient HTML et CSS ainsi que la dépendance `forge-mvc==1.0.0rc9` dans ses métadonnées.
Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `237c27050dde4b146a722059c2ef59f396d10dee042f97d89648d40d3ec77efb`.
Script local de vérification : `tmp/verify_fd_web_002.py` (artefact de travail ignoré par Git).

## Commandes exécutées et résultats

| Commande / contrôle | Résultat |
|---|---|
| `git status`, `git log --oneline --decorate -5` | État initial inspecté |
| `git ls-remote https://github.com/caucrogeGit/Forge.git refs/heads/main` | Référence main confirmée |
| `python -m pip index versions --pre forge-mvc` | rc9 publiée et disponible |
| `python -m pip install forge-mvc==1.0.0rc9` | Installation réussie |
| `python -m pip install -e .` | Métadonnées et dépendances Forge Design installées |
| `pytest` | 165 tests réussis, dont 28 cas Web |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| `python -m pip wheel --no-deps --wheel-dir tmp/wheels .` | Wheel construite |
| Installation temporaire et HTTP réel depuis la wheel | Succès |

Les outils sont ceux de `.venv`. Les tests HTTP nécessitent l'autorisation de sockets locaux hors sandbox.
Un diagnostic Pyright sur la signature non typée de `monkeypatch.syspath_prepend` a été résolu avec `monkeypatch.setattr(sys, "path", ...)`, sans suppression de diagnostic.
Le diff complet est relu avant commit, rapport inclus.

## Tests sautés

Aucun test pytest sauté.
Aucun test visuel navigateur n'est revendiqué ; les réponses HTTP, ressources et protections sont vérifiées réellement.

## Limites restantes

- Transport WSGI standard synchrone réservé au service local, sans délai d'inactivité spécifique ni capacités de production publique.
- Pas de renderer Jinja enregistré pour le shell statique ; les erreurs Forge utilisent leur repli et peuvent journaliser l'absence de renderer.
- Forge porte certaines configurations et caches internes au processus ; aucun mécanisme multi-application n'est promis ici.
- La sonde `/health` et le parsing des paramètres suivent Forge, pas l'ancien comportement expérimental.
- Pin préversion à faire évoluer explicitement après tests.
- Aucun choix de projet, formulaire, Tool Web, session applicative ou authentification ajouté.

## État Git final

Un seul commit pour ce ticket sur `main`, rapport inclus, sans push.
Le commit FD-UI-001 était déjà local au début du ticket ; la branche aura donc deux commits d'avance sur `origin/main` à la livraison.
Message : `refactor: utiliser Forge pour le Web (FD-WEB-002)`.
Le hash et l'état final vérifié sont communiqués dans la réponse de livraison.

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-WEB-002.md
```
