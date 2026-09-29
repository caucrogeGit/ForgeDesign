# Rapport — FD-CONTRACT-001

## Ticket et objectif

Définir et documenter le format minimal .view.json, sous forme d'un JSON Schema
normatif distribué dans la wheel. Aucun chargement de contrat projet, modèle
Pydantic, validateur Python, interface ou génération.

## État Git initial

main propre et synchronisée avec origin/main à `2599012` — FD-TEMPLATE-005.
Git status et dix derniers commits inspectés avant modification. Aucun AGENTS.md.
Baseline de 1409 tests conservée. Dépôt Forge propre, aucun fichier Forge modifié.

## Sources de cadrage utilisées

Ticket FD-CONTRACT-001 fourni en pièce jointe, source précise du format minimal.
docs/01-cadrage-fonctionnel.md : conception de vues et séparation stockage/écriture.
docs/03-roadmap.md : contrats puis design/bindings/génération, tickets distincts.
docs/02-architecture.md et pyproject.toml : cinq Tools, packages explicites et
ressources distribuées. Aucun format supposé de Forge Core ou de l'ancien projet.

## Rôle du contrat de vue

Le contrat décrit ce que la vue est autorisée à utiliser, sans constituer un
mécanisme de contrôle d'accès. Le contrôleur produit les données, le template les
utilise et Forge Design comprend leur structure. Aucune logique métier déplacée.

## Convention .view.json

Convention future : mvc/views/<vue>.view.json à côté de mvc/views/<vue>.html.
name est une identité explicite, indépendante du chemin physique template.
Aucune déduction depuis le nom de fichier ni vérification de concordance.
Aucun scan ajouté ; Template Viewer conserve son inventaire générique inchangé.

## Schéma JSON normatif

forge_design/contracts/view_contract.schema.json, Draft 2020-12, titre
« Forge Design View Contract ». Pas de $id fictif, de schema_version ou de default.
Deux $defs : ContextVariable et ViewAction. La documentation explique ce fichier,
sans second schéma ni moteur maison. Le package ne contient qu'un __init__ déclaratif
et la ressource JSON ; aucun helper runtime.

## Racine

Objet strict : name, template et context obligatoires ; actions optionnel.
name : chaîne de 1 à 256 caractères, sans regex de nom logique.
template : chaîne non vide, maximum 4096 caractères, préfixe mvc/views/ et suffixe
non vide par motif léger. Ce n'est ni source_parts ni un contrôle filesystem.
Les longueurs sont en caractères, sans normalisation/trim. Autres propriétés refusées.

## Context

Objet éventuellement vide, clés non vides. Chaque valeur est un objet strict
avec type obligatoire et label/entity/fields optionnels. label est une chaîne
humaine éventuellement vide. Aucune expression, valeur backend ou calcul embarqué.

## Types minimaux

Vocabulaire exact : string, boolean, integer, number, object et list.
email n'est pas un type principal. Aucun schéma récursif d'objet ou d'élément de
liste ajouté ; ce ticket décrit le vocabulaire minimal, pas les instances backend.

## Entity

Chaîne non vide, déclarative, sans vérification avec Entity Explorer.
Aucune condition sur le type : une liste ou un objet peut représenter Contact.
Aucune validation métier supplémentaire inventée.

## Fields

Objet optionnel : nom non vide → chaîne de type non vide. Vocabulaire libre,
notamment email. Pas de résolution d'entité/champ, de compatibilité de types ni
de modèle complexe par champ.

## Actions

Objet optionnel éventuellement vide, noms non vides. ViewAction strict avec
method/path obligatoires, csrf booléen optionnel. Méthode selon ^[A-Z]+$, sans enum
ni interprétation Router. Path non vide, paramètres comme {id} purement textuels.
Absence de csrf sans valeur sémantique implicite ; aucune protection exécutée ici.

## Séparation avec contrôleur

Le contrat décrit, le contrôleur prépare et calcule. can_create est une donnée
fournie par le backend, pas une permission calculée dans le fichier. Ni SQL,
Python, Jinja, callback ou condition exécutable ; aucune chaîne n'est évaluée.
Les propriétés de code telles que source/visible_if ne font pas partie du schéma.

## Séparation avec Entity JSON

Entity JSON décrit la structure métier persistée ; le contrat décrit les données
exposées à une vue. Aucune base parallèle ni revalidation des entités.
Une action décrit ce que la vue propose ; une route définit l'accès au contrôleur.
Le contrat ne remplace ni le modèle métier ni le routeur.

## Séparation avec .design.json

.view.json décrit ce que la page peut utiliser ; le futur .design.json décrira
comment elle est composée. Aucun layout, classe, Tailwind, couleur ou position.

## Responsabilités reportées

FD-CONTRACT-002 : modèles Pydantic et validation complète des instances.
FD-CONTRACT-003 : scan et lecteur sécurisé, politique de chemin et filesystem.
Affichage, croisements template/entités/routes, bindings, rendu et génération futurs.
Pas de nouveau Tool ni route, aucun changement des cinq Tools, Web, Bridge ou scripts.
Le format pourra recevoir un mécanisme de version avant stabilisation publique.

## Packaging

Package forge_design.contracts ajouté explicitement à setuptools ; package-data
inclut exactement view_contract.schema.json. Aucune dépendance ajoutée, runtime ou dev.
Wheel construite : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `d86669336271327cb412e0449848c4d2f79a1de7c29af0526529f5f7028e9936`.
Archive inspectée : __init__ et schéma identiques aux sources, aucun tests/ ou tmp/.
Installation réelle --no-deps --no-index --target dans un répertoire temporaire.
Processus Python -I : import du package depuis l'installation, lecture par
importlib.resources, octets exacts et JSON contrôlés. Aucun projet Forge consulté.
Script/journal ignorés : tmp/verify_fd_contract_001.py et .log.

## Fichiers créés

- forge_design/contracts/__init__.py
- forge_design/contracts/view_contract.schema.json
- docs/contracts/view-contract.md
- tests/test_view_contract_schema.py
- tests/fixtures/contracts/minimal.view.json
- tests/fixtures/contracts/contacts-list.view.json
- docs/rapports/FD-CONTRACT-001.md

## Fichiers modifiés

- pyproject.toml : package explicite et ressource JSON.
- docs/02-architecture.md : place du contrat et étapes futures.

## Tests ajoutés

16 cas, uniquement assertions ciblées et bibliothèque standard pour le JSON.
Dialecte, racine, $defs, propriétés obligatoires, objets stricts, bornes, vocabulaire,
clés non vides, actions et csrf sans default. Exemples de racine non objet, champs
obligatoires absents (name/template/context/type/method/path), type inconnu, csrf
non booléen et propriété inconnue aux trois niveaux reliés aux déclarations du schéma.
Ces tests ne prétendent pas avoir rejeté des instances via un moteur JSON Schema.
Fixtures minimal et contacts parsables ; contacts exerce string/list/boolean,
labels, entity, fields, GET, POST et csrf. Blocs JSON documentaires comparés aux
fixtures. Déclaration packaging, dépendances inchangées et cinq Tools contrôlés.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat |
|---|---|
| git status ; git log --oneline --decorate -10 | Baseline conforme |
| pytest -q tests/test_view_contract_schema.py | 16 réussis |
| pytest -q --tb=short | 1425 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Inspection wheel, installation, import Python -I | Succès |

Outils .venv, Python 3.13.5. Suite HTTP et build isolé exécutés hors sandbox avec
autorisation ; installation temporaire sans réseau. Pip a désactivé son cache
utilisateur inaccessible, sans échec. Journal complet : tmp/pytest_fd_contract_001.log.
Diff complet, nouveaux fichiers, fixtures, documentation et rapport relus avant commit.

## Tests sautés

Aucun pytest sauté. Aucun moteur JSON Schema exécuté, conformément au périmètre ;
pas de mini-validateur ni de dépendance jsonschema/Pydantic. MkDocs build --strict
non applicable : aucune configuration MkDocs dans le dépôt.

## Limites restantes

Schéma structurel minimal en construction. Pas de validation complète d'instances
dans ce ticket, de sécurité filesystem, de résolution croisée ou de chargement runtime.
La conformité déclarative ne prouve ni existence des fichiers/entités/routes, ni
validité métier, ni disponibilité réelle des données ou protection CSRF.
Aucun fichier .view.json écrit dans un projet cible.

## État Git final

Un seul commit local sur main, rapport inclus, sans push conformément au ticket.
Message : `feat: définir le contrat de vue minimal (FD-CONTRACT-001)`.
Hash et état Git après commit communiqués dans la réponse de livraison.
