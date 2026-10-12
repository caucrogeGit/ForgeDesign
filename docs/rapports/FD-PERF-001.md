# Rapport — FD-PERF-001

Partager la vérification de la racine Forge dans l'analyse des contrats de vue. Date : 2026-10-12.

## Objectif

Supprimer les redétections répétées du même projet Forge pendant une analyse des contrats de vue, sans changer aucun résultat fonctionnel. Le gain doit venir de la **suppression d'un travail redondant**, et non d'un cache global, d'un affaiblissement des contrôles de sécurité ou d'un changement des règles métier.

| Décision | Résultat |
|---|---|
| A. Nouveau comportement fonctionnel ? | Non : résultats, diagnostics et fragments HTML identiques |
| B. Cache persistant ? | Non : un objet par appel, aucun état global |
| C. Nouveau Tool ? | Non : cinq Tools |
| D. Nouveau contrat module ? | Non |
| E. Graphic Core modifié ? | Non : 0 diff, 134 tests Node |
| F. Résultats des contrats changés ? | Non |
| G. Détection Forge partagée ? | Oui : **251 → 1** par analyse |

## État Git initial

| Élément | Valeur |
|---|---|
| HEAD | `87adc58` (FD-ROUTES-021), contient FD-PROJECT-006 (`e411d0c`) |
| `origin/main` | `e411d0c` ; 0 en retard, 1 en avance |
| Version | `forge-design 0.2.0`, inchangée : ni publication ni tag |
| Arbre | Seul `docs/rapports/FD-CONTRACT-001.md` modifié par l'utilisateur, préservé et hors commit |
| Modules | ForgeDesign-Circuit et ForgeDesign-Flowchart non modifiés |

## Défaut mesuré

Mesure de FD-ROUTES-021 sur le projet maximal (200 routes, 250 templates, 250 contrats) : `GET /routes` prenait environ 270 ms, dont environ 124 ms pour `analyze_view_contract_links`.

Le profil de l'analyse, avec l'inventaire des templates déjà fourni, montre où va le temps :

| Poste | Appels | Part du temps profilé |
|---|---|---|
| `_root` du lecteur de contrats (résolution + détection) | 251 | ~54 % |
| dont `detect_forge_project` | 251, soit environ 3 000 `lstat` | ~45 % |
| `resolve_project_root` | 503 | inclus |
| Lectures sécurisées (250 contrats et 250 cibles) | 500 ouvertures ancrées | ~20 % |
| Validation Pydantic | 250 | Négligeable |

## Périmètre

Ce ticket relève de la piste B, au niveau des contrats de vue. Il ne touche ni le Graphic Core, ni l'hôte des modules ou des ressources, ni les modules externes. `web/routes.py` et `tools/project_health.py` restent **inchangés** : tout est encapsulé dans les contrats.

## Architecture avant

```text
analyze_view_contract_links(root, templates)
 ├─ resolve_project_root(root)                         (sans détection)
 ├─ read_templates(root)          → _root : résolution + détection   (sans inventaire fourni)
 ├─ read_view_contracts(root)     → _root : résolution + détection
 └─ pour chaque contrat :
      read_view_contract(root, p) → _root : résolution + détection   ← ×250
                                  → ouverture confinée du fichier
      inspect_project_source(…)   → ouverture confinée de la cible
```

## Appels répétés

| Où la racine est validée | Quand |
|---|---|
| `contracts/reader.py::_root` | Une fois par `read_view_contracts`, **une fois par `read_view_contract`** |
| `forge/templates.py::_root` | Une fois par `read_templates` |
| `contracts/linkage.py` | `resolve_project_root` seul |

La donnée recalculée sans raison est la racine canonique d'un projet reconnu, qui ne change pas pendant l'opération. Ce qui n'était **pas** répété à tort : l'ouverture sécurisée de chaque fichier (`_open_project_source`), qui protège le fichier lu, pas le projet. Elle reste individuelle.

## Solution retenue

```text
analyze_view_contract_links(root, templates)       (signature publique inchangée)
 ├─ checked = check_forge_root(root)                  ← résolution + détection, une fois
 ├─ read_templates(root, checked=checked)           (sans inventaire fourni)
 ├─ read_view_contracts(root, checked=checked)
 └─ pour chaque contrat :
      read_view_contract(root, p, checked=checked)  → garde root == checked.root
                                                    → ouverture confinée du fichier (inchangée)
      inspect_project_source(…)                     (inchangé)
```

## Contexte Forge partagé

`forge_design/forge/checked_root.py`, dans la zone propre à Forge (module séparé pour éviter les imports circulaires) :

- `CheckedForgeRoot(root: Path)` : objet gelé, racine canonique d'un projet reconnu ;
- `check_forge_root(root)` : résolution et détection, avec **les mêmes exceptions et les mêmes messages** que les lecteurs ;
- `checked_root(root, checked)` : le `_root` des lecteurs. Sans contexte, il fait la vérification complète comme avant ; avec un contexte, il n'applique que la garde stricte.

Le nom évite le trop général `AnalysisContext` : l'objet ne porte que la preuve d'une racine Forge vérifiée. Ce n'est ni un `CurrentProjectContext`, ni un cache, ni un singleton, ni une ressource, ni un contrat de module.

## Cycle de vie

L'objet est créé au début d'un appel à `analyze_view_contract_links` et disparaît à sa fin. Il n'y a ni thread local, ni variable de module, ni `lru_cache`, ni mémoïsation par chemin. Deux affichages successifs font chacun leur propre vérification.

## Garde root/context

`CheckedForgeRoot.require(root)` exige `Path(root) == checked.root`, sans nouvelle résolution. Sinon, `ValueError("Racine Forge vérifiée pour une autre racine.")` est levée.

Un contexte créé pour `/A` est donc refusé pour `/B`, et aussi pour une forme non canonique de `/A` (`/A/mvc/..`). Le test couvre les trois lecteurs, et la mutation « mismatch accepté » est tuée.

## Sécurité filesystem

Aucune protection n'est retirée. Chaque contrat lu et chaque cible inspectée passe toujours par `_open_project_source` : racine et parents ancrés par descripteur, `O_NOFOLLOW`, `S_ISREG`, `samestat`, lecture bornée à 1 Mio. L'inventaire garde ses `dir_fd`, `fstat` et `samestat`. Preuves :

- le nombre d'`os.open` est **strictement identique** avant et après (5 760 sur le projet maximal) ;
- un contrat lien symbolique reste refusé (`contract.unreadable`), avec ou sans contexte ;
- la mutation « sécurité fichier relâchée » (`follow_symlinks` et `O_NOFOLLOW` retirés) est tuée.

Il n'y a ni `Path.read_text` ni nouvel `open()`.

**Contexte périmé.** Le contexte ne promet aucun instantané. Une seule différence existe, et seulement sous modification concurrente. Si un fichier requis du projet est supprimé **pendant** l'analyse, les contrats suivants ne relèvent plus `NotForgeProjectError` au milieu de l'analyse. Chaque fichier lu reste néanmoins contrôlé individuellement. Il n'y a ni transaction ni verrou de projet.

## Compatibilité des API existantes

| API | Changement |
|---|---|
| `analyze_view_contract_links(root, templates=None)` | Aucun dans la signature ; partage interne |
| `read_view_contracts(root, *, checked=None)` | Paramètre nommé ajouté ; sans lui, comportement identique |
| `read_view_contract(root, contract_path, *, checked=None)` | Idem ; l'appel historique `read_view_contract(root, path)` reste valide |
| `read_templates(root, *, checked=None)` | Idem (validé) ; Template Viewer l'appelle toujours sans contexte |

Le test de contrat public de Template Viewer (`test_public_contracts`) inscrit désormais `("root", "checked")` et vérifie que `checked` est nommé seulement, avec `None` par défaut.

## Analyse des contrats

Les résultats sont identiques. Le test compare l'analyse partagée au chemin historique, où chaque lecteur est appelé sans contexte, avec et sans inventaire fourni, sur un projet comportant :

- un contrat valide ;
- un contrat JSON invalide ;
- un contrat de schéma invalide (3 diagnostics) ;
- un template sans contrat ;
- un template visé par deux contrats.

L'ordre des diagnostics est vérifié en absolu par rapport au lecteur appelé seul : même ordre de chargement, mêmes `location`.

## Route Explorer

Pas une ligne de `web/routes.py` n'a changé. Les tests de FD-ROUTES-021 passent sans adaptation fonctionnelle. Le rapport de liaison (`RouteLinkage`, `ContractsOverview`, `LinkedDiagnostic`, états de chaîne) de la fixture FD-ROUTES-021 est identique avec et sans partage (test `test_route_linkage_and_cockpit_unchanged`).

## Project Inspector

Pas une ligne de `project_health.py` n'a changé. La section « Contrats de vue » de la synthèse est identique (même test), et tous les tests de FD-PROJECT-006 passent.

## Template Viewer

La page n'utilise pas l'analyse des contrats. Son lecteur `read_templates` est appelé sans contexte, donc à l'identique. Elle n'est pas mesurée (§65). Le fragment HTML de la page est identique, hors horodatages des fichiers recréés.

## Résultats fonctionnels avant/après

Les fragments HTML ont été comparés sur un serveur réel, entre `87adc58` (worktree temporaire) et le nouveau code, sur la fixture de FD-ROUTES-021 :

| Fragment | Identique |
|---|---|
| `/routes` : chaînes et contrats (15 141 caractères) | Oui |
| `/routes` : diagnostics | Oui |
| `/inspector` : section Contrats de vue | Oui |
| `/inspector` : section Templates | Oui |
| `/templates` | Oui, hors horodatages des fichiers (`data-modified-ns` et date affichée) |

Sur le projet maximal, l'empreinte de `ViewContractLinksResult` et celle de la section des chaînes de `GET /routes` sont identiques avant et après.

## Performance Route Explorer

Projet maximal, vraie application, médiane de 7 passes, même machine, avant (`87adc58`) puis après :

| Mesure | Avant | Après |
|---|---|---|
| `GET /routes` | 268,3 ms | **213,5 ms** (−20 %) |
| `analyze_view_contract_links`, avec inventaire | 118,2 ms | **59,2 ms** (−50 %) |
| `analyze_view_contract_links`, sans inventaire | 130,6 ms | **70,9 ms** (−46 %) |

## Performance Project Inspector

| Mesure (projet maximal) | Avant | Après |
|---|---|---|
| Synthèse de santé | 237,3 ms | **179,9 ms** (−24 %) |

## Nombre d'appels avant/après

| Appel | Analyse (avec inventaire) | Analyse (sans inventaire) | `GET /routes` | Synthèse du cockpit |
|---|---|---|---|---|
| `detect_forge_project` | 251 → **1** | 252 → **1** | 253 → **3** | 258 → **8** |
| `resolve_project_root` | 251 → **1** | 252 → **1** | 253 → **3** | 257 → **7** |
| `read_view_contract` | 250 → 250 | 250 → 250 | 250 → 250 | 250 → 250 |
| `read_view_contracts` | 1 → 1 | 1 → 1 | 1 → 1 | 1 → 1 |
| `read_templates` | — | 1 → 1 | 1 → 1 (Template Viewer) | 1 → 1 |
| `read_routes` | — | — | 1 → 1 | 1 → 1 |
| `os.open` | 5 760 → **5 760** | 6 270 → 6 270 | 6 400 → 6 400 | 6 932 → 6 932 |
| `os.stat` | 4 516 → 1 015 | 5 031 → 1 516 | 6 163 → 2 662 | 7 248 → 3 747 |

Les détections restantes de `GET /routes` et du cockpit viennent des autres lecteurs (routes, inventaire de Template Viewer, entités, journal, migrations, inspection) : une par lecteur et par affichage, hors du périmètre (§66).

## Tests Python

**9 tests** dans `tests/test_view_contract_context.py` :

- racine vérifiée canonique et gelée ;
- mêmes erreurs que les lecteurs (racine inexistante, projet non Forge, mêmes messages) ;
- contexte d'une autre racine refusé, pour les trois lecteurs et pour une forme non canonique ;
- lecteurs identiques avec et sans contexte : inventaire, templates, contrat valide, JSON invalide, schéma invalide, contrat partagé ;
- analyse identique au chemin historique, avec et sans inventaire, ordre absolu des diagnostics compris ;
- liaison de FD-ROUTES-021 et section Contrats du cockpit identiques ;
- **une détection pour 250 contrats**, contre 1 + 1 + 254 sur le chemin historique ;
- ouverture confinée de chaque contrat, et lien symbolique toujours refusé.

**Tests existants adaptés, sans changement fonctionnel :**

- dans `test_view_contract_linkage.py`, cinq doubles de test remplacent les lecteurs ; ils acceptent et transmettent maintenant l'argument `checked=` ;
- dans `test_template_viewer_stabilization.py`, la signature publique de `read_templates` inclut `checked`.

**Suite complète : 4 727 tests verts** (4 718 + 9).

## Mutations

**10/10 tuées**, sources restaurées à l'identique (empreinte vérifiée) :

1. contexte ignoré par l'analyse ;
2. détection refaite pour chaque contrat dans le lecteur ;
3. inventaire lu sans la racine vérifiée ;
4. mismatch racine ↔ contexte accepté ;
5. validation Forge supprimée ;
6. racine non canonique ;
7. résultat différent avec contexte ;
8. contrat invalide perdu ;
9. ordre des diagnostics changé ;
10. sécurité fichier relâchée (`follow_symlinks` et `O_NOFOLLOW`).

Aucune mutation ne porte sur un temps : chacune vérifie un comportement structurel.

## Chromium

La vraie commande est lancée depuis la roue 0.2.0, dans un venv neuf, sur la fixture de FD-ROUTES-021. Résultat : **12/12** :

- sélection du projet, puis Route Explorer ;
- chaîne complète avec son contrat valide ;
- contrôleur absent, template dynamique, plusieurs templates ;
- contrat invalide présent seulement dans la section globale ;
- lien Template Viewer, puis retour ;
- clavier ;
- Project Inspector → « Voir les routes » ;
- **section Contrats de vue du cockpit** : Contrats 4, Valides 3, Invalides 1, Templates associés 1, sans contrat 2, liaison complète, état « attention » ;
- lecture seule ;
- aucune erreur.

## Firefox

Même scénario : **12/12**. L'activation clavier du `<summary>` reste non vérifiable en headless (limite déjà notée dans FD-ROUTES-021).

## Sans JavaScript

| Navigateur | Résultat |
|---|---|
| Chromium | 12 chaînes, détails, diagnostics et contrats lisibles |
| Firefox | 12 chaînes, 12 détails, section Contrats, 3 chaînes problématiques |

Le résultat est identique à FD-ROUTES-021.

## ToolRegistry

Le registre reste `project-inspector`, `route-explorer`, `entity-explorer`, `debug-center` et `template-viewer`, vérifié par les tests existants de FD-ROUTES-021, FD-PROJECT-006 et `test_module_boundaries`.

## Graphic Core

Aucune modification : 134 tests Node sur 134 passent.

**Modules (vérification légère).** La vraie commande est lancée avec Circuit et Flowchart, et le scénario Chromium passe 12/12.

## Dette / limites

- **Détection restante.** Elle a lieu une fois par lecteur et par affichage, dans les autres lecteurs (routes, Template Viewer, entités, journal, migrations) : 3 pour `GET /routes`, 8 pour le cockpit. C'est raisonnable et hors périmètre. Elle peut se partager de la même façon si une mesure le justifie un jour.
- **Ouvertures confinées.** Chaque ouverture réancre toujours la racine et ses parents (environ 23 `os.open` par contrat). C'est la protection voulue par fichier ; elle n'a pas été touchée.
- **Pas de snapshot.** Une modification concurrente de la structure du projet pendant l'analyse n'interrompt plus les contrats suivants. Ce comportement est documenté.
- **Taille de page.** Le rendu de 200 chaînes reste le premier coût de `GET /routes` après la lecture des routes.

## Recommandation ticket suivant

1. Reprendre la Phase 5 (diagnostics Forge exécutés), Route Explorer et Project Inspector servant de vues de détail et de synthèse pour ses résultats.
2. Si de grands projets le demandent, une pagination ou un repli des chaînes de Route Explorer (rendu), plutôt qu'une nouvelle optimisation de lecture.

## Fichiers créés

- `forge_design/forge/checked_root.py`
- `tests/test_view_contract_context.py`
- `docs/rapports/FD-PERF-001.md`

## Fichiers modifiés

- `forge_design/contracts/reader.py` : `checked=` sur `read_view_contracts` et `read_view_contract`, `_root` partagé
- `forge_design/contracts/linkage.py` : racine vérifiée une fois et transmise
- `forge_design/forge/templates.py` : `checked=` sur `read_templates`
- `tests/test_view_contract_linkage.py` : doubles acceptant `checked=`
- `tests/test_template_viewer_stabilization.py` : signature publique de `read_templates`
- `docs/tools/route-explorer.md`, `docs/tools/project-inspector.md` : une phrase chacun
- `docs/03-roadmap.md` : ligne de la piste B

## Validation finale

| Commande | Résultat |
|---|---|
| `python -m compileall -q forge_design` | OK |
| `ruff check forge_design tests` | All checks passed |
| `ruff format --check .` | Tout formaté |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Propre |
| `pytest` (suite complète, relancée après la documentation) | **4 727 tests verts** |
| Graphic Core | 134/134 |
| Mutations | 10/10 |
| Roue `forge-design 0.2.0`, venv neuf (avec Circuit et Flowchart) | `pip check` OK, `checked_root.py` présent |
| Chromium, Firefox (vraie commande) | 12/12 chacun ; avec modules : 12/12 |
| Sans JavaScript (Chromium, Firefox) | OK |

## État Git final

| Dépôt | État |
|---|---|
| Forge Design | `main`, un commit `perf: partager l'analyse Forge des contrats de vue (FD-PERF-001)` au-dessus de `87adc58`. `docs/rapports/FD-CONTRACT-001.md` toujours modifié, hors commit. Aucun push |
| ForgeDesign-Circuit, ForgeDesign-Flowchart | Non modifiés |
