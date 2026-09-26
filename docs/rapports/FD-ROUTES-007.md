# Rapport — FD-ROUTES-007

## Ticket et objectif

Vérifier la syntaxe Jinja des templates statiques présents, sans rendu, contexte ou chargement des templates dépendants.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `d4a441b` — FD-ROUTES-006.
`git status` et `git log --oneline --decorate -5` exécutés avant modification.

## Configuration Jinja Forge vérifiée

`git ls-remote https://github.com/caucrogeGit/Forge.git refs/heads/main` confirme `73a956e587e5f169c028415e0e540c149cbaff56`.
Le `pyproject.toml` Forge déclare `jinja2==3.1.6`, également installé dans `.venv`.
`integrations/jinja2/renderer.py` construit un `Environment` avec loader projet/opt-ins et autoescape activé pour toutes les extensions et les chaînes.
Aucune extension syntaxique ni `StrictUndefined` n’est configuré : le comportement Undefined par défaut demeure.
Le renderer ajoute notamment `url_for`, `csp_nonce`, `current_user`, `is_authenticated`, `can`, `trans` et éventuellement des helpers workflow. Aucun filtre spécifique ni délimiteur personnalisé n’y est configuré.
Ces globals et l’autoescape concernent le rendu ; ils ne sont pas nécessaires à `Environment.parse`.
Le Bridge ne construit pas le renderer Forge et ne charge aucun opt-in.

Jinja2 est désormais une dépendance directe explicite, au même pin `3.1.6` que Forge : le Bridge utilise directement son API publique et ne dépend plus seulement d’une dépendance transitive implicite. Aucune nouvelle bibliothèque ni changement de version installée.

## Modèle de validation Jinja

`TemplateResolution` reste gelée et ajoute `syntax` (`valid`, `invalid`, `unreadable`, `not-applicable`), `syntax_line` et `syntax_message` optionnels.
Les valeurs par défaut préservent les constructions antérieures.
Seule une référence `found` avec présence `present` est analysée. Les autres cas restent `not-applicable` sans warning syntaxique.
La présence reste `present` si une erreur survient ensuite pendant la lecture : les deux statuts décrivent des contrôles distincts.

## Lecture du template

La primitive existante `_read_source` lit exclusivement le chemin préalablement accepté par le contrôle de présence.
Elle exige un fichier ordinaire sans lien, utilise `O_NOFOLLOW` et `O_NONBLOCK` lorsqu’ils sont disponibles, puis vérifie le type et l’identité du descripteur par comparaison de métadonnées.
La lecture est bornée à 1 Mio plus un octet de détection ; dépassement et UTF-8 invalide donnent `unreadable`. UTF-8 avec BOM est accepté.
Les parents ont été contrôlés par `lstat` lors de la présence ; le contrôle du fichier avant ouverture est conservé plutôt que supprimé pour économiser un appel.

## Parsing Jinja

`Environment(loader=None).parse(source)` produit uniquement l’AST Jinja.
Aucun appel à `get_template`, `from_string`, `compile`, `render` ou `render_async`.
Aucune extension, aucun contexte, aucun global du projet ou de Forge installé dans cet environnement.
Les variables et filtres inconnus sont acceptés au niveau syntaxique. HTML, JavaScript et CSS ne sont pas validés.

## Gestion des dépendances de templates

`extends`, `include` et `import` sont reconnus syntaxiquement mais leurs cibles ne sont pas chargées.
Un parent absent ou un include dynamique n’empêche pas `valid` lorsque la syntaxe du fichier courant est correcte.
Aucun loader filesystem actif, aucun scan et aucun fallback.

## Gestion des erreurs

`TemplateSyntaxError` donne `invalid`, avec numéro de ligne et message Jinja ramené sur une ligne et limité à 240 caractères.
Ni source complète, ni ligne de code, ni traceback ne sont copiés dans le diagnostic.
Les erreurs de lecture contrôlées donnent `unreadable`, tout comme un dépassement de profondeur de parsing (`RecursionError`).
Les autres exceptions inattendues restent propagées.
Un warning est ajouté une seule fois par fichier pour `invalid` ou `unreadable`, après les warnings existants ; aucun warning supplémentaire pour les autres statuts.

## Cache local

Le cache de présence conserve désormais le résultat de template enrichi complet.
Un template partagé par plusieurs routes est lu et parsé une seule fois par `read_routes`, avec mémorisation des succès et des échecs.
Un nouvel appel relit et reparcourt le fichier ; aucun cache persistant.

## Intégration Bridge

`read_routes(...) -> RoutesResult` reste inchangé.
Les champs antérieurs des routes, handlers et templates, leur ordre et les warnings existants sont conservés.
Aucun nouveau Tool, changement du registre ou modification d’Inspector.

## Intégration Web

Colonne Jinja après Présence : « Valide », « Invalide », « Non vérifiable » ou « — ».
Le détail syntaxique est affiché dans les warnings existants, avec échappement Jinja.
`Cache-Control: no-store` demeure actif ; aucune nouvelle route HTTP.

## Sécurité

La lecture nouvelle est limitée aux vues statiques présentes autorisées sous `mvc/views`.
Les traversals, chemins absolus, liens et fichiers spéciaux restent refusés par le contrôle existant avant lecture.
Aucun import du projet, exécution d’expression, résolution de variable, chargement de dépendance ou écriture du projet.
Les limites de stabilité des parents du filesystem restent celles du Bridge ; aucune garantie générale contre les remplacements concurrents n’est ajoutée.

## Fichiers créés

- [docs/rapports/FD-ROUTES-007.md](FD-ROUTES-007.md).

## Fichiers modifiés

- [forge_design/forge/routes.py](../../forge_design/forge/routes.py) : statuts, lecture, parsing et cache.
- [forge_design/web/templates/routes.html](../../forge_design/web/templates/routes.html) : colonne Jinja.
- [pyproject.toml](../../pyproject.toml) : dépendance Jinja explicite.
- [tests/test_routes.py](../../tests/test_routes.py) : parsing, cache et sécurité.
- [tests/test_web_inspector.py](../../tests/test_web_inspector.py) : statuts et échappement.
- [docs/02-architecture.md](../02-architecture.md) : contrat syntaxique et limites.

## Tests ajoutés

15 nouveaux cas : 12 scénarios de parsing et trois contrôles HTTP.
Ils couvrent variable inconnue, filtre inconnu, includes statique/dynamique, extends absent, import externe non chargé, HTML/JS invalide, BOM, syntaxe invalide, encodage invalide et dépassement de 1 Mio.
Chaque scénario vérifie une lecture et au plus un parsing pour deux routes, puis une nouvelle vérification au prochain appel. Les échecs sont également mis en cache.
Des sentinelles interdisent loader, compilation, rendu, scan et ouvertures de tout fichier autre que routes, contrôleur et vue autorisée. Les octets et dates de modification restent identiques.
Les tests antérieurs vérifient `not-applicable` sur chemins refusés, absents, méthodes non vérifiées et références non statiques. Leur ancienne interdiction de lecture de la vue a été adaptée à l’autorisation nouvelle.
Le test HTTP d’échappement injecte un diagnostic contenant `<script>` ; les autres cas utilisent le parseur réel. Les tests de registre et Inspector restent inchangés.

## Test réel

Wheel construite et inspectée : ressources présentes et dépendance `jinja2==3.1.6` confirmée dans les métadonnées.
Installation temporaire sans dépendances, puis processus Python isolé (`-I`) vérifiant l’origine de Forge Design, avec runtime de `.venv`.
Une copie du squelette reçoit une vue contact avec `extends "base-inexistante.html"`, bloc et variable inconnue, sans création du parent.
Le GET `/routes` affiche Présent et Valide. Après remplacement de cette seule vue par un `if` sans `endif`, le GET suivant affiche Présent et Invalide.
Le dépôt Forge de référence reste intact ; serveur arrêté, socket fermé et port réutilisable.
L’absence de lecture de dépendances est instrumentée dans les tests unitaires ; le contrôle HTTP utilise le même environnement sans loader.

Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `3b261e1290bf1da4a5df18e0e5fde142107ba18b13d7cc8b0e5c8700c3ee9a0a`.
Script ignoré par Git : `tmp/verify_fd_routes_007.py`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| État Git, historique et référence Forge main | Vérifiés |
| `pytest` | 330 tests réussis, dont 15 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| `python -m pip wheel --no-deps --wheel-dir tmp/wheels .` | Succès |
| Wheel installée, HTTP Valide puis Invalide | Succès |

Outils de `.venv`, Python 3.13.5, Jinja2 3.1.6 ; sockets locaux autorisés hors sandbox.
Un diagnostic Pyright sur le message optionnel Jinja a été corrigé. Le premier test HTTP d’échappement attendait à tort que le message réel Jinja contienne le caractère HTML source ; une injection ciblée vérifie désormais ce cas sans dépendre du libellé du parser.
Pip a désactivé son cache utilisateur inaccessible dans le sandbox, sans erreur de dépendances.
Le diff complet est relu avant commit, rapport compris.

## Tests sautés

Aucun test pytest sauté. Aucun rendu de la vue cible, contrôle visuel navigateur ou nouvelle génération Forge revendiqué.

## Limites restantes

Syntaxe valide ne garantit ni rendu réussi, ni dépendances présentes, ni filtres/globals runtime valides, ni HTML valide.
Les extensions personnalisées et la configuration du projet ne sont pas chargées ; la baseline vérifiée est celle de Forge main inspecté.
Les limites de racine conventionnelle et de stabilité filesystem des tickets précédents restent applicables.

## État Git final

Un seul commit local sur `main`, rapport inclus, sans push.
Message : `feat: vérifier la syntaxe Jinja des templates (FD-ROUTES-007)`.
Le hash et l’état Git après commit sont communiqués dans la réponse de livraison.
