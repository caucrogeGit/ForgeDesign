# Génération de templates simples — FD-GENERATE-001

## Objectif et API

`generate_simple_template(design: DesignFile, contract: ViewContract)` produit
du HTML/Jinja en mémoire. Les exports de `forge_design.generate` comprennent
TemplateGenerationResult(template, issues, complete) et
TemplateGenerationIssue(code, message, location), dataclasses gelées ; issues et
locations sont des tuples. Toute issue implique complete=False.

Aucun chemin projet reçu, fichier lu ou écrit, moteur Jinja exécuté, donnée
fictive injectée ou backend consulté. Le résultat est du code lisible, modifiable
à la main. Diff et écriture contrôlée sont des étapes futures distinctes.

## Mapping et limites fonctionnelles

| Bloc | Sortie |
|---|---|
| page | Enfants uniquement, aucun wrapper |
| section | section |
| container, grid | div |
| card | article |
| title | h2 |
| text | p |

Button, table, form, field, alert et empty_state sont omis avec unsupported_block,
ainsi que leur sous-arbre. Les autres branches supportées restent générables.
Une condition visible_if sur un bloc supporté produit unsupported_condition :
**le bloc et son sous-arbre sont omis**, pour ne pas produire de contenu sans
la condition demandée. Cela vaut aussi pour la racine.

Aucun layout, extends, block, include, formulaire fonctionnel, route, boucle,
condition, attribut data-forge-design-* ou style inline n'est inventé.
Les règles d'imbrication Design restent applicables : title se place sous card,
text ne peut pas être enfant direct de page, grid reste une feuille.

## Props et bindings

Props acceptées sur les éléments HTML : tag et class string. Tag est restreint à
div, section, article, header, footer, main, aside, p, span, h1 à h6.
Tag inconnu : fallback par défaut avec invalid_tag. Toute autre prop ou valeur
non string est ignorée avec unsupported_prop. Page n'ayant aucune balise, ses
props sont ignorées avec unsupported_prop.

Les classes restent explicites, sans transformation Tailwind ou CSS synthétique.
Les caractères HTML sont échappés. Les accolades sont encodées en entités HTML
pour empêcher l'ouverture d'expressions, directives ou commentaires Jinja ;
CR/LF sont également encodés pour conserver une ligne par élément textuel.
La valeur HTML décodée conserve exactement la chaîne de classe d'origine.

Title/text avec binding produisent `{{ page_title }}`, sans valeur de preview.
Le validateur existant exige une variable string présente dans le contrat.
Sans binding : contenu vide sans diagnostic. Les noms générables satisfont
`[A-Za-z_][A-Za-z0-9_]*` sur la chaîne entière ; constantes et mots d'expression
Jinja (true/false/none, variantes initiales majuscules, and/or/not/in/is/if/else/for)
sont exclus pour ne pas changer le sens de la référence. Les clés pointées,
tirets, espaces, Unicode ou fragments Jinja donnent unsupported_binding_syntax
et un contenu vide. Aucun accès de chemin ou expression libre.

## Validation et diagnostics

Avant sérialisation, un parcours itératif borne les occurrences et la profondeur,
cycles synthétiques compris. Les modèles sont ensuite copiés par
model_dump(exclude_unset=True) puis model_validate. Les mutations invalides
produisent invalid_design ou invalid_contract, sans template.
Les erreurs attendues de validation/sérialisation sont capturées, sans catch global.

validate_design_nesting est appelé avant toute génération : invalid_nesting avec
les chemins originaux, sortie vide. validate_design_bindings est ensuite appelé ;
les erreurs title/text deviennent invalid_binding, conservent leurs locations et
bloquent toute sortie. Les bindings des blocs reportés ne bloquent pas à eux seuls
les autres branches. Une troncature de validation reste bloquante.

Les codes portent tous le préfixe generate :

- invalid_design, invalid_contract, invalid_nesting, invalid_binding ;
- unsupported_binding_syntax, unsupported_block, unsupported_condition ;
- invalid_tag, unsupported_prop ;
- analysis_truncated, output_too_large.

Les issues de validation précèdent le rendu ; les issues de rendu suivent l'ordre
source. Pas de déduplication. Les erreurs de revalidation ont une location vide ;
les autres ciblent le nœud, la propriété ou le binding concerné.

## Lisibilité

Deux espaces par niveau HTML, sans niveau supplémentaire pour page.
Text/title et conteneurs vides sont sur une ligne ; conteneurs avec enfants ont
une ouverture et une fermeture sur leurs lignes propres. Tout résultat non vide
finit par un unique LF. Une page vide donne template="", issues=(), complete=True.

```jinja
<section class="max-w-5xl mx-auto py-8">
  <h1 class="text-3xl font-bold">{{ page_title }}</h1>
</section>
```

## Bornes, pureté et limites

MAX_DESIGN_NODES=4096 (racine comprise), MAX_DESIGN_DEPTH=128 (racine à zéro),
MAX_DESIGN_ISSUES=512 (marqueur terminal compris). Le précontrôle parcourt aussi
les branches qui seront omises. Les références partagées comptent par occurrence.
En cas de surplus, analysis_truncated et aucune sortie ; le dernier diagnostic
est remplacé par le marqueur si nécessaire.

MAX_GENERATED_TEMPLATE_CHARS=1_000_000 compte indentation, échappement et LF.
Un dépassement retourne template="" avec output_too_large, sans tronquer une
balise ou expression. Ce n'est pas une limite de mémoire totale : objets d'entrée,
copies Pydantic et chaînes temporaires existent indépendamment du budget de sortie.

Aucune mutation des entrées, hasard, accès fichier, réseau, subprocess, Forge
runtime ou Web. Aucune nouvelle dépendance ni Tool. Preview et formats
Design/Contract inchangés. Jinja est parsé seulement dans les tests, jamais rendu.
Le consommateur futur devra fournir son environnement Jinja et sa politique
d'auto-échappement ; ce ticket génère uniquement le texte du template.
Des choix de tags incompatibles peuvent rester sémantiquement invalides en HTML :
la whitelist protège la syntaxe, elle ne remplace pas une validation navigateur.

FD-GENERATE-002 ajoutera conditions et primitive de boucle ;
FD-GENERATE-003 traitera les tables et états vides.
