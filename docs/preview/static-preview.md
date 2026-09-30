# Prévisualisation statique — données fictives

FD-PREVIEW-001 prépare un contexte Python sérialisable JSON depuis un ViewContract
validé. Il ne rend pas de HTML ; le renderer local appartient à FD-PREVIEW-002.

```python
from forge_design.preview import generate_preview_data

result = generate_preview_data(contract)
# result.data : dictionnaire fictif ; result.issues : tuple ; result.complete : bool
```

## Valeurs fixes

| Type | Valeur preview |
|---|---|
| string | `"Exemple"` |
| boolean | `true` |
| integer | `42` |
| number | `12.5` |
| object | Objet construit depuis fields, sinon `{}` |
| list | Trois objets construits depuis fields, sinon `[{}, {}, {}]` |
| email (field) | `"contact@example.test"` |
| date (field) | `"2026-05-16"` |

42 et 12.5 sont des conventions explicites. La date est l'exemple fixe du cadrage,
jamais la date courante. Email/date sont des chaînes. Aucun hasard, Faker, UUID,
datetime Python ou Decimal. Les types bool/int/float restent distincts.

## Objets et listes

ViewContextVariable.fields est l'unique source des propriétés fictives pour object
et list. Fields absent ou vide est valide. L'ordre du contexte et des champs est
préservé exactement, sans tri, normalisation Unicode ou transformation des noms.
Les métadonnées label/entity et actions sont ignorées ; aucun nom de champ n'est
inféré depuis une entité réelle. Les éventuels fields sur un scalaire top-level
n'interviennent pas dans la génération de sa valeur.

Les types de champs supportés sont exactement string, boolean, integer, number,
email, date, object et list. Un champ object donne un nouveau `{}`, un champ list
un nouveau `[]` : fields ne décrit pas de structure récursive. Ce dernier cas est
distinct de la variable top-level list, qui produit toujours trois objets.

Les trois objets d'une liste ont des valeurs égales mais des identités distinctes,
y compris leurs conteneurs de champs. Aucun partage mutable entre lignes,
variables ou appels. Modifier les données retournées n'affecte pas le contrat
ni les prochaines générations.

## Types inconnus et complétude

Un type de champ non supporté, tel que money, uuid, image ou une chaîne Unicode
inconnue, est omis. Aucun None ou contenu arbitraire n'est injecté. Une issue
preview.unsupported_field_type est produite par définition de champ, pas trois
fois pour les instances d'une liste. Location :
("context", "contacts", "fields", "avatar"). Les issues suivent l'ordre déclaré.

Le parent reste présent avec les seuls champs générables. complete=False si un
champ est omis ; sinon complete=True. Un contexte vide donne data={}, issues=()
et complete=True. Il n'y a aucune erreur pour label/entity/actions/fields absents.

PreviewDataResult et PreviewDataIssue sont des dataclasses gelées ; issues est un
tuple. **Le gel reste superficiel** : data contient des dicts/listes ordinaires,
mutables pour le futur renderer. Le même contrat inchangé produit toujours les
mêmes valeurs, ordre, diagnostics et complétude.

## Portée et limites

Aucun DesignFile, binding, rendu HTML/Jinja, route, backend Forge, DB, réseau,
subprocess, filesystem ou contexte Web n'est consulté. Aucune mutation du contrat,
revalidation Pydantic ou résolution d'entité. L'entrée doit conserver son contrat
structurel validé ; les mutations arbitraires ou concurrentes ne sont pas prises
en charge.

Complexité O(V+F), avec facteur fixe trois pour les objets de liste. Pas de récursion
métier ni de nouveau plafond : temps, mémoire et nombre de diagnostics suivent la
taille du contrat en mémoire fourni. Le lecteur de contrat garde ses propres bornes,
mais un contrat synthétique peut être beaucoup plus grand.

Les booléens sont toujours True, les listes top-level toujours non vides : ce jeu
nominal n'exerce ni les branches False ni les empty_state de la preview.
Aucune variante de scénario n'est ajoutée au générateur. Le renderer FD-PREVIEW-002
ci-dessous consomme ces données ; aucune route, page ou Tool n'est créé.

## Rendu HTML local — FD-PREVIEW-002

`render_preview(design: DesignFile, data: Mapping[str, object])` retourne une
`PreviewRenderResult` gelée : html, issues (tuple de PreviewRenderIssue gelées),
complete. Chaque issue porte code, message et location (tuple str/int).
Ces trois symboles sont exportés par `forge_design.preview`.

L'appelant compose explicitement `generate_preview_data(contract)` puis
`render_preview(design, preview.data)` ; les diagnostics des deux opérations
restent indépendants. Le renderer n'appelle ni générateur ni validateur de bindings
ou d'imbrication. Il reçoit un Design Pydantic valide et un mapping en mémoire.

### Fragment et blocs

Le résultat est un fragment sans doctype, enveloppe navigateur, CSS, script,
ressource externe ou génération Jinja. La racine porte
`data-forge-design-preview="page"`, chaque bloc `data-forge-design-type`.

| Bloc | Balise par défaut |
|---|---|
| page, container, grid | div |
| section | section |
| card | article |
| title | h2 |
| text | p |
| button | button |
| table | table |
| form | form |
| field, alert, empty_state | div |

Seules les props `tag` et `class` de type string sont interprétées.
`tag` s'applique à page, section, container, grid, card, title et text.
Whitelist stricte : div, section, article, header, footer, main, aside, p, span,
h1, h2, h3, h4, h5, h6. Un tag inconnu conserve la balise par défaut avec
preview.invalid_tag. Un tag autorisé sur un autre bloc donne unsupported_prop.
Les autres props, ou tag/class non string, sont ignorées avec unsupported_prop.

Les classes explicites sont conservées et échappées, sans interprétation Tailwind.
Textes, cellules, labels et classes passent par html.escape avec quote=True :
même une chaîne présentée comme HTML sûr reste du texte. Aucun attribut libre,
style inline, href, action, method ou gestionnaire d'événement n'est produit.
Les accolades Jinja éventuellement présentes dans une donnée restent du texte ;
aucune syntaxe Jinja n'est générée ou évaluée.

### Bindings, conditions et tableaux

title/text cherchent leur binding par clé exacte, sans expression ni résolution
de chemin. Sans binding, le contenu reste vide sans issue. Une clé manquante donne
missing_value. Les valeurs str, bool, int et float finis deviennent du texte ;
bool utilise true/false. None, objets, listes, floats non finis ou entiers dont
Python refuse la conversion donnent unsupported_value et un contenu vide.

visible_if accepte exclusivement True ou False : False supprime tout le sous-arbre.
Une clé absente donne missing_condition, une autre valeur condition_type_mismatch ;
dans ces deux cas le sous-arbre est également ignoré. Aucune truthiness.

Une table produit thead/tr/th et tbody/tr/td dans l'ordre des colonnes et lignes.
Sans binding elle est vide ; clé absente : missing_value ; valeur autre qu'une
list : table_type_mismatch. Chaque ligne doit être un dict ; sinon une seule
row_type_mismatch est émise et toutes ses cellules restent vides. Les colonnes
accèdent à leur clé exacte : missing_field si absente, règle scalaire précédente
sinon. L'ordre interne des clés de ligne n'intervient pas.

Une table vide, y compris après binding absent ou invalide, rend ses enfants directs
empty_state **après la table, comme frères HTML**, pour éviter un div invalide
dans table. Une liste non vide supprime ces enfants. Les autres enfants directs
d'une table ne sont pas rendus. Les conditions propres aux empty_state s'appliquent.
Hors table, empty_state reste un div ordinaire. « Aucune donnée » et « Action »
sont des textes internes de preview, sans contrat avec un futur générateur Jinja.

button ignore son binding d'action et porte toujours type="button". form rend
seulement ses enfants sans action/method ; field reste un div, sans contrôle
de saisie ni soumission implémentée.

### Diagnostics et bornes

Les codes, tous préfixés par `preview.`, sont :

- invalid_tag, unsupported_prop ;
- missing_value, unsupported_value ;
- missing_condition, condition_type_mismatch ;
- table_type_mismatch, row_type_mismatch, missing_field ;
- analysis_truncated, output_too_large.

Toute issue implique complete=False, même si le reste du fragment est rendu.
Locations : chemins depuis root ; props et bindings ciblent leur propriété.
Pour les données d'une table : root/.../rows/index/columns/index/binding.
Les diagnostics suivent le parcours source sans tri ni déduplication.

Les limites centralisées réutilisées sont MAX_DESIGN_NODES=4096 (racine comprise),
MAX_DESIGN_DEPTH=128 (racine à zéro), MAX_DESIGN_ISSUES=512 et
MAX_TABLE_COLUMNS=512. Les nœuds visités sont comptés ; les descendants d'un bloc
masqué et les enfants d'une table non vide ne sont pas visités. Pour une table
vide, chaque enfant direct examiné consomme un nœud, même s'il n'est pas empty_state.

MAX_PREVIEW_HTML_CHARS=1_000_000 compte les caractères produits après échappement,
pas les octets UTF-8. Les lignes, même sans colonne, consomment ce budget.
Les valeurs trop grandes sont détectées avant leur expansion lorsque possible.
Le dépassement annule tout le fragment accumulé et retourne uniquement :

```html
<div data-forge-design-preview-error="output-too-large"></div>
```

Un dépassement de nœuds/profondeur/colonnes/issues utilise de même
`data-forge-design-preview-error="analysis-truncated"`. Le dernier emplacement
de diagnostic est réservé par remplacement au marqueur terminal si nécessaire.
Atteindre exactement une limite reste permis ; seul le surplus interrompt.

### Pureté et limites du rendu

Le rendu est déterministe pour les mêmes entrées et leur ordre, sans mutation du
Design, des listes ou dictionnaires de données. Aucun fichier, template utilisateur,
backend, réseau, DB, subprocess, Web, registre ou contexte projet n'est consulté.
Aucune route, iframe, écriture HTML ou génération utilisateur n'est ajoutée.

Le renderer ne répare pas la sémantique HTML d'un Design mal imbriqué ou de choix
de tags incompatibles entre eux. Les limites arrêtent aussi les cycles introduits
après validation, mais les mutations structurelles arbitraires/concurrentes et les
objets Python exécutant des méthodes personnalisées ne constituent pas son contrat.
Aucun navigateur réel ni rendu visuel responsive n'est testé ici. L'enveloppe de
preview appartient à FD-PREVIEW-003.

## Aperçu responsive — FD-PREVIEW-003

Les trois presets Forge Design v0.1 sont des conventions indicatives, sans hauteur
fixe ni prétention à reproduire un appareil ou le CSS final du projet :

| Mode | Largeur cible |
|---|---:|
| desktop | 1440 px |
| tablet | 768 px |
| mobile | 390 px |

Ces valeurs ne sont pas des normes universelles. Le contenu peut croître
verticalement ; max-width:100% réduit la largeur si le conteneur disponible est
plus étroit. Une largeur de div ne simule pas un viewport navigateur : elle ne
déclenche pas les media queries comme le ferait une iframe ou une fenêtre dédiée.

### API et composition

Exports publics depuis `forge_design.preview` :

- PreviewViewportMode : Literal desktop/tablet/mobile ;
- PreviewViewport : dataclass gelée, mode et width_px ;
- PREVIEW_VIEWPORTS : mapping immuable des trois presets gelés ;
- preview_viewport(mode) : retourne le preset ;
- wrap_preview_html(html, *, mode) : enveloppe un fragment existant ;
- render_responsive_preview(design, data, *, mode) : appelle une fois render_preview ;
- ResponsivePreviewResult : dataclass gelée, mode, width_px, html, issues, complete.

Un mode invalide produit ValueError avec le message stable
« Mode de preview inconnu : desktop, tablet ou mobile attendu. » avant rendu.
Aucun mode arbitraire ne devient un attribut HTML.

```python
from forge_design.preview import (
    generate_preview_data,
    render_preview,
    wrap_preview_html,
)

data = generate_preview_data(contract)
rendered = render_preview(design, data.data)
mobile = wrap_preview_html(rendered.html, mode="mobile")
tablet = wrap_preview_html(rendered.html, mode="tablet")
desktop = wrap_preview_html(rendered.html, mode="desktop")
```

Ce parcours réutilise le même rendu. L'API principale compose les deux étapes
pour un seul mode, en reprenant exactement le tuple issues et complete du renderer.
Elle n'appelle pas le générateur de données automatiquement.

### Enveloppe contrôlée

```html
<div data-forge-design-responsive="mobile" data-forge-design-width="390" style="width:390px;max-width:100%;margin:0 auto;">...fragment...</div>
```

Le style appartient exclusivement à l'enveloppe de simulation Forge Design.
Seuls les presets internes fournissent ses nombres ; aucune donnée utilisateur
ni prop du Design n'est transformée en style. Pas de hauteur, police, fond,
bordure, ombre, padding ou CSS supplémentaire. Cette exception au principe
« pas de style généré » du renderer n'est pas du code généré pour le projet.

Le fragment est concaténé exactement, sans parsing, reconstruction ou double
échappement. Un fragment d'erreur du renderer est également conservé.
**wrap_preview_html n'est pas un assainisseur** : l'appelant doit fournir le HTML
contrôlé de render_preview, jamais du HTML utilisateur arbitraire à rendre sûr.

La limite MAX_PREVIEW_HTML_CHARS est inchangée. Le wrapper ajoute seulement
l'ouverture et la fermeture contrôlées (surcoût fixe pour chaque preset), sans
second budget. La primitive sur fragment ne vérifie pas elle-même sa taille.

### Portée de la phase statique

Rendu déterministe, aucune mutation du Design, des données ou du résultat initial.
Aucun filesystem, backend Forge, réseau, navigateur, serveur, route HTTP ou iframe.
Aucune dépendance supplémentaire. Les renderers data.py et render.py restent
indépendants de l'enveloppe.

Aucune feuille Tailwind n'est embarquée : md:grid-cols-2 reste dans class, sans
reproduction de son comportement. Pas de calcul de breakpoint, DPR, orientation,
touch mode ou user-agent. Ces trois modes montrent une structure dans une largeur
cible ; ils ne remplacent pas les tests responsive réels. La preview avancée
devra traiter le rendu navigateur et CSS réel.

FD-PREVIEW-003 clôt la phase Preview statique ; la suite est FD-GENERATE-001,
génération d'un template simple.
