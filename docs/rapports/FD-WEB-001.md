# Rapport — FD-WEB-001

## Ticket et objectif

Ajouter un serveur HTTP local minimal, avec réponse fixe, API Python réutilisable et arrêt propre.
Aucun projet n'est sélectionné ou inspecté ; aucune UI métier ni ouverture de navigateur n'est ajoutée.

## État Git initial

- Branche : `main`, synchronisée avec `origin/main`.
- HEAD : `5c98c1f` — `feat: ajouter le point de composition (FD-PLATFORM-003)`.
- Répertoire de travail propre.
- `git status` et `git log --oneline --decorate -5` exécutés avant modification.

## Serveur retenu

`http.server.HTTPServer` et un gestionnaire privé dérivé de `BaseHTTPRequestHandler` suffisent pour une réponse texte fixe.
Contrairement à un gestionnaire de fichiers, ce gestionnaire ne fournit ni répertoire public ni accès au filesystem.
Le service est synchrone : aucun thread de requête ni framework supplémentaire n'est nécessaire pour ce périmètre.

Références consultées : [http.server](https://docs.python.org/3/library/http.server.html) et [socketserver](https://docs.python.org/3/library/socketserver.html).
La documentation standard décrit le cycle `serve_forever` / `shutdown` / fermeture ; `shutdown` doit être appelé depuis un autre thread que celui servant les requêtes.
Le choix est limité à ce service local à réponse fixe, pas à un serveur public de production.

## Dépendances

Aucune dépendance ajoutée : bibliothèque standard uniquement.
Le paquet `forge_design.web` est ajouté à la liste explicite des paquets distribués dans `pyproject.toml`.
`pip check` n'est pas requis par le ticket en l'absence de nouvelle dépendance.

## Host et port

- Hôte par défaut et seul hôte accepté : `127.0.0.1`.
- Port par défaut : `8765`, fixe et explicite.
- Port `0` : attribution d'un port éphémère par le système, utilisée par tous les tests qui démarrent un serveur.
- Ports hors de `0..65535` et booléens : `ValueError`.
- Autres hôtes, dont `0.0.0.0`, chaîne vide, `localhost` et IPv6 : `ValueError` avant création du socket.
- Port occupé : `OSError` avec `errno.EADDRINUSE` dans l'environnement testé ; aucun changement automatique de port.

## API ajoutée

```python
from forge_design.web.server import create_server, run_server

# Appel bloquant, arrêt par Ctrl+C.
run_server()  # 127.0.0.1:8765
```

Signatures :

```python
create_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> HTTPServer
run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None
```

`create_server` ouvre le socket d'écoute sans lancer la boucle HTTP et retourne l'instance standard à gérer explicitement.
`run_server` constitue l'entrée Python bloquante, sans modification de la CLI.

La seule route implémentée est `GET /` : code 200, `Content-Type: text/plain; charset=utf-8`, corps `Forge Design\n` et longueur explicite.
Les autres chemins, y compris `/health` et les requêtes contenant un paramètre de projet, retournent 404.
Les méthodes non implémentées conservent le traitement standard du gestionnaire HTTP.

## Sécurité réseau

L'API n'autorise que la boucle locale IPv4 ; aucun repli vers `0.0.0.0`.
Le gestionnaire ne lit aucun projet ni fichier, n'exécute aucune commande et n'accepte aucun chemin de projet.
Il n'importe ni le Bridge, ni Project Inspector, ni le point de composition.
Les URL reçues ne sont jamais utilisées comme chemins de fichiers.
La journalisation des requêtes est désactivée pour ne pas recopier les chemins fournis par les clients.
Aucun secret ou état utilisateur n'est chargé par le serveur.

## Gestion du cycle de vie

`run_server` utilise un bloc `with` qui ferme le socket à la sortie.
`KeyboardInterrupt` est traité comme un arrêt normal ; les autres exceptions sont propagées après fermeture.
Il n'appelle pas `shutdown` depuis le thread de service : cet appel depuis le même thread provoquerait un blocage.

Les tests utilisent un thread de service explicitement créé, `shutdown` depuis le thread de test, `join` avec délai et fermeture du serveur dans le bloc `with`.
Ils vérifient que le thread est terminé et que le port peut être réutilisé.
Le serveur de production ne crée aucun thread implicitement.
Un délai de deux secondes borne l'attente d'une connexion inactive ; il ne s'agit pas d'un délai global de requête.

## Fichiers créés

- [forge_design/web/__init__.py](../../forge_design/web/__init__.py)
- [forge_design/web/server.py](../../forge_design/web/server.py)
- [tests/test_web_server.py](../../tests/test_web_server.py)
- [docs/rapports/FD-WEB-001.md](FD-WEB-001.md)

## Fichiers modifiés

- [pyproject.toml](../../pyproject.toml) : inclusion du paquet Web.
- [docs/02-architecture.md](../02-architecture.md) : API locale, adresse, port et cycle de vie réellement disponibles.

La CLI, le Bridge, les Tools et le registre restent inchangés.

## Tests ajoutés

19 cas couvrent :

- valeurs par défaut des deux API ;
- adresse réelle du socket, port attribué, réponse 200 et contenu attendu ;
- quatre chemins non servis ;
- absence d'appel à Project Inspector ou au Bridge et absence d'ouverture de fichier via `Path.open` pendant une requête ;
- arrêt, terminaison du thread, fermeture et réutilisation du port ;
- port déjà occupé ;
- trois ports invalides ;
- cinq hôtes refusés ;
- fermeture de `run_server` sur Ctrl+C et sur exception inattendue.

## Commandes exécutées et résultats

Les outils utilisés proviennent de `.venv`.

| Commande | Résultat final |
|---|---|
| `git status` | État initial propre |
| `git log --oneline --decorate -5` | Historique initial inspecté |
| `pytest` | 156 tests réussis, dont 19 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |

Le premier passage des tests Web dans le sandbox a échoué avant écoute avec `PermissionError: Operation not permitted` lors de la création de sockets.
Les tests ont ensuite été exécutés avec autorisation de sockets locaux hors sandbox ; les 19 cas Web passent et aucun n'a été sauté.
La suite complète est également exécutée dans ce contexte pour inclure les échanges HTTP réels.
Le diff complet est relu avant le commit, rapport compris.

## Tests sautés

Aucun test pytest sauté.
Aucun test navigateur, génération Forge ou build de distribution n'est revendiqué.

## Limites restantes

- Service local synchrone minimal, réservé à une réponse fixe ; pas de serveur public de production.
- Un client actif lent peut monopoliser le traitement ; le délai d'inactivité n'est pas une échéance absolue.
- IPv4 `127.0.0.1` uniquement, sans authentification ni TLS.
- Aucune intégration CLI, navigateur, Project Inspector ou UI métier.
- Les tests HTTP nécessitent un environnement autorisant les sockets sur la boucle locale.

## État Git final

Livraison sur `main` dans un seul commit local, rapport inclus, sans push.
Message : `feat: ajouter le serveur Web local minimal (FD-WEB-001)`.
Le hash et l'état Git vérifié après commit sont communiqués dans la réponse de livraison.

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-WEB-001.md
```
