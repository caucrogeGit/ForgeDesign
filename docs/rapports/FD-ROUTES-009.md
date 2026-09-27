# Rapport — FD-ROUTES-009

## Ticket et objectif

Vérifier les métadonnées des dépendances Jinja directes statiques sous `mvc/views`, sans lire leur contenu, les parser ou suivre leurs propres dépendances.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `7ab366e` — FD-ROUTES-008.
`git status` et `git log --oneline --decorate -5` exécutés avant modification.

## Modèle de présence des dépendances

`TemplateDependency` reste gelée et ajoute `presence: TemplatePresenceStatus = "not-applicable"`.
Le type existant du template principal est réutilisé : `present`, `missing`, `invalid-path`, `unreadable`, `not-applicable`.
Type de déclaration, chemin source, caractère dynamique et ligne restent identiques. Les constructions à quatre arguments sont préservées.

## Réutilisation de la politique de chemin

La primitive `_template_presence` de FD-ROUTES-006 est appelée pour les deux usages : aucun second validateur.
Racine fixe `<projet>/mvc/views`, sans lecture de configuration ou de `VIEWS_DIR`.
La référence est conservée telle quelle ; les chemins absolus, traversals, segments vides ou point, antislashs, deux-points et NUL restent refusés avant accès.
Aucun fallback ni recherche de cible alternative.

## Vérification filesystem

`lstat` vérifie les parents comme dossiers ordinaires puis la cible comme fichier ordinaire.
Absence : `missing`. Lien ou mauvais type : `invalid-path`. Autre `OSError`, dont permission refusée : `unreadable`.
Les autres exceptions restent propagées.
Les quatre types de déclaration utilisent le même traitement. Chaque candidat statique d’une liste d’include reçoit son propre statut.
Aucun contenu de dépendance ouvert, décodé ou parsé ; un fichier non UTF-8 ou Jinja invalide peut être présent.

## Dépendances dynamiques

`dynamic=True` ou chemin absent conserve `not-applicable`, sans contrôle filesystem pour cette déclaration.
Le libellé dynamique reste affiché. Aucune résolution de variable ou expression.

## Cache local

Un dictionnaire de présence par référence exacte est partagé entre toutes les dépendances et les templates principaux du `read_routes` courant.
Les erreurs sont également mémorisées. Les occurrences ne sont pas dédupliquées, seul leur contrôle est mutualisé.
Le cache des résultats de syntaxe/extraction reste distinct et conserve son rôle.
Si une dépendance correspond aussi au template principal d’une autre route, sa présence est réutilisée ; sa lecture éventuelle relève uniquement de cette route principale.
Le contrôle du descripteur lors d’une lecture principale reste conservé. Aucun cache persistant.

## Intégration Bridge

`read_routes(...) -> RoutesResult` et les API des Tools restent inchangés.
L’enrichissement s’applique aux dépendances issues de l’AST déjà validé et conserve tous les champs antérieurs, l’ordre, les doublons et les lignes.
Aucune alerte systématique nouvelle ; les statuts suffisent.
Aucun changement d’Inspector, registre ou contexte projet.

## Intégration Web

La liste sous la cellule Template ajoute le libellé de présence après chaque référence : Présent, Absent, Chemin refusé ou Non vérifiable.
Les références dynamiques gardent leur libellé et une présence « — ».
Aucune colonne, route HTTP ou action nouvelle. Échappement Jinja et `Cache-Control: no-store` conservés.

## Sécurité

Références exclusivement issues de l’AST du template principal valide, politique de confinement partagée, liens internes et externes refusés.
Aucun scan, chargement Jinja, lecture de contenu dépendant, parsing récursif, rendu ou écriture projet.
Les vérifications supposent des parents stables pendant l’appel, comme les contrôles de présence précédents.

## Fichiers créés

- [docs/rapports/FD-ROUTES-009.md](FD-ROUTES-009.md).

## Fichiers modifiés

- [forge_design/forge/routes.py](../../forge_design/forge/routes.py) : présence des dépendances et cache partagé.
- [forge_design/web/templates/routes.html](../../forge_design/web/templates/routes.html) : libellés par dépendance.
- [tests/test_routes.py](../../tests/test_routes.py) : présence, refus, erreurs et cache.
- [tests/test_web_inspector.py](../../tests/test_web_inspector.py) : affichage des statuts.
- [docs/02-architecture.md](../02-architecture.md) : contrat et limites.

Aucune dépendance ou métadonnée de distribution modifiée.

## Tests ajoutés

14 nouveaux cas : 13 scénarios de présence et un test de cache partagé.
Les quatre déclarations, absence, sous-dossiers, chemins absolus Unix/Windows, traversal, fichier lié, parent lié, répertoire cible, permission refusée et référence dynamique sont couverts.
Une sentinelle limite les ouvertures aux sources de routes, contrôleurs et templates principaux ; les dépendances contiennent du Jinja invalide et des octets non UTF-8.
Le cache est exercé avec deux templates principaux, plusieurs références identiques, une liste d’include aux statuts différents et une cible également principale : une vérification de présence par référence et par appel, puis une nouvelle vérification à l’appel suivant.
Scan et ouvertures haut niveau sont interdits pendant le contrôle ; contenus et dates de modification sont comparés.
Les tests existants continuent de vérifier parsing unique, extraction unique, absence de loader/rendu et ordre des déclarations.
Le test HTTP existant est enrichi : Présent, Absent, Chemin refusé, dynamique, échappement et `no-store`.
Une suppression Pyright locale `reportPrivateUsage` instrumente uniquement la primitive de présence dans le test du cache.

## Test réel

Wheel construite, archive inspectée puis installation temporaire sans dépendances dans un processus Python isolé (`-I`), origine des imports vérifiée. Le runtime provient de `.venv`.
Une copie du squelette reçoit la vue contact déclarant `extends "base.html"` et `include "contacts/_table.html"`.
Seul `mvc/views/base.html` est créé initialement, avec contenu non UTF-8 : le GET affiche Présent pour extends et Absent pour include.
Après création de `_table.html` avec syntaxe Jinja volontairement invalide, le GET suivant affiche Présent pour include, tandis que le template principal reste Valide.
Aucun changement du dépôt Forge de référence ; serveur arrêté, socket fermé et port réutilisable.
L’interdiction d’ouverture des cibles est instrumentée dans les tests unitaires.

Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `52de08db85b62a4b33cb9325931133c8207a1e27f4d6d8a07e4dee3ddc275d94`.
Script ignoré par Git : `tmp/verify_fd_routes_009.py`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| État Git et historique | Vérifiés |
| `pytest` | 357 tests réussis, dont 14 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| `python -m pip wheel --no-deps --wheel-dir tmp/wheels .` | Succès |
| Wheel installée et HTTP Absent puis Présent | Succès |

Outils de `.venv`, Python 3.13.5 ; sockets locaux autorisés hors sandbox.
Pip a désactivé son cache utilisateur inaccessible dans le sandbox, sans erreur de dépendances.
Le diff complet est relu avant commit, rapport compris.

## Tests sautés

Aucun test pytest sauté. Aucun rendu cible, parsing de dépendance, contrôle visuel navigateur ou nouvelle génération Forge revendiqué.

## Limites restantes

Présence sous `mvc/views` ne garantit ni résolution runtime avec un `VIEWS_DIR` personnalisé, ni syntaxe valide, ni rendu réussi.
Aucun suivi transitif, résolution de dynamique ou détection de cycles.
Les résultats restent des instantanés soumis aux limites de stabilité filesystem du Bridge.

## État Git final

Un seul commit local sur `main`, rapport inclus, sans push.
Message : `feat: vérifier les dépendances Jinja directes (FD-ROUTES-009)`.
Le hash et l’état Git après commit sont communiqués dans la réponse de livraison.
