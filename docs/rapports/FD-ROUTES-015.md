# Rapport — FD-ROUTES-015

## Ticket et objectif

Représenter les fermetures transitives et cycles déjà connus dans RouteGraph et le SVG, sans découverte après le Bridge.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `76163bf` — FD-ROUTES-014.
État Git et cinq derniers commits inspectés avant modification.

## Intégration transitive RouteGraph

Le builder consomme exclusivement les données de RoutesResult : représentation directe conservée, puis lecture des tables plates `TemplateResolution.dependency_graph`.
Une fermeture par racine est traitée dans l’ordre des routes, conformément au partage par racine du Bridge. Aucun parcours de fichiers, parsing, expansion ou calcul de fermeture.

## Nœuds transitifs

Même type template, mêmes IDs déterministes et labels. Les nœuds de chaque table et les cibles statiques de ses déclarations sont représentés.
Absence, chemin refusé et cible non contrôlée restent visibles avec leur présence existante. Une cible non contrôlée conserve not-applicable, jamais missing inventé.
Aucun nœud dynamique artificiel. Les statuts de première occurrence restent conservés, comme auparavant.

## Arêtes transitives

Chaque arête provient d’une déclaration du nœud source de la fermeture : extends, includes, imports, from-imports.
La simple présence de deux templates dans la table ne crée aucun lien.
Les arêtes directes restent identiques hors nouveau marquage explicite de cycle, avec les mêmes extrémités et types.

## Intégration des cycles

GraphEdge ajoute `in_cycle: bool = False`.
Les triplets source/cible/type des cycles fournis par le Bridge forment un index. Il marque uniquement les arêtes déjà représentées, sans créer de relation supplémentaire.
Une arête appartenant à plusieurs cycles est marquée une seule fois. Aucune détection, inversion ou canonicalisation nouvelle.

## Mutualisation

Nœuds et arêtes sont mutualisés globalement. Le préfixe direct et son ordre sont conservés, puis les nouvelles données apparaissent dans l’ordre des fermetures et de leurs déclarations.
Le builder parcourt les tables reçues et diagnostics une fois, puis marque les arêtes une fois. Le coût est linéaire dans les données d’entrée, y compris les occurrences partagées entre tables.

## Gestion de la troncature

RouteGraph ajoute `transitive_truncated: bool = False`, vrai si une fermeture utilisée est tronquée.
La vue graphique affiche « Analyse partielle. ». Les cibles connues aux limites restent des références syntaxiques ; leur absence n’est pas déduite.

## Algorithme de profondeur

Distance minimale par parcours en largeur multi-sources depuis les cibles de renders, sur les arêtes du graphe déjà construit.
Chaque template est enfilé une fois. Les cycles et auto-cycles terminent ; un nœud partagé garde la distance minimale.
Un template principal qui est aussi dépendance reste au niveau 3. Les éventuels templates sans chemin depuis un principal restent au niveau 4.
Aucune détection de cycle pendant ce calcul de coordonnées.

## Évolution du layout

Niveaux structurels 0/1/2 conservés. Les niveaux templates commencent à 3 et ne sont plus limités à deux colonnes.
Un compteur par niveau empile les rectangles dans l’ordre des nœuds, sans chevauchement. Largeur calculée sur le niveau maximal.
Tailles, marges et troncature visuelle des labels inchangées. Les chemins orthogonaux existants acceptent retours en arrière et même colonne.

## Représentation SVG

Trait pointillé et texte « (cycle) » sur les relations marquées, également indiqué dans la liste textuelle.
Présences textuelles existantes, marker partagé et échappement Jinja conservés. Aucun script, moteur tiers, zoom ou édition.
Le défilement horizontal conserve les colonnes à leur taille lisible.

## Pureté et isolation

Les tests interdisent filesystem, AST Python, parsing Jinja, Bridge, registre et détecteur de cycles autour du builder et du layout.
Un graphe contenant un auto-cycle mais dépourvu de diagnostic ne reçoit aucun marquage implicite.
Les modèles sources demeurent immuables ; aucun accès au projet après le Bridge.

## Intégration Web

Le tableau et la section textuelle de cycles restent inchangés. Le template existant consomme les nouveaux champs de RouteGraph et GraphEdge.
No-store et échappement restent actifs. Aucun nouveau Tool, route HTTP ou appel métier.

## Fichiers créés

- [tests/test_route_graph_transitive.py](../../tests/test_route_graph_transitive.py).
- [docs/rapports/FD-ROUTES-015.md](FD-ROUTES-015.md).

## Fichiers modifiés

- [forge_design/tools/route_graph.py](../../forge_design/tools/route_graph.py) : projection des fermetures et marquage.
- [forge_design/web/route_graph_layout.py](../../forge_design/web/route_graph_layout.py) : niveaux variables minimaux.
- [forge_design/web/templates/routes.html](../../forge_design/web/templates/routes.html) : cycle et analyse partielle.
- [forge_design/web/static/shell.css](../../forge_design/web/static/shell.css) : trait pointillé.
- [tests/test_web_inspector.py](../../tests/test_web_inspector.py) : assertions SVG transitive.
- [docs/02-architecture.md](../02-architecture.md) : nouveau flux.

Aucune modification du Bridge, de ses limites, du détecteur de cycles ou des dépendances de distribution.

## Tests ajoutés

Neuf nouveaux cas : sept tests de builder/layout et deux HTTP.
Profondeurs 1/2/3/5, compatibilité du préfixe direct, branches, partage entre racines, deux cycles partageant une arête, déduplication, marquage exclusif des diagnostics, auto-cycle, cibles absentes/refusées/non contrôlées, dynamique ignorée et troncature sont couverts.
Les tests vérifient largeur, niveaux minimaux, principal également dépendance, retour d’arête, déterminisme, absence de superposition et sentinelles d’isolation.
Les tests HTTP vérifient une cible à profondeur 2, un cycle pointillé et textuel, absence, analyse partielle, échappement, unicité des templates, sections conservées, CSS et no-store.
Les suites antérieures restent actives.

## Test réel

Wheel reconstruite et installée sans dépendances dans un répertoire temporaire ; processus Python isolé avec origine importée vérifiée et runtime de `.venv`.
La copie Forge contient contacts/list.html → base.html → layouts/site.html → macros/layout.html → base.html.
Le contrôle vérifie les templates uniques, trois arêtes de cycle, niveaux croissants, arête de retour, section textuelle et SVG marqué via GET /routes. Le serveur est arrêté et le port libéré.
Le dépôt de référence reste intact. L’absence d’accès projet pendant builder/layout est instrumentée dans les tests unitaires.

Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `8f933f2bad7dcc2e7a7544e81780bbf18a2aa1616627050454397bf0cbcd180e`.
Script ignoré : `tmp/verify_fd_routes_015.py`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| État Git et historique | Vérifiés |
| `pytest` | 412 tests réussis, dont 9 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| `python -m pip wheel --no-deps --wheel-dir tmp/wheels .` | Succès |
| Wheel installée, graphe et HTTP transitifs | Succès |

Outils de `.venv`, Python 3.13.5 ; sockets HTTP autorisés hors sandbox.
Les premières lignes trop longues Ruff ont été formatées avant validation finale. Pip a désactivé son cache utilisateur inaccessible sans erreur de dépendances.
Diff complet relu avant commit, rapport et nouveaux tests compris.

## Tests sautés

Aucun test pytest sauté. Aucun contrôle visuel navigateur, rendu cible ou nouvelle génération Forge revendiqué.

## Limites restantes

Le SVG peut être large et haut ; les segments peuvent partager des trajets ou se croiser. Aucun moteur de réduction des croisements.
Seuls les cycles témoins déjà diagnostiqués sont marqués. Une arête non marquée n’est pas une preuve d’absence de tout cycle possible.
La projection hérite des bornes, identités syntaxiques et statuts de première occurrence des étapes antérieures. Aucun nouveau contrôle n’arbitre des données contradictoires.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `feat: intégrer le graphe transitif des routes (FD-ROUTES-015)`.
Le hash et l’état Git après commit sont communiqués dans la réponse de livraison.
