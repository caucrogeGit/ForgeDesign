# Rapport — FD-TEMPLATE-004

## Ticket et objectif

Rendre les références Jinja statiques locales navigables depuis les vues brute et
arbre, uniquement après validation lexicale et inspection sécurisée sous mvc/views.
Aucun parsing cible, rendu, opt-in, transitivité, Tool, route ou JavaScript ajouté.

## État Git initial

main propre et synchronisée avec origin/main à `1b0a863`, FD-TEMPLATE-003.
État Git et dix derniers commits inspectés. Aucun AGENTS.md ou MkDocs configuré.
Squelette Forge local à `73a956e587e5f169c028415e0e540c149cbaff56`, dépôt propre.
Aucun fichier Forge modifié.

## Contrat TemplateNavigation

Dataclass gelée : reference, status, target_path=None. États disponibles :
available, dynamic, invalid-path, missing, unreadable. target_path n'est renseigné
que pour available. resolve_template_references(root, references) retourne un tuple
dans l'ordre original ; chaque occurrence garde sa référence et sa ligne.
La racine fournie est la racine canonique courante, déjà contrôlée par la lecture
principale. Aucun état global ou persistant.

## Validation lexicale

reference_rejection est une étape pure : dynamic=True ou path=None donne dynamic.
Les autres chemins passent par template_source/source_parts, sans politique
parallèle. Traversal, absolus, segments cachés/vides, backslash, deux-points, NUL,
noms sensibles et longueur excessive donnent invalid-path, sans ouverture.
Aucune normalisation a/../b, résolution d'expression ou double décodage.

## Inspection filesystem locale

Petite extraction de l'ouverture du lecteur commun en context manager privé.
inspect_project_source retourne SourceMetadata(size, modified_ns), sans lire le
contenu. Inspection et read_project_source_details partagent exactement ancrage
segment par segment, O_NOFOLLOW/O_NONBLOCK, type régulier, stat/fstat/samestat et
borne historique de 1 Mio. Descripteurs fermés en finally, y compris après erreur.
Aucun Path.exists comme garantie, aucune ouverture non confinée.

Le lecteur brut garde décodage UTF-8/BOM et contrôle de mutation size/mtime/ctime.
Ses APIs, erreurs et handler /source restent inchangés ; aucun refactoring des
lecteurs d'inventaire ou Routes.

## Références statiques

extends/include/import/from-import traités identiquement depuis les références
existantes. Chaque chemin autorisé désigne seulement mvc/views/<path>. Include
liste statique : chaque référence est indépendante, doublons conservés. Aucun
contenu cible injecté dans la page appelante, aucun parsing supplémentaire.
Un fichier Jinja syntaxiquement cassé reste navigable vers le brut.

## Références dynamiques

Pas d'accès filesystem ni même conversion du path d'une référence dynamique.
Une liste mixte reste la référence dynamique produite par FD-TEMPLATE-002 ; aucune
récupération de ses sous-parties littérales. État textuel « Non résolue statiquement ».

## États missing/unreadable

FileNotFoundError pour un chemin admis : missing, texte « Non disponible dans
mvc/views/ ». Source liée, parent refusé, type spécial/dossier, remplacement,
inaccessibilité ou taille excessive : unreadable, texte « Source locale inaccessible ».
Aucun lien pour ces états ou invalid-path/dynamic.

available confirme ouverture régulière locale et taille autorisée au moment du
contrôle. L'inspection ne décode pas UTF-8 : un fichier binaire peut proposer Voir
puis être refusé 409 à la lecture. Cette limite explicite évite le préchargement de
contenu et ne prétend pas valider la source ou sa syntaxe.

## Opt-ins

Aucune instanciation de loader, import de package ou recherche site-packages.
Une référence absente localement peut être fournie par un opt-in ; l'interface
ne conclut jamais à une inexistence globale dans Forge. Une surcharge physique
locale apparaît normalement.

## Intégration vue brute

Le détail commun résout une fois structure.dependencies après l'unique lecture et
analyse principales. La section Dépendances déclarées conserve type/chemin/ligne
et ajoute état local/action. Source brute, métadonnées et analyse textuelle intactes.
Chaque occurrence available propose Voir vers le fichier brut spécialisé.

## Intégration arbre

Même tuple de navigation, mêmes libellés et helper URL que la vue brute. Les
références deviennent type/ligne puis chemin ou dynamique, état local et Voir
éventuel. Blocks, hiérarchie HTML, partial/truncated et rendu itératif inchangés.
Le texte précise observation locale courante, sans promesse de disponibilité future.

## URLs et encodage

template_url/urlencode existants, uniquement /templates/view?path=... . Aucun lien
arbre secondaire par dépendance, /source, return_to, next, from ou pile de navigation.
Retour par le navigateur ; la cible brute garde Voir l'arbre. Tests d'espaces,
accents/emoji, &, +, %, guillemets et balises dans les noms admissibles.
Un nom contenant littéralement %2e%2e reste ce nom, sans double décodage.

## Sécurité

Politique source unique, ouverture refusant liens et fichiers spéciaux, contrôle
d'identité contre remplacement. Tests FIFO, socket Unix, lien fichier/parent et
race stat/open. Cas hostiles synthétiques échappés dans les deux vues ; un path
refusé ne crée aucun href. Un nom admissible hostile existant est encodé dans une
URL locale et échappé dans le texte/aria-label. Aucun Markup, safe ou JS ajouté.

## Accessibilité

États visibles en texte, jamais couleur seule. Lien Voir avec aria-label
« Voir le template <chemin complet> ». En-têtes État local/Action dans le tableau,
liste hiérarchique serveur conservée dans l'arbre. Navigation globale inchangée.
Vérifications DOM ; aucun navigateur/lecteur d'écran réel revendiqué.

## Performance

Au plus MAX_TEMPLATE_REFERENCES=512, constante existante. L'API refuse une entrée
synthétique de 513 références avant toute I/O, sans nouveau plafond ni troncature
silencieuse. Dictionnaire local de statuts par path : contrôle unique d'un chemin
répété dans cet appel, tout en conservant les déclarations. Aucun cache entre GET.
Coût O(références) hors opérations filesystem. Les cibles ne sont ni lues ni
analysées ; aucune recherche de références transitives ou de cycles.

## Non-exécution

Pas de loader, get_template, rendu cible, import projet, subprocess ou DB dans la
navigation. Les tests interdisent os.read/fdopen et Path.read_text/read_bytes pendant
la résolution. Une cible contenant une référence jamais inspectée et du Jinja
cassé reste disponible ; aucune analyse de son contenu n'a lieu avant le clic.
Tests historiques des projets hostiles conservés.

## Non-écriture

Snapshots de fichiers source/cible/historique en HTTP ; scénario installé comparant
projet/XDG en octets, taille, mtime et identité CurrentProjectContext.inspection
avant/après chaque GET. Aucun changement. Mutations entre requêtes uniquement par
le script de fixture. Aucun cache persistant ou fichier .forge-design.

## Compatibilité Template Viewer

Inventaire, parser Jinja/HTML, projection arbre, Tool, registre et routes HTTP
inchangés. Une lecture source et une analyse principales, auxquelles s'ajoutent les
seules inspections de références statiques directes. Les tests instrumentent cet
ordre et le cache. Source/métadonnées/statuts/no-store et navigation brut/arbre
historiques conservés ; tests FD-TEMPLATE-001/002/003 actifs sans modification.

## Compatibilité Route Explorer

forge/routes.py, parser commun, graphes, filtres, cycles, layouts et scripts
inchangés. Suites historiques Routes et /source actives et vertes. Toujours cinq
Tools ; aucune utilisation de Route Explorer par la navigation du Viewer.

## Fichiers créés

- forge_design/tools/template_navigation.py
- tests/test_template_navigation.py
- tests/test_web_template_navigation.py
- docs/rapports/FD-TEMPLATE-004.md

## Fichiers modifiés

- forge_design/forge/source.py : ouverture commune et inspection sans contenu.
- forge_design/web/template_viewer.py : résolution unique et états communs.
- forge_design/web/templates/template_view.html : états/action dans la structure.
- forge_design/web/templates/template_tree.html : états/action dans l'arbre.
- docs/tools/template-viewer.md : navigation, observation locale et limites.
- docs/02-architecture.md : résolution contrôlée vers TemplateNavigation.

Aucune modification de packaging, dépendance, CSS, JavaScript, roadmap ou Forge.

## Tests ajoutés

26 cas : 22 unitaires et 4 HTTP paramétrés. Quatorze chemins refusés sans I/O ;
trois variantes dynamiques sans accès ni validation path. Présent/absent/nested,
UTF-8 non prévalidé, taille excessive, absence de lecture du contenu, modèles gelés.
Symlinks fichier/parent, dossier, FIFO, socket Unix, remplacement pendant inspection,
inaccessibilité simulée, 512/513 références, cache et refresh sans fusion des doublons.

HTTP même matrice available/missing/dynamic/invalid-path/unreadable sur brut/arbre,
liens exacts et nom accessible, contenu cible absent, une lecture/analyse de source,
inspections directes uniques, noms hostiles/Unicode/encodage, XSS synthétique refusée,
no-store, non-écriture, clic vers Jinja invalide (200), ajout puis suppression (404)
et symlink (409). Aucun lien sur les états non available, vérifié par parsing DOM.

## Test réel

Wheel installée --no-deps --no-index --target dans un dossier temporaire ; processus
Python -I avec provenance installée des modules vérifiée et cinq Tools. Copie du
squelette Forge. Home : extends layouts/base.html et from-import components/ui.html
available ; base : include partials/nav.html available. Liens suivis, contenu brut
cible comparé au fichier réel. Parcours brut/arbre conservé sur quatre templates.

Fixture navigation : référence locale absente, dynamique, traversal et opt-in
plausible non local. États attendus sans lien dans les deux vues. Création externe
de la cible avec Jinja cassé : lien visible et source brute 200. Suppression : lien
retiré et ancien clic 404. Remplacement par symlink : unreadable et clic 409.
Modifications structurelles/partielles et suppression du template principal aussi
vérifiées. /routes, /entities et /debug accessibles.

Snapshots projet/XDG et contexte inchangés par les GET. Serveur arrêté, thread
terminé, socket fermé et port réutilisable. Forge demeure propre.
Script/journal ignorés : tmp/verify_fd_template_004.py et .log.

## Packaging

Wheel : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `6226b3107718704156be8e4af20b199b726cedc68b7e91bd827a90d376da083b`.
Archive inspectée : navigation, source, modules structure/arbre/Routes/Bridge/Tool/
Web, templates, CSS et scripts comparés aux octets sources. Aucun tests/ ou tmp/
distribué. Installation réelle et scénario HTTP réussis, aucune nouvelle dépendance.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| git status ; git log --oneline --decorate -10 | Baseline conforme |
| Tests navigation et régressions source/templates ciblés | 203 réussis |
| pytest -q --tb=short | 1381 réussis, 26 nouveaux cas |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Wheel inspectée/installée, liens suivis en HTTP | Succès |
| git -C ../Forge status --short | Propre |

Outils .venv, Python 3.13.5, Node disponible. Premier test socket Unix bloqué en
sandbox ; tests sockets/HTTP ensuite autorisés hors sandbox et réussis. Build
isolé et scénario installé également autorisés. Annotation du context manager
corrigée d'Iterator vers Generator selon pyright avant la validation complète.
Journal : tmp/pytest_fd_template_004.log. Diff, nouveaux fichiers et rapport relus.

## Tests sautés

Aucun test pytest sauté. Aucun navigateur réel ou lecteur d'écran testé.
Aucune configuration MkDocs : mkdocs build --strict non applicable.

## Limites restantes

État affiché = observation du GET courant, sans garantie atomique/persistante.
Le cache de l'appel ne reflète pas un changement intervenant entre deux occurrences
du même chemin pendant ce GET. Une cible peut disparaître avant clic (404), devenir
liée/inaccessible (409), ou échouer au décodage UTF-8 non effectué par l'inspection.
La taille est contrôlée mais aucune syntaxe cible n'est validée avant navigation.
Pas de résolution d'opt-in, graphe transitif, cycles Viewer ou historique de retour.
Les limites HTML/Jinja et du rendu profond des tickets précédents restent inchangées.

## État Git final

Un seul commit local sur main, rapport inclus, sans push conformément au ticket.
Message : `feat: naviguer entre les templates (FD-TEMPLATE-004)`.
Hash et état Git final vérifiés communiqués dans la réponse de livraison.
