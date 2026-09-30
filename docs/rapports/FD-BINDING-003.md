# Rapport — FD-BINDING-003

## Ticket et objectif

Ajouter visible_if au format Design v0.1 et valider sa référence exacte vers une
variable booléenne du contrat, sans moteur d'expression ou évaluation runtime.

## État Git initial

main synchronisée avec origin/main à `0588156` — FD-BINDING-002.
Git status et dix derniers commits inspectés. Modification utilisateur de
FD-CONTRACT-001.md (« État Git initiala ») préservée exactement hors commit.
Aucun AGENTS.md trouvé. Baseline : 2226 tests.

## Sources fonctionnelles

Besoin « bouton visible si can_create », déclaré boolean dans le contrat.
La roadmap mentionne Condition, mais aucun bloc condition n'existe ; aucun
nouveau type de bloc n'est ajouté pour représenter ce besoin transversal.

## Limite du format avant ticket

Ni visible_if ni propriété conditionnelle dédiée. binding désigne une donnée ou
une action selon le type du bloc ; il ne peut pas porter simultanément cette
référence principale et une condition de visibilité.

## Décision visible_if

Chaîne non vide facultative sur tous les DesignNode et PageRoot. Exemple :
button avec binding=create et visible_if=can_create. Une seule référence exacte,
pas de visible_unless, négation, comparaison, AND/OR ou AST d'expression.

## Compatibilité format v0.1

Version maintenue à 0.1 : extension additive optionnelle, aucune propriété existante
modifiée et documents historiques toujours valides. Les anciens lecteurs stricts
peuvent refuser des documents utilisant le nouveau champ ; cette asymétrie est
explicitée dans la documentation. Les fixtures minimal/contacts sont inchangées.

## Schéma JSON

Seule addition à DesignNode.properties : visible_if, type string, minLength=1.
Non required, non nullable ; PageRoot l'hérite via la composition existante.
Vocabulaire des blocs, version, props, colonnes et chemins inchangés.
Tests de déclaration mis à jour ; visible_unless reste un exemple d'extra refusé.

## Modèles Pydantic

Une seule propriété ajoutée à _NodeProperties : visible_if: _Omissible[_NonEmpty]
avec défaut interne None. BeforeValidator refuse le null explicite. Absence
préservée par exclude_unset=True ; chaîne vide, nombres, booléens, objets/listes
refusés en dict et JSON, pour DesignNode et PageRoot. Concordance normative/générée
existante couvre automatiquement la nouvelle propriété optionnelle non nullable.

## Sémantique conditionnelle

Recherche exacte de visible_if dans contract.context. Absence : aucune issue.
Référence inconnue : unknown_variable ; variable non boolean : type_mismatch.
Les chaînes true, permission.create, !can_create, not can_create ou comparaisons
ne sont jamais évaluées : seule une clé littérale boolean peut les rendre valides.
Pas de strip/casefold, normalisation Unicode, découpage ou parcours de fields.

## Boolean contractuel

Seul le type boolean est accepté, sans truthiness de string/integer/number/object/
list. Aucun accès à une valeur runtime. Actions homonymes ignorées ; le namespace
context est exclusif pour visible_if. Les bindings principaux restent indépendants.

## Permissions

Le backend prépare une décision sous forme de variable booléenne. Forge Design
ne lit ni RBAC, rôle, politique, utilisateur ou session et ne décide pas des droits.
Il valide la référence déclarative, pas la visibilité réelle ou une autorisation.

## API publique

Exports ConditionalBindingIssue, ConditionalBindingResult et
validate_conditional_bindings(design, contract). Dataclasses gelées, issues tuple.
Entrées supposées validées Pydantic ; aucun appel automatique aux autres validateurs.

## Diagnostics

Codes design.condition.unknown_variable, design.condition.type_mismatch et
design.condition.analysis_truncated. Au maximum une erreur ordinaire par occurrence.
Message humain distinct du contrat machine. valid=True uniquement sans erreur et
sans troncature ; résultat incomplet toujours invalide.

## Locations

Erreur ordinaire : (..., "visible_if"), y compris ("root", "visible_if").
node_type conservé et champ binding égal à la référence visible_if. Le marqueur
de troncature vise le nœud déclencheur et binding peut être None si aucune condition
n'y figure. Aucun champ absent inventé dans les diagnostics.

## Parcours et bornes

Pile explicite d'itérateurs, parcours préfixe, ordre source, racine comprise.
MAX_DESIGN_NODES=4096, MAX_DESIGN_DEPTH=128 racine à zéro et MAX_DESIGN_ISSUES=512
marqueur compris réutilisés sans nouvelle constante. Exactement à la limite sans
surplus : pas de troncature. Premier surplus : arrêt global avec marqueur unique.
Si les 512 issues sont déjà occupées, la dernière est remplacée par le marqueur.
Priorité nœuds/profondeur/issues. Objets partagés analysés à chaque chemin ; cycles
synthétiques stoppés par les bornes, largeur consommée paresseusement.
Coût O(N) à profondeur bornée, accès dictionnaire O(1) moyen, pas d'index secondaire.

## Déterminisme

Même paire de modèles inchangés : mêmes résultats, locations et ordre. Aucun tri,
dédoublonnage ou dépendance à l'ordre des déclarations context.

## Pureté

Module sans filesystem, lecteur Design/Contracts, ToolRegistry, Web ou Jinja.
Tests bloquant open, os.open/stat/listdir/scandir, Path.open/read_text/read_bytes,
lecteurs, autres validateurs et model_dump pendant l'analyse. Props, binding,
columns, entity, fields et routes n'influencent pas la condition.

## Non-mutation

Payloads Design/Contract et identités children/nœuds/props/columns/context/actions
comparés avant/après. Résultats et issues gelés testés. Les conteneurs d'entrée
conservent leur mutabilité historique ; aucune revalidation ou réparation implicite.

## Round-trip I/O

Nouvelle fixture conditional.design.json ajoutée au test I/O existant : création,
lecture, réécriture identique, modification de view, update et nouvelle lecture.
Payload complet comparé, visible_if conservé exactement. Contrat/template/XDG
sentinelles inchangés. io.py ne nécessite aucune modification ; les tests de
révision, conflit et sécurité historiques restent actifs.

## Compatibilité nesting

nesting.py inchangé. La fixture suit page → section → container → button, toutes
relations autorisées. Aucun section → button introduit. Conditions sur tous les
types admises sans modifier les règles d'enfants. Nesting invalide n'empêche pas
l'analyse conditionnelle indépendante.

## Compatibilité bindings simples

bindings.py inchangé. button.binding résout create dans actions ; visible_if résout
can_create dans context. Nominal et homonymie testés. Un binding principal invalide
n'empêche pas la validation d'une référence conditionnelle correcte.

## Compatibilité tables

table_bindings.py inchangé. Les colonnes ne sont pas parcourues par le validateur
conditionnel. La visibilité d'une table ou d'un empty_state ne modifie pas leur
validation structurelle ou leur projection. Tests FD-BINDING-001/002 inchangés.

## Documentation

Design : ajout de visible_if au tableau de propriétés, correction de son ancien
statut hors format, section additive v0.1 et lien vers la fixture compatible nesting.
Bindings : exemple JSON, séparation action/condition, namespace exact, permissions,
diagnostics/bornes et limites. Architecture : context[boolean] + visible_if →
validateur pur. Jinja reporté à FD-GENERATE-002, données runtime à FD-PREVIEW-001.

## Fichiers créés

- forge_design/design/conditional_bindings.py
- tests/test_conditional_bindings.py
- tests/fixtures/design/conditional.design.json
- docs/rapports/FD-BINDING-003.md

## Fichiers modifiés

- forge_design/design/design.schema.json
- forge_design/design/models.py
- forge_design/design/__init__.py
- tests/test_design_schema.py
- tests/test_design_models.py
- tests/test_design_io.py
- docs/design/design-json.md
- docs/design/bindings.md
- docs/02-architecture.md

Contrats, Forge, Tools, Web, app.py, limits.py, dépendances et JavaScript inchangés.
Le diff utilisateur FD-CONTRACT-001.md reste hors ticket.

## Tests ajoutés

73 cas nouveaux : 41 conditionnels, 30 modèles/round-trips de fixture, 1 déclaration
schéma et 1 scénario I/O paramétré supplémentaire. Conditions sur 13 types et root,
six types context, noms littéraux/Unicode, namespace, fixture, erreurs ordonnées,
locations, gel, frontières nœuds/profondeur/issues, limites combinées, partage/cycle,
pureté/non-mutation et largeur paresseuse. Null/vide/types incorrects et dumps
avec omission testés en dict/JSON pour les deux modèles de nœud.

## Packaging

Wheel : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `0c8d0f92f44ec9d21f0a051592753fe3119de36add172e88404d46570d22b2e9`.
Archive inspectée : schéma, modèles, validateur conditionnel, bindings simples,
tables, nesting, io, exports et primitives historiques comparés aux sources.
Aucun tests/ ou tmp/ distribué ; Requires-Dist inchangés.

Installation temporaire --no-deps --no-index --target puis Python -I avec runtime
.venv. Provenance installée design/io/conditional_bindings vérifiée, schéma distribué
identique et visible_if déclaré. Contrat en mémoire : page_title:string,
contacts:list et can_create:boolean ; action create. Nominal valide, page_title
conditionnel donne type_mismatch, can_delete donne unknown_variable.
Copie temporaire du squelette Forge : fixture conditionnelle créée, relue, modifiée,
sauvegardée, relue puis conflit après changement externe. Payload/visible_if
conservés, sentinelles et XDG inchangés. Dépôt Forge Core intact.
Script/journal ignorés : tmp/verify_fd_binding_003.py et .log.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat |
|---|---|
| git status ; git log --oneline --decorate -10 | Baseline conforme, diff utilisateur identifié |
| pytest schéma/modèles Design | 225 réussis |
| pytest bindings simples/tableaux/conditionnels | 150 réussis |
| pytest tests/test_design_io.py | 71 réussis |
| pytest phase Design/Binding complète ciblée | 632 réussis |
| pytest -q --tb=short | 2299 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Installation temporaire, validation et I/O Python -I | Succès |

Outils .venv, Python 3.13.5. Suites historiques avec sockets et build isolé exécutés
hors sandbox. Une ligne longue du test schéma reformatée ; types des dictionnaires
de tests précisés après pyright, puis contrôles finaux sans erreur. Journal complet :
tmp/pytest_fd_binding_003.log. Diff et nouveaux fichiers relus avant commit.

## Tests sautés

Aucun test pytest sauté. mkdocs build --strict non applicable : aucune configuration
MkDocs présente dans ForgeDesign. Aucun navigateur ou rendu de visibilité revendiqué.

## Limites restantes

Références booléennes déclaratives uniquement. Pas de négation/comparaison/AND/OR,
expression Jinja, RBAC, permission résolue ou valeur runtime. Pas de génération,
preview, Web ou Tool. Validation séparée de l'I/O et des autres règles. Modèles
supposés structurellement valides et sans mutation concurrente ; analyse tronquée
jamais valide. Anciens binaires stricts susceptibles de refuser la propriété nouvelle.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `feat: ajouter les bindings conditionnels (FD-BINDING-003)`.
Modification utilisateur FD-CONTRACT-001 préservée hors commit ; Forge Core inchangé.
Hash et état final communiqués dans la livraison.
