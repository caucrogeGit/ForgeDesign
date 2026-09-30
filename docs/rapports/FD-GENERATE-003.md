# Rapport — FD-GENERATE-003

## Ticket et objectif

Étendre la génération en mémoire avec tables, colonnes et état vide, en réutilisant
le validateur de tables et la primitive Jinja de FD-GENERATE-002.
Aucune écriture, action CRUD ou modification du format Design.

## État Git initial

Main synchronisée avec origin/main à 5c651e0 — FD-GENERATE-002.
État réel et cinq derniers commits inspectés. Seule modification préexistante :
docs/rapports/FD-CONTRACT-001.md, titre « État Git initiala », préservée hors commit.
Aucun AGENTS.md dans le dépôt.

## Sources fonctionnelles

Ticket, générateur simple/control_flow, validateurs table/condition/nesting,
modèles Design/Contract et tests historiques examinés.
TableBindingInfo fournit statut, colonnes, positions et has_empty_state.

## Portée des tables

Binding list requis, table dynamique sans données runtime. Table invalide omise
en entier avec diagnostic ; les branches sœurs restent générables.
Une collection sans fields est permise si aucune colonne n'est déclarée.
Aucun nouveau package public ou modification des exports.

## Actions reportées

Aucun row_actions/table_actions dans le modèle ; table n'accepte que empty_state.
Aucune action create/edit/delete, lien, bouton HTTP, CSRF ou heuristique inventé.
Formulaires, pagination, tri, filtres, HTMX, layout et includes restent hors périmètre.

## Validation des tables

validate_table_bindings appelé une fois après les validations historiques.
Projection indexée par location, transmise au module tables.py sans relecture du
contrat. Statuts no_binding/unresolved_variable/type_mismatch/fields_unavailable
et valid des colonnes déterminent les diagnostics de génération.
Pas de doublon des erreurs de bindings simples des tables. Troncature de table :
analysis_truncated avec location finale, template vide.

## Colonnes

Ordre et index fournis par la projection. Labels statiques dans th,
binding de colonne dans {{ item.champ }}. Syntaxe simple commune obligatoire ;
aucun bracket access ou filtre. Colonne inconnue : une seule invalid_table_column
à root/.../columns/index/binding. Syntaxe refusée seulement si le champ est connu.
Zéro colonne : tr vide dans thead et dans le corps de la boucle.

## Variable locale item

Nom fixe item, sans dérivation d'entity ni singularisation de collection.
Collection nommée item également acceptée : for item in item, portée Jinja locale.
Tables imbriquées toujours interdites par nesting.

## Boucle Jinja

render_jinja_loop réellement appelée et instrumentée dans le test nominal.
Le module table fournit les lignes tr/td avec indentation relative ; la primitive
produit for/endfor. Pas de seconde implémentation de la boucle.

## HTML généré

Table/thead/tr/th puis tbody/for/tr/td/endfor, fermeture table.
Deux espaces par niveau et LF final conservés. Aucun attribut de preview.
La sortie nominale Nom/Email est comparée exactement et parsée par Jinja.

## État vide

has_empty_state de la projection pilote if collection / table / else / div.
Un seul enfant accepté. « Aucune donnée » : convention temporaire v0.1,
faute de propriété éditable. Classe du div conservée.
Plusieurs enfants : multiple_empty_states, table omise.
État vide conditionnel : unsupported_empty_state_condition, table omise.

Hors table, les règles nesting historiques rejettent déjà empty_state :
l'API publique renvoie invalid_nesting avant rendu, sans relâcher la validation.
Le test confirme également le fallback unsupported_block du moteur interne si
ce bloc lui est présenté directement. Cette priorité résout les exigences
« nesting conservé » et « empty_state autonome non supporté » du ticket.

## Conditions + état vide

Visible_if de table reprend l'enveloppe existante autour de toute sa représentation.
Ordre : if show_contacts, if contacts, table, else, état vide, endif, endif.
La préparation de table précède l'ouverture de visible_if.
Le validateur conditionnel reste appelé ; erreurs sur empty_state non propagées
comme invalid_condition, car toute condition sur cet enfant est refusée par la
règle dédiée, même si la variable est inconnue. Les autres conditions gardent
leur comportement précédent. Troncature du validateur toujours bloquante.

## Props et classes

Table fixée à table, état vide fixé à div ; seule class string acceptée.
Tag, style, autres props et class non string donnent unsupported_prop.
Échappement mutualisé dans l'émetteur général, sans changement de politique
pour les blocs historiques. Classes Tailwind restent explicites.

## Sécurité Jinja/HTML

Labels et classes : html.escape avec quotes, neutralisation des accolades Jinja
et CR/LF. Tests script, include, expression, guillemets et esperluette :
valeurs DOM décodées intactes, aucun script ou Include AST.
Identifiants de collection/champ hostiles refusés avant interpolation.
Aucun safe, filtre de formatage ou moteur Jinja exécuté ; parsing dans les tests.

## Diagnostics

Nouveaux codes generate.table_missing_binding, invalid_table_binding,
invalid_table_column, unsupported_field_syntax, multiple_empty_states,
unsupported_empty_state_condition. Réutilisation de unsupported_binding_syntax,
unsupported_prop, analysis_truncated et output_too_large.
Code et position pertinents sans doublon design.table.* ; complete=False dès
la première issue. Les limites restent globalement bloquantes.

## Bornes

MAX_TABLE_COLUMNS via le validateur, testé à la limite et au surplus.
MAX_DESIGN_NODES/DEPTH/ISSUES et MAX_GENERATED_TEMPLATE_CHARS inchangés.
Le corps temporaire des cellules vérifie son volume cumulé avant accumulation ;
toutes les lignes produites, y compris boucle et état vide, passent par l'émetteur.
Frontière exacte de sortie autorisée, surplus : template="" sans découpe.

## Déterminisme

Même entrée : template, ordre des colonnes/diagnostics et complete identiques.
Deux appels comparés ; aucun temps, hasard ou nom local calculé.

## Pureté

Tests bloquant open/os.open, Path.open/read_text/write_text, socket et subprocess.
Aucun import Forge runtime, DB, Web, contexte ou registre dans tables.py.
Pas de lecture ou écriture de fichier projet.

## Non-mutation

Comparaison profonde des modèles et conteneurs avant/après. Revalidation sur copies
conservée. Projection de table gelée seulement lue, sans mutation des colonnes.

## Compatibilité GENERATE-001/002

Tests historiques conservés ; deux cas paramétrés de bloc table/empty_state reporté
déplacés vers la nouvelle couverture, car ils sont maintenant générables ensemble.
Le test table conditionnelle attend désormais une table sous if au lieu d'une
omission. Les autres sorties, bindings, conditions, budgets et sécurité restent actifs.
Aucun changement des modèles, schémas, validateurs Design, Preview ou API publique.

## Documentation

Section Tables et états vides ajoutée au guide, descriptions précédentes mises à
jour. Flux table validation → colonnes → primitive → HTML/Jinja et état vide
décrits dans docs/02-architecture.md. Actions et limites explicitement reportées.

## Fichiers créés

- forge_design/generate/tables.py
- tests/test_generate_tables.py
- docs/rapports/FD-GENERATE-003.md

## Fichiers modifiés

- forge_design/generate/simple.py : orchestration, projection et émetteur commun.
- tests/test_generate_simple.py : seuls blocs encore reportés dans la matrice.
- tests/test_generate_control_flow.py : table conditionnelle désormais générée.
- docs/generate/template-generation.md
- docs/02-architecture.md

Exports, limites, pyproject.toml, JavaScript et modules hors génération inchangés.
Modification utilisateur FD-CONTRACT-001.md préservée.

## Tests ajoutés

34 cas : nominal exact, instrumentation validateur/boucle, 0/1/plusieurs colonnes,
ordre, condition/table/état vide imbriqués, erreurs collection/fields/colonne,
identifiants hostiles, labels/classes hostiles, props restreintes,
ambiguïtés empty_state, priorité nesting hors table, budgets colonnes et sortie,
pureté, déterminisme et non-mutation. Sorties complètes nominales parsées par Jinja.

## Validations ciblées

| Contrôle | Résultat |
|---|---|
| pytest simple + control_flow + tables | 152 réussis |
| pytest table_bindings + conditional_bindings + control_flow + tables | 174 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| git diff --check | Succès |

Aucun test ciblé sauté. Formatage/imports normalisés avant validation finale.
Forge Core propre et inchangé.

## Tests non exécutés

Suite globale non exécutée conformément au ticket. Pas de Node ou pip check.
Pas de wheel : tables.py appartient au package déjà déclaré, aucun export public
ou ressource ajouté. MkDocs strict non applicable, aucune configuration.
Aucun rendu runtime Jinja ou navigateur, aucun test visuel revendiqué.

## Limites restantes

Colonnes déclaratives et accès item.champ uniquement, sans filtre ni formatage.
Le futur consommateur fournit l'environnement Jinja et sa politique d'échappement.
Texte d'état vide fixe ; aucune condition propre à cet état, un seul accepté.
Actions de table sans modèle explicite reportées. Pas de validation navigateur
du CSS final, diff ou écriture. Le budget de sortie n'est pas un plafond de mémoire
globale des entrées et copies Pydantic.

## État Git final

Un commit local, rapport inclus, sans push.
Message : feat: générer les tables Jinja (FD-GENERATE-003).
FD-CONTRACT-001.md hors commit ; hash et état final communiqués à la livraison.
