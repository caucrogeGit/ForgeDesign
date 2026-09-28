# Rapport — FD-ENTITIES-005

## Ticket et objectif

Projeter les EntityIssue existants en diagnostics structurés, sans nouvelle analyse,
avec compteurs et affichage serveur dans Entity Explorer.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `d9677d5` — FD-ENTITIES-004.
`git status` et les cinq derniers commits ont été inspectés avant modification.

## Architecture des diagnostics

`EntitiesResult` alimente indépendamment `build_entity_graph()` et
`build_entity_diagnostics()`. Cette dernière ne reçoit que le résultat déjà acquis.
Le modèle Route Explorer a été examiné : route_indices, source_available et
consolidation des occurrences sont spécifiques à son domaine. Deux modèles
indépendants évitent une généralisation artificielle et préservent ici les doublons.
Aucun changement Bridge, Tool, registre, graphe, layout, JavaScript ou route.

## Modèle EntityDiagnostic

Dataclass gelée : code, severity, message, source, subject et relation_index.
EntityDiagnostics est gelée et expose un tuple items ainsi que error_count,
warning_count et info_count. Les compteurs dérivent des sévérités des items.
La transformation conserve toutes les occurrences, erreurs puis avertissements,
dans l’ordre du Bridge ; aucun tri ni déduplication.

## Sévérités

DiagnosticSeverity est le Literal info/warning/error local au module.
Les issues de errors donnent error ; celles de warnings donnent warning,
indépendamment de leur code ou message. Aucun fait informatif n’est fabriqué :
info_count vaut zéro pour les résultats actuels du Bridge.

## Codes stables

Les onze codes sont conservés strictement et testés dans les deux sévérités :

- entity.source_missing, entity.unreadable, entity.json_invalid,
  entity.schema_version_unsupported, entity.structure_invalid ;
- relation.unreadable, relation.json_invalid,
  relation.schema_version_unsupported, relation.structure_invalid,
  relation.type_unsupported, relation.entity_missing.

Les tests historiques du Bridge restent actifs. Aucun renommage ou nouvelle
interprétation du code, aucune liste de rejet dans la projection.

## Sources et sujets

Message conservé tel quel ; source conservée avec son identité et sa ligne éventuelle.
Sans index, le sujet est source.path si disponible, sinon None. Avec source_index,
le sujet est relations[n] et relation_index conserve l’index, y compris zéro.
Ce sujet est conservé et affiché même en l’absence de source.
Les chemins sont textuels, sans lien ; /source reste inchangé.

## Diagnostic des entités

Les erreurs et avertissements déjà produits deviennent des éléments de liste
avec code et sévérité explicites. Aucun JSON relu et aucune recherche de nom
métier à partir du contenu ou du message. Pas de validation supplémentaire.

## Diagnostic des relations

Les indices du document sont conservés sans recherche par contenu dans les
relations interprétées. Une relation avec relation.entity_missing reste dans
result.relations et dans le tableau. Aucun diagnostic de cycle, doublon, FK ou SQL.

## Intégration Entity Explorer

Un seul appel Tool par GET. Les projections utilisent le même résultat ; le
contexte projet ne conserve aucun diagnostic. Sans projet, aucun résultat ou
diagnostic construit. Les exceptions globales du Tool gardent le traitement existant.
Les trois Tools enregistrés restent project-inspector, route-explorer, entity-explorer.

## Intégration Web

La section Diagnostics remplace Anomalies, avec trois compteurs, liste structurée,
sévérité visible, code, message, chemin et index éventuel. Sans anomalie :
« Aucun diagnostic dans les informations disponibles. » et trois compteurs à zéro.
Les attributs data-diagnostic-code, data-diagnostic-severity et l’index optionnel
préparent les futurs filtres ; aucun filtrage implémenté. GET conserve no-store.
Tableaux et graphe sont inchangés ; aucune association interactive aux diagnostics.

## Accessibilité

Section nommée via aria-labelledby, titre h2, liste ul/li, sévérités en texte
Erreur/Avertissement/Information et en gras. Aucun recours à la couleur seule,
aucun aria-live sur la section. Les styles existants suffisent : CSS inchangé.

## Pureté

Tests interdisant builtins.open, os.open/stat/listdir/scandir,
Path.open/read_text/read_bytes/stat/iterdir, json.loads/load, ToolRegistry.get et
read_entities pendant la transformation. Résultat déterministe et entrée inchangée.
Immutabilité des dataclasses et tuple vérifiés. Aucune dépendance Web, contexte,
registre, parseur JSON ou appel Forge dans le module.

## Sécurité

Jinja échappe les messages, chemins et attributs ; fixtures contrôlées avec balises,
guillemets et esperluette vérifiées via parsing HTML. Aucune injection de script,
source navigable, nouvelle lecture, écriture projet, requête ou exécution cible.
Aucun nouveau JavaScript, modification de CSP ou score/verdict global.

## Fichiers créés

- forge_design/tools/entity_diagnostics.py
- tests/test_entity_diagnostics.py
- tests/test_web_entity_diagnostics.py
- docs/rapports/FD-ENTITIES-005.md

## Fichiers modifiés

- forge_design/web/entities.py : projection du résultat déjà obtenu.
- forge_design/web/templates/entities.html : section Diagnostics.
- tests/test_entity_explorer.py : libellé Diagnostics attendu.
- tests/test_entity_relations.py : libellé Diagnostics attendu.
- docs/tools/entity-explorer.md : contrat utilisateur et codes.
- docs/02-architecture.md : projection pure indépendante.

## Tests ajoutés

26 cas pytest : 22 unitaires et 4 HTTP paramétrés.
Unitaires : vide, erreurs seules, warnings seuls, mélange, ordre, conservation des
codes/messages/sources, sujets, indices zéro et non nul avec ou sans source,
doublons, compteurs, information explicite du modèle, absence de mutation,
immutabilité, déterminisme et pureté. Les onze codes passent dans errors et warnings.
HTTP : compteurs exacts, ordre, codes, sévérités textuelles, sources, indices et
attributs DOM, échappement, absence de liens source/aria-live de section,
no-store, un seul appel Tool, sans projet, tableaux, graphe et script conservés.
Les tests historiques FD-ENTITIES-001 à 004 restent actifs ; seuls deux libellés
attendus changent de Anomalies à Diagnostics.

## Test réel

Copie temporaire de ../Forge/skeleton/data. Article et Tag sont créés avec le
constructeur canonique Forge ; Broken contient un JSON invalide. Relations :
Article → Tag et Article → Missing, toutes deux many_to_one interprétables.
Wheel installée dans un répertoire temporaire avec --no-deps --no-index --target.
Un processus Python -I vérifie l’origine installée du serveur et du module diagnostics.

GET /entities affiche entity.json_invalid et relation.entity_missing, deux erreurs,
zéro avertissement/information, sources et relations[1]. Les deux déclarations
restent dans les lignes du tableau, y compris Missing. Le SVG contient l’arête
interprétable, et le script interactif defer reste référencé.

Broken et la cible absente sont ensuite corrigés dans la fixture : le GET suivant
a zéro diagnostic et deux arêtes, sans cache. Comparaison des octets et mtime
avant/après chaque phase de consultation : aucune écriture du projet par l’application.
Route Explorer reste accessible. Configuration XDG temporaire ; serveur arrêté,
thread terminé, socket fermé et port réutilisable. Le dépôt Forge reste intact.
Script et journal ignorés : tmp/verify_fd_entities_005.py et .log.

## Packaging

Wheel reconstruite : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `2bb1fbf9ad9b4da40c3ebf74b2acdd36318358aab5d1d2ae65e3ff0633891a73`.
Archive inspectée : module diagnostics, template, CSS et JavaScript présents,
avec octets identiques aux sources ; tests/ et tmp/ non distribués.
Installation réelle et scénario HTTP réussis. Aucune dépendance ajoutée.

## Commandes exécutées et résultats

Outils de .venv, Python 3.13.5 ; Node disponible.

| Commande ou contrôle | Résultat final |
|---|---|
| git status ; git log --oneline --decorate -5 | Baseline conforme |
| pytest | 712 réussis, dont 26 nouveaux cas |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check forge_design/web/static/entity-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Installation temporaire, scénario HTTP depuis la wheel | Succès |

La première exécution pytest en sandbox a échoué sur les sockets locaux ; la
suite complète hors sandbox a réussi. La construction isolée de la wheel a
nécessité l’accès aux dépendances de build hors sandbox après un échec réseau.
Le scénario installé utilise également un serveur HTTP local autorisé hors sandbox.
Une variable inutilisée de test signalée par pyright a été corrigée avant validation.

## Tests sautés

Aucun test pytest sauté. Tests JavaScript historiques exécutés, syntaxe Node vérifiée.
Aucun test navigateur réel ou lecteur d’écran revendiqué ; vérification HTTP/DOM
et tests existants sur double DOM pour l’interaction du graphe.

## Limites restantes

Diagnostics limités aux faits déjà produits par le Bridge, sans validation Forge
exhaustive ni instantané atomique des fichiers. Pas de filtre, score, verdict,
navigation source ou association aux nœuds. Aucun info produit artificiellement.
Les limites existantes du graphe et de son accessibilité navigateur sont inchangées.

## État Git final

Un seul commit local sur main, rapport inclus, sans push conformément au ticket.
Message : `feat: structurer les diagnostics Entity Explorer (FD-ENTITIES-005)`.
Le hash et l’état Git après commit sont communiqués dans la réponse de livraison.
