# Rapport — FD-GENERATE-002

## Ticket et objectif

Générer visible_if sous forme de conditions Jinja et fournir une primitive interne
de boucle sûre, sans nouveau bloc Design ni génération partielle de table.

## État Git initial

Le ticket avait d'abord été reçu sans son prérequis. Après réception de
FD-GENERATE-001, celui-ci a été réalisé et validé dans le commit local 6b6c694.
Ce ticket reprend la demande FD-GENERATE-002 déjà fournie.
Main est donc en avance d'un commit sur origin/main (7f53ebe) : écart expliqué par
le prérequis local, aucun push effectué. État Git et historique vérifiés.
La modification utilisateur FD-CONTRACT-001.md reste hors ticket et commit.

## Conditions Jinja

Source unique : node.visible_if. If/endif entourent toute la représentation HTML,
classes et binding inclus. La racine page reste sans balise ; sa condition entoure
ses enfants. Les sept types simples peuvent être conditionnés.
Une syntaxe non générable omet le sous-arbre avec unsupported_condition_syntax.
Les blocs fonctionnels restent unsupported_block lorsqu'ils sont rencontrés,
même avec une condition valide.

## Validation conditionnelle

validate_conditional_bindings appelé après les validations historiques.
Variable inconnue ou non boolean : invalid_condition dans le namespace generate,
location d'origine conservée et sortie vide. Pas de doublon design.condition.*.
Validation sur tout l'arbre, y compris blocs reportés. Troncature transmise sous
analysis_truncated. Aucune résolution du contrat réimplémentée.
Les permissions restent des booléens fournis par le backend.

## Syntaxe des identifiants

Regex ASCII fullmatch unique extraite de simple.py dans control_flow.py.
Règle commune aux bindings, conditions, collection et item : identifiant simple,
sans point, tiret, espace, filtre, slice ou appel.
Constantes et mots Jinja exclus comme dans FD-GENERATE-001. Le nom local loop
est refusé spécifiquement pour les boucles.

## Conditions imbriquées

Root/carte/titre conditionnels vérifiés ensemble, avec classe et binding.
Chaque niveau if ajoute un niveau logique. Ordre source et fermeture des
directives conservés. Pas de not/and/opérateur généré.

## Primitive de boucle

render_jinja_loop(collection, item, body, indent) avec arguments nommés, retourne
un tuple de lignes. Collection/item sont explicites, body un tuple de lignes
contrôlées sans LF/CR. Indent entier positif ou nul, bool exclu.
Body vide accepté ; indentation relative conservée, aucun ré-échappement.
Erreurs de programmation : ValueError. Fonctions internes au package,
non réexportées depuis forge_design.generate.

## Absence de bloc Loop

Schéma et modèles Design inchangés. Aucun loop/for/repeat ou mapping artificiel.
La primitive ne reçoit ni Design ni contrat, et n'est pas branchée sur table.

## Préparation FD-GENERATE-003

Le futur générateur de tables pourra fournir contacts/contact et des lignes tr/td.
Aucune singularisation, conversion Entity, état vide ou action de ligne ici.
Le futur appelant décidera les noms locaux, collisions de portée et budget.

## Indentation

Deux espaces par niveau logique HTML ou if/for. Condition imbriquée et root
conditionnelle comparées à des sorties exactes.
Même helper pour l'indentation simple et les boucles ; sorties sans condition
inchangées. LF final du générateur conservé.

## Sécurité Jinja

Noms hostiles include, foo.bar, foo-bar, foo | safe et expressions refusés.
Body de boucle : code contrôlé, pas une entrée HTML/Jinja utilisateur à assainir.
Classes toujours protégées par la politique FD-GENERATE-001.
Parsing Jinja uniquement en tests, comptage des nœuds If/For, aucun rendu runtime.

## Déterminisme

Même entrée : mêmes lignes, template, diagnostics et indentation.
Les boucles contacts/contact et users/user sont testées à plusieurs niveaux,
avec corps vide, une ligne ou plusieurs lignes.

## Pureté

Tests bloquant filesystem, socket et subprocess pendant conditions et boucle.
Aucun import Forge runtime, Web, contexte, registre ou DB.
Le test instrumente le validateur conditionnel existant pour vérifier sa réutilisation.

## Non-mutation

Comparaison profonde du Design et du contrat avant/après. Modèles revalidés sur
copies comme au ticket précédent ; primitive sur tuples sans mutation.

## Compatibilité FD-GENERATE-001

Les 60 tests précédents restent actifs ; seuls les deux cas de condition reportée
attendent maintenant la génération exacte if/endif. Toutes les sorties sans
condition, l'exemple roadmap, sécurité des classes, props, binding, revalidation,
budgets et pureté restent testés sans changer leurs attentes.
MAX_GENERATED_TEMPLATE_CHARS, exports publics et setuptools inchangés.

## Documentation

docs/generate/template-generation.md étendu avec conditions, validation,
identifiants, primitive interne, indentation et limites ; description courante
mise à jour pour ne plus annoncer des conditions reportées.
docs/02-architecture.md ajoute les deux flux et le futur consommateur table.

## Fichiers créés

- forge_design/generate/control_flow.py
- tests/test_generate_control_flow.py
- docs/rapports/FD-GENERATE-002.md

## Fichiers modifiés

- forge_design/generate/simple.py
- tests/test_generate_simple.py : deux cas de condition actualisés.
- docs/generate/template-generation.md
- docs/02-architecture.md

Contracts, Design, Preview, Bridge, Tools, Web, app.py, limites, exports,
pyproject.toml et JavaScript inchangés dans ce ticket.

## Tests ajoutés

60 cas : conditions simples et imbriquées sur sept types, root, classe/titre,
conditions inconnues/non boolean et syntaxe hostile, table toujours omise,
boucles nominales et indentées, douze noms invalides testés comme collection/item,
invariants de body/indent/local loop, budget de sortie avec directives,
déterminisme, pureté, non-mutation et appel au validateur existant.

## Validations ciblées

| Contrôle | Résultat |
|---|---|
| pytest génération simple + control flow | 120 réussis |
| pytest bindings + conditional bindings + génération | 231 réussis |
| pytest control flow après correction du typage de test | 60 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| git diff --check | Succès |

Noms de fonctions intermodules sans underscore pour respecter le contrôle
reportPrivateUsage ; elles restent internes au package et non réexportées.
Un appel de test par kwargs trop large a été remplacé par deux arguments explicites.

## Tests non exécutés

Suite globale non exécutée : aucun changement transversal, validations ciblées
suffisantes conformément au ticket. Pas de Node, pip check ou nouvelle wheel :
package déjà déclaré et vérifié au ticket 001, aucun export public ou packaging
modifié ici. MkDocs strict non applicable sans configuration.
Aucun moteur de rendu Jinja exécuté ni navigateur testé.

## Limites restantes

Booléens contractuels simples seulement ; aucun moteur d'expression ni autorisation.
La primitive de boucle organise du code de confiance et ne borne pas sa sortie
indépendamment de son futur appelant. Aucun nom local inféré, aucune gestion
automatique des collisions. Tables, états vides, formulaires, includes/layout,
diff et écriture restent reportés. Limites de revalidation/mémoire du ticket 001
inchangées.

## État Git final

Un commit pour ce ticket, distinct du commit FD-GENERATE-001 préalable.
Message : feat: générer les contrôles Jinja (FD-GENERATE-002).
Aucun push ; FD-CONTRACT-001.md préservé hors commit ; Forge Core inchangé.
Hash et état final communiqués dans la réponse de livraison.
