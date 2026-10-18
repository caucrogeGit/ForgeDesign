# Rapport — FD-SEQUENCIEL-005

Qualification de **Real Preview** sur SéquenCiel avec Forge Design 0.2.1.
Date : 2026-10-18.

## Objectif

Question du ticket : Forge Design 0.2.1 peut-il démarrer, exposer puis arrêter
proprement le vrai SéquenCiel en Real Preview, avec des effets applicatifs
entièrement observés et attribués, sans modification incontrôlée du projet ni
fuite de secret ?

Le ticket interdit de modifier, pendant la qualification, tout `.design.json`,
template, ressource spécialisée ou fichier SéquenCiel (§3). La base de
développement reste arrêtée (§6).

## Décision

L'analyse préalable obligatoire (phase A, §8) révèle **avant tout démarrage**
que le parcours Real Preview n'est pas accessible sur SéquenCiel sans créer des
ressources dans le projet. La question a été posée au porteur, qui a tranché :
**constater et bloquer**.

| Option | Décision |
|---|---|
| Créer un design et un contrat temporaires dans SéquenCiel | **Écartée** : contourne le §3 |
| Piloter `RealPreviewController` depuis un script Python | **Écartée** : ne qualifie que le runner, déjà qualifié (FD-REALPREVIEW-002 à 007, FD-RELEASE-003), et pas le parcours utilisateur |
| Ouvrir l'éditeur structurel | Non fait |
| **Constater la précondition non satisfaite et s'arrêter avant tout Start Preview** | **Retenue** |

Le texte du ticket reçu s'arrête au §8. La décision ci-dessus le complète pour
ce cas, sur instruction explicite du porteur.

| Contrôle | Résultat |
|---|---|
| Start Preview demandé | **Non** |
| Serveur Forge Design lancé | Non |
| Éditeur utilisé | Non |
| Fichier créé ou modifié dans SéquenCiel | **Aucun** |
| Contournement par script | Aucun |
| Instantané final | **= T0** |
| Verdict | **SEQUENCIEL_REALPREVIEW_BLOCKED** |

## Baseline Forge Design

Dépôt ForgeDesign à `3a9e711` (FD-SEQUENCIEL-004), sur `main`, 3 commits d'avance
sur `origin/main` (`bb16f90`). Seuls autres changements : `FD-CONTRACT-001.md`
(modification utilisateur, préservée) et les fichiers non suivis historiques.

## Artefact utilisé

| Élément | Valeur |
|---|---|
| Roue | `tmp/fd-release-003-dist/forge_design-0.2.1-py3-none-any.whl` (FD-RELEASE-003) |
| SHA-256 | `8f4167c92567964ac5663cc0720bd338675ecf0ba7d8eb850608da78ce91a9da` (vérifié) |
| Usage | **Lecture seule** : la roue est extraite dans le scratchpad (`unzip`) pour citer le code réellement livré, et non le checkout ; elle n'est ni installée ni exécutée |

## Baseline SéquenCiel

| Élément | Valeur |
|---|---|
| Branche | `main` |
| HEAD | `89fb8a1329b05fb1ca0f8635aa2b1c3bb31e673f` (inchangé depuis FD-SEQUENCIEL-002) |
| Statut (`GIT_OPTIONAL_LOCKS=0`) | 20 fichiers non suivis, préexistants ; empreinte `cdfb4f1f…` identique |
| Processus avec SéquenCiel pour cwd | 0 |
| Écouteurs 8090, 8092, 33389, 8765, 9341 | Aucun |

Rien n'a été nettoyé.

## DB développement

`127.0.0.1:33389` est **arrêtée** (aucun écouteur), et
`tmp/base-locale/demarrer.sh` n'a pas été lancé. La question du §7 (connexion à
la construction de l'application ou à la première requête) reste **ouverte** :
aucune application n'a été démarrée.

## Analyse préalable : implémentation Real Preview

Lue dans la roue 0.2.1, avec les numéros de ligne du code livré :

| Élément | Constat |
|---|---|
| Commande de l'enfant (`real_preview/controller.py`) | `<racine>/.venv/bin/python -I -B -u <roue>/forge_design/real_preview/child_bootstrap.py --port <port>`, cwd = racine, `start_new_session=True`, environnement en liste blanche plus `APP_ENV=dev` |
| Bootstrap (`real_preview/child_bootstrap.py`) | Dans l'ordre : garde d'audit `socket.bind` (loopback seul, code Python seulement : ni code natif, ni ctypes, ni sous-processus), vérification forge-mvc 1.0.0rc9, `import app` (donc `config.py`, `env/dev` et toute l'application), `create_wsgi_app`, garde `Host`, bind `127.0.0.1:<port>`, `serve_forever` (un thread par requête) |
| Readiness | Sonde `GET /health` sur l'application, démarrage limité à 15 s |
| Arrêt | SIGTERM au groupe, puis SIGKILL (5 s, puis 2 s) |
| Persistance | Aucun état écrit sur disque par le runner |

## Point d'entrée Real Preview dans l'interface

La recherche dans la roue (routes du serveur et gabarits) trouve **un seul**
point d'entrée :

| Élément | Emplacement (roue 0.2.1) |
|---|---|
| Routes | `web/server.py` : `POST /editor/real-preview/start` et `/stop`, l. 259-263 et 355 |
| Formulaire Start | `web/templates/editor.html` l. 228, **seul gabarit** qui y mène ; il est affiché dans le panneau Real Preview de l'éditeur d'un Design |
| Navigation | `layout.html` → `/editor` ; sans paramètre `design`, l'éditeur s'affiche sans Design ni panneau Real Preview (`web/editor.py` l. 469-471) |

Ni Route Explorer, ni Template Viewer, ni Project Inspector, ni Debug Center ne
proposent Real Preview.

## Préconditions

Chaîne vérifiée dans `web/real_preview.py`. Chaque maillon manquant donne un
refus **avant** `runtime.start` :

| # | Précondition | Code (roue 0.2.1) | Sinon |
|---|---|---|---|
| 1 | Champ `design` présent (seul champ requis) | `_REQUIRED_FIELDS = frozenset({"design"})`, l. 75 | 400 |
| 2 | Le `.design.json` du projet est lisible et valide | `read = load_design(…)`, l. 388-391 | 409 « Design illisible ou invalide : preview réelle impossible. » |
| 3 | Le Design référence un contrat de vue (`source_contract`) lisible | `load_contract`, `web/editor.py` l. 277-282 ; `route_selection`, l. 282-285 | 409 « Contrat indisponible : route réelle inconnue. » |
| 4 | Le template du contrat est servi par une route GET, statique, publique, unique, dont le handler le rend littéralement | `select_real_preview_route` (`real_preview/route_selection.py`) | 409 « Preview réelle indisponible : <raison> » |
| 5 | Démarrage | `status = runtime.start(context.root)`, l. 402 | — |

## État de SéquenCiel

Inventaire fait **à partir de l'instantané T0**, qui couvre tout le checkout sauf
`.git`, sans accès supplémentaire au projet, complété par l'index Git :

| Ressource | Nombre |
|---|---:|
| `*.design.json` | **0** |
| `*.view.json` | **0** |
| `.json` sous `mvc/views/` | 0 |
| Dossier `.forge-design/` | absent |
| Fichiers `*.design.json` ou `*.view.json` suivis par Git | 0 |

Les préconditions 2 et 3 sont donc **impossibles à satisfaire** sans créer au
moins un `.design.json` et un `.view.json` dans SéquenCiel, ce qu'interdit le §3.

La précondition 4 serait satisfiable : FD-SEQUENCIEL-001 a établi que `GET /`
(groupe public, `HomeController.index`) forme une chaîne complète vers
`home/index.html`. Elle n'est pas atteignable sans les deux précédentes.

## Contournements écartés

| Contournement | Pourquoi |
|---|---|
| Design et contrat temporaires dans SéquenCiel, supprimés ensuite | Écriture volontaire dans le projet, interdite par le §3, même réversible |
| Design et contrat hors de SéquenCiel | Impossible : le Design et le contrat sont lus sous la racine du projet courant |
| `RealPreviewController` en script | Ne passe ni par l'interface, ni par les préconditions, ni par la sélection de route : il qualifie le runner, déjà couvert, et pas le parcours utilisateur |

## Frontière attendue (pour la reprise)

Ce que la reprise de FD-SEQUENCIEL-005 devra observer, d'après le code et
FD-SEQUENCIEL-004 :

- `import app` charge au moins les 375 modules de `mvc.routes`, `config.py` et
  `env/dev` (dans `os.environ`) ;
- la **rafale weasyprint** : environ 86 `ldconfig`, `gcc`, `collect2` et `ld`,
  avec 81 temporaires dans `/tmp` ;
- en plus, ce que font `app.py` et `create_wsgi_app` au démarrage (middlewares,
  sessions, opt-ins), non encore lus ;
- la sonde `/health` est une **vraie requête applicative**, qui peut déjà toucher
  la session ou la base (refus attendu sur 33389) ;
- l'application vit ensuite dans un serveur à threads : instantanés **pendant** la
  preview, `strace -f` et surveillant `/proc` sur toute sa durée de vie, arrêt du
  groupe vérifié au Stop.

## Snapshots

| Instantané | Heure | Entrées | Comparaison |
|---|---|---:|---|
| T0 | 21:36:14 | 519 214 (7 828 complet / 511 385 lourd) | — |
| Final | 21:37:47 | 519 214 | **= T0** : 0 ajout, 0 suppression, 0 changement, même HEAD, même statut |

Il n'y a pas de gate T0/T1 : rien n'a été exécuté contre SéquenCiel.

## Processus finaux

Aucun processus n'a été lancé contre SéquenCiel : ni serveur Forge Design, ni
Chromium, ni `strace`, ni bootstrap de preview. Les écouteurs 8765 et 9341 sont
libres, et 0 processus a SéquenCiel pour cwd.

## Observations

| # | Observation | Classement |
|---|---|---|
| 1 | Real Preview 0.2.1 n'est accessible **que depuis l'éditeur, pour un Design valide relié à un contrat de vue**. Un projet Forge réel qui n'a pas encore adopté les ressources Forge Design ne peut pas être prévisualisé, alors que le runner lui-même ne dépend ni du Design ni du contrat : ils ne servent qu'à choisir la route | **FORGEDESIGN-LIMITATION** : frontière produit, conforme à la conception actuelle (Phase 8, « preview réelle » rattachée à la conception de vues), révélée par le premier projet réel |
| 2 | Pour ce parcours précis, la limite empêche la qualification | **BLOCKING** |
| 3 | SéquenCiel n'a aucune ressource Forge Design : c'est son état normal, pas un défaut | EXPECTED |
| 4 | Ce n'est **pas** un échec technique de Real Preview : rien n'a été démarré ; le runner reste qualifié par les tickets FD-REALPREVIEW et FD-RELEASE-003 | EXPECTED |

## Classification

| Catégorie | Constats |
|---|---|
| FORGEDESIGN-LIMITATION | Real Preview rattachée à l'éditeur : Design valide et contrat de vue requis |
| BLOCKING | Parcours Real Preview sur SéquenCiel impossible sous les contraintes du ticket |
| EXPECTED | 0 Design et 0 contrat dans SéquenCiel ; base arrêtée ; aucun effet sur le projet |
| SEQUENCIEL-ISSUE | Aucun |
| FORGEDESIGN-ISSUE | Aucun nouveau |
| UNKNOWN | Effets de démarrage de `app.py` et de `create_wsgi_app`, et comportement de `/health` avec la base arrêtée : non observés |

## Verdict

**SEQUENCIEL_REALPREVIEW_BLOCKED**

Cause : **précondition fonctionnelle non satisfaite**. SéquenCiel ne contient
aucune ressource `.design.json` reliée à un `.view.json`, condition nécessaire
pour accéder à Real Preview depuis l'interface de Forge Design 0.2.1.

Ce n'est pas un échec technique de Real Preview, c'est une frontière produit
révélée par le premier projet réel. Le rapport s'arrête avant tout Start
Preview : aucun fichier n'a été créé, aucun éditeur utilisé, aucun contournement
fait, et l'instantané final est identique à T0.

## Recommandation ticket suivant

Ne pas passer à FD-SEQUENCIEL-006 comme si Real Preview avait été testée.
D'abord **un ticket ciblé qui lève la précondition, puis la reprise de
FD-SEQUENCIEL-005**.

Deux voies, à trancher par le porteur :

1. **Côté Forge Design (recommandée)**. Un ticket du type FD-REALPREVIEW-008 :
   point d'entrée Real Preview **sans Design**, par exemple depuis Route
   Explorer ou Template Viewer. La route serait choisie par les mêmes règles
   strictes (`select_real_preview_route` : GET, statique, publique, unique,
   template exact) et rien ne serait écrit dans le projet.

   C'est une capacité publique additive, donc une **version MINEURE** selon la
   politique de version (0.3.0), suivie d'une qualification de release avant de
   rejouer FD-SEQUENCIEL-005 sur la nouvelle roue. SéquenCiel reste en lecture
   seule, et la séparation « runner qualifié / parcours utilisateur » est
   conservée.
2. **Côté SéquenCiel (Phase 12)**. Le porteur décide que SéquenCiel adopte un
   premier Design et son contrat (par exemple pour `home/index.html`, route
   `GET /`), dans un ticket SéquenCiel distinct et versionné. FD-SEQUENCIEL-005
   est ensuite rejoué sur ce Design existant, sans écriture pendant la
   qualification.

La reprise de FD-SEQUENCIEL-005 devra aussi lire `app.py` et `wsgi.py` (non lus
ici, puisque rien n'a été démarré) et suivre les points de la section Frontière
attendue.

## Fichiers créés

- `docs/rapports/FD-SEQUENCIEL-005.md`

Aucun fichier n'est créé dans SéquenCiel. Les sources extraites de la roue et les
instantanés (`tmp/fd-sequenciel-005/`, ignoré par Git) restent hors des deux
dépôts suivis.

## Fichiers modifiés

- `docs/03-roadmap.md` : FD-SEQUENCIEL-005 bloqué, et la suite (lever la
  précondition, puis reprise).

Non modifiés : `forge_design/`, les tests, le kit, les rapports historiques,
`docs/rapports/FD-CONTRACT-001.md`, SéquenCiel.

## Validation finale

Le ticket ne change que ce rapport et la roadmap : la suite complète n'est pas
relancée. Validation documentaire faite après la dernière modification :

| Commande | Résultat |
|---|---|
| `git diff --check` (roadmap) et recherche d'espaces finaux (rapport) | OK |
| `ruff format --check` (rapport + roadmap) | 2 fichiers déjà formatés |
| Tests qui lisent `docs/` (`test_design_schema.py`, `test_view_contract_schema.py`) | 45 réussis |

## États Git finaux

**Forge Design** : un commit sur `main`,
`test: constater le blocage de Real Preview sur SéquenCiel (FD-SEQUENCIEL-005)`.
Il contient ce rapport et la roadmap. Il n'est pas poussé : 4 commits d'avance sur
`origin/main`. `FD-CONTRACT-001.md` et les fichiers non suivis historiques sont
inchangés.

**SéquenCiel** : HEAD `89fb8a1329b05fb1ca0f8635aa2b1c3bb31e673f`, statut
identique (20 fichiers non suivis, préexistants), **aucun commit et aucune
modification**.
