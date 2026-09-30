# Rapport — FD-PREVIEW-001

## Ticket et objectif

Transformer un ViewContract validé en contexte fictif déterministe JSON-like,
intégralement en mémoire, sans rendu ni accès au backend.

## État Git initial

main synchronisée avec origin/main à `49f1f1a` — FD-BINDING-003.
Git status et dix derniers commits inspectés. Modification utilisateur de
FD-CONTRACT-001.md (« État Git initiala ») conservée exactement hors commit.
Aucun AGENTS.md trouvé. Baseline : 2299 tests.

## Sources fonctionnelles

Valeurs du cadrage : string=Exemple, boolean=True, liste de trois objets,
email=contact@example.test, date fixe=2026-05-16. Les constantes integer=42 et
number=12.5 suivent la convention explicite du ticket. Fields est la seule source
des propriétés d'objet, sans lecture d'entité.

## API publique

Nouveau package forge_design.preview exportant PreviewDataIssue, PreviewDataResult
et generate_preview_data(contract). Dataclasses gelées, issues tuple. data est un
dictionnaire de valeurs JSON-like avec conteneurs mutables : gel superficiel seulement.
Aucun export ajouté à forge_design.__init__.

## Déterminisme

Table privée de scalaires immuables et helper _fake_value_for_type. Aucun hasard,
Faker, UUID, horloge ou date courante. Même contrat inchangé : mêmes valeurs, ordre,
diagnostics et complétude ; nouveaux conteneurs à chaque appel.

## Valeurs top-level

| Type | Valeur |
|---|---|
| string | "Exemple" |
| boolean | True |
| integer | 42 |
| number | 12.5 |
| object | Objet généré depuis fields, sinon {} |
| list | Trois objets générés depuis fields, sinon [{}, {}, {}] |

Types bool/int/float préservés. Fields sur les scalaires ne modifie pas leur valeur.
Label/entity/actions ignorés, aucune URL fictive d'action ajoutée au contexte.

## Génération des objets

Un nouveau dict, rempli avec les champs supportés dans l'ordre déclaré.
Fields absent ou vide : objet vide sans issue. Parent conservé même si tous ses
champs ont un type inconnu. Pas de structure inférée depuis entity.

## Génération des listes

Exactement trois dicts sémantiquement égaux, créés séparément. Les champs object/list
créent aussi de nouveaux conteneurs pour chaque ligne. Aucun alias mutable entre
lignes, variables ou appels. Une mutation de la première ligne ne touche pas les autres.

## Fields

Vocabulaire exact : string, boolean, integer, number, email, date, object et list.
Aucun strip/casefold ou normalisation du type ou du nom. Field object → {}, field
list → [], sans récursion car le contrat ne décrit pas de sous-structure.
Le cas field list diffère de la variable top-level list à trois objets.

## Types email/date

Email : chaîne contact@example.test. Date : chaîne 2026-05-16, exemple fixe du
cadrage, sans datetime.date ni date courante. Valeurs JSON sérialisables directement.

## Types de champ inconnus

Champ omis, sans None, sentinelle ou valeur arbitraire. Une issue par définition,
pas une par ligne produite. Exemples money/uuid/custom/type Unicode et variantes
de casse/espaces non reconnues. La variable parent reste présente.

## Diagnostics

Code preview.unsupported_field_type. Message humain générique et location exacte
("context", nom_variable, "fields", nom_champ). Ordre des variables puis des
fields. Aucun diagnostic pour fields/entity/label/actions absents.

## Complétude

complete=True si aucune définition de champ demandée n'a été omise ; False dès
qu'un type de champ est inconnu. Contexte vide : data={}, issues=(), complete=True.
Aucune borne ni troncature supplémentaire dans cette API.

## Ordre

Ordre original de context et fields conservé dans les données et diagnostics.
Pas de tri alphabétique. Clés Unicode/decomposition Unicode conservées telles quelles.

## Pureté

Aucun DesignFile, binding, filesystem, réseau, DB, subprocess, Forge, contexte,
registre, Web ou Jinja. Tests bloquant open, os.open/stat/listdir/scandir,
Path.open/read_text/read_bytes, socket, subprocess.run/Popen et random.random.
model_dump bloqué pendant la génération : pas de revalidation/copie globale du contrat.

## Non-mutation

Payload contractuel comparé avant/après ; identités context, variable, fields et
actions conservées. Résultat modifiable sans effet sur le contrat ou les générations
suivantes. Gel des attributs de résultat et diagnostic vérifié, mutabilité data testée.

## Complexité

O(V+F), facteur constant trois pour la matérialisation des listes. Pas de récursion
métier, tri ou index secondaire. Aucune nouvelle limite arbitraire : coût mémoire,
temps et diagnostics proportionnels au contrat fourni. Une entrée synthétique peut
être plus grande qu'un contrat passé par le lecteur filesystem borné.

## Compatibilité Contracts

Tout forge_design/contracts reste inchangé. Entrée supposée structurellement valide,
sans tentative de réparer des mutations arbitraires après validation Pydantic.
Actions, labels et entités ne pilotent pas les valeurs fictives.

## Compatibilité Design/Bindings

Tout forge_design/design reste inchangé, ainsi que Forge, Tools, Web, app.py,
limits.py et JavaScript. Aucun renderer ou nouveau Tool ; cinq Tools historiques.
Dépôt Forge Core inchangé.

## Documentation

Nouvelle page docs/preview/static-preview.md : API, tableau des valeurs, champs,
omission, complétude, gel superficiel, identité des conteneurs, pureté et limites
nominales. Architecture : contrat → contexte fictif → renderer local FD-PREVIEW-002.

## Packaging

Seule modification pyproject.toml : ajout forge_design.preview à la liste explicite
setuptools. Aucun package-data ou dépendance ajouté ; Requires-Dist inchangés.
Wheel : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `19097d68ad0124bd50d652a4a839121d7b1b50598d8f684891705a7da35bd6a2`.
preview/__init__.py et data.py présents et identiques aux sources. Aucun tests/ ou
tmp/ distribué.

## Fichiers créés

- forge_design/preview/__init__.py
- forge_design/preview/data.py
- tests/test_preview_data.py
- docs/preview/static-preview.md
- docs/rapports/FD-PREVIEW-001.md

## Fichiers modifiés

- pyproject.toml : déclaration du package seulement.
- docs/02-architecture.md : pipeline Preview.

FD-CONTRACT-001.md reste une modification utilisateur hors ticket.

## Tests ajoutés

34 cas : six types top-level, huit types fields pour object/list, fields absent/vide,
contexte vide, exemple roadmap, métadonnées ignorées, types inconnus/ordre/locations,
Unicode, parent conservé, indépendance profonde des conteneurs, fields sur scalaire,
pureté/non-mutation/déterminisme et gel superficiel. Aucune attente historique modifiée.

## Installation réelle

Installation temporaire --no-deps --no-index --target. Processus Python -I avec
runtime .venv, provenance de forge_design.preview et preview.data vérifiée sous
l'installation. Contrat contacts/list créé en mémoire, génération nominale contrôlée
(page_title, trois contacts/email, can_create=True) et identité distincte des lignes.
Ajout avatar:image : une issue localisée, complete=False et aucune clé avatar dans
les objets. open/os.open/Path.open/Path.read_text interdits pendant ce scénario.
Script/journal ignorés : tmp/verify_fd_preview_001.py et .log.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat |
|---|---|
| git status ; git log --oneline --decorate -10 | Baseline et diff utilisateur vérifiés |
| pytest -q tests/test_preview_data.py | 34 réussis |
| pytest modèles Contracts + Preview | 177 réussis |
| pytest bindings simples/tableaux/conditionnels + Preview | 184 réussis |
| pytest -q --tb=short | 2333 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Installation temporaire et Python -I | Succès |

Outils .venv, Python 3.13.5. Suite historique avec sockets et build isolé exécutés
hors sandbox. Types de dicts vides dans les données paramétrées précisés après
pyright ; tests concernés revérifiés, contrôle final sans erreur. Journal complet :
tmp/pytest_fd_preview_001.log. Diff et nouveaux fichiers relus avant commit.

## Tests sautés

Aucun test pytest sauté. mkdocs build --strict non applicable : aucune configuration
MkDocs présente dans ForgeDesign. Aucun HTML, navigateur ou rendu revendiqué.

## Limites restantes

Booléens toujours True et listes top-level toujours à trois objets : ni branches
False ni empty_state exercés par le futur rendu nominal. Aucun scénario alternatif.
Fields non récursifs et types inconnus omis. Gel superficiel, coût proportionnel
sans plafond supplémentaire ; modèles supposés valides et non mutés concurremment.
Aucun backend, valeur réelle, rendu HTML/Jinja, Web ou génération Design.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `feat: générer les données de preview (FD-PREVIEW-001)`.
Modification utilisateur FD-CONTRACT-001 préservée hors commit ; Forge Core inchangé.
Hash et état final communiqués dans la livraison.
