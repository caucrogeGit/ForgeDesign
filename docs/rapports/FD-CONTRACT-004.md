# Rapport — FD-CONTRACT-004

## Ticket et objectif

Relier les templates physiques et les contrats validés par la seule déclaration
contract.template. Projection en lecture seule, diagnostics de cible et ambiguïtés,
sans UI, Tool, génération ou validation d'entités/routes.

## État Git initial

main synchronisée avec origin/main à `9b44be3`. État Git et dix derniers commits
inspectés. Modification utilisateur du rapport FD-CONTRACT-001.md conservée
(« État Git initiala »), non modifiée et hors commit. Aucun AGENTS.md trouvé.
Baseline 1630 tests.

## Baseline Forge

Lecture distante de ../Forge origin/main :
`73a956e587e5f169c028415e0e540c149cbaff56`, identique à la baseline attendue.
Dépôt Forge propre, aucun fichier modifié. Squelette copié dans le scénario installé.

## Principe de liaison

analyze_view_contract_links(root) compose read_templates, read_view_contracts et
une lecture par contrat inventorié. Inspection sécurisée par cible distincte,
puis _project_links, fonction interne pure. Aucun troisième scanner.

## Source de vérité contract.template

Nom du fichier, nom logique et voisinage n'interviennent jamais dans la résolution.
Le test different/abc.view.json → target.jinja prouve la liaison explicite avec un
name différent. Les données brutes d'un contrat invalide ne sont jamais récupérées.

## Modèles de liaison

Dataclasses frozen et tuples : ViewContractLink, TemplateContractStatus,
ViewContractLinkIssue, ViewContractLinksResult. Exports publics avec les deux
vocabulaires Literal, analyze_view_contract_links et is_view_template_path.
Le résultat distingue issues de liaison, contract_issues originales et template_issues
originales. Il expose truncated et contracts_complete pour expliciter les limites.
Statuts principaux contrat : linked, template-missing, template-unreadable,
template-invalid-path et contract-invalid. Ambiguïtés portées par des issues
indépendantes pour ne pas perdre plusieurs anomalies simultanées.

## Templates physiques

Tout fichier régulier admissible sous views, sans restriction .html, sauf suffixes
exacts .view.json et .design.json. is_view_template_path centralise cette règle
locale avec la politique source commune. Aucun changement de read_templates.
Les métadonnées reconnues ne sont ni des lignes « sans contrat » ni des cibles
utilisateur admissibles. Cible non HTML, binaire ou Jinja cassée physiquement
ouvrable peut être linked : aucune validation de contenu cible.

## Contrats valides et invalides

Contrat valide : nom et cible déclarés conservés. Contrat invalide : ligne
contract-invalid avec name/declared_template/template_path à None, diagnostics
source intacts. JSON cassé et erreur de modèle restent distincts.
Un template voisin peut être without-contract simultanément ; aucune supposition
par filename. Disparition d'un contrat après scan : issue contract.unreadable,
ligne contract-invalid et collecte contractuelle incomplète, sans exception d'absence.

## Validation des chemins cible

source_parts(contract.template), contrôle explicite de mvc/views puis conversion
relative. Exclusion des métadonnées avant inspection. Chemin hors views même dans
un modèle synthétique, traversal, noms cachés/sensibles : template-invalid-path,
aucun accès cible. Le schéma normatif reste structurel et inchangé.

## Templates sans contrat

Avec inventaire contractuel complet : zéro chemin associé → without-contract,
sans issue automatique ; un → linked ; plusieurs → ambiguous. Template manuel
sans contrat légitime. Si l'exhaustivité n'est pas connue, zéro ou un → unknown.
Une ambiguïté déjà observée reste certaine même avec collecte incomplète.

## Contrats sans template

Inspection directe FileNotFoundError → template-missing et issue de liaison.
L'absence dans l'inventaire seule ne permet jamais cette conclusion.
Une cible présente hors inventaire est ajoutée aux lignes après inspection réussie.

## Doublons de name

Index Counter sur les noms de tous les contrats validés, égalité exacte Unicode.
contract.link.duplicate-name sur chaque déclaration concernée, sans gagnant ou fusion.
Le statut principal peut rester linked : il décrit la cible physique, pas l'unicité.

## Plusieurs contrats par template

Index sur les cibles lexicalement admissibles. contract.link.multiple-contracts
sur chaque déclaration, y compris pour une cible manquante/inaccessible partagée.
Pour une cible inspectée avec succès, tous les contract_paths restent visibles et
la ligne template est ambiguous. Même nom + même cible conserve les deux catégories
d'issues. Aucun choix par ordre lexical, proximité ou ancienneté.

## Inventaires tronqués

Toute troncature templates/contrats ou des diagnostics de détail propage truncated
et un marqueur final contract.link.analysis-truncated.
contracts_complete=False si inventaire contractuel tronqué/avec issues ou contrat
illisible/disparu. JSON ou modèle définitivement invalide ne crée pas à lui seul
une incertitude sur un contrat valide caché. L'inspection directe résout l'existence
d'une cible même hors inventaire templates, mais ne résout pas l'exhaustivité des
contrats qui pourraient la déclarer.

## Diagnostics

Codes de liaison : contract.link.invalid-template-path, template-missing,
template-unreadable, duplicate-name, multiple-contracts et analysis-truncated
(tous préfixés contract.link.). Issues par déclaration, ordre déterministe.
MAX_VIEW_CONTRACT_LINK_ISSUES=512, marqueur terminal inclus : jusqu'à trois anomalies
par contrat justifient ce plafond. Exact-limit sans surplus ne tronque pas.
Aucune limite MAX_LINKS ajoutée : liens bornés par les 512 contrats inventoriés ;
au plus 512 templates inventoriés + 512 cibles vérifiées supplémentaires.
Issues source préservées, déjà bornées par leurs lecteurs (jusqu'à 512 + 512 × 256
issues contractuelles). Aucune perte de code/location par traduction générique.

## Déterminisme et complexité

Contrats dans l'ordre lexical du lecteur, templates triés par path, issues dans
l'ordre des contrats et des contrôles. Index locaux noms/cibles et projection
O(T+C), hors diagnostics, I/O et tris de présentation. Aucun produit cartésien.
Cache d'inspection par cible limité à l'appel ; doublons toujours conservés.
Projection pure testée avec open/os.open/Path.read_text interdits.

## Sécurité filesystem

Confinement des lecteurs réutilisé sans modification. Inspection directe via
inspect_project_source : ancrage segment par segment, O_NOFOLLOW/O_NONBLOCK,
fichier régulier, identité et borne de taille. Symlink fichier/parent/views,
FIFO/socket/dossier et fichier trop gros ne deviennent pas linked.
Aucune lecture du contenu cible, aucun parsing Jinja/dépendances supplémentaire.

## Races

Suppression ou remplacement par symlink entre inventaire et inspection testés.
L'observation directe est prioritaire : ligne template inventoriée devenue absente
ou inaccessible retirée, déclaration et issue conservées côté contrat.
Les candidats sans déclaration ne sont pas réinspectés ; leur état reste celui
de l'inventaire. Observation cohérente au mieux pendant l'appel, aucun snapshot
atomique. Deux déclarations d'une cible partagent le même contrôle durant l'appel.
Modifications de nom/cible/validité et suppression contractuelle visibles au suivant.

## Non-exécution

Fixtures app.py/config.py/controller levant à l'import, cible Jinja cassée ou binaire,
sans exécution. Aucun import projet, rendu, interprétation des actions, entités,
fields ou contrôleur. Aucun subprocess Forge.

## Non-écriture

Snapshots octets/taille/mtime projet et XDG comparés en tests et scénario installé.
Identité CurrentProjectContext.inspection et racine inchangées pendant les analyses.
Créations/modifications/suppressions sont effectuées explicitement par la fixture
entre appels. Aucun fichier Forge modifié, aucune configuration persistée par la liaison.

## Compatibilité contrats 001–003

Schéma, modèles Pydantic, reader et fixtures inchangés. Aucune dépendance ajoutée.
Les diagnostics originaux conservent leur code, message, path et location.
Les exceptions de niveau projet restent celles des lecteurs existants.

## Compatibilité Template Viewer

Inventaire historique intact : .view.json et .design.json restent visibles dans
Template Viewer. Seule cette projection les exclut. Aucun Web, Tool, template HTML,
script, graphe ou analyse Jinja modifié. Registre toujours exactement cinq Tools.

## Fichiers créés

- forge_design/contracts/linkage.py
- tests/test_view_contract_linkage.py
- docs/rapports/FD-CONTRACT-004.md

## Fichiers modifiés

- forge_design/contracts/__init__.py : exports.
- forge_design/limits.py : plafond des issues de liaison.
- docs/contracts/view-contract.md : statuts, ambiguïtés et observation partielle.
- docs/02-architecture.md : composition I/O et projection pure.

Le rapport 001 préexistant est exclu du commit.

## Tests ajoutés

29 cas : liaison explicite et absence d'inférence, templates manuels/non HTML,
JSON/Pydantic invalides, chemins interdits et métadonnées cibles, objet synthétique
hors views, trois combinaisons de doublons, refresh, cibles liées/spéciales/trop grosses,
views symlink, suppression/remplacement pendant observation, contrat disparu,
troncatures des deux inventaires, cible hors inventaire, cache par cible, limite
exacte/surplus des issues, projection pure, Unicode et non-écriture.
Tous les 1630 tests précédents restent actifs et inchangés.

## Test réel

Copie du squelette Forge, wheel installée, processus Python -I avec provenance de
forge_design/contracts/linkage vérifiée. Home lié, manual sans contrat, missing absent,
broken JSON invalide, deux contrats de même name et deux contrats vers shared.jinja.
Vérification des statuts, issues et déterminisme. Création de la cible manquante →
linked ; suppression du contrat home → without-contract ; shared remplacé par
symlink → template-unreadable pour les deux déclarations, plus aucune ligne physique
shared dans la projection. Snapshots projet/XDG et contexte conservés à chaque appel.
Script/journal ignorés : tmp/verify_fd_contract_004.py et .log.

## Packaging

Wheel : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `472127728fe8a689e2675a9fc0cf8700a60f8c7e905ff97b4a0481c736b88bcc`.
Models, reader, linkage, __init__, limits et schéma comparés aux octets sources.
Aucun tests/ ou tmp/ distribué. METADATA conserve Requires-Dist pydantic<3,>=2.
Installation --no-deps --no-index --target ; dépendances déjà dans .venv, métadonnées
vérifiées séparément. Scénario isolé réussi, aucune dépendance nouvelle.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| git status ; git log --oneline --decorate -10 | Baseline conforme, diff utilisateur conservé |
| git -C ../Forge ls-remote origin refs/heads/main | Baseline distante identique |
| pytest ciblé schema/models/reader/linkage | 250 réussis |
| pytest -q --tb=short | 1659 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Inspection wheel, installation et scénario Python -I | Succès |

Outils .venv, Python 3.13.5. Suites avec sockets et build isolé autorisés hors sandbox.
Typage des doubles de lecteurs corrigé avant validation finale. Installation et
scénario sans réseau. Journal : tmp/pytest_fd_contract_004.log. Diff et nouveaux
fichiers relus ; aucun changement du rapport utilisateur.

## Tests sautés

Aucun pytest sauté. Node exécuté. MkDocs build --strict non applicable, aucune
configuration MkDocs. Aucun parcours Web ou navigateur ajouté/revendiqué.

## Limites restantes

Observation non atomique et cache par cible intra-appel. Cibles non déclarées vues
seulement à l'inventaire. Bornes et sous-ensemble filesystem hérités des lecteurs.
linked garantit une cible physique inspectable à cet instant, pas UTF-8, Jinja,
unicité de name, validité métier ou disponibilité future. Issues d'ambiguïté à
consulter séparément du statut principal. Diagnostic de troncature global, sources
bornées mais potentiellement nombreuses. Aucun croisement entité/route, contrôleur,
génération ou UI.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `feat: lier templates et contrats de vue (FD-CONTRACT-004)`.
Diff utilisateur du rapport 001 conservé non commité. Hash et état Git après commit
communiqués dans la réponse de livraison.
