# Rapport — FD-PROJECT-003

## Ticket et objectif

Conserver localement les dix derniers projets Forge ouverts avec succès, les proposer sur l’accueil après redémarrage et permettre leur réouverture ou retrait explicite. Le projet courant reste exclusivement runtime.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `51a3202` — FD-ROUTES-020.
État Git et cinq derniers commits inspectés avant modification.

## Emplacement de persistance

`resolve_user_config_dir()` et `recent_projects_file()` centralisent la résolution.
Base XDG_CONFIG_HOME si non vide et absolue, sinon `~/.config` ; suffixe fixe `forge-design/recent-projects.json`.
Une valeur XDG relative est ignorée pour ne jamais dépendre du cwd. Pas de chemin propre au dépôt, ni de répertoire .forge-design dans les projets.
Le fichier est injectable dans `RecentProjects(path=...)`. L’ajout/refus de mutation vérifie que son emplacement ne se trouve pas sous la racine concernée ou celles déjà enregistrées.

## Format du fichier

JSON UTF-8 versionné : `{"version": 1, "projects": ["/chemin/canonique"]}`.
Aucun diagnostic, version Forge, timestamp, préférence ou état courant. Version entière stricte ; version inconnue, champs supplémentaires et liste mal formée sont refusés sans conversion.
Les chaînes doivent être absolues, lexicalement normalisées, sans NUL, encodables en UTF-8 et limitées à 4096 caractères. Ces contrôles ne consultent pas les chemins projet.

## Modèle RecentProjects

Module indépendant du Web : `forge_design/recent_projects.py`.
`RecentProject(path: str)` est gelé ; `RecentProjects.list()` expose un tuple immuable, `add(Path)` et `remove(Path)` effectuent les mutations. Le champ warning rend les échecs de lecture consultables ; les mutations lèvent RecentProjectsError en cas d’échec.
Le contrat d’add reçoit une racine canonique issue d’une inspection valide. L’intégration Web transmet exclusivement `ProjectInspection.root`, jamais directement le texte soumis.
Chaque application construit ou reçoit son store au point de composition ; aucun singleton. CurrentProjectContext n’est pas modifié.

## Lecture

Lecture au démarrage du store puis lors des consultations et avant chaque mutation. Aucun Project Inspector automatique, aucune vérification de présence des projets mémorisés.
Fichier absent : tuple vide, aucun dossier créé. JSON incorrect, nombre JSON excessif, version inconnue, Unicode invalide, mauvais type ou accès refusé : liste vide avec avertissement contrôlé.
Limite 64 Kio contrôlée par taille déclarée puis lecture bornée à la limite plus un octet. Une mutation relit le fichier et refuse d’écraser un fichier devenu invalide depuis la construction du store.
Les entrées dupliquées ou les listes de plus de dix éléments sont considérées comme un format invalide, sans réparation silencieuse.

## Écriture atomique

Création exclusive d’un temporaire dans le même dossier, écriture UTF-8, flush puis fsync du fichier, remplacement via os.replace avec descripteurs du dossier.
Le fichier existant reste inchangé si le remplacement échoue. Le temporaire créé par l’opération est supprimé en sortie, succès ou erreur contrôlée. Une collision de nom temporaire ne supprime jamais le fichier préexistant.
Dossiers manquants créés en 0700 et nouveau fichier en 0600, sous réserve de l’umask ; aucune modification des permissions des dossiers existants.
Aucun verrou interprocessus : atomicité du fichier, pas fusion de mises à jour concurrentes ni garantie complète face à une coupure électrique.

## Déduplication et limite

MAX_RECENT_PROJECTS vaut 10. L’ajout retire l’occurrence existante, place la racine en tête et garde les dix premières entrées. L’ordre représente la récence.
La suppression d’une entrée absente est idempotente et n’écrit pas le fichier. Aucune suppression automatique d’un projet disparu ou invalide.

## Intégration projet courant

Inspector valide d’abord l’ouverture puis définit le contexte courant. L’enregistrement des récents est tenté ensuite ; un échec affiche un avertissement dans la page Inspector sans annuler le projet valide.
L’extraction du traitement `inspect_path` permet de partager exactement ce comportement avec la réouverture d’un récent. Une inspection invalide ou une erreur de racine conserve le contexte précédent.
Actualisation et fermeture ne changent pas les récents. Un redémarrage construit toujours un contexte vide.

## Ouverture d’un récent

POST /project/open-recent reçoit le champ recent. Après contrôle d’origine et de format, le serveur vérifie son appartenance exacte à la liste relue depuis le store.
Un chemin fabriqué non enregistré est refusé avec 400 avant appel au Tool. L’ouverture arbitraire demeure dans le formulaire Inspector.
Une entrée acceptée passe à ProjectInspectorTool ; les erreurs et résultats sont rendus par la page Inspector existante. Une ouverture valide remonte la racine canonique en tête. Un récent disparu ou devenu invalide reste enregistré jusqu’au retrait explicite.

## Suppression

POST /project/recent/remove applique les mêmes contrôles et retire uniquement l’entrée enregistrée. Le projet courant reste ouvert, ses fichiers et son diagnostic ne sont pas modifiés.
Un échec d’écriture est affiché sur l’accueil. Les GET sur ces actions ne mutent rien et sont refusés par le routeur.

## Sécurité

Réutilisation de is_local_action, sans duplication de sa logique : Origin égal exactement à l’origine locale et Sec-Fetch-Site absent ou same-origin. Les routes POST sont explicitement csrf=False dans le modèle local sans session ; les middlewares restent inchangés.
Il s’agit d’une protection contre les soumissions de pages étrangères, pas d’une authentification des programmes locaux capables de fabriquer des en-têtes.
La lecture de configuration exige un fichier ordinaire et refuse les liens fichier et parents. Le parcours des dossiers est ancré par descripteurs avec O_DIRECTORY/O_NOFOLLOW ; ouverture du fichier avec O_NOFOLLOW/O_NONBLOCK, puis comparaison des métadonnées. Les fichiers spéciaux ne sont pas lus.
Le stockage sécurisé est signalé indisponible si les drapeaux nécessaires manquent ; aucun repli suivant les liens. La cible du remplacement n’est pas suivie.
Les chemins affichés passent par l’échappement Jinja. Aucune télémétrie, requête externe, exécution de code projet ou écriture de fichier projet.
Les tests utilisent une configuration XDG temporaire par défaut grâce à tests/conftest.py, ou un chemin explicitement injecté. Le vrai fichier utilisateur n’est pas utilisé par les contrôles automatisés.

## Intégration Web

L’accueil ajoute Projets récents, l’état « Aucun projet récent. », les formulaires Ouvrir/Retirer et l’indication « Ouvert » pour le projet courant. Inspector conserve son rôle d’ouverture d’un nouveau chemin.
Le store est injecté dans create_application ; create_server propose la même injection pour les tests. Les instances avec fichiers différents restent isolées.
Accueil et réponses d’actions conservent Cache-Control: no-store. Aucun JavaScript, CSS, Tool, dépendance ou middleware ajouté.

## Persistance entre redémarrages

Test HTTP : application A ouvre deux projets et enregistre leurs racines ; application B utilise le même fichier mais démarre avec « Aucun projet ouvert. ». Une autre application avec un autre store reste indépendante.
Le contrôle installé exécute aussi deux processus Python distincts : le premier ouvre et écrit, le second charge l’historique sans rouvrir, puis réouvre et retire explicitement le projet.

## Fichiers créés

- forge_design/recent_projects.py
- forge_design/web/recent_projects.py
- tests/conftest.py
- tests/test_recent_projects.py
- tests/test_web_recent_projects.py
- docs/features/recent-projects.md
- docs/rapports/FD-PROJECT-003.md

## Fichiers modifiés

- forge_design/web/inspector.py : traitement partagé et ajout après succès.
- forge_design/web/server.py : composition, injection et deux POST.
- forge_design/web/templates/index.html : liste et formulaires échappés.
- docs/02-architecture.md : séparation runtime/persistance et contrat de stockage.

Aucune modification de CurrentProjectContext, du Bridge, du registre, des dépendances ou de package-data.

## Tests ajoutés

38 nouveaux cas : 26 de stockage et 12 Web/composition.
Stockage : fichier absent et liste vide, Unicode, ajout, déduplication/remontée, limite dix, suppression et idempotence, redémarrage, permissions, JSON invalide ou excessif, version inconnue, taille, symlinks fichier/parent, répertoire/FIFO, échec de remplacement, nettoyage, collision temporaire, absence d’inspection au chargement, refus sous projet et plateforme indisponible.
Web : canonisation de la saisie, accueil, réouverture, ordre, redémarrage sans projet courant, isolation de deux stores, disparu/invalide avec conservation du contexte et de l’historique, retrait sans fermeture, valeurs fabriquées, origine étrangère et cross-site pour les deux actions, format incorrect, GET non mutant, no-store, échappement de guillemets et HTML, échec d’écriture non bloquant et inspection invalide non enregistrée.
Les tests historiques restent actifs. Le premier test d’échappement attendait une autre notation d’entité pour le guillemet ; il vérifie désormais le DOM HTML parsé et la conservation exacte des valeurs, sans imposer cette notation.

## Test réel

Copie temporaire du squelette Forge ; XDG_CONFIG_HOME pointe sur un autre dossier temporaire.
Premier processus installé : accueil vide, POST Inspector avec chemin contenant mvc/.., JSON avec racine canonique uniquement, indication Ouvert et Route Explorer fonctionnel.
Second processus installé : contexte vide mais récent présent ; POST open-recent valide, remontée, puis retrait. Le JSON devient une liste vide tandis que le contexte reste ouvert ; fermeture explicite ensuite.
Comparaison de l’ensemble des fichiers, tailles, octets et dates de modification de la copie après chaque processus : identiques. Aucun changement du dépôt Forge de référence. Aucun temporaire de stockage résiduel ; serveurs arrêtés, sockets fermés et ports réutilisables.
Script et journal ignorés par Git : tmp/verify_fd_project_003.py et tmp/verify_fd_project_003.log.

## Packaging

Wheel reconstruite et inspectée : modules récents, template d’accueil mis à jour, CSS/JS existants présents ; aucun fichier tests/ ou tmp/ distribué.
Installation temporaire avec --no-deps --no-index --target. Chaque processus utilise -I, vérifie l’origine installée de Forge Design et utilise les dépendances runtime de .venv.
Artefact : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `87de31c255c44fe9a33730cc6f9b384a95dcf6985fc9d3800841c417bc344bab`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| État Git et cinq derniers commits | Vérifiés |
| pytest | 584 réussis, dont 38 nouveaux cas |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip check | No broken requirements found |
| git diff --check | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Wheel installée, deux processus et persistance HTTP | Succès |

Outils .venv, Python 3.13.5 ; HTTP avec autorisation de sockets locaux hors sandbox.
Annotations de parsing JSON et de contextmanager ajustées aux exigences Pyright, puis formatage Ruff corrigé. Pip a désactivé son cache utilisateur inaccessible sans erreur de dépendances.
Diff complet, nouveaux fichiers, documentation et rapport relus avant commit.

## Tests sautés

Aucun test pytest sauté. Aucun contrôle visuel navigateur, exécution du projet cible ou utilisation de la configuration utilisateur réelle revendiqué.

## Limites restantes

Stockage local nécessitant les primitives POSIX utilisées, sans synchronisation cloud ni verrou multi-processus. Dernier écrivain en cas de modifications concurrentes ; un arrêt brutal peut laisser un temporaire, sans transformation de celui-ci en historique valide.
Les chemins récents décrivent des usages passés, pas leur validité actuelle. Un fichier incompatible requiert une intervention manuelle ; pas de migration ou réparation automatique.
La protection hors projet vérifie les racines connues sans scan global du disque. L’utilisateur choisit son emplacement XDG ; le module ne découvre pas les autres projets potentiellement présents ailleurs.
Le contexte courant reste partagé entre les clients de la même instance selon le contrat existant, et disparaît à l’arrêt. Aucun workspace général, préférence persistante ou réouverture automatique.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `feat: ajouter les projets récents persistants (FD-PROJECT-003)`.
Le hash et l’état final sont communiqués dans la réponse de livraison.
