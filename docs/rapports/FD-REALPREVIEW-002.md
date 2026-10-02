# Rapport — FD-REALPREVIEW-002

## Ticket et objectif

Implémenter le runner local de preview réelle défini par FD-REALPREVIEW-001,
corrigé par FD-REALPREVIEW-001A : processus enfant isolé, bootstrap autonome,
confinement réseau garanti avant le bind, cycle de vie explicite, readiness
par `/health`, arrêt contrôlé et logs bornés. Pas de proxy, d'iframe, d'UI ni
de composition Web.

## État Git initial

`main` synchronisée avec `origin/main` à `20b6a71` — FD-REALPREVIEW-001A.
Seule modification suivie préexistante : `docs/rapports/FD-CONTRACT-001.md`,
préservée hors commit.

## Architecture

```text
RealPreviewController.start(root)            (processus Forge Design)
  resolve_project_root → detect_forge_project → .venv/bin/python → bootstrap
  → port éphémère → environnement en liste blanche
  → Popen([python, -I, -u, child_bootstrap.py, --port, N], cwd=root,
          shell=False, start_new_session=True, stdout=PIPE, stderr=STDOUT)
  → thread lecteur → sondes /health → running | failed
child_bootstrap.py                            (processus enfant)
  garde d'audit → forge-mvc 1.0.0rc9 + create_wsgi_app → import app
  → create_wsgi_app(app.application) → garde Host → bind 127.0.0.1:N → serve_forever
```

Trois modules : `models.py`, `controller.py`, `child_bootstrap.py`, plus
`__init__.py`. Les fonctions de module `_spawn`, `_allocate_port`,
`_probe_health`, `_signal_group`, `_leader_exited`, `_clock` et `_sleep` sont
les seuls points de substitution des tests : pas de service locator, et aucune
injection dans l'API publique.

## API publique

`forge_design.real_preview` exporte exactement `RealPreviewConfig`,
`RealPreviewController`, `RealPreviewError`, `RealPreviewState` et
`RealPreviewStatus`. Le bootstrap n'est pas exporté.

- `RealPreviewState` : `Literal["stopped", "starting", "running", "failed",
  "stopping"]`.
- `RealPreviewConfig` : dataclass gelée. Valeurs par défaut 15 / 1 / 0,2 / 5
  / 2 s, 200 lignes, 2 000 caractères. Validée à la construction (nombres
  finis dans ]0, 3600], booléens refusés, entiers dans [1, 10 000] et
  [1, 100 000]) ; une configuration invalide lève `ValueError`.
- `RealPreviewStatus` : dataclass gelée `state`, `project_root`, `pid`,
  `port`, `exit_code`, `error`, `logs` (tuple). Aucun `Popen`, thread ni
  socket exposé.
- `RealPreviewError` : `start()` pendant `starting`, `running`, `stopping`
  ou une autre opération en cours. Les échecs du projet donnent `failed`
  avec `error`, sans exception.

## Child bootstrap

Bibliothèque standard seulement : un test AST vérifie que ses imports sont
inclus dans `sys.stdlib_module_names`, et il n'importe jamais `forge_design`.
Ordre :
1. `--port` exact ;
2. hook d'audit ;
3. version `forge-mvc` et `core.app.wsgi.create_wsgi_app`, **avant**
   l'insertion de la racine dans `sys.path`, si bien qu'un dossier `core/` du
   projet ne peut pas se substituer à Forge (testé) ;
4. `import app` ;
5. `app.application.dispatch` ;
6. `create_wsgi_app` ;
7. garde `Host` ;
8. `make_server("127.0.0.1", port, …)` ;
9. `serve_forever()`.

Aucun handler de signal, aucun TLS.

Codes de sortie : 2 usage, 3 Forge incompatible (version, symbole,
`application` sans `dispatch`, échec de `create_wsgi_app`), 4 port occupé,
5 import du projet, **6 bind impossible pour une autre raison**. Le code 6
s'ajoute aux codes normatifs ; il est documenté dans le contrat.

## Confinement pré-bind

L'hôte est la constante `"127.0.0.1"` et le port l'argument du parent. Aucun
des deux n'est lu dans `os.environ`, `config.py` ou `env/*`. Démontré par un
processus réel dont `env/dev` contient `APP_HOST=0.0.0.0`,
`APP_PORT=<autre port>` et `APP_SSL_ENABLED=true` :
- l'enfant affiche bien ces valeurs (`ENV-DEV 0.0.0.0 <autre> True`) ;
- `/proc/net/tcp` ne montre qu'une écoute, `0100007F:<port>`
  (`127.0.0.1`), et aucune sur l'autre port ;
- `/health` répond en HTTP.

## Audit hook

Événement `socket.bind`. Admis : IP littérales `127.0.0.0/8` en `AF_INET`,
`::1` en `AF_INET6`, sockets Unix. Refusés : noms (`localhost`, nom de
machine), `""`, `0.0.0.0`, `::`, `::ffff:127.0.0.1`, adresses LAN, CGNAT et
lien local, hôte non textuel, autres familles. La décision est testée
directement (26 cas). Le hook n'est jamais installé dans le processus pytest.

**Preuve centrale (FD-REALPREVIEW-001A) : oui, le bind est refusé avant
l'appel système.**
- Un `app.py` synthétique tente `socket.bind(("0.0.0.0", 0))` pendant son
  import, sous le vrai bootstrap. Il reçoit `PermissionError`, puis
  `getsockname()` renvoie `('0.0.0.0', 0)` : avec le port 0, un bind réel
  aurait attribué un port non nul. Le socket n'a donc jamais été lié. Le
  bootstrap sort avec le code 5, le contrôleur passe en `failed` (« import du
  projet impossible »), et la ligne `bind refusé sur ('0.0.0.0', 0)` figure
  dans les logs.
- Même preuve en processus dédié pour `0.0.0.0`, `192.0.2.1`, `::` et
  `localhost`, avec un bind loopback qui reste possible.

Hors de portée, comme documenté : `ctypes`, code natif, sous-processus du
projet.

## Host guard

Seul `Host: 127.0.0.1:<port>` exact atteint l'application. Tout autre Host,
ou son absence, donne `400`, `text/plain; charset=utf-8`, `no-store`, sans
appel à l'application. Testé en WSGI pur (10 refus, application non appelée)
et sur l'enfant réel (`localhost`, domaine tiers, autre port, `[::1]`).

## Compatibilité Forge

`importlib.metadata.version("forge-mvc") == "1.0.0rc9"` est exigé exactement.
Une fausse distribution `9.9.9` donne le code 3 sans importer le projet. Une
fausse `1.0.0rc9` sans `create_wsgi_app` donne aussi le code 3. Le squelette
rc9 réel fonctionne tel quel. Écart découvert : son import exige le dossier
`optins/`, ajouté à `docs/04-compatibilite-forge.md`.

## Interpréteur projet

Seul `<racine>/.venv/bin/python` est admis. `.venv` et `bin` sont vérifiés
par `open_directory` (`O_NOFOLLOW` sur chaque composant, primitive existante).
`python` peut être un lien, mais sa cible doit être un fichier ordinaire
exécutable. Le chemin **non résolu** est lancé, car le venv est reconnu par
l'emplacement invoqué. Pas de `PATH`, ni de `sys.executable`, ni de
`python3`. Sous une autre plateforme que POSIX : `failed`, « Preview réelle
indisponible sur cette plateforme ».

## Environnement

Nouveau dictionnaire construit positivement : `PATH`, `HOME`, `LANG`,
`LC_ALL`, `LC_CTYPE`, `TZ` et `TMPDIR` s'ils existent, plus `APP_ENV=dev`.
Testé avec un environnement hostile : `APP_HOST`, `APP_PORT`,
`APP_SSL_ENABLED`, `APP_ENV=prod`, `VIRTUAL_ENV`, `PYTHON*`, `XDG_*`, jetons,
CI, `SSH_AUTH_SOCK` et `DB_PASSWORD` sont absents. Le dictionnaire transmis
est égal exactement à l'attendu.

## Allocation du port

Socket `AF_INET` lié à `127.0.0.1:0`, port lu, socket fermé, intervalle
[1024, 65535] vérifié (et revérifié par le bootstrap). Collision réelle
testée : un socket en écoute occupe le port injecté, le bootstrap sort en 4,
l'état est `failed` / « port occupé », avec **une** allocation et **un**
lancement, sans nouvel essai. Le port alloué est rebindable après
l'allocation (testé).

## Processus enfant

`Popen` avec `shell=False`, `start_new_session=True`, `close_fds=True`,
`stdin=DEVNULL`, `stdout=PIPE`, `stderr=STDOUT`, texte UTF-8 avec
remplacement, et `cwd=root`. Options vérifiées par un test sur
`subprocess.Popen` substitué.

## États runtime

Initial `stopped` avec tous les champs vides. `start` n'est admis que depuis
`stopped` ou `failed` ; un autre `start` concurrent lève `RealPreviewError`
(testé pendant `starting` et `stopping`). Un nouveau `start` après `failed`
termine l'ancien groupe, attend le lecteur, ferme le tube et réinitialise les
logs (testé). Si l'ancien processus reste impossible à arrêter, rien n'est
relancé.

## Health check

`GET http://127.0.0.1:<port>/health` par `urllib`, avec `Host` naturel
`127.0.0.1:<port>`, sans proxy d'environnement ni redirection suivie, timeout
de 1 s, toutes les 0,2 s, jusqu'à 15 s. Prête seulement si : statut 200,
`application/json`, corps d'au plus 1 024 octets égal à `{"status": "ok"}`
en JSON. Testé contre un serveur local : corps faux ou augmenté, type texte,
corps trop long, 500, 302 vers une santé valide (non suivie), proxy
d'environnement ignoré, connexion refusée. Une sortie de l'enfant avant
readiness donne `failed` immédiatement (codes 0 à 6 et signaux, testés). À
l'expiration du délai, le groupe est arrêté avec « Délai de démarrage dépassé
(15 s) » (testé réellement avec un import qui dort).

## Logs bornés

Un seul thread lecteur (`daemon`), démarré juste après `Popen`, lit jusqu'à
EOF dans un `deque(maxlen=200)` sous verrou. Une ligne garde ses 2 000
premiers caractères (`readline(limit)`), et le reste est lu puis jeté sans
être conservé. Convention : lignes sans fin de ligne, de la plus ancienne à
la plus récente ; dernière ligne sans `\n` conservée. Bornes exactes testées
(3 lignes de 5 caractères), ainsi que les valeurs par défaut (253 lignes →
200, à partir de `ligne-53`, lignes de 5 000 et de 2 000 caractères) et un
enfant réel. Les logs restent visibles après `stop()` et sont remis à zéro
par `start()`. Un instantané n'est jamais modifié. Rien n'est écrit sur
disque.

## Arrêt SIGTERM

`stop()` depuis `running` ou `starting` passe par `stopping`, puis
`os.killpg(pid, SIGTERM)` et une attente de 5 s. Résultat : `stopped`,
`pid`/`port` à `None`, `exit_code` -15. `ProcessLookupError` est ignoré
(course testée : le groupe disparaît pendant le signal, l'arrêt reste
réussi). Depuis `stopped`, rien n'est fait ; depuis `failed` sans processus
vivant, l'état devient `stopped`. Arrêt du groupe réel testé : un petit-enfant
lancé par le projet meurt avec la preview.

## Escalade SIGKILL

Si le leader vit encore après 5 s : `SIGKILL` au groupe, puis 2 s. Testé en
faux processus et réellement, avec un projet qui ignore `SIGTERM` (code -9).
Un processus impossible à tuer donne `failed`, « Processus de preview
impossible à arrêter », avec `pid` conservé. Le contrôleur ne prétend jamais
être `stopped`.

Dès que le leader se termine, les survivants du groupe reçoivent `SIGKILL`
**avant** la récolte du leader. Son PID, encore réservé, garantit que le
groupe ciblé est le sien (`os.waitid(..., WNOWAIT)`).

## Sortie spontanée

`status()` interroge l'enfant à chaque appel : `running` ou `starting`
devient `failed`, avec le code et sa traduction (« arrêt inattendu
(signal 9) »). Testé en faux processus, pendant `starting` et réellement
(`SIGKILL` externe).

## Sécurité parent/enfant

Test réel :
- `sys.path`, `os.environ` et le cwd sont inchangés après start et stop ;
- aucun module `app`, `config`, `bootstrap` ou `mvc` n'est ajouté, et aucun
  module ajouté ne vient de la racine du projet ;
- `runpy` est interdit pendant le test ;
- aucun thread ne survit ;
- **aucun socket du parent n'est en écoute** pendant `running`.

Un test statique vérifie que `controller.py` n'importe que la bibliothèque
standard et `forge_design`, sans `runpy`, `exec(`, `import_module`,
`sys.path`, `chdir` ni `shell=True`.

## Tests unitaires

`tests/test_real_preview_bootstrap.py` : 64 tests. Arguments (16), décision
de bind (26), hook appelé directement, garde Host (11), classe serveur.

`tests/test_real_preview_controller.py` (partie unitaire), harnais de faux
processus avec horloge, signaux et sonde substitués : transitions, commande
exacte, options `Popen`, liste blanche, racine canonique, 8 préconditions
sans lancement, racine invalide, plateforme, bootstrap absent, port, échec de
lancement, 8 codes de sortie, sorties spontanées, refus de `start`, délai,
SIGTERM, SIGKILL, processus impossible à tuer, course `ProcessLookupError`,
arrêts depuis chaque état, redémarrage, logs, instantanés, configuration
(12), exports, packaging, sonde (10).

## Tests d'intégration

Projets synthétiques copiés du squelette `forge-mvc` 1.0.0rc9 installé, avec
un **venv léger** : `pyvenv.cfg`, `bin/python` lié à l'interpréteur de base,
et un `.pth` vers les site-packages contenant Forge. Aucun venv complet n'est
créé. Cas réels :
- cycle nominal (start, `/health`, running, stop, stopped) ;
- garde Host ;
- `env/dev` hostile ;
- bind à l'import ;
- collision de port ;
- import en échec (`RuntimeError`) ;
- délai de démarrage ;
- sortie spontanée ;
- groupe de processus ;
- repli SIGKILL ;
- logs bornés ;
- invariants du parent.

Bootstrap réel : usage (3), version (2), `dispatch`, `core` du projet ignoré,
port occupé.

Une fixture arrête tous les contrôleurs et vérifie automatiquement, par
`/proc/*/cmdline`, qu'aucun processus mentionnant le dossier du test ne
survit.

## Tests de sécurité

Couverts explicitement :
- bind non loopback refusé avant l'appel système ;
- Host invalide refusé ;
- `env/dev` hostile sans effet sur l'endpoint ;
- pas de nouvel essai sur port occupé ;
- arrêt du groupe de processus ;
- environnement parent filtré ;
- `core` du projet ignoré ;
- parent intact.

Vérification par mutation, lancée depuis le scratchpad avec restauration
vérifiée par `cmp` : **18 mutations, toutes détectées**.

- Bootstrap :
  - hook absent ;
  - hook installé après `import app` ;
  - IPv4 non loopback admis ;
  - garde Host inactive ;
  - hôte lu dans l'environnement (le bind échoue, code 6) ;
  - port lu dans l'environnement (readiness jamais atteinte) ;
  - version non vérifiée ;
  - racine insérée avant `core`.
- Contrôleur :
  - environnement copié ;
  - `os.kill` au lieu de `os.killpg` (le petit-enfant survit) ;
  - pas d'escalade SIGKILL ;
  - ligne longue non tronquée ;
  - corps de `/health` ignoré ;
  - proxy d'environnement suivi ;
  - redirection suivie ;
  - `status()` sans poll ;
  - code 0 pris pour un processus vivant ;
  - double allocation de port.

Deux mutations de la première campagne étaient mal construites et ont été
remplacées :
- un nouvel essai par appel récursif bouclait sans fin ;
- « exit 0 accepté comme running » était inopérant, parce que `status()`
  redétecte la sortie.

La mutation `os.kill` a laissé, comme attendu, un petit-enfant `sleep(120)`.
Il a été arrêté à la main après la campagne.

## Répétitions anti-race

Les deux fichiers de tests (148 tests, dont 12 sur processus réels) ont été
exécutés **5 fois de suite** : 148 réussis à chaque passe, en environ 11 s.
La fixture vérifie à chaque test réel qu'aucun processus ne survit. Après les
cinq passes, aucun processus `child_bootstrap` ni de fixture n'est actif, et
aucun `storage/` n'a été créé dans le répertoire d'exécution.

## Packaging

`pyproject.toml` liste ses paquets explicitement : `forge_design.real_preview`
y est ajouté, sinon la wheel n'aurait contenu ni le runner ni le bootstrap.
C'est le seul écart à la liste des fichiers à ne pas modifier, et il est
nécessaire. Un test vérifie cette entrée et la résolution du bootstrap
(`Path(controller.__file__).with_name("child_bootstrap.py")`, indépendante du
cwd et du dépôt).

Wheel `forge_design-0.1.0.dev0-py3-none-any.whl` dans `tmp/wheels` (ignoré
par Git), SHA-256
`6c01746227ab8c745fdb220effc68bcfcefd537d850a229987090bb022f88f77`. Elle
contient les quatre modules de `forge_design/real_preview/`, dont
`child_bootstrap.py` (sans bit exécutable, inutile : il est lancé par
`python child_bootstrap.py`).

## Installation wheel

Installation `--no-deps --no-index --target` dans un dossier temporaire, puis
`python -I`, avec ce dossier en tête de `sys.path` :
1. `forge_design.real_preview` et le bootstrap résolu viennent bien de
   l'installation temporaire (origine vérifiée) ;
2. projet synthétique (squelette rc9 et venv léger) : `start` donne
   `running` sur un port connu avec un PID, `/health` renvoie
   `{"status": "ok"}`, puis `stop` donne `stopped` (code -15, `pid` et `port`
   à `None`), sans processus survivant.

Aucun projet réel (SéquenCiel, Forge Design, projet utilisateur) n'a été
lancé.

## Fichiers créés

- `forge_design/real_preview/__init__.py`, `models.py`, `controller.py`,
  `child_bootstrap.py`
- `tests/test_real_preview_controller.py`, `tests/test_real_preview_bootstrap.py`
- `tests/real_preview_support.py` (projets synthétiques, venv léger, `/proc`)
- `docs/rapports/FD-REALPREVIEW-002.md`

## Fichiers modifiés

- `pyproject.toml` : paquet `forge_design.real_preview`.
- `docs/preview/real-preview-contract.md` : section « Implémentation du
  runner », sans redéfinir le contrat.
- `docs/02-architecture.md` : couche implémentée.
- `docs/04-compatibilite-forge.md` : constats d'exécution (`optins/`).

Non modifiés : `web/`, `preview/`, `editor/`, `design/`, `generate/`,
`safewrite/`, `tools/`, `app.py`, le JavaScript, `ProjectSelector`,
`CurrentProjectContext`, et le dépôt Forge.

## Validation globale finale

Ordre suivi : code, tests ciblés, tests de sécurité et mutations,
documentation, rapport, puis wheel et installation (avant la suite, pour que
le rapport soit complet), statique final, et enfin suite globale.

| Commande | Résultat |
|---|---|
| `pytest -q tests/test_real_preview_controller.py` | 84 réussis |
| `pytest -q tests/test_real_preview_bootstrap.py` | 64 réussis |
| Répétition ×5 des deux fichiers | 148 réussis à chaque passe |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` / `ruff format --check .` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |
| `pytest` (depuis le scratchpad, `--rootdir` vers le dépôt) | **3789 réussis** en 52 s, aucun échec |
| `python -m pip check` | No broken requirements found |
| MkDocs | N/A : aucune configuration dans Forge Design |

Seul ce tableau a été ajouté au rapport après l'exécution. Les validations
statiques et la suite globale ont ensuite été relancées sur le contenu final,
avec un résultat identique. Aucun `storage/` n'a été créé dans le répertoire
d'exécution, et aucun processus de preview n'a survécu.

## Limites restantes

- Le contrôleur n'est pas encore créé par `create_application`, ni arrêté au
  changement de projet ou à la fermeture : c'est le rôle de l'intégration.
- POSIX uniquement. Sans `os.waitid` (macOS), les survivants sont tués après
  la récolte du leader.
- Un descendant sorti du groupe (`setsid`) ou tenant le tube peut survivre.
  Le lecteur est alors attendu 2 s puis laissé (thread démon).
- La garde d'audit ne couvre ni le code natif, ni `ctypes`, ni les
  sous-processus du projet. Ce n'est pas une sandbox.
- Seul `forge-mvc` 1.0.0rc9 est accepté.
- Rendu par le chemin WSGI : `/static/` n'est pas servi (rôle du futur
  proxy).

## État Git final

Un commit sur `main`, rapport inclus, sans push.
Message : `feat: implémenter le runner de preview réelle (FD-REALPREVIEW-002)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Hash :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-REALPREVIEW-002.md
```
