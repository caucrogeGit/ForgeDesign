# Rapport — FD-ENTITIES-001

## Ticket et objectif

Ajouter le troisième Tool réel, Entity Explorer : lecture des contrats JSON directs, affichage des entités, tables, champs et options, sans lecture SQL/Python ni analyse de relations.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `7c131bf` — FD-PROJECT-005.
État Git et cinq derniers commits inspectés avant modification.

## Conventions Forge vérifiées

`git ls-remote https://github.com/caucrogeGit/Forge.git refs/heads/main` confirme `73a956e587e5f169c028415e0e540c149cbaff56`, identique au checkout inspecté avant implémentation.
Sources examinées : packages/forge-mvc-entities/forge_mvc_entities/make_entity.py, schemas/field.schema.json, field_resolver.py, canonical_model_normalizer.py, model.py et cli/schemas/entity.schema.json.
Le générateur écrit mvc/entities/<snake>/<snake>.json avec schema_version "1.0", name, table, fields et options. Son constructeur minimal produit Contact avec title:string, max_length 255 et required true.
Le schéma exige name, table et une liste non vide de fields. Options est facultatif ; timestamps et soft_delete sont faux par défaut. Les champs exigent name/type, avec required et unique faux, nullable vrai ; field_resolver.nullable_of donne priorité à required true.
Default accepte une valeur JSON quelconque ; references est une chaîne pour foreign_key, sans besoin de suivre sa cible. Decimal expose precision/scale.
Le pipeline model.py refuse explicitement format_version: 1. Aucune migration n’est reproduite.

## Source de vérité

Uniquement mvc/entities/<identifiant_simple>/<identifiant_simple>.json.
Ordre lexical des dossiers directs ; champs dans leur ordre JSON. Le nom métier et la table restent ceux du JSON, sans reconstruction depuis le dossier ni contrôle de leur correspondance.
Les noms de dossiers non canoniques, cachés, env et préfixes de clés SSH sont ignorés ; aucun JSON de remplacement cherché. Un dossier canonique sans son fichier attendu produit une anomalie.

## Modèle EntityInfo

Dataclass gelée : name, table, tuple fields, timestamps, soft_delete et SourceLocation relative.
EntitiesResult gelé : tuples entities, errors et warnings. Les entités non interprétables sont représentées par leur anomalie et leur source, sans modèle partiel inventé.

## Modèle EntityFieldInfo

Dataclass gelée : name, type, required, nullable, unique, max_length, precision, scale, default_json et references.
Les attributs complémentaires restent optionnels. Default est sérialisé en texte JSON immuable : absence = None, valeur null = "null", structures JSON conservées sans objet mutable exposé.
Aucune liste de types Forge codée en dur. Types inconnus affichés comme texte ; pas de validation métier exhaustive ni ajout de champs système implicites.
Le contrat minimal vérifie objets, liste non vide, chaînes non vides encodables, booléens stricts et attributs numériques entiers. Il ne réimplémente ni tout JSON Schema ni les contraintes sémantiques Forge. Les propriétés hors périmètre restent ignorées.

## Diagnostics

Codes entity.source_missing, entity.unreadable, entity.json_invalid, entity.schema_version_unsupported et entity.structure_invalid.
Chaque anomalie contient un message sobre et une source relative. Aucun extrait JSON ou traceback affiché.
Un fichier invalide, legacy, trop grand ou non UTF-8 n’empêche pas les autres entités d’être exposées. Une erreur de métadonnées d’un dossier est également locale.
L’absence de mvc/entities retourne un résultat vide avec warning. Une racine non Forge lève explicitement NotForgeProjectError, comme les autres Bridge.

## Lecture et confinement

resolve_project_root et detect_forge_project sont réutilisés ; leurs contrôles portent sur les métadonnées de structure.
Le lecteur ouvre la racine canonique, mvc, entities puis chaque dossier via descripteurs, O_DIRECTORY et O_NOFOLLOW. Une seule énumération directe de mvc/entities, aucun parcours récursif.
Les types des entrées sont contrôlés sans suivi de lien. Le JSON doit être régulier, ouvert avec O_NOFOLLOW/O_NONBLOCK et comparé à ses métadonnées préalables par samestat.
Limite MAX_SOURCE_BYTES centralisée : 1 Mio, taille déclarée puis lecture bornée à la limite plus un octet. UTF-8 avec BOM accepté. Les descripteurs sont fermés par context managers.
Les drapeaux sécurisés sont requis, sans repli suivant les liens. Aucun chemin du JSON n’est utilisé pour ouvrir un fichier.

## EntityExplorerTool

Dataclass gelée, id entity-explorer, nom Entity Explorer, description « Inspecter les entités déclarées d’un projet Forge. ».
run(project_root: Path) retourne directement read_entities(project_root), sans orchestration additionnelle.
Conformité Tool[EntitiesResult] vérifiée par typage et test de délégation.

## Intégration ToolRegistry

Enregistrement explicite après project-inspector et route-explorer ; exactement trois Tools dans cet ordre.
Les tests de composition vérifient l’ordre, l’indépendance des registres et l’absence d’exécution de chacun des trois Tools au démarrage.

## Intégration Web

GET /entities uniquement. Sans courant, aucun accès au registre ; le shell affiche « Aucun projet ouvert. ».
Avec courant, registry.get("entity-explorer").run(context.root), relecture à chaque GET. Le contexte ne mémorise aucun résultat et n’est pas modifié.
Tableau des entités/options, détails natifs des champs, section Anomalies. Navigation fixe et aria-current, échappement Jinja et no-store.
Sources affichées en texte, sans extension de /source. Aucun JS, nouveau POST ou comportement de Route Explorer modifié.

## Sécurité

Aucune lecture de relations.json, SQL, Python généré, configuration ou secret ; aucune résolution de references. Noms sensibles et chemins hors convention ne sont pas ouverts.
Les sentinelles limitent les ouvertures de fichiers à contact.json, interdisent Path.open, exec, eval et subprocess.run pendant le Bridge. Les fichiers Python factices qui lèveraient une exception restent inertes.
Le constructeur JSON Forge est utilisé uniquement pour préparer la fixture du test installé, jamais par Entity Explorer. Aucun build:model/check:model, connexion BDD ou écriture projet dans le Tool.

## Fichiers créés

- forge_design/forge/entities.py
- forge_design/tools/entity_explorer.py
- forge_design/web/entities.py
- forge_design/web/templates/entities.html
- tests/test_entities.py
- tests/test_entity_explorer.py
- docs/tools/entity-explorer.md
- docs/rapports/FD-ENTITIES-001.md

## Fichiers modifiés

- forge_design/app.py : troisième enregistrement.
- forge_design/web/server.py : GET entities.
- forge_design/web/templates/layout.html : navigation fixe.
- pyproject.toml : template distribué, sans nouvelle dépendance.
- tests/test_app.py : contrat de trois Tools.
- docs/02-architecture.md : nouvelle verticale indépendante.

## Tests ajoutés

29 nouveaux cas : 27 Bridge, un Tool et un HTTP regroupant les scénarios Web.
Couverture : absence, refus non Forge, valeurs/options/défauts, BOM, plusieurs entités et ordre, types inconnus, default scalaire/null/objet, references, immutabilité, versions/legacy, structures invalides, booléens et entiers stricts, JSON invalide, taille et encodage, JSON absent, liens fichier/dossier/parent, répertoire et FIFO, erreur locale de métadonnées et continuation.
Le test de confinement vérifie une seule lecture du JSON canonique par appel, aucun accès aux contenus voisins, puis compare fichiers et mtime ; le prochain appel relit.
Le test HTTP vérifie registre, absence de Tool sans courant, refus de POST, tableaux/détails/options, source relative sans lien, navigation active, anomalies, XSS échappé, no-store, fichier changé pris en compte et Route Explorer encore disponible.
Les 600 tests historiques restent actifs ; les attentes du registre sont adaptées au troisième Tool.

## Test réel

Copie temporaire du véritable skeleton/data Forge. Le constructeur build_entity_json_canonical("Contact") du checkout Forge vérifié prépare la fixture ; seuls ses octets JSON sont déposés sous mvc/entities/contact/contact.json. Aucun générateur SQL/Python ou commande Forge lancé.
La wheel installée sert /entities : Contact, contact, title, string, 255 et source affichés. Route Explorer reste accessible.
Après remplacement volontaire du JSON par une syntaxe invalide, le GET suivant affiche entity.json_invalid. Les instantanés avant/après chaque consultation confirment les contenus et mtime inchangés.
XDG temporaire, dépôt Forge intact, serveur arrêté, thread terminé, socket fermé et port réutilisable.
Script/journal ignorés : tmp/verify_fd_entities_001.py et tmp/verify_fd_entities_001.log.

## Packaging

Wheel reconstruite et inspectée : Bridge, Tool, Web et template entities présents, aucun tests/ ou tmp/ distribué.
Installation temporaire --no-deps --no-index --target, processus Python -I avec origine importée vérifiée et runtime de .venv.
Artefact : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `638902868f18dfbdb56e3726797c51295f4d2ebe6a7d51e4a1f96a2c729c36a8`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| Git initial, historique et Forge main | Vérifiés |
| Tests ciblés initiaux Bridge/Tool/Web/registre | 32 réussis |
| pytest final | 629 réussis, dont 29 nouveaux cas |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip check | No broken requirements found |
| git diff --check | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Fixture Forge et wheel installée, HTTP réel | Succès |

Outils .venv, Python 3.13.5 ; HTTP avec sockets locaux autorisés hors sandbox.
Les lignes longues et imports ont été formatés avant validation finale. Pip check a désactivé son cache utilisateur inaccessible sans erreur de dépendances.
Diff complet, fichiers nouveaux, documentation et rapport relus avant commit.

## Tests sautés

Aucun test pytest sauté. Aucun contrôle visuel navigateur, génération complète make:entity, exécution du projet ou validation BDD revendiqué.

## Limites restantes

Interprétation minimale du contrat, pas validation complète Forge. Les contraintes métier, propriétés hors périmètre, relations, index, champs synthétiques et cohérence SQL restent exclus.
Dossiers directs à identifiant simple uniquement, ordre lexical ; pas de vérification nom métier/dossier. Nombre d’entités non plafonné, taille bornée individuellement.
Primitives POSIX requises. Le parcours des parents est ancré, mais le contenu n’est pas un instantané atomique ; le projet peut changer entre lectures. Aucun cache ou écriture correctrice.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `feat: ajouter Entity Explorer minimal (FD-ENTITIES-001)`.
Le hash et l’état final vérifiés sont communiqués dans la réponse de livraison.
