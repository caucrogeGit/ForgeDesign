# Rapport — FD-DESIGN-002

## Ticket et objectif

Valider en mémoire le format design v0.1 avec des modèles Pydantic v2 stricts,
conformes au schéma existant, sans lecture projet ni règles d'imbrication métier.

## État Git initial

main synchronisée avec origin/main à `225a1b6` — FD-DESIGN-001.
Git status et dix derniers commits inspectés. La modification utilisateur de
`docs/rapports/FD-CONTRACT-001.md` (titre « État Git initiala ») est conservée
exactement et exclue du commit. Aucun AGENTS.md trouvé.

## Source normative

`forge_design/design/design.schema.json` reste strictement inchangé.
Ses contraintes sont reproduites dans les modèles et comparées dans les tests.
Aucun chargement du schéma pendant la validation des données.

## API publique

Exports depuis forge_design.design : DesignFile, DesignNode, PageRoot,
TableColumn, DesignNodeType et PropValue. Entrées par model_validate(dict) ou
model_validate_json(text), sans helper load/read ni modèle spécialisé de binding.

## DesignNodeType

Literal exact : page, section, container, grid, card, title, text, button,
table, form, field, alert, empty_state. Les treize valeurs sont testées.
Aucun type supplémentaire.

## PropValue

Union str/bool/int/float. Les types restent distincts en validation dict et JSON :
« true » reste une chaîne, true un booléen, 12 un entier et 1.0 un flottant.
Chaîne vide autorisée ; null, objets, listes, NaN et Infinity refusés.
Les clés props sont des chaînes non vides, Unicode admis sans normalisation.

## TableColumn

label et binding sont obligatoires, chaînes non vides. Extra interdit.
Absences, null, nombres, chaînes vides et propriété width sont testés en refus.

## DesignNode

Modèle générique avec type obligatoire, binding, props, columns et children
facultatifs par omission. Enfants récursifs et colonnes typés par leurs modèles.
Page descendant, button avec children et columns sur section restent autorisés.

## PageRoot

Modèle explicite partageant les propriétés communes avec DesignNode, sans
redéfinition incompatible d'un attribut mutable. type est Literal page sans défaut ;
children est obligatoire. binding, props et columns restent admis.

## DesignFile

version obligatoire et exactement « 0.1 », view de 1 à 256 caractères,
source_contract de 1 à 4096 caractères et root PageRoot obligatoire.
Aucun trim, normalisation Unicode ou conversion volontaire.

## Mode strict

Base interne avec extra=forbid, strict=True, frozen=True et allow_inf_nan=False.
Tests des types incorrects, bytes, tuples, clés non textuelles et extras.
Pydantic v2 existant réutilisé ; aucune dépendance ajoutée.

## Absence vs null

Mécanisme local BeforeValidator : None interne représente l'absence, mais un
None/null explicitement fourni est rejeté. Les champs facultatifs du schéma généré
ne publient ni branche null ni défaut None. Les objets et listes vides explicitement
fournis restent distincts de l'omission. Aucun refactoring des contrats.

## source_contract

Field applique longueurs et motif principal ; AfterValidator reproduit les quatre
exclusions not.anyOf, également publiées dans le schéma généré. Tests des chemins
absolus, segments vides, dot/dotdot, préfixe mvc/views, antislash, deux-points,
suffixes incorrects, basename .view.json et CR/LF. Espaces et Unicode sont admis
selon le schéma. Frontières 4096/4097 vérifiées avec caractères multi-octets.
Aucun appel source_parts ni contrôle filesystem ajouté.

## Récursivité

Références récursives Pydantic standards, sans parser manuel. Arbre de 30 niveaux
validé et sérialisé ; cycle Python refusé par ValidationError de type recursion_loop.
Aucune borne métier de profondeur ajoutée ; limites internes Pydantic conservées.

## Sérialisation

model_dump(exclude_unset=True) et model_dump_json(exclude_unset=True) préservent
sémantiquement les fixtures minimal et contacts-list. Revalidation du dump testée.
Les None internes ne sont pas exportés avec cette option ; props/columns/children
vides fournis explicitement restent présents. Le dump sans option peut exposer les
None internes et n'est pas l'export conforme recommandé.

## Immutabilité

Attributs gelés, affectation refusée avec frozen_instance. Gel superficiel seulement :
children.append et modification de props fonctionnent, sans validation automatique.
La revalidation des données sérialisées accepte une mutation valide et refuse une
clé vide introduite ensuite. Les API de confiance Pydantic ne constituent pas une
frontière de validation ; cette limite est documentée.

## Erreurs de validation

Assertions sur loc et type, sans figer les messages anglais :
root.children.0.type/literal_error, root.children.1.columns.0.binding/missing,
JSON mal formé/json_invalid et cycle/recursion_loop.

## Concordance JSON Schema

Comparaison du schéma généré au normatif : propriétés racine, required, extras,
version, longueurs, source_contract avec exclusions, vocabulaire, binding,
props, columns, children et TableColumn. PageRoot comparé sous forme aplatie
équivalente à son allOf normatif. Annotations ignorées ; PropValue normalisé entre
liste de types et anyOf. Aucun changement du schéma pour faciliter Pydantic.

## Documentation

Section « Modèles Python — FD-DESIGN-002 » dans docs/design/design-json.md : API,
strictness, absence/null, sérialisation, gel superficiel et responsabilités reportées.
Architecture mise à jour : schéma → modèles → FD-DESIGN-003 → FD-DESIGN-004.

## Packaging

Wheel reconstruite : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `a4e871e6adca8a62d464f44586e2f3fce0420d6f67c0f9d3047f7745247355b1`.
__init__.py, models.py et design.schema.json présents et identiques aux sources.
Aucun tests/ ou tmp/ distribué. Requires-Dist inchangés, pyproject.toml inchangé.

## Non-régression

Suite complète réussie. Contrats, Bridge, Tools, registre, Web, app.py, limits.py
et JavaScript inchangés. Composition historique de cinq Tools conservée.
Le dépôt Forge est resté propre ; aucun accès projet dans les nouveaux modèles.

## Fichiers créés

- forge_design/design/models.py
- tests/test_design_models.py
- docs/rapports/FD-DESIGN-002.md

## Fichiers modifiés

- forge_design/design/__init__.py
- docs/design/design-json.md
- docs/02-architecture.md

La modification utilisateur FD-CONTRACT-001 reste hors ticket.

## Tests ajoutés

168 cas : fixtures dict/JSON, treize types, structures génériques, omissions et
valeurs vides, props scalaires sans coercition, racines/nœuds/colonnes invalides,
nulls, extras, chemins, Unicode et frontières, erreurs localisées, récursivité,
gel superficiel, sérialisation et concordance normative. Validation également
exécutée avec open et Path.read_text interdits.

## Installation réelle

Installation temporaire --no-deps --no-index --target. Processus Python -I avec
runtime .venv ; provenance de forge_design.design et de models vérifiée sous
l'installation. Schéma installé lu par importlib.resources et comparé à la source.
Les deux fixtures sont lues depuis le dépôt de test, jamais prétendues distribuées.
Validation dict/JSON et sérialisation des deux fixtures réussies ; version 0.2 et
binding=null produisent ValidationError. Script et journal ignorés :
tmp/verify_fd_design_002.py et tmp/verify_fd_design_002.log.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat |
|---|---|
| git status ; git log --oneline --decorate -10 | Baseline et modification utilisateur vérifiées |
| pytest -q tests/test_design_schema.py tests/test_design_models.py | 194 réussis |
| pytest -q --tb=short | 1853 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Inspection, installation temporaire et Python -I | Succès |

Python 3.13.5, Pydantic 2.13.5, outils .venv. Suite HTTP historique et construction
isolée exécutées hors sandbox pour sockets et dépendances de build. Typages de
fixtures de tests précisés après les premiers diagnostics pyright ; contrôle final
sans erreur. Journal complet : tmp/pytest_fd_design_002.log.

## Tests sautés

Aucun test pytest sauté. mkdocs build --strict non applicable : aucune configuration
MkDocs présente. Aucun navigateur requis pour cette validation en mémoire.

## Limites restantes

Pas d'imbrication métier, de résolution de binding, de lecteur/écrivain sécurisé,
de génération ou de Web. Aucune immuabilité profonde ni plafond métier de volume.
Les noms structurellement valides ne garantissent pas un accès filesystem autorisé.
Les limites internes de récursion Pydantic subsistent. FD-DESIGN-003 traitera les
règles d'imbrication et FD-DESIGN-004 les I/O.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `feat: ajouter les modèles design (FD-DESIGN-002)`.
Modification utilisateur de FD-CONTRACT-001 conservée hors commit ; dépôt Forge
inchangé. Hash et état après commit communiqués dans la réponse de livraison.
