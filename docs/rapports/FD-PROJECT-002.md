# Rapport — FD-PROJECT-002

## Ticket et objectif

Réinspecter explicitement le projet courant via le Tool existant et mettre à jour ou vider son diagnostic runtime, sans persistance ni surveillance automatique.

## État Git initial

- Branche `main`, propre et synchronisée avec `origin/main`.
- HEAD `1bc4a15` — `feat: ajouter le contexte projet courant (FD-PROJECT-001)`.
- État Git et cinq derniers commits inspectés avant modification.

## Cycle d’actualisation

Après contrôle d'origine, le handler lit `context.root` et appelle le Tool sur cette racine uniquement.
Aucun chemin HTTP n'est utilisé, même si un champ est envoyé.
Un nouveau résultat valide remplace le diagnostic via `set_project` ; la racine canonique, la version et les avertissements proviennent entièrement de ce résultat.
La page Inspector affiche « Projet actualisé. » et le nouveau diagnostic.
Sans projet courant, la réponse est 409 avec « Aucun projet à actualiser. », sans appel au Tool.

## Projet devenu invalide

Un diagnostic structurellement invalide vide le contexte et est affiché avec ses erreurs et le message « Le projet n’est plus reconnu ; il a été fermé. ».
Le statut est 200, comme pour un diagnostic structurel invalide de l'Inspector initial.
Ce choix diffère volontairement d'une tentative d'ouverture d'un autre projet invalide : ici le diagnostic concerne le projet déjà courant et prouve qu'il n'est plus reconnu.

## Racine disparue

`ProjectRootNotFoundError`, `ProjectRootNotDirectoryError` et `ProjectRootResolutionError` vident le contexte et produisent un message exploitable, statut 400, sans traceback.
Les erreurs inattendues restent propagées ; aucune capture générale n'est ajoutée.

## Intégration ToolRegistry

L'appel est `registry.get("project-inspector").run(root)`.
Aucune instanciation directe du Tool ni appel direct à `inspect_project`, aucune duplication du Bridge.
Le type `ProjectInspection` est vérifié avant toute mise à jour, comme pour l'Inspector existant.
Le contexte et le registre demeurent propres à chaque application.

## Intégration Web

`POST /project/refresh` est la seule nouvelle route.
Le shell affiche un formulaire « Actualiser » distinct de « Fermer le projet », uniquement lorsqu'un projet existe.
Le GET n'effectue aucune mutation. Les pages et réponses conservent `Cache-Control: no-store`.
Le message de succès est local au rendu, avec `role="status"`, sans système de notifications persistant.
Le contexte lui-même n'est pas modifié : il stocke toujours un seul diagnostic.

## Sécurité

Le handler réutilise `is_local_action`, avant lecture de la racine et appel au Tool.
`csrf=False` est explicite sur cette action runtime sans session : le même choix que pour l'activation et la fermeture s'applique, le CSRF Forge rc9 étant fondé sur une session.
Une origine locale exacte est obligatoire ; `Sec-Fetch-Site`, lorsqu'il existe, doit être `same-origin`.
Origines absentes ou étrangères et requêtes cross-site sont refusées avec 403 avant mutation.
Le contrôle protège les soumissions de pages étrangères dans un navigateur ; il ne constitue pas une authentification des programmes locaux.
Aucun chemin utilisateur supplémentaire n'est lu, aucun fichier projet n'est écrit.

## Fichiers créés

- [docs/rapports/FD-PROJECT-002.md](FD-PROJECT-002.md)

## Fichiers modifiés

- [forge_design/web/inspector.py](../../forge_design/web/inspector.py) : handler d'actualisation et message de résultat.
- [forge_design/web/server.py](../../forge_design/web/server.py) : route explicite avec contexte et registre existants.
- [forge_design/web/templates/layout.html](../../forge_design/web/templates/layout.html) : action Actualiser.
- [forge_design/web/templates/inspector.html](../../forge_design/web/templates/inspector.html) : message contextuel.
- [tests/test_web_inspector.py](../../tests/test_web_inspector.py) : actualisation et délégation.
- [docs/02-architecture.md](../02-architecture.md) : diagnostic actualisable explicitement.

## Tests ajoutés

Huit nouveaux cas couvrent l'absence de projet, la nouvelle version, le remplacement des avertissements, la racine canonique, la structure devenue invalide, le dossier supprimé ou remplacé par un fichier et les refus de sécurité.
Le test de délégation existant vérifie également la récupération dans le registre et la transmission de la racine mémorisée malgré un autre chemin envoyé par HTTP.
Les contrôles vérifient `no-store`, l'absence d'écriture, l'absence d'actualisation lors d'un GET, le refus du GET sur la route et la fermeture après actualisation.
Les tests existants d'isolation des applications restent actifs ; aucun état global nouveau n'est introduit.

## Test réel

Wheel reconstruite et ressources inspectées dans l'archive, puis installation temporaire avec `pip --no-deps --no-index --target`.
Un processus Python isolé (`-I`) importe le serveur depuis cette installation ; les dépendances runtime proviennent de `.venv`.
Le squelette Forge de référence est copié dans un répertoire temporaire.
Après ouverture HTTP avec version `1.0.0rc9`, seul le `requirements.txt` de cette copie est modifié en `forge-mvc==2.0.0`.
Le POST d'actualisation retourne 200, « Projet actualisé. » et `2.0.0` ; la fermeture fonctionne ensuite.
Le dépôt Forge de référence n'est pas modifié. Le répertoire temporaire est nettoyé, le serveur arrêté et son port libéré.

Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `79e94965d9125d226f97b1f226172555cc580b5cd96e5ef78ee36c15780e092a`.
Script séparé ignoré par Git : `tmp/verify_fd_project_002.py`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| État Git et `git log --oneline --decorate -5` | État initial inspecté |
| `pytest` | 220 tests réussis, dont 8 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| `python -m pip wheel --no-deps --wheel-dir tmp/wheels .` | Succès |
| Wheel installée, actualisation HTTP sur copie temporaire | Succès |

Outils de `.venv`, Python 3.13.5 ; échanges HTTP avec autorisation de sockets locaux hors sandbox.
Le diff complet est relu avant commit, rapport compris.

## Tests sautés

Aucun test pytest sauté.
Aucun contrôle visuel navigateur ni nouvelle génération Forge revendiqué.

## Limites restantes

- Le diagnostic peut redevenir obsolète après actualisation ; aucune surveillance automatique.
- Les limites du Bridge et le partage du contexte entre clients d'une même instance sont conservés.
- Les exceptions inattendues ne vident pas automatiquement le contexte ; elles restent diagnostiquables par Forge.

## État Git final

Un seul commit local sur `main`, rapport inclus, sans push.
Message : `feat: actualiser le projet courant (FD-PROJECT-002)`.
Le hash et l'état Git vérifié après commit sont communiqués dans la réponse de livraison.

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-PROJECT-002.md
```
