# Forge Design — Roadmap V2

## 0. Principe

Le nouveau dépôt repart d'une feuille blanche **architecturale**, sans effacer l'expérience acquise dans `Forge-Design-old`.

L'ancien dépôt est une référence historique.
Son architecture et son code ne sont pas repris automatiquement.

Ordre directeur :

```text
documenter
→ paquet minimal
→ Bridge réel
→ Project Inspector réel
→ extraire le contrat Tool
→ UI
→ élargir
```

Cette roadmap privilégie une tranche verticale réelle avant les abstractions générales.

## Pistes (depuis FD-ARCH-001)

La phase pilote Circuit est close : elle a prouvé le moteur générique sur un
module réel. La suite du produit se lit en **quatre pistes** séparées ;
frontières normatives : [cœur et modules](architecture/core-module-boundaries.md).
Les phases numérotées ci-dessous restent l'historique de construction.

| Piste | Contenu | État | Suite recommandée |
|---|---|---|---|
| **A. Cœur Forge Design** | Application locale Forge MVC, sélection et contexte de projet, stockage `.forge-design/`, sécurité système de fichiers, hôte de ressources, contrat spécialisé, hôte des modules, actions bornées | Socle fait ; frontières auditées et gardées (FD-ARCH-001) ; version **0.2.0** et compatibilité déclarée des modules (FD-RELEASE-001, [politique](release/versioning.md)) | Reprendre la piste B ; chaque nouvelle capacité publique du cœur : version MINEURE, puis relèvement des modules qui l'utilisent |
| **B. Outils propres à Forge** | Project Inspector, Route Explorer, Entity Explorer, Debug Center, Template Viewer, Template Designer, preview réelle | Lecture et conception de vues faites ; Project Inspector devient le cockpit du projet sélectionné : synthèse de santé en lecture seule (Projet, Forge, Structure, Routes, Entités, Templates, Migrations, Diagnostics, Contrats de vue) et liens vers les outils (FD-PROJECT-006, [Project Inspector](tools/project-inspector.md)) ; Route Explorer donne la chaîne statique de chaque route : handler, contrôleur et méthode, template(s) avec niveau de confiance, contrat(s) de vue, diagnostics avec origine et état de chaîne (FD-ROUTES-021, [Route Explorer](tools/route-explorer.md)) ; l’analyse des contrats de vue vérifie la racine Forge une fois par opération au lieu d’une fois par contrat (FD-PERF-001, mêmes résultats) ; Debug Center lance à la demande le `forge doctor` officiel du projet, par POST explicite, avec `.venv/bin/python -s -B -P -u`, dans un sous-processus borné (10 s, 256 Kio par flux, groupe tué), résultat non interprété ni persisté (FD-RUNTIME-001, [Debug Center](tools/debug-center.md)) ; il lance de même `forge project:audit`, audit officiel en lecture seule qui n’exécute aucun code du projet, par un second POST, sur un runner privé commun à liste fermée (FD-RUNTIME-002) ; puis `forge project:check`, qui importe réellement les routes et exécute donc du code applicatif, derrière un avertissement explicite ; la liste fermée compte trois commandes et la frontière des trois niveaux de confiance est démontrée par sentinelles (FD-RUNTIME-003) ; les trois commandes sont lancées en Python non tamponné (`-u`) : la sortie déjà produite reste visible après un délai dépassé, sans streaming (FD-RUNTIME-004) ; **qualification de bout en bout FD-ACCEPTANCE-001 : REJECTED, gate SéquenCiel fermé** — cockpit, commandes, sécurité locale, lecture seule et modules conformes sur roue installée (Chromium, Firefox, sans JavaScript), mais l'éditeur structurel peut modifier silencieusement un autre bloc depuis une vue périmée (ACC-004, MAJOR) ; kit rejouable dans `scripts/acceptance/` ([rapport](rapports/FD-ACCEPTANCE-001.md)) ; **ACC-004 corrigé par FD-EDITOR-007** : chaque page de l'éditeur porte le jeton opaque de la révision affichée, une vue périmée reçoit 409 sans mutation ni écriture (jeton commun avec les actions de modules) ; **ACC-003 corrigé par FD-REALPREVIEW-007** : la preview réelle lance le projet avec `python -I -B -u`, sans bytecode écrit dans le projet ni caches existants touchés (le code applicatif garde ses propres effets de bord) ; **requalification FD-ACCEPTANCE-002 : ACCEPTED_WITH_MINOR_ISSUES, SéquenCiel gate: OPEN** — kit complet rejoué sans filtre, deux passes sur dossiers neufs, depuis un worktree propre de la baseline (roue identique octet pour octet à `forge_design/` committé, travail concurrent exclu) : ACC-004 et ACC-003 corrigés et vérifiés (Chromium, Firefox, sans JavaScript, instantanés conformes), aucune nouvelle anomalie ; restent ACC-002 (MINOR) et ACC-001 (COSMETIC) ([rapport](rapports/FD-ACCEPTANCE-002.md)) ; **ACC-001 corrigé par FD-DOCS-001** : le cadrage, le README (description longue de la distribution) et l'architecture annoncent l'URL réellement servie, `http://127.0.0.1:8765/`, et le refus de `localhost` par la garde `Host`, sans changement fonctionnel ; seul ACC-002 (MINOR) reste ([rapport](rapports/FD-DOCS-001.md)) ; **FD-RELEASE-002 : RELEASE_READY — Forge Design 0.2.0 prêt pour premier essai sur SéquenCiel** : wheel et sdist construits deux fois depuis un worktree propre (contenu identique), wheel et sdist identiques à l'arbre Git du commit de release (travail concurrent exclu), installations hors ligne wheel, sdist et modules Circuit 0.1.0 / Flowchart 0.1.0 (`pip check` OK, mêmes fichiers installés), smoke tests sur les artefacts installés (démarrage, garde `Host`, parcours, modules et isolation des assets, ACC-004, ACC-003, commandes runtime) et suite complète verts ; SHA-256 consignés ([rapport](rapports/FD-RELEASE-002.md)) ; le masquage commun de Debug Center reconnaît les clés dont le dernier composant est sensible (`DB_PASSWORD`, `SERVICE_TOKEN`, `OPENAI_API_KEY`), `Authorization` préfixé et le mot de passe des URL de connexion, pour le journal comme pour le diagnostic (FD-DEBUG-006, toujours non exhaustif) ; **FD-FORGE-004 : `bootstrap.py` optionnel** dans la reconnaissance d'un projet, comme pour forge-mvc 1.0.0rc9 (`load_bootstrap`, ADR-093) ; `app.py`, `config.py`, `mvc/` et `mvc/routes/` restent obligatoires ; un `bootstrap.py` présent mais invalide reste refusé ; SéquenCiel est reconnu par la détection statique (correctif committé après la 0.2.0, version inchangée, [rapport](rapports/FD-FORGE-004.md)) ; **FD-RELEASE-003 : RELEASE_READY — Forge Design 0.2.1**, version corrective qui consolide FD-FORGE-004, FD-EDITOR-008 (verrou interprocessus de `write_design`, un commit) et FD-ACC-002 (registre d'opt-ins vide reconnu, un commit), sans capacité nouvelle ; `MODULE_API_VERSION` reste 1 et Circuit/Flowchart 0.1.0 (`>=0.2.0,<1`) acceptent la 0.2.1 sans modification ; acceptance complète en deux passes identiques (Chromium et Firefox 31/31, sans JavaScript 11/11, instantanés conformes, fixture `A-no-bootstrap`, A en Routes OK), wheel et sdist reproductibles et identiques à Git, installations hors ligne, smoke 86/86 sur l'artefact installé, course `write_design` 100/100 sur la roue installée ; **SéquenCiel readiness: READY_FOR_FD-SEQUENCIEL-001** (détection statique : reconnu) ([rapport](rapports/FD-RELEASE-003.md)) ; **FD-SEQUENCIEL-001 : SEQUENCIEL_READONLY_PASS_WITH_ISSUES** — premier essai réel de la roue 0.2.1 sur le vrai SéquenCiel, en lecture seule (Inspector, Routes, Entités, Templates, Migrations, Contrats, Designs, Debug sans commande) : projet reconnu (`bootstrap.py` optionnel absent), instantané final identique à la baseline stable (567 471 entrées, ctime et inodes compris), 0 valeur sensible exposée, 0 sortie de racine, réseau loopback seul ; 629 routes, 86 entités, 497 templates valides, 251 migrations ; limites : borne globale de 128 templates (102 chaînes non analysées), routes d'opt-ins et générées par boucle non inventoriées, templates rendus par helper non suivis, version Forge indéterminée pour un épinglage Git ([rapport](rapports/FD-SEQUENCIEL-001.md)) ; **FD-SEQUENCIEL-002 : SEQUENCIEL_AUDIT_PASS** — première frontière d'exécution : `forge project:audit` seul, lancé deux fois depuis Debug Center par un clic réel (Chromium), avec `.venv/bin/python -s -B -P -u` du projet : code 0, 2 avertissements (entité `page_document` sans fichiers générés), sortie identique d'une exécution à l'autre et juste à 23/23 lignes contre un recomptage indépendant ; enfant dans sa propre session, 3 variables d'environnement, aucun processus restant ; 6 instantanés identiques à T1 (519 214 entrées, `.venv` compris), 0 valeur sensible sur 49, résultat non persisté ; limite amont : la famille « Modules » de l'audit rc9 ignore le registre d'opt-ins ([rapport](rapports/FD-SEQUENCIEL-002.md)) ; **FD-SEQUENCIEL-003 : SEQUENCIEL_DOCTOR_PASS_WITH_ISSUES** — deuxième frontière : `forge doctor` seul, base de développement volontairement arrêtée, lancé deux fois par un clic réel, `strace` attaché au serveur : `config.py` lu avant (aucun import du projet, aucun effet hors `os.environ` de l'enfant), une seule tentative TCP vers `127.0.0.1:33389` refusée, 0 ouverture en écriture, aucun descendant ; code 1, FAIL « Base de données » fidèle, 16/16 contrôles justes contre une prévision indépendante, sorties identiques ; 4 instantanés identiques à T1, 0 secret sur 49 ; limite amont : le pilote MariaDB cite l'errno 115 (`EINPROGRESS`) au lieu du refus ([rapport](rapports/FD-SEQUENCIEL-003.md)) ; **FD-SEQUENCIEL-004 : SEQUENCIEL_CHECK_PASS_WITH_ISSUES** — troisième frontière : `forge project:check` seul, base toujours arrêtée, après un graphe d'imports statique (AST, sans exécution) de 375 modules locaux et 106 modules Forge et un gate préflight franchi ; deux exécutions par un clic réel sous `strace -f` : code 0, 7/7 justes, sorties identiques, 375/375 modules prévus réellement chargés, 5 opt-ins sur 9 importés, 0 socket, 0 écriture dans le checkout (`-B` a empêché la réécriture d'un `.pyc` périmé) ; effet applicatif contrôlé : l'import de weasyprint par `mvc/services/pdf.py` lance 86 `ldconfig`, `gcc` et `ld` (`ctypes.util.find_library`), qui créent puis suppriment 81 temporaires dans `/tmp`, tous dans le groupe du runner, sans survivant ; 0 secret exposé ([rapport](rapports/FD-SEQUENCIEL-004.md)) ; **FD-SEQUENCIEL-005 : SEQUENCIEL_REALPREVIEW_BLOCKED** — précondition fonctionnelle non satisfaite, constatée avant tout Start Preview : Real Preview 0.2.1 n'est accessible que depuis l'éditeur, pour un `.design.json` valide relié à un `.view.json`, et SéquenCiel n'en possède aucun ; frontière produit (FORGEDESIGN-LIMITATION), pas un échec technique du runner ; aucun fichier créé, aucun éditeur ni contournement, instantané final identique ([rapport](rapports/FD-SEQUENCIEL-005.md)) ; **FD-REALPREVIEW-008 : REALPREVIEW_ROUTE_ENTRY_PASS** — second point d'entrée de la preview réelle, depuis Route Explorer, **sans Design ni contrat de vue** : bouton « Prévisualiser réellement » sur les seules routes éligibles (GET, chemin statique, publique, handler vérifié, template exact et présent, identité `GET <chemin>` non ambiguë), raison lisible sinon ; `POST /routes/real-preview/start` à champ unique `route`, revalidé côté serveur (inventaire relu, égalité exacte, éligibilité recalculée, TOCTOU refusé) ; même `RealPreviewRuntime`, runner et proxy inchangés ; parcours éditeur inchangé ; 109 cas de test nouveaux, intégration réelle sans Design (`-I -B -u`, nouvelle session, aucune écriture), acceptance complète verte (Chromium et Firefox 32/32, sans JavaScript 12/12, fixture `A-route-preview`) ; constat : la sélection de l'éditeur ne détecte pas deux déclarations GET différentes du même chemin ([rapport](rapports/FD-REALPREVIEW-008.md)) ; **FD-RELEASE-004 : RELEASE_READY — Forge Design 0.3.0**, version MINEURE qui consolide FD-REALPREVIEW-008 (Real Preview depuis Route Explorer sans Design), sans autre capacité ; `MODULE_API_VERSION` reste 1, Circuit/Flowchart 0.1.0 (`>=0.2.0,<1`) acceptés sans modification (5 Tools) ; roue reproductible au SHA-256 (`d7e9f2ec…c2b1`), sdist identique en contenu, roue et sdist identiques à Git (164/164, 309/309), `route_real_preview.html` vérifié de Git à l'installation ; installations hors ligne roue, sdist et modules ; smoke 83/83 sur artefacts installés (Route Explorer sans Design, éditeur, runtime partagé, routes refusées, POST forgés, TOCTOU, ACC-003) ; acceptance complète en deux passes déterministes (Chromium et Firefox 32/32, sans JavaScript 12/12) ; 5305 tests Python, 134 Node, 8/8 mutants tués ; **SéquenCiel Real Preview readiness: READY_FOR_FD-SEQUENCIEL-005-RETRY** ([rapport](rapports/FD-RELEASE-004.md)) ; **FD-SEQUENCIEL-005R : SEQUENCIEL_REALPREVIEW_BLOCKED** — reprise sur le vrai SéquenCiel avec la roue 0.3.0 : `GET /` seule route éligible (1/629), vrai clic, vrai démarrage par le runner partagé (`-I -B -u`, nouvelle session, 4 variables), puis sortie 3 « Forge incompatible » : le bootstrap exige `app.application` (convention du squelette rc9) et l'`app.py` de SéquenCiel (lignée rc3) n'expose que `application_armee` ; blocage démontré au préflight puis observé ; ni bind, ni `/health`, ni `GET /` ; 0 écriture dans le checkout (T0 = T1 = S-START = S-STOP = FINAL), 0 socket de l'application, 0 fuite, aucun survivant ; constat : Route Explorer propose le bouton malgré un contrat de point d'entrée statiquement non satisfait ([rapport](rapports/FD-SEQUENCIEL-005R.md)) ; **FD-SEQUENCIEL-005R2 : SEQUENCIEL_REALPREVIEW_PASS_WITH_ISSUES** — requalification après SC-FORGE-001 (alias `application = application_armee` dans l'`app.py` de SéquenCiel, `07a4aeed`) avec la même roue 0.3.0 : vrai clic depuis Route Explorer sur `GET /`, ancien point d'arrêt franchi, bind loopback, `/health` 200 (WSGI Forge, sans base ni session), `running` en environ 6 s ; `GET /` répond 302 vers `/login`, suivi par l'iframe, et `/login` répond 503 avec la base volontairement arrêtée (une tentative refusée vers `127.0.0.1:33389`, session `DbSessionStore` créée dès l'affichage) ; 16/16 ressources `/static` en 200, servies par le proxy de Forge Design en lecture confinée, sans requête à l'application ; maintien stable sans sonde, Stop par SIGTERM en 121 ms, groupe vide, ports fermés ; deux cycles déterministes sous `strace -f` ; 0 écriture dans le checkout (T0 = T1 = tous les instantanés = FINAL, 519 571 entrées), 0 connexion externe, 0 secret sur 49 ; limite non bloquante : la preview sert `app.application` sans les enveloppes WSGI propres au projet (CSP complétée de `wsgi.py`), d'où des styles en ligne bloqués ([rapport](rapports/FD-SEQUENCIEL-005R2.md)) ; Phase 5 (diagnostics Forge exécutés) commencée et Phase 12 (intégration applicative) ouverte | **FD-SEQUENCIEL-006 : première édition contrôlée sur SéquenCiel**, sur la base désormais qualifiée (lecture, `project:audit`, `doctor`, `project:check`, Real Preview depuis Route Explorer) ; préalable : Design et contrat de vue adoptés par SéquenCiel dans un ticket distinct, au choix du porteur ; démarrer la base de développement reste une décision explicite ; hors chemin critique : FD-REALPREVIEW-009 (contrôle statique du contrat `app.application` dans l'éligibilité, pour les autres projets) ; étude d'une prise en charge déclarée des enveloppes WSGI du projet dans la preview ; mémoire de `/routes` sur un grand projet ; correction de la sélection de l'éditeur (déclarations GET conflictuelles) ; hors chemin critique : FD-ROUTES-023 (borne de templates adaptée aux grands projets, constat de FD-SEQUENCIEL-001) ; puis intégration applicative (Phase 12) ; la synthèse reprend toute nouvelle analyse du cœur sans nouveau Tool |
| **C. Moteur graphique générique** | Graphic Core : scène, rendu, viewport, minicarte, niveaux de détail, sélection de nœuds, `nodeMove`, calques monde, `worldAt`, `onViewChange` | Éprouvé par trois clients du cœur et un module | Aucune capacité nouvelle sans besoin réel d'au moins un client ; la sélection d'arête n'est pas prévue |
| **D. Modules externes** | Dépôts `ForgeDesign-<Domaine>` installés et activés explicitement | ForgeDesign-Circuit : module de validation (édition FDC-EDIT-001 à 007 dans son dépôt) ; **ForgeDesign-Flowchart 0.1.0** : second pilote réalisé (FD-MODULE-PILOT-001 dans son dépôt : renommage de nœuds et d'arêtes, 0 nouvelle API du cœur), qualifié avec Circuit par FD-RELEASE-002 | Aucun nouveau pilote requis ; Circuit et Flowchart poursuivent dans leurs dépôts, hors de la progression du cœur |

## Phase 0 — Fondation documentaire

### FD-FOUNDATION-001 — Documents fondateurs

Responsabilité : poser philosophie, cadrage, architecture, roadmap et politique de compatibilité.

Aucun code fonctionnel.

Validation :

```bash
git diff --check
```

### Décision de gouvernance à garder ouverte

La licence de Forge Design doit être décidée explicitement avant la première diffusion versionnée.

Aucun `LICENSE` n'est copié automatiquement depuis Forge.

## Phase 1 — Paquet minimal

### FD-FOUNDATION-002 — Paquet Python minimal

Créer :

- `pyproject.toml` ;
- package `forge_design` ;
- version Forge Design indépendante ;
- test d'import ;
- `.gitignore`.

Forge Design ne reprend pas le numéro de version de Forge.

Validation visée :

```bash
pytest
python -m compileall -q forge_design
ruff check forge_design tests
pyright
git diff --check
```

### FD-FOUNDATION-003 — CLI minimale

Fournir :

```text
forge-design --version
```

Pas encore de commande métier.

## Phase 2 — Première tranche verticale en lecture seule

### FD-FORGE-001 — Racine projet sûre

Responsabilité :

- accepter un chemin ;
- le canoniser ;
- vérifier qu'il est un dossier ;
- établir la racine de sécurité ;
- gérer les symlinks conformément à l'architecture.

Pas encore de détection Forge complète.

### FD-FORGE-002 — Détecter un projet Forge réel

Détecter un projet selon les conventions réellement produites par Forge supporté.

Ne pas exécuter l'application cible.

Le ticket comprend un test d'intégration contre un projet généré par Forge.

### FD-FORGE-003 — Lire la version Forge

Utiliser une ou plusieurs sources fiables et indiquer la source retenue.

Ne pas inventer une version si elle n'est pas déterminable.

### FD-INSPECTOR-001 — Project Inspector minimal

Project Inspector produit un résultat structuré :

```text
racine
validité
version détectée
source de version
erreurs
avertissements
```

Pas encore de registre générique.

### FD-INSPECTOR-002 — Résumé structurel

Ajouter uniquement les informations de structure réellement utiles.

Toujours en lecture seule.

## Phase 3 — Extraire Platform et contrat Tool

À ce stade seulement, observer les besoins réels de Project Inspector.

### FD-PLATFORM-001 — Contrat Tool minimal

Extraire :

- identifiant ;
- nom ;
- responsabilité ;
- entrée nécessaire ;
- résultat ou état minimal si nécessaire.

Pas d'API de plugins externes.

### FD-PLATFORM-002 — Registre explicite

Enregistrer et retrouver les Tools intégrés.

Pas de chargement dynamique arbitraire.

### FD-PLATFORM-003 — Point de composition

Centraliser l'assemblage explicite :

```text
configuration
+ services
+ Tool
```

Interdire service locator et singleton global comme mécanisme principal.

## Phase 4 — Interface Web locale

L'interface Web est une décision architecturale, pas une option à réévaluer.

### FD-WEB-001 — Serveur Web local minimal

Créer le serveur local Forge Design.

Contraintes :

```text
127.0.0.1 par défaut
pas de 0.0.0.0 par défaut
pas d'accès direct navigateur → filesystem
pas d'exposition distante implicite
```

Le ticket ne construit pas encore une interface graphique riche.

### FD-UI-001 — Shell Web minimal

Créer l'interface nécessaire pour :

- choisir un projet ;
- afficher son état ;
- accéder à Project Inspector.

Stack initiale sobre :

```text
HTML
Jinja
Tailwind
HTMX
Alpine.js seulement si nécessaire
```

### FD-UI-002 — Project Inspector graphique

Présenter les données du Tool sans dupliquer sa logique dans l'UI.

### FD-UI-003 — Ouverture navigateur

Étudier et implémenter séparément le confort de lancement :

```text
forge-design
→ serveur local
→ URL affichée
→ navigateur ouvert si configuré
```

Le comportement exact et une éventuelle option `--no-browser` sont testés dans ce ticket.

## Phase 5 — Diagnostics Forge

Après vérification des commandes réellement présentes dans les versions Forge supportées :

- runner sécurisé ;
- commandes de diagnostic autorisées (fait pour `forge doctor`, FD-RUNTIME-001, et
  `forge project:audit`, FD-RUNTIME-002, et `forge project:check`, FD-RUNTIME-003) ;
- routes si exposées de façon fiable ;
- migrations si exposées de façon fiable ;
- erreurs structurées.

Chaque capacité reste un ticket séparé.

## Phase 6 — Exploration

Introduire progressivement :

- Route Explorer ;
- Template Viewer ;
- Entity Viewer ;
- Debug Center.

Lecture seule en priorité.

## Phase 7 — Contrat de stockage projet

Avant toute ressource persistante Forge Design :

- décider la structure de `.forge-design/` ;
- versionner le format ;
- définir ce qui est partageable par Git ;
- définir ce qui reste dans le stockage utilisateur local ;
- documenter les migrations de format.

Ce ticket ne construit ni Circuit ni 3D.

## Phase 8 — Conception de vues

Après stabilisation du socle :

- contrats de vue ;
- `.design.json` ;
- bindings ;
- preview statique ;
- génération Jinja/Tailwind ;
- diff ;
- anti-écrasement ;
- éditeur structurel ;
- HTMX/Alpine contrôlés ;
- preview réelle : contrat de sécurité (FD-REALPREVIEW-001) → runner → intégration Web.

`Forge-Design-old` peut servir de référence technique, jamais de source à recopier massivement.

## Phase 9 — Contrat d'outil spécialisé

Avant Circuit, Network ou 3D, définir le minimum réellement nécessaire :

- identité ;
- capacités ;
- ressource ;
- validation ;
- erreurs ;
- sauvegarde contrôlée ;
- dépendances optionnelles ;
- intégration UI.

Valider le modèle avec un Tool simple si nécessaire.

Démarche retenue : cas réel DrawCiel → contrat minimal (FD-SPECIALIZED-001,
[contrat](specialized-tools/specialized-tool-contract.md)) → validation par un outil
spécialisé volontairement simple (FD-SPECIALIZED-002 : socle exécutable
`forge_design.specialized`, éprouvé par un outil témoin limité aux tests) →
registre et intégration seulement ensuite, si un besoin réel les justifie.

## Phase 10 — Circuit (historique : phase pilote close)

Circuit n'est plus une phase du produit : c'est un **module externe**
(piste D, dépôt ForgeDesign-Circuit) qui a servi de pilote au moteur générique.
Ce qui suit est l'historique de la phase pilote.

Périmètre normatif : Circuit — besoins et périmètre (FD-CIRCUIT-001), désormais
dans le module ForgeDesign-Circuit ([renvoi](circuit/README.md)). Circuit V1 est un éditeur de schémas électriques exacts ;
la simulation est une capacité optionnelle future, hors du premier jalon.

Sous-phase Graphics (FD-GRAPHICS-001) : avant de figer le format Circuit, le
[noyau graphique commun](graphics/graphics-core-contract.md) répartit les
responsabilités entre Graphics (géométrie, nœuds, ports, arêtes, routes,
routage, sélection, commandes, historique) et Circuit (sémantique électrique).
Il capitalise sur DrawCiel, suivi par une [procédure de référence](graphics/drawciel-reference.md)
appliquée à chaque ticket concerné. Les phases globales ne sont pas renumérotées.

**Changement de priorité (FD-GRAPHICS-002).** Forge Design porte l'analyse de
projet, Platform, le moteur graphique générique et l'infrastructure des modules
spécialisés ; il ne devient pas lui-même l'application métier (Circuit,
Network, Flowchart…), qui utilisera le moteur ensuite. Ordre désormais retenu :

```text
Graphics solide → preuve sur la plateforme → autres clients plateforme → modules spécialisés
```

```text
fait      FD-CIRCUIT-001   besoins et périmètre
fait      FD-GRAPHICS-001  contrat du noyau graphique commun, capitalisation DrawCiel
fait      FD-CIRCUIT-002   ressource Circuit V0.1 (forge_design.circuit, mvc/circuit/**/*.circuit.json)
fait      FD-CIRCUIT-003   domaine Circuit V1 (catalogue, topologie, validation), réalisé avant
                           le changement de priorité et conservé ; suite Circuit en attente
fait      FD-GRAPHICS-002  premier noyau graphique JS (scène, validation, renderer SVG,
                           sélection) ; Route Explorer premier client
fait      FD-GRAPHICS-003  Entity Explorer deuxième client ; API validée par deux clients,
                           seule extension : données opaques d'arête et edge(id)
fait      FD-GRAPHICS-004  viewport générique (fit, zoom, pan, home, resize) pour Route et
                           Entity ; première capacité interactive capitalisée de DrawCiel
fait      FD-GRAPHICS-005  allocation générique de couloirs partagée par Route et Entity
                           (Route : 19 → 9 couloirs, hauteur −18 %, 0 croisement ;
                           Entity : aucun gain possible à deux colonnes)
fait      FD-GRAPHICS-006  niveau de détail générique (overview, normal, detail) selon l'échelle ;
                           Route au fit en vue structurelle, Entity au fit en normal
fait      FD-GRAPHICS-007  minicarte générique et recentrage (centerAt), affichée seulement quand
                           la scène dépasse la zone ; mêmes mécanismes pour Route et Entity
fait      FD-GRAPHICS-008  Debug Center troisième client (flux séquentiel) ; moteur inchangé,
                           trois clients sur les mêmes modules
état      Graphics : socle de visualisation éprouvé (trois clients) ; édition graphique
                           pilotée par un module réel (Phase Modules) : déplacement de nœud
                           opt-in depuis FD-GRAPHICS-EDIT-001
extrait   Circuit hors du cœur (FD-MODULES-003) : dépôt ForgeDesign-Circuit ; les tickets
                           suivants sont des tickets du module :
fait      (module)         projection Circuit → scène en consultation (FD-MODULES-003)
          FD-CIRCUIT-004   commandes Circuit
          FD-CIRCUIT-005   intégration hôte, session, éditeur Web minimal
          FD-CIRCUIT-006   export SVG depuis le modèle
          FD-CIRCUIT-007   qualification du premier jalon en navigateur
          FD-CIRCUIT-008+  moteurs et IR de simulation, simulation DC, mesures
```

Le contenu prévu initialement pour FD-GRAPHICS-002 (primitives géométriques,
transformations exactes, ports) est reporté aux tickets Graphics suivants.
Le moteur de simulation n'est pas choisi avant une étude dédiée.

Premier jalon de la phase : créer, éditer, valider, enregistrer avec
révision, rouvrir à l'identique et exporter en SVG un schéma exact, sans
simulation.

## Phase Modules — modules spécialisés externes

Normatif : [Architecture des modules spécialisés](modules/module-architecture.md)
(FD-MODULES-001). Forge Design héberge des modules **externes**, installés,
compatibles et explicitement activés ; il ne contient aucune logique métier de
domaine. Direction des dépendances : module → cœur, jamais l'inverse. Toute
nouvelle capacité d'édition générique du Graphic Core est motivée par un besoin
réel d'un module.

```text
fait      FD-MODULES-001  frontière core / module, ModuleDescriptor et activation explicite
                          (forge_design.modules), plan de migration Circuit
fait      FD-MODULES-002  hôte Web des modules : --module PAQUET, routes GET exactes sous
                          /modules/<id>/, assets déclarés, zone « Modules », inventaire et
                          lecture par l'hôte, projection rendue par le Graphic Core
fait      FD-MODULES-003  extraction de Circuit dans ForgeDesign-Circuit (forge-design-circuit,
                          forge_design_circuit), provenance explicite, projection
                          CircuitDocument → GraphicScene dans le module, retrait du cœur
fait      FD-EDIT-001     actions bornées des modules : POST exact par action exposée, payload
                          formulaire borné, jeton de révision opaque, handler pur du module,
                          écriture et historique par le cœur ; témoin de test, aucune action
                          Circuit
fait      FD-GRAPHICS-EDIT-001  déplacement de nœud opt-in du Graphic Core (coordonnées monde,
                          seuil écran, aperçu des extrémités incidentes, Ctrl + Maj + flèches,
                          Échap / pointercancel) et script d'édition déclaré par un module,
                          chargé par le client générique de la page ressource
fait      FDC-EDIT-001    (module) premier geste réel : déplacer un composant Circuit
                          (move-component, capacité edit, une écriture par geste, routes
                          persistées inchangées)
fait      FD-GRAPHICS-EDIT-002  calques monde des clients (addOverlay : racine dédiée soumise
                          au viewport, survivant au rendu, retirée au destroy), notification
                          onViewChange (échelle, origine, zone, niveau de détail) et worldAt ;
                          aucun vocabulaire de domaine ; premier client : création de
                          connexions Circuit (FDC-EDIT-004, module)
fait      (module) FDC-EDIT-002 à 007 : routes après déplacement, sorties orientées,
                          connexions, dérivations fil → borne et fil → fil, évitement local
                          des composants ; aucun changement du cœur après FD-GRAPHICS-EDIT-002
fait      FD-ARCH-001     audit et consolidation des frontières : matrice normative, exports
                          publics figés, direction des dépendances, second domaine témoin
                          (flowchart-like) dans les tests, validation multi-modules avec
                          Circuit ; MODULE_API_VERSION reste 1
fait      FD-RELEASE-001  version 0.2.0 (source unique forge_design.__version__), politique
                          de version 0.x, requires_forge_design (PEP 440) vérifié à
                          l'activation, diagnostics core-version-incompatible / -unknown ;
                          Circuit déclare forge-design>=0.2.0,<1 ; MODULE_API_VERSION reste 1
fait      (module) FD-MODULE-PILOT-001 : second module pilote Flowchart, dépôt
                          ForgeDesign-Flowchart (0.1.0, forge-design>=0.2.0,<1), sans
                          changement du cœur
suivant   piste B ; Circuit et Flowchart poursuivent dans leurs dépôts
```

## Phase 11 — 3D

Ordre indicatif :

```text
besoins exacts
→ étude des moteurs
→ modèle de ressource
→ visualisation
→ transformations
→ assemblage
→ sauvegarde
→ export
```

Ne pas supposer qu'un modeleur 3D complet est nécessaire.

## Phase 12 — Intégration applicative

Définir comment une application Forge telle que SéquenCiel référence une ressource Forge Design sans dépendre des détails internes de l'outil graphique.

## Règles de tickets

Chaque ticket respecte :

- une responsabilité ;
- périmètre court ;
- tests adaptés ;
- documentation minimale ;
- pas de refactoring opportuniste ;
- pas d'écrasement utilisateur ;
- rapport final.

## Premier jalon mesurable

Le premier jalon est atteint lorsque :

```text
forge-design démarre
→ lance son serveur Web local sur loopback
→ reçoit un chemin projet
→ sécurise la racine
→ reconnaît un projet réellement généré par Forge supporté
→ lit sa version de manière traçable
→ Project Inspector produit un diagnostic en lecture seule
→ ce diagnostic est affichable dans le navigateur
→ les tests de compatibilité passent
```

Aucun Template Designer, Circuit, Network ou 3D n'est nécessaire pour atteindre ce jalon.
