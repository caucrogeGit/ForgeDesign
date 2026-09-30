# Rapport — FD-GENERATE-001

## Ticket et objectif

Créer un générateur HTML/Jinja simple en mémoire depuis DesignFile et ViewContract,
sans fichier utilisateur écrit, backend ou exécution du template.
Ce ticket fournit le prérequis manquant de FD-GENERATE-002.

## État Git initial

main et origin/main à 7f53ebe — FD-PREVIEW-003. État Git et dix derniers commits
inspectés. Le package generate n'existait pas. La modification utilisateur de
docs/rapports/FD-CONTRACT-001.md (« État Git initiala ») reste hors ticket et commit.
Aucun AGENTS.md dans le dépôt.

## Sources fonctionnelles

Ticket FD-GENERATE-001, modèles Design/Contract, validateurs nesting/bindings,
limites et conventions des tests examinés. Le générateur respecte les règles
d'imbrication actuelles ; il n'élargit pas les parents autorisés des blocs.

## Absence de layout implicite

Pas de extends, block, include, layout ou référence à un template inventé.
Le résultat est autonome et n'ajoute aucun champ au format Design.

## API publique

generate_simple_template(design, contract) retourne TemplateGenerationResult :
template, issues tuple et complete. TemplateGenerationIssue contient code,
message et location tuple. Deux dataclasses gelées, trois exports publics depuis
forge_design.generate. Toute issue implique complete=False.

## Blocs supportés

Page, section, container, grid, card, title et text exclusivement.
Les règles nesting restent inchangées : title sous card, text sous un parent
autorisé, grid feuille. Aucun nouveau type de nœud.

## Blocs reportés

Button, table, form, field, alert et empty_state omis avec unsupported_block.
Leurs enfants ne sont pas générés automatiquement. Les autres branches peuvent
produire un template partiel explicitement incomplet.
Visible_if sur un bloc supporté : unsupported_condition et omission du sous-arbre,
racine comprise. Aucun bloc conditionnel rendu inconditionnellement.

## Mapping HTML

Page ne produit aucun wrapper. Section → section, container/grid → div,
card → article, title → h2, text → p. Aucun attribut data-forge-design-*.
Les conteneurs vides sont sur une ligne ; les enfants respectent l'ordre source.

## Bindings Jinja

Title/text avec binding valide donnent {{ nom }} ; absence de binding donne
un élément vide. Aucune donnée fictive utilisée.
validate_design_bindings impose la variable string du contrat. Ses erreurs
title/text deviennent invalid_binding avec locations conservées et sortie vide.
Les erreurs de bindings des blocs reportés ne bloquent pas à elles seules les
autres branches. Une troncature du validateur est bloquante.

## Syntaxe des identifiants

Fullmatch ASCII [A-Za-z_][A-Za-z0-9_]*. Constantes true/false/none et variantes
initiales majuscules, opérateurs/mots and/or/not/in/is/if/else/for exclus :
ils ne doivent pas remplacer une référence par une expression ou constante.
Noms pointés, tirets, espaces, Unicode ou chaîne hostile : diagnostic
unsupported_binding_syntax et texte vide. Aucun moteur d'expression libre.

## Classes Tailwind

Classes conservées comme attribut HTML explicite, sans CSS synthétique.
Échappement HTML standard ; accolades encodées en entités pour neutraliser
également les délimiteurs Jinja. CR/LF encodés pour conserver les lignes.
La valeur HTML décodée reste identique à l'entrée.

## Props

Tag/class string seulement. Whitelist div/section/article/header/footer/main/
aside/p/span/h1–h6. Tag inconnu : fallback par défaut et invalid_tag.
Autres props ou valeurs non string : unsupported_prop. Page sans balise :
props ignorées avec diagnostic. Aucun attribut arbitraire, style ou événement.

## Lisibilité et indentation

Deux espaces par niveau HTML, page transparente. Title/text sur une ligne,
conteneurs non vides avec ouverture/fermeture séparées. LF final unique pour
tout template non vide. Page vide : template="", issues=(), complete=True.
L'exemple roadmap avec section, h1 et classes est comparé exactement.

## Revalidation des entrées

Précontrôle itératif des occurrences et profondeur avant model_dump, afin de
borner aussi les cycles synthétiques. Élément children de mauvais type :
invalid_design. Puis model_dump(exclude_unset=True) et model_validate pour les
deux modèles. Copies distinctes, sans modification des entrées.
ValidationError, ValueError de sérialisation et RecursionError capturées dans
ces étapes seulement ; aucun except Exception global.
Erreur Design/Contract : invalid_design/invalid_contract et aucun template.
validate_design_nesting est ensuite appliqué ; ses erreurs invalid_nesting
conservent leurs chemins et annulent toute sortie.

## Diagnostics

Namespace generate, codes : invalid_design, invalid_contract, invalid_nesting,
invalid_binding, unsupported_binding_syntax, unsupported_block,
unsupported_condition, invalid_tag, unsupported_prop, analysis_truncated,
output_too_large. Locations de revalidation vides ; autres locations structurelles.
Validation avant rendu ; diagnostics de rendu en ordre source.
Aucune traduction des messages d'entrée arbitraires dans le code généré.

## Bornes

MAX_DESIGN_NODES=4096, racine comprise ; MAX_DESIGN_DEPTH=128, racine à zéro ;
MAX_DESIGN_ISSUES=512, marqueur terminal compris. Précontrôle sur tout l'arbre,
y compris branches ensuite omises, références partagées comptées par occurrence.
En cas de dépassement, sortie vide et analysis_truncated.
La dernière issue est remplacée par le marqueur si le budget est plein.

MAX_GENERATED_TEMPLATE_CHARS=1_000_000 ajouté à limits.py. Caractères après
échappement, indentation et LF compris. Dépassement : output_too_large et sortie
vide ; aucune balise ou expression tronquée. Les copies Pydantic et allocations
temporaires ne constituent pas un budget mémoire global.

## Sécurité

Whitelist de tags, aucun attribut libre, échappement des classes y compris
syntaxes Jinja. Tests parser HTML sur guillemets/onclick et parser Jinja sur
{{ }}, {% include %}, {# #} dans class : aucune expression ou include créé.
Binding hostile jamais interpolé. Syntaxes nominales parsées avec Environment
uniquement en tests ; aucun rendu runtime ni import Jinja dans le générateur.
Pas de permissions, route, CSRF ou sémantique backend inventés.

## Déterminisme

Sortie, indentation, ordre des issues et complete stables pour les mêmes entrées.
Aucun hasard, horloge ou ID généré.

## Pureté

Tests bloquant open, os.open, Path.open/read_text/write_text, socket et subprocess
durant la génération. Aucun lecteur projet, Forge runtime, contexte, registre,
Web ou DB dans le package. Les cinq Tools existants sont vérifiés inchangés.

## Non-mutation

Payloads Design/Contract comparés avant/après ; identités children/context
conservées. Revalidation effectuée sur copies. Résultat gelé vérifié.

## Compatibilité Contracts

Aucun modèle ou lecteur modifié. Pas de résolution du source_contract, du chemin
template ou d'entité. Le contrat est explicitement fourni par l'appelant.

## Compatibilité Design/Bindings

Schéma, modèles, nesting, bindings et Preview inchangés. Les validateurs existants
sont réutilisés, pas réimplémentés. Tests historiques ciblés conservés.

## Documentation

Création docs/generate/template-generation.md : API, mapping, revalidation,
diagnostics, sécurité, indentation, budgets et limites.
docs/02-architecture.md décrit validation → génération mémoire → futur diff →
future écriture contrôlée. Conditions/boucles puis tables documentées comme suites.

## Fichiers créés

- forge_design/generate/__init__.py
- forge_design/generate/simple.py
- tests/test_generate_simple.py
- docs/generate/template-generation.md
- docs/rapports/FD-GENERATE-001.md

## Fichiers modifiés

- pyproject.toml : ajout explicite du package setuptools.
- forge_design/limits.py : borne de template.
- docs/02-architecture.md : flux de génération.

Aucune dépendance ajoutée. Modification utilisateur FD-CONTRACT-001 préservée.

## Tests ajoutés

60 cas : page vide, mapping, tags autorisés/interdits, classes et exemple roadmap,
bindings valides/absents/inconnus/mauvais type/syntaxe hostile, injection Jinja
dans les classes, blocs et conditions reportés, nesting, mutations invalides,
frontières nœuds/profondeur/issues/sortie, cycles, déterminisme, pureté,
non-mutation et gel. Frontière de profondeur testée avec budget réduit sur un
arbre légal ; cycle exercé avec la borne réelle.

## Validations ciblées

| Contrôle | Résultat |
|---|---|
| pytest -q tests/test_generate_simple.py | 60 réussis |
| pytest nesting + bindings + génération simple | 316 réussis |
| test_registry_contains_five_tools | 1 réussi |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| git diff --check | Succès |

Formatage et annotation Never du chemin d'arrêt corrigés avant validation finale.
Les mutations de conteneurs volontairement invalides provoquent des avertissements
Pydantic de sérialisation attendus, capturés explicitement dans les tests.

## Packaging

Wheel construite avec autorisation hors sandbox pour le build isolé :
tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : 2f611b4372f08341890fa6cb71ced3cc7c5239eead5d8a7964b9c2fd1512b517.
Archive inspectée : generate/__init__.py, simple.py et limits.py identiques aux
sources, aucun tests/ ou tmp/ distribué. Dépendances runtime inchangées.

Installation --no-deps --no-index --target temporaire. Python -I vérifie l'origine
installée du package, construit contrat/Design en mémoire et compare exactement
les lignes section/p avec {{ page_title }} et LF final. Parsing Jinja réussi,
sans exécution ; déterminisme vérifié. Aucun serveur utilisé.
Script/journal ignorés : tmp/verify_fd_generate_001.py et .log ;
journal build tmp/wheel_fd_generate_001.log.

## Tests sautés

Aucun test ciblé sauté. Suite globale non exécutée, conformément au ticket.
Node non relancé ; JavaScript inchangé. Pip check non requis, dépendances
vérifiées inchangées dans la wheel. MkDocs strict non applicable sans configuration.
Aucun navigateur ou test visuel revendiqué.

## Limites restantes

Blocs structurels/textuels seulement. Pas de condition, boucle, table, formulaire,
action, layout, diff ou écriture. Les props de page n'ont pas de cible HTML.
La sécurité des délimiteurs ne valide pas la sémantique de toutes les combinaisons
de tags HTML. Le consommateur futur choisira son environnement Jinja et son
auto-échappement. Contrats volumineux et copies Pydantic consomment de la mémoire
hors budget de sortie ; aucune mutation concurrente des entrées prise en charge.

## État Git final

Un seul commit local, rapport inclus, sans push.
Message : feat: générer les templates simples (FD-GENERATE-001).
FD-CONTRACT-001.md reste hors commit. Forge Core propre et inchangé.
Hash et état final communiqués dans la réponse de livraison.
