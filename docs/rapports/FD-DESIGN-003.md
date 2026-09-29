# Rapport — FD-DESIGN-003

## Ticket et objectif

Valider les relations parent/enfant du design v0.1 par une fonction pure distincte
de Pydantic, avec diagnostics localisés et parcours itératif borné.

## État Git initial

main synchronisée avec origin/main à `4d388dd` — FD-DESIGN-002.
Git status et dix derniers commits inspectés. Modification utilisateur de
FD-CONTRACT-001.md (titre « État Git initiala ») préservée exactement, hors commit.
Aucun AGENTS.md trouvé. Baseline de 1853 tests.

## Sources fonctionnelles

Matrice du ticket réduite aux treize types existants, puis confrontée à la fixture
officielle contacts-list.design.json. Deux incohérences explicites sont résolues
pour conserver la validité de cette fixture sans modifier ses octets.

## Vocabulaire v0.1

page, section, container, grid, card, title, text, button, table, form, field,
alert, empty_state. Aucun header/main/footer/image/hidden_field/actions ajouté.
Les clés de la matrice correspondent exactement au Literal DesignNodeType.

## Réduction des règles au vocabulaire réel

Les relations vers des types absents sont exclues. TableColumn reste une propriété
columns, pas un DesignNode. Grid, title, text, button, field, alert et empty_state
sont feuilles selon une politique conservatrice v0.1, sans préjuger des extensions.
Aucune règle Grid fiable n'est donnée par le cadrage actuel.

## Contradiction Section → Text

section → text est ajouté conformément à la décision explicite du ticket :
la fixture utilise text/tag=h1 sous section. Cela n'autorise pas section → title.

Une seconde contradiction existe : la même fixture contient page → table, tandis
que la matrice finale du ticket limite page à section. Le ticket exige aussi la
validité et la conservation de cette fixture. Cette contradiction a été signalée,
avec proposition d'ajouter page → table. En l'absence de réponse, cette hypothèse a
été annoncée et retenue pour préserver la fixture normative. L'écart est documenté
et testé ; aucune exception basée sur le nom de fixture, le binding ou les props.

## Matrice finale

| Parent | Enfants autorisés v0.1 |
|---|---|
| page | section, table |
| section | container, grid, card, form, table, alert, text |
| container | grid, card, form, table, text, button |
| card | title, text, form, button, grid |
| form | field, button, alert |
| table | empty_state |
| grid | aucun |
| title | aucun |
| text | aucun |
| button | aucun |
| field | aucun |
| alert | aucun |
| empty_state | aucun |

Toute page descendante est refusée. Page vide reste valide.

## API publique

Exports supplémentaires depuis forge_design.design : ALLOWED_CHILDREN,
DesignNestingIssue, DesignNestingResult, can_contain et validate_design_nesting.
Matrice MappingProxyType de frozenset, précisément typée avec DesignNodeType.
Dataclasses de résultat et diagnostic gelées ; collection issues en tuple.

## can_contain

Consultation pure de la matrice, sans dépendance aux propriétés du nœud.
Les 169 couples parent/enfant sont testés contre une matrice attendue explicite.
L'API attend les types du vocabulaire déclaré.

## Validation d’arbre

DesignFile déjà valide Pydantic → validate_design_nesting → DesignNestingResult.
Aucun validateur automatique ajouté à DesignFile. Seules les relations entre types
sont examinées ; binding, props et columns ignorés. Aucun champ supplémentaire
requis. Une mauvaise imbrication retourne une issue, sans exception applicative.
Le parcours continue sous les parents invalides jusqu'à la fin ou une borne.

## Diagnostics

Code ordinaire : design.nesting.child_not_allowed. Message humain court,
parent_type, child_type et path. Code terminal : design.nesting.analysis_truncated.
valid vaut True uniquement sans issue et sans troncature. L'analyse tronquée
sans erreur d'imbrication observée reste invalide.

## Locations

Tuple commençant par root puis paires children/index, par exemple
("root", "children", 0, "children", 2). Une occurrence partagée reçoit un diagnostic
par chemin ; pas de dédoublonnage par identité. Le marqueur terminal désigne
l'occurrence qui déclenche l'arrêt, avec les types parent/enfant correspondants.

## Bornes

MAX_DESIGN_NODES=4096, racine comprise. MAX_DESIGN_DEPTH=128, racine à zéro.
MAX_DESIGN_ISSUES=512, marqueur compris. Constantes dans limits.py.
Exactement à la borne sans surplus : pas de troncature. Premier surplus : arrêt
complet et marqueur terminal unique. Si 512 erreurs existent déjà, la dernière
est remplacée par le marqueur ; les 511 premières sont conservées. À 512 erreurs
sans surplus, toutes sont conservées, même si des nœuds valides suivent.

Priorité si plusieurs bornes coïncident : nœuds, profondeur, diagnostics.
La borne de nœuds limite les occurrences inspectées ; une référence supplémentaire
est consommée pour détecter le surplus. Les tests couvrent les bornes exactes,
les dépassements et la troncature par nœuds après un budget de diagnostics plein.

## Parcours itératif

Pile de parents, itérateurs d'enfants, chemins et profondeurs. Aucun appel récursif,
model_dump, copie d'arbre ou empilement de tous les enfants. Le test de largeur
instrumente un conteneur et vérifie la consommation limitée des occurrences.
Temps linéaire dans les occurrences inspectées à profondeur plafonnée ; pile et
chemins bornés par la profondeur, stockage des issues plafonné.

Les tests profonds assemblent des nœuds par leurs listes mutables pour isoler
cette borne des limites récursives Pydantic. Un cycle créé ainsi s'arrête à 128.
Aucun model_construct ni contournement Pydantic dans le produit.

## Déterminisme

Parcours préfixe, profondeur d'abord, ordre source. Aucun tri d'issues.
Même modèle inchangé → même résultat, ordre et chemins. Le parcours ne dépend
pas de l'ordre des frozenset, consultés uniquement par appartenance.

## Pureté

Pas de filesystem, contexte projet, registre, contrat, Jinja ou Web dans le module.
Validation testée avec builtins.open, os.open/stat/listdir/scandir,
Path.open/read_text/read_bytes/stat et model_dump interdits.

## Non-mutation

Identité des nœuds, des listes, des props et des columns conservée. Comparaison
du contenu avant/après validation. Le modèle conserve son gel superficiel historique.
Le validateur suppose des types structurellement valides, pas des mutations
arbitraires qui remplaceraient les nœuds par des objets étrangers.

## Compatibilité Design 001/002

Schéma, models.py et fixtures officielles strictement inchangés. Les deux fixtures
restent valides Pydantic et valides pour l'imbrication. Tests historiques maintenus.
Contrats, Bridge, Tools, Web, app.py, JavaScript et pyproject.toml inchangés.
Cinq Tools toujours ; dépôt Forge propre et inchangé.

## Documentation

Section « Règles d’imbrication — FD-DESIGN-003 » ajoutée au format design : matrice,
deux corrections de cohérence, politique conservatrice, API, bornes et limites.
Architecture documentant la séparation JSON/Pydantic et validation sémantique.

## Fichiers créés

- forge_design/design/nesting.py
- tests/test_design_nesting.py
- docs/rapports/FD-DESIGN-003.md

## Fichiers modifiés

- forge_design/design/__init__.py
- forge_design/limits.py
- docs/design/design-json.md
- docs/02-architecture.md

FD-CONTRACT-001.md est une modification utilisateur préexistante, hors ticket.

## Tests ajoutés

186 cas : 169 couples, immutabilité matrice/résultats, deux fixtures, arbre complexe,
propriétés ignorées, erreurs multiples préfixes/chemins/déterminisme, bornes nœuds,
profondeur et issues exactes/surplus, budget issues plein puis surplus de nœuds,
cycle, pureté, largeur consommée paresseusement, objet partagé et budget d'erreurs
exact suivi d'éléments valides. Aucun test historique modifié.

## Packaging

Wheel : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `5ea5b4dddbeef451f65fcdcce18c4ea84514d08b9a97db7a72f8b639d502b2ea`.
__init__.py, models.py, nesting.py, design.schema.json et limits.py inspectés et
comparés aux sources. Aucun tests/ ou tmp/ distribué. Requires-Dist inchangés.

Installation temporaire --no-deps --no-index --target, puis Python -I avec runtime
.venv. Provenance installée du package design, models et nesting vérifiée.
Schéma installé comparé à la source via importlib.resources. Fixtures lues depuis
le dépôt de test : validation Pydantic, sérialisation et imbrication réussies.
page → button retourne l'unique diagnostic et le chemin attendus. Tests installés
historiques version incorrecte et binding=null conservés.
Script/journal ignorés : tmp/verify_fd_design_003.py et .log.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat |
|---|---|
| git status ; git log --oneline --decorate -10 | Baseline conforme, diff utilisateur identifié |
| pytest -q tests/test_design_schema.py tests/test_design_models.py tests/test_design_nesting.py | 380 réussis |
| pytest -q --tb=short | 2039 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Installation réelle et scénario Python -I | Succès |

Outils .venv, Python 3.13.5. Suite historique HTTP et build exécutés hors sandbox
pour les sockets locaux et dépendances de build. Correction de formatage/imports
signalés par Ruff avant validation finale. Une commande utilisant python absent
du PATH a été reprise avec .venv/bin/python. Journal complet :
tmp/pytest_fd_design_003.log. Diff et nouveaux fichiers relus avant commit.

## Tests sautés

Aucun test pytest sauté. mkdocs build --strict non applicable : aucune configuration
MkDocs présente. Aucune interaction navigateur ajoutée ou revendiquée.

## Limites restantes

Matrice conservatrice v0.1, enrichie explicitement de page → table pour la fixture.
Troncature signifie résultat incomplet, jamais validation réussie. Types des modèles
supposés corrects ; absence de mutation concurrente requise pour le déterminisme.
Aucun binding validé, fichier projet lu/écrit, HTML/Jinja généré ou Web ajouté.
Les extensions de matrice et le lecteur/écrivain FD-DESIGN-004 restent ultérieurs.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `feat: valider l'imbrication des blocs (FD-DESIGN-003)`.
Modification utilisateur FD-CONTRACT-001 préservée hors commit. Hash et état final
communiqués dans la livraison ; dépôt Forge inchangé.
