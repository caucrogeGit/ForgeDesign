# Rapport — FD-ROUTES-004

## Ticket et objectif

Vérifier par AST la présence directe d'une méthode dans la classe contrôleur importée, sans exécution, introspection ou analyse métier.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `a467d6e` — FD-ROUTES-003.
État et cinq derniers commits inspectés avant modification.

## Conventions Forge vérifiées

`git ls-remote` confirme Forge main `73a956e587e5f169c028415e0e540c149cbaff56`.
Le squelette `HomeController` hérite de `BaseController` et définit `index` et `charte` avec `@staticmethod`.
Le générateur auth définit également `AuthController(BaseController)` et des méthodes statiques.
Le générateur CRUD, module `crud/controller_builder.py`, émet de nombreuses méthodes `@staticmethod`.
La prise en charge de `async def` et `@classmethod` est testée sur fixtures, sans prétendre qu'ils ont été observés dans ces exemples générés.

## Modèle et résolution

`HandlerInfo` ajoute `verification`, un Literal parmi `found`, `class-missing`, `method-missing`, `unreadable`, `ambiguous`, `not-applicable`, avec cette dernière valeur par défaut.
La table d'imports conserve désormais le chemin et le symbole original. Un alias `Contact` peut donc désigner la classe `Original` sans modifier la référence affichée.
Aucun champ de route antérieur n'est supprimé ou réordonné.

La vérification exige une référence à deux composantes et un contrôleur déjà résolu.
Seules les classes de niveau module sont candidates ; plusieurs classes de même nom donnent `ambiguous`.
La recherche porte uniquement sur les fonctions synchrones ou asynchrones directement présentes dans la classe ; plusieurs méthodes de même nom sont également ambiguës.
Les décorateurs ne sont pas interprétés. L'héritage n'est pas suivi : une méthode héritée uniquement donne `method-missing`.

## Lecture sécurisée et cache

Le lecteur réutilise `_read_source` : fichier ordinaire sans lien, ouverture avec les protections disponibles, comparaison des métadonnées du descripteur, limite 1 Mio, UTF-8 avec BOM accepté.
Les parents sont vérifiés avant lecture. Le fichier contrôleur provient exclusivement de l'import déjà résolu.
`ast.parse` produit un arbre ; aucune compilation explicite, import cible, eval ou exec.
Le contenu complet est nécessairement parsé, mais seul le niveau classe/méthode est inspecté, sans analyse du corps métier.
Un dictionnaire local à chaque `read_routes` conserve l'AST ou l'échec par fichier. Il est partagé entre les sources de routes d'un même appel et abandonné à son retour.

## Erreurs et avertissements

Fichier absent ou lié : le warning existant est conservé et la vérification devient `unreadable`, sans warning supplémentaire.
Syntaxe invalide, encodage invalide ou taille excessive : route, handler et chemin déjà associé sont conservés, statut `unreadable` et warning de lecture/syntaxe, une fois par fichier et par appel.
Classe ou méthode absente et ambiguïté : warning explicite sans copie du code.
Aucun warning de vérification lorsque la méthode est trouvée.
Une fonction simple reste `not-applicable` ; un handler dynamique reste absent et n'ajoute pas de warning redondant.

## Intégration Web

La page `/routes` ajoute Vérification après Contrôleur : Trouvée, Classe absente, Méthode absente, Non vérifiable, Ambiguë ou « — ».
Aucun lien, nouveau Tool, nouvelle route HTTP ou nouvelle dépendance.
Jinja échappe les données comme auparavant et `no-store` reste actif.

## Fichiers créés

- [docs/rapports/FD-ROUTES-004.md](FD-ROUTES-004.md)

## Fichiers modifiés

- [forge_design/forge/routes.py](../../forge_design/forge/routes.py) : statut, symbole importé, vérification et cache local.
- [forge_design/web/templates/routes.html](../../forge_design/web/templates/routes.html) : colonne Vérification.
- [tests/test_routes.py](../../tests/test_routes.py) : cas AST et cache.
- [tests/test_web_inspector.py](../../tests/test_web_inspector.py) : statut HTML.
- [docs/02-architecture.md](../02-architecture.md) : nouvelle autorisation de lecture des contrôleurs.

## Tests ajoutés

11 nouveaux cas couvrent méthode synchrone, async, staticmethod, classmethod, classe absente, méthode absente, syntaxe invalide, dépassement de taille, classes ambiguës, méthode héritée uniquement et cache/encodage.
Les fixtures utilisent un alias vers le symbole original. Le contrôle de cache vérifie une seule lecture pour deux routes, y compris en cas d'échec, puis une nouvelle lecture au prochain appel.
Les anciennes assertions de non-lecture des contrôleurs sont adaptées à cette nouvelle autorisation : seuls les fichiers de routes et le contrôleur explicitement associé sont permis.
Les fixtures de syntaxe invalide vérifient désormais `unreadable` ; les routes et leurs autres données restent identiques.
Une suppression Pyright ciblée `reportPrivateUsage` sert uniquement à instrumenter la primitive privée de lecture dans le test de cache.

## Test réel et packaging

Wheel reconstruite, ressources inspectées et installation temporaire sans dépendances dans un processus Python isolé utilisant le runtime de `.venv`.
Une copie du squelette reçoit un contrôleur contact avec méthode statique contenant une exception qui serait levée si elle était exécutée.
Le GET `/routes` affiche le handler, le fichier et « Trouvée », sans exécution de cette méthode.
Le dépôt Forge reste intact ; serveur arrêté et port libéré.

Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `941c4cf068b4aa6847c90b0f0a49c7d76bf7e5fff22cb1b72697c0f5c0a2fab6`.
Script ignoré : `tmp/verify_fd_routes_004.py`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| État Git, historique, référence Forge main | Vérifiés |
| `pytest` | 273 tests réussis, dont 11 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| Wheel construite, installée et HTTP réel | Succès |

Outils de `.venv`, Python 3.13.5, sockets locaux autorisés hors sandbox.
Le premier passage ciblé révélait les anciennes attentes de non-lecture et de statut ; elles ont été adaptées au contrat du ticket avant validation finale.
Le diff complet est relu avant commit, rapport compris.

## Tests sautés

Aucun test pytest sauté. Aucun contrôle visuel navigateur ni exécution de contrôleur revendiqué.

## Limites restantes

Définition syntaxique directe uniquement : le statut trouvé ne garantit ni disponibilité runtime ni comportement des décorateurs.
Pas d'héritage, réexport, métaclasse ou analyse métier. Les limites de stabilité filesystem des lecteurs existants sont conservées.
Les références attributaires de plus de deux composantes restent non applicables pour la vérification.

## État Git final

Un seul commit local sur `main`, rapport inclus, sans push.
Message : `feat: vérifier statiquement les méthodes contrôleurs (FD-ROUTES-004)`.
Le hash et l'état final sont communiqués dans la réponse de livraison.
