# Rapport — FD-ENTITIES-007

## Ticket et objectif

Ouvrir les contrats JSON d’Entity Explorer en lecture seule via GET /source,
depuis les entités, relations et diagnostics, avec une politique stricte.

## État Git initial

main propre, synchronisée avec origin/main à `cb618dc` — FD-ENTITIES-006.
`git status` et les cinq derniers commits inspectés avant modification.
Aucun AGENTS.md trouvé dans le dépôt.

## Politique source existante

source_parts reste la source de vérité lexicale. Les règles historiques restent :
.py directement sous mvc/routes ou mvc/controllers ; fichiers imbriqués sous mvc/views.
Les tests historiques source et Route Explorer restent actifs, sans modification.

## Extension mvc/entities

Ajout d’une branche _is_entity_source, après les protections globales partagées.
Regex fixe identique à celle d’Entity Explorer, sans nouvelle dépendance ni
modification de forge/entities.py. Aucune consultation filesystem dans la politique.

## Chemins autorisés

- mvc/entities/relations.json, exactement ;
- mvc/entities/<snake>/<snake>.json, avec correspondance exacte dossier/fichier
  et nom conforme à `[a-z][a-z0-9]*(?:_[a-z0-9]+)*`.

## Chemins refusés

Fichiers Python/SQL, JSON isolés ou de nom différent du dossier, profondeur
supplémentaire, majuscules et noms non conformes. Les refus globaux subsistent :
segments vides/cachés, . et .., env, suffixes .pem/.key, préfixes SSH sensibles,
antislash, deux-points, NUL, chemins absolus et longueur supérieure à 4096.
Aucune normalisation du chemin source. Les valeurs décodées par HTTP sont soumises
à la même politique ; double encodage non interprété comme une autorisation.

## Confinement filesystem

openat via dir_fd, O_DIRECTORY, O_NOFOLLOW, O_NONBLOCK, fstat/samestat et limites
avant/après lecture conservés. Fichiers réguliers uniquement, 1 Mio maximum,
UTF-8/BOM, tous les descripteurs fermés en finally.

Renforcement justifié de l’ancrage : ouvrir la racine complète avec O_NOFOLLOW
ne refuse pas les symlinks de ses parents intermédiaires. Le lecteur ouvre donc
désormais chaque segment de la racine absolue par descripteur, avant mvc et ses
descendants. Un segment .. de racine non canonique est refusé. Les tests couvrent
parent de racine, racine, mvc, entities, dossier d’entité et JSON liés.

Le JSON n’est pas parsé. Un fichier contenant seulement une accolade ou du texte
non JSON reste lisible ; encodage invalide, FIFO, dossier et fichier trop grand
restent refusés. Les garanties de lecture des espaces historiques sont conservées.

## Navigation Entity Explorer

Une macro location utilise la SourceLocation existante et source_available avant
source_url(source.path). Aucun chemin reconstruit depuis le nom métier, aucune
query string manuelle, aucune ligne ou pseudo-ancre générée, même si une fixture
synthétique fournit un numéro de ligne. Les liens ouvrent le fichier entier.
Entités : lien dans les détails ; relations : lien du JSON suivi de relations[n].
Les filtres restent actifs ; le retour à /entities n’en préserve pas les valeurs.
Les nœuds du graphe restent consacrés à la sélection locale.

## Diagnostics et sources

Les sources autorisées des diagnostics deviennent des liens, y compris JSON invalide.
Source absente, dossier mvc/entities ou chemin hostile : texte échappé sans lien.
source_available utilise uniquement source_parts, sans accès filesystem ; il
vérifie l’autorisation lexicale, pas l’existence ni la lisibilité. Une source
lexicalement autorisée peut donc produire 404 ou 400 lors de l’ouverture.
Aucun changement de modèle ou de projection des diagnostics.

## Retour contextuel

show_source appelle source_parts et déduit active_page du tuple validé : entities
pour mvc/entities, routes pour les trois espaces historiques. Le template propose
le retour fixe correspondant. Aucun return_to pris en compte, aucune redirection.
Chemin refusé avant catégorisation, projet absent ou ligne mal formée : état neutre.
Une source autorisée mais absente conserve son contexte et retourne 404.
Le lecteur revalide la même politique à sa frontière ; aucune politique divergente.

## Sécurité

Liens encodés par source_url, contenus et chemins échappés par Jinja. Tests de XSS
sur contenu et SourceLocation synthétique. Pas de parsing/colorisation JSON,
exécution cible, formulaire de chemin, scan, catalogue, navigation dossier ou écriture.
Tests bloquant json.loads/load, exec/eval et subprocess pendant la lecture brute.
Helper lexical testé avec open/stat/Path.exists interdits. Les chemins refusés
sont testés avec os.open interdit, garantissant le refus avant ouverture.

GET /source existant réutilisé, POST reste 405, no-store conservé pour 200/400/404.
Aucun nouveau Tool, route, JavaScript ou CSS. Registre inchangé à trois Tools.

## Non-écriture

Tests unitaires et HTTP comparant octets, taille et mtime des fichiers projet.
Scénario installé comparant aussi la configuration XDG avant/après chaque GET.
Aucune différence. La modification volontaire du JSON pour le scénario cassé
est faite uniquement par le script de vérification, entre deux phases de consultation.

## Régression Route Explorer

Les sources routes/controllers/views conservent liens, retour Route Explorer,
numérotation, cible line et message de ligne hors fichier. Le moteur de lecture et
les tests historiques restent actifs. Aucune modification des scripts de graphe,
des filtres Entity Explorer, du Bridge entités ou de EntityExplorerTool.

## Fichiers créés

- tests/test_entity_source.py
- tests/test_web_entity_source.py
- docs/rapports/FD-ENTITIES-007.md

## Fichiers modifiés

- forge_design/forge/source.py : politique Entity et ancrage renforcé de racine.
- forge_design/web/source.py : helper lexical et contexte issu du chemin validé.
- forge_design/web/entities.py : helpers injectés dans le rendu.
- forge_design/web/templates/entities.html : liens des sources textuelles.
- forge_design/web/templates/source.html : retour contextuel.
- tests/test_entity_explorer.py : attente de liens désormais présents.
- tests/test_entity_relations.py : attente de liens désormais présents.
- tests/test_web_entity_diagnostics.py : attente de liens désormais présents.
- docs/tools/entity-explorer.md : navigation et périmètre.
- docs/02-architecture.md : politique des quatre espaces et confinement.

## Tests ajoutés

66 nouveaux cas : 51 unitaires et 15 HTTP.
Unitaires : quatre chemins autorisés, 36 refus lexicaux, six niveaux de symlinks,
quatre fichiers refusés (FIFO inclus) et helper/encodage URL sans filesystem.
Lecture brute UTF-8/BOM et JSON invalide, absence de parsing/exécution et non-écriture.

HTTP : treize scénarios source (entités, relations, JSON invalide, absence, chemins
interdits/encodés et trois espaces historiques), retours/navigation, numéros de
ligne, message hors fichier, no-store, POST refusé et non-écriture.
Deux scénarios supplémentaires suivent les liens d’entités/relations/diagnostics,
y compris après invalidation d’un JSON et depuis une vue filtrée, puis vérifient
les sources synthétiques hostiles, absentes ou non navigables, sans line artificiel.

Trois assertions historiques d’absence de lien sont adaptées à la fonctionnalité.
Aucun test historique désactivé ni assertion de sécurité supprimée.

## Test réel

Copie temporaire de ../Forge/skeleton/data avec Article et Tag créés par le
constructeur canonique Forge et une relation Article → Tag dans relations.json.
Installation wheel --no-deps --no-index --target ; processus Python -I avec
origine installée du serveur et de web/source.py vérifiée.

GET /entities, extraction des trois chemins via parsing HTML, suivi de chaque
lien : 200, texte JSON visible, numéros de lignes et retour Entity Explorer.
Article est ensuite remplacé volontairement par `{`. La page filtrée q=article
produit entity.json_invalid ; son lien ouvre le texte brut avec ligne 1.
Traversal article/../relations.json : 400 et navigation neutre. Une source route
conserve son retour Route Explorer, et GET /routes reste fonctionnel.
Comparaison projet/configuration autour de chaque GET : aucune écriture.
Serveur arrêté, thread terminé, socket fermé et port réutilisable. Dépôt Forge intact.
Script et journal ignorés : tmp/verify_fd_entities_007.py et .log.

## Packaging

Wheel reconstruite : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `3e5f8095cac3a787cce96a272e4b38196df3a66f383f1997dfe1f0fa198a1810`.
Archive inspectée : forge/source.py, web/source.py, templates source/entities,
CSS et JS présents, identiques aux sources ; aucun tests/ ou tmp/ distribué.
Installation réelle et scénario HTTP réussis. Aucune dépendance ajoutée.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| git status ; git log --oneline --decorate -5 | Baseline conforme |
| pytest -q --tb=short | 845 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check forge_design/web/static/entity-graph.js | Succès |
| node --check forge_design/web/static/route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Installation wheel et scénario réel HTTP | Succès |

Outils .venv, Python 3.13.5, Node disponible. Tests et scénario HTTP hors sandbox
pour les sockets ; build isolé hors sandbox pour ses dépendances. Première suite :
quatre échecs du garde __import__ qui bloquait monkeypatch lui-même ; garde corrigé,
51 tests unitaires puis suite complète réussis. Aucun échec produit restant.
Journal de suite ignoré : tmp/pytest_fd_entities_007.log.
Diff complet, nouveaux fichiers et rapport relus avant commit.

## Tests sautés

Aucun test pytest sauté, y compris FIFO et suites Node historiques.
Aucun test navigateur ou lecteur d’écran réel revendiqué ; contrôle HTTP/HTML.

## Limites restantes

La navigabilité est lexicale ; le fichier peut disparaître ou être remplacé avant
ou pendant lecture. Le confinement et les contrôles du descripteur ne promettent
pas un instantané atomique du contenu. Primitives POSIX requises, pas de repli faible.
Les filtres ne sont pas conservés au retour. Aucune ligne JSON fiable n’est calculée.
/source reste une politique de chemins autorisés, pas une liste d’instantané :
un chemin saisi manuellement respectant strictement la politique reste consultable.

## État Git final

Un seul commit local sur main, rapport inclus, sans push conformément au ticket.
Message : `feat: ouvrir les sources Entity Explorer (FD-ENTITIES-007)`.
Le hash et l’état Git final sont communiqués dans la réponse de livraison.
