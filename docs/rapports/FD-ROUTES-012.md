# Rapport — FD-ROUTES-012

## Ticket et objectif

Afficher le RouteGraph existant sous forme de SVG statique déterministe, sans découverte, nouvelle lecture du projet ou JavaScript.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `d5e5514` — FD-ROUTES-011.
État Git et cinq derniers commits inspectés avant modification.

## Choix de rendu

SVG produit par le template serveur, sans bibliothèque graphique. Le tableau diagnostique et la liste textuelle des relations sont conservés.

## Modèle RouteGraphLayout

Trois dataclasses gelées : PositionedNode (nœud original, coordonnées, dimensions, libellé visuel), PositionedEdge (arête originale, chemin et position du label), RouteGraphLayout (tuples et dimensions).
Les coordonnées ne sont pas ajoutées au modèle RouteGraph.

## Algorithme de layout

`layout_route_graph(graph)` ne reçoit que RouteGraph.
Un ensemble des cibles de renders distingue les templates principaux. Les autres templates sont placés en dépendances. Un template à double rôle reste dans la colonne principale.
Les nœuds sont parcourus dans leur ordre, avec un compteur par colonne ; un index par ID permet de positionner les arêtes en temps linéaire. Aucun parcours récursif ou transitif.

## Positionnement des nœuds

Colonnes 0 à 4 : route, handler, contrôleur, template principal, dépendance.
Pas horizontal 360 unités, rectangles 260 × 100, pas vertical 132, marges 30.
Les libellés de plus de 30 caractères deviennent 29 caractères et une ellipse. Le texte complet reste dans le titre SVG et le tableau.
Les dimensions sont calculées à partir des rectangles et restent positives pour un graphe vide.

## Représentation des arêtes

Chaque arête conserve son type et ses extrémités réels : le handler est relié directement au template, sans inventer un lien contrôleur-template.
Des segments orthogonaux passent dans les intervalles entre colonnes et dans des couloirs horizontaux distincts au-dessus des nœuds, espacés de 24 unités.
Chaque type est affiché sur son couloir. Un unique marker SVG définit les pointes de flèche.
Les nœuds partagés ne sont pas dupliqués. Les arêtes convergent vers leur même rectangle.

## Déterminisme

Aucun hasard, mesure navigateur ou état persistant. Ordre d’entrée conservé dans les tuples, identifiants métier inchangés, viewBox et coordonnées reproductibles.

## Accessibilité

Titre « Vue des relations », description du sens des colonnes, SVG avec role img et aria-labelledby.
Le conteneur défilant est accessible au clavier et possède un focus visible.
Le tableau et la liste textuelle offrent les références complètes. Les présences restent textuelles, sans dépendre d’une couleur.

## Intégration RouteGraph

`RoutesResult → RouteGraph → RouteGraphLayout → SVG`.
Le layout ne consulte ni RoutesResult, ni Bridge, ni registre. Aucun nouveau Tool ni modification du builder métier.

## Intégration Web

La page transmet le layout au template existant. Les labels et titres SVG sont échappés par Jinja, sans safe ni HTML brut.
Aucune balise script ajoutée, aucune interaction graphique. no-store conservé.

## CSS

Les anciens styles de cartes sont remplacés par les styles SVG : rectangles, texte, traits et marqueur.
Le conteneur utilise overflow auto et une hauteur maximale de 45rem, avec défilement horizontal sans compression des colonnes.

## Pureté et isolation

Les tests interdisent open, stat, lstat, parsing Python/Jinja, read_routes et ToolRegistry pendant le layout.
Les modèles d’entrée sont conservés dans les objets positionnés et ne sont pas mutés. Les modèles de sortie sont immuables.

## Fichiers créés

- [forge_design/web/route_graph_layout.py](../../forge_design/web/route_graph_layout.py).
- [tests/test_route_graph_layout.py](../../tests/test_route_graph_layout.py).
- [docs/rapports/FD-ROUTES-012.md](FD-ROUTES-012.md).

## Fichiers modifiés

- [forge_design/web/routes.py](../../forge_design/web/routes.py) : appel du layout.
- [forge_design/web/templates/routes.html](../../forge_design/web/templates/routes.html) : SVG et accessibilité.
- [forge_design/web/static/shell.css](../../forge_design/web/static/shell.css) : styles graphiques.
- [tests/test_web_inspector.py](../../tests/test_web_inspector.py) : SVG, partage et échappement.
- [docs/02-architecture.md](../02-architecture.md) : contrat de présentation pure.

Aucune dépendance ou métadonnée de packaging modifiée.

## Tests ajoutés

Cinq nouveaux cas couvrent graphe vide, une et deux routes, enrichissements partagés, dépendances multiples, ordre, colonnes, absence de chevauchement de rectangles, dimensions, troncature, déterminisme, immutabilité et isolation.
Un cas traite un template à la fois principal et dépendance, sans exiger une chaîne complète.
Le test HTTP est enrichi : SVG et marker unique, handler partagé affiché une fois avec deux relations handles, présence absente, labels échappés, tableau et no-store conservés.

## Test réel

Wheel construite et archive inspectée, installation temporaire sans dépendances puis processus Python isolé avec origine importée vérifiée. Runtime fourni par `.venv`.
Une copie du squelette Forge contient ContactController.list, contacts/list.html, extends base.html et include contacts/_table.html.
Le contrôle HTTP vérifie tableau, SVG, relations et labels attendus, marker unique et absence de script. Il couvre aussi les diagnostics, l’actualisation, la fermeture, l’arrêt du serveur et le port libéré.
Aucun changement au dépôt Forge de référence. L’absence d’accès projet pendant le layout est instrumentée dans les tests unitaires.

Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `f3dbf1fac5cc804f8c892b332b529addf3c87caa66413978248a96ab06453afc`.
Script ignoré : `tmp/verify_fd_routes_012.py`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat |
|---|---|
| État Git et historique | Vérifiés |
| `pytest` | 379 tests réussis, dont 5 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| `python -m pip wheel --no-deps --wheel-dir tmp/wheels .` | Succès |
| Wheel installée et HTTP réel | Succès |

Outils de `.venv`, Python 3.13.5 ; sockets locaux autorisés hors sandbox.
Une assertion trop longue signalée initialement par Ruff a été scindée. Pip a désactivé son cache utilisateur inaccessible sans erreur de dépendances.
Le diff complet, fichiers nouveaux et rapport compris, est relu avant commit.

## Tests sautés

Aucun test pytest sauté. Aucun contrôle visuel dans un navigateur ou rendu de template cible revendiqué.

## Limites restantes

Layout destiné aux petits et moyens graphes : la hauteur croît avec les arêtes. Les segments peuvent se croiser ou partager une partie de leur trajet ; aucun moteur de réduction des croisements n’est ajouté.
Les rectangles ne se superposent pas. Les labels longs sont tronqués, avec texte complet accessible ailleurs.
Le graphe doit respecter le contrat du builder : identifiants uniques et extrémités présentes. Aucune réparation de graphe invalide.
Aucun zoom, déplacement, édition ou sauvegarde. Les limites syntaxiques et de mutualisation du RouteGraph restent applicables.

## État Git final

Un seul commit local sur `main`, rapport inclus, sans push.
Message : `feat: ajouter la vue graphique statique des routes (FD-ROUTES-012)`.
Le hash et l’état Git après commit sont communiqués dans la réponse de livraison.
