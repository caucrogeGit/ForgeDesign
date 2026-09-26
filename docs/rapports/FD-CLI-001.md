# Rapport — FD-CLI-001

## Ticket et objectif

Faire de `forge-design` le lancement normal de l'application Web locale existante, sans nouvelle fonctionnalité métier ni ouverture automatique du navigateur.

## État Git initial

- Branche `main`, propre et synchronisée avec `origin/main`.
- HEAD `5a21caf` — `feat: afficher Project Inspector dans le Web (FD-UI-002)`.
- État Git et cinq derniers commits inspectés avant modification.

## Comportement CLI

Sans argument, la commande affiche la version Forge Design et l'URL `http://127.0.0.1:8765`, puis reste active jusqu'à l'arrêt du serveur.
La sortie est explicitement vidée pour être visible même lorsqu'elle est redirigée.
L'URL est annoncée avant l'appel bloquant ; elle ne constitue pas une confirmation que le socket est déjà ouvert.
`--version` et `--help` conservent le comportement argparse existant et ne chargent pas le backend Web.
Aucune option de host, port ou chemin projet n'est ajoutée.

## Intégration avec le serveur Web

`forge_design.cli.main()` appelle `run_server(host=DEFAULT_HOST, port=DEFAULT_PORT)`.
Les constantes publiques existantes valent `127.0.0.1` et `8765`.
`run_server` réutilise `create_server` et toute l'application Forge déjà construite.
La CLI ne connaît ni le routeur, ni WSGI, ni le registre, ni Inspector.
Aucune modification du serveur ou des métadonnées de distribution n'est nécessaire.

## Gestion de l'arrêt

Le serveur existant traite `KeyboardInterrupt` dans sa boucle et ferme son socket via son gestionnaire de contexte.
La CLI traite également `KeyboardInterrupt` remontant de l'appel comme une sortie normale de code 0.
Aucun thread, daemon ou mécanisme de signal supplémentaire n'est introduit en production.

## Gestion des erreurs

Un `OSError` avec `errno.EADDRINUSE` affiche « Le port 8765 est déjà occupé. » sur stderr et retourne 1.
Les autres `OSError`, notamment une interdiction d'ouvrir le socket, affichent leur cause avec un message de serveur local et retournent 1.
Cette capture couvre les `OSError` remontant de l'appel serveur, y compris pendant son exécution ; elle n'est pas limitée au bind.
Aucun repli sur un autre port. Les autres exceptions inattendues restent propagées, sans capture générale.

## Fichiers créés

- [docs/rapports/FD-CLI-001.md](FD-CLI-001.md)

## Fichiers modifiés

- [forge_design/cli.py](../../forge_design/cli.py) : lancement, affichage et erreurs.
- [tests/test_cli.py](../../tests/test_cli.py) : délégation et tests de sortie.
- [README.md](../../README.md) : usage disponible, URL et arrêt.

## Tests ajoutés

Cinq nouveaux cas portent la suite CLI à huit cas ; le test sans argument est adapté au lancement.
Ils couvrent l'appel avec host et port exacts, l'URL, Ctrl+C, port occupé, permission refusée, propagation d'une erreur inattendue et fermeture du contexte serveur.
Le démarrage est exercé avec la vraie composition applicative, une boucle serveur simulée et des sentinelles interdisant l'exécution du Tool, l'inspection et les appels d'ouverture de navigateur.
Le test de `--version` utilise toujours la commande installée depuis un répertoire temporaire.
Les tests HTTP existants continuent de vérifier le serveur et le socket réels.

## Test réel

La commande installée `.venv/bin/forge-design` est lancée sans argument dans un répertoire temporaire.
Un client HTTP vérifie `GET /`, statut 200 et contenu « Aucun projet ouvert. ».
Un SIGINT arrête le processus avec code 0, sans traceback ; l'URL est bien présente sur stdout.
Le port est ensuite réutilisé pour une écoute de contrôle : un second lancement échoue avec code 1 et message de port occupé.
Tous les processus sont terminés et les sockets fermés.
Script séparé, ignoré par Git : `tmp/verify_fd_cli_001.py`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| État Git et `git log --oneline --decorate -5` | État initial inspecté |
| `pytest` | 191 tests réussis, dont 8 cas CLI |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| Commande installée, HTTP, SIGINT et port occupé | Succès |

Outils de `.venv`, Python 3.13.5 ; tests HTTP et contrôle réel exécutés avec autorisation de sockets locaux hors sandbox.
Une lambda de test non annotée signalée par Pyright a été remplacée par une fonction typée ; l'ordre des imports Ruff a été corrigé avant les validations finales.
Le diff complet est relu avant commit, rapport compris.

## Tests sautés

Aucun test pytest sauté.
Pas de reconstruction de wheel : les métadonnées et ressources distribuées sont inchangées.
Aucun test visuel navigateur n'est revendiqué.

## Limites restantes

- Port fixe 8765 ; le contrôle réel nécessite sa disponibilité initiale.
- Le message d'URL précède l'ouverture effective du socket.
- Le service conserve les limites du transport WSGI local existant.
- Aucun navigateur ouvert automatiquement, aucun projet sélectionné au démarrage.

## État Git final

Livraison sur `main` dans un seul commit local, rapport suivi et inclus, sans push.
Message : `feat: lancer Forge Design depuis la CLI (FD-CLI-001)`.
Le hash et l'état Git vérifié après commit sont communiqués dans la réponse de livraison.

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-CLI-001.md
```
