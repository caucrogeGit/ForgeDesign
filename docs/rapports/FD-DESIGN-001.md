# Rapport — FD-DESIGN-001

## Ticket et objectif

Définir uniquement le format normatif .design.json v0.1, source graphique structurée,
lisible et supprimable de Forge Design. Aucun modèle de blocs, lecteur/écrivain,
générateur, binding évalué ou interface.

## État Git initial

main synchronisée avec origin/main à `f72cb6b`. État Git et dix derniers commits
inspectés. Modification utilisateur du rapport FD-CONTRACT-001.md conservée
(« État Git initiala »), non modifiée et hors commit. Aucun AGENTS.md trouvé.
Baseline 1659 tests.

## Sources de cadrage

Ticket FD-DESIGN-001 et son exemple contacts : source précise du format v0.1.
Sections conception de vues du cadrage fonctionnel et de la roadmap, architecture
et packaging existants consultés. Baseline distante ../Forge origin/main vérifiée :
`73a956e587e5f169c028415e0e540c149cbaff56`. Dépôt Forge propre et inchangé.

## Rôle du .design.json

Source graphique éditable de Forge Design, jamais source unique du projet Forge.
Une application doit rester compréhensible et fonctionnelle sans Forge Design.
Aucun état opaque indispensable à son exécution.

## Convention physique

mvc/views/<vue>.design.json, par exemple contacts/list.design.json dans l'espace
views. source_contract relatif à mvc/views : contacts/list.view.json, sans préfixe
mvc/views/. Suffixe .view.json obligatoire ; chaîne non vide, au plus 4096 caractères.
Motif de segments excluant absolus, backslash, deux-points, segments vides et CR/LF ;
exclusions lisibles pour segments ./.., préfixe mvc/views/ et nom .view.json sans stem.
Pas de duplication complète de source_parts, de résolution ou d'ouverture filesystem.

## Version du format

version obligatoire, type string et const "0.1". Le flottant 0.1 n'est pas équivalent.
Cette version est explicite dans le cadrage, contrairement au contrat de vue minimal.

## Racine

Objet strict, champs obligatoires version/view/source_contract/root uniquement.
view : chaîne de 1 à 256 caractères, sans regex métier, trim ou normalisation.
root référence PageRoot ; racine unique, type page, children obligatoire.
Aucun champ template, metadata, editor, generated_at, hash ou roots.

## DesignNode

Objet strict ; type obligatoire, binding/props/columns/children facultatifs.
PageRoot compose DesignNode par allOf et renforce type=page et required children.
La strictesse est héritée, sans recopier les propriétés du nœud.
Aucun identifiant, action ou content inventé pour l'éditeur futur.

## Types de blocs initiaux

Vocabulaire exact : page, section, container, grid, card, title, text, button,
table, form, field, alert, empty_state. Représentation minuscules snake_case.
Choix explicite autorisé par le ticket : page reste dans DesignNode, donc admissible
structurellement en descendant jusqu'aux règles d'imbrication de FD-DESIGN-003.

## Props

Objet optionnel, clés non vides, valeurs PropValue string/boolean/integer/number.
Ni null, objet ou tableau imbriqué ; omission pour une propriété absente.
Integer est inclus dans number au sens JSON Schema, vocabulaire explicite conservé.
Tag/class restent des chaînes, chaînes vides permises ; aucun objet Tailwind/style
ni liste de propriétés propres à chaque bloc.

## Bindings

Chaîne non vide déclarative, sans contrôle d'existence dans un contrat.
Ne pas écrire d'expression Jinja ou métier ; aucune interprétation de chaîne.
Cette règle de contenu est documentaire, le schéma ne parse pas Jinja.
Pas de visible_if, if, unless ou condition. Phase FD-BINDING-001 future.

## Columns

Champ optionnel tableau de TableColumn strict. Label et binding non vides,
obligatoires. Aucun champ supplémentaire. Pas de condition type=table dans cette
première structure ; tableau vide admis.

## Children

Tableau récursif de DesignNode, optionnel pour descendants, obligatoire pour root.
Vide admis ; pas de règle Button→aucun enfant ou Form→Field. Ni profondeur métier,
ni taille fichier bornée dans le schéma : modèles/lecteurs futurs responsables.

## Séparation avec .view.json

Le contrat décrit les données disponibles ; le design décrit leur composition.
Aucun changement des modèles, schéma, reader ou linkage contractuels. Référence
source_contract textuelle sans chargement, liaison ou validation croisée.

## Séparation avec template

Le design est la source éditable ; le template .html est le résultat utilisable
par Forge. Suppressibilité normative : supprimer le .design.json ne doit pas casser
le template existant. Aucun chemin template dupliqué, aucune association réelle
par nom de fichier, aucune modification de HTML dans ce ticket.

## Données interdites

Secrets, tokens, credentials, données backend réelles, état runtime et état éditeur
opaque exclus architecturalement. Aucun zoom/viewport/selection/undo_stack ou
current_user/csrf_token à stocker. Les chaînes libres ne sont pas analysées pour
détecter secrets ou code ; props n'est pas un filtre sémantique de tous les noms.
Aucune exécution ou logique métier.

## Responsabilités reportées

FD-DESIGN-002 : modèles Pydantic ; 003 : imbrication ; 004 : lecture/écriture projet.
FD-BINDING-001 : validation des bindings. Génération, diff et écriture contrôlée futurs.
Aucun scanner, helper runtime, validateur Python, moteur jsonschema, Web ou Tool.

## JSON Schema normatif

forge_design/design/design.schema.json, Draft 2020-12, titre Forge Design Design File.
Description de source graphique structurée et supprimable ; aucun $id fictif.
$defs DesignNode, PageRoot, TableColumn et PropValue. Schéma unique normatif,
documentation explicative et tests structurels sans second moteur de validation.

## Fixtures

minimal.design.json reproduit la page home/index avec children vide.
contacts-list.design.json reproduit l'exemple fourni : page, section/header,
text lié à page_title, table liée à contacts, classes et colonnes nom/email/telephone.
JSON indenté, aucun enrichissement actions/conditions/IDs/HTMX/Alpine.
Blocs documentaires comparés aux fixtures par json.loads. Aucun fichier projet créé.

## Packaging

Package forge_design.design ajouté explicitement à setuptools, design.schema.json
ajouté aux package-data. __init__.py déclaratif uniquement.
Wheel : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `c70b0fac83f2fa8c69f5f9202d0f58cb6c68089c8b6d6e99604d4983ee832c53`.
Schéma et __init__ identiques aux sources dans l'archive ; aucun tests/ ou tmp/.
Requires-Dist runtime inchangés : packaging, forge-mvc, jinja2, pydantic.
Aucune dépendance nouvelle.

## Architecture

Documentation dédiée docs/design/design-json.md, architecture complétée :
ViewContract + Design JSON → futurs bindings/générateur → template → diff/écriture.
La séparation des formats et la suppression sans impact Forge sont explicites.
Template Viewer conserve son inventaire générique ; linkage exclut déjà localement
les .design.json. Aucun de ces comportements n'est modifié.

## Fichiers créés

- forge_design/design/__init__.py
- forge_design/design/design.schema.json
- docs/design/design-json.md
- tests/test_design_schema.py
- tests/fixtures/design/minimal.design.json
- tests/fixtures/design/contacts-list.design.json
- docs/rapports/FD-DESIGN-001.md

## Fichiers modifiés

- pyproject.toml : package et ressource.
- docs/02-architecture.md : place du design et pipeline futur.

Diff préexistant du rapport FD-CONTRACT-001 hors ticket et hors commit.

## Tests ajoutés

26 cas : JSON parsable, dialecte/$defs, racine stricte, version, view, composition
PageRoot, vocabulaire exact, récursivité, props simples, colonnes strictes, motifs
relatifs/suffixe et exclusions, champs obligatoires absents, contre-exemples ciblés,
fixtures/documentation synchronisées, packaging, dépendances et cinq Tools inchangés.
Contre-exemples : version différente, root non page, type inconnu, propriété racine/
nœud/colonne inconnue, binding vide, prop objet/tableau/null, colonne sans binding.
Ces assertions vérifient des déclarations ou motifs isolés ; elles ne prétendent
pas avoir validé/rejeté une instance complète via JSON Schema.

## Installation réelle

Wheel installée --no-deps --no-index --target dans un répertoire temporaire.
Processus Python -I : provenance forge_design et forge_design.design sous cette
installation, lecture du schéma via importlib.resources, comparaison des octets
par SHA-256 et json.loads. Deux fixtures chargées comme JSON avec contrôle ciblé
version/root ; aucun moteur d'instance exécuté. Aucun projet Forge consulté/écrit.
Script/journal ignorés : tmp/verify_fd_design_001.py et .log.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| git status ; git log --oneline --decorate -10 | Baseline conforme, diff utilisateur conservé |
| git -C ../Forge ls-remote origin refs/heads/main | Baseline distante identique |
| pytest -q tests/test_design_schema.py | 26 réussis |
| pytest -q --tb=short | 1685 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Inspection wheel, installation et processus Python -I | Succès |

Outils .venv, Python 3.13.5. Suite historique avec sockets et build isolé autorisés
hors sandbox. Typage d'un contre-exemple corrigé avant validation finale.
Installation sans réseau. Journal complet : tmp/pytest_fd_design_001.log.
Diff, schéma, fixtures, tests, documentation et rapport relus avant commit.

## Tests sautés

Aucun pytest sauté, tous les tests contrats/Template Viewer actifs. Node exécuté.
MkDocs build --strict non applicable : aucune configuration MkDocs.
Aucun moteur JSON Schema ou modèle Pydantic design exécuté, conformément au ticket.

## Limites restantes

Format structurel seulement. Imbrication, identité de blocs, types de props par
bloc, bindings, profondeur/taille et sécurité filesystem reportés. Un schéma
conforme ne prouve ni existence de contrat, ni absence de secret dans une chaîne,
ni validité métier ou sécurité de génération. Page descendant encore admis.
Aucun fonctionnement Forge dépendant de cette nouvelle ressource déclarative.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `feat: définir le format design json (FD-DESIGN-001)`.
Diff utilisateur du rapport 001 conservé non commité. Hash et état Git après commit
communiqués dans la réponse de livraison.
