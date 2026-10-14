# Rapport — FD-ACCEPTANCE-001

Qualification de bout en bout de Forge Design avant usage sur un vrai projet (SéquenCiel). Date : 2026-10-14.

## Objectif

Question posée : Forge Design est-il assez stable, cohérent et sûr pour être utilisé sur un vrai projet Forge, sans risquer d'altérer ses sources ni de produire des diagnostics trompeurs ? Ce ticket est une qualification, pas un développement : aucun code de Forge Design n'est modifié, et chaque défaut est classé puis renvoyé à un ticket correctif.

| Décision | Résultat |
|---|---|
| A. Nouvelle fonctionnalité ? | Non |
| B. Qualification globale ? | Oui |
| C. Projets contrôlés avant SéquenCiel ? | Oui : 10 projets jetables, SéquenCiel jamais touché |
| D. Roue réelle ? | Oui : roue 0.2.0 installée hors ligne dans un venv neuf |
| E. Chromium + Firefox ? | Oui |
| F. Sans JavaScript ? | Oui |
| G. Modules externes ? | Oui : Circuit 0.1.0 et Flowchart 0.1.0 actifs |
| H. Écriture utilisateur réelle ? | Non : copies jetables seulement |
| I. Verdict formel ? | **REJECTED** |
| J. Gate SéquenCiel ? | **CLOSED** |

## État Git initial

| Élément | Valeur |
|---|---|
| HEAD | `08a4354` (FD-RUNTIME-004) |
| `origin/main` | `e411d0c` ; 0 commit en retard, 7 en avance |
| Arbre | Seul `docs/rapports/FD-CONTRACT-001.md` est modifié par l'utilisateur ; il est préservé et hors commit |
| Collision | Aucune : FD-ACCEPTANCE-001 n'existait nulle part |
| Modules | ForgeDesign-Circuit (`967b5b3`) et ForgeDesign-Flowchart (`a8ec22d`) propres, non modifiés |

## Périmètre

Le ticket qualifie ce qui existe aujourd'hui dans l'interface (§41) :

- Project Inspector et projets récents ;
- Route Explorer, Entity Explorer, Template Viewer ;
- éditeur structurel (`.design.json`), avec preview statique et preview réelle ;
- Debug Center : journal, détail, flux, `doctor`, `project:audit`, `project:check` ;
- modules Circuit et Flowchart.

La génération de template, SAFEWRITE et l'historique de génération n'ont **aucune route Web**. Ils ne sont pas qualifiables par l'interface et restent couverts par pytest (§41).

MkDocs n'est pas configuré (pas de `mkdocs.yml`) : le §113 est sans objet.

## Baseline

| Élément | Valeur |
|---|---|
| Forge Design | 0.2.0 (roue, `forge-design --version`) |
| Forge | forge-mvc, forge-mvc-sqlite, forge-mvc-entities 1.0.0rc9 (venv réel par projet) |
| Python | 3.13.5 |
| Navigateurs | Chromium headless (CDP), Firefox headless (WebDriver BiDi) |
| Suite existante | 5 024 tests pytest, 134 tests Node, tous verts |

## Méthode de qualification

Le kit versionné **`scripts/acceptance/`** est hors paquet : il n'est pas inclus dans la roue (vérifié). Il ne contient aucun secret réel, chemin local absolu, venv, journal ou résultat, et se lance par `run.sh <dossier-de-travail>`. Tout est produit sous ce dossier.

| Étape | Contenu |
|---|---|
| `wheels` | Roues du cœur et des deux modules construites depuis leurs dépôts ; inspection de la roue du cœur |
| `install` | Dépendances téléchargées une fois, venv neuf, installation **hors ligne** (`--no-index`), `pip check` |
| `projects` | Venv Forge 1.0.0rc9 réel, projets construits par `build_projects.py` |
| `startup` | Démarrage depuis `/tmp`, un dossier HOME et un projet Forge : aucun projet implicite |
| `security` | Écoute réseau, garde Host et Origin |
| `browsers` | Parcours de 29 étapes, Chromium puis Firefox, modules actifs, instantanés sha256 avant et après |
| `nojs` | Parcours Firefox sans JavaScript, 8 étapes |
| `measures` | Temps des pages (B, D), commandes runtime (A), endurance mémoire avec modules |
| `shutdown` | Preview réelle active, puis Ctrl+C réel (SIGINT), puis recherche de processus restants |

Contrôles transverses à **chaque** page : exceptions et erreurs de console, violations CSP (écouteur injecté avant les scripts de la page), requêtes hors `127.0.0.1`, présence d'une valeur sensible dans le HTML et les attributs, accessibilité minimale (un `h1`, pas de saut de titre, libellés de champs, noms accessibles).

La suite pytest et les tests Node existants sont relancés tels quels, pas recopiés (§91).

Le parcours complet a été rejoué de bout en bout sur un dossier de travail **neuf**, avec des résultats identiques à la première passe.

## Projets utilisés

| Projet | Contenu | Rôle |
|---|---|---|
| **A** | Vrai squelette Forge, entité `Contact`, route `/contacts` → contrôleur → template, contrat et design, migration, journal vide | Nominal, lecture seule |
| A-preview | Copie de A | Seule cible de la preview réelle (exécute le projet) |
| A-bare | Squelette nu, sans entité ni journal | États optionnels (journal absent, entités absentes) |
| **B** | gx8 enrichi (vendorisé dans `fixtures/gx8`) : routes, contrôleurs (dont un manquant et un handler d'usine), entités et relations hostiles, templates imbriqués, contrats (dont un invalide), design, migrations (dont une mal nommée), journal avec secrets synthétiques, doublons et ligne invalide | Représentatif et volontairement problématique ; routes et application lèvent si exécutées |
| B-write | Copie de B, plus les ressources Circuit et Flowchart | **Seule** cible des écritures (éditeur, modules, rotation du journal) |
| **C** | Squelette importable avec les défauts du §15 : route vers template absent, contrats (JSON invalide, sans template, deux sur un template), Jinja invalide, contenu hostile, relation vers entité inexistante, migration mal nommée, route `/items/<int:item_id>`, template calculé, journal avec erreurs | Diagnostics |
| C-check | Copie de C dont le contrôleur écrit `CONTROLLER_IMPORTED` | Effet de bord contrôlé de `project:check` |
| C-timeout | Copie de C dont les routes impriment puis bloquent | Délai dépassé avec `-u` |
| **D** | 200 routes, 250 templates, 250 contrats, 250 entités, 500 migrations, 2 000 événements | Volume, performance |
| invalid | Dossier non Forge, fichier à la place d'un dossier ; chemin absent | Projets invalides |

## Installation depuis wheel

| Vérification | Résultat |
|---|---|
| Roue `forge_design-0.2.0` | 165 fichiers ; **34 ressources** du dépôt (gabarits, statiques, schémas) toutes présentes ; `py.typed`, `child_bootstrap.py` présents |
| Absences | Aucun test, document, rapport, fixture, `__pycache__`, `.pyc`, `env/dev`, ni Circuit ou Flowchart dans la roue du cœur |
| Installation hors ligne | `pip install --no-index` depuis les roues et les dépendances locales : OK |
| `pip check` | No broken requirements found |
| `forge-design --version` | Forge Design 0.2.0 |
| Sans checkout | Le serveur tourne depuis le venv neuf, lancé hors du dépôt |

## Démarrage

Commande réelle : `forge-design --no-browser [--module …]`, avec HOME et XDG isolés.

| Dossier courant | Prêt en | Projet ouvert implicitement |
|---|---:|---|
| `/tmp` | 475 ms | Non |
| Dossier HOME de test | 474 ms | Non |
| Racine d'un projet Forge (A) | 469 ms | **Non** |

Sans projet : aucune analyse, aucune synthèse et aucun bouton de commande sur `/routes`, `/entities`, `/templates`, `/debug` et `/inspector`.

## Sécurité locale

| Contrôle | Résultat |
|---|---|
| Écoute | `127.0.0.1:8765` uniquement ; ni `0.0.0.0` ni `::` |
| Host `127.0.0.1:8765` | 200 |
| Host `localhost:8765` | 400, conforme au contrat FD-WEB-003 (voir ACC-001) |
| Host étranger, DNS rebinding | 400 |
| POST avec Origin étrangère, sans Origin, ou `Sec-Fetch-Site: cross-site` | 403 |
| Preview réelle active | Proxy et application sur `127.0.0.1` seulement |

## Project Inspector

A, B et C (deux navigateurs) :

- projet reconnu, Forge 1.0.0rc9, structure 5/5 ;
- 9 sections de synthèse ;
- chaque état est écrit en texte (`✓ OK`, `! Attention`, `✕ Erreur`), jamais par la seule couleur ;
- chaque lien de section mène à sa page.

| Projet | État global | Sections non OK |
|---|---|---|
| A | ! Attention | Routes ! Attention (ACC-002) |
| B | ✕ Erreur | Routes ✕, Migrations !, Diagnostics !, Contrats ! (défauts de la fixture) |
| C | ✕ Erreur | Routes ✕, Entités ✕, Migrations !, Diagnostics !, Contrats ! (défauts de la fixture) |

Actualiser conserve le projet ; Fermer revient à « Aucun projet ».

Projets invalides (non Forge, absent, fichier) : message, aucun projet ouvert.

Projet modifié hors Forge Design (`app.py` supprimé, puis Actualiser) : le projet est **fermé** (« Aucun projet ouvert »), conformément au contrat, sans `.forge-design/` ni autre fichier créé.

## Projets récents

- Ordre du plus récent au plus ancien.
- Ouverture depuis la liste ; le projet courant est marqué « Ouvert », sans bouton d'ouverture.
- Retrait.
- Projet supprimé du disque : état `missing`, « Projet introuvable », plus de bouton Ouvrir, Retirer toujours possible.

## Route Explorer

**B** (deux navigateurs) :

- routes, handlers, contrôleurs, méthodes et templates (`/contact/list`, `ContactController.list`, `contacts/list.html`, `/users`, `/factory`) ;
- recherche au clavier (saisie, puis Entrée), filtres méthode, visibilité, sévérité et « uniquement avec diagnostics » ;
- chaîne dépliée ;
- graphe du Graphic Core (22 nœuds) ;
- lien vers la source.

**C**, chaque route dans son état :

| Route | Chaîne |
|---|---|
| `/items/<int:item_id>` (route dynamique) | `items/show.html`, ✓ Complète |
| `/dynamic` (template calculé) | « template non déterminable », ◐ Partielle : **jamais** déclaré absent ni invalide |
| `/absent` | `missing/page.html`, ✕ Problématique |
| `/broken` | `broken/jinja.html`, ✕ Problématique ; template « Présent, Invalide » |

## Entity Explorer

- B : entités et relations hostiles affichées en texte ; aucun script exécutable ne les contient (la scène JSON du graphe les échappe en `<…`).
- Graphe du Graphic Core, filtres.
- A-bare : l'absence d'entités reste optionnelle, jamais une erreur.

## Template Viewer

- B : inventaire ; lecture brute de `contacts/list.html` (`{% extends "base.html" %}`, `include`) ; arbre ; navigation par les références.
- C : contenu hostile `<script>alert(1)</script>` affiché en texte, jamais exécuté ; `broken/jinja.html` signalé « Syntaxe Jinja invalide à la ligne 2. ».

## Contrats de vue

| Cas | Observé |
|---|---|
| Valide | `contacts/list.view.json` (A), associé, liaison complète |
| JSON invalide | `broken.view.json` (B), `broken/jinja.view.json` (C) : listés invalides, comptés dans « Invalides » de la synthèse, non associés |
| Sans template | `orphan.view.json` (C) : listé, non associé |
| Plusieurs contrats pour un template | `items/show.view.json` et `items/second.view.json` (C) : la chaîne en retient un, comme le prévoit FD-ROUTES-021 |

## Design / Editor existants

Sur B-write :

- lecture d'un `.design.json` et de son arbre ;
- preview statique dans une iframe ;
- action explicite (classe Tailwind) écrite immédiatement, JSON valide, « Modification enregistrée. » ;
- même action répétée : « Aucune modification. », **aucune** écriture (octets identiques).

**Défaut** : une action envoyée depuis une vue périmée vise le bloc qui occupe **maintenant** le chemin, et non celui que l'utilisateur voyait (ACC-004).

## Écritures contrôlées existantes

Seul l'éditeur Web écrit, uniquement dans le `.design.json`, une écriture par action, atomique, avec révision vérifiée **à l'intérieur de la requête**.

Les formulaires ne transportent pas la révision affichée. Démonstration dans les deux navigateurs (aucune écriture externe, deux « onglets ») :

1. ajout d'une section : `[section, table, section]` ;
2. un onglet supprime le bloc 0 : `[table, section]` ;
3. l'autre onglet, dont la vue est périmée, supprime « le bloc 1 », qu'il voyait comme la `table`.

Résultat : 303 « Modification enregistrée. », et `[table]` sur le disque. C'est **la section qui a été supprimée**, avec ses descendants, sans conflit annoncé. L'éditeur n'a pas d'historique pour annuler. Une écriture externe valide (éditeur de texte, Git) produit le même effet.

Diff avant écriture, SAFEWRITE et historique de génération ne sont pas exposés dans l'UI (§43).

## Debug Center

| Journal | Projet | Affiché |
|---|---|---|
| Absent | A-bare | « Aucune erreur runtime enregistrée. » |
| Vide | A | « Aucune erreur runtime enregistrée. » |
| Valide et partiellement invalide | C, B | Événements, plus « anomalies de lecture » |
| Au plafond (2 000) | D | « Lecture partielle du journal. » |

Sur B-write :

- `DB_PASSWORD=[masqué] connection refused` ; `token_count=3 password_policy=strict` conservé ;
- filtres `q`, `level=CRITICAL`, `category=database`, `order=oldest` ;
- recherche d'une valeur sensible : aucun événement ;
- doublon d'id : deux liens distincts (ligne et id) ;
- détail : `postgresql://roger:[masqué]@10.0.0.2/db`, URL de détail sans valeur ;
- flux en SVG serveur et en Graphic Core ;
- rotation simulée du journal : l'ancien lien répond **404**.

Aucune des six valeurs synthétiques (`DB_PASSWORD`, `SERVICE_TOKEN`, URL avec mot de passe, `Authorization`, `OPENAI_API_KEY`, query) n'apparaît dans le HTML d'aucune page. Le champ de recherche réaffiche la saisie de l'utilisateur : c'est sa propre entrée, exclue du contrôle comme dans FD-DEBUG-006.

## Doctor

| Projet | État, code | Cause | FAIL |
|---|---|---|---|
| A | succeeded, 0 | — | — |
| B | checks-failed, 1 | `[FAIL] Environnement` (clés SSL absentes de l'`env/example` minimal de B) ; `[FAIL] Entités` (`hostile.json` invalide) | **Attendu** de la fixture |
| C | checks-failed, 1 | `[FAIL] Entités` (relation vers entité inexistante) | **Attendu** de la fixture |

Le GET n'exécute rien. Un POST lance une exécution. Le résultat n'est pas persisté. Les deux autres sections restent « non exécutées ».

## Project audit

A, B et C : succeeded, code 0. Un POST par exécution, isolé, non persisté.

## Project check

| Projet | État, code | Cause | FAIL |
|---|---|---|---|
| A | succeeded, 0 | — | — |
| B | checks-failed, 1 | `[FAIL] Routes — AssertionError: controller executed` : le contrôleur hostile de gx8 lève à l'import | **Attendu** de la fixture |
| C | succeeded, 0 | — | — |
| C-check | succeeded | `DB_PASSWORD=[masqué] depuis le contrôleur` ; `CONTROLLER_IMPORTED` écrit par le code applicatif (et non par Forge Design) | Effet contrôlé attendu |

L'avertissement de chaque commande est lisible avant le clic :

- `doctor` « exécute la configuration du projet » ;
- l'audit « n'exécute ni config.py, ni l'application, ni les tests » ;
- la vérification « importe réellement les routes du projet », « n'est pas un bac à sable ».

## Runtime timeout / -u

C-timeout, vraie commande, vrai délai : 10,12 s (Chromium), 10,13 s (Firefox). État `timed-out`. Sortie conservée : `AVANT TIMEOUT`, `SERVICE_TOKEN=[masqué] avant blocage`, `SANS-LF`. Aucun processus restant.

## Sans JavaScript

Firefox avec `javascript.enabled=false`, vrais clics et vraie saisie, **8/8** :

- Project Inspector ;
- Route Explorer, avec tableau, chaînes, filtre et SVG serveur ;
- Entity Explorer, avec SVG serveur ;
- Template Viewer ;
- Debug Center, avec liste masquée, filtre, détail et flux SVG statique ;
- `doctor`, audit et check par POST natif, chacun dans sa section ;
- modules : métadonnées, validation et message « La visualisation graphique nécessite JavaScript. », conformément au contrat des modules, qui exclut tout rendu SVG serveur ;
- aucune requête externe.

## Graphic Core

Avec JavaScript, rendus vérifiés : graphe des routes (22 nœuds sur B), graphe des entités, flux runtime du détail, ressources Flowchart et Circuit (calque, poignées). Sans JavaScript, les replis serveur sont lisibles.

La sélection d'un nœud du flux n'est pas rejouée par le kit ; elle est couverte par les tests de FD-GRAPHICS-008.

## Circuit

Ressource `demo.circuit.json` (B-write) ouverte, composant déplacé **au clavier** (Ctrl+Maj+→). Un seul composant change sur le disque, avec une ligne d'historique. Aucun asset Flowchart n'est chargé sur la page Circuit.

La création ou modification de connexion n'est pas rejouée (§63, « si fixture adaptée »).

## Flowchart

Ressource `simple.flow.json` ouverte ; un nœud renommé, puis une arête renommée, au pointeur. Le disque est modifié, le nombre de nœuds est inchangé, et il y a une ligne d'historique par action (3 au total avec Circuit). Aucun asset Circuit n'est chargé sur la page Flowchart.

## Real Preview

Sur A-preview, dans les deux navigateurs et par HTTP :

- démarrage, puis état `running` ;
- iframe `http://127.0.0.1:<port dédié>/contacts`, sur un port distinct du serveur ; le proxy rend « Contacts » ;
- arrêt, puis état `stopped` ;
- redémarrage, puis changement de projet : la preview est arrêtée ;
- Ctrl+C du serveur avec la preview active : application et proxy arrêtés, aucun processus restant.

La page du squelette demande des polices `fonts.googleapis.com` : la CSP de la preview les bloque. La requête est signalée par le navigateur, puis refusée. Ce comportement est attendu (aucune ressource externe ne charge) ; le squelette s'affiche alors sans ses polices.

**Défaut** : la preview lance le projet sans `-B` et écrit des `__pycache__` dans le projet (ACC-003).

## Accessibilité

Aucun problème relevé sur l'ensemble des pages parcourues : un seul `h1`, pas de saut de titre, chaque champ libellé, chaque bouton et lien nommé.

Clavier (Chromium) :

- navigation principale atteinte par Tab, focus visible (contour de 3 px, `:focus-visible`), lien activé par Entrée ;
- recherche par Entrée ;
- commande lancée au clavier ;
- composant Circuit déplacé au clavier.

Firefox headless ne donne jamais le focus au document. `:focus-visible` et l'activation d'un bouton par Entrée n'y sont pas vérifiables, et ont été vérifiés dans Chromium : c'est une limite de l'outil, pas de Forge Design.

## CSP

Aucune violation sur les pages de Forge Design, dans les deux navigateurs, grâce à un écouteur `securitypolicyviolation` injecté avant les scripts de page. Seules violations observées : les polices externes du **projet** dans l'iframe de preview, bloquées (voir Real Preview).

## Réseau

Chromium : 604 requêtes ; Firefox : 789 ; Firefox sans JavaScript : toutes relevées. Toutes vont vers `127.0.0.1`, hormis les polices du projet dans la preview, bloquées par la CSP.

## Lecture seule

Instantanés sha256 (nom, taille, mtime, empreinte) de chacun des 10 projets, avant et après chaque passage navigateur, `.venv` exclu :

| Projet | Chromium | Firefox | Écarts |
|---|---|---|---|
| A, A-bare, B, C, C-timeout, D, invalid | Conforme | Conforme | **Aucun**, ni octet ni mtime, alors que `doctor`, audit et check y ont tourné |
| B-write | Conforme | Conforme | Écritures attendues seulement (voir ci-dessous) |
| C-check | Conforme | Conforme | `CONTROLLER_IMPORTED`, sentinelle écrite par le code applicatif |
| A-preview | **Écart** | **Écart** | 12 entrées `__pycache__` (ACC-003) |

Écritures de B-write, toutes attendues :

- `.design.json` (éditeur) ;
- `demo.circuit.json` et `simple.flow.json` (actions des modules) ;
- `.forge-design/history.jsonl` (historique des modules) ;
- `storage/logs/errors.dev.jsonl` (rotation faite par le scénario lui-même).

Aucun `.forge-design/` ni `__pycache__` inattendu ailleurs.

## Processus

- Après chaque passage navigateur, aucun processus n'a pour dossier courant un projet, ni ne le cite dans sa commande.
- Ctrl+C réel (SIGINT par défaut rétabli) avec la preview active : arrêt propre, sans trace d'erreur, aucun processus restant.
- Endurance : aucun enfant après 30 commandes.

## Packaging

Voir la section « Installation depuis wheel ».

Le kit `scripts/acceptance/` n'entre pas dans la roue : la liste de paquets est explicite et la sonde le vérifie. Les fixtures hostiles sont exclues de ruff par `scripts/acceptance/fixtures/ruff.toml`, ce qui laisse `pyproject.toml` inchangé.

## Performance

Médianes sur 7 GET (B) et 5 GET (D) :

| Page | B | D (volumineux) |
|---|---:|---:|
| Ouverture du projet | 26 ms | 198 ms |
| `/inspector` | 21,9 ms | 204,4 ms |
| `/routes` | 53,5 ms | 205,8 ms |
| `/entities` | 31,2 ms | 58,8 ms |
| `/templates` | 8,7 ms | 19,7 ms |
| `/debug` | 19 ms | 72 ms |

Aucune latence gênante, D compris.

Commandes runtime sur A (médianes sur 5, aller-retour HTTP) : `doctor` 134 ms, audit 107 ms, check 124 ms.

## Mémoire / endurance légère

Serveur avec modules, projet B-write, rounds de 9 pages (cœur et modules) × 20, puis 30 commandes :

- **un round** : 52,4 → 54,3 Mio ;
- **huit rounds sur un même serveur** : 54,1 / 54,7 / 55,6 / 55,6 / 55,6 / 55,7 / 55,7 / 55,7 Mio.

C'est un échauffement suivi d'un **plateau** (+24 Kio sur les cinq derniers rounds) : pas de fuite.

## Matrice d'acceptation

| Domaine | Projet A | Projet B | Projet C | Chromium | Firefox | Sans JS | Verdict |
|---|---|---|---|---|---|---|---|
| Project Inspector | OK (! routes, ACC-002) | OK | OK | OK | OK | OK | Accepté avec réserve mineure |
| Routes | OK | OK | OK (dynamique incertain) | OK | OK | OK | Accepté |
| Entités | OK | OK (hostile échappé) | OK | OK | OK | OK | Accepté |
| Templates | OK | OK | OK (Jinja invalide signalé) | OK | OK | OK | Accepté |
| Contrats | OK | OK (invalide global) | OK | OK | OK | OK | Accepté |
| Debug | OK (vide) | OK (masquage, 404) | OK | OK | OK | OK | Accepté |
| doctor | OK (0) | FAIL attendu (1) | FAIL attendu (1) | OK | OK | OK | Accepté |
| audit | OK (0) | OK (0) | OK (0) | OK | OK | OK | Accepté |
| check | OK (0) | FAIL attendu (1) | OK (0), C-check sentinelle | OK | OK | OK | Accepté |
| Modules | — | B-write : OK | — | OK | OK | OK (contrat) | Accepté |
| Éditeur (design) | — | B-write : **vue périmée** | — | **ÉCHEC** | **ÉCHEC** | — | **Rejeté (ACC-004)** |
| Preview réelle | A-preview : `__pycache__` écrits | — | — | OK, sauf écriture | OK, sauf écriture | — | Accepté avec réserve mineure (ACC-003) |

## Anomalies découvertes

| ID | Sévérité | Reproductibilité | Zone | Description | Impact | Contournement | Ticket recommandé |
|---|---|---|---|---|---|---|---|
| **ACC-004** | **MAJOR** | Systématique (2 navigateurs, HTTP) | Éditeur structurel (`/editor/action`) | Les formulaires ne portent pas la révision affichée ; `write_design` ne contrôle la révision qu'à l'intérieur de la requête. Une action envoyée depuis une vue périmée (deux onglets, écriture externe valide) s'applique au bloc qui occupe **maintenant** le chemin : suppression silencieuse d'un autre bloc et de ses descendants, « Modification enregistrée. » | Modification non voulue d'un fichier utilisateur, sans alerte ni annulation | Un seul onglet ; recharger l'éditeur avant chaque action ; versionner `.design.json` | **FD-EDITOR-007** : révision affichée transmise par chaque formulaire, comparée avant mutation, 409 si elle diffère |
| **ACC-003** | MINOR | Systématique | Preview réelle | Le projet est lancé avec `python -I -u`, sans `-B` : des `__pycache__` sont écrits dans le projet (racine, `mvc/controllers`, `mvc/routes`, `optins`), contrairement aux commandes de Debug Center | Écriture évitable de Forge Design dans le projet (ignorée par le `.gitignore` du squelette, sans perte de données) | Ignorer ou supprimer `__pycache__/` | **FD-REALPREVIEW-007** : ajouter `-B` à la commande de preview, avec un test d'instantané |
| **ACC-002** | MINOR | Systématique | Synthèse Project Inspector, Bridge des routes | Sur le squelette Forge officiel, `register_optins(router)` est « déclaration non interprétée » : tout projet neuf sort en « ! Attention » global | Bruit sur le cas nominal ; risque d'habituer l'utilisateur à ignorer l'avertissement | Lire le détail (avertissement honnête : liste peut-être partielle) | **FD-ROUTES-022** : reconnaître l'appel standard du squelette comme limite connue informative |
| **ACC-001** | COSMETIC | Systématique | Documentation | `01-cadrage-fonctionnel.md` annonce « écoute sur `127.0.0.1` / `localhost` », alors que `Host: localhost` est refusé (400) par contrat (FD-WEB-003) | Confusion possible en tapant `http://localhost:8765` | Utiliser l'URL affichée (`127.0.0.1`) | **FD-DOCS-001** : aligner le cadrage |

Les autres constats ne sont pas des défauts de Forge Design :

- **Firefox headless** : focus et `:focus-visible` non vérifiables (limite de l'outil, vérifiés dans Chromium) ;
- **modules sans JavaScript** : pas de SVG serveur, conformément à leur contrat ;
- **polices externes** du squelette bloquées dans la preview : comportement de sécurité attendu ;
- **FAIL de B et C** : tous attendus des fixtures, cause par cause.

## Classification

| Sévérité | Nombre | IDs |
|---|---:|---|
| BLOCKER | 0 | — |
| MAJOR | 1 | ACC-004 |
| MINOR | 2 | ACC-003, ACC-002 |
| COSMETIC | 1 | ACC-001 |

Le classement d'ACC-004 en MAJOR, et non en BLOCKER, tient à trois éléments : l'effet est limité au `.design.json`, il exige un usage concurrent, et il se contourne. C'est néanmoins une écriture silencieuse sur le mauvais bloc d'un fichier utilisateur, dans une fonction exposée de l'interface.

## Verdict

**REJECTED**

Règle du §103 appliquée sans arrangement : un défaut MAJOR (ACC-004) impose REJECTED. Le reste de la qualification est conforme :

- cockpit de lecture, diagnostics et frontière de confiance des trois commandes ;
- masquage, lecture seule hors exceptions déclarées ;
- sécurité locale, processus, packaging, performance, mémoire ;
- modules, Chromium, Firefox, sans JavaScript.

## SéquenCiel gate

**SéquenCiel gate: CLOSED**

Deux raisons : le verdict est REJECTED, et un problème d'écriture subsiste (ACC-004, ainsi qu'ACC-003 dans une moindre mesure). SéquenCiel n'a pas été touché par ce ticket.

## Tickets correctifs recommandés

1. **FD-EDITOR-007** (ACC-004, MAJOR) : transmettre la révision affichée par chaque formulaire de l'éditeur, la comparer avant toute mutation, répondre 409 et préserver le fichier. Le cas « deux onglets » de `scenario.mjs` doit alors passer.
2. **FD-REALPREVIEW-007** (ACC-003, MINOR) : ajouter `-B` à la commande de la preview réelle ; l'instantané d'A-preview doit devenir conforme.
3. **FD-ROUTES-022** (ACC-002, MINOR) : traiter `register_optins(router)` du squelette comme une limite connue informative.
4. **FD-DOCS-001** (ACC-001, COSMETIC) : aligner le cadrage sur le contrat Host.

Après 1 et 2 : rejouer `scripts/acceptance/run.sh` (FD-ACCEPTANCE-002), dont le résultat attendu est ACCEPTED_WITH_MINOR_ISSUES (ou ACCEPTED) et un gate ouvert. Viennent ensuite FD-DOCS-001 et FD-RELEASE-002, puis SéquenCiel.

## Fichiers créés

- `scripts/acceptance/README.md`, `run.sh`, `build_projects.py`, `probes.py`
- `scripts/acceptance/drivers.mjs`, `browser.mjs`, `scenario.mjs`, `nojs.mjs`
- `scripts/acceptance/fixtures/ruff.toml`
- `scripts/acceptance/fixtures/gx8/` (projet hostile, 24 fichiers, vendorisé depuis `tmp/gx8-browser`)
- `scripts/acceptance/fixtures/modules/demo.circuit.json`, `simple.flow.json`
- `docs/rapports/FD-ACCEPTANCE-001.md`

## Fichiers modifiés

- `docs/03-roadmap.md` (état d'acceptation, prochaine étape)

Aucun fichier de `forge_design/` ni de `tests/` n'est modifié ; `pyproject.toml` est inchangé.

## Validation finale

| Commande | Résultat |
|---|---|
| `python -m compileall -q forge_design tests` | OK |
| `ruff check forge_design tests` | All checks passed |
| `ruff format --check .` | 438 fichiers formatés (kit compris, fixtures exclues) |
| `pyright` (strict) | 0 erreur, 0 avertissement |
| `git diff --check` | OK |
| `pytest` (suite complète) | 5 024 passed |
| `node --test tests/js/graphics/*.test.mjs` | 134/134 |
| `mkdocs build --strict` | Sans objet (MkDocs non configuré) |
| Roue 0.2.0, venv neuf, hors ligne | `pip check` OK, inspection OK |
| Chromium, Firefox (29 étapes chacun) | 28/29 : seul échec, ACC-004 |
| Firefox sans JavaScript | 8/8 |
| Qualification rejouée sur dossier neuf | Résultats identiques |

## État Git final

Un seul commit : `test: qualifier Forge Design avant usage réel (FD-ACCEPTANCE-001)`, au-dessus de `08a4354`. Il contient le kit, ce rapport et la roadmap, et n'a pas été poussé. `docs/rapports/FD-CONTRACT-001.md` reste modifié localement, hors commit. La version reste 0.2.0.
