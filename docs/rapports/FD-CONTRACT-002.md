# Rapport — FD-CONTRACT-002

## Ticket et objectif

Introduire la validation stricte en mémoire des contrats de vue par Pydantic v2,
conforme au schéma normatif FD-CONTRACT-001. Aucun lecteur projet, résolution croisée,
Tool ou interface ajouté.

## État Git initial

main synchronisée avec origin/main à `1a57d4b`. État Git et dix derniers commits
inspectés. Différence avec la baseline attendue : modification locale préexistante
dans docs/rapports/FD-CONTRACT-001.md (« État Git initiala »). Elle est conservée,
non modifiée et exclue du commit de ce ticket. Aucun AGENTS.md trouvé.

## Source normative

forge_design/contracts/view_contract.schema.json demeure inchangé. Ses contraintes
required, types, longueurs, enum, patterns, objets stricts et noms de propriétés
non vides sont reproduites. Aucun champ supplémentaire ni validation métier.
Documentation officielle Pydantic v2 consultée pour les validators et la
personnalisation json_schema_extra ; liens dans la documentation technique.

## Dépendance Pydantic

Ajout runtime `pydantic>=2,<3` ; aucune dépendance jsonschema. Validation exécutée
avec Pydantic 2.13.5 et pydantic-core 2.46.5, installés dans .venv.
API v2 exclusivement : BaseModel, ConfigDict, Field, BeforeValidator, model_validate,
model_validate_json, model_dump et model_json_schema. Aucun adaptateur v1.

## API publique

Exports de forge_design.contracts : ViewContract, ViewContextVariable, ViewAction,
ViewValueType. Un seul module models.py, aucun helper filesystem ou projet.
Les entrées sont des dictionnaires ou du JSON déjà disponibles en mémoire.

## ViewValueType

Literal exact : string, boolean, integer, number, object et list. Ces mots décrivent
les données backend ; aucune valeur backend numérique n'est validée dans ce ticket.
email reste une chaîne libre de fields, pas un type principal.

## ViewContextVariable

Objet strict : type obligatoire ; label/entity/fields facultatifs. Label vide admis,
entity non vide, fields objet de chaînes non vides vers chaînes non vides.
Aucune obligation d'entity pour list, aucune interdiction de fields sans entity.
Object + entity et noms Unicode restent admis.

## ViewAction

Method et path obligatoires, csrf facultatif. Method : min_length=1 et motif
^[A-Z]+$, sans enum HTTP ; FOO admis, minuscules/chiffres/tirets/espaces/majuscules
non ASCII refusés. Path non vide, sans obligation de slash initial ; {id} textuel.
CSRF strictement booléen quand fourni, sans False implicite ni règle liée à POST.

## ViewContract

Name obligatoire, de 1 à 256 caractères ; template obligatoire, au plus 4096,
non vide et motif ^mvc/views/.+. Context obligatoire, vide admis ; actions absent
ou objet éventuellement vide. Aucune normalisation Unicode ou suppression d'espaces.
Un chemin mvc/views/../secret.html reste structurellement admis : le futur lecteur
appliquera une politique filesystem séparée. Aucun import de forge.source.

## Mode strict

Base interne ConfigDict(extra="forbid", strict=True, frozen=True), partagée par les
trois modèles. Aucune conversion volontaire bool/int/float/string : csrf=1, 0,
1.0 ou "true" refusés ; nombres, booléens et bytes refusés comme chaînes.
Erreurs de type, propriétés inconnues et clés non chaînes contrôlées par Pydantic.

## Absence vs null

Type interne _Omissible : union avec None pour une API Python ergonomique,
BeforeValidator refusant None explicitement fourni, défaut None non validé pour
l'absence. Aucun besoin d'importer une sentinelle. Applicable à label, entity,
fields, actions et csrf ; null testé en dict et JSON sur chacun.
Le schéma généré retire la branche null et le défaut interne via json_schema_extra.
Cette personnalisation ne change pas le schéma produit et n'autorise aucune valeur
supplémentaire. model_fields_set conserve la distinction absent/objet vide.

## Dictionnaires et clés

Type Annotated[str, Field(min_length=1)] pour context/actions/fields, sans regex,
trim ou normalisation. Clés espace, emoji, tiret et formes NFC/NFD admises.
Attributs gelés, mais dicts imbriqués mutables : limite documentée et testée.
La validation d'un dictionnaire produit des conteneurs indépendants de l'entrée.
Une mutation interne n'est pas revalidée automatiquement et peut invalider le
contrat ; revalider le dump pour franchir à nouveau la frontière de validation.

## Sérialisation

model_dump(exclude_unset=True) et model_dump_json(exclude_unset=True) conservent
les fixtures sémantiquement à l'identique. Aucun null artificiel ; label vide,
actions vide et csrf False explicite préservés. Dumps revalidables.
Un dump sans exclude_unset peut inclure les None internes ; il n'est pas l'export
recommandé du format. Aucun override complexe des méthodes Pydantic.

## Erreurs de validation

ValidationError standard, errors() avec loc/code exploitables. Tests précis sur
context.contacts.type (literal_error) et actions.save.csrf (bool_type), sans figer
les textes anglais. JSON mal formé : json_invalid contrôlé. Pas de couche de
traduction supplémentaire ; diagnostics projet laissés au lecteur futur.

## Concordance avec JSON Schema

Le schéma généré est comparé intégralement au schéma normatif après retrait des
annotations title/description/$schema et alignement du nom de définition
ViewContextVariable → ContextVariable. Toutes les contraintes restent comparées,
y compris absence de default/null, required, additionalProperties, propertyNames,
enums, patterns et bornes. Aucun moteur JSON Schema maison ou dépendance jsonschema.
Le schéma normatif et les deux fixtures officielles sont inchangés.

## Documentation

Section « Modèles Python — FD-CONTRACT-002 » ajoutée à docs/contracts/view-contract.md :
API dict/JSON, mode strict, absence/null, export, erreurs, gel superficiel et limites.
Architecture complétée : schéma normatif → modèles stricts → lecteur FD-CONTRACT-003.
Les sections historiques du ticket 001 gardent leur portée, et la validation
maintenant disponible est explicitement indiquée.

## Packaging

Package contracts déjà déclaré ; models.py inclus sans ajout de package-data.
Wheel : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `5153b056a61b84dad731c348b59517f6981a2e80ea1e1e578d4493de65f4dd06`.
Inspection de METADATA : Requires-Dist pydantic<3,>=2, sans marqueur optionnel.
Modules et schéma identiques aux octets sources ; aucun tests/ ou tmp/ distribué.

## Non-régression

1425 cas précédents actifs, 143 nouveaux cas : total 1568 réussis. Seul le test
historique listant exactement les dépendances runtime reçoit Pydantic dans son
attendu. Schéma et fixtures inchangés. Cinq Tools toujours, aucun changement Web,
Bridge, app, explorateurs ou JavaScript. Dépôt Forge propre et inchangé.
Validation sans accès fichier vérifiée en bloquant open et les méthodes Path.

## Fichiers créés

- forge_design/contracts/models.py
- tests/test_view_contract_models.py
- docs/rapports/FD-CONTRACT-002.md

## Fichiers modifiés

- forge_design/contracts/__init__.py : exports publics.
- pyproject.toml : dépendance runtime Pydantic v2.
- tests/test_view_contract_schema.py : attendu de dépendances mis à jour.
- docs/contracts/view-contract.md : API et limites.
- docs/02-architecture.md : chaîne de validation.

Le diff préexistant de docs/rapports/FD-CONTRACT-001.md n'appartient pas à ce ticket.

## Tests ajoutés

143 cas : deux fixtures dict/JSON et round-trip, six types, valeurs déclaratives,
absence/objet vide, Unicode et limites, chemins et méthodes, matrices de refus
racine/variables/actions en dict et JSON, coercitions, clés, erreurs localisées,
JSON invalide, gel des attributs et mutabilité des mappings, concordance des schémas,
validation sans accès filesystem. Clés Unicode et noms de 256/257 emoji couverts.
Les champs requis, propriétés inconnues et chaque null facultatif sont exercés.

## Installation réelle

Wheel installée --no-deps --no-index --target dans un répertoire temporaire.
Processus Python -I : provenance de forge_design, contracts et models sous cette
installation vérifiée ; schéma lu via importlib.resources et comparé par SHA-256.
Deux fixtures validées en dict et JSON puis sérialisées fidèlement ; null refusé.
Pydantic provient de .venv où il a été installé préalablement : --no-deps ne prouve
pas la résolution des dépendances. Leur déclaration est vérifiée séparément dans
METADATA et leur cohérence installée par pip check. Aucun projet cible lu/écrit.
Script/journal ignorés : tmp/verify_fd_contract_002.py et .log.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| git status ; git log --oneline --decorate -10 | Baseline identique, diff utilisateur préservé |
| pytest ciblé modèles + schéma | 159 réussis |
| pytest -q --tb=short | 1568 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Métadonnées, installation temporaire, Python -I | Succès |

Python 3.13.5 et outils .venv. Installation Pydantic, build isolé et suite avec
sockets HTTP exécutés hors sandbox avec autorisation. Une première représentation
SkipJsonSchema de None ajoutait des branches inutiles aux loc des erreurs ; elle a
été remplacée avant validation finale par union nullable interne et schéma adapté.
Typage des jeux paramétrés corrigé avant contrôle final. Journal complet :
tmp/pytest_fd_contract_002.log. Diff complet et nouveaux fichiers relus avant commit.

## Tests sautés

Aucun pytest sauté ; Node exécuté. MkDocs build --strict non applicable, toujours
sans configuration MkDocs. Aucun moteur jsonschema ni scénario Web nouveau requis.

## Limites restantes

Validation structurelle en mémoire uniquement. Pas de vérification filesystem,
entités, champs, routes ou protection CSRF ; pas de valeur backend calculée.
Dicts mutables : pas d'immuabilité profonde. API Pydantic de confiance model_construct,
model_copy(update=...) et overrides permissifs ne garantissent pas la conformité ;
revalider les données sérialisées après mutation, pas seulement l'instance existante.
Format non versionné encore en construction, schéma normatif conservé.

## État Git final

Un seul commit local sur main, rapport inclus, aucun push conformément au ticket.
Message : `feat: ajouter les modèles de contrat de vue (FD-CONTRACT-002)`.
La modification préexistante du rapport 001 reste non commitée. Hash et état Git
après commit communiqués dans la réponse de livraison.
