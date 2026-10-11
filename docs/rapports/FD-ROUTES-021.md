# Rapport — FD-ROUTES-021

Chaîne statique d'une route dans Route Explorer. Date : 2026-10-11.

Ce ticket a été soumis sous le nom FD-ROUTES-005, identifiant déjà pris : FD-ROUTES-001 à 020 existent, avec leurs commits et leurs rapports. Il a été renommé **FD-ROUTES-021** avec l'accord de l'utilisateur. La roadmap ne citait que 001 à 004 ; c'est le code qui fait foi (§10).

## Objectif

Depuis une route Forge, permettre de comprendre la chaîne applicative connue statiquement :

```text
route → handler → contrôleur et méthode → template(s) → contrat(s) de vue → diagnostics
```

Elle distingue le fait connu, le résultat possible, l'ambiguïté, l'information non déterminable et l'erreur démontrée. Le tout sans exécuter le projet, sans modifier ses fichiers, sans nouveau Tool et sans toucher au moteur générique.

| Décision | Résultat |
|---|---|
| A. Nouveau Tool ? | Non : cinq Tools (test et mutation) |
| B. Exécuter le projet ? | Non : AST et lecteurs existants seulement |
| C. Modifier le Graphic Core ? | Non : 0 diff, 134 tests Node |
| D. Modifier un module externe ? | Non |
| E. Route Explorer devient la vue détaillée de la chaîne d'une route ? | Oui |

Le cockpit fonctionne désormais à deux niveaux : Project Inspector répond à « où regarder ? », Route Explorer à « que se passe-t-il précisément sur cette route ? ».

## État Git initial

| Élément | Valeur |
|---|---|
| HEAD | `e411d0c` (FD-PROJECT-006), contient FD-RELEASE-001 (`8cf8203`) |
| `origin/main` | `e411d0c` après la poussée demandée par l'utilisateur avant ce ticket ; 0/0 au départ |
| Version | `forge-design 0.2.0` |
| Arbre | Seul `docs/rapports/FD-CONTRACT-001.md` modifié par l'utilisateur, préservé et hors commit |
| Modules | ForgeDesign-Circuit et ForgeDesign-Flowchart non modifiés |

## État réel de FD-ROUTES-001 à 004

La question posée par le ticket (001 à 004) appelle une réponse sur toute la verticale réellement livrée, de 001 à 020 :

| Capacité | Ticket | État avant ce ticket |
|---|---|---|
| Route : méthode, chemin, nom, public, source | 001, 016 | Implémenté |
| Référence syntaxique du handler, handler dynamique | 002 | Implémenté |
| Contrôleur importé → fichier, sans lecture ni exécution | 003 | Implémenté |
| Classe et méthode vérifiées par AST (trouvée, classe absente, méthode absente, ambiguë, illisible ; fichier absent via `missing_controller`) | 004 | Implémenté |
| `BaseController.render` littéral → template | 005 | **Partiel** : plusieurs littéraux donnaient `ambiguous` sans les chemins ; un seul rendu dynamique faisait perdre les littéraux connus |
| Présence et syntaxe Jinja, dépendances directes et transitives, cycles | 006 à 010, 013, 014 | Implémenté |
| Graphe des relations (Graphic Core), interaction | 011, 012, 015, 019, FD-GRAPHICS-002 | Implémenté |
| Liens vers les sources | 016 | Implémenté |
| Diagnostics consolidés (code, sévérité, message, source, `route_indices`) | 017 | Implémenté |
| Filtres | 018 | Implémenté |
| Stabilisation | 020 | Implémenté |
| Route → contrat de vue | — | **Manquant** |
| Chaîne compacte, niveau de confiance, état de chaîne, origine des diagnostics | — | **Manquant** |

## Périmètre

Ce ticket relève de la piste B (Route Explorer). Il n'introduit ni nouveau Tool, ni nouveau graphe, ni nouveau moteur d'analyse, ni contrat de module, ni ressource spécialisée. La section Routes de Project Inspector reste une synthèse, avec le même lien « Voir les routes ».

## Architecture

```text
GET /routes
 ├─ route-explorer.run → RoutesResult (read_routes, une fois)
 ├─ build_route_diagnostics(result)                   (inchangé)
 ├─ filter_route_explorer(...)                        (inchangé)
 ├─ template-viewer.run → TemplatesResult             (une fois)
 ├─ analyze_view_contract_links(root, templates)      (une fois, inventaire réutilisé)
 └─ build_route_linkage(result, diagnostics, links)   (pur, sans lecture)
        → RouteLinkageReport.select(routes filtrées)
        → routes.html : section « Chaînes des routes » + « Contrats de vue »
```

Le modèle est une **couche adjacente** : `RoutesResult` n'est étendu que d'un champ additif, et ses consommateurs (graphe, diagnostics, filtres, synthèse du cockpit, preview réelle) sont inchangés.

## Services existants réutilisés

| Besoin | Service |
|---|---|
| Routes, handlers, contrôleurs, méthodes, templates | `read_routes` par `route-explorer.run`, analyse AST existante |
| Présence des candidats | `_template_presence` existant (métadonnées seulement), une fois par chemin |
| Diagnostics | `build_route_diagnostics` (codes, sévérités, `route_indices`) |
| Inventaire des templates | `read_templates` par `template-viewer.run` |
| Liaison contrats ↔ templates | `analyze_view_contract_links(root, templates)`, paramètre ajouté par FD-PROJECT-006 |
| Liens | `source_url` (vue source en lecture seule), `template_url` (Template Viewer), `view_contract_source` |

## Modèle de liaison

`forge_design/tools/route_linkage.py` est runtime, en lecture seule, propre à Forge et jamais persisté. Ses éléments :

- `RouteLinkage` : un par route, avec `index`, `route`, `handler_kind`, `controller_state`, `confidence`, `templates`, `diagnostics` et `state` ;
- `TemplateLink` : `path`, `presence`, `source`, `contract_state`, `contracts` ;
- `LinkedDiagnostic` : `code`, `severity`, `message`, `origin`, `source`, `source_available`, `subject` ;
- `ContractsOverview` : disponibilité, totaux et diagnostics globaux ;
- `RouteLinkageReport.select(routes)` : retient les chaînes des routes affichées, **par identité d'objet**, puisque les indices des diagnostics se rapportent au résultat non filtré.

Seul ajout au lecteur : `TemplateCandidate(path, presence, source)` et `TemplateResolution.candidates`, avec une valeur par défaut `()`.

## Routes

Rien de ce qui était affiché n'est retiré : méthode, chemin, nom, handler déclaré, public ou protégé, source. Le tableau, les filtres, les cycles et le graphe restent en place. Le détail d'une chaîne reprend ces faits, avec un lien vers la déclaration.

## Handlers

| Type | Règle (structure déjà connue, aucune nouvelle analyse) |
|---|---|
| Méthode de contrôleur | Référence `Classe.méthode` avec contrôleur importé |
| Fonction (non analysée) | Référence sans point : Forge Design n'a jamais analysé les fonctions handlers |
| Référence non résolue | Référence pointée sans import de contrôleur |
| Handler dynamique | Expression non syntaxique (`handlers["x"]`) ; diagnostic `handler.dynamic` existant |

## Contrôleurs

Les états reprennent `HandlerInfo` tel quel : résolu (`found`), fichier absent (`missing_controller`), classe absente, méthode absente, ambigu, non vérifiable (lecture ou syntaxe), non applicable. Le fichier, la classe et la méthode sont liés à la vue source, avec leur ligne quand l'AST la connaît. Aucune convention de nom n'est utilisée (§24).

## Méthodes

La méthode est vérifiée par l'AST existant (définition directe dans la classe). Une méthode absente est une erreur démontrée (`controller.method_missing`), affichée avec son message précis : « Méthode absente : Users.nope (mvc/controllers/users.py) ».

## Templates probables

`_template` gardait déjà tous les littéraux de `BaseController.render`, sans interpréter les branches. Il les rend maintenant comme **candidats** dans l'ordre de la source, sans doublon, y compris quand le statut est `ambiguous` ou `dynamic`. Le statut lui-même ne change pas. La présence de chaque candidat est vérifiée par la même politique que pour un template unique (métadonnées seulement, une fois par chemin). La syntaxe et les dépendances restent réservées au template exact : il n'y a pas d'analyse transitive par candidat (décision validée).

## Niveaux de confiance

| Niveau | Cas | Affichage |
|---|---|---|
| `exact` | Un seul `render` littéral | Le chemin |
| `multiple` | Plusieurs littéraux | « Plusieurs templates possibles » et tous les chemins |
| `partial` | Des littéraux et au moins un rendu dynamique | Les chemins, plus « ? » (« au moins un rendu non déterminable ») |
| `unknown` | Rendu dynamique seulement | « Non déterminable statiquement » ; jamais « aucun template » |
| `none` | Aucun `render` détecté | « Aucun rendu détecté (pas une preuve d’absence de template) » |
| `not-applicable` | Méthode non résolue | « Non applicable » |

Il n'y a aucun pourcentage.

## Templates dynamiques

`render(template_name)` donne `unknown` et le diagnostic existant `template.dynamic`, en **avertissement**. La route reste affichée, avec l'état « partielle ». Un littéral combiné à un rendu dynamique donne `partial`, et le littéral garde sa liaison de contrat.

## Branches multiples

```python
if ok:
    return BaseController.render("users/edit.html")
return BaseController.render("users/error.html")
```

Ce code donne deux templates possibles, chacun avec sa présence et son contrat : `users/edit.html` a deux contrats (ambigu), `users/error.html` n'en a aucun. Il n'y a pas d'analyse de flux : les deux branches sont simplement possibles. Un candidat absent est affiché « Absent » mais ne rend pas la chaîne problématique, puisque la branche peut ne pas s'exécuter. Seul un template exact absent est une erreur démontrée (`template.missing`).

## Inventaire templates

Par affichage, `read_templates` est appelé **une fois**, par Template Viewer. L'inventaire est transmis à l'analyse des contrats, qui ne rebalaye pas `mvc/views` : test avec un `read_templates` d'analyse qui lève une exception, et mutation « inventaire non transmis ». Un projet de 200 routes et 250 templates ne déclenche jamais 200 lectures : mutation « read_templates appelé par route ».

## Contrats de vue

L'association passe toujours par route → template rendu → contrat, à partir de l'index par chemin de `ViewContractLinksResult.templates`.

| État d'un template | Source | Sévérité |
|---|---|---|
| Contrat associé | `linked` | — |
| Plusieurs contrats (ambigu) | `ambiguous` + anomalies `contract.link.multiple-contracts` | Avertissement |
| Aucun contrat (optionnel) | `without-contract` | Aucun diagnostic |
| Liaison inconnue | `unknown`, ou analyse indisponible | — |
| Non applicable | Template hors inventaire (absent, chemin refusé) | — |

**Contrats invalides.** Un contrat JSON ou de schéma invalide n'a pas de cible lisible. Comme demandé, il n'est **jamais** rattaché à une route : il apparaît dans la section globale « Contrats de vue » de la page (par exemple `contract.json_invalid`, avec un lien vers la source). Une route sans contrat affiche seulement « des contrats invalides non associables existent (voir « Contrats de vue ») », sans les lui attribuer. Ce comportement est couvert par un test et par la mutation « contrat invalide rattaché aux routes ».

Si l'inventaire ou l'analyse est indisponible, les routes restent affichées. La section Contrats annonce la raison, et chaque template passe en « Liaison inconnue ».

## Diagnostics consolidés

Une chaîne reprend les diagnostics existants de la route (`route_indices` de `build_route_diagnostics`, sans duplication), puis les anomalies de liaison des contrats de ses templates. Chacun garde son code, sa sévérité, son message et son **origine**, dérivée du préfixe stable du code :

```text
route → handler → controller → template → dependency (template.dependency_*) → contract
```

Les diagnostics sont triés dans cet ordre. Un code d'origine inconnue lève une erreur (test), plutôt qu'une origine inventée. Les diagnostics globaux (`route.partial`, cycles) restent dans la liste générale de la page. Une incertitude statique n'est jamais transformée en erreur (mutation « incertitude transformée en erreur »).

## États de chaîne

| État | Règle |
|---|---|
| ✓ Complète | Méthode résolue, template exact **présent**, aucune erreur |
| ✕ Problématique | Au moins un diagnostic d'erreur de la route |
| ◐ Partielle | Tous les autres cas : rendu non déterminable, plusieurs templates, fonction, présence non vérifiable, etc. |

Il n'y a aucun score. Un template exact non vérifiable (avertissement) laisse la chaîne partielle (test sur modèle).

## Interface Route Explorer

La nouvelle section « Chaînes des routes » contient un `<details>` par route affichée, replié par défaut, avec l'ancre `route-chain-N`. Le résumé est la chaîne compacte :

```text
GET /users/{id} → Users.show → users/show.html → users/show.view.json — ✓ Complète
GET /users/{id}/edit → Users.edit → users/edit.html | users/error.html → users/edit-bis.view.json, users/edit.view.json | sans contrat — ◐ Partielle
GET /mixed → Users.mixed → users/show.html | users/ghost.html | ? → … — ◐ Partielle
```

Le détail contient la route, le handler, le contrôleur, le niveau de confiance, chaque template avec sa présence et son contrat, puis les diagnostics avec leur origine. Les états sont écrits et marqués (✓ ◐ ✕) ; la couleur ne fait que les souligner. Il n'y a aucun JavaScript, et le graphe n'est pas enrichi.

## Navigation

| Depuis la chaîne | Cible |
|---|---|
| Contrôleur, classe, méthode | `/source?path=…&line=…` (vue source existante) |
| Template présent | `/templates/view?path=…` (ciblage stable de Template Viewer) |
| Contrat | `/source?path=mvc/views/…view.json` |
| Diagnostics | Source du diagnostic, si autorisée |

Forge Design n'étant pas un IDE, il n'y a ni « ouvrir dans l'éditeur » ni modification.

## Lecture seule

Rien n'est écrit dans le projet : instantané identique avant et après dans les tests (`test_page_is_read_only`) et dans les deux navigateurs. `.forge-design/` n'est pas créé.

## Sécurité

Toutes les lectures passent par les lecteurs existants : `_read_source` borné pour l'AST des routes et des contrôleurs, `_template_presence` par `lstat` sans contenu, descripteurs ancrés de l'inventaire et des contrats. Le code livré n'ajoute ni `open()`, ni `read_text`, ni import, ni `exec`, ni `eval`. Les valeurs hostiles (`<script>`, guillemets, `&`, accents) sont échappées par Jinja (test et mutation « nom de route non échappé »). Les bornes existantes s'appliquent, sans nouvelle limite.

## Performance

Mesure de `GET /routes` par la vraie application, en médiane sur 7 passes, avant (`e411d0c`, worktree temporaire) et après. Les projets sont les mêmes que pour le cockpit : petit, moyen (`gx8-browser` avec 10 contrats et 20 migrations) et maximal (**200 routes, 250 templates, 250 contrats**).

| Projet | Avant | Après | HTML avant → après |
|---|---|---|---|
| Petit | 32,6 ms | 48,9 ms | 10,5 → 12,2 Ko |
| Moyen | 37,1 ms | 58,8 ms | 39,6 → 47,4 Ko |
| Maximal | 114,9 ms | 270,5 ms | 913 → 1 137 Ko |

Appels par affichage, sur le projet maximal :

| Appel | Avant | Après |
|---|---|---|
| `read_routes` | 1 | 1 |
| Lectures de source contrôleur | 1 | 1 |
| `read_templates` (Template Viewer) | 0 | **1** |
| `read_templates` par l'analyse des contrats | — | **0** |
| `read_view_contracts` | 0 | **1** |
| `read_view_contract` (un par contrat) | 0 | 250 |

Décomposition sur le projet maximal :

| Étape | Temps |
|---|---|
| `read_routes` | 53,6 ms |
| `read_templates` | 7,9 ms |
| `analyze_view_contract_links` | **123,5 ms** |
| `build_route_linkage` | 0,7 ms |
| Diagnostics | 0,9 ms |

Le reste du surcoût vient du rendu des 200 chaînes. Le surcoût est dominé par l'analyse **existante** des contrats : chaque contrat est relu, validé, et sa racine redétectée. Aucune optimisation prématurée n'a été faite (voir « Dette / limites »).

## Tests Python

**31 tests** dans `tests/test_route_linkage.py`, sur une fixture `tests/route_linkage_support.py` de 12 routes et 4 contrats dont un invalide, avec un nom de route hostile :

- **Lecteur** : candidats dans l'ordre de la source, littéraux gardés malgré un rendu dynamique, présence par candidat, doublons fusionnés.
- **Liaison** : chaîne complète avec contrat valide ; matrice des 11 états (méthode de contrôleur, fonction, non résolue, dynamique ; résolu, fichier, classe ou méthode absente ; exact, multiple, partial, unknown, none, non applicable) ; plusieurs templates avec chacun son contrat ; template dynamique non déterminable ; erreurs avec leur origine ; contrats invalides globaux ; contrats indisponibles ; template exact non vérifiable.
- **Origines et sélection** : ordre des origines, sélection filtrée par identité, immuabilité.
- **Page** : chaîne compacte et détail, liens exacts, section des contrats, échappement, filtres appliqués aux chaînes, un inventaire et une analyse par affichage, contrats indisponibles, lecture seule, projet sans route, cinq Tools.

Les tests existants n'ont pas été modifiés : les 365 tests de routes passaient sans changement.

## Mutations

**25/25 tuées**, sources restaurées à l'identique (empreinte vérifiée).

- Les dix exigées par le §97 :
  1. contrôleur manquant considéré résolu ;
  2. méthode absente ignorée ;
  3. template dynamique présenté comme certain ;
  4. premier `render` seulement retenu ;
  5. contrat invalide présenté valide ;
  6. template absent ignoré ;
  7. diagnostic qui perd son origine ;
  8. incertitude transformée en erreur ;
  9. `read_templates` appelé par route ;
  10. sixième Tool.
- Confiance et états : littéraux + dynamique, aucun rendu, plusieurs littéraux, complète sans template présent, erreur non problématique, fonction prise pour une méthode.
- Contrats : anomalies de liaison non rattachées, contrat invalide rattaché aux routes, contrats indisponibles pris pour « sans contrat », indisponibilité qui fait tomber la page.
- Page : inventaire non transmis, sélection par ressemblance, nom non échappé, lien Template Viewer non ciblé, `no-store` supprimé.

Deux mutations ont d'abord survécu, chacune tuée par un ajout :

- « template absent ignoré » : un candidat absent, `users/ghost.html`, a été ajouté à la fixture ;
- « complète sans template présent » : test sur modèle avec une présence non vérifiable.

## Chromium

La vraie commande `forge-design --no-browser` est lancée depuis la roue 0.2.0, dans un venv neuf, avec un HOME isolé. La fixture est celle des tests. Résultat : **11/11** :

1. sélection par le formulaire, puis Route Explorer par la navigation (12 chaînes, tableau conservé) ;
2. chaîne complète, avec les liens Template Viewer et contrat, et le nom hostile affiché en texte ;
3. contrôleur absent : problématique, origine contrôleur ;
4. template dynamique : non déterminable, `partial` affiché « | ? » ;
5. plusieurs templates et contrats ambigus ; template exact absent ;
6. contrat invalide uniquement dans la section globale ;
7. lien Template Viewer, puis retour à Route Explorer ;
8. clavier : Tab jusqu'au résumé (41 appuis), puis Entrée ouvre le détail ;
9. Project Inspector → « Voir les routes » ;
10. lecture seule ;
11. aucune exception ni violation CSP.

Pour l'étape 8, les pilotes ont dû envoyer une vraie touche Entrée : `keyDown` avec texte en CDP, Retour `` en BiDi.

## Firefox

Même scénario par WebDriver BiDi : **11/11**.

Une limite d'automatisation : dans Firefox headless, `document.hasFocus()` est faux. `keydown`, `keypress` et `keyup` arrivent bien sur le `<summary>`, mais Firefox ne synthétise pas l'activation native, ni avec Entrée, ni avec Espace. Le résumé est bien atteint au clavier (41 Tab). L'ouverture par Entrée est vérifiée dans Chromium. Le comportement natif de `<details>` n'a pas été remplacé par du JavaScript.

## Sans JavaScript

| Navigateur | Résultat |
|---|---|
| Chromium (scripts désactivés) | 12 chaînes, 12 détails, 9 diagnostics de chaîne, section Contrats, résumé exact ; repli du graphe présent |
| Firefox (`javascript.enabled = false`) | 12 chaînes, 12 détails, section Contrats, 3 chaînes problématiques |

`<details>` est natif : les chaînes et leurs diagnostics sont entièrement consultables sans script.

## ToolRegistry

Le registre reste `project-inspector`, `route-explorer`, `entity-explorer`, `debug-center` et `template-viewer` : vérifié par `test_tool_registry_unchanged`, par `test_module_boundaries` et par la mutation « sixième Tool ».

## Dogfooding Forge MVC

La page reste la route existante `GET /routes` (`no_store=True`), avec un handler Forge MVC (`Request`, `Response`) et un rendu Jinja par `render_page`. Il n'y a ni infrastructure parallèle, ni JavaScript, ni Graphic Core supplémentaire. Le CSS ajoute sept règles `route-chain*` et `chain-*` dans `shell.css`.

**Modules activés (vérification légère).** La vraie commande est lancée avec `--module forge_design_circuit --module forge_design_flowchart` (zone Modules présente). Le scénario Chromium passe 11/11, et la section des chaînes est identique octet pour octet à celle obtenue sans modules.

## Dette / limites

- **Coût de l'analyse des contrats.** `read_view_contract` redétecte la racine pour chaque contrat (250 détections sur le projet maximal), et `GET /routes` passe de 115 à 270 ms. Un ticket pourrait partager la détection dans `analyze_view_contract_links`, sans changer son résultat.
- **Contrats invalides.** Ils restent non associables par construction : sans cible lisible, aucune association n'est possible.
- **Candidats.** Présence seulement : ni syntaxe ni dépendances par candidat. Les branches ne sont pas interprétées : un candidat est possible, pas certain.
- **Handlers fonctions.** Ils ne sont pas analysés : Route Explorer ne lit que les contrôleurs importés.
- **Firefox headless.** Il ne permet pas de vérifier l'activation clavier native d'un `<summary>` (`hasFocus` faux).
- **Taille de page.** Elle croît avec les détails (+224 Ko pour 200 routes). Aucune pagination.

## Recommandation ticket suivant

1. Partager la détection de racine dans l'analyse des contrats (performance, piste B), avec un résultat identique et mesuré sur le même projet maximal.
2. Ou poursuivre la Phase 5 (diagnostics Forge exécutés) déjà ouverte dans la roadmap, Route Explorer servant de vue de détail pour ses résultats.

## Fichiers créés

- `forge_design/tools/route_linkage.py`
- `tests/route_linkage_support.py`, `tests/test_route_linkage.py`
- `docs/rapports/FD-ROUTES-021.md`

## Fichiers modifiés

- `forge_design/forge/routes.py` : `TemplateCandidate`, `TemplateResolution.candidates`, présence des candidats
- `forge_design/web/routes.py` : inventaire et liaison une fois par affichage, contexte de page
- `forge_design/web/templates/routes.html` : sections « Chaînes des routes » et « Contrats de vue »
- `forge_design/web/static/shell.css` : règles `route-chain*` et `chain-*`
- `docs/tools/route-explorer.md` : section « Chaînes des routes », limites, contrats Python
- `docs/03-roadmap.md` : ligne de la piste B

## Validation finale

| Commande | Résultat |
|---|---|
| `python -m compileall -q forge_design` | OK |
| `ruff check forge_design tests` | All checks passed |
| `ruff format --check .` | Tout formaté |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Propre |
| `pytest` (suite complète, relancée après la documentation) | **4 718 tests verts** |
| Graphic Core (`node --test tests/js/graphics/*.test.mjs`) | 134/134 |
| Mutations | 25/25 |
| Roue `forge-design 0.2.0`, venv neuf (avec Circuit et Flowchart) | `pip check` OK, `route_linkage.py` présent |
| Chromium, Firefox (vraie commande) | 11/11 chacun ; avec modules : 11/11 |
| Sans JavaScript (Chromium, Firefox) | OK |

## État Git final

| Dépôt | État |
|---|---|
| Forge Design | `main`, un commit `feat: relier les routes aux vues Forge (FD-ROUTES-021)` au-dessus de `e411d0c`. `docs/rapports/FD-CONTRACT-001.md` toujours modifié, hors commit. Aucun push |
| ForgeDesign-Circuit, ForgeDesign-Flowchart | Non modifiés |
