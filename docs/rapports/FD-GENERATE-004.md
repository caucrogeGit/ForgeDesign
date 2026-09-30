# Rapport — FD-GENERATE-004

## Ticket et objectif

Comparer en mémoire contenu actuel et contenu généré, avec unified diff,
métriques sémantiques, cible et origine. Aucune lecture automatique, écriture,
confirmation, UI, historique ou gestion de conflit.

## État Git initial

main synchronisée avec origin/main à 677791c — FD-GENERATE-003.
État réel et cinq derniers commits inspectés. Modification utilisateur existante :
docs/rapports/FD-CONTRACT-001.md (« État Git initiala »), préservée hors commit.
Aucun AGENTS.md trouvé dans le dépôt.

## Sources fonctionnelles

Ticket FD-GENERATE-004, exports et limites existants du package generate.
Bibliothèque standard difflib : unified_diff pour la présentation,
SequenceMatcher pour les métriques. Aucun modèle Design/Contract consulté
par le nouveau service.

## API publique

build_template_diff(*, target, current, generated, origin) → TemplateDiffResult.
Dataclass gelée contenant target, origin, current, generated, unified_diff,
changed, added_lines, removed_lines, modified_lines, issues et complete.
TemplateDiffIssue(code, message) gelée ; issues est un tuple.
Les trois symboles sont exportés depuis forge_design.generate.

## Unified diff

En-têtes --- target et +++ target.generated, sans timestamp ; contexte standard
de trois lignes. Lignes de contenu fournies par splitlines(keepends=True).
Contenus identiques : retour immédiat, changed=False, diff vide, compteurs zéro.
Current vide représente un ajout, generated vide une suppression.
Aucun parsing ou exécution HTML/Jinja, aucun ANSI ajouté.

## Cible

Chaîne descriptive non vide, conservée exactement. Aucun resolve, absolute,
exists, stat ou ouverture. Traversal descriptif accepté sans prétendre à une
validation filesystem. Chaîne vide ou valeur non string : ValueError.
Les en-têtes utilisent la cible fournie ; aucune normalisation de chemin.

## Origine

Obligatoire, string non vide ; conservation exacte sans strip ou valeur inventée.
Présente dans le résultat seulement, absente des en-têtes du diff.
Métadonnée invalide : ValueError, y compris lorsque les contenus sont identiques.

## Métriques

Calcul séparé avant construction du diff, depuis les opcodes de SequenceMatcher
sur splitlines() sans séparateurs. Comportement standard autojunk conservé.
Les préfixes de lignes et en-têtes du texte unifié n'interviennent pas.
Les métriques restent disponibles même si la sortie dépasse la borne.

## Lignes ajoutées

Insert : nombre de lignes nouvelles. Replace : seules les lignes nouvelles
excédant les lignes appariées comptent comme ajoutées.
Nouveau contenu à partir de current="" testé.

## Lignes supprimées

Delete : nombre de lignes anciennes. Replace : seules les lignes anciennes
excédant les lignes appariées comptent comme supprimées.
Suppression totale vers generated="" testée.

## Lignes modifiées

Pour chaque replace : min(nombre ancien, nombre nouveau).
1→1 donne une modification sans ajout/suppression ; 1→3 ajoute deux lignes en plus ;
3→1 supprime deux lignes en plus. Les blocs d'insertion/suppression indépendants
ne sont pas fusionnés en modifications.

## Fins de ligne

Current et generated gardent exactement leurs caractères.
CRLF préservés dans les lignes du diff. Ligne produite sans LF :
LF de présentation suivi du marqueur standard « \ No newline at end of file ».
Ainsi deux lignes sans LF ne sont pas collées dans le diff.
Diff avec/sans LF final distinct, même si les métriques sans séparateurs sont zéro.
Changed reflète toujours l'inégalité exacte des chaînes, pas les compteurs.

## Taille maximale

MAX_TEMPLATE_DIFF_CHARS=1_000_000 dans limits.py. Compte les caractères du diff,
en-têtes et marqueurs compris, pas les octets UTF-8.
Accumulation incrémentale : limite exacte acceptée, surplus abandonne tous les
fragments du diff. Les deux chaînes originales, changed et métriques sont conservés.
Aucune limite ajoutée aux entrées ou à la mémoire totale de SequenceMatcher.

## Diagnostics

Un seul diagnostic métier : diff.output_too_large.
Résultat : unified_diff="", complete=False, issues tuple à un élément.
Sinon issues=() et complete=True. Métadonnées invalides traitées comme erreurs
d'appel ValueError, sans nouveau diagnostic métier.

## Déterminisme

Même contenu et mêmes métadonnées : même résultat, compteur et diff.
Aucun timestamp, UUID, hash aléatoire, couleur ou environnement externe.

## Pureté

Tests bloquant open/os.open/os.replace, Path.open/read_text/write_text/exists/
stat/resolve/absolute, socket et subprocess pendant la comparaison.
Pas d'import Forge, Web, Bridge, DB, registre, contexte ou générateur.
Les labels descriptifs ne déclenchent aucune opération filesystem.

## Non-mutation

Entrées string immuables reprises telles quelles. Pas d'état global mutable.
Résultat et diagnostic gelés vérifiés par tentative de modification.
Aucune modification du projet ciblé.

## Compatibilité GENERATE-001/002/003

simple.py, control_flow.py et tables.py inchangés.
La composition relève de l'appelant ; aucun appel automatique au générateur.
Tous les tests de génération précédents restent actifs et inchangés.
Modèles, Preview, Web, Tools, app.py, pyproject.toml et JavaScript inchangés.

## Documentation

Section Diff avant écriture ajoutée au guide : API, métriques, LF/CRLF, limites,
cible/origine, présentation future et absence d'I/O.
Architecture complétée : génération + contenu actuel → diff → future revue →
future écriture contrôlée. Aucun écran de confirmation implémenté.

## Fichiers créés

- forge_design/generate/diff.py
- tests/test_generate_diff.py
- docs/rapports/FD-GENERATE-004.md

## Fichiers modifiés

- forge_design/generate/__init__.py : exports.
- forge_design/limits.py : limite de diff.
- docs/generate/template-generation.md
- docs/02-architecture.md

Modification utilisateur FD-CONTRACT-001.md maintenue hors ticket.

## Tests ajoutés

34 cas : égalité, insert/delete, replace symétrique/asymétrique, éditions
indépendantes, nouveau fichier et suppression totale, lignes vides, LF final,
CRLF/CR, Unicode, Jinja/HTML/ANSI littéraux, préfixes ---/+++ de contenu,
en-têtes et origine, métadonnées vides ou non string, cible descriptive,
frontière exacte/surplus, entrée très longue identique, pureté et gel.
Comparaison exacte d'un diff nominal avec interpolation Jinja littérale.

## Validations ciblées

| Contrôle | Résultat |
|---|---|
| pytest -q tests/test_generate_diff.py | 34 réussis |
| pytest simple + control_flow + tables + diff | 186 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| git diff --check | Succès |

Aucun test ciblé sauté. Les tests et exports ont été formatés avant validation.
Forge Core propre et inchangé.

## Tests non exécutés

Suite globale non exécutée conformément au ticket. Pas de Node, pip check ou
wheel : structure du package inchangée, imports publics validés par les tests,
aucun problème d'import installé constaté ni fin de phase.
MkDocs strict non applicable sans configuration. Aucun affichage Web/terminal
ou application de patch testé.

## Limites restantes

Le diff sert à une revue textuelle ; il ne garantit pas l'application universelle
d'un patch sur tous les encodages/séparateurs. Les séparateurs reconnus sont ceux
de str.splitlines. L'alignement de SequenceMatcher, autojunk compris, détermine
les compteurs : ce n'est pas une analyse sémantique du template.
Le budget borne la sortie, pas le coût des entrées, listes, allocations temporaires
ou alignement, potentiellement coûteux sur certains contenus répétitifs.
Contenus et métadonnées hostiles conservés littéralement : leur affichage futur
doit respecter le contexte Web ou terminal. Aucun chemin réellement autorisé,
conflit détecté, backup ou fichier écrit par ce service.

## État Git final

Un commit local avec rapport, sans push.
Message : feat: ajouter le diff avant écriture (FD-GENERATE-004).
FD-CONTRACT-001.md hors commit ; hash et état final communiqués à la livraison.
