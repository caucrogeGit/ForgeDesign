# Rapport — FD-REALPREVIEW-001A

## Ticket et objectif

Corriger le contrat de FD-REALPREVIEW-001 avant le runner : garantir que
l'endpoint de preview écoute sur `127.0.0.1`, sur le port choisi par Forge
Design et sans TLS, **avant** le bind, quelle que soit la configuration
`env/` du projet. Une détection après démarrage ne suffit pas. Ticket
documentaire : aucun runner, aucun lancement, aucun code Python.

## État Git initial

`main` synchronisée avec `origin/main` à `e8a886a` — FD-REALPREVIEW-001.
Seule modification suivie préexistante : `docs/rapports/FD-CONTRACT-001.md`,
préservée hors commit.

## Problème découvert

Le contrat précédent transmettait `APP_HOST`, `APP_PORT` et
`APP_SSL_ENABLED` par l'environnement, puis lançait `python app.py --env dev`.
Or `config.py` charge `env/dev` avec `override=True` avant de lire ces
variables : un `env/dev` contenant `APP_HOST=0.0.0.0` ou `APP_PORT=8000`
remplaçait silencieusement les valeurs de Forge Design avant le bind. La sonde
prévue ne l'aurait constaté qu'après coup, et ne pouvait même pas détecter un
bind `0.0.0.0` qui répond aussi sur `127.0.0.1`.

## Ordre réel de chargement Forge

Inspection statique de `forge-mvc==1.0.0rc9` (paquet installé) et du dépôt
Forge au commit `73a956e587e5f169c028415e0e540c149cbaff56`, sans
modification. Fichiers : `skeleton/data/app.py`, `skeleton/data/config.py`,
`skeleton/data/env/example`, `skeleton/data/bootstrap.py`,
`core/app/env.py`, `core/app/app_factory.py`, `core/app/wsgi.py`,
`core/app/dev_server.py`, `core/security/headers.py`, `forge.py`,
`cli/project/run.py`, `docs/release/stability-contract.md`,
`docs/deployment/wsgi-deployment.md`,
`tests/test_skeleton_public_application_001.py`,
`tests/test_wsgi_entrypoint_001.py`.

`python app.py --env dev` :

1. `app.py`, sous `__main__` : `--env` (`choices=["dev", "prod"]`) puis
   `os.environ.setdefault("APP_ENV", …)` ;
2. `from config import …` : `read_app_env()`, `load_dotenv("env/example")`,
   `load_dotenv("env/dev", override=True)`, puis `os.getenv` des trois
   valeurs ;
3. `application = build_application()` (config, routes, `bootstrap.py`) ;
4. sous `__main__` : garde prod, **bind**
   `TLSThreadingHTTPServer((APP_HOST, APP_PORT), RequestHandler)`, contexte
   TLS si `APP_SSL_ENABLED`, `serve_forever()`.

## APP_HOST

Lu une fois à l'import de `config.py`, ligne 71
(`os.getenv("APP_HOST", "127.0.0.1")`), après `env/dev`. Consommé uniquement
dans le bloc `__main__` d'`app.py` (garde prod, bind, message de port occupé).
Aucun module de `core/` ne le lit.

## APP_PORT

Lu ligne 72 (`int(os.getenv("APP_PORT", 8000))`), après `env/dev`. Consommé
uniquement au bind et dans les messages du bloc `__main__`.

## APP_SSL_ENABLED

Lu ligne 74 (défaut vrai hors prod), après `env/dev`. Consommé uniquement
par le bloc `__main__` (contexte TLS, messages). Le chemin WSGI ne l'utilise
pas : HSTS dépend de `wsgi.url_scheme == "https"`.

## Solutions étudiées

Réponses aux questions du ticket :

- **A (surcharge après dotenv)** : aucune. Ni `app.py` ni `forge run`
  n'acceptent d'hôte ou de port ; `config.py` ne relit rien après l'import.
- **B (désactiver dotenv)** : pas d'option officielle. `config.py` charge
  toujours `env/example` puis `env/<APP_ENV>`.
- **C (environnement dédié)** : `--env` n'accepte que `dev` ou `prod`.
- **D (bootstrap)** : réalisable avec l'API WSGI documentée.
- **E (primitive dédiée)** : Forge n'a pas de fonction « lancer avec hôte et
  port ». La voie documentée laisse le bind au serveur WSGI externe.

## Solution A

`app.py --env dev` et variables d'environnement. Pas de garantie avant le
bind : `env/dev` écrase les variables. **Éliminée** (critère éliminatoire).

## Solution B

Environnement Forge alternatif (`APP_ENV=forge-design-preview` dans
l'environnement, `--env` refusant toute autre valeur). Si
`env/forge-design-preview` n'existe pas, seul `env/example` est chargé sans
écrasement. Mais :
- la garantie dépend de l'absence d'un fichier que n'importe qui peut créer ;
- les réglages du projet (`env/dev` : base, services) ne sont plus chargés ;
- `APP_ENV` inconnu casse le bloc `__main__` (`_fmt[APP_ENV]`) ;
- créer le fichier serait une écriture cachée, interdite.

**Éliminée.**

## Solution C

Bootstrap enfant qui importe `config`, en modifie les attributs
(`config.APP_HOST = …`), puis exécute `app.py` en `__main__` par `runpy`.
Elle repose sur la liaison de noms interne d'`app.py` et patche un module du
projet. Elle est donc fragile, même si elle garantit le bind pour le
squelette. **Écartée** au profit de D.

## Solution D

Bootstrap enfant sur l'API documentée : `import app` (sans bloc `__main__`),
puis `core.app.wsgi.create_wsgi_app(app.application)`, servi par un serveur
WSGI de la bibliothèque standard que le bootstrap lie lui-même à
`127.0.0.1:<port>`. C'est exactement le schéma `wsgi.py` + `gunicorn --bind
127.0.0.1:…` de la documentation Forge, avec le bootstrap comme serveur
externe. **Retenue.**

Variante E : `gunicorn --bind` lui-même. Gunicorn n'est pas une dépendance
de Forge ni des projets. **Éliminée** (nouvelle dépendance).

| Critère | A | B | C | D |
|---|---|---|---|---|
| Garantie avant bind | Non | Conditionnelle | Oui (squelette) | **Oui** |
| Aucune modification projet | Oui | Non si fichier créé | Oui | Oui |
| Aucun shell | Oui | Oui | Oui | Oui |
| Compatible rc9 | Oui | Partiel (`_fmt`) | Oui | Oui |
| Stabilité API | Stable | Stable | Interne (`app.py`) | Documentée, hors contrat de stabilité |
| Complexité | Faible | Faible | Moyenne | Moyenne |
| Testabilité | — | — | Moyenne | Bonne (bootstrap pur stdlib) |
| Processus séparé | Oui | Oui | Oui | Oui |
| Respect environnement projet | Oui | Non | Oui | Oui |

## Critères éliminatoires

Toute solution laissant `env/dev → APP_HOST=0.0.0.0` agir avant le bind est
éliminée : A ; B dès qu'un `env/<nom>` existe. Une sonde ou un scan des
sockets après démarrage n'est jamais une barrière.

## Stratégie retenue

Une seule stratégie pour FD-REALPREVIEW-002 : **bootstrap enfant
`forge_design/real_preview/child_bootstrap.py`**, en bibliothèque standard
seulement, lancé par l'interpréteur du projet. Étapes normatives :
1. argument `--port` ;
2. garde d'audit `socket.bind` (loopback seulement, PEP 578) ;
3. racine dans `sys.path` ;
4. contrôle de compatibilité : `forge-mvc` 1.0.0rc9, `create_wsgi_app`
   présent ;
5. `import app` ;
6. `create_wsgi_app(app.application)` et garde `Host` ;
7. bind sur `127.0.0.1:<port>` sans `SO_REUSEADDR` ni `SO_REUSEPORT` ;
8. `serve_forever()`.

Codes de sortie : 2 usage, 3 Forge incompatible, 4 port occupé, 5 import du
projet.

`create_wsgi_app` ne figure pas parmi les imports publics du contrat de
stabilité Forge. Il est retenu parce que c'est la voie documentée et testée
par Forge pour servir l'application armée. Une incompatibilité est détectée
avant tout bind (version et symbole), et la preview passe alors en `failed`
avec la raison « Forge incompatible ».

## Garantie pré-bind

> Forge Design garantit que le serveur HTTP utilisé comme endpoint de preview
> est configuré sur `127.0.0.1:<port choisi par Forge Design>`, en HTTP sans
> TLS, avant son bind.

- L'hôte est une constante du bootstrap et le port un argument ; aucun des
  deux n'est lu dans le projet.
- Le bind a lieu après l'import d'`app.py`, donc après toute configuration
  projet.
- Le bloc `__main__`, seul consommateur des trois variables, n'est jamais
  exécuté.
- Le serveur du bootstrap ne fait pas de TLS.
- La garde d'audit refuse en plus tout bind non loopback dans l'enfant,
  avant l'appel système.

Les valeurs ne sont pas « réimposées après `env/dev` » : elles en sont
indépendantes par construction, ce qui donne la même garantie.

## Vérification post-bind

La sonde `/health` (avec `Host: 127.0.0.1:<port>`) reste, mais uniquement
comme validation de readiness : le serveur écoute, sur le port attendu, et
répond. Ce n'est plus une barrière de confinement.

## Commande FD-REALPREVIEW-002

```python
[f"{root}/.venv/bin/python", "-I", "-u", CHILD_BOOTSTRAP, "--port", str(port)]
# cwd = racine canonique, shell=False, start_new_session=True
```

`.venv/bin/python app.py --env dev` **n'est plus acceptable**. Environnement :
liste blanche inchangée et `APP_ENV=dev`. `APP_HOST`, `APP_PORT`,
`APP_SSL_ENABLED` et `PYTHONUNBUFFERED` ne sont plus transmis (`-u` remplace
le dernier, ignoré sous `-I`).

Effets de bord de ce choix, documentés dans le contrat :
- le rendu passe par le chemin WSGI de Forge et non par le `RequestHandler`
  de développement ;
- `/static/` sera servi par le proxy de Forge Design depuis `<racine>/static`,
  comme le reverse proxy du déploiement documenté ;
- l'endpoint reçoit une garde `Host`, ce qui neutralise aussi le DNS
  rebinding visant directement le port cible.

## Compatibilité Forge

`docs/04-compatibilite-forge.md` : ordre de lecture des trois variables,
consommation limitée au bloc `__main__`, import sans serveur, API
`create_wsgi_app`, mécanisme retenu, contrôle de version, commit vérifié.

## Threat model mis à jour

Le scénario « `env/dev` impose un bind non loopback » est couvert par la
garantie pré-bind : il ne reste aucun risque résiduel pour l'endpoint de
preview. Lignes ajoutées :
- code projet ouvrant un serveur à l'import (garde d'audit) ;
- code projet ouvrant d'autres sockets ;
- API Forge modifiée (contrôle avant bind).

Le DNS rebinding est désormais traité par le `Host` strict du proxy **et** de
l'endpoint.

## Risques résiduels

- Code natif, `ctypes` ou sous-processus lancés par le projet peuvent
  contourner la garde d'audit et ouvrir un port non loopback avec les droits
  de l'utilisateur. Forge Design ne prétend pas l'empêcher : ce n'est pas une
  sandbox OS.
- Sockets loopback supplémentaires ouverts par le projet.
- Processus locaux capables d'envoyer le `Host` attendu à l'endpoint.
- Changement sémantique de `create_wsgi_app` non détectable statiquement.
- Course sur le port éphémère, résolue par la sortie 4 (`failed`), sans
  partage de port.

## Fichiers modifiés

- `docs/preview/real-preview-contract.md` : frontière d'exécution, processus
  séparé, commande Forge (faits, ordre réel, commande, bootstrap, garde
  d'audit, dépendance API), environnement, réseau (garantie pré-bind,
  vérification post-bind, port, Host), arrêt, proxy (statiques), timeouts,
  threat model, limites, décisions, questions reportées.
- `docs/02-architecture.md` : schéma et paragraphe « Preview réelle »
  (commande changée).
- `docs/04-compatibilite-forge.md` : complément FD-REALPREVIEW-001A.

Fichier créé : `docs/rapports/FD-REALPREVIEW-001A.md`. Roadmap non modifiée
(FD-REALPREVIEW-002 n'est pas bloqué). Aucun fichier Python, test ni
dépendance modifié. Aucun fichier du dépôt Forge modifié. Aucun processus
cible, socket ni requête HTTP lancé.

## Validations finales

Exécutées après la dernière modification documentaire, ce rapport compris.

| Commande | Résultat |
|---|---|
| `git diff --check` | Succès |
| `pytest -q tests/test_design_schema.py tests/test_view_contract_schema.py` (depuis le scratchpad) | 45 réussis |
| compileall / ruff / pyright | Non requis : aucun Python modifié |
| MkDocs | N/A : aucune configuration MkDocs dans Forge Design |

## État Git final

**FD-REALPREVIEW-002 peut démarrer**, avec la garantie réseau pré-bind
démontrée ci-dessus.

Un commit sur `main`, rapport inclus, sans push.
Message : `docs: garantir le confinement réseau de la preview (FD-REALPREVIEW-001A)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Hash :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-REALPREVIEW-001A.md
```
