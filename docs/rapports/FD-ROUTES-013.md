# Rapport — FD-ROUTES-013

## Ticket et objectif

Analyser les dépendances Jinja transitives statiques avec des bornes explicites, sans rendu ni diagnostic métier de cycle. Le graphe visuel reste direct.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `bd0038c` — FD-ROUTES-012.
État Git et cinq derniers commits inspectés avant modification.

## Modèle d’analyse transitive

`TemplateResolution` ajoute `dependency_graph`, optionnel par défaut pour conserver les constructions existantes.
`TemplateDependencyGraph` gelé expose root, templates et truncated.
Chaque `TemplateNodeInfo` gelé expose path, presence, syntax et un tuple des dépendances locales. Le chemin du nœud donne la source ; chaque déclaration conserve cible, type, ligne et caractère dynamique.
La représentation est plate, sans objets enfants récursifs. Les références dynamiques restent des déclarations sans nœud cible.

## Algorithme de parcours

Les templates principaux et leurs dépendances directes sont traités en priorité, dans l’ordre des routes, pour conserver les informations directes existantes hors atteinte des limites.
Chaque racine est ensuite parcourue en largeur avec deque, dans l’ordre source des déclarations. Ce choix atteint chaque nœud par sa plus courte distance et évite qu’un chemin long bloque un chemin plus court.
Les références statiques sont contrôlées par le pipeline existant ; seules celles présentes et syntaxiquement valides fournissent de nouvelles déclarations. Absence, refus ou syntaxe invalide restent terminaux et visibles.

## Profondeur maximale

`MAX_TEMPLATE_DEPTH = 8`, principal à profondeur 0.
Le niveau 8 est lu, parsé et extrait ; ses déclarations restent connues mais leurs cibles ne sont pas contrôlées au titre de cette expansion. Un warning de profondeur est émis une seule fois par appel, et truncated vaut vrai.
Une autre route principale peut légitimement analyser la même cible dans sa propre limite.

## Limite globale

`MAX_VISITED_TEMPLATES = 128` par read_routes, références exactes distinctes, y compris les références absentes ou refusées.
Au-delà, aucune nouvelle vérification filesystem, lecture ou parsing. Les déclarations restent exposées avec statuts non applicables ; les résultats déjà acquis sont conservés.
Un warning global unique indique la limite. Les fermetures concernées portent truncated.
Cette borne de sécurité prime également sur les contrôles directs lorsque le projet comporte plus de 128 références ; la priorité aux données directes réduit l’effet de l’expansion transitive sur leur disponibilité.

## Gestion des revisites

Un ensemble discovered par racine empêche d’enfiler deux fois un même chemin. Toutes les relations entrantes restent dans les déclarations des nœuds sources, doublons compris.
Les caches communs à l’appel évitent les lectures, parsings et extractions répétés entre chemins et entre racines.

## Préparation aux cycles

Une référence est marquée découverte dès son insertion dans la file, avant expansion. L’état en attente ou traité se déduit de la file et de l’ensemble ; aucune récursion Python.
La relation de retour a → b → a reste dans les données sans réenfiler a. Aucun message « cycle détecté » ni classification de cycle.

## Cache local

Cache de présence/parsing existant conservé ; cache d’extraction ajouté par référence exacte. Les succès et échecs sont mutualisés.
Chaque fermeture utilise ces résultats immuables sans nouvelle analyse. Un nouvel appel recommence les contrôles.
Le coût d’analyse des fichiers est linéaire dans les fichiers et relations visités ; la matérialisation des fermetures est répétée par racine distincte et proportionnelle à leurs résultats.

## Intégration Bridge

`read_routes(...) -> RoutesResult` inchangé. Les champs directs existants sont conservés ; l’analyse transitive est supplémentaire.
Aucun changement de Tool, registre, Web, RouteGraph ou layout SVG.

## Sécurité

Réutilisation de la validation sous mvc/views, lstat des parents, refus des liens et fichiers spéciaux, ouverture protégée et comparaison du descripteur.
Lecture limitée à 1 Mio, UTF-8 avec BOM accepté. Parsing Environment sans loader, sans compilation ni rendu. Les déclarations d’un template invalide ne sont jamais extraites.
Aucun scan, import cible ou écriture. Les limites existantes de stabilité des parents du filesystem restent applicables.

## Fichiers créés

- [tests/test_template_transitive.py](../../tests/test_template_transitive.py).
- [docs/rapports/FD-ROUTES-013.md](FD-ROUTES-013.md).

## Fichiers modifiés

- [forge_design/forge/routes.py](../../forge_design/forge/routes.py) : modèles, parcours et limites.
- [tests/test_routes.py](../../tests/test_routes.py) : autorisation d’extraction transitive et métadonnées des nouvelles cibles.
- [docs/02-architecture.md](../02-architecture.md) : contrat borné.

Aucune dépendance, ressource Web ou métadonnée de packaging modifiée.

## Tests ajoutés

Six cas nouveaux : chaînes de profondeur 2, 3 et au-delà de 8 ; diamant avec cycle ; cibles terminales à profondeur transitive ; limite globale réduite à 3 pour contrôle précis.
Ils vérifient ordre en largeur/source, warnings uniques, déclarations conservées aux limites, absence/dynamique/syntaxe invalide/traversal/symlink terminaux et fin du cycle sans diagnostic.
Le diamant compte une lecture, un parsing et une extraction par fichier, puis leur répétition au nouvel appel. Scan, loader, compilation et rendu sont interdits ; contenus et dates de modification sont comparés.
Les tests antérieurs sont adaptés à l’autorisation d’extraire les dépendances valides et de vérifier leurs cibles. Ils conservent les assertions de données directes et les protections de lecture.

## Test réel

Copie temporaire du squelette Forge, ajout d’une route contact et de cinq templates : contacts/list.html, base.html, contacts/_table.html, layouts/site.html et macros/forms.html.
Le Bridge retourne exactement les cinq templates dans l’ordre attendu et quatre relations. Après ajout d’un include de macros/forms.html vers contacts/list.html, il termine avec les mêmes cinq nœuds et cinq relations, sans diagnostic de cycle.
Le dépôt Forge de référence reste intact et la copie est nettoyée.
Script ignoré : `tmp/verify_fd_routes_013.py`, exécuté avec l’interpréteur de `.venv` et le checkout courant via PYTHONPATH.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat |
|---|---|
| État Git et historique | Vérifiés |
| Tests ciblés routes et analyse transitive | 139 réussis |
| `pytest` | 385 tests réussis, dont 6 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| Copie réelle Forge, fermeture puis cycle | Succès |

Outils de `.venv`, Python 3.13.5 ; suite HTTP avec autorisation de sockets locaux hors sandbox.
Les premiers tests ciblés ont signalé les attentes historiques de deux extractions seulement et de non-consultation des cibles transitives ; elles sont adaptées au nouveau contrat. Une ligne Ruff trop longue est corrigée.
Pip a désactivé son cache utilisateur inaccessible sans erreur de dépendances.
Le diff complet, rapport et nouveaux tests compris, est relu avant commit.

## Tests sautés

Aucun test pytest sauté. Wheel non reconstruite : ressources et métadonnées inchangées.
Aucun contrôle visuel, rendu cible ou nouvelle génération Forge revendiqué.

## Limites restantes

Bornes fixes internes, sans nouvelle option CLI. Au-delà des limites, les données sont explicitement partielles.
Les statuts non applicables d’une cible non contrôlée ne signifient pas qu’elle est absente.
Pas de diagnostic métier de cycle ni d’intégration graphique transitive. Les configurations personnalisées de loader et VIEWS_DIR restent hors contrat.
Les fermetures de plusieurs racines peuvent partager les mêmes nœuds logiques dans des tuples distincts ; leurs fichiers restent analysés une seule fois par appel.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `feat: analyser transitivement les templates Jinja (FD-ROUTES-013)`.
Le hash et l’état final sont communiqués dans la réponse de livraison.
