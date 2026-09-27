# Rapport — FD-ENTITIES-003

## Ticket et objectif

Représenter les entités et relations déjà interprétées par un SVG statique, avec pivots, auto-relations et cycles, sans nouvelle analyse ou interaction.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `7e643a7` — FD-ENTITIES-002.
État Git et cinq derniers commits inspectés avant modification.

## Architecture du graphe

`EntitiesResult → build_entity_graph → EntityGraph → layout_entity_graph → SVG`.
Le Bridge, les modèles Forge et EntityExplorerTool restent inchangés. Les deux transformations sont pures et indépendantes des types RouteGraph. Le Web utilise le résultat de son seul appel au Tool.

## Modèle EntityGraph

Dataclasses gelées EntityGraphNode, EntityGraphEdge et EntityGraph ; nœuds et arêtes exposés comme tuples.
Un nœud conserve ID, kind, label, table et nombre de champs. Une arête conserve ID, source, cible, kind et label métier.
Les IDs typés utilisent les positions dans le résultat : entity:n, pivot:n, relation:n avec suffixes from/to si nécessaire. Ils sont reproductibles, sans hash, UUID ou hasard, et ne contiennent aucune donnée projet.

## Nœuds entités

Chaque EntityInfo produit exactement un nœud, même sans relation. Ordre d’entrée conservé ; nom, table et nombre de champs affichés.
Les noms homonymes ne fusionnent pas les nœuds ; les relations désignent la première occurrence du nom. Cette politique déterministe ne valide ni ne répare l’ambiguïté du modèle.

## Nœuds pivots

Chaque many_to_many dont les extrémités existent produit son propre pivot, après les entités et dans l’ordre des relations. Une table pivot identique sur plusieurs déclarations ne provoque aucune fusion.
Texte « Pivot », nom de table, nombre de champs supplémentaires, coins arrondis et bordure discontinue distinguent ce type sans dépendre de la couleur.

## Relations many_to_one

Arête dirigée de from_entity vers to_entity, donc depuis l’entité portant la FK. Nom métier affiché sur l’arête, type conservé dans son titre.
Les déclarations parallèles et auto-relations sont conservées. Aucun nœud fantôme lorsque source ou cible manque : la relation n’est pas dessinée, mais reste dans les données et anomalies textuelles existantes.

## Relations many_to_many

Deux arêtes ordonnées : source → pivot, puis pivot → cible. Types many_to_many_from et many_to_many_to ; nom métier sur le premier segment seulement.
L’auto many_to_many conserve son pivot et ses deux segments. Aucun champ n’est transformé en nœud et aucune relation inverse n’est inventée.

## Layout

Modèles gelés PositionedEntityNode, PositionedEntityEdge et EntityGraphLayout, distincts du graphe logique.
Deux colonnes : entités à x=40, pivots à x=480. Rectangles 260 × 100, pas vertical 140. Les nœuds suivent leur ordre de graphe, avec un compteur par colonne.
Un couloir supérieur par arête, espacé de 26 unités, produit un chemin orthogonal orienté. L’index des positions permet un calcul linéaire en nœuds/arêtes.
Dimensions positives, y compris pour le graphe vide. Libellés visuels limités à 30 caractères, ellipse comprise ; originaux conservés. Les tableaux et titres gardent les textes complets.

## Gestion des cycles

Aucune traversée topologique ni hypothèse de DAG. Les boucles et cycles sont simplement des arêtes positionnées ; aucun diagnostic métier ajouté.
Une auto-relation quitte la droite du rectangle, passe au-dessus des nœuds et revient à gauche, avec un trajet non nul. Les relations parallèles disposent de couloirs distincts, même si certains segments verticaux se partagent.

## SVG

Produit par Jinja depuis les données positionnées, sans chaîne HTML construite en Python. Un marker local dessine les flèches ; viewBox et dimensions proviennent du layout.
IDs de nœuds SVG indexés entity-node-n, indépendants des labels projet. CSS dédié, sans styles inline, dépendance graphique ou script.
La section suit les anomalies et précède les tableaux. Sans entité, elle n’est pas rendue ; les entités isolées restent visibles.

## Accessibilité

SVG role=img avec titre et description référencés par aria-labelledby. Les titres de nœuds/arêtes conservent leurs libellés complets.
Conteneur défilant horizontalement et verticalement, hauteur maximale 45rem, accessible au clavier avec focus visible. Aucun bouton ou navigation de nœuds. Les tableaux restent disponibles avec toutes les informations.

## Intégration Entity Explorer

GET /entities construit graphe puis layout depuis EntitiesResult déjà reçu. Aucun nouveau Tool, route, registre, cache ou état courant.
Navigation, compteurs, anomalies, détails des champs, relations et no-store sont conservés. Sans courant, aucun Tool ni graphe artificiel. Route Explorer demeure inchangé.

## Sécurité

Aucun filesystem, registre, parsing ou Bridge appelé par les transformations. Les tests interdisent ces accès autour du constructeur et du layout.
Échappement Jinja pour noms, tables et relations ; aucun safe, Markup, identifiant utilisateur brut ou JavaScript. Les tests HTTP utilisent des noms contenant HTML, guillemets et antislash, ainsi qu’un nom de relation contenant une balise script.
Aucun SQL, BDD, import projet, génération ou écriture ajouté.

## Déterminisme

Ordres d’entrée conservés, aucune déduplication de relation. Même résultat d’entrée, mêmes IDs, coordonnées, chemins et labels.
Les IDs sont des positions typées, pas des identifiants persistants entre réordonnancements. Les modèles sont immuables ; les tests comparent l’entrée avant/après et les résultats de deux appels.

## Non-écriture

Le contrôle installé compare octets et dates de modification de l’ensemble des fichiers de la copie Forge après chaque consultation. Les seules mutations sont les changements volontaires de fixture entre les GET.
Le dépôt Forge de référence reste intact. Les transformations pures n’ont aucune primitive d’écriture ou d’accès projet.

## Fichiers créés

- forge_design/tools/entity_graph.py
- forge_design/web/entity_graph_layout.py
- tests/test_entity_graph.py
- tests/test_entity_graph_layout.py
- tests/test_web_entity_graph.py
- docs/rapports/FD-ENTITIES-003.md

## Fichiers modifiés

- forge_design/web/entities.py : projection du résultat existant.
- forge_design/web/templates/entities.html : SVG statique accessible.
- forge_design/web/static/shell.css : styles du graphe.
- tests/test_entity_relations.py : assertion d’ordre bornée au tableau et SVG désormais autorisé.
- docs/tools/entity-explorer.md : usage et limites du graphe.
- docs/02-architecture.md : séparation des transformations.

Aucune dépendance, métadonnée de packaging ou modification du Bridge.

## Tests ajoutés

21 nouveaux cas : dix de graphe, six de layout et cinq HTTP.
Graphe : vide, entités isolées/homonymes, direction, labels, pivots distincts et champs comptés, parallèles, auto-relations des deux types, six combinaisons d’extrémités absentes, ordre, déterminisme et immutabilité.
Sentinelles communes constructeur/layout sur open/stat/lstat/listdir/scandir/glob, parsing Python/JSON/Jinja, Bridge et registre.
Layout : dimensions positives, coordonnées et chemins dans le viewBox, rectangles disjoints, labels longs, boucles non nulles, parallèles distinctes, cycles de deux/trois entités, 30 entités et 60 relations.
HTTP : sans courant, vide, isolées, auto-relations, pivots, cycles et 30/60 ; DOM SVG, marker, chemins, IDs sûrs, accessibilité, XSS, tableaux et anomalies, no-store, absence de scripts, un seul appel du Tool par GET et Route Explorer accessible.
Les 662 cas historiques restent actifs.

## Test réel

Copie temporaire du véritable squelette Forge avec Article, Tag, Comment et User. Les contrats JSON sont préparés par le constructeur de la baseline déjà vérifiée, exclusivement pour la fixture.
Relations Comment → Article, Article → article_tag → Tag et User → User. Depuis la wheel installée, HTMLParser vérifie cinq nœuds, quatre chemins distincts non nuls, marker unique, noms, accessibilité et absence de script.
CSS distribué servi et contrôlé. Le scénario vérifie aussi la relecture après ajout volontaire d’une relation puis JSON invalide, avec entités conservées et Route Explorer accessible.
Serveur arrêté, thread terminé, socket fermé et port réutilisable. XDG temporaire et fichiers projet inchangés par les consultations.
Script/journal ignorés : tmp/verify_fd_entities_003.py et tmp/verify_fd_entities_003.log.

## Packaging

Wheel reconstruite, archive inspectée : graph/layout, template et CSS présents, aucun tests/ ou tmp/ distribué. Package-data existant suffisant, sans modification de pyproject.toml.
Installation temporaire --no-deps --no-index --target ; processus Python -I vérifiant l’origine installée, runtime de .venv.
Artefact : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `3e46e214f6300072093d9a0bab3bd746f6168b34d8c3ab56c5554c31732e86ed`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| Git initial et cinq derniers commits | Vérifiés |
| Tests ciblés graphe/layout | 16 réussis |
| pytest | 683 réussis, dont 21 nouveaux cas |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip check | No broken requirements found |
| git diff --check | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Wheel installée, SVG/DOM/CSS et HTTP réel | Succès |

Outils .venv, Python 3.13.5 ; HTTP avec sockets locaux autorisés hors sandbox.
L’assertion historique d’ordre global a été bornée au tableau. Une attente du nouveau cas isolé a été corrigée : son anomalie de relation injectée implique « Aucune relation interprétable ».
La première construction wheel a échoué faute de réseau pour setuptools dans le sandbox ; elle a réussi avec accès réseau autorisé. Pip check signale son cache utilisateur inaccessible, sans erreur de dépendances.
Diff complet, nouveaux fichiers, documentation et rapport relus avant commit.

## Tests sautés

Aucun test pytest sauté. Aucun contrôle visuel navigateur ou capture pixel-perfect, conformément au ticket. Les vérifications portent sur le layout et le DOM HTTP, pas sur un moteur SVG ni une technologie d’assistance.
Aucune exécution cible, génération SQL/Python ou validation BDD revendiquée.

## Limites restantes

Placement simple pour petits graphes : hauteur proportionnelle aux arêtes et rangées, croisements et segments partagés possibles. Aucune optimisation des croisements ou limite globale nouvelle ; le calcul reste linéaire dans l’entrée.
Les libellés sont tronqués par nombre de caractères, sans mesure typographique navigateur. Pas de zoom, sélection ou édition.
Noms homonymes résolus à la première occurrence ; aucun diagnostic de cycle ou validation métier supplémentaire. Le layout attend des IDs uniques et extrémités présentes, garantis par le constructeur.
Les limites d’interprétation du Bridge restent applicables.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `feat: ajouter le graphe Entity Explorer (FD-ENTITIES-003)`.
Le hash et l’état final vérifiés sont communiqués dans la réponse de livraison.
