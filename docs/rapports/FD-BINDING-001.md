# Rapport — FD-BINDING-001

## Ticket et objectif

Valider les bindings simples entre un DesignFile et un ViewContract explicitement
fournis, avec diagnostics localisés, sans I/O, mutation ou génération.

## État Git initial

main synchronisée avec origin/main à `8ac5e53` — FD-DESIGN-004.
Git status et dix derniers commits inspectés. Modification utilisateur de
FD-CONTRACT-001.md (« État Git initiala ») préservée exactement hors commit.
Aucun AGENTS.md trouvé. Baseline : 2117 tests.

## Sources fonctionnelles

Ticket confronté aux modèles actuels : context/actions côté contrat, binding
facultatif générique côté nœud et binding des colonnes. Aucune nouvelle propriété
ou valeur de DesignNodeType ajoutée.

## Limites du format v0.1

Pas de bloc condition, champ action dédié, visible_if ou form_action. Les exemples
de roadmap non représentables ne donnent lieu à aucune interprétation implicite.
Les validations Pydantic, nesting et bindings restent indépendantes et composables.

## Décision button.binding

button.binding désigne exclusivement une clé de contract.actions. Convention v0.1
explicite, susceptible d'évoluer avec un futur champ action. Aucune syntaxe spéciale
introduite : action:create, @create et actions.create restent des clés littérales.

## Bindings context

title/text attendent string ; table attend list. Recherche exacte dans le dict
context existant, sans index supplémentaire. Aucun strip/casefold/normalisation
Unicode, conversion de type ou découpage sur point/slash/deux-points/crochets.
contact.email n'est reconnu que si cette clé littérale existe.

## Bindings actions

Présence du nom dans actions uniquement. Actions absent ou vide : unknown_action.
Les champs method/path/csrf ne sont pas interprétés ; aucune route consultée.
Homonymes context/actions résolus seulement selon le type du bloc.

## Matrice de compatibilité

| Bloc | Règle |
|---|---|
| title, text | context de type string |
| table | context de type list |
| button | action nommée |
| page, section, container, grid, card | unsupported si binding présent |
| form, field | unsupported, sémantique reportée |
| alert, empty_state | unsupported si binding présent |

Binding absent accepté sur tous les types, racine comprise. Props sans effet sur
la règle. Matrice interne immuable MappingProxyType, typée avec DesignNodeType.

## API publique

Exports depuis forge_design.design : DesignBindingIssue, DesignBindingResult et
validate_design_bindings(design, contract). Dataclasses gelées, tuple issues.
Aucun helper de lecture, aucune validation automatique ajoutée aux modèles.

## Diagnostics

Codes : design.binding.unknown_variable, unknown_action, type_mismatch, unsupported
et analysis_truncated (même préfixe design.binding). Au maximum une erreur ordinaire
par occurrence. Messages humains distincts du contrat machine code/location.
valid=True uniquement sans erreur et sans troncature.

## Locations

Erreur ordinaire : chemin du nœud suivi de binding, par exemple
("root", "children", 0, "children", 2, "binding"). Binding racine unsupported à
("root", "binding"). Le marqueur de troncature vise le nœud déclencheur, sans
suffixe binding. Son champ binding peut être None si le nœud n'a pas de binding ;
cette adaptation du modèle évite d'inventer une valeur ou une propriété absente.

## Parcours

Pile explicite d'itérateurs ; préfixe/profondeur d'abord/ordre source. Racine traitée
comme toute occurrence. Aucun parcours de columns, dump, copie complète ou
empilement de toute la largeur. Les objets partagés sont analysés à chaque chemin.
Coût O(N) à profondeur bornée ; recherches dictionnaire O(1) moyen.

## Bornes

Réutilisation sans modification de MAX_DESIGN_NODES=4096 racine comprise,
MAX_DESIGN_DEPTH=128 racine à zéro, MAX_DESIGN_ISSUES=512 marqueur compris.
Exactement à la borne sans surplus : pas de troncature. Premier surplus : arrêt
et marqueur terminal unique, truncated=True, valid=False. Si 512 erreurs existent
déjà, la dernière est remplacée par le marqueur ; les 511 premières sont conservées.
Sans surplus, les 512 erreurs restent, même si des nœuds valides suivent.
Priorité nœuds/profondeur/issues. Cycles synthétiques arrêtés par les bornes.

## Déterminisme

Pas de tri ou dédoublonnage. Même paire de modèles inchangés → même résultat et
même ordre. Noms Unicode conservés exactement. Le parcours utilise les dictionnaires
du contrat sans reconstruction d'index.

## Pureté

Pas de filesystem, read_design, read_view_contract, contexte, registre ou Web.
Tests bloquant open, os.open/stat/listdir/scandir, Path.open/read_text/read_bytes,
les lecteurs, nesting et model_dump pendant l'analyse. Aucun appel automatique
Pydantic/nesting, aucun lien via source_contract, aucune comparaison view/name.
Le scénario installé fonctionne avec les seuls modèles en mémoire.

## Non-mutation

Payloads design/contract comparés avant/après. Identités children, nœud, props,
columns, context et actions conservées. Résultats/diagnostics gelés testés.
Les modèles d'entrée doivent conserver leurs types structurels ; les conteneurs
restent mutables selon leur contrat historique.

## Colonnes reportées

columns[].binding ignoré, même inconnu, lorsque la table référence une list connue.
Aucun accès à entity/fields ni diagnostic unknown_field. FD-BINDING-002 traitera
les listes, colonnes et champs.

## Conditions reportées

Aucun type condition ou champ implicite ajouté. FD-BINDING-003 nécessitera une
représentation explicite. Aucun comportement déduit de tag ou d'autres props.

## Formulaires reportés

form/field avec binding donnent unsupported, sans recherche de variable ou action.
Aucune obligation de complétude de composant, action de formulaire ou route.

## Compatibilité Contracts

Modèles, lecteur, liaison et schéma Contracts inchangés. ViewContract est consommé
sans modification fonctionnelle. Tests historiques maintenus.

## Compatibilité Design

Schéma, models.py, nesting.py, io.py, fixtures et limits.py inchangés.
Nesting invalide autorisé comme entrée de l'analyse des bindings. Aucun nouveau
Tool, route, JavaScript, Web ou dépendance. Dépôt Forge Core inchangé.

## Documentation

Nouveau docs/design/bindings.md : API, namespaces, matrice, décision button,
absence, diagnostics, bornes, chemins exacts et responsabilités reportées.
Architecture mise à jour avec les étapes indépendantes et un lien vers cette page.

## Fichiers créés

- forge_design/design/bindings.py
- tests/test_design_bindings.py
- docs/design/bindings.md
- docs/rapports/FD-BINDING-001.md

## Fichiers modifiés

- forge_design/design/__init__.py : exports publics.
- docs/02-architecture.md : pipeline et séparation des responsabilités.

Le diff utilisateur FD-CONTRACT-001.md reste hors ticket.

## Tests ajoutés

70 cas : matrice de 3 blocs × 6 types context, absence sur les 13 types,
unsupported sur les 9 autres, actions absent/vide, homonymes, noms littéraux,
Unicode sans normalisation, fixtures, colonnes ignorées, erreurs préfixes et
locations dont racine, immutabilité, frontières nœuds/profondeur/issues,
limites combinées, objets partagés/cycle, pureté/non-mutation et largeur paresseuse.
Tous les tests historiques conservés.

## Packaging

Wheel : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `47db51c57383984d54bedc775dfe2aba0d50842ba91664fb90777e0a653a76ca`.
Archive inspectée : design/__init__, bindings, modèles Design/Contracts et schéma
Design identiques aux sources. Aucun tests/ ou tmp/ distribué. Requires-Dist
inchangés ; aucune dépendance nouvelle.

Installation --no-deps --no-index --target temporaire, processus Python -I avec
runtime .venv. Provenance de design et bindings vérifiée. Contrat créé en mémoire
avec page_title:string, contacts:list et create. Scénario nominal text/table/button
valide ; scénario missing/page_title/delete produit unknown_variable/type_mismatch/
unknown_action dans l'ordre source avec locations exactes. Colonne inconnue ignorée.
open/Path.read_text interdits pendant le scénario de validation installé.
Script/journal ignorés : tmp/verify_fd_binding_001.py et .log.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat |
|---|---|
| git status ; git log --oneline --decorate -10 | Baseline conforme, diff utilisateur identifié |
| pytest -q tests/test_design_bindings.py | 70 réussis |
| pytest ciblé modèles/nesting/I/O Design + modèles Contracts + bindings | 637 réussis |
| pytest -q --tb=short | 2187 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Installation temporaire et Python -I | Succès |

Outils .venv, Python 3.13.5. Suites historiques avec sockets et build isolé exécutés
hors sandbox. Journal complet : tmp/pytest_fd_binding_001.log. Diff, nouveaux
fichiers et rapport relus avant commit.

## Tests sautés

Aucun test pytest sauté. mkdocs build --strict non applicable : aucune configuration
MkDocs présente dans ForgeDesign. Aucun test navigateur requis pour cette fonction pure.

## Limites restantes

Bindings simples exacts seulement ; aucune complétude obligatoire. Colonnes, champs,
conditions, formulaires avancés, routes et résolution filesystem reportés.
Résultat tronqué jamais valide. Types des modèles supposés corrects, pas de garantie
de déterminisme sous mutation concurrente. Gel des entrées toujours superficiel.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `feat: valider les bindings simples (FD-BINDING-001)`.
Diff utilisateur FD-CONTRACT-001 conservé hors commit ; Forge Core inchangé.
Hash et état final communiqués dans la livraison.
