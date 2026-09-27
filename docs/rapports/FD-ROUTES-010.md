# Rapport — FD-ROUTES-010

## Ticket et objectif

Vérifier la syntaxe Jinja des dépendances directes statiques présentes, sans extraire ni suivre leurs propres dépendances. L’analyse reste à profondeur 1.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `f4844e6` — FD-ROUTES-009.
`git status` et `git log --oneline --decorate -5` exécutés avant modification.

## Modèle de syntaxe des dépendances

`TemplateDependency` reste gelée et ajoute `syntax`, `syntax_line` et `syntax_message` avec les mêmes types et valeurs par défaut que le template principal.
Le statut réutilisé est `TemplateSyntaxStatus` : `valid`, `invalid`, `unreadable`, `not-applicable`.
Les champs existants, ordre, doublons et lignes de déclaration restent inchangés.
Une dépendance dynamique, absente, refusée ou de présence non vérifiable conserve une syntaxe non applicable.

## Réutilisation du validateur Jinja

La fonction existante `_template_syntax` reste l’unique validateur. Elle retourne maintenant le résultat syntaxique et l’AST éventuel sans extraire de dépendances.
Le même chemin de code traite templates principaux et dépendances directes.
Jinja2 3.1.6 et sa configuration de parsing ne changent pas ; aucune dépendance ajoutée.

## Lecture sécurisée

La présence est contrôlée par la politique existante sous `mvc/views`, puis la lecture utilise `_read_source` : fichier ordinaire sans lien, protections `O_NOFOLLOW`/`O_NONBLOCK` lorsqu’elles sont disponibles, comparaison des métadonnées du descripteur.
Limite de 1 Mio, UTF-8 avec BOM accepté. Taille excessive, erreur de lecture ou décodage impossible donnent `unreadable`.
Les chemins refusés et références dynamiques n’arrivent pas à la lecture.
Les parents doivent rester stables pendant l’opération, comme dans les autres lecteurs du Bridge.

## Parsing Jinja

`Environment(loader=None).parse(source)` uniquement, sans compilation, contexte, résolution de variables ou rendu.
Variables et filtres inconnus restent acceptés syntaxiquement.
Un extends vers un parent absent dans la dépendance peut rester valide.

## Absence de récursion

Seule la boucle des routes principales appelle `_template_dependencies` sur leur AST.
Le traitement d’une dépendance appelle uniquement le cache de parsing : aucun appel à l’extracteur, aucune recherche de ses includes/extends/imports, aucun contrôle de leurs chemins.
Il n’existe ni appel récursif, ni détection de cycles, ni graphe transitif.

## Cache local

Un cache local par référence conserve présence, résultat syntaxique et AST éventuel, y compris les échecs.
Une dépendance répétée, même sur plusieurs routes, n’est lue et parsée qu’une fois pendant `read_routes`.
Un second cache conserve les résultats principaux enrichis afin de ne pas répéter leur extraction.
Les caches sont abandonnés au retour ; un nouvel appel recommence les contrôles.

## Mutualisation avec template principal

Un fichier d’abord rencontré comme dépendance peut ensuite fournir son AST déjà parsé lorsqu’il est explicitement principal d’une autre route.
L’extraction intervient alors uniquement au titre de cette route principale. Présence et lecture/parsing ne sont pas répétés.
La situation inverse réutilise le même cache. Ce partage n’étend pas la profondeur d’analyse depuis une route donnée.

## Gestion des erreurs

Les erreurs Jinja conservent numéro de ligne et message sur une ligne limité à 240 caractères, sans recopier de ligne source ou traceback.
Le warning `invalid` ou `unreadable` est émis lors du remplissage du cache, une seule fois par référence pendant l’appel.
Les résultats valides et non applicables n’ajoutent pas de warning syntaxique.
La présence déjà constatée reste inchangée si la lecture échoue ensuite. Les exceptions inattendues hors du contrat existant restent propagées.

## Intégration Bridge

`read_routes(...) -> RoutesResult` et les APIs des Tools sont conservés.
L’enrichissement utilise les modèles immuables existants. Aucun changement de registre, Inspector ou contexte projet.
Les dépendances ne reçoivent pas de champ pour leurs propres dépendances.

## Intégration Web

La liste compacte ajoute Valide, Invalide ou Non vérifiable après Présent quand la syntaxe est applicable.
Une dépendance absente conserve uniquement Absent ; une référence dynamique garde son indication sans statut Jinja.
Les diagnostics passent par les warnings échappés existants. Aucun `safe`, nouvelle colonne, route HTTP ou action.
`Cache-Control: no-store` reste actif.

## Sécurité

Aucune configuration ou code du projet chargé, aucun loader, rendu, scan ou écriture.
La nouvelle autorisation de lecture couvre uniquement les dépendances directes statiques présentes des templates principaux valides.
Les références contenues dans ces dépendances ne sont ni extraites, ni vérifiées, ni ouvertes.
Les limites de stabilité filesystem du Bridge restent applicables.

## Fichiers créés

- [docs/rapports/FD-ROUTES-010.md](FD-ROUTES-010.md).

## Fichiers modifiés

- [forge_design/forge/routes.py](../../forge_design/forge/routes.py) : modèle, séparation parsing/extraction et cache partagé.
- [forge_design/web/templates/routes.html](../../forge_design/web/templates/routes.html) : statut syntaxique compact.
- [tests/test_routes.py](../../tests/test_routes.py) : profondeur, cache et lecture autorisée.
- [tests/test_web_inspector.py](../../tests/test_web_inspector.py) : statuts et diagnostic échappé.
- [docs/02-architecture.md](../02-architecture.md) : contrat à profondeur 1.

Aucune dépendance ni métadonnée de distribution modifiée.

## Tests ajoutés

10 nouveaux cas : sept scénarios de syntaxe directe et trois contrôles HTTP.
Ils couvrent syntaxe valide/invalide, ligne et message borné, non UTF-8, dépassement de taille, BOM, variable/filtre inconnus, extends et include internes non suivis.
Les compteurs vérifient une lecture et un parsing pour une dépendance répétée dans deux templates principaux, puis de nouveaux contrôles au prochain appel. L’extracteur est appelé uniquement pour les deux principaux.
Une sentinelle de métadonnées refuse les noms des cibles transitives ; les ouvertures sont limitées aux fichiers autorisés. Loader, compilation, rendu et scan sont interdits pendant le contrôle. Contenus et dates de modification restent identiques.
Le test existant de cache partagé vérifie aussi la lecture unique d’un fichier à la fois principal et dépendance et un warning unique pour une dépendance illisible.
Les tests de présence sont adaptés à la nouvelle autorisation de lecture : leurs fichiers non UTF-8 donnent désormais une syntaxe illisible, sans changer leur présence. Absence, chemin refusé et dynamique conservent `not-applicable`.
Les tests HTTP vérifient Valide/Invalide, Absent sans syntaxe, dynamique et `no-store`. Un diagnostic HTML injecté contrôle l’échappement.

## Test réel

Wheel construite, archive inspectée et installation temporaire sans dépendances dans un processus Python isolé (`-I`), origine des imports vérifiée. Runtime fourni par `.venv`.
Une copie du squelette reçoit un template principal incluant `contacts/_table.html`.
Cette dépendance contient un extends vers `parent-inexistant.html` et un if correctement fermé, sans création du parent : le GET affiche Présent — Valide.
Après remplacement de cette seule dépendance par un if non fermé, le GET suivant affiche Présent — Invalide ; la syntaxe principale reste valide.
L’absence de suivi du parent est instrumentée dans les tests unitaires. Le dépôt Forge de référence reste intact, le serveur est arrêté et le port libéré.

Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `ad7b99cf59c5db83afefbe2a9b32ed22df4e917dd88d9ab8a7677a3a1c615b9c`.
Script ignoré par Git : `tmp/verify_fd_routes_010.py`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| État Git et historique | Vérifiés |
| `pytest` | 367 tests réussis, dont 10 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| `python -m pip wheel --no-deps --wheel-dir tmp/wheels .` | Succès |
| Wheel installée et HTTP dépendance Valide puis Invalide | Succès |

Outils de `.venv`, Python 3.13.5 ; sockets locaux autorisés hors sandbox.
Le premier passage ciblé a révélé les anciennes sentinelles interdisant toute lecture des dépendances ; elles ont été adaptées au nouveau contrat avant validation finale.
Pip a désactivé son cache utilisateur inaccessible dans le sandbox, sans erreur de dépendances.
Le diff complet est relu avant commit, rapport compris.

## Tests sautés

Aucun test pytest sauté. Aucun rendu cible, contrôle visuel navigateur ou nouvelle génération Forge revendiqué.

## Limites restantes

Syntaxe valide ne garantit ni validité des dépendances internes, ni rendu réussi, ni HTML valide.
Aucun graphe transitif. Une cible également principale peut être analysée indépendamment au titre de cette autre route.
Racine conventionnelle, configuration Jinja minimale et limites de stabilité filesystem des tickets précédents conservées.

## État Git final

Un seul commit local sur `main`, rapport inclus, sans push.
Message : `feat: vérifier la syntaxe des dépendances Jinja (FD-ROUTES-010)`.
Le hash et l’état Git après commit sont communiqués dans la réponse de livraison.
