# Rapport — FD-REALPREVIEW-001

## Ticket et objectif

Définir le contrat de sécurité de la preview réelle avant toute exécution du
projet cible : ce qui est exécuté, dans quel processus, avec quelle commande,
sur quelle interface, avec quel environnement, quelles limites et quels effets
de bord, comment l'arrêter et signaler ses erreurs. Ticket documentaire :
aucun runner, aucun lancement, aucun code Python.

## État Git initial

`main` synchronisée avec `origin/main` à `719e08a` — FD-INTERACT-006. Seule
modification suivie préexistante : `docs/rapports/FD-CONTRACT-001.md`,
préservée hors commit.

## Définition de la preview réelle

Rendu d'une vue par une instance réellement exécutée du projet Forge cible,
dans un processus séparé de Forge Design. Trois niveaux distincts : preview
statique (Design et données fictives), template généré (HTML/Jinja écrit ou
diffé), preview réelle (application exécutée, route rendue). Aucun niveau ne
remplace silencieusement un autre.

## Frontière de sécurité

Le projet n'est jamais importé dans Forge Design (`import mvc`, `config`,
`bootstrap`, `from app import`, `sys.path`, `runpy` interdits). Processus
enfant unique, `shell=False`, liste d'arguments construite côté serveur depuis
`CurrentProjectContext.root` canonique ; le navigateur ne fournit ni cwd, ni
exécutable, ni configuration. Le contrat écrit explicitement qu'un processus
séparé n'est pas une sandbox OS.

## Forge inspecté

Version vérifiée : `forge-mvc==1.0.0rc9` installé dans le venv de Forge
Design, et dépôt local `/home/roger/Projets/Forge` au commit
`73a956e587e5f169c028415e0e540c149cbaff56` (`v1.0.0-rc.9-7-g73a956e5`,
`version = "1.0.0rc9"`), en lecture seule, sans commit.

Fichiers inspectés : `forge.py`, `cli/project/run.py`,
`cli/project/dev_reloader.py`, `skeleton/data/app.py`,
`skeleton/data/config.py`, `skeleton/data/env/example`,
`core/http/health.py`, `core/app/wsgi.py`, `core/app/dev_server.py`,
`core/app/application.py`, `core/http/router.py`,
`core/security/headers.py`, `core/security/csp.py`,
`cli/_support/help_dispatch.py` (convention `.venv`).

## Commande de lancement vérifiée

- `forge run` : reloader par défaut ; `--no-reload` passe par
  `bash scripts/dev-server.sh` si présent, sinon `[sys.executable, "app.py"]` ;
  ni hôte ni port en option ; prod refusée.
- `app.py --env dev` : `ThreadingHTTPServer` (threads, aucun enfant), aucun
  handler `SIGTERM`, `EADDRINUSE` → message et sortie 1.
- Hôte, port et TLS par `APP_HOST`, `APP_PORT`, `APP_SSL_ENABLED`, que
  `env/<APP_ENV>` peut écraser (`load_dotenv(..., override=True)`).
- `/health` : `200 {"status": "ok"}`, garanti par le contrat de stabilité
  Forge sur les deux serveurs.

**Commande retenue** : `[<racine>/.venv/bin/python, "app.py", "--env", "dev"]`,
cwd = racine canonique, `shell=False`, `start_new_session=True`. `forge run`
n'est pas retenu (reloader, script shell). Interpréteur : `.venv/bin/python`
du projet (convention Forge), sinon preview indisponible ; ni `PATH` ni
`sys.executable`.

## Réseau

Écoute `127.0.0.1` uniquement. **Port** : éphémère, alloué par bind
`127.0.0.1:0` puis transmis par `APP_PORT` ; collision → `failed`, sans
port+1 ni nouvel essai automatique ; la course est documentée. La sonde
vérifie l'écoute effective, car `env/dev` peut imposer un autre hôte, port ou
TLS. Le serveur cible n'a pas de contrôle `Host` : le risque DNS rebinding est
limité par le proxy à `Host` strict, le port imprévisible et la durée de vie
courte, mais pas supprimé.

## Environnement

**Politique** : liste blanche. Copiées si présentes : `PATH`, `HOME`, `LANG`,
`LC_ALL`, `LC_CTYPE`, `TZ`, `TMPDIR`. Fixées : `APP_ENV=dev`,
`APP_HOST=127.0.0.1`, `APP_PORT=<port>`, `APP_SSL_ENABLED=false`,
`PYTHONUNBUFFERED=1`. Tout le reste n'est jamais transmis (jetons, CI,
`VIRTUAL_ENV`, `PYTHONPATH`…). Forge Design ne lit, ne parse, ne copie, ne
modifie ni n'affiche aucun `.env` ou `env/*` ; le projet charge ses fichiers
`env/` lui-même et a donc accès à ses propres secrets (documenté).

## Effets de bord

Base, migrations, mails, fichiers, API externes, modifications de données :
l'exécution n'est pas considérée comme sûre. Activation uniquement explicite,
état initial arrêté, avertissement prévu avant le premier démarrage.

## Cycle de vie

Au plus une preview par instance. Contrôleur détenu par `create_application`,
sans singleton. États : `stopped`, `starting`, `running`, `failed`,
`stopping` ; sortie spontanée détectée par `poll()` (`running` → `failed`).
PID et port en mémoire seulement, aucun état disque. Pas de reload.

## Arrêt

**Politique** : `SIGTERM` au groupe de processus, attente 5 s, `SIGKILL` au
groupe, attente 2 s. Groupe (`start_new_session=True`, `os.killpg`) parce que
le code du projet peut créer des enfants même si le serveur Forge n'en crée
pas. Arrêt à la fermeture de Forge Design et avant tout changement de projet
courant. Limites : descendant en `setsid`, arrêt brutal de Forge Design.

## Logs

stdout et stderr fusionnés, lus en continu par un thread. Tampon mémoire de
200 lignes de 2 000 caractères au plus. Rien dans `<project>/storage/` ni
`.forge-design/`. Affichage échappé à la demande. Les logs propres de
l'application restent son comportement normal.

## Template utilisé

Seul le template présent sur disque, après génération, diff et SAFEWRITE, est
rendu. Loader patché, template temporaire, overlay et écriture/restauration
silencieuse sont interdits. Un écart avec la preview statique est attendu et
sera signalé par l'UI.

## Sélection de route

**Mode** : Route Explorer. Candidate si `GET`, méthode `found`, template
`found` égal au chemin du contrat (sans `mvc/views/`), `present`, et chemin
sans `{param}`. Disponible seulement si une seule candidate existe et qu'elle
est `public`. Sinon, indisponible avec une raison explicite : aucune route,
route dynamique, plusieurs routes, route protégée ou résolution incertaine.
Aucune déduction depuis le nom de vue ou le chemin de template. Le
`ViewContract` ne porte pas de route (vérifié).

## Authentification

Aucune session fabriquée, aucun utilisateur injecté, aucun contournement du
RBAC. Les routes non `public` passent par les middlewares Forge : elles sont
indisponibles en première version. Une réponse 401, 403, 404 ou 500 est
montrée telle quelle.

## Architecture iframe/proxy

Comparaison sur same-origin, CSP, X-Frame-Options, cookies, Origin, Host,
sessions, HTMX, navigation et assets dans le contrat. **Stratégie retenue :
B, proxy contrôlé par Forge Design.** Proxy transparent minimal sur une
origine loopback dédiée, `GET`/`HEAD` seulement (`405` sinon), `Host` strict,
vers le seul port de la preview active, ne réécrivant que les en-têtes
d'encadrement. A (iframe directe) est écarté : Forge envoie `DENY` et
`frame-ancestors 'none'`, ce qui imposerait de modifier le projet, et
exposerait directement un serveur sans contrôle `Host`.

## CSP

Iframe `sandbox="allow-scripts allow-same-origin"`, justifiés par HTMX et par
une origine de preview distincte de l'éditeur. Pas d'`allow-forms`, de
navigation du parent, de popups, de modales ni de téléchargements.
`frame-src` de l'éditeur limité à l'origine de preview. Timeouts : démarrage
15 s, sonde `/health` 1 s par tentative toutes les 200 ms, requête proxy 10 s.

## Threat model

Tableau dans le contrat : code malveillant, code bogué, boucle infinie,
enfant survivant, port exposé, DNS rebinding, bind non loopback imposé par
`env/dev`, secrets d'environnement, effets base de données, requêtes
externes, logs sensibles, navigation iframe, avec mesure et risque résiduel
pour chacun. Les termes « sandbox sécurisé », « isolé totalement » et « sans
risque » sont proscrits.

## Décisions retenues

- **Architecture pour FD-REALPREVIEW-002** : paquet
  `forge_design/real_preview/`, `RealPreviewController` détenu par la
  composition, contrats `RealPreviewState`, `RealPreviewConfig`,
  `RealPreviewStatus`, `RealPreviewError` ; runner seul (cycle de vie,
  commande, environnement, port, sonde, arrêt, logs), sans proxy, iframe ni
  UI.
- **Commande Forge** : déterminée, `.venv/bin/python app.py --env dev`.
- **Port** : éphémère, sans nouvel essai.
- **Route** : unique, `GET`, statique, publique, via Route Explorer.
- **Environnement** : liste blanche plus variables fixées.
- **Arrêt** : `SIGTERM`, 5 s, `SIGKILL` au groupe de processus.
- **Iframe/proxy** : proxy transparent `GET`/`HEAD` sur origine dédiée.

## Questions reportées

Texte exact de l'avertissement et UI ; Windows ; choix manuel d'une route
parmi plusieurs ou avec paramètres ; routes protégées ; persistance XDG des
logs ; détection d'un bind non loopback imposé par `env/dev` ; interpréteur
configurable. Aucune ne bloque FD-REALPREVIEW-002.

## Fichiers créés

- `docs/preview/real-preview-contract.md`
- `docs/rapports/FD-REALPREVIEW-001.md`

## Fichiers modifiés

- `docs/02-architecture.md` : section « Preview réelle » et lien vers le
  contrat.
- `docs/04-compatibilite-forge.md` : constats de lancement vérifiés.
- `docs/03-roadmap.md` : annotation d'une ligne (contrat → runner →
  intégration Web).

Aucun fichier Python, test, dépendance ni fichier du dépôt Forge modifié.
Aucun processus cible, socket ni requête HTTP n'a été lancé.

## Validations finales

Exécutées après la dernière modification documentaire, ce rapport compris.

| Commande | Résultat |
|---|---|
| `git diff --check` | Succès |
| `pytest -q tests/test_design_schema.py tests/test_view_contract_schema.py` (depuis le scratchpad) | 45 réussis |
| compileall / ruff / pyright | Non requis : aucun Python modifié |
| MkDocs | N/A : aucune configuration MkDocs |
| Suite globale | Non requise pour un ticket documentaire |

## État Git final

Un commit sur `main`, rapport inclus, sans push.
Message : `docs: définir le contrat de preview réelle (FD-REALPREVIEW-001)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Hash :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-REALPREVIEW-001.md
```
