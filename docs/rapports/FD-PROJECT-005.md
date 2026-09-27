# Rapport — FD-PROJECT-005

## Ticket et objectif

Centraliser la sélection explicite du projet courant et rendre l’accueil après ouverture d’un récent, sans ouverture automatique ou nouvelle persistance.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `9d42471` — FD-PROJECT-004.
État Git et cinq derniers commits inspectés avant modification.

## Modèle ProjectSelectionResult

Dataclass gelée : status, inspection optionnelle, error optionnelle et recent_warning optionnel.
Les états selected, invalid, not-found, not-directory et resolution-error distinguent les résultats sans interprétation des messages par le Web.
Le détail de résolution est conservé pour Inspector ; l’accueil utilise un message sobre.

## ProjectSelector

Service indépendant du Web dans forge_design/project_selector.py. Dataclass gelée contenant uniquement les trois dépendances explicites : registre, contexte et store.
`open(Path)` récupère `registry.get("project-inspector")`, exécute l’inspection puis applique les mutations autorisées. Aucun singleton, cache ou état de sélection supplémentaire.
Le mauvais type de résultat produit le TypeError historique. Les exceptions inattendues sont propagées.

## Sélection réussie

Une inspection valide active d’abord le contexte, puis tente l’ajout dans les récents.
La racine sélectionnée et persistée est exclusivement ProjectInspection.root, jamais le chemin soumis.
L’échec contrôlé du store donne recent_warning sans annuler selected.

## Gestion des échecs

Inspection invalide : invalid avec son diagnostic détaillé, sans mutation.
Les trois exceptions de résolution existantes deviennent respectivement not-found, not-directory et resolution-error, sans changer contexte ou historique.
Aucun catch général. Les erreurs inattendues de programmation ou de Tool restent diagnostiquables.

## Intégration CurrentProjectContext

Le service remplace le courant uniquement après validation. Aucune modification du modèle CurrentProjectContext.
Actualisation et fermeture restent distinctes, avec leur comportement historique. Aucun GET ni démarrage ne sélectionne un projet.

## Intégration RecentProjects

Le store conserve son format, sa déduplication, sa limite et sa politique d’écriture atomique.
Une sélection valide remonte la racine canonique en tête. Une erreur de validation laisse le fichier inchangé ; une erreur d’enregistrement ne ferme pas le nouveau courant.

## Intégration Inspector

Le handler valide l’origine et le formulaire, appelle selector.open, puis rend le résultat.
L’ancienne orchestration inspect_path est supprimée. Inspector conserve inspection détaillée, messages de résolution, avertissement d’historique et statuts HTTP existants.
L’actualisation appelle toujours directement Inspector puisqu’elle ne sélectionne pas un autre projet et ne modifie pas les récents.

## Intégration projets récents

L’appartenance exacte au store relu est contrôlée avant appel du selector.
Succès : accueil avec « Projet ouvert. », indication « Ouvert », ordre actualisé et navigation existante vers les Tools.
Échec : « Le projet récent n’est plus disponible. », accueil conservé, sans suppression de l’entrée ni remplacement du courant. Le statut historique reste 200 pour une structure invalide et 400 pour les erreurs de racine.
L’avertissement de persistance est passé explicitement au rendu pour survivre à la relecture du store par l’accueil.
Le calcul des états d’affichage FD-PROJECT-004 reste indépendant et peut réinspecter les récents au rendu, sans activation.

## Composition

create_application construit un ProjectSelector après registre, contexte et store ; Inspector et open-recent partagent cette instance.
Chaque application construit son propre selector et contexte. Les stores injectés peuvent rester indépendants.
Aucune route ou dépendance ajoutée.

## Sécurité

Contrôles is_local_action, formulaire, appartenance aux récents et csrf=False explicite inchangés. Un chemin fabriqué est refusé avant sélection.
Messages échappés par Jinja, no-store conservé. Aucun import ou exécution du projet, scan, édition ou paramètre HTTP supplémentaire.

## Non-écriture projet

Le service ne possède aucune primitive d’écriture projet. Ses mutations passent uniquement par set_project et RecentProjects.add.
Les tests de refus comparent octets et mtime du JSON ; les tests existants de non-écriture des GET restent actifs.
Le contrôle installé compare l’ensemble des fichiers, octets et mtime des deux copies Forge après les ouvertures et le changement de courant. La suppression volontaire de B est réalisée uniquement par le scénario de test, puis A est vérifié inchangé.

## Fichiers créés

- forge_design/project_selector.py
- tests/test_project_selector.py
- tests/test_web_project_selector.py
- docs/rapports/FD-PROJECT-005.md

## Fichiers modifiés

- forge_design/web/inspector.py : délégation et présentation du résultat.
- forge_design/web/recent_projects.py : sélection et retour accueil.
- forge_design/web/server.py : composition du service partagé.
- forge_design/web/templates/index.html : succès et avertissement de sélection.
- tests/test_web_recent_projects.py : attentes adaptées au retour accueil.
- docs/02-architecture.md : responsabilité du selector.
- docs/features/recent-projects.md : sélection explicite depuis l’accueil.

## Tests ajoutés

Neuf nouveaux cas : huit de service et une sentinelle HTTP/composition.
Les tests couvrent succès, racine canonique, remplacement, remontée, immutabilité, isolation, ordre contexte avant persistance, échec du store, quatre échecs métier, exception inattendue et mauvais type de résultat.
La sentinelle remplace open et interdit registry.get, set_project et add dans les handlers. L’inspection d’affichage indépendante est neutralisée uniquement dans ce test. Les deux formulaires utilisent la même instance ; une autre application en utilise une autre. GET, chemin fabriqué, origine étrangère et cross-site ne déclenchent aucune sélection.
Elle vérifie aussi le retour accueil, succès, échappement du warning et no-store.
Les tests historiques conservent les scénarios réels de succès Inspector, racines invalides, avertissement d’écriture, récence, disparition/invalidation entre GET et POST, contexte et historique conservés, isolation et redémarrage.

## Test réel

XDG temporaire et deux copies du véritable squelette Forge. Wheel installée, origine importée vérifiée dans un processus Python -I.
Ouverture de A puis B par Inspector avec chemins mvc/.. : racines canoniques enregistrées dans l’ordre B, A.
Ouverture de A depuis les récents : accueil, message, courant A, ordre A, B. Les deux projets restent identiques.
Suppression volontaire de B puis tentative d’ouverture : erreur propre 400, A toujours courant et JSON inchangé contenant encore B.
Une nouvelle application recharge l’historique sans courant. Serveurs arrêtés, threads terminés, socket fermé et port réutilisé. Dépôt Forge de référence intact.
Script et journal ignorés : tmp/verify_fd_project_005.py et tmp/verify_fd_project_005.log.

## Packaging

Wheel reconstruite et inspectée : module ProjectSelector et template d’accueil présents ; aucun tests/ ou tmp/ distribué. Installation temporaire --no-deps --no-index --target, runtime de .venv.
Artefact : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `bec44703912f86d9e7fb211d9180dd98b6a0b55471a5ba11f6f4cfa9f89856f3`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| État Git et cinq derniers commits | Vérifiés |
| pytest | 600 réussis, dont 9 nouveaux cas |
| Tests ciblés après derniers ajustements | 21 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip check | No broken requirements found |
| git diff --check | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Wheel installée et parcours HTTP A/B/A/échec/redémarrage | Succès |

Outils .venv, Python 3.13.5 ; HTTP avec sockets locaux autorisés hors sandbox.
Imports, lignes longues et annotation de la sentinelle d’affichage ont été corrigés avant validation finale. Pip check a désactivé son cache utilisateur inaccessible, sans erreur de dépendances.
Diff complet, nouveaux fichiers, documentation et rapport relus avant commit.

## Tests sautés

Aucun test pytest sauté. Aucun contrôle visuel navigateur ou exécution du projet cible revendiqué.

## Limites restantes

Le service gèle ses références mais ses dépendances restent volontairement mutables. La sélection runtime et l’écriture de l’historique ne forment pas une transaction : un échec de persistance laisse le courant sélectionné.
Les états d’accueil restent des instantanés ; la sélection réinspecte systématiquement. Les limites filesystem, de concurrence du store et de contexte partagé entre clients locaux restent applicables.
Aucun cache de sélection, restauration de session ou ouverture automatique.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `refactor: centraliser la sélection de projet (FD-PROJECT-005)`.
Le hash et l’état final vérifiés sont communiqués dans la réponse de livraison.
