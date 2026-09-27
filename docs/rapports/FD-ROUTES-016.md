# Rapport — FD-ROUTES-016

## Ticket et objectif

Ajouter des références source structurées et des liens internes vers une vue en lecture seule, confinée aux espaces source autorisés du projet courant.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `f3c2b90` — FD-ROUTES-015.
État Git et cinq derniers commits inspectés avant modification.

## Modèle SourceLocation

Dataclass gelée dans forge/source.py : path relatif, line optionnelle.
Les champs optionnels sont ajoutés à la fin des modèles existants, avec None par défaut. Les constructions Python antérieures restent valides.
Les références logiques ne prouvent pas qu’un fichier est toujours présent ; les statuts de présence existants restent la référence pour proposer un lien.

## Sources des routes

RouteInfo.source utilise le nom réel transmis au parseur et call.lineno.
La racine conserve mvc/routes/__init__.py ; une fonction explicitement branchée conserve mvc/routes/<module>.py. Les appels de groupe suivent le même contrat.
La référence du handler dans les routes est couverte par cette localisation, sans champ dupliqué.

## Sources contrôleurs

class_source et method_source utilisent les nœuds AST déjà obtenus lors de la vérification, sans relecture ni second parsing.
La ligne correspond à class ou def/async def, pas au décorateur. Une méthode absente garde éventuellement la classe connue sans inventer de ligne de méthode ; une classe absente ne reçoit aucune ligne.
Le chemin controller_file existant reste disponible pour un lien fichier sans ligne lorsque la classe ou méthode n’est pas vérifiable. Un contrôleur absent n’a pas de lien.

## Sources templates

TemplateResolution.source et TemplateNodeInfo.source donnent mvc/views/<référence> lorsque le chemin respecte la politique de vue source.
Les templates présents sont liés ; les templates absents restent du texte. La référence originale et sa présence sont conservées.
Les chemins refusés par la politique source ne sont pas transformés en liens ouvrables.

## Sources dépendances

Chaque TemplateDependency.source est construite au moment de l’extraction déjà existante, avec le chemin du template analysé et la ligne Jinja déjà connue.
Une déclaration transitive est donc localisée dans son propre parent et non dans le principal.
Les dépendances dynamiques peuvent avoir une source de déclaration sans cible inventée. Aucune nouvelle lecture ou extraction n’est nécessaire.

## Lecteur source

Primitive indépendante read_project_source(root, path), appelée uniquement lors de GET /source.
Lecture UTF-8 avec BOM accepté, limitée à 1 Mio. Taille déclarée trop grande ou dépassement à la lecture : refus explicite ; erreur d’encodage : diagnostic propre.
Chaque ouverture relit l’état courant, sans appel au registre ni réinspection. La lecture est séparée de la primitive d’analyse _read_source : le paramètre HTTP non fiable requiert en plus le parcours sécurisé de tous les parents par descripteurs.

## Confinement

Racines autorisées : mvc/routes, mvc/controllers, mvc/views.
Routes et contrôleurs : fichiers .py directement dans le dossier ; vues : sous-dossiers ordinaires autorisés.
Refus avant accès des chemins hors périmètre, absolus, segments vides ou commençant par un point, backslashes, deux-points, NUL et longueurs supérieures à 4096.
.env, .git, env/prod et autres espaces ne sont pas accessibles. Aucun scan, recherche, listing ou formulaire d’exploration générale.
Une URL manuelle respectant cette politique stricte est autorisée ; il ne s’agit pas d’une liste blanche persistante issue d’une ancienne inspection.

## Gestion des lignes

Paramètre line optionnel : entier décimal ASCII strictement positif, au plus neuf chiffres ; sinon 400 sans lecture.
Une ligne valide affiche ±20 lignes, numérotées, avec fond distinct et marqueur > sur la cible.
Sans ligne, tout fichier accepté est affiché. Si la ligne dépasse le fichier actuel, retour 200 avec « La ligne demandée n’est plus disponible. » et fichier complet.
Les fins de ligne CRLF et CR sont adaptées pour la numérotation. Aucun décalage arbitraire dû aux séparateurs Unicode de splitlines.

## Intégration RouteGraph

Aucun changement du builder, du layout ou des nœuds SVG. Les sources restent dans les modèles détaillés consommés par le tableau.
Les tests existants d’isolation du graphe restent actifs ; aucun filesystem ajouté à cette couche.

## Intégration Web

Une colonne Sources avec details/summary natifs expose route, contrôleur, classe, méthode, templates et déclarations Jinja directes/transitives.
Les URL sont construites avec urlencode puis échappées par Jinja. Aucun protocole d’éditeur ni HTML brut.
GET /source utilise le contexte courant et le renderer Forge pour une page packagée : code échappé, retour vers Route Explorer, message sur l’instantané.
Sans projet : 409 et aucune lecture. Fichier disparu : 404. Refus de chemin/type/taille/encodage : 400. Les exceptions attendues ne produisent pas de traceback utilisateur.
No-store est déclaré sur la route. Aucun POST /source, bouton Modifier ou sauvegarde.

## Sécurité

Le lecteur exige os.open avec dir_fd et O_NOFOLLOW, sans repli moins strict.
La racine canonique du contexte est ouverte, puis chaque dossier via son parent avec O_DIRECTORY/O_NOFOLLOW. Les descripteurs ancrent le parcours et les symlinks sont refusés, internes comme externes.
La cible est contrôlée par métadonnées sans suivre de lien, puis ouverte avec O_NOFOLLOW/O_NONBLOCK ; type régulier et identité du descripteur sont comparés. Tous les descripteurs sont fermés, y compris sur erreur.
Aucune exécution du code ou rendu du template cible, aucun import projet, scan, écriture ou nouvelle dépendance.

## Fichiers créés

- [forge_design/forge/source.py](../../forge_design/forge/source.py).
- [forge_design/web/source.py](../../forge_design/web/source.py).
- [forge_design/web/templates/source.html](../../forge_design/web/templates/source.html).
- [tests/test_source.py](../../tests/test_source.py).
- [docs/rapports/FD-ROUTES-016.md](FD-ROUTES-016.md).

## Fichiers modifiés

- [forge_design/forge/routes.py](../../forge_design/forge/routes.py) : localisations issues des AST et chemins connus.
- [forge_design/web/routes.py](../../forge_design/web/routes.py) : générateur d’URL au rendu.
- [forge_design/web/server.py](../../forge_design/web/server.py) : GET source explicite.
- [forge_design/web/templates/routes.html](../../forge_design/web/templates/routes.html) : liens Sources.
- [forge_design/web/static/shell.css](../../forge_design/web/static/shell.css) : code et ligne ciblée.
- [pyproject.toml](../../pyproject.toml) : template source distribué.
- [tests/test_routes.py](../../tests/test_routes.py) : assertions enrichies de sources.
- [tests/test_web_inspector.py](../../tests/test_web_inspector.py) : navigation et erreurs HTTP.
- [docs/02-architecture.md](../02-architecture.md) : politique source et limites.

## Tests ajoutés

32 nouveaux cas : 25 contrôles de lecteur/modèles et sept contrôles Web.
Les tests couvrent les trois espaces autorisés, BOM, refus lexicaux avant accès, symlink fichier/parent, répertoire, dépassement de taille, encodage invalide, suppression et absence de modification.
Les localisations vérifient racine et branchement, ligne d’appel, classe et méthode sync/async, méthode/classe absente, template présent puis absent, déclaration directe/transitive, immutabilité et compatibilité des constructions.
Les tests HTTP couvrent les liens, numéros de ligne, cible marquée, échappement HTML, absence de lien vers template manquant, relecture après changement, ligne périmée, fichier supprimé, refus de POST, absence de lecture sans projet et no-store.
Les sentinelles existantes de lecture/parsing unique restent actives. Les anciennes égalités de modèles sont adaptées aux champs source enrichis.

## Test réel

Wheel construite et inspectée, nouveau template vérifié, installation temporaire sans dépendances puis processus isolé avec origine de l’import vérifiée. Runtime de `.venv`.
Une copie du squelette contient contact_routes.py, contact_controller.py et contacts/list.html. Le contrôle extrait les href réels de /routes avec HTMLParser, puis suit les liens source route, contrôleur et template.
Chaque réponse est 200 avec no-store, chemin attendu, numéros de ligne et marquage lorsque line est fourni. Octets et dates des fichiers comparés après consultation.
Le contrôle conserve le graphe transitif et le cycle existants, termine le serveur et vérifie la libération du port. Le dépôt Forge de référence reste intact.

Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `bee61bac8c7484855f5a9f51660b8558cbbbd8905c76e0517f1eaaf38c756656`.
Script ignoré : `tmp/verify_fd_routes_016.py`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| État Git et historique | Vérifiés |
| `pytest` | 444 tests réussis, dont 32 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| `python -m pip wheel --no-deps --wheel-dir tmp/wheels .` | Succès |
| Wheel installée et liens source HTTP suivis | Succès |

Outils de `.venv`, Python 3.13.5 ; HTTP avec autorisation de sockets locaux hors sandbox.
Les premières égalités de tests sans SourceLocation ont été adaptées au nouveau contrat ; les lignes trop longues Ruff sont formatées avant validation finale.
Pip a désactivé son cache utilisateur inaccessible sans erreur de dépendances.
Le diff complet est relu avant commit, rapport et fichiers nouveaux compris.

## Tests sautés

Aucun test pytest sauté. Aucun contrôle visuel navigateur, lancement d’éditeur, rendu cible ou génération complète Forge revendiqué.

## Limites restantes

Support du lecteur sécurisé dépendant des primitives dir_fd/O_NOFOLLOW ; refus explicite sur plateforme non compatible.
Le contexte projet est partagé par les clients locaux, selon le contrat existant. Les liens relatifs concernent le projet courant au moment de l’ouverture.
Le fichier peut évoluer pendant la lecture ; aucune garantie d’instantané atomique du contenu. Sans ligne ou avec ligne périmée, l’affichage complet reste borné à 1 Mio.
Les références peuvent devenir obsolètes. Les noms cachés et sous-paquets Python restent hors politique de lecture source ; aucune navigation SVG ou exploration générale n’est ajoutée.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `feat: ajouter la navigation vers les sources (FD-ROUTES-016)`.
Le hash et l’état Git après commit sont communiqués dans la réponse de livraison.
