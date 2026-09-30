# Rapport — FD-PREVIEW-002

## Ticket et objectif

Produire en mémoire un fragment HTML à partir de DesignFile et d'un mapping de
données, avec bindings, conditions et tableaux. Aucun template utilisateur lu ou
écrit, génération Jinja, backend, route, serveur ou Tool ajouté.

## État Git initial

main synchronisée avec origin/main à df1204e — FD-PREVIEW-001.
État Git et dix derniers commits inspectés. La modification utilisateur existante
dans docs/rapports/FD-CONTRACT-001.md (titre « État Git initiala ») est préservée
hors ticket et hors commit. Aucun AGENTS.md trouvé dans le dépôt.

## Sources fonctionnelles

Ticket FD-PREVIEW-002, modèles Design/Pydantic, limites centralisées, générateur
FD-PREVIEW-001, validateurs de bindings simples/tableaux/conditions et fixtures
contacts-list examinés. Les conventions existantes de données restent inchangées.

## API publique

render_preview(design: DesignFile, data: Mapping[str, object]) retourne
PreviewRenderResult(html, issues, complete).
PreviewRenderIssue(code, message, location) et PreviewRenderResult sont des
dataclasses gelées. Issues et locations sont des tuples, sans sévérités nouvelles.
Les trois symboles sont exportés depuis forge_design.preview.

## Fragment HTML

Fragment sans doctype ni enveloppe html/body. La racine porte
data-forge-design-preview="page", chaque bloc rendu data-forge-design-type.
Les éléments sont émis dans l'ordre source. Aucun fichier HTML n'est écrit.

## Mapping des blocs

page/container/grid → div ; section → section ; card → article ; title → h2 ;
text → p ; button → button ; table → table ; form → form ;
field/alert/empty_state → div. Les 13 types existants sont conservés.

## Props

Seules tag/class string sont supportées. Tag s'applique à page, section,
container, grid, card, title et text. Whitelist : div, section, article, header,
footer, main, aside, p, span, h1 à h6.
Tag inconnu : fallback avec invalid_tag. Tag connu sur un bloc non concerné,
prop inconnue ou tag/class non string : unsupported_prop, propriété ignorée.
Classes conservées après échappement, sans Tailwind synthétique ni CSS.

## Sécurité HTML

html.escape(..., quote=True) protège textes, cellules, labels et classes.
Les fixtures hostiles contiennent script, chevrons, esperluette et guillemets ;
HTMLParser vérifie les textes restaurés et les attributs réellement produits.
Les attaques par tag ou class ne créent aucun script ou événement.
Aucun MarkupSafe implicite, Jinja Environment, attribut arbitraire, style, href,
ressource externe ou JavaScript. Une donnée contenant des accolades Jinja reste
un texte ordinaire ; le renderer ne génère ni n'interprète cette syntaxe.

## Bindings texte

title/text accèdent à la clé exacte de data. Sans binding : contenu vide.
Clé absente : missing_value. Str, bool, int et float finis sont supportés ;
bool rendu true/false. None, dict/list, floats non finis et conversion d'entier
refusée par Python donnent unsupported_value et un texte vide.
Aucune résolution de chemin, expression ou conversion naïve d'objet.

## Conditions

visible_if absent : rendu normal. True : bloc rendu ; False : sous-arbre ignoré.
Clé absente : missing_condition ; valeur non bool : condition_type_mismatch.
Ces deux cas masquent aussi le bloc et ses descendants. Aucune truthiness ;
racine et états vides suivent la même règle.

## Tables

Binding list uniquement. Sans binding : table vide ; clé absente : missing_value ;
autre valeur : table_type_mismatch. Thead et tbody sont toujours structurés.
Les labels de colonnes sont échappés ; l'ordre des colonnes et lignes est conservé.
Ligne non dict : une row_type_mismatch et cellules vides. Champ absent :
missing_field. Les cellules suivent les règles scalaires des textes.
Les accès sont exacts, indépendants de l'ordre interne des clés de ligne.

## Empty state

Une table vide rend ses enfants directs empty_state après sa fermeture, comme
frères HTML : aucun div inséré dans table. Une table sans binding ou avec binding
invalide suit également ce fallback. Une liste non vide supprime ces enfants.
Les autres enfants directs d'une table sont ignorés. Hors table, empty_state
reste un bloc div. « Aucune donnée » appartient au renderer de preview.

## Formulaires

Form est un conteneur structurel sans action/method. Field est un div sans
contrôle de saisie. Button garde type="button" et le texte interne « Action »,
sans résoudre son binding contractuel, créer un lien ou soumettre un formulaire.

## Diagnostics

Onze codes préfixés preview : invalid_tag, unsupported_prop, missing_value,
unsupported_value, missing_condition, condition_type_mismatch,
table_type_mismatch, row_type_mismatch, missing_field, analysis_truncated,
output_too_large. Chaque issue implique complete=False.
Ordre de parcours conservé, sans déduplication. Les locations partent de root ;
les cellules utilisent rows/index/columns/index/binding pour localiser les
valeurs runtime. Aucun diagnostic de validation n'est fusionné implicitement.

## Bornes

MAX_DESIGN_NODES=4096, racine comprise ; MAX_DESIGN_DEPTH=128, racine à zéro ;
MAX_DESIGN_ISSUES=512 ; MAX_TABLE_COLUMNS=512. Nouvelle limite centralisée :
MAX_PREVIEW_HTML_CHARS=1_000_000, caractères après échappement, pas octets UTF-8.
Les nœuds effectivement visités sont comptés. Les descendants masqués et les
enfants de table non vide ne sont pas parcourus. Pour une table vide, chaque
enfant direct examiné consomme un nœud même s'il est ensuite ignoré.

Les lignes consomment le budget HTML, même avec zéro colonne. Les chaînes déjà
trop grandes sont rejetées avant expansion. Le dépassement de sortie abandonne
tout le fragment et retourne un div data-forge-design-preview-error="output-too-large".
Les autres budgets utilisent le marqueur analysis-truncated. Aucune découpe
de balise ni restitution de HTML partiel. Le marqueur terminal remplace la dernière
issue lorsque le tuple aurait dépassé sa limite. Frontières exactes autorisées.
La récursion bornée traite également les cycles introduits après validation.

## Déterminisme

Même Design, mêmes données et ordre : mêmes caractères HTML, issues et complétude.
Aucun hasard, horloge, identifiant généré ou ordre de set utilisé dans le rendu.

## Pureté

Tests bloquant open/os.open/Path.open/read_text, socket, subprocess, lecteur
Design, générateur de données et validateurs nesting/bindings simples/tableaux/
conditions pendant le rendu. Aucun import Web, Forge, registre ou contexte dans
le renderer. Le scénario installé bloque aussi les accès fichiers.

## Non-mutation

Payloads avant/après comparés, identités des conteneurs Design, colonnes et données
conservées. MappingProxyType accepté. Deux appels égaux, résultat gelé vérifié.
Aucune modification des listes ou dicts de lignes.

## Compatibilité Preview Data

Fixture contacts-list avec generate_preview_data : Exemple, trois lignes,
Nom/Email/Téléphone et contact@example.test. La fixture choisit un tag header
pour son bloc section et h1 pour son texte ; ces props sont conservées.
Générateur et ses tests historiques inchangés. Les résultats de génération et de
rendu restent indépendants ; l'appelant fournit explicitement preview.data.

## Compatibilité Design/Bindings

Aucun changement des modèles, schémas, validateurs ou lecteurs. Aucun appel de
validation implicite. Les suites bindings simples, tableaux et conditions restent
actives ; 258 tests combinés avec la preview réussissent.

## Documentation

docs/preview/static-preview.md étendu : API, mapping, props, sécurité, conditions,
tableaux, états vides, diagnostics, budgets et limites.
docs/02-architecture.md décrit ViewContract → données fictives + DesignFile →
renderer → fragment local. Aucune configuration MkDocs dans le dépôt.

## Fichiers créés

- forge_design/preview/render.py
- tests/test_preview_render.py
- docs/rapports/FD-PREVIEW-002.md

## Fichiers modifiés

- forge_design/preview/__init__.py : exports publics.
- forge_design/limits.py : borne HTML.
- docs/preview/static-preview.md : contrat du renderer.
- docs/02-architecture.md : pipeline en mémoire.

Contracts, Design, Bridge, Tools, Web, app.py, pyproject.toml et JavaScript inchangés.
La modification utilisateur FD-CONTRACT-001 reste hors commit.

## Tests ajoutés

74 cas : fragment minimal, 13 types, whitelist et props rejetées, échappement
texte/cellules/labels/classes, scalaires, valeurs non supportées, bindings absents,
conditions strictes et racine masquée, contacts nominaux, tableaux et ordre,
diagnostics localisés, états vides, frontières de nœuds/profondeur/issues/colonnes,
budget HTML après échappement, lignes sans colonnes, cycles et nœuds partagés,
pureté, déterminisme, non-mutation et gel du résultat.
Les assertions HTML passent par un parseur et vérifient aussi la fermeture des
balises ; aucun test de navigateur réel revendiqué.

## Packaging

Wheel reconstruite : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : 3fc38ec4f04249a364c4020d996bf39a6fc3f47cafff07c38729904f2e49537e.
Archive inspectée : preview/__init__.py, data.py, render.py et limits.py identiques
aux sources. Aucun tests/ ou tmp/ distribué ; dépendances runtime inchangées.

## Installation réelle

Installation temporaire --no-deps --no-index --target, puis Python -I avec
provenance installée de preview, data et render vérifiée.
ViewContract et DesignFile contacts construits en mémoire. Vérifications :
section, Exemple, table à trois lignes, email, bouton conditionnel True/False,
injection script échappée, contacts=[] affichant Aucune donnée, déterminisme et
données initiales préservées. Accès fichiers bloqués pendant les opérations.
Aucun serveur nécessaire. Script/journal ignorés : tmp/verify_fd_preview_002.py
et tmp/verify_fd_preview_002.log.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat |
|---|---|
| Git initial et dix derniers commits | Baseline conforme |
| pytest -q tests/test_preview_data.py tests/test_preview_render.py | 108 réussis |
| pytest bindings simples/tableaux/conditions + preview | 258 réussis |
| pytest -q --tb=short | 2407 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | Aucune dépendance cassée |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Inspection et installation wheel, Python -I | Succès |

Outils .venv. Suite complète hors sandbox pour ses sockets HTTP historiques ;
build isolé hors sandbox pour ses dépendances. Scénario installé exécuté sans
élévation. Les types list/dict runtime ont été précisés pour pyright et l'ordre
d'import corrigé avant validation finale. Journaux ignorés :
tmp/pytest_fd_preview_002.log et tmp/wheel_fd_preview_002.log.

## Tests sautés

Aucun test pytest sauté. MkDocs strict non applicable faute de configuration.
Aucun navigateur, iframe, rendu visuel ou lecteur d'écran testé.

## Limites restantes

Fragment structurel sans CSS, responsive ou backend. Texte de bouton et état vide
fixe ; formulaires sans contrôles. Classes non interprétées. Aucun appel des
validateurs : des imbrications Design ou choix de tags incohérents peuvent produire
une structure HTML sémantiquement invalide malgré des balises équilibrées.
Les entrées doivent conserver leur structure Pydantic valide ; mutations
arbitraires/concurrentes et méthodes Python personnalisées hors contrat.
Le budget porte sur les caractères de sortie, pas une limite mémoire totale :
les objets d'entrée existent déjà et l'échappement alloue une chaîne temporaire.
La future enveloppe navigateur appartient à FD-PREVIEW-003.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : feat: rendre la preview HTML locale (FD-PREVIEW-002).
FD-CONTRACT-001.md préservé hors commit ; dépôt Forge Core propre et inchangé.
Hash et état après commit communiqués dans la réponse de livraison.
