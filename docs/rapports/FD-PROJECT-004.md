# Rapport — FD-PROJECT-004

## Ticket et objectif

Présenter l’état actuel des projets récents sur l’accueil, sans ouverture automatique, modification du contexte courant ou nouvelle persistance.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `36088d7` — FD-PROJECT-003.
État Git et cinq derniers commits inspectés avant modification.

## Modèle d’état des récents

Module indépendant du Web `forge_design/recent_project_states.py`.
`RecentProjectState` est gelé : project, status, inspection optionnelle et is_current.
Les statuts sont available, missing, invalid et unavailable. Le résultat est un tuple dans l’ordre du store.
`RecentProject`, le format JSON et `CurrentProjectContext` restent inchangés.

## Inspection des récents

`inspect_recent_projects` reçoit le tuple du store, le registre et la racine courante optionnelle. Il ne reçoit ni store mutable ni contexte mutable.
Chaque rendu d’accueil inspecte séquentiellement les entrées existantes ; la borne de dix est garantie par le store. Aucun cache ou parallélisme.
La construction de l’application ne lance pas d’inspection. Une liste vide ne consulte même pas le registre.
Les erreurs contrôlées de résolution sont converties en états par entrée. Une erreur de résolution générale donne unavailable ; les autres entrées continuent. Une exception inattendue ou un résultat de Tool incorrect reste propagé.

## Projet disponible

Un résultat ProjectInspection valide donne available, même si sa version est inconnue.
L’accueil affiche « Disponible », puis « Forge <version> » ou « Version Forge indéterminée ».
Le bouton Ouvrir existe uniquement si ce projet n’est pas déjà courant.

## Projet introuvable

ProjectRootNotFoundError donne missing et « Projet introuvable ».
L’entrée reste dans l’historique, avec Retirer et sans formulaire d’ouverture.

## Projet invalide

Une inspection structurelle invalide ou ProjectRootNotDirectoryError donne invalid et « Projet non reconnu ».
Les détails Inspector ne sont pas copiés sur l’accueil. Retirer reste proposé, sans Ouvrir.
Une erreur contrôlée empêchant la résolution donne « Non disponible », selon la même politique d’actions.

## Projet courant

is_current compare le chemin mémorisé à la racine du contexte, sans actualiser son diagnostic.
La mention « Ouvert » et le retrait restent disponibles, sans bouton Ouvrir redondant.
Si le projet courant se dégrade sur disque, l’accueil peut afficher son nouvel état et « Ouvert » : le contexte runtime précédent n’est ni remplacé ni fermé.
Un redémarrage conserve les chemins mais commence toujours sans projet courant.

## Intégration ToolRegistry

Une recherche `registry.get("project-inspector")` par liste non vide, puis un appel run par entrée.
Aucune instanciation directe de ProjectInspectorTool dans le Web ni duplication des règles Forge.
Le registre construit par create_application est transmis au rendu de l’accueil, y compris après les actions existantes.
Le POST open-recent conserve sa réinspection indépendante : aucun résultat d’accueil ne sert d’autorisation ou de diagnostic mis en cache.

## Intégration Web

Le template affiche chemin, état, version pertinente et actions conditionnelles. Un attribut data-recent-status permet d’identifier chaque entrée dans les tests HTML.
L’ordre est conservé. Retirer fonctionne pour les disponibles, absents, invalides et pour le projet courant.
Les avertissements du store restent globaux et le reste de l’accueil reste affiché.
Aucune nouvelle route, paramètre HTTP, ressource CSS/JS, dépendance ou modification des middlewares. No-store conservé.

## Sécurité

Seuls les chemins lus dans le store sont inspectés, via les lecteurs existants du Project Inspector.
Aucun scan, import cible ou exécution de code projet ajouté. Les chemins et versions sont échappés par Jinja ; aucun contenu de fichier, traceback ou message technique d’erreur de résolution n’est exposé sur l’accueil.
Les contrôles d’origine, de formulaire et d’appartenance à l’historique des POST sont inchangés. Les états affichés restent des observations, pas une garantie de validité future.

## Non-écriture

Les nouveaux tests comparent les octets et dates de modification de tous les fichiers des projets temporaires et du JSON avant/après les GET, y compris après ouverture et dégradation du courant.
Le test du service vérifie l’identité du diagnostic courant, l’ordre du store et son fichier inchangé. Le service ne possède aucune référence lui permettant de modifier ces deux objets.
Le contrôle installé compare également l’ensemble des fichiers, tailles, octets et dates des projets après chacun des deux processus. Les écritures volontaires de retrait/ouverture restent limitées au JSON temporaire.

## Fichiers créés

- forge_design/recent_project_states.py
- tests/test_recent_project_states.py
- tests/test_web_recent_project_states.py
- docs/rapports/FD-PROJECT-004.md

## Fichiers modifiés

- forge_design/web/recent_projects.py : projection des états au rendu.
- forge_design/web/server.py : transmission du registre existant.
- forge_design/web/templates/index.html : états, versions et actions.
- tests/test_web_recent_projects.py : GET disponible avant suppression ou invalidation et tentative de réouverture.
- docs/features/recent-projects.md : comportement utilisateur.
- docs/02-architecture.md : distinction stockage, inspection d’état et contexte courant.

## Tests ajoutés

Sept nouveaux cas : quatre cas modèle et trois HTTP/composition.
Couverture groupée : quatre états, version connue/inconnue, ordre, courant identifié même après disparition, non-mutation, immutabilité, liste vide sans registre, exception inattendue et mauvais résultat propagés.
Les tests HTTP vérifient les formulaires par entrée avec HTMLParser, les versions, les labels, no-store, le courant dégradé conservé et le retrait de plusieurs états.
Un registre injecté avec un Tool contrôlé prouve son utilisation par l’accueil : zéro appel à la construction et pour la liste vide, exactement dix par GET non vide, puis dix nouveaux au GET suivant. Deux applications avec stores différents restent indépendantes.
Une erreur contrôlée n’empêche pas l’affichage de l’entrée suivante et son message interne n’est pas exposé.
Les tests FD-PROJECT-003 restent actifs pour l’échappement HTML, le store invalide préservé, l’accueil vide, les origines, le redémarrage et l’isolation. Les deux scénarios de réouverture après suppression/invalidation vérifient désormais qu’un GET précédent annonçait disponible.

## Test réel

Configuration XDG temporaire distincte des projets. Copie du véritable skeleton/data Forge, dossier existant non Forge et chemin absent enregistrés dans le JSON de test.
Premier processus installé : aucun courant initial, trois états corrects, un seul formulaire Ouvrir et trois Retirer ; le GET ne change pas le JSON.
Ouverture explicite du valide : « Ouvert », disparition du bouton Ouvrir correspondant et Route Explorer toujours accessible.
Retrait de l’absent : le courant reste ouvert, les deux autres entrées restent enregistrées.
Second processus : états recalculés mais aucun courant automatiquement rouvert.
Projets inchangés, serveurs arrêtés, sockets fermés et ports réutilisables. Le dépôt Forge de référence n’est pas modifié.
Script et journal ignorés par Git : tmp/verify_fd_project_004.py et tmp/verify_fd_project_004.log.

## Packaging

Wheel reconstruite et inspectée : nouveau module d’état, template mis à jour, CSS et JavaScript existants présents ; aucun tests/ ou tmp/ distribué.
Installation temporaire --no-deps --no-index --target. Deux processus Python -I vérifient l’origine installée de Forge Design ; runtime fourni par .venv.
Artefact : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `e0855f10b05c281d2fd515770587eb516d59128ca4bc38d6379c884156cd6d8e`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| État Git et cinq derniers commits | Vérifiés |
| Tests ciblés états et récents | 19 réussis |
| pytest | 591 réussis, dont 7 nouveaux cas |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip check | No broken requirements found |
| git diff --check | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Wheel installée, états et actions HTTP, redémarrage | Succès |

Outils .venv, Python 3.13.5 ; sockets locaux autorisés hors sandbox.
Le nom du paramètre du double de Tool a été aligné sur le protocole signalé par Pyright ; imports et formatage de tests corrigés avec Ruff. Pip check a désactivé son cache utilisateur inaccessible, sans erreur de dépendances.
Diff complet, fichiers nouveaux, documentation et rapport relus avant commit.

## Tests sautés

Aucun test pytest sauté. Aucun contrôle visuel navigateur ni exécution du projet cible revendiqué. La vérification de dix appels utilise un Tool contrôlé ; le test installé utilise le véritable Inspector sur trois entrées puis deux au redémarrage, sans benchmark.

## Limites restantes

États recalculés à chaque accueil, sans cache : jusqu’à dix inspections séquentielles. Un filesystem lent reste susceptible de ralentir la réponse.
Les observations peuvent devenir obsolètes immédiatement ; l’ouverture réinspecte toujours. Les limites des lecteurs Forge et du stockage FD-PROJECT-003 restent applicables.
L’indication courant décrit le contexte runtime, même si les fichiers ont changé. Aucun état persisté, actualisation automatique du courant, scan ou réparation de l’historique.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `feat: afficher l’état des projets récents (FD-PROJECT-004)`.
Le hash et l’état final vérifiés sont communiqués dans la réponse de livraison.
