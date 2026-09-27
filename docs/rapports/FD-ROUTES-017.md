# Rapport — FD-ROUTES-017

## Ticket et objectif

Consolider les faits statiques déjà calculés dans un modèle immuable de diagnostics, puis les afficher sans nouvelle analyse ni verdict global.

## État Git initial

`main` propre et synchronisée avec `origin/main`, HEAD `b2165c2` — FD-ROUTES-016.
État Git et cinq derniers commits inspectés avant modification.

## Modèle Diagnostic

`Diagnostic` gelé contient code, severity, message, source optionnelle, subject optionnel et source_available.
Le dernier champ indique si la référence déjà connue peut être proposée à la navigation ; il ne déclenche aucun contrôle filesystem.
`RouteDiagnostics` gelé contient un tuple items. Aucun objet RouteInfo complet, état persistant ou score.

## Codes de diagnostic

| Codes | Sévérité |
|---|---|
| route.partial, handler.dynamic | warning |
| controller.missing, controller.class_missing, controller.method_missing | error |
| controller.ambiguous, controller.unreadable | warning |
| template.dynamic, template.ambiguous | warning |
| template.missing, template.invalid_path, template.syntax_invalid | error |
| template.unreadable | warning |
| template.dependency_missing, template.dependency_invalid_path, template.dependency_syntax_invalid | error |
| template.dependency_unreadable | warning |
| template.cycle | error |
| template.analysis_truncated | warning |

Aucun diagnostic systématique pour les dépendances dynamiques, conformément à la préférence du ticket.

## Sévérités

error exprime une relation statique cassée, une référence refusée ou un cycle connu ; warning une incertitude ou une limite.
info est accepté par le modèle mais aucun succès systématique n'en produit.
Les messages décrivent des faits disponibles, pas une qualité globale ou une garantie de fonctionnement runtime.

## Consolidation

`build_route_diagnostics(result)` consomme routes, handlers, templates, déclarations directes/transitives, cycles et troncature.
Les statuts structurés commandent les codes et sévérités. Les lignes et messages Jinja existants sont conservés dans le diagnostic syntaxique.

Deux faits étaient détectés mais perdus : l'absence explicite de fichier contrôleur était ramenée à unreadable, et None ne distinguait pas un handler dynamique d'une valeur non renseignée.
`HandlerInfo.missing_controller` conserve désormais le chemin attendu dans le catch FileNotFoundError existant ; `RouteInfo.handler_dynamic` conserve le résultat déjà connu de l'extraction du handler.
Ces champs ajoutés en fin de modèle ont des valeurs par défaut compatibles. Aucun contrôle, accès fichier ou parsing supplémentaire ; les anciens statuts et warnings restent identiques.

Les warnings historiques restent affichés intégralement. Un unique route.partial signale leur présence et renvoie aux détails, sans classifier ni parser leurs chaînes.
Les limites historiques sans structure dédiée ne reçoivent donc pas encore de diagnostic individuel localisé. Les anomalies disposant de statuts typés utilisent leurs propres codes.

## Déduplication

Ensemble local de clés code/sujet/source, première occurrence conservée.
Pour les erreurs d'un template principal partagé et les erreurs de syntaxe/lecture d'une dépendance partagée, code/sujet suffit : plusieurs appels ne multiplient pas l'erreur de fichier.
Les dépendances manquantes ou refusées conservent leurs déclarations source distinctes ; la même déclaration retrouvée depuis plusieurs racines est dédupliquée.
Les cycles utilisent leur clé canonique existante, sans nouvelle détection. Troncature : un diagnostic par racine.
Les rôles template principal et dépendance conservent leurs codes distincts, même lorsqu'ils concernent le même fichier.

## Ordre

Routes dans leur ordre, faits associés, dépendances directes puis fermetures connues, cycles et troncature ; résumé historique en dernier.
Une fermeture est parcourue une fois par racine. Un index de sources permet de localiser les cycles sans rechercher tous les nœuds pour chaque cycle.
Coût proportionnel aux routes, déclarations des fermetures distinctes et diagnostics/cycles matérialisés. Aucun parcours récursif ou découverte.

## Comptages

error_count, warning_count et info_count sont des propriétés calculées depuis items.
Aucun compteur stocké séparément, aucun pourcentage ou statut global de projet.

## Sources

Contrôleur absent : déclaration de route ; classe/méthode absente : contrôleur connu.
Template absent ou refusé : méthode contrôleur, ou référence source disponible en repli.
Syntaxe principale invalide : template présent et ligne syntaxique.
Dépendance en erreur : source et ligne de sa déclaration ; le message distingue la ligne syntaxique dans sa cible.
Cycle : première relation canonique et sa ligne connue. Troncature : template racine, lié seulement s'il est présent.
La politique lexicale source_parts existante refuse les références non navigables, sans accès disque. Le Web réutilise source_url et la macro location ; aucune nouvelle route.

## Pureté et isolation

Le constructeur ne lit aucun fichier, n'appelle aucun parser, Bridge, registre ou détecteur de cycles.
Sentinelles sur open/stat/lstat/scan, ast.parse, Environment.parse, read_routes, ToolRegistry et detect_template_cycles.
Les modèles d'entrée restent identiques ; les diagnostics et leur conteneur sont gelés. Même entrée, même ordre et même résultat.

## Intégration Web

Section Diagnostics avec sévérités textuelles, compteurs et liste compacte. Les codes sont également exposés comme attributs data pour identifier les diagnostics.
Messages et sources échappés par Jinja. Liens internes existants, aucun HTML brut, filtre interactif ou JavaScript.
Tableau, warnings historiques, section Cycles de templates, SVG et no-store conservés.
Flux parallèle documenté : RoutesResult → RouteDiagnostics → Web et RoutesResult → RouteGraph → SVG.

## Fichiers créés

- [forge_design/tools/route_diagnostics.py](../../forge_design/tools/route_diagnostics.py).
- [tests/test_route_diagnostics.py](../../tests/test_route_diagnostics.py).
- [docs/rapports/FD-ROUTES-017.md](FD-ROUTES-017.md).

## Fichiers modifiés

- [forge_design/forge/routes.py](../../forge_design/forge/routes.py) : conservation de deux faits déjà détectés.
- [forge_design/web/routes.py](../../forge_design/web/routes.py) : consolidation du résultat existant.
- [forge_design/web/templates/routes.html](../../forge_design/web/templates/routes.html) : Diagnostics.
- [tests/test_routes.py](../../tests/test_routes.py) : attentes des champs enrichis.
- [tests/test_web_inspector.py](../../tests/test_web_inspector.py) : diagnostics HTTP.
- [docs/02-architecture.md](../02-architecture.md) : contrat pur et limites.

Aucune dépendance ni métadonnée de distribution modifiée.

## Tests ajoutés

26 nouveaux cas : 25 contrôles de consolidation et un contrôle HTTP ; les quatre scénarios HTTP de cycle/troncature existants sont enrichis.
Couverture : tous les codes, sévérités, compteurs, vide/valide, absence de bruit dynamique, faits Bridge retenus, sources, ordre, déduplication de fichiers et déclarations, cycles partagés entre racines distinctes, immutabilité et isolation.
Les tests HTTP vérifient erreurs, avertissements, compteurs exacts, code stable, lien source suivi, échappement HTML, cycles, analyse partielle et conservation des surfaces précédentes avec no-store.
Les attentes antérieures de handler dynamique et contrôleur manquant sont adaptées aux nouveaux champs sans relâcher les assertions existantes.

## Test réel

Wheel reconstruite et installée sans dépendances dans un répertoire temporaire. Processus Python isolé avec origine d'import vérifiée et runtime de `.venv`.
Une copie du squelette reçoit une route et un contrôleur valides, un template principal incluant missing.html, et le cycle base.html → layouts/site.html → macros/layout.html → base.html.
Le GET /routes expose template.dependency_missing et template.cycle, les erreurs, compteurs, le SVG et les anciens diagnostics.
Les liens source route/contrôleur/template sont suivis ; no-store, numérotation et absence d'écriture vérifiés. Serveur arrêté, socket fermé et port réutilisable.
Le dépôt Forge de référence reste intact. L'absence d'analyse dans la consolidation est instrumentée par les tests unitaires.

Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `645003145df16cc3f8832e0640e43e8d659ca2b19c0aaab88514f735fc57a693`.
Script ignoré : `tmp/verify_fd_routes_017.py`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| État Git et historique | Vérifiés |
| `pytest` | 470 tests réussis, dont 26 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| `python -m pip wheel --no-deps --wheel-dir tmp/wheels .` | Succès |
| Wheel installée et diagnostics HTTP | Succès |

Outils de `.venv`, Python 3.13.5 ; HTTP avec autorisation de sockets locaux hors sandbox.
Les premières égalités de modèles et lignes trop longues sont corrigées avant validation finale. Pip a désactivé son cache utilisateur inaccessible sans erreur de dépendances.
Le diff complet est relu avant commit, rapport et nouveaux fichiers compris.

## Tests sautés

Aucun test pytest sauté. Aucun contrôle visuel navigateur, rendu cible ou nouvelle génération Forge revendiqué.

## Limites restantes

Diagnostics statiques uniquement, avec les limites du lecteur et des fermetures bornées existantes.
Le résumé route.partial ne localise pas les warnings historiques dépourvus de structure. Les codes principal/dépendance restent distincts ; la première source d'une erreur de fichier partagée est conservée.
Les liens sont des références d'instantané : les fichiers peuvent changer avant ouverture. Aucun score, verdict runtime ou correction.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `feat: consolider les diagnostics Route Explorer (FD-ROUTES-017)`.
Le hash et l'état Git après commit sont communiqués dans la réponse de livraison.
