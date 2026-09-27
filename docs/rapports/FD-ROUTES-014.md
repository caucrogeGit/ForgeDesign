# Rapport — FD-ROUTES-014

## Ticket et objectif

Détecter des cycles dans la fermeture Jinja déjà connue et exposer leurs diagnostics structurés et textuels, sans nouvelle découverte ni lecture.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `e3211bc` — FD-ROUTES-013.
État Git et cinq derniers commits inspectés avant modification.

## Modèle TemplateCycle

Dataclasses gelées dans `forge/template_cycles.py` : TemplateCycleEdge(source, target, kind, line), puis TemplateCycle(edges).
La propriété paths expose les sources et la dernière cible, donc un chemin fermé. La propriété key identifie les relations orientées sans leurs lignes.
TemplateDependencyGraph ajoute cycles, tuple vide par défaut ; les constructions antérieures restent valides.

## Algorithme de détection

`detect_template_cycles(graph)` ne consomme que TemplateDependencyGraph.
Une adjacency indexée conserve l’ordre des nœuds et déclarations. Les dépendances dynamiques et les cibles absentes de la table sont ignorées.
DFS itérative avec pile d’itérateurs, index des nœuds actifs et ensemble des nœuds terminés. Chaque arête vers un nœud actif ferme un cycle témoin avec les arêtes de l’arbre DFS.
Aucune récursion Python ni énumération de tous les chemins. Parcours O(V + E), plus le volume des diagnostics matérialisés et canonicalisés.
Les quatre types extends/include/import/from-import sont conservés, avec leurs lignes connues.

## Canonicalisation

Rotation du cycle vers la plus petite source lexicographique ; aucune inversion des arêtes.
Un cycle témoin simple ne contient chaque source qu’une fois, ce qui rend cette rotation non ambiguë.
Les déclarations de même source/cible/type gardent leur première ligne. Les cycles de mêmes relations orientées sont dédupliqués, même si des déclarations répétées ont des lignes différentes.
L’ordre des diagnostics est celui de leur première découverte.

## Gestion des auto-cycles

Une arête vers le nœud courant produit un cycle à une arête et le chemin fermé a → a.
Aucun traitement filesystem spécial.

## Gestion des cycles multiples

Les composantes indépendantes sont parcourues dans l’ordre d’entrée. Les motifs a → b → a et a → c → a donnent deux témoins distincts.
La politique est celle des arêtes de retour DFS, pas un inventaire exhaustif des cycles simples combinatoires dans une composante dense. Chaque cycle retourné suit exclusivement des arêtes réellement présentes et leur orientation.

## Gestion de la troncature

La détection considère les relations connues, même lorsque truncated vaut vrai. Aucune expansion n’est tentée pour compléter les cibles.
Les cycles déjà visibles sont conservés avec les warnings de limites existants.
L’absence de diagnostic dans une analyse tronquée ne prouve pas l’absence de cycle dans le projet.

## Intégration analyse transitive

La détection intervient après la construction de chaque fermeture. Le résultat gelé est enrichi via replace.
MAX_TEMPLATE_DEPTH, MAX_VISITED_TEMPLATES, queue et politique de découverte restent inchangés.
Un ensemble local au read_routes déduplique les warnings par identité de cycle entre racines. Deux routes ou deux racines décrivant le même cycle ne produisent pas deux warnings identiques.
Aucun cache persistant, nouveau Tool ou changement du RouteGraph.

## Intégration Web

Nouvelle section textuelle « Cycles de templates », avec chemins fermés et détail source:ligne, type et cible.
Les cycles déjà présents dans les fermetures sont agrégés sans recalculer leur détection.
Sans cycle : « Aucun cycle détecté dans l’analyse disponible. » ; fermeture tronquée : « Analyse partielle. ».
Échappement Jinja, no-store, tableau et SVG direct conservés. Aucun script, interaction ou dessin transitif ajouté.

## Pureté et isolation

Le module de détection n’importe les types de graphes que sous TYPE_CHECKING et ne dépend d’aucune primitive de lecture.
Les tests bloquent filesystem, parsing Python/Jinja, read_routes et ToolRegistry autour du détecteur.
Une chaîne de 1500 nœuds vérifie l’absence de récursion Python. L’entrée reste inchangée et les diagnostics sont gelés.

## Fichiers créés

- [forge_design/forge/template_cycles.py](../../forge_design/forge/template_cycles.py).
- [tests/test_template_cycles.py](../../tests/test_template_cycles.py).
- [docs/rapports/FD-ROUTES-014.md](FD-ROUTES-014.md).

## Fichiers modifiés

- [forge_design/forge/routes.py](../../forge_design/forge/routes.py) : enrichissement et warnings dédupliqués.
- [forge_design/web/routes.py](../../forge_design/web/routes.py) : agrégation de diagnostics existants.
- [forge_design/web/templates/routes.html](../../forge_design/web/templates/routes.html) : section textuelle.
- [tests/test_template_transitive.py](../../tests/test_template_transitive.py) : cycle désormais diagnostiqué et partage entre racines.
- [tests/test_web_inspector.py](../../tests/test_web_inspector.py) : diagnostics HTTP.
- [docs/02-architecture.md](../02-architecture.md) : contrat et politique de témoins.

Aucune dépendance ou métadonnée de distribution modifiée.

## Tests ajoutés

18 nouveaux cas : 13 tests purs, un test de warning partagé entre racines et quatre cas HTTP.
Couverture : vide, acyclique, auto-cycle, deux/trois nœuds, cycles indépendants et partagés, rotations, orientation, doublons, types et lignes, dynamique et terminaux, troncature avec/sans cycle, ordre et déterminisme, immutabilité et isolation.
Le test transitif antérieur conserve ses compteurs de lecture/parsing/extraction et attend maintenant un diagnostic unique de cycle.
Les tests HTTP couvrent cycle, absence, analyse partielle avec et sans cycle, échappement de <script> dans un nom, déduplication entre routes et no-store.

## Test réel

Wheel reconstruite puis installée sans dépendances dans un répertoire temporaire. Un processus Python isolé vérifie l’origine de l’import ; runtime fourni par `.venv`.
Une copie Forge contient contacts/list.html → base.html → layouts/site.html → contacts/list.html. L’analyse retourne un cycle, canonicalisé depuis base.html.
Après ajout de macros/forms.html → contacts/_table.html, un second cycle contacts/_table.html → macros/forms.html → contacts/_table.html est retourné.
Le GET /routes affiche les deux diagnostics avec le SVG existant et no-store. Le serveur est arrêté, le socket fermé et le port réutilisable. Le dépôt Forge de référence reste intact.

Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `fdcb3b5c734c9ff2110b97f8735ec663f960e25e9c4fcf4b2f7615a7cdb3e4c7`.
Script ignoré : `tmp/verify_fd_routes_014.py`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| État Git et historique | Vérifiés |
| `pytest` | 403 tests réussis, dont 18 nouveaux cas |
| Tests transitifs après annotation de test | 7 réussis |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| `python -m pip wheel --no-deps --wheel-dir tmp/wheels .` | Succès |
| Wheel installée, un puis deux cycles et HTTP | Succès |

Outils de `.venv`, Python 3.13.5 ; HTTP avec autorisation de sockets locaux hors sandbox.
Une ligne trop longue Ruff et une liste de test initialement non annotée signalée par Pyright sont corrigées avant livraison.
Pip a désactivé son cache utilisateur inaccessible sans erreur de dépendances.
Le diff complet est relu avant commit, rapport et nouveaux fichiers compris.

## Tests sautés

Aucun test pytest sauté. Aucun rendu cible, contrôle visuel navigateur ou nouvelle génération Forge revendiqué.

## Limites restantes

Cycles témoins DFS, pas énumération exhaustive de tous les cycles simples. Le choix des témoins dépend de l’ordre déterministe de la fermeture ; leur orientation n’est jamais inversée.
La fermeture bornée peut masquer des cycles non encore connus. Aucun diagnostic sur les dépendances dynamiques ou les cibles non analysées.
Les limites de découverte et de stabilité filesystem restent celles du Bridge. Le SVG demeure direct.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `feat: détecter les cycles Jinja (FD-ROUTES-014)`.
Le hash et l’état final sont communiqués dans la réponse de livraison.
