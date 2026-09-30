# Rapport — FD-BINDING-002

## Ticket et objectif

Valider les colonnes des tables contre les fields déclarés d'une collection et
proposer des colonnes en mémoire, sans mutation, génération ou accès projet.

## État Git initial

main synchronisée avec origin/main à `3497376` — FD-BINDING-001.
Git status et dix derniers commits inspectés. Modification utilisateur de
FD-CONTRACT-001.md (« État Git initiala ») préservée exactement hors commit.
Aucun AGENTS.md trouvé. Baseline : 2187 tests.

## Sources fonctionnelles

Ticket confronté aux modèles Design/Contracts existants. TableColumn possède
label/binding ; ViewContextVariable.fields est un dictionnaire facultatif de
chaînes libres. Le dictionnaire vide est effectivement accepté par Pydantic.

## Périmètre

Tables, colonnes configurées, champs disponibles, suggestions et indicateur d'état
vide. Aucun accès aux entités, relations, routes, actions de ligne, tri, pagination,
filtres, conditions, formulaires, filesystem ou génération HTML.

## Résolution de la collection

Recherche exacte context.get(table.binding), sans relancer FD-BINDING-001.
Statuts : no_binding, unresolved_variable, type_mismatch, fields_unavailable,
resolved. Binding absent/inconnu/non-list : aucune cascade d'erreurs de colonnes.
TableBindingResult.valid ne concerne que cette étape ; simple.valid=False et
tables.valid=True reste possible. L'appelant doit composer les deux résultats.

## Fields disponibles

La list résolue fournit fields, seule source des champs. available_fields conserve
l'ordre du dictionnaire. Les tuples de noms sont réutilisés pour les tables partageant
le même dictionnaire. entity est exposée comme information, sans résolution Forge.

## Fields absents

fields=None signifie structure non décrite. Sans columns ou avec [] : aucune erreur.
Avec colonnes : une seule issue fields_unavailable sur la propriété columns.
fields={} signifie explicitement aucun champ déclaré : chaque colonne est inconnue.
Les colonnes non vérifiables exposent valid=None et field_type=None ; cette adaptation
distingue l'absence de validation d'un champ effectivement inconnu (valid=False).

## Validation des colonnes

Par ordre source, recherche exacte column.binding dans fields. Label sans effet,
aucun parsing de point, strip/casefold ou normalisation Unicode. Colonnes dupliquées
admises. Projections avec index, label, binding, field_type et valid. Les colonnes
portées par d'autres types de blocs ne sont pas validées.

## Champs inconnus

Une issue design.table.unknown_field par colonne absente du dictionnaire, sans
suppression ni correction du Design. Plusieurs erreurs conservées dans l'ordre
source jusqu'au budget. Le nom de table et le nom de colonne restent disponibles.

## Types de champs

Chaîne exacte conservée, y compris email, telephone ou type personnalisé avec
espaces. Aucune enum, normalisation ou compatibilité column.type_mismatch :
TableColumn ne déclare pas de type attendu.

## Suggestions de colonnes

suggest_table_columns(variable) exige type=list, sinon ValueError. Fields absent
ou vide : (). Sinon tuple de SuggestedTableColumn gelées dans l'ordre déclaré,
avec binding, field_type et label=nom exact. Aucun title-case, TableColumn créé,
champ inféré depuis entity ou écriture dans DesignNode.columns.

## État vide

has_empty_state devient True à l'inspection d'un enfant direct empty_state de la
table. Pas de recherche indirecte, obligation, unicité, contenu ou binding ajouté.
Le repérage est intégré au parcours global borné, sans scanner d'abord une liste
d'enfants potentiellement énorme. En cas de troncature, False ne garantit pas
l'absence d'un état vide dans la partie non inspectée.

## API publique

Exports : TableBindingIssue, TableBindingInfo, TableBindingResult,
TableColumnBindingInfo, TableBindingStatus, SuggestedTableColumn,
validate_table_bindings et suggest_table_columns. Dataclasses gelées, collections
publiques tuples. API sans dépendance au contexte ou aux lecteurs projet.

## Diagnostics

Codes design.table.fields_unavailable, design.table.unknown_field et
design.table.analysis_truncated. Aucun unknown_variable/type_mismatch réémis.
Le résultat est invalide en présence d'erreurs propres à cette étape ou de troncature.

## Locations

TableBindingInfo vise le nœud. fields_unavailable vise (..., "columns") ;
unknown_field vise (..., "columns", index, "binding"). Troncature : nœud ou colonne
qui déclenche l'arrêt. Occurrences partagées : informations distinctes par chemin.

## Bornes

MAX_DESIGN_NODES=4096 racine comprise, MAX_DESIGN_DEPTH=128 racine à zéro,
MAX_DESIGN_ISSUES=512 marqueur compris, inchangés. Nouvelle constante unique :
MAX_TABLE_COLUMNS=512, par occurrence de table, même si collection non résolue.
Aucune copie préalable de toutes les colonnes. Une référence supplémentaire peut
être consommée pour détecter le surplus.

Borne exacte sans surplus : pas de troncature. Premier dépassement : arrêt global,
marqueur terminal unique, truncated=True et valid=False. Si les 512 diagnostics
sont déjà occupés, le dernier est remplacé. Les projections du préfixe et de la
table partiellement inspectée sont conservées.

Coût O(N+C) pour nœuds/colonnes, plus O(F) pour matérialiser les noms des dictionnaires
fields distincts. Le contrat fourni et ses suggestions restent complets : la borne
de colonnes configurées ne plafonne pas fields ni suggest_table_columns. La projection
de suggestions coûte O(F). Cette distinction est documentée sans troncature silencieuse.

## Déterminisme

Parcours préfixe itératif par pile d'itérateurs. Aucun tri ou dédoublonnage de colonnes.
Même paire de modèles inchangés → même résultat et ordre. Objets partagés analysés
à chaque occurrence ; cycles synthétiques arrêtés par les bornes.

## Pureté

Aucun filesystem, lecteur d'entités, ToolRegistry, Web ou génération dans le module.
Tests avec open, os.open/stat/listdir/scandir, Path.open/read_text/read_bytes,
read_design/read_view_contract et validateurs simple/nesting interdits.
Les fonctions ne consultent ni source_contract ni correspondance view/name.

## Non-mutation

Payloads Design/Contract comparés avant/après, identités children/columns/context/
fields conservées. Suggestions comparées à l'entrée. Immutabilité des DTO de
suggestion, table, colonne, issue et résultat vérifiée.

## Compatibilité FD-BINDING-001

bindings.py et tous ses tests restent inchangés. Il continue à ignorer les colonnes.
Le nouveau validateur ne relance pas le précédent et ne duplique pas ses diagnostics.
Composition nominale vérifiée sur la fixture contacts officielle.

## Compatibilité Contracts

Modèles, schéma, lecteur et liaison inchangés. fields absent/vide et types libres
respectent exactement le modèle existant. Aucune résolution d'EntityInfo.

## Compatibilité Design

Schéma, models.py, nesting.py, io.py et fixtures inchangés. Nesting invalide accepté
comme entrée de cette analyse indépendante. Aucun Web, Tool ou dépendance ajouté.
Dépôt Forge Core inchangé.

## Documentation

Section « Bindings de listes et tableaux — FD-BINDING-002 » ajoutée à bindings.md :
résolution, statuts, absence/vide, exactitude des champs, suggestions, état vide,
projections partielles et budgets. Architecture mise à jour avec le flux fields +
columns et la projection de suggestions.

## Fichiers créés

- forge_design/design/table_bindings.py
- tests/test_table_bindings.py
- docs/rapports/FD-BINDING-002.md

## Fichiers modifiés

- forge_design/design/__init__.py
- forge_design/limits.py : MAX_TABLE_COLUMNS uniquement.
- docs/design/bindings.md
- docs/02-architecture.md

Le diff utilisateur FD-CONTRACT-001.md reste hors ticket.

## Tests ajoutés

39 cas : fixture nominale, champs inconnus/ordre/locations, labels, doublons,
Unicode et clé pointée littérale, types libres, fields absent/vide, absence/inconnu/
non-list sans cascade, suggestions ordonnées et précondition, états vides directs/
indirects/multiples, tables imbriquées/partagées, bornes colonnes/nœuds/profondeur/
issues, cycle, largeur paresseuse, pureté, non-mutation et gel des résultats.
Tous les tests FD-BINDING-001 et historiques actifs sans modification.

## Packaging

Wheel : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `f237080fe1ef1b8f49b1facef1d30efd6fa61eb67da6b28ef576ba32960b14a4`.
Archive inspectée : exports, bindings.py, table_bindings.py, limits.py, modèles
Design/Contracts et schéma Design identiques aux sources. Tests/tmp non distribués.
Requires-Dist inchangés, aucune dépendance nouvelle.

Installation temporaire --no-deps --no-index --target, Python -I avec runtime .venv.
Provenance installée de table_bindings vérifiée. Contrat contacts et Design créés
en mémoire, open/Path.read_text interdits pendant le scénario. Bindings simples
et tables valides ; ajout adresse → unknown_field localisé ; fields absent avec
colonnes → fields_unavailable ; sans colonnes → valide. Trois suggestions dans
l'ordre, état vide direct détecté. Aucun fichier projet consulté.
Script/journal ignorés : tmp/verify_fd_binding_002.py et .log.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat |
|---|---|
| git status ; git log --oneline --decorate -10 | Baseline conforme, diff utilisateur identifié |
| pytest -q tests/test_design_bindings.py tests/test_table_bindings.py | 109 réussis |
| pytest modèles Contracts/Design, nesting, bindings simples/tableaux | 606 réussis |
| pytest -q --tb=short | 2226 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Installation temporaire et Python -I | Succès |

Outils .venv, Python 3.13.5. Suite historique avec sockets et build isolé exécutés
hors sandbox. Imports remis en forme par Ruff avant validation. Journal complet :
tmp/pytest_fd_binding_002.log. Diff, nouveaux fichiers et rapport relus avant commit.

## Tests sautés

Aucun test pytest sauté. mkdocs build --strict non applicable : aucune configuration
MkDocs dans ForgeDesign. Aucun navigateur requis pour ces projections pures.

## Limites restantes

Validité indépendante de la résolution principale ; composition avec FD-BINDING-001
nécessaire. Résultats partiels si troncature, état vide négatif alors non conclusif.
Fields disponibles et suggestions proportionnels à la taille du contrat fourni.
Aucune compatibilité de types de colonnes, résolution d'entité, condition, formulaire,
route, génération ou I/O. Modèles supposés structurellement valides et non mutés
concurremment. Le prochain ticket reste FD-BINDING-003.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `feat: valider les bindings de tableaux (FD-BINDING-002)`.
Modification utilisateur FD-CONTRACT-001 préservée hors commit ; Forge Core inchangé.
Hash et état final communiqués dans la livraison.
