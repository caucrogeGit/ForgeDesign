# Rapport — FD-ROUTES-008

## Ticket et objectif

Extraire les déclarations de dépendances Jinja directes du template valide déjà analysé, sans charger les cibles ni construire de graphe transitif.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `4265802` — FD-ROUTES-007.
`git status` et `git log --oneline --decorate -5` exécutés avant modification.

## AST Jinja vérifié

Jinja2 installé et déclaré : `3.1.6`, baseline déjà utilisée par Forge.
Inspection de `jinja2/nodes.py` et exécution de `Environment(loader=None).parse` sur les formes du ticket :

| Déclaration | Nœud public | Référence |
|---|---|---|
| extends | `nodes.Extends` | `template` |
| include | `nodes.Include` | `template` |
| import | `nodes.Import` | `template` |
| from import | `nodes.FromImport` | `template` |

Une chaîne produit `nodes.Const` ; la liste d’include produit `nodes.List` contenant les constantes dans leur ordre. Les variables et concaténations produisent des expressions distinctes, non évaluées.
Le parcours utilise uniquement `iter_child_nodes` et les nœuds publics Jinja.
Aucune dépendance ou configuration de parser modifiée.

## Modèle TemplateDependency

Dataclass gelée : `kind`, `path: str | None`, `dynamic: bool`, `line: int`.
`kind` distingue `extends`, `include`, `import`, `from-import`.
`TemplateResolution` ajoute `dependencies: tuple[TemplateDependency, ...] = ()`.
Le tuple vide représente l’absence de déclaration ou une analyse non applicable ; les statuts de résolution, présence et syntaxe existants distinguent ces situations.

## Dépendances statiques

Les références `nodes.Const` contenant une chaîne sont conservées sans normalisation.
Un include avec liste non vide entièrement littérale fournit une occurrence par élément, dans l’ordre de la liste.
Les chemins tels que `../secret.html` restent des références syntaxiques : aucune validation filesystem ni ouverture.
Les symboles d’un import ne sont pas analysés.

## Dépendances dynamiques

Variables, concaténations, appels et autres expressions donnent `dynamic=True`, `path=None`.
Une liste mixte, vide ou non littérale donne une seule déclaration non résolue ; aucun candidat partiel n’est présenté comme résolution complète.
Aucune variable, constante nommée ou branche n’est évaluée. Aucun warning supplémentaire pour ces cas normaux.

## Ordre et lignes

Parcours itératif des nœuds, incluant les branches, macros et blocs sans analyse de leur comportement.
Un tri stable par ligne conserve l’ordre source et l’ordre de parcours des occurrences sur une même ligne. Aucun tri alphabétique.
Les doublons sont conservés. Tous les éléments d’une liste d’include portent la ligne de sa déclaration.

## Réutilisation AST

L’unique appel `Environment.parse` existant retourne désormais son AST à l’extracteur après succès.
Aucune extraction ni seconde tentative de parsing sur syntaxe invalide ou lecture impossible.
L’AST n’est pas conservé au-delà de son utilisation : le cache existant mémorise le résultat enrichi, ce qui évite de garder un arbre inutile.

## Cache local

Une lecture, un parsing et une extraction par référence pendant `read_routes`.
Les routes partageant le même template utilisent le résultat mis en cache. Le cache est abandonné au retour ; un nouvel appel répète les contrôles.
Les résultats invalides et non applicables restent sans dépendances.

## Intégration Bridge

`read_routes(...) -> RoutesResult` conserve son contrat.
Les routes, handlers, contrôleurs, vérifications, références, présences, syntaxes, noms, indicateurs public, ordre et warnings antérieurs restent inchangés.
Aucun nouveau Tool ni changement du registre ou d’Inspector.

## Intégration Web

Une liste compacte est ajoutée sous la référence dans la cellule Template, sans nouvelle colonne.
Exemples : `extends: base.html`, `include: dynamique`.
Tous les chemins passent par l’échappement Jinja ; aucun `safe`, lien ou nouvelle route HTTP. `Cache-Control: no-store` est conservé.

## Sécurité

Aucun accès filesystem supplémentaire pour les dépendances, aucune vérification d’existence ou de confinement de leurs chemins.
Le parser reste sans loader, sans compilation ni rendu. Aucun import du projet, scan, écriture ou suivi récursif.
Les garanties de lecture du template courant restent celles de FD-ROUTES-007.

## Fichiers créés

- [docs/rapports/FD-ROUTES-008.md](FD-ROUTES-008.md).

## Fichiers modifiés

- [forge_design/forge/routes.py](../../forge_design/forge/routes.py) : modèle et extraction sur AST existant.
- [forge_design/web/templates/routes.html](../../forge_design/web/templates/routes.html) : résumé des déclarations.
- [tests/test_routes.py](../../tests/test_routes.py) : nœuds, ordre, lignes et cache.
- [tests/test_web_inspector.py](../../tests/test_web_inspector.py) : rendu HTTP échappé.
- [docs/02-architecture.md](../02-architecture.md) : contrat direct non transitif.

Aucune dépendance ni métadonnée de distribution modifiée.

## Tests ajoutés

13 nouveaux cas : 12 scénarios AST et un test HTTP.
Ils couvrent les quatre déclarations statiques, extends/include dynamiques, concaténation, appel, liste littérale ordonnée, liste mixte, traversal conservé sans ouverture et un scénario regroupant branches, macro, bloc, doublons et lignes exactes.
La sentinelle d’ouverture limite les accès aux seules sources déjà autorisées.
Les 12 scénarios de syntaxe existants sont instrumentés pour vérifier une seule extraction après parsing valide et aucune extraction après échec, en plus des compteurs de lecture/parsing et des interdictions de scan, loader, compilation et rendu.
Les assertions existantes confirment le tuple vide pour les cas non applicables. Les comparaisons de contenu et dates de modification restent actives.
Le test HTTP vérifie extends, include statique/dynamique, échappement HTML, Présent, Valide et `no-store`.
Une suppression Pyright locale `reportPrivateUsage` sert uniquement à instrumenter l’extracteur interne dans le test de cache.

## Test réel

Wheel construite et archive inspectée, puis installation temporaire sans dépendances dans un processus Python isolé (`-I`), origine des imports vérifiée. Les dépendances runtime proviennent de `.venv`.
Une copie du squelette reçoit la vue contact avec `extends "base.html"` et `include "contacts/_table.html"` dans un bloc, sans création de ces dépendances.
Le GET `/routes` affiche les deux déclarations et conserve Présent/Valide. Le contrôle vérifie aussi une modification rendant le template courant invalide, la fermeture du projet, l’arrêt du serveur et la libération du port.
Aucun changement du dépôt Forge de référence. L’absence d’ouverture des dépendances est instrumentée dans les tests unitaires ; l’extracteur lui-même ne réalise aucun accès fichier.

Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `d28c453c2bdda23be04ff06430375f1ab2ca931a4ccf76e96ea6f872ca8ee030`.
Script ignoré par Git : `tmp/verify_fd_routes_008.py`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| État Git et historique | Vérifiés |
| Version Jinja, inspection des nœuds et parsing des exemples | 3.1.6, formes confirmées |
| `pytest` | 343 tests réussis, dont 13 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| `python -m pip wheel --no-deps --wheel-dir tmp/wheels .` | Succès |
| Wheel installée et HTTP réel | Succès |

Outils de `.venv`, Python 3.13.5 et Jinja2 3.1.6 ; sockets locaux autorisés hors sandbox.
Deux lignes de fixtures trop longues ont été corrigées avant validation finale. Pip a désactivé son cache utilisateur inaccessible dans le sandbox, sans erreur de dépendances.
Le diff complet est relu avant commit, rapport compris.

## Tests sautés

Aucun test pytest sauté. Aucun rendu cible, contrôle visuel navigateur ou génération complète Forge revendiqué.

## Limites restantes

Une déclaration détectée ne prouve ni présence, ni validité, ni chargement de sa cible. Aucun graphe transitif ou détection de cycles.
Les déclarations dans des branches ou macros non exécutées restent visibles ; leur exécution effective n’est pas déduite.
Les listes mixtes et expressions complexes restent non résolues. Les limites de lecture et de syntaxe des tickets précédents sont conservées.

## État Git final

Un seul commit local sur `main`, rapport inclus, sans push.
Message : `feat: analyser les dépendances Jinja des templates (FD-ROUTES-008)`.
Le hash et l’état Git après commit sont communiqués dans la réponse de livraison.
