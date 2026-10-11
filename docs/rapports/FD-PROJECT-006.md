# Rapport — FD-PROJECT-006

Synthèse de santé du projet Forge sélectionné dans Project Inspector. Date : 2026-10-11.

Ce ticket a été soumis sous le nom FD-PROJECT-005, identifiant déjà pris par `7c131bf` (« centraliser la sélection de projet ») et son rapport. Il a été renommé **FD-PROJECT-006** avec l'accord de l'utilisateur.

## Objectif

Faire de Project Inspector le point d'entrée du cockpit pour le projet Forge sélectionné. Une synthèse en lecture seule rassemble ce que Forge Design comprend déjà du projet, avec un état par domaine et un lien vers l'outil qui donne le détail.

Les neuf domaines couverts sont : Projet, Forge, Structure, Routes, Entités, Templates, Migrations, Diagnostics et Contrats de vue.

Ce que le ticket n'a pas fait :

- aucun nouveau Tool ;
- aucune écriture dans le projet ;
- aucun moteur graphique, aucun module ;
- aucune compatibilité Forge inventée ;
- aucun cache.

| Décision | Résultat |
|---|---|
| A. Nouveau Tool ? | Non : le registre contient toujours exactement les cinq Tools |
| B. Écriture dans le projet ? | Non : instantané identique avant et après, dans les tests et dans les navigateurs |
| C. Nouveau moteur graphique ? | Non : Graphic Core intact (0 diff, 134 tests Node) |
| D. Nouvelle abstraction module ? | Non |
| E. Project Inspector devient le cockpit de synthèse ? | Oui |

## État Git initial

| Élément | Valeur |
|---|---|
| HEAD | `8cf8203` (FD-RELEASE-001), contient FD-GRAPHICS-EDIT-002 (`44ded4b`) et FD-ARCH-001 (`3fcb51d`) |
| `origin/main` | `691e83e` ; `rev-list --left-right` : 0 en retard, 3 en avance |
| Version | `forge-design 0.2.0` |
| Arbre | Seul `docs/rapports/FD-CONTRACT-001.md` modifié, par l'utilisateur. Préservé, ni restauré ni commité |
| Modules | ForgeDesign-Circuit (`967b5b3`) et ForgeDesign-Flowchart (`a8ec22d`) non modifiés |

## Périmètre

Ce ticket relève de la piste B (outils propres à Forge). Il ne concerne ni le Graphic Core, ni les modules externes, ni le contrat spécialisé.

La synthèse s'affiche sur `/inspector`, sans nouvelle route. `project-inspector.run` est inchangé.

## Architecture

```text
GET /inspector · POST /inspector · POST /project/refresh
        │ (racine du CurrentProjectContext, jamais un chemin HTTP)
        ▼
web/inspector.py ── summarize_project_health(root, registry, inspection=…)
        │
        ▼ tools/project_health.py (Forge-specific, runtime, lecture seule)
   ToolRegistry ── project-inspector · route-explorer · entity-explorer
                   template-viewer · debug-center
   détection     ── detect_forge_project (entrées structurées)
   contrats      ── analyze_view_contract_links(root, templates=inventaire déjà lu)
   migrations    ── forge/migrations.py (inventaire des noms et tailles)
        │
        ▼
ProjectHealthSummary → inspector.html (HTML seul, sans JavaScript)
```

## Services existants réutilisés

| Domaine | Service | Appel |
|---|---|---|
| Projet, Forge | `inspect_project` | `registry.get("project-inspector").run` ; repris tel quel s'il vient d'être fait |
| Structure | `detect_forge_project` | Direct (nouvelles entrées structurées) |
| Routes | `read_routes` + `build_route_diagnostics` | `registry.get("route-explorer").run` |
| Entités | `read_entities` + `build_entity_diagnostics` | `registry.get("entity-explorer").run` |
| Templates | `read_templates` | `registry.get("template-viewer").run` |
| Diagnostics | `read_debug_errors` + `filter_debug_events` (ordre du Debug Center) | `registry.get("debug-center").run` |
| Contrats de vue | `analyze_view_contract_links` | Avec l'inventaire de Template Viewer |
| Cache | `no_store=True` du routeur Forge MVC | Inchangé pour `/inspector` |

Aucune seconde implémentation : les routes, les entités, les templates, le journal et les contrats ne sont jamais relus par une logique propre à la synthèse.

## Factorisations éventuelles

Les deux factorisations validées sont petites, locales et ne changent aucun comportement.

1. **`ForgeProjectDiagnostic.entries`** : un `StructureEntry(label, required, state)` par élément contrôlé, `state` valant `present`, `absent` ou `invalid`. `_check` rend désormais l'état et le message, au lieu du seul message. Les messages publics restent identiques au caractère près (test `test_structured_entries_match_the_messages`). La liste des dossiers optionnels est nommée (`OPTIONAL_MVC_DIRECTORIES`).
2. **`analyze_view_contract_links(root, templates=None)`** : l'inventaire de Template Viewer déjà lu est réutilisé ; sans lui, le comportement est inchangé. Le test vérifie un résultat identique et qu'aucun rebalayage n'a lieu.

Il y a aussi un petit lecteur nouveau, faute de lecteur existant : voir « Migrations ».

## Modèle de synthèse

`ProjectHealthSummary` est gelé et propre à Forge. Il est calculé à chaque affichage, jamais persisté, et n'est ni un contrat de module ni une ressource spécialisée. Ses champs :

- `root`, `name`, `status` ;
- `sections` : neuf `HealthSection` ;
- `inspection` : sert au détail de l'inspection ;
- `structure` : les entrées de structure.

Chaque `HealthSection` porte `key`, `title`, `status`, `summary` et `facts` (couples libellé–valeur), ainsi que `diagnostics` (cinq au plus), `diagnostic_total` et `action` (libellé et URL, ou rien). `HealthDiagnostic` porte `severity` (`error`, `warning` ou `info`), `message` et `subject`.

## Projet

La section donne le nom (dernier segment de la racine) et le dossier. Ce dossier est la même racine canonique que celle que le shell affiche déjà (« Projet : … ») : aucune information système supplémentaire. L'état de sélection est dit dans le résumé.

## Forge

La section indique si le projet est reconnu, la version détectée et sa source. La compatibilité Forge Design est affichée « non évaluée (aucune règle de version définie) », puisque `04-compatibilite-forge.md` ne donne encore aucune matrice.

Une version indéterminée vaut « attention », avec les avertissements de version de l'inspection. Ces avertissements sont séparés de ceux de la structure **par position** : `inspect_project` les ajoute après ceux de la détection. Aucun texte n'est interprété.

## Structure

La section donne les éléments requis trouvés (`n / 5`), les dossiers optionnels trouvés et le nombre d'anomalies. Sévérités :

- élément requis absent ou invalide : erreur ;
- dossier optionnel invalide (lien ou type) : avertissement ;
- dossier optionnel absent : simple information.

## Routes

La section donne le nombre de routes, les méthodes HTTP rencontrées, les routes sans et avec diagnostic (indices `route_indices` des diagnostics), les comptages par sévérité et le lien « Voir les routes ».

Les sévérités sont celles de `build_route_diagnostics`, avec une exception. `RoutesResult.warnings[0]` est **toujours** la mise en garde « Lecture statique… La liste peut être partielle » : `_parse` la place en tête, et `read_routes` la retire lui-même des branchements avec `[1:]`. À elle seule, elle déclencherait `route.partial` en avertissement sur tout projet, et aucun projet ne pourrait être « OK ». Dans la synthèse, `route.partial` devient donc une information quand cette mise en garde est la seule entrée de `warnings`. C'est une décision sur la position, pas sur le texte, et Route Explorer reste inchangé. Une vraie limite, par exemple un branchement non résolu, reste un avertissement (test et mutation).

## Entités

La section donne les entités, les relations, les erreurs et les avertissements, selon les sévérités de `build_entity_diagnostics`. Le code `entity.source_missing` (dossier optionnel `mvc/entities` absent) est ramené à une information, conformément à la règle « optionnel absent ». C'est une décision sur un code stable, pas sur un message. Lien « Voir les entités ».

## Templates

La section donne les fichiers détectés par Template Viewer (inventaire identique), les templates de vue, les métadonnées (`.view.json`, `.design.json`) et l'état de l'inventaire, complet ou partiel. Toute anomalie de l'inventaire vaut « attention », faute de sévérité existante. `mvc/views` absent est une information. Lien « Voir les templates ».

La synthèse ne parse pas chaque template, ce qui demanderait de lire tout le contenu. L'analyse syntaxique reste dans Template Viewer et Route Explorer.

## Migrations

Forge Design n'avait aucun lecteur de migrations. La convention Forge (`mvc/migrations/AAAAMMJJHHMMSS_nom.sql`) est vérifiée côté Forge par le diagnostic de son outil en ligne de commande. Ce module n'est pas importable : la règle de frontière 2 n'autorise que les paquets `core` et `integrations`, et il lit les fichiers sans les protections de Forge Design.

Le nouveau `forge_design/forge/migrations.py` vit dans la zone Forge-specific existante, sans nouveau paquet. Il fait :

- un inventaire direct, sans récursion, par descripteurs ancrés ;
- aucun lien suivi ;
- un plafond de 4 096 entrées (`MAX_MIGRATION_DIRECTORY_ENTRIES`) ;
- seulement les fichiers `.sql` ;
- un contrôle du nom par la convention ;
- un contrôle de taille, par métadonnée, pour repérer un fichier vide.

Il n'ouvre jamais un fichier `.sql` (test sur un fichier en mode 000 et sur `os.open`), n'interprète rien, n'exécute rien et n'importe pas `cli.project.doctor`. Toute anomalie vaut « attention ». Le dossier absent est une information. Pas de lien, puisqu'aucun outil de migrations n'existe.

## Diagnostics

La section reprend le journal du Debug Center :

- comptes ERROR et CRITICAL, WARNING, INFO ;
- anomalies de lecture ;
- premiers événements dans l'ordre du filtre par défaut du Debug Center ;
- lien « Voir les diagnostics ».

Les événements ERROR et CRITICAL sont des erreurs **passées** du runtime. Ils donnent « attention », jamais « erreur » : le cockpit ne confond pas une ancienne exception avec une corruption actuelle du projet. Les diagnostics propres à Project Inspector sont dans les sections Forge et Structure.

## Contrats de vue

La section donne le nombre de contrats, les valides, les invalides, les templates associés ou sans contrat et l'état de la liaison. Un contrat invalide est compté comme invalide, sans devenir bloquant : toute anomalie de contrat ou de liaison vaut « attention ». Le lien mène à Template Viewer. Aucun contrat n'est modifié.

## Statuts de santé

| État | Marque | Signification |
|---|---|---|
| `ok` | ✓ OK | Analyse disponible, aucun avertissement |
| `attention` | ! Attention | Avertissement connu, ou section indisponible |
| `erreur` | ✕ Erreur | Diagnostic d'erreur connu |
| `indisponible` | – Indisponible | Analyse impossible |

Chaque état est rendu en texte, avec une marque (`aria-hidden`) et un style. La couleur seule ne porte jamais l'information. Aucun score.

## Agrégation globale

La règle validée, dans l'ordre :

1. **erreur** si une section est en erreur ;
2. sinon **indisponible** si le projet lui-même n'est plus analysable (racine introuvable ou remplacée) ;
3. sinon **attention** si une section est en attention ou indisponible : une section secondaire indisponible ne rend pas le projet indisponible ;
4. sinon **ok**.

Un projet devenu non reconnu (fichier requis supprimé) donne Structure et Forge en erreur et les autres domaines indisponibles, d'où un état global « erreur ».

## Résultats partiels

Chaque section ne capture **que** les erreurs de domaine que la page de son outil traite déjà :

- racine introuvable, pas un dossier ou non résoluble ;
- `NotForgeProjectError` ;
- pour les routes, en plus, `RoutesSourceMissingError` et `RoutesSourceUnreadableError`.

La section devient alors « indisponible » avec le message de l'erreur, et le reste est présenté (test : Entity Explorer refusé, huit sections OK, global « attention »). Il n'y a pas de `except Exception` : une erreur inattendue remonte en 500, et un résultat de Tool du mauvais type lève `TypeError`, comme sur les pages des outils (tests et mutation « bug masqué »).

## Navigation

| Section | Lien |
|---|---|
| Forge, Structure | « Voir le détail de l’inspection » → `/inspector#inspection-details` |
| Routes | « Voir les routes » → `/routes` |
| Entités | « Voir les entités » → `/entities` |
| Templates | « Voir les templates » → `/templates` |
| Contrats de vue | « Voir les templates et leurs contrats » → `/templates` |
| Diagnostics | « Voir les diagnostics » → `/debug` |
| Projet, Migrations | Aucun |

Le détail de l'inspection, déjà présent sur la page, porte maintenant l'ancre `inspection-details`. Au GET, il montre l'inspection fraîche de la synthèse.

## Projet absent

Sans projet sélectionné, aucune analyse n'est faite : « Aucun projet sélectionné : aucune analyse. » La page invite à saisir un chemin (formulaire, désormais sous un titre « Ouvrir un projet ») ou propose un lien vers l'accueil pour les projets récents. Une ouverture refusée, sans projet courant, n'analyse rien non plus (test et mutation).

## Projet inaccessible

Si le dossier est supprimé ou remplacé par un fichier, les neuf sections deviennent indisponibles, avec « Projet inaccessible : … », et l'état global vaut « indisponible ». La réponse reste 200, sans trace d'exception.

Le GET ne ferme pas le projet : il est en lecture seule. Seul « Actualiser » ferme un projet, comme avant. Si le projet n'est plus reconnu, la synthèse le montre en erreur (voir « Agrégation globale »).

## Sécurité filesystem

Toutes les lectures passent par les lecteurs existants et leurs protections : descripteurs ancrés `openat`/`dir_fd`, `O_NOFOLLOW`, `samestat`, lectures bornées. La racine vient toujours du `CurrentProjectContext`, jamais d'un paramètre HTTP. Le nouveau lecteur de migrations suit le même modèle que l'inventaire des templates.

Aucun `Path.read_text`, `open()` ou lien suivi n'est ajouté dans le code livré. Le test d'instantané vérifie qu'aucun fichier n'est modifié ni créé, pas même `.forge-design/`.

## Cache

Il n'y a ni cache ni persistance : la synthèse est recalculée à chaque affichage (test : une nouvelle anomalie apparaît au calcul suivant). `/inspector` garde `Cache-Control: no-store` (tests HTTP et mutation).

## Performance

La mesure porte sur la vraie synthèse, avec une instrumentation non intrusive : les enveloppes sont enregistrées dans `os.supports_dir_fd`, et les états mesurés sont égaux à ceux d'une passe sans instrumentation. Projets :

- petit : squelette, une route ;
- moyen : `gx8-browser` avec 10 contrats et 20 migrations ;
- maximal raisonnable : 200 routes, 250 templates et 250 contrats, 250 entités, 2 000 événements de journal, 500 migrations.

| Mesure | Petit | Moyen | Maximal |
|---|---|---|---|
| Fichiers du projet | 7 | 54 | 1 257 |
| Synthèse, médiane sur 7 passes | 5,4 ms (min 3,4) | 12,1 ms | 241,8 ms |
| `inspect_project`, `read_routes`, `read_entities`, `read_templates`, `read_debug_errors`, `read_migrations`, `read_view_contracts`, `analyze_view_contract_links` | **1 appel chacun** | **1 chacun** | **1 chacun** |
| `read_templates` par l'analyse des contrats | 0 | 0 | 0 |
| `read_view_contract` (un par contrat) | 0 | 10 | 250 |
| `detect_forge_project` | 8 | 18 | 258 |
| `os.scandir` (dossiers listés) | 2 | 14 | 4 |
| `os.open` (descripteurs) | 52 | 234 | 6 932 |
| `os.stat` | 142 | 419 | 7 248 |

**Lectures répétées évitées.** L'inventaire de `mvc/views` est lu une seule fois. Sans réutilisation, l'analyse des contrats aurait refait un `read_templates` complet par affichage :

| Projet | Coût évité |
|---|---|
| Petit | 1 dossier listé, 11 descripteurs, 16 `stat`, 0,4 ms |
| Moyen | 6 dossiers listés, 33 descripteurs, 38 `stat`, 0,7 ms |
| Maximal | 1 dossier listé, 510 descripteurs, 515 `stat`, 6,1 ms |

Après une ouverture ou une actualisation, l'inspection qui vient d'être faite est reprise : un seul `project-inspector.run` par action, invariant du test existant `test_registry_delegation_and_escaping`.

**Coût restant.**

- `detect_forge_project` est appelé une fois par lecteur. C'est un contrôle de structure, pas un balayage : douze `lstat`.
- Il est aussi appelé une fois par contrat, dans `read_view_contract`. C'est le coût de l'analyse des contrats existante, d'où 258 appels sur le projet maximal.
- Les descripteurs ouverts viennent surtout de Route Explorer, qui vérifie la présence et la syntaxe des templates de chaque route.

Rien n'a été optimisé au-delà, ni cache, ni partage de détection (§93).

## Tests Python

**56 tests ajoutés** :

| Fichier | Tests | Contenu |
|---|---|---|
| `tests/test_project_health.py` | 30 | Projet sain (tout OK), minimal, routes avec erreurs et avertissements, vraies limites des routes, entités, templates et contrats, migrations, journal (attention, jamais erreur), aperçu borné, optionnel invalide, version indéterminée, projet non reconnu ou inaccessible, agrégation (7 cas), section indisponible, bug non masqué, mauvais type, réutilisation par le registre espionné, inspection reprise, navigation, cinq Tools, lecture seule, recalcul |
| `tests/test_web_project_health.py` | 8 | HTTP réel : sans projet, ouverture refusée, synthèse au POST et au GET identique, `no-store`, hiérarchie h1/h2/h3, états écrits et marqués, liens, aperçu borné, projet devenu inaccessible, section indisponible, bug → 500, page identique avec modules |
| `tests/test_migrations.py` | 15 | Dossier absent ou vide, inventaire, convention (6 cas), liens et entrées non ordinaires, dossier lié, aucun `.sql` ouvert, borne, erreurs de racine, aucune écriture |
| `tests/test_project_detection.py` | +2 | Entrées structurées et messages inchangés ; arrêt quand `mvc` est invalide |
| `tests/test_view_contract_linkage.py` | +1 | Inventaire réutilisé, résultat identique, aucun rebalayage |

**Tests existants adaptés (8 fichiers).** L'ouverture d'un projet affiche désormais la synthèse, qui lit chaque domaine une fois.

- Sept fichiers espionnaient un outil et comptaient ses appels à partir de l'ouverture : `test_web_debug`, `_debug_filters`, `_debug_flow`, `_entity_diagnostics`, `_entity_filters`, `_entity_graph` et `_templates`. Ils vérifient maintenant que cette ouverture lit le domaine **une** fois, puis vident le compteur. Les assertions des pages elles-mêmes sont inchangées.
- Dans `test_web_inspector`, deux tests de Route Explorer comptent ou interdisent les lectures après l'ouverture. Un troisième cherchait « mvc/views » dans toute la page ; il cherche maintenant le message exact « mvc/views : absent. ».

**Mutations : 35/35 tuées**, sources restaurées à l'identique (empreinte vérifiée).

- Les huit exigées par le §91 :
  1. domaine ignoré ;
  2. avertissement transformé en erreur ;
  3. erreur transformée en ok ;
  4. section indisponible qui fait tomber la page ;
  5. lien vers le mauvais Tool ;
  6. sixième Tool dans le registre ;
  7. `no-store` supprimé ;
  8. projet non sélectionné analysé.
- Sévérités : journal mis « en erreur », optionnel absent, `mvc/entities`, mise en garde des routes dans les deux sens, contrats.
- Agrégation : section secondaire indisponible, projet inaccessible.
- Isolation : `except Exception`, type non vérifié, inspection d'une autre racine, avertissements de structure recopiés.
- Lectures partagées : rebalayage des contrats dans les deux sens, aperçu non borné.
- Migrations : convention, fichier vide, lien suivi, non `.sql`, borne, dossier absent.
- Structure et affichage : optionnel marqué requis, état invalide, état sans texte, ancre absente.

Une seule a d'abord survécu : « vraies limites des routes = information ». Elle est tuée par `test_real_route_limits_stay_warnings`.

## Chromium

La vraie commande `forge-design --no-browser` est lancée depuis la roue 0.2.0, dans un venv neuf, avec un HOME isolé. Le projet de fixture est `gx8-browser`, enrichi d'un contrat valide, d'un contrat invalide et de trois migrations dont une mal nommée. Résultat : **11/11** :

- sans projet, aucune analyse ;
- sélection par le formulaire ;
- les neuf sections, leurs états écrits, leurs comptages, le nombre de diagnostics visibles et leurs liens sont **identiques** au service Python ;
- état global « ✕ Erreur » (une route vers un template manquant) ;
- liens vers Route Explorer, Entity Explorer, Debug Center et Template Viewer, chacun avec retour (`history.back`) ;
- clavier : Tab jusqu'à « Voir les routes », puis Entrée ;
- ancre du détail de l'inspection ;
- aucun fichier modifié ;
- aucune exception ni violation CSP.

Le seul 404 réseau est `/favicon.ico`, comportement existant.

Constat sans lien avec le ticket : la page résultat du POST de sélection n'est pas rejouée par « Précédent », puisqu'elle est servie en `no-store`. La navigation part donc d'un GET `/inspector`.

## Firefox

Même scénario par WebDriver BiDi : **11/11**.

## Sans JavaScript

| Navigateur | Mode | Résultat |
|---|---|---|
| Chromium | Scripts désactivés | 9 sections, état global, 7 liens, détail de l'inspection ; un lien suivi sans script ouvre Route Explorer |
| Firefox | `javascript.enabled = false` | 9 sections, 7 liens, état global, détail ; Debug Center ouvert sans script |

La page ne contient aucun `<script>` propre à la synthèse.

## ToolRegistry

Le registre reste exactement `project-inspector`, `route-explorer`, `entity-explorer`, `debug-center` et `template-viewer`. C'est vérifié par trois tests : `test_tool_registry_keeps_exactly_five_tools`, `test_module_boundaries.py::test_modules_never_become_tools` (registre réellement composé par le serveur) et la mutation « sixième Tool ».

## Dogfooding Forge MVC

La page reste un handler Forge MVC : `Router`, `Request`, `Response`, rendu Jinja par `render_page`, route `GET /inspector` existante avec `no_store=True`. Il n'y a ni HTMX, ni JavaScript, ni Graphic Core, ni infrastructure parallèle. Le CSS ajoute une dizaine de règles `health-*` dans `shell.css`, avec la palette existante.

**Modules activés (vérification légère).** La vraie commande est lancée avec `--module forge_design_circuit --module forge_design_flowchart` (zone Modules présente). La synthèse est identique octet pour octet à celle obtenue sans modules (comparaison du HTML), et le scénario Chromium complet passe 11/11.

## Fichiers créés

- `forge_design/tools/project_health.py` : service et modèle de synthèse
- `forge_design/forge/migrations.py` : inventaire des migrations
- `tests/test_project_health.py`, `tests/test_web_project_health.py`, `tests/test_migrations.py`
- `docs/tools/project-inspector.md`
- `docs/rapports/FD-PROJECT-006.md`

## Fichiers modifiés

- `forge_design/forge/project_detection.py` : entrées structurées
- `forge_design/contracts/linkage.py` : paramètre `templates`
- `forge_design/limits.py` : `MAX_MIGRATION_DIRECTORY_ENTRIES`, `MAX_HEALTH_VISIBLE_DIAGNOSTICS = 5`
- `forge_design/web/inspector.py`, `forge_design/web/server.py` : registre transmis au GET
- `forge_design/web/templates/inspector.html` : synthèse, titre « Ouvrir un projet », ancre du détail
- `forge_design/web/static/shell.css` : règles `health-*`
- `docs/03-roadmap.md` : ligne de la piste B
- Tests existants adaptés (voir « Tests Python ») : `test_project_detection`, `test_view_contract_linkage`, `test_web_inspector` et les sept tests web cités

## Validation finale

| Commande | Résultat |
|---|---|
| `python -m compileall -q forge_design` | OK |
| `ruff check forge_design tests` | All checks passed |
| `ruff format --check .` | Tout formaté |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Propre |
| `pytest` (suite complète) | Voir « État Git final » : relancée après les docs |
| Graphic Core (`node --test tests/js/graphics/*.test.mjs`) | 134/134 |
| Mutations | 35/35 |
| Roue `forge-design 0.2.0`, venv neuf (avec Circuit et Flowchart) | `pip check` OK ; `project_health.py`, `migrations.py` et `inspector.html` présents dans la roue |
| Chromium, Firefox (vraie commande) | 11/11 chacun ; avec modules : 11/11 |
| Sans JavaScript (Chromium, Firefox) | OK |

## État Git final

| Dépôt | État |
|---|---|
| Forge Design | `main`, un commit `feat: synthétiser la santé du projet Forge (FD-PROJECT-006)` au-dessus de `8cf8203`. `docs/rapports/FD-CONTRACT-001.md` toujours modifié, hors commit. Aucun push |
| ForgeDesign-Circuit, ForgeDesign-Flowchart | Non modifiés |

Suite complète relancée après la documentation, avant le commit : **4 687 tests verts**.
