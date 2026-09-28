# Rapport — FD-ENTITIES-008

## Ticket et objectif

Stabiliser la verticale Entity Explorer 001–007 : revue complète, bornes de volume,
corrections ciblées, contrats publics et limites documentés. Aucune nouvelle fonction
majeure, édition, DB, SQL, génération ou Tool.

## État Git initial

main propre et synchronisée avec origin/main à `4058f86` — FD-ENTITIES-007.
`git status` et `git log --oneline --decorate -8` inspectés avant modification.
Aucun AGENTS.md dans le dépôt.

## Baseline Forge vérifiée

`git -C ../Forge ls-remote origin refs/heads/main` retourne
`73a956e587e5f169c028415e0e540c149cbaff56`, identique au HEAD local propre et à la
baseline FD-ENTITIES-001/002. Vérification distante en lecture seule, sans fetch,
checkout ou modification du dépôt Forge.

Schémas entity/relations sous skeleton/data/schemas, field/pivot du package
forge-mvc-entities, model.py et relations.py examinés. schema_version 1.0 et les
deux relations restent en vigueur. foreign_key/on_delete restent exigés par le
validateur Python many_to_one, malgré la liste required plus courte du schéma.
Pivot id/unique_pair=true, on_delete par défaut cascade et fields optionnels restent
cohérents. Aucun ajustement fondé sur un changement supposé de Forge.
Les doublons globaux sont des faits structurels déjà visibles, sans copier check:model.

## Revue de la verticale

Bridge entities, Tool, graphe, diagnostics, filtres, parsing Web, handler entities,
layout, entity-graph.js, template entities, politique source et handler source relus,
ainsi que les tests ciblés et contrats historiques.

Les défauts concrets concernent les volumes non bornés, le remplacement d’un dossier
après découverte, la duplication de politique lexicale et l’expansion Unicode de q.
Les diagnostics existants, associations, graphe, layout, scripts, formulaire et
navigation source n’exigent pas de réécriture. Les zones sans anomalie restent intactes.

## APIs stabilisées

Signatures conservées : read_entities(root), EntityExplorerTool.run(project_root),
build_entity_graph(result), build_entity_graph_from_items(entities, relations),
build_entity_diagnostics(result), filter_entities(result, diagnostics, filters),
layout_entity_graph(graph).

EntitiesResult, EntityInfo, EntityFieldInfo, RelationInfo, ManyToOneInfo et
ManyToManyInfo restent gelés et inchangés. Les projections restent des modèles
immuables avec tuples. Tests verrouillant symboles, signatures principales, gel
des dataclasses, champs de EntitiesResult et composition exacte de trois Tools.
Documentation « API stable actuelle » avec entrées, sorties et responsabilités.

## Limites centralisées

| Limite | Valeur | Motivation |
|---|---:|---|
| MAX_SOURCE_BYTES | 1 Mio | Borne historique du texte JSON/source |
| MAX_ENTITY_DIRECTORY_ENTRIES | 4096 | Bornage même avec des milliers de noms ignorés |
| MAX_ENTITY_FILES | 256 | Inventaire raisonnable pour la vue synchrone |
| MAX_ENTITY_RELATIONS | 512 | Relations et SVG de taille finie |
| MAX_ENTITY_FIELDS | 256 | Structures/tabulations bornées par entité |
| MAX_ENTITY_PIVOT_FIELDS | 64 | Pivot destiné à des attributs supplémentaires |
| MAX_FILTER_QUERY_LENGTH | 256 | Contrat de recherche Web existant |

Toutes les nouvelles valeurs sont dans limits.py. Elles bornent les objets
interprétés et rendus ; le parseur JSON décode encore au plus 1 Mio complet.
Les fonctions pures ne plafonnent pas à nouveau les résultats synthétiques reçus.

## Bornes entités

scandir via descripteur remplace listdir non borné. Au plus 4097 noms sont consommés,
le dernier servant uniquement à détecter le dépassement. Les 4096 premiers sont
triés lexicalement, puis au plus 256 candidats canoniques sont inspectés.
Les candidats illisibles, invalides ou fichiers réguliers de nom admissible comptent
également ; les entrées exclues lexicalement ne consomment que la borne de découverte.
Un surplus produit entity.analysis_truncated dans warnings, sans perdre les faits acquis.

Sous la borne de découverte, l’ordre lexical historique est conservé. Au-delà, le
sous-ensemble dépend de l’ordre d’énumération du filesystem ; cette limite est
explicitement documentée. Un plafond strict et un tri lexical global sans parcourir
le dossier entier ne peuvent pas être garantis simultanément.

Les 256 premiers champs sont interprétés ; si l’entité est interprétable et la
liste dépasse le plafond, entity.fields_truncated signale le reste non analysé.

## Bornes relations

Les 512 premières déclarations JSON sont traitées, y compris celles invalides.
L’index d’origine est conservé ; relation.analysis_truncated signale les suivantes.
Les 64 premiers champs pivot sont interprétés, avec relation.fields_truncated et
source_index de la relation. Les erreurs restent locales, aucune analyse ultérieure
n’est déclenchée par un filtre. Les premières données interprétables sont gardées.

## Diagnostics

Six codes supplémentaires, tous warnings du Bridge :
entity.analysis_truncated, relation.analysis_truncated, entity.fields_truncated,
relation.fields_truncated, entity.name_duplicate et entity.table_duplicate.
Les onze codes historiques restent inchangés. build_entity_diagnostics est inchangé
et conserve code, source, index et sévérité de toutes les nouvelles issues.

Les doublons de nom/table sont établis par Counter sur les EntityInfo déjà lus,
en égalité exacte, puis signalés sur chaque occurrence et sa source. Aucune donnée
supprimée, aucune validation métier de type/FK/SQL. Les avertissements globaux sans
rattachement n’entraînent aucune sélection arbitraire par diagnostics_only.

## Filtres

Correction q : une entrée de 129 ß était admise puis affichée sous 258 caractères
après casefold, rendant sa resoumission invalide. La limite s’applique désormais
avant et après normalisation ; une valeur affichée normalisée peut être resoumise.
Le test vérifie 128 ß → 256 caractères et le refus au-delà, y compris en HTTP.

Les associations source.path et relation_index restent identiques. Les filtres ne
relancent pas une lecture plus large ; les totaux représentent les données disponibles.
Diagnostics filtrés par sévérité seule, global warnings toujours affichables.
Une relation à cible absente demeure dans le tableau et sélectionnable par son
index de diagnostic, sans nœud fantôme dans le graphe ; sa source reste consultable.

## Graphe

Algorithmes et IDs inchangés. Noms indexés par map, occurrence initiale conservée
comme extrémité, y compris si un homonyme est sélectionné directement par un filtre.
La nouvelle issue de doublon rend l’ambiguïté visible sans inventer de résolution.

Test 100 entités/200 relations (dont many_to_many) : 200 nœuds, 300 arêtes, IDs
uniques, déterminisme, dimensions finies et coordonnées non négatives.
Les tests historiques contrôlent précisément les axes du viewBox, boucles,
parallèles, labels longs, absence de chevauchement des rectangles et graphes vides.
Construction, sélection et layout utilisent maps/sets et parcours linéaires dans
les éléments disponibles ; seul le tri de découverte borné reste O(D log D).

## Interaction

entity-graph.js relu, inchangé. Double DOM Node historique : nœuds absents,
arêtes partielles, boucle, parallèles, plusieurs conteneurs, Entrée/Espace/Échap,
retour focus, texte hostile et réinitialisation. Sélection en O(nœuds + arêtes).
Rôles, aria-labelledby, aria-pressed, focus, noscript, labels formulaire et en-têtes
de tableaux existants vérifiés structurellement ; aucune incohérence exigeant une
modification relevée. Aucun test navigateur/lecteur d’écran réel revendiqué.

## Navigation source

Suppression de la regex et de la liste de noms sensibles dupliquées dans le Bridge :
il valide maintenant le chemin canonique proposé avec source_parts. La politique
source devient réellement unique, sans modifier ses formes autorisées.
Tests env/.env/id_rsa/id_ed25519/.pem/.key et variantes de casse sur les deux chemins.
Sources de troncature globales (dossier) non navigables ; celles de champs et de
relations restent des références canoniques, contrôlées au moment de lecture.

/source conserve explicitement son contrat historique : première valeur non vide
path/line et clés inconnues ignorées. /entities garde son rejet des répétitions
non vides et clés inconnues. La différence est documentée et testée ; aucune
relaxation de la politique lexicale, aucun paramètre de retour ajouté.

## Sécurité

Dossier d’entité : stat découvert comparé au fstat du descripteur ouvert via samestat.
Un remplacement par un autre dossier réel entre les deux produit entity.unreadable.
Le parcours de la racine du Bridge est ancré segment par segment sans symlink,
comme le lecteur source stabilisé au ticket précédent. Descripteurs fermés par
context managers/ExitStack, y compris en cas d’échec.

Race stat → remplacement → open de relations.json simulée : samestat déjà présent
produit relation.unreadable. JSON profondément imbriqué : diagnostic contrôlé,
aucune modification requise. NaN/Infinity/-Infinity restent refusés.
Listes de 12 000 champs et 10 001 relations sous 1 Mio : structures produites bornées.
Pas d’import projet, subprocess Forge, DB, parsing Python/SQL ou commande de génération.

## Bugs découverts

| Symptôme | Cause | Correction | Non-régression |
|---|---|---|---|
| Inventaire et rendu potentiellement excessifs | listdir complet et listes non plafonnées | Découverte et structures bornées, warnings | Bornes exactes/surplus et bombes sous 1 Mio |
| Dossier remplacé lu après découverte | Aucune comparaison identité du parent | samestat après ouverture | Remplacement contrôlé par dossier réel |
| Racine du Bridge ouverte à travers un parent lié en cas de remplacement | O_NOFOLLOW appliqué au chemin complet seulement | Ouverture segment par segment | Garanties ancrées, suites historiques symlinks |
| Recherche normalisée affichée mais non resoumissible | casefold peut augmenter la longueur | Contrôle après normalisation | ß, frontière et HTTP 400 |
| Ambiguïté silencieuse des homonymes | Première occurrence utilisée sans avertissement | Warnings structurels sur chaque occurrence | Doublons, filtre et graphe |
| Risque de divergence Bridge/source | Deux copies de règles lexicales | Réutilisation source_parts | Noms sensibles et casse |

## Corrections appliquées

Trois fichiers produit seulement : limits.py, forge/entities.py et tools/entity_filters.py.
Aucun changement des modèles publics, de la projection diagnostics, du Tool,
registre, graphe, layout, Web, template, CSS ou JavaScript. Aucun refactoring transversal.

## Régressions vérifiées

Tous les tests FD-ENTITIES-001 à 007 restent actifs et inchangés, ainsi que Route
Explorer et /source. HTTP : 200/400/404/409 selon endpoints, no-store, POST refusés,
CSP script-src 'self', source JSON invalide consultable et erreurs locales conservées.
Les nouveaux warnings passent par la section Diagnostics existante, sans bannière.

## Non-écriture

Scénario installé : comparaison octets/taille/mtime du projet et de la configuration
XDG autour de chaque GET. Identité CurrentProjectContext.inspection vérifiée avant
et après chaque GET, stable après l’ouverture initiale. Dépôt Forge propre à la fin.
Aucune écriture, connexion DB ou commande Forge dans le parcours produit.

## Fichiers créés

- tests/test_entity_explorer_stabilization.py
- docs/rapports/FD-ENTITIES-008.md

## Fichiers modifiés

- forge_design/limits.py : bornes centralisées.
- forge_design/forge/entities.py : découverte, listes, races, politique et doublons.
- forge_design/tools/entity_filters.py : borne de recherche normalisée.
- docs/tools/entity-explorer.md : API stable actuelle et limites connues.
- docs/02-architecture.md : plafonds et contrats stabilisés.

## Tests ajoutés

32 cas nouveaux : contrat API/composition, borne entités exacte et dépassée,
découverte bornée même avec noms ignorés, relations/champs/pivots aux limites,
doublons et première occurrence, races dossier/fichier, JSON profonds et constantes
non standard, onze noms sensibles, gros graphe, Unicode, parcours HTTP transversal,
bombes de listes sous 1 Mio. Préservation des issues vers diagnostics vérifiée.

## Test réel

Wheel installée avec --no-deps --no-index --target. Copie temporaire Forge avec
Article, Tag, Comment, User, Broken invalide ; many_to_one, many_to_many avec
position dans pivot.fields, auto-relation User → User et User → Missing.
Deux processus Python -I distincts exécutent le parcours avec provenance installée
vérifiée et trois Tools seulement.

Chaque processus ouvre le projet puis visite /entities, q=article,
relation=many_to_many, severity=error&diagnostics=only, type=relation, un filtre vide,
les liens source extraits (entités, relations et Broken invalide), une requête invalide,
le retour à /entities et /routes. Les nombres de nœuds/arêtes/tableaux sont contrôlés.
Diagnostics entity.json_invalid et relation.entity_missing conservés ; relation
manquante visible, source lisible, aucun nœud absent inventé.
Contexte identique et fichiers/configuration inchangés après chaque GET.
Serveurs arrêtés, threads terminés, sockets fermés, ports réutilisables.
Script/journal ignorés : tmp/verify_fd_entities_008.py et .log.

## Packaging

Wheel : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `7adbc1b73328f264300be0b1c90e704d465e95b1c8550c326e1ac203f906aa60`.
Modules Bridge/Tool/diagnostics/filtres/graphe/layout/source, limits.py,
entities.html/source.html, entity-graph.js et shell.css inspectés et comparés
aux octets sources. Aucun tests/ ou tmp/ distribué. Installation réelle et deux
parcours HTTP réussis. Aucune dépendance nouvelle.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| git status ; git log --oneline --decorate -8 | Baseline conforme |
| git -C ../Forge ls-remote origin refs/heads/main | Baseline Forge identique |
| pytest -q --tb=short | 877 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Wheel installée, deux processus HTTP | Succès |

Outils .venv, Python 3.13.5 ; sockets locaux et build isolé exécutés hors sandbox.
Un premier test HTTP isolé en sandbox était bloqué par les sockets. La fixture
JSON initiale de profondeur 2000 ne provoquait pas RecursionError sous ce Python ;
profondeur 10000 vérifiée puis utilisée. Corrections de typage des listes de tests
avant contrôle final ; le dernier test modifié a été revérifié séparément.
Journal complet : tmp/pytest_fd_entities_008.log. Diff et nouveaux fichiers relus.

## Tests sautés

Aucun test pytest sauté. Suites Node historiques exécutées. Aucun navigateur réel
ou lecteur d’écran vérifié ; aucune mesure de performance murale fragile ajoutée.

## Limites restantes

Analyse JSON statique minimale, sans validation Forge exhaustive, DB, SQL, édition
ou génération. Décodage entier d’un document limité à 1 Mio ; volume cumulé possible
256 Mio d’entités + 1 Mio de relations, coût mémoire Python supplémentaire.
Sous-ensemble de découverte dépendant du filesystem au-delà de 4096 entrées.
Champs hors plafond non validés, compteurs limités aux faits disponibles.
Doublons établis parmi les seules données lues, égalité exacte ; première occurrence
conservée graphiquement. Aucun instantané filesystem global : un répertoire déjà
ouvert peut être renommé et son contenu changé. Layout simple, grands dessins,
segments partagés/croisements, interaction locale seulement. Source lexicalement
autorisée peut devenir absente ou illisible à l’ouverture.

## État Git final

Un seul commit local sur main, rapport inclus, aucun push conformément au ticket.
Message : `refactor: stabiliser Entity Explorer (FD-ENTITIES-008)`.
Le hash et l’état Git final sont communiqués dans la réponse de livraison.
