# Rapport — FD-SEQUENCIEL-001

Premier essai réel de Forge Design 0.2.1 sur SéquenCiel, en **lecture seule**.
Date : 2026-10-16.

## Objectif

Une question : Forge Design 0.2.1 peut-il inspecter réellement SéquenCiel de bout
en bout, en lecture seule, sans écrire dans le projet, sans fuite de secret et avec
des diagnostics suffisamment fiables ?

Aucune correction fonctionnelle. Les éléments suivants n'ont pas été lancés :

- `doctor`, `project:audit`, `project:check` ;
- Real Preview, l'éditeur, les actions de modules ;
- la génération, SAFEWRITE, les migrations ;
- l'application SéquenCiel et sa base.

Aucun module externe n'est activé. Aucun fichier n'est créé dans SéquenCiel.

| Décision | Résultat |
|---|---|
| A. 0.2.1 installé depuis la wheel ? | Oui, SHA-256 vérifié |
| B. Vrai checkout SéquenCiel ? | Oui : `/home/roger/Projets/SequenCiel` |
| C. Lecture seule ? | Oui : 3 POST, tous d'état interne (ouvrir, fermer, rouvrir) |
| D. Deux instantanés de stabilité ? | Oui : T0 = T1 |
| E. Instantané complet et métadonnées lourdes ? | Oui : 567 471 entrées |
| F. HOME et XDG isolés ? | Oui |
| G. Chromium uniquement ? | Oui |
| H–L. doctor, audit, check, preview, éditeur, modules, base ? | Non |
| M. Secrets recherchés uniquement en mémoire ? | Oui |
| N. SéquenCiel modifié ? | **Non** : instantané final = T1 |
| O. Verdict | **SEQUENCIEL_READONLY_PASS_WITH_ISSUES** |

## Baseline Forge Design

Le dépôt ForgeDesign est à `a80316e` (FD-RELEASE-003), sur `main`, 19 commits en
avance sur `origin/main` (`e411d0c`). Il ne sert qu'au rapport : **le code exécuté
est celui de la roue installée**, jamais le checkout (ni installation éditable, ni
`PYTHONPATH`).

Le dépôt n'a pas d'autre changement que `docs/rapports/FD-CONTRACT-001.md`
(modification utilisateur, préservée) et les 575 fichiers non suivis
historiques.

## Artefact utilisé

| Élément | Valeur |
|---|---|
| Roue | `tmp/fd-release-003-dist/forge_design-0.2.1-py3-none-any.whl` |
| SHA-256 | `8f4167c92567964ac5663cc0720bd338675ecf0ba7d8eb850608da78ce91a9da` (identique à FD-RELEASE-003) |
| Venv | Neuf, hors SéquenCiel, installation hors ligne (`--no-index`) |
| `pip check` | No broken requirements found |
| `forge-design --version` | Forge Design 0.2.1 |
| Paquets | forge-design 0.2.1, forge-mvc 1.0.0rc9 ; **ni Circuit ni Flowchart** ; aucun `.pth` ni éditable |
| `forge_design.__file__` | `site-packages` du venv neuf |

## Baseline SéquenCiel

| Élément | Valeur |
|---|---|
| Branche | `main` |
| HEAD | `008a895e6f97c79444228b4837816b3409ee881b` (« feat(drawciel): qualifier le WiFi virtuel R4 professeur 08D ») |
| Statut | 17 fichiers non suivis, préexistants : ADR 327, rapport DC-017-09A, `docs/specs/drawciel-r4/dc01709a/` (13 fichiers), `livrables/` (2 fichiers) ; aucun fichier modifié |
| Taille | `tmp/` 57 Go, `sauvegardes/` 2,6 Go, `site/` 574 Mo, `storage/` 609 Mo, `docs/` 415 Mo, `.git` 502 Mo, `.venv` 281 Mo, `node_modules` 165 Mo, `mvc/` 11 Mo |
| Stockage | ext4 |

## État Git initial SéquenCiel

Les commandes du §7 ont été exécutées. L'état utilisateur préexistant (17 fichiers
non suivis) est inventorié et préservé. Aucun stash, reset, clean, checkout ni
commit.

**Transparence.** Le premier `git status` du §7 (21:08) a rafraîchi
`.git/index`, ce qui a mis à jour la mtime de `.git`. C'est le comportement
normal de git, mais c'est une écriture dans `.git`. Elle est **antérieure à T0**,
et `.git` est exclu de l'instantané par le ticket. Tous les points de contrôle
suivants ont utilisé `git --no-optional-locks` (`GIT_OPTIONAL_LOCKS=0`), qui
n'écrit pas.

## Stabilisation

| Contrôle | Constat initial | Action |
|---|---|---|
| Fenêtre VS Code ouverte sur SéquenCiel | Hôte d'extensions avec `ruff server` (cwd SéquenCiel), Pylance, serveur Markdown, surveillant de fichiers, 2 terminaux inactifs, **un `codex app-server`** | Question posée ; **tu as fermé la fenêtre**. J'ai vérifié qu'aucun processus n'avait plus SéquenCiel comme répertoire courant. |
| nginx, gunicorn locaux | Absents | — |
| Ports 8090, 8092, 33389 | Libres | — |
| Base de développement SéquenCiel | `env/dev` la place sur `127.0.0.1:33389` (port lu seul, aucune autre valeur) : **arrêtée** | — |
| `mariadbd` sur `127.0.0.1:3306` | Service système (systemd, utilisateur `mysql`, actif depuis environ 45 jours), qui n'est pas la cible SéquenCiel (33389) | Laissé tel quel ; aucune connexion |
| Activité sur la racine | mtime de la racine à 21:07:55, puis 21:37:10 ; `.git` à 21:37:18 | Les dernières correspondent à la fermeture de la fenêtre VS Code, **avant T0** (21:38:40). Attribution plausible, non démontrée (UNKNOWN). |

## Processus préexistants autorisés

- **Session VS Code Remote-SSH entrante** (`sshd-session roger@notty`, depuis
  192.168.1.63) : c'est elle qui porte les fenêtres VS Code. **Aucune session SSH
  sortante** vers la production n'a été trouvée.
- **Fenêtre VS Code ForgeDesign**, avec son hôte d'extensions et un
  `codex app-server` (cwd `/home/roger`), et la session Claude Code de ce ticket
  (cwd ForgeDesign).
- **`mariadbd` système** (3306).

Aucun effet observé sur le checkout : tous les instantanés sont identiques à T1.

## HOME / XDG isolés

Serveur lancé avec un environnement minimal (`env -i`) :

- `HOME` et `XDG_CONFIG_HOME`, `XDG_STATE_HOME`, `XDG_CACHE_HOME`, `XDG_DATA_HOME`
  pointent vers le scratchpad de la session, hors SéquenCiel et hors préférences
  réelles ;
- `PATH=/usr/bin:/bin`, `LANG=C.UTF-8` ;
- cwd `/tmp`.

À la fin, le HOME isolé contient un seul fichier :
`.config/forge-design/recent-projects.json` (77 octets).

Le vrai `~/.config/forge-design/` de l'utilisateur est **inchangé** (dernière
modification le 4 octobre).

## Snapshots T0 / T1

Outil d'instantané écrit pour ce ticket, qui ne suit aucun lien :

- **Niveau complet** : chemin, type, taille, `mtime_ns`, `ctime_ns`, inode,
  SHA-256 et cible des liens, pour tout sauf `.git`, `.venv`, `node_modules`,
  `tmp` et `sauvegardes`.
- **Niveau métadonnées** : les mêmes champs sans SHA-256, pour ces quatre dossiers.
- **`.git`** : `rev-parse HEAD` et `status --porcelain=v1 --untracked-files=all`
  seulement.

| Instantané | Heure | Entrées | Complet / métadonnées |
|---|---|---:|---|
| T0 | 21:38:40 | 567 471 | 7 798 / 559 673 |
| T1 | 21:44:11 (5 min 31 s plus tard) | 567 471 | 7 798 / 559 673 |

**T0 == T1** : 0 ajout, 0 suppression, 0 changement, même HEAD, même statut.
**Gate de stabilité franchi.**

## Ouverture

Le serveur est lancé depuis `/tmp`, `--no-browser`, sans `--module`. Il affiche
`Forge Design 0.2.1` et `http://127.0.0.1:8765/`.

| Contrôle avant ouverture | Résultat |
|---|---|
| Écoute | `127.0.0.1:8765` seulement |
| Host `localhost` / Host étranger | 400 / 400 |
| `Cache-Control` | `no-store` |
| Aucun projet implicite | Oui (« Aucun projet » ; aucune synthèse) |

Ouverture par le formulaire de Project Inspector, dans Chromium :

| Mesure | Valeur |
|---|---|
| Durée | **729 ms** |
| Projet reconnu | **Oui** |
| `bootstrap.py` | **Optionnel absent** (information), sans erreur de détection (FD-FORGE-004) |
| Version Forge détectée | Indéterminée (voir Forge) |
| État global | Attention |
| Structure | OK : 4/4 éléments requis, 7 dossiers MVC optionnels présents |

## Project Inspector

| Section | État | Diagnostic exact | Classement |
|---|---|---|---|
| Projet | OK | Sélectionné et accessible | EXPECTED |
| Forge | **Attention** | « Version Forge absente ou indéterminable. » ; « Ligne 15 : aucune version exacte inconditionnelle. » (source `requirements.txt`) | **FORGEDESIGN-ISSUE** (mineure) : SéquenCiel épingle forge-mvc par une référence Git directe (`forge-mvc @ git+https://…@1af6301…`), légitime ; le lecteur n'accepte que `==` |
| Structure | OK | 4/4 requis ; `bootstrap.py` : « Élément optionnel absent. » | EXPECTED (FD-FORGE-004) |
| Routes | **Attention** | 629 routes, 593 sans diagnostic, 201 avertissements, 0 erreur ; lecture statique possiblement partielle | Voir Route Explorer : effet de borne (FORGEDESIGN-ISSUE), puis opt-ins (FORGE-LIMITATION) |
| Entités | OK | 86 entités, 120 relations, 0 erreur, 0 avertissement | EXPECTED |
| Templates | OK | 497 fichiers dans `mvc/views`, inventaire complet | EXPECTED |
| Migrations | OK | 251 migrations SQL, inventaire seul | EXPECTED |
| Diagnostics | **Attention** | 13 erreurs passées du journal (ERROR) ; 0 anomalie de lecture | SEQUENCIEL-ISSUE (erreurs runtime historiques, à examiner côté application) |
| Contrats | OK | 0 contrat de vue ; 497 templates sans contrat (optionnel) | EXPECTED |

L'instantané pris après l'Inspector est **identique à T1**.

## Route Explorer

Page `/routes` chargée en 1,15 s dans Chromium (4 Mo de HTML) : 629 lignes de
chaîne, graphe présent, 6 512 liens sources. Les filtres `q=agora` et
`q=drawciel` répondent.

| Inventaire | Valeur |
|---|---|
| Routes | **629** : 276 GET, 353 POST ; 13 publiques ; 0 handler dynamique |
| Handlers | 626 méthodes de contrôleur (toutes résolues), 3 fonctions |
| Chaînes | **99 complètes, 530 partielles, 0 problématique** |
| Templates par route | 0 : 425 ; 1 : 202 ; 2 : 2 |
| Confiance | exact 201, aucune 389, inconnue 33, multiple 2, partielle 1, non applicable 3 |
| Diagnostics | 201 avertissements : `template.analysis_truncated` 164, `template.dynamic` 34, `template.ambiguous` 2, `route.partial` 1 |
| Avertissements de lecture | Réserve statique ; 5 déclarations non interprétées (l. 208, 225, 234, 243, 251) ; branchement opt-ins non résolu ; `drawciel_mcu_routes.py` l. 23 non interprétée ; « Limite globale de 128 templates atteinte ; analyse partielle. » |

**Constat principal : la borne globale `MAX_VISITED_TEMPLATES = 128`.** Sur un
projet de 497 templates, l'analyse des dépendances s'arrête après 128 templates
distincts, sur l'ensemble des routes. Conséquences :

- 164 avertissements « Analyse partielle de X.html : limite atteinte » ;
- **102 chaînes (72 GET, 30 POST) dont le template est exact et présent sur
  disque**, mais classées « partielles » : présence et syntaxe `not-applicable`,
  graphe de dépendances vide et `truncated=True`. Elles n'ont simplement pas été
  analysées ;
- la section Routes en Attention, même hors opt-ins.

Le comportement est **honnête et documenté** (`route-explorer.md` : « un statut
non applicable à la limite ne signifie pas absence »), mais la borne n'est pas
adaptée à un vrai projet de cette taille. Classement : **FORGEDESIGN-ISSUE**,
majeure pour la fiabilité perçue des routes, non bloquante.

Les 389 routes « sans template » sont partielles **par contrat** : « complète »
exige un template exact présent. Une heuristique sur le corps des méthodes
(estimation, non une preuve) les répartit ainsi :

- redirection seule : 213 (200 POST, 13 GET) ;
- téléchargement ou fichier : 33 ;
- JSON : 30 ;
- délégation à un helper : 64 ;
- autre : 49.

Environ 276 sont donc légitimement sans template. Une partie des 113 dernières
sont de vrais templates rendus par un helper, donc invisibles (voir ci-dessous).

## Vérification manuelle des routes

Vingt routes ont été vérifiées dans le code source de SéquenCiel, en lecture
seule : déclaration, contrôleur, méthode et template.

| Route | Forge Design | Code réel | Verdict |
|---|---|---|---|
| `GET /` | Complète, `home/index.html` | `render("home/index.html")` (+ redirections) | Exact |
| `GET /formation/show/{id}` | Complète, `app/formation/show.html` | Rendu de ce template, présent | Exact (faux négatif exclu) |
| `GET /scenario/show/{id}` | Complète, `app/scenario/show.html` | Idem | Exact |
| `GET /famille_competence/show/{id}` | Complète, `…/show.html` | Idem | Exact |
| `GET /login` | Partielle, `app/auth/login.html` exact | `render("app/auth/login.html")` | Template exact ; « partielle » due à la borne 128 |
| `POST /login` | Sans template | Redirections seulement | Exact |
| `GET /agora` (+2 variantes) | Sans template | `return AgoraController._traiter(...)` (helper) | **Faux négatif** de template |
| `GET /drawciel` | `app/drawciel/index.html` | `render("app/drawciel/index.html")` | Exact (borne) |
| `GET /drawciel/nouveau` | Sans template | `return editeur(...)`, qui rend `app/drawciel/editeur.html` | **Faux négatif** de template |
| `GET /drawciel/bibliotheque` | Sans template | `Response.json(...)` | Exact |
| `GET /annee_scolaire/export-csv` (+2 autres CSV) | Sans template | CSV, `Content-Disposition: attachment` | Exact |
| `GET /matiere` | Template dynamique | `template = "_results.html" if HX else "index.html"` | Exact, non classé invalide (§33) |
| `GET /conception/scenario/{id}` | Ambigu (multiple) | Plusieurs `render` | Exact |
| `GET /bilan/preparer` | Ambigu | Deux littéraux (`form.html`, `preparer.html`) | Exact |
| `GET /referentiel/{id}` | Confiance partielle, dynamique | Littéral + variable `gabarit` | Exact |
| `POST /arduino-programme/televersement-r4`, `POST /drawciel-mcu/r4`, `POST /drawciel-mcu/recommencer` | Handler fonction, non applicable | Fonctions importées (`televersement_r4`, `r4`, `recommencer`) | Exact ; limite documentée (handlers fonctions non analysés) |

**Faux positifs** : aucune route n'est classée « problématique », et les 36
diagnostics par route vérifiés (dynamique, ambigu) correspondent au code.

Les 5 « déclarations non interprétées » de `mvc/routes/__init__.py` sont, en revanche, du **bruit** :

- l. 208 : `register_admin(router)`, l'opt-in admin ;
- l. 225 : `register_optins(router)` ;
- l. 234 : une fonction de contexte RBAC ;
- l. 243 : un `register_jinja_context_provider` ;
- l. 251 : le dictionnaire `RBAC_PREFIX_RULES`.

Les trois dernières ne déclarent aucune route.

**Faux négatifs de routes** :

- `drawciel_mcu_routes.py` l. 23 : une boucle `for … in (...)` déclare **12
  routes** (`/capacites`, `/compiler`, `/sauvegarder`…) **absentes de
  l'inventaire**. Ce sont des routes dynamiques, limite documentée (FORGE-LIMITATION) ;
- les routes des opt-ins (`register_admin`, `register_optins`, registre actif)
  ne sont pas inventoriées et n'ont pas été dénombrées. C'est la limite connue
  (FORGE-LIMITATION, EXPECTED).

L'inventaire de 629 routes est donc un **minorant**, ce que la page affiche
explicitement (« liste possiblement partielle »).

L'instantané pris après Routes est **identique à T1**.

## Entity Explorer

| Inventaire | Valeur |
|---|---|
| Entités | 86 (89 entrées dans `mvc/entities` : 86 dossiers + `__init__.py`, `relations.json`, `relations.sql`) |
| Champs | 457 ; les plus grandes : ElementSeance 16, Sequence 14, Scenario 13, Seance 13, Questionnaire 12 |
| Relations | 120 (= `relations.json`) |
| Diagnostics | 0 erreur, 0 avertissement |
| Troncature | Aucune (bornes de 256 fichiers et 256 champs non atteintes) |
| Page | 203 ms, graphe présent |

Vérification manuelle :

- Sequence (14 champs, table `sequence`), ElementSeance (16) et Seance (13)
  correspondent exactement à leurs fichiers JSON ;
- les relations Sequence → NiveauClasse (`many_to_one`, `niveau_classe_id`) et
  Seance → Sequence existent bien dans `relations.json`.

Aucun accès à la base : l'analyse reste statique.

**Faux positif : 0. Faux négatif : 0.** L'instantané est identique à T1.

## Template Viewer

| Inventaire | Valeur |
|---|---|
| Templates | **497** (496 `.html` + `components/pdf/texte_enrichi.css.jinja`) ; inventaire complet, 0 anomalie |
| Jinja | **497 valides, 0 invalide** |
| Références | `extends` 195, `include` 382, `from … import` 361, `import` 9 ; 9 dynamiques ; au plus 14 par template |
| HTMX | 100 templates portent des attributs `hx-*` |
| Contrats associés | 0 (aucun `.view.json`) |
| Pages | `/templates` en 121 ms ; 12 pages `/templates/view` entre 20 et 41 ms |

Vérification manuelle de 10 templates (`home/index.html`, `layouts/base.html`,
`app/drawciel/editeur.html` et `index.html`, `app/matiere/index.html` et
`_results.html` (HTMX), `app/auth/login.html`, `app/bilan_eleve/preparer.html`,
`app/referentiel_atelier/tunnel.html`, `app/formation/show.html`).

Les références de Forge Design ont été comparées à un relevé indépendant par
expression régulière : **10/10 justes**. Le seul écart apparent,
`layouts/base.html` (7 contre 8), vient de mon relevé : la 8ᵉ occurrence est un
`{% extends %}` cité **dans un commentaire Jinja** (l. 4), que Forge Design
ignore à juste titre.

L'instantané est identique à T1.

## Vendor / DrawCiel

Pas de bruit : Template Viewer n'analyse que `mvc/views`.

- Les 228 fichiers de `static/vendor/`, le fichier HTML de `static/` et les 641
  pages HTML générées de `site/` et `site-guide/` (MkDocs) sont **hors
  inventaire**, ce qui est correct.
- Les 5 templates DrawCiel (`app/drawciel/*.html`) sont inventoriés et valides.
- DrawCiel est une fonctionnalité de SéquenCiel, sans lien avec le module Circuit,
  qui n'est pas activé.

## Migrations

**251** fichiers `mvc/migrations/*.sql` (= `ls`), en ordre lexical, du
`20260626150000_create_notifications.sql` au
`20261013181349_catalogue_reseau_virtuel_r4_v1.sql`.

Aucun nom non conforme, aucun fichier vide, 0 anomalie. Aucune exécution.

## View Contracts

**0 contrat** (aucun `*.view.json` dans le dépôt). 0 valide, 0 invalide, 0
associé, 0 orphelin ; les 497 templates sont « sans contrat » (optionnel).
EXPECTED : SéquenCiel n'utilise pas ce format de Forge Design.

## Design Files

**0 fichier `*.design.json`** dans tout le dépôt (`tmp/` et `sauvegardes/`
compris). Aucun n'est ouvert dans l'éditeur.

## Debug Center lecture seule

| Contrôle | Résultat |
|---|---|
| Journal | `storage/logs/errors.dev.jsonl` présent (17 868 octets, 13 lignes) |
| Événements lisibles | 13, tous `ERROR`, catégorie runtime : 10 `OperationalError`, 3 `UniqueViolationError` ; du 2026-09-14 au 2026-10-08 |
| Anomalies de lecture | 0 |
| Troncature | Non |
| Pages | Liste (62 ms), détail d'un événement (82 ms), recherche `q` (42 ms) |
| Formulaires doctor, audit, check | Affichés (3), **jamais soumis** : 0 `POST /debug/forge*` dans le journal du serveur |
| Masquage | Visible sur un message (« unrecognized token: [masqué] ») |

Les erreurs (`database is locked`, `unrecognized token`, violations d'unicité)
sont des erreurs passées de l'application : SEQUENCIEL-ISSUE, à examiner côté
SéquenCiel. Aucun contenu d'événement n'est recopié ici.

L'instantané est identique à T1.

## Vérification des secrets

Méthode : un seul processus Python extrait les valeurs candidates **en mémoire**,
récupère lui-même le HTML servi et compare sur place.

- Sources des candidats : `env/*` (actualisation, dev, example, prod), clés
  sensibles et mots de passe d'URL ; `config.py`, constantes à clé sensible ;
  `cert.pem` et `key.pem`, lignes de contenu.
- Aucune valeur n'a transité par des arguments, une sortie, un journal ou un
  fichier.
- Surfaces vérifiées : texte, attributs et URL de chaque page explorée, et
  réponses aux sondes de traversée.

| Mesure | Résultat |
|---|---|
| Valeurs candidates analysées | **45**, dont 1 nom de fichier non secret (`key.pem`) |
| Pages vérifiées | 400 (exploration GET bornée), plus les 9 sections de l'Inspector et les sondes |
| **Valeur sensible retrouvée** | **0** |

Une correspondance est apparue, puis a été écartée par analyse en mémoire. La page
de refus `/source?path=key.pem` (400) réaffiche le **chemin demandé**, « key.pem »,
qui est aussi la *valeur* d'une clé de configuration du type fichier de clé (dans
`env/example` et `config.py`). Ce n'est pas un secret. C'est un faux positif de mon
détecteur, pas de Forge Design.

## Liens sources

Les 394 liens `/source?…` découverts par l'exploration (sur 6 512 proposés par
`/routes`) répondent tous 200, en lecture seule, et pointent **tous** sous la
racine de SéquenCiel (394/394 ; 0 hors racine).

Le premier lien source de `/routes` ouvert dans Chromium affiche une source en
lecture seule.

## Sécurité

Traversée testée par le vrai paramètre de l'interface (`/source?path=`, modifiable
dans la barre d'adresse) :

| Sonde | Statut | Contenu exposé |
|---|---|---|
| `../../../etc/passwd` | 400 | Non |
| `/etc/passwd` (absolu) | 400 | Non |
| `../ForgeDesign/README.md` | 400 | Non |
| `..%2F..%2Fetc%2Fpasswd` (encodé) | 400 | Non |
| `env/dev` (dans la racine, fichier de secrets) | 400 | Non |
| `key.pem` (dans la racine) | 400 | Non (seul le chemin est réaffiché) |

**Aucune sortie de racine.** La vue source refuse aussi les fichiers sensibles
situés dans la racine. Garde Host stricte (400) et écoute en loopback seulement.

## Chromium

Six phases scriptées (ouverture et Inspector, Routes, Entités, Templates, Debug,
Récents), chacune avec un profil neuf, détruit ensuite : **24 pages**, toutes
avec un seul `h1` et aucune alerte d'erreur.

Le seul chargement de plus de 500 ms est `/routes` (1 152 ms). Pas de Firefox ni
de parcours sans JavaScript : ils sont qualifiés par la release 0.2.1.

## Console / CSP

- **0 violation CSP** et 0 exception JavaScript.
- 6 « erreurs » de console, toutes de type réseau : ce sont les 6 requêtes
  `GET /favicon.ico` en **404**, car Forge Design ne sert pas de favicon.
  FORGEDESIGN-ISSUE, cosmétique.

## Réseau

**105 requêtes**, toutes vers `127.0.0.1:8765`. Aucune ressource externe.

Les seuls POST sont `/inspector` (ouverture), `/project/close` et
`/project/open-recent`, qui écrivent uniquement l'état de Forge Design dans le
HOME isolé.

## Performances

Cinq GET par page, mesurés côté HTTP, avec SéquenCiel ouvert :

| Page | Médiane | Max | Taille | Classement |
|---|---:|---:|---:|---|
| `/inspector` | 660 ms | 767 ms | 10,6 Ko | Acceptable (synthèse recalculée à chaque affichage) |
| `/routes` | 875 ms | 951 ms | **4,0 Mo** | Acceptable mais lourd : page très volumineuse, 1,15 s dans le navigateur |
| `/entities` | 53 ms | 54 ms | 275 Ko | Fluide |
| `/templates` | 23 ms | 24 ms | 181 Ko | Fluide |
| `/debug` | 19 ms | 20 ms | 12 Ko | Fluide |

Ouverture du projet : 729 ms. Aucune page n'est gênante. La taille de `/routes`
(629 chaînes dépliables) est le seul point à surveiller.

## Mémoire

RSS du serveur :

| Moment | RSS |
|---|---:|
| Avant ouverture | 46,0 Mio |
| Après ouverture (Inspector) | 86,3 Mio |
| Après Routes | 109,5 Mio |
| Après la navigation complète (Entités, Templates, Debug, Récents) | 109,6 Mio |
| Après l'exploration de 400 pages et les mesures | 143,7 Mio |

Il ne s'agit pas d'un banc d'essai mémoire. La croissance pendant l'exploration
(400 GET, dont 394 pages sources) n'est pas qualifiée comme fuite, mais elle est
notée.

## Projets récents

- Pendant que SéquenCiel est le projet courant, l'accueil ne propose pas de bouton
  « Ouvrir » pour lui (comportement du gabarit, EXPECTED).
- Après **Fermer** (« Aucun projet »), SéquenCiel figure dans les récents.
- **La réouverture depuis les récents fonctionne.**
- État écrit uniquement dans `HOME isolé/.config/forge-design/recent-projects.json`.

## Snapshots intermédiaires

| Point | Comparaison avec T1 |
|---|---|
| Après Inspector | Identique |
| Après Routes | Identique |
| Après Entités | Identique |
| Après Templates | Identique |
| Après Debug | Identique |

## Snapshot final

Pris à 21:56:03, après l'arrêt de Forge Design.

**Final == T1** : 0 création, 0 suppression, 0 contenu modifié, et aucune
mtime, ctime ou inode modifiée, sur 567 471 entrées (7 798 au niveau complet avec
SHA-256).

HEAD reste `008a895e…`, et l'empreinte du statut (`8ab46141…`) est identique avant
et après, et identique à celle des sondes de FD-FORGE-004 et FD-RELEASE-003.

**Aucune dérive pendant le test** : la qualification n'est pas contaminée.

## Processus finaux

- Ctrl+C (SIGINT) sur le serveur : arrêt propre, **code de sortie 0**.
- Aucun enfant n'a existé pendant le test : ni runtime, ni preview, ni proxy.
- Il ne reste aucun processus Forge Design ni Chromium, et aucune écoute sur 8765
  (serveur) ou 9341 (CDP).
- Restent les processus préexistants autorisés (session VS Code Remote-SSH,
  fenêtre ForgeDesign, `mariadbd` système).

## Observations SéquenCiel

- **13 erreurs runtime passées** dans le journal de développement :
  `database is locked`, `unrecognized token` (SQL), 3 violations d'unicité. Elles
  vont du 14/09 au 08/10 et sont à examiner côté application.
- **Forge épinglé par une référence Git directe** (même commit `1af6301` pour
  forge-mvc et ses opt-ins). C'est un choix légitime, documenté dans
  `requirements.txt`.
- **Projet sans `bootstrap.py`** (squelette Forge 1.0.0-rc.3), registre d'opt-ins
  actif (MariaDB, admin, rbac, mfa…). Il est désormais reconnu.
- Aucun défaut SéquenCiel n'est révélé par les analyses statiques : 497 templates
  valides, 0 anomalie d'entité, 0 anomalie de migration.

## Observations Forge Design

| # | Observation | Gravité | Classement |
|---|---|---|---|
| 1 | Borne globale de 128 templates : 102 chaînes à template exact classées partielles, 164 avertissements, Routes en Attention | Majeure, non bloquante (limite signalée) | FORGEDESIGN-ISSUE |
| 2 | Templates rendus par un helper (`_traiter`, `editeur()`) non suivis : faux négatifs de template (2 confirmés ; au plus environ 113 routes concernées, estimation) | Mineure (limite documentée) | FORGEDESIGN-ISSUE |
| 3 | Version Forge « indéterminée » pour un épinglage Git direct | Mineure | FORGEDESIGN-ISSUE |
| 4 | « Déclaration non interprétée » sur des instructions qui ne déclarent pas de route (l. 234, 243, 251) | Cosmétique | FORGEDESIGN-ISSUE |
| 5 | `favicon.ico` en 404 | Cosmétique | FORGEDESIGN-ISSUE |
| 6 | 389 handlers sans template classés « partiels » par contrat (redirections, JSON, fichiers) : état dominant peu informatif | Amélioration | EXPECTED (contrat documenté) |
| 7 | `/routes` de 4 Mo, à 0,9–1,2 s | À surveiller | EXPECTED |

## Limites Forge

- **Opt-ins actifs** (`register_admin`, `register_optins`) : leurs routes ne sont
  pas visibles statiquement (FORGE-LIMITATION ; FD-ACC-002 ne couvre que le
  registre vide).
- **Routes générées par boucle** (12 dans `drawciel_mcu_routes.py`) : absentes de
  la lecture statique (FORGE-LIMITATION, documentée).
- Aucune analyse n'exécute le projet : par construction, ni la configuration, ni
  la base, ni les imports dynamiques ne sont pris en compte.

## Matrice

| Domaine | Inventaire | OK | Attention | Erreur | Faux positif | Faux négatif | Verdict |
|---|---|---|---|---|---|---|---|
| Projet | SéquenCiel reconnu en 729 ms ; 9 sections | 6 | 3 (Forge, Routes, Diagnostics) | 0 | 0 | 0 | Utilisable |
| Routes | 629 (276 GET, 353 POST) ; 99 complètes, 530 partielles, 0 problématique ; 201 avertissements | 593 routes sans diagnostic | 36 routes à diagnostic ; 164 troncatures | 0 | 0 (0 route problématique) ; 3 lignes non-route signalées | 12 routes en boucle ; routes d'opt-ins ; templates par helper (2 confirmés, au plus environ 113) ; 102 chaînes non analysées (borne) | **Utilisable avec limites** |
| Entités | 86 entités, 457 champs, 120 relations | 86 | 0 | 0 | 0 | 0 | Fiable |
| Templates | 497 ; 497 Jinja valides ; 947 références | 497 | 0 | 0 | 0 (10/10) | 0 (10/10) | Fiable |
| Migrations | 251 | 251 | 0 | 0 | 0 | 0 | Fiable |
| Diagnostics | 13 événements, 0 anomalie de lecture | — | 13 erreurs passées (Attention) | 0 (jamais « erreur » projet) | 0 | 0 | Fiable |
| Contrats | 0 | — | — | — | — | — | Sans objet |
| Designs | 0 `*.design.json` | — | — | — | — | — | Sans objet |

## Classification

| Catégorie | Constats |
|---|---|
| SEQUENCIEL-ISSUE | 13 erreurs runtime historiques du journal de développement |
| FORGEDESIGN-ISSUE | Borne de 128 templates (majeure, non bloquante) ; templates rendus par helper ; version Forge par épinglage Git ; déclarations non-route signalées ; favicon 404 |
| FORGE-LIMITATION | Routes des opt-ins actifs ; routes générées par boucle |
| EXPECTED | `bootstrap.py` optionnel absent ; Routes en Attention par lecture statique ; Diagnostics en Attention (erreurs passées) ; 0 contrat, 0 design ; commandes de Debug affichées mais non exécutées ; vue source refusant les chemins hors `mvc` ; handlers sans template « partiels » par contrat |
| UNKNOWN | Écritures de la racine et de `.git` à 21:07:55 et 21:37 (avant T0), probablement liées à la fermeture de la fenêtre VS Code SéquenCiel ; hors fenêtre de qualification |
| BLOCKING | **Aucun** |

## Verdict

**SEQUENCIEL_READONLY_PASS_WITH_ISSUES**

Conditions de PASS réunies :

- SéquenCiel reconnu ;
- les cinq outils utilisables ;
- **aucune écriture** (instantané final = T1, au niveau des ctime et des inodes) ;
- **aucune fuite** (0 valeur sensible sur 44) ;
- **aucune sortie de racine** ;
- aucun processus restant.

Pourquoi « with issues » plutôt que PASS : la fiabilité de Route Explorer est
dégradée sur un projet de cette taille. 102 chaînes ne sont pas analysées à cause
de la borne de 128 templates, l'inventaire ne voit ni les routes générées ni
celles des opt-ins, et des templates rendus par des helpers échappent à
l'analyse.

Ces limites sont **toutes signalées** par l'interface (« limite atteinte »,
« liste possiblement partielle ») et aucune n'induit un faux diagnostic d'erreur :
0 route problématique à tort. Ce ne sont donc pas des « fausses analyses
importantes » au sens du §80. Aucune condition de BLOCKED n'est remplie.

## Recommandation ticket suivant

**FD-SEQUENCIEL-002 : première frontière d'exécution, `project:audit` seul**, sur
la même 0.2.1 installée, avec la même méthode : stabilité T0/T1, HOME isolé,
instantanés avant/après, secrets en mémoire. C'est l'audit officiel en lecture
seule de forge-mvc rc9, qui n'exécute aucun code du projet. Ensuite `doctor`, puis
`project:check`, puis Real Preview, puis l'édition, un ticket par frontière (§91).

En parallèle, hors chemin critique, un ticket Forge Design est recommandé :
**FD-ROUTES-023**, une borne de templates adaptée aux grands projets. Par exemple
une borne par route plutôt que globale, ou un plafond revu et mesuré sur
SéquenCiel (497 templates). Le constat n°1 en est la cause principale. Les
constats 2 à 5 sont des améliorations distinctes et mineures.

## Fichiers créés

- `docs/rapports/FD-SEQUENCIEL-001.md`

Aucun fichier n'est créé dans SéquenCiel.

Les outils (instantané, Chromium, exploration) et les instantanés compressés
restent dans le scratchpad de la session, hors des deux dépôts. Ils ne contiennent
aucune valeur sensible : seulement des empreintes et des métadonnées.

## Fichiers modifiés

- `docs/03-roadmap.md` : FD-SEQUENCIEL-001 et son verdict, et la suite (FD-SEQUENCIEL-002).

Non modifiés : `forge_design/`, les tests, le kit, les rapports historiques,
`docs/rapports/FD-CONTRACT-001.md`, SéquenCiel, Circuit, Flowchart.

## Validation finale

Le ticket ne change que ce rapport et la roadmap. Conformément au §87, la suite
complète n'est pas relancée. Validation documentaire faite sur le contenu exact du
commit :

| Commande | Résultat |
|---|---|
| `git diff --check` (rapport + roadmap) | OK |
| `ruff format --check` (rapport + roadmap) | 2 fichiers déjà formatés |
| Tests qui lisent `docs/` (`test_design_schema.py`, `test_view_contract_schema.py`) | 45 réussis |

## États Git finaux

**Forge Design** : un commit sur `main`,
`test: qualifier SéquenCiel en lecture seule (FD-SEQUENCIEL-001)`. Il contient ce
rapport et la roadmap. Il n'est pas poussé : 20 commits d'avance sur `origin/main`.
`FD-CONTRACT-001.md` et les 575 fichiers non suivis sont inchangés.

**SéquenCiel** : HEAD `008a895e6f97c79444228b4837816b3409ee881b`, statut
identique (17 fichiers non suivis, préexistants), **aucun commit et aucune
modification**.
