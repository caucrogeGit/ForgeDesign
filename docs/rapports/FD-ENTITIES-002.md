# Rapport — FD-ENTITIES-002

## Ticket et objectif

Enrichir Entity Explorer avec les relations déclaratives many_to_one et many_to_many, leurs pivots et champs, sans SQL, base de données, exécution cible ou graphe.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `76fb642` — FD-ENTITIES-001.
État Git et cinq derniers commits inspectés avant modification.

## Conventions Forge vérifiées

`git ls-remote https://github.com/caucrogeGit/Forge.git refs/heads/main` confirme `73a956e587e5f169c028415e0e540c149cbaff56`.
Inspection de cli/schemas/relations.schema.json, common.schema.json, packages/forge-mvc-entities/forge_mvc_entities/schemas/pivot.schema.json et relations.py.
Le document canonique utilise schema_version "1.0" et relations[]. Le validateur accepte exactement many_to_one et many_to_many, et refuse le format legacy.
Précision : le schéma général décrit foreign_key comme optionnel avec un défaut futur, mais le validateur canonique many_to_one exige effectivement foreign_key et on_delete. Le Bridge suit cette exigence, sans fabriquer de clé.
Nullable et index valent true par défaut. Le pivot exige id et unique_pair strictement true ; on_delete y vaut cascade par défaut et fields vaut une liste vide.

## Contrat relations.json

Chemin fixe mvc/entities/relations.json, sans glob ni fichier alternatif.
Absence = tuple vide sans anomalie de relation. Racine objet, version "1.0", liste relations exigées ; aucun format legacy converti.
Ordre et occurrences préservés. Un document invalide ne masque pas les entités ; un item invalide ne masque pas les autres relations.

## Modèle RelationInfo

Dataclass gelée : type limité aux deux variantes, from_entity, to_entity, name, inverse_name optionnel, source, source_index et sous-structure typée selon la variante.
EntitiesResult ajoute relations en fin de modèle avec tuple vide par défaut. EntityIssue ajoute source_index optionnel en fin de modèle. Les constructions antérieures restent compatibles.
SourceLocation conserve le chemin du document sans ligne inventée ; l’index identifie relations[n].

## many_to_one

ManyToOneInfo conserve foreign_key, nullable, index et on_delete. La direction est de l’entité portant la FK vers sa cible.
Foreign_key et on_delete sont obligatoires, nullable/index strictement booléens avec défaut true. Les quatre politiques restrict, cascade, set_null et no_action sont conservées sous leur forme déclarative, sans traduction SQL.
Inverse_name est optionnel. Aucun on_update interne ajouté. Une FK non déclarée comme champ ne produit aucun diagnostic ; la comparaison references/cible est hors de ce ticket.

## many_to_many

ManyToManyInfo conserve table pivot, clés source/cible, id, unique_pair, on_delete et champs pivot.
Les trois noms sont des chaînes non vides ; id et unique_pair doivent être true (l’entier 1 n’est pas accepté). Cascade et champs vides sont les seuls défauts appliqués à ces propriétés optionnelles.
Les clés sont affichées avec leur entité correspondante ; aucune symétrie d’API ni colonne artificielle n’est déduite.

## Pivot fields

Réutilisation du modèle gelé EntityFieldInfo et du parseur minimal existant, puisque Forge utilise aussi son schéma de champ commun.
Tuple ordonné, nom/type, nullable et unique, max_length/precision/scale et valeurs complémentaires lorsqu’elles existent. Required conserve la priorité sur nullable. Aucun calcul SQL ni liste interne de types copiée.

## Diagnostics

Codes relation.unreadable, relation.json_invalid, relation.schema_version_unsupported, relation.structure_invalid, relation.type_unsupported et relation.entity_missing.
Erreurs globales localisées au document ; erreurs d’item localisées par source_index. Messages sobres, sans contenu de ligne ni traceback.
Les références from/to sont comparées aux noms des EntityInfo disponibles, sans accès disque additionnel. Une entité invalide n’est pas une cible disponible.
Une relation structurellement lisible avec référence manquante reste affichée et reçoit une anomalie ; elle ne doit pas être interprétée comme validée. Les auto-relations sont conservées. Aucun arbitrage de doublons de noms d’entités ni validation métier exhaustive.

## Lecture et confinement

Réutilisation exacte de _read avec le descripteur déjà ouvert de mvc/entities : contrôle sans suivi de lien, fichier régulier, O_NOFOLLOW/O_NONBLOCK, comparaison samestat et fermeture du descripteur.
MAX_SOURCE_BYTES (1 Mio), vérification de taille et lecture bornée, UTF-8/BOM. JSON non standard, erreur d’encodage ou dépassement produisent une anomalie contrôlée.
Le refus des parents liés reste celui du lecteur d’entités ; l’erreur globale est alors entity.unreadable et aucun contenu de relations n’est ouvert.

## Intégration Entity Explorer

Même read_entities, même EntityExplorerTool, même registre à exactement trois Tools. Aucun changement du contexte ou de la composition Web.
La lecture des relations suit celle des entités, dans le même appel ; aucun cache, chaque GET recommence les contrôles.

## Intégration Web

Section Relations sous les entités : type, source, nom, cible, détails FK/pivot, inverse_name et champs pivot dans details natifs.
Compteurs d’entités et de relations interprétées. Source et index affichés en texte, sans lien /source.
Section Anomalies existante réutilisée. Document absent ou vide : « Aucune relation déclarée. » ; erreur de document sans relation interprétable : « Aucune relation interprétable. ».
Échappement Jinja, navigation active et no-store conservés. Aucun script, graphe, route ou Tool ajouté.

## Sécurité

Seules les ouvertures des JSON canoniques et de relations.json sont autorisées dans les sentinelles. SQL, Python et JSON alternatifs ne sont pas ouverts.
Sentinelles sur exec, eval, subprocess.run/Popen et imports mvc.*. Les données déclarées ne servent jamais de chemin d’accès fichier.
Les autorisations de la sentinelle FD-ENTITIES-001 sont étendues uniquement au fichier fixe désormais autorisé.

## Non-écriture

Le test Bridge compare tailles, octets et mtime de tous les fichiers de la fixture avant/après l’analyse.
Le contrôle installé compare aussi les instantanés avant/après chaque consultation ; les seules modifications volontaires sont celles du script de test entre les GET.
Aucun générateur, SQL ou écriture du projet dans le Tool. Dépôt Forge de référence intact.

## Fichiers créés

- tests/test_entity_relations.py
- docs/rapports/FD-ENTITIES-002.md

## Fichiers modifiés

- forge_design/forge/entities.py : modèles, lecture et diagnostic des relations.
- forge_design/web/templates/entities.html : section Relations et index des anomalies.
- tests/test_entities.py : autorisation de lecture du fichier fixe.
- docs/tools/entity-explorer.md : contrat et limites des relations.
- docs/02-architecture.md : enrichissement du résultat et nouvelle source autorisée.

## Tests ajoutés

33 nouveaux cas : valeurs/ordre/défauts/auto-relation/entité devenue illisible, sept documents invalides, treize items invalides avec continuation, cinq refus de lecture, non-exécution/non-écriture, parcours HTTP, quatre références manquantes et parent lié.
Les scénarios couvrent les deux directions, inverse_name, les quatre politiques, id/unique_pair stricts, plusieurs champs pivot, types/contraintes, BOM, absence et document vide.
La continuation vérifie exactement les indices 0 et 2 affichables avec une seule anomalie à l’index 1. Les déclarations avec cibles manquantes sont explicitement conservées avec leur diagnostic.
Le HTTP contrôle les deux types, ordre, champs pivot, XSS, anomalies, état vide, no-store, navigation, absence de graphe/lien source et Route Explorer accessible. Les tests historiques de registre et absence de Tool sans courant restent actifs.

## Test réel

Copie temporaire du squelette Forge avec Article, Tag et Comment, contrats d’entité préparés par le constructeur JSON de la baseline vérifiée, uniquement pour fabriquer les fixtures.
Premier GET installé : many_to_many Article → Tag, pivot article_tag, article_id, tag_id et cascade.
Ajout volontaire de Comment → Article many_to_one dans relations.json : GET suivant affiche les deux types avec restrict et la FK. Aucun cache.
JSON ensuite rendu invalide : anomalie relation.json_invalid, entités toujours affichées. Route Explorer reste accessible.
XDG temporaire, serveur arrêté, thread terminé, socket fermé et port réutilisable.
Script/journal ignorés : tmp/verify_fd_entities_002.py et tmp/verify_fd_entities_002.log.

## Packaging

Wheel reconstruite et inspectée, Bridge et template mis à jour distribués. Installation temporaire --no-deps --no-index --target, processus Python -I avec origine importée vérifiée et runtime .venv.
Artefact : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `eb30d9af58b79049cec8cc1ebf67959a29599a5317b40c63128363968898b817`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| Git initial, historique, Forge main et contrat | Vérifiés |
| Tests ciblés initiaux entités/relations/Web | 57 réussis |
| pytest | 662 réussis, dont 33 nouveaux cas |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip check | No broken requirements found |
| git diff --check | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Wheel installée, deux types et relecture HTTP | Succès |

Outils .venv, Python 3.13.5 ; HTTP avec sockets locaux autorisés hors sandbox.
Lignes longues des fixtures formatées avant validation finale. Pip check a désactivé son cache utilisateur inaccessible sans erreur de dépendances.
Diff complet, tests nouveaux, documentation et rapport relus avant commit.

## Tests sautés

Aucun test pytest sauté. Aucun contrôle visuel navigateur, génération SQL/Python, exécution cible ou validation BDD revendiqué.

## Limites restantes

Validation structurelle minimale fondée uniquement sur les contrats JSON ; pas de validation métier Forge exhaustive, SQL, DB, graphe, comparaison modèle/base, génération ou édition.
Identifiants, unicités, compatibilité set_null/nullable et contraintes propres aux types pivot ne sont pas entièrement validés. Les déclarations à référence manquante restent visibles avec anomalie.
Bornes de lecture et primitives POSIX du ticket précédent conservées, sans instantané atomique du contenu ou plafond global de relations.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `feat: ajouter les relations à Entity Explorer (FD-ENTITIES-002)`.
Le hash et l’état final vérifiés sont communiqués dans la réponse de livraison.
