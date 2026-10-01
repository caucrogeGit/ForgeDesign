# Rapport — FD-WEB-003

## Ticket et objectif

Refuser toute requête HTTP dont l'en-tête `Host` n'est pas l'adresse d'écoute
exacte, afin de fermer l'exposition au DNS rebinding relevée lors de l'audit du
1er octobre 2026. Aucune fonctionnalité métier ajoutée.

## État Git initial

- Branche : `main`, synchronisée avec `origin/main` après le commit
  `style: appliquer ruff format`.
- Une modification locale non liée (`docs/rapports/FD-CONTRACT-001.md`) est
  laissée hors de ce ticket.

## Constat

`is_local_action` ne protège que les POST. Les routes GET acceptaient n'importe
quel `Host` : `GET /` et `GET /debug` avec `Host: attacker.example:<port>`
répondaient `200`. Avec un projet ouvert, une page malveillante dont le domaine
est rebindé sur `127.0.0.1` pouvait lire `/source`, `/debug`, `/templates/view`,
etc. comme une page same-origin. `forge-mvc==1.0.0rc9` ne fournit aucune
validation de `Host` (recherche `allowed_host`/`trusted_host` vide).

## Architecture retenue

Contrôle au niveau du transport, dans `create_server` :

```text
HTTP local → garde Host → adaptateur WSGI Forge → Application Forge
```

- Le port effectif n'est connu qu'après le bind (port `0` éphémère) :
  `make_server` est appelé, puis `server.set_app` installe la garde qui lit
  `server.server_port`.
- Seul `127.0.0.1:<port>` est accepté ; sur le port 80, `127.0.0.1` sans port
  l'est aussi (forme envoyée par les navigateurs).
- `localhost`, `[::1]`, un autre port, un suffixe de domaine et un `Host` absent
  ou vide sont refusés, cohérents avec `is_local_action`.
- Refus : `400 Bad Request`, corps texte UTF-8, `Cache-Control: no-store`, sans
  dispatch Forge. Pages, ressources statiques et `/health` sont couverts.
- `create_wsgi_app` reste appelé une seule fois (avertissements Forge émis une
  seule fois).
- `create_application()` n'applique pas le contrôle : les tests qui dispatchent
  directement l'application ne sont pas concernés.

## Fichiers modifiés

- [forge_design/web/server.py](../../forge_design/web/server.py) : garde
  `_require_local_host` et installation dans `create_server`.
- [tests/test_web_server.py](../../tests/test_web_server.py) : 46 cas ajoutés.
- [docs/02-architecture.md](../02-architecture.md) : section « Contrôle de
  l'en-tête Host ».

## Fichiers créés

- [docs/rapports/FD-WEB-003.md](FD-WEB-003.md)

## Tests ajoutés

- `test_foreign_host_rejected` : 9 valeurs de `Host` × 5 chemins (`/`,
  `/shell.css`, `/health`, `/debug`, `/source`) → `400`.
- `test_exact_local_host_accepted` : `127.0.0.1:<port>` → `200` sur `/` et
  `/health`.

Les tests HTTP existants (client `HTTPConnection` vers `127.0.0.1:<port>`)
passent sans modification.

## Vérification réelle

Serveur sur port éphémère : `Host: attacker.example:<port>` → `400` sur `/` et
`/debug` ; `Host: 127.0.0.1:<port>` → `200`.

## Commandes exécutées et résultats

| Commande | Résultat |
|---|---|
| `pytest` | 2705 tests réussis (2659 + 46) |
| `ruff check .` | Succès |
| `ruff format --check .` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |

## Limites restantes

- Protection navigateur uniquement : un processus local peut toujours forger
  son `Host`, comme pour `is_local_action`. Pas d'authentification locale.
- Un accès via `http://localhost:<port>/` est désormais refusé ; la CLI ouvre
  `http://127.0.0.1:<port>/`.

## État Git final

Un seul commit pour ce ticket sur `main`, rapport inclus, sans push.
Message : `fix: refuser les Host étrangers (FD-WEB-003)`.
