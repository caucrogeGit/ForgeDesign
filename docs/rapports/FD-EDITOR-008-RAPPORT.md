# FD-EDITOR-008 — Sérialisation des mutations concurrentes de designs

Date : 15 octobre 2026.
Statut : implémenté et qualifié dans le périmètre Linux local mono-hôte, ext4 et tmpfs.
Ce verdict ne vaut pas acceptation de FD-ACCEPTANCE-001 ni qualification d’ACC-003.

## Objectif et résultat

Les mutations Web et l’API publique `write_design` utilisent désormais la même
coordination interprocessus par design.
La lecture décisionnelle Web, la comparaison de révision, l’action et la
publication sont effectuées sous le même verrou noyau.
L’API publique conserve sa signature et revalide `expected_revision` sous ce verrou.

Les 600 courses qualifiées donnent chacune une seule réussite et un conflit de
révision pour l’autre exécutant, sans sauvegarde incertaine due à cette course.
Les deux actions concurrentes produisent des contenus distincts, ce qui permet de
détecter une seconde publication que des octets identiques auraient pu masquer.

## État Git et périmètre

Le travail a commencé sur `main`, HEAD `561ff93`, après FD-EDITOR-007.
L’état initial contenait la modification utilisateur de `FD-CONTRACT-001.md` et
les preuves complémentaires non suivies de FD-EDITOR-007 ; ils sont préservés.
Les [empreintes de préservation](fd-editor-008/preservation.json) sont archivées.

Une autre session a modifié puis committé la preview réelle pendant ce travail,
produisant `8ca9b72` (FD-REALPREVIEW-007).
Ce commit n’a pas été effectué dans FD-EDITOR-008.
Les modifications concomitantes ont été conservées.
Une copie figée de `561ff93` avec uniquement les changements FD-EDITOR-008 a servi
à la qualification isolée, puis la suite entière a aussi été exécutée sur l’arbre
courant incluant `8ca9b72` et le correctif non committé.
Les [empreintes qualifiées](fd-editor-008/qualified-files.json) identifient cette copie.

Aucun commit, push, installation, publication ou déploiement effectué pour ce ticket.
Aucun changement dans Forge IoT, SéquenCiel ou les modules Circuit/Flowchart.
Aucune nouvelle dépendance ni migration.

## Reproduction préalable

Les deux tests préalables ont été écrits et exécutés avant modification du code.
Ils imposent des entrelacements permis par l’ancienne implémentation, sans injecter
d’erreur disque.

| Cas | Observation avant correction | Preuve |
|---|---|---|
| Deux threads WSGI | `303 / 500`, sauvegarde incertaine | [Journal](fd-editor-008/preflight.txt) |
| Deux processus Python indépendants, démarrés par `spawn` | une réussite, une sauvegarde incertaine | [Journal](fd-editor-008/process-preflight.txt) |

Les assertions exigeant une réussite et un conflit échouaient, comme attendu.
Les scripts préalables sont archivés avec les journaux ; ils ciblent l’ancienne
fenêtre interne et ne constituent pas les tests à rejouer sur le writer sérialisé.
Les tests de régression finaux synchronisent les concurrents avant acquisition,
puis vérifient leurs résultats sans exiger qu’ils entrent ensemble dans une
section devenue exclusive.

## Mise en œuvre des décisions A à D

### Coordination commune

`forge_design/design/locking.py` porte le protocole Linux `flock`.
`design_mutation` dans la couche I/O fournit le contexte interne commun.
Le writer public entoure son moteur privé de ce contexte ; le Web ouvre le
contexte avant sa lecture décisionnelle et le conserve jusqu’au résultat.

Chaque occupation indépendante ouvre son propre descripteur.
Le contexte de mutation courant peut être réutilisé uniquement par son thread et
son processus propriétaires, pour le même projet canonique et le même design.
Cette réutilisation évite un deuxième `flock` concurrent du même thread lorsque
le Web appelle le writer public.
Le `ContextVar` porte cette occupation temporaire ; il ne remplace pas le verrou
interprocessus et est réinitialisé à la sortie.
Un petit verrou Python protège uniquement la liste de descripteurs pendant fork.

Le projet courant est capturé pour la requête, afin qu’une sélection simultanée
d’un autre projet ne change pas la cible entre lecture et publication.
Les sondes vérifient qu’un second descripteur ne peut prendre le verrou pendant
chacune des étapes lecture, comparaison, action et `os.replace`.
Un test de requête en attente vérifie que sa révision est relue après acquisition.
Deux designs différents peuvent progresser indépendamment.

### Verrous stables et sûrs

Le nom est `.forge-design/locks/design-<sha256-du-chemin-relatif>.lock`.
Il ne dépend pas de l’inode du design, remplacé par la sauvegarde atomique.
Le fichier de verrou reste présent et n’est ni tronqué ni supprimé automatiquement.
Sa présence seule ne signifie pas qu’il est occupé.
Un fichier est conservé par cible logique ayant nécessité cette coordination.

Les ouvertures sont ancrées par descripteurs, avec refus des symlinks.
Le propriétaire, les permissions, le type régulier, le nombre de liens physiques
et l’identité fichier/répertoire sont contrôlés.
`locks` est privé (0700), les fichiers sont privés (0600), soumis à l’umask.
Le répertoire `.forge-design` préexistant peut être lisible, mais pas inscriptible
par le groupe ou les autres utilisateurs.
Aucune permission préexistante n’est réparée silencieusement.
Les GET et la preview réelle ne créent aucun verrou.

Les descripteurs sont fermés sur exception ou mort du détenteur.
`O_CLOEXEC` empêche leur héritage après exec ; le callback fork ferme les copies
dans l’enfant sans effectuer `LOCK_UN`, pour préserver l’occupation du parent.
Les tests gardent volontairement l’enfant vivant pour vérifier qu’il ne prolonge
pas le verrou du parent.

### Réponses et état disque

| Situation | Comportement qualifié |
|---|---|
| Révision obsolète constatée sous verrou | HTTP 409, aucune mutation de cette requête |
| Conflit Web ou précondition I/O | design courant rendu, sélection racine, lien de rechargement, `no-store` |
| Attente atteignant cinq secondes | HTTP 503 avant action, aucun retry automatique |
| Verrou ou garantie invérifiable | HTTP 503 avant action |
| Publication potentiellement réalisée, résultat incertain | HTTP 500, invitation à relire, aucun faux rollback |

L’échéance repose sur une horloge monotone et des acquisitions non bloquantes.
Une acquisition obtenue à l’échéance est elle-même refusée et son descripteur fermé.
Le délai réel a été vérifié, ainsi que sa borne avec une horloge injectée.
Un timeout ne prouve pas l’obsolescence de la révision et n’est pas déguisé en 409.

Le writer conserve la création exclusive par `link`, la mise à jour atomique par
`replace`, la gestion des écritures partielles et les fsync du temporaire et du
répertoire.
La sérialisation du JSON et les comparaisons de révision sont inchangées.
Une divergence observée après publication est désormais une erreur de sauvegarde
incertaine, et non un conflit promettant abusivement une absence d’écriture.
Les pannes de fsync avant et après publication et la modification externe après
publication vérifient cette distinction et la validité du fichier restant.

### Montage du projet cible

La vérification part des descripteurs réels du projet, des répertoires, du design
existant et des métadonnées de verrou.
Le `mnt_id` de `/proc/self/fdinfo/<fd>` est rapproché de `/proc/self/mountinfo`.
Les sous-montages et fichiers montés séparément sont contrôlés ; le type de
stockage du dépôt source n’est jamais utilisé comme autorisation pour la cible.
La vérification est répétée après acquisition et lors de la participation du writer.

Seuls Linux et les types ext4/tmpfs sont acceptés.
Un type non qualifié, des informations noyau indisponibles, un verrou noyau
indisponible ou des métadonnées non sûres provoquent un refus explicite.
La qualification vérifie le type réel de chaque projet temporaire.

## Résultats effectifs

| Vérification | Résultat |
|---|---|
| Suite Python complète isolée, base `561ff93` + FD-EDITOR-008 | **5 131 réussis**, 0 échec, 0 sauté ; 159,45 s |
| Suite Python complète sur l’arbre courant avec `8ca9b72` | **5 136 réussis**, 0 échec, 0 sauté ; 151,90 s |
| Courses finales répétées | **600 réussies**, 0 échec, 0 sauté ; 237,68 s |
| Pannes/refus/héritage, ext4 | **27 réussis**, 0 échec, 0 sauté ; 7,80 s |
| Pannes/refus/héritage, tmpfs | **27 réussis**, 0 échec, 0 sauté ; 7,82 s |
| Chromium, parcours éditeur | 2 étapes réussies |
| Firefox, parcours éditeur | 2 étapes réussies |
| Firefox sans JavaScript, parcours éditeur | 2 étapes réussies |
| Ruff, formatage Python, Pyright strict | réussis, 0 erreur de typage |
| Tests JavaScript exécutés | 16 réussis, 0 échec, 0 sauté |
| Compilation Python, syntaxe JavaScript et shell, `git diff --check` | réussis |

Les deux suites Python ne sont pas additionnées : ce sont deux vérifications
sur des bases explicitement distinctes.
Les 27 tests de panne ont été rejoués sur les deux stockages après généralisation
de l’injection de montage non qualifié ; aucun code fonctionnel n’a changé.
Les [journaux](fd-editor-008/) et les résultats JUnit compressés conservent les
preuves et leurs nombres effectifs.

### Matrice des courses

| Stockage | Exécution | Web/Web | API/API | Web/API |
|---|---|---:|---:|---:|
| ext4 | threads | 50 | 50 | 50 |
| ext4 | processus indépendants | 50 | 50 | 50 |
| tmpfs | threads | 50 | 50 | 50 |
| tmpfs | processus indépendants | 50 | 50 | 50 |

Chaque processus est créé par `spawn`, charge sa propre application ou appelle
l’API publique, et les PID sont vérifiés distincts.
Les barrières garantissent que les deux exécutants ont la même révision initiale.
Les réponses Web sont réellement servies par HTTP ; les exécutants possèdent
des serveurs distincts afin que le serveur mono-thread ne masque pas la course.
Une erreur ou un 500 inattendu fait échouer le test, sans retry pour le cacher.
Le [résumé extrait du JUnit](fd-editor-008/race-summary.json) vérifie les douze
cellules à 50 succès chacune.

## Prémortem et preuves

| Risque | Preuve réalisée |
|---|---|
| Double passage sur la même révision | 600 courses, contenus concurrents distincts, une seule réussite |
| Verrou acquis trop tard | sondes sous verrou et requête en attente relisant après acquisition |
| Coordination seulement Python | processus indépendants et conflits Web/API |
| Fuite de verrou sur exception | RuntimeError, KeyboardInterrupt, pannes I/O puis nouvelle sauvegarde |
| Blocage ou acquisition tardive | délai réel de cinq secondes, test à l’échéance, refus 503 |
| Héritage conservant une occupation | enfant fork ou exec maintenu vivant, nouvelle acquisition réussie |
| Détenteur tué | arrêt brutal avant/après sauvegarde, nouvelle acquisition réussie |
| Publication incertaine masquée | injections avant/après fsync et après modification externe, 500 honnête |
| Mauvais stockage vérifié | descripteur de la cible, refus d’un type non qualifié/invérifiable |
| Régression ACC-004/modules | régression complète, trois vecteurs, onze formulaires et navigateurs |

## Préservation et adaptations des tests

`DesignFile`, `NodePath`, le schéma `.design.json`, les jetons modules et le
contenu des onze formulaires restent identiques.
L’AST de la signature publique `write_design` et des fonctions `_payload`,
`_revision`, `_current`, `_check` est comparé au socle initial.
Les contrôles Host/Origin et de format de formulaire restent actifs ; le shell
local n’acquiert pas un nouveau mécanisme d’authentification ou de session.

Les tests qui interdisaient toute présence de `.forge-design` vérifient désormais
exactement le répertoire `locks`, un fichier de verrou vide attendu, et l’absence
d’historique ; leurs assertions sur les templates et sentinelles sont conservées.
Le test de course historique n’accepte plus 303/303 ni 303/500 : il exige 303/409.
La barrière est déplacée avant l’entrée WSGI pour ne pas attendre deux détenteurs
dans la section exclusive.
Le kit d’acceptation autorise uniquement le chemin précis du verrou de sa fixture,
pas un joker sur toutes les métadonnées.

## Limites résiduelles

- La garantie concerne les écrivains participants, sur un même hôte Linux.
  [`flock` reste consultatif](https://man7.org/linux/man-pages/man2/flock.2.html) : un outil externe ignorant ce protocole ou supprimant
  ses fichiers de verrou n’est pas sérialisé par Forge Design.
- ext4 a été qualifié sur le stockage local de ce poste ; tmpfs est volatil et ne
  conserve pas les données après redémarrage. Les fsync sont conservés, mais aucun
  essai matériel de coupure électrique ni certification de contrôleur disque
  n’est revendiqué.
- Aucun stockage réseau, multi-hôtes, autre OS ou autre type de filesystem n’est
  déclaré pris en charge. Le fonctionnement dépend aussi de `/proc` vérifiable.
- L’attente d’acquisition est bornée. Cela ne constitue pas une borne de temps
  générale sur les opérations disque en cas de panne matérielle du noyau.
- Les fichiers de verrou sont conservés. Aucun nettoyage en ligne ni suppression
  par ancienneté n’est ajouté ; leur suppression pendant une activité serait dangereuse.
- Les tests navigateur utilisent les sources figées, sans installation de roue.
  Aucune acceptance globale, preview réelle ou publication n’a été ajoutée à ce ticket.

## Rejouer

Depuis le dépôt avec son environnement existant :

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
FD_EDITOR_008_TRIALS=50 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_design_concurrency.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider --basetemp=/tmp/fd-editor-008-faults-tmpfs tests/test_design_locking.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider --basetemp=tmp/fd-editor-008-faults-ext4 tests/test_design_locking.py
.venv/bin/ruff check --no-cache forge_design tests
.venv/bin/ruff format --check --no-cache forge_design tests
.venv/bin/pyright
node --check scripts/acceptance/scenario.mjs
node --check scripts/acceptance/nojs.mjs
bash -n scripts/acceptance/run.sh
git diff --check
```

Le dépôt doit résider sur ext4 pour la commande ext4 ci-dessus ; sinon fournir
`FD_EDITOR_008_EXT4_ROOT` vers un répertoire jetable effectivement sur ext4 pour
les courses, et adapter `--basetemp` pour les pannes.
Le test refuse un type de montage différent au lieu de le qualifier implicitement.
Les répertoires `--basetemp` sont réservés à pytest, qui peut les recréer.
Le lanceur de [navigateurs utilisé](fd-editor-008/final-browsers.py), le script de
construction de la copie figée et les empreintes sont joints aux preuves.

## Fichiers du ticket

- `forge_design/design/locking.py` — nouveau protocole de coordination.
- `forge_design/design/io.py` — participation du writer, erreur de verrou et distinction après publication.
- `forge_design/web/editor.py` — contexte couvrant la mutation et réponses 409/503/500.
- `tests/test_design_locking.py`, `tests/test_design_concurrency.py` — pannes et concurrence.
- `tests/test_design_io.py`, `tests/test_web_editor.py`, `tests/test_web_editor_revision.py` — assertions historiques adaptées et renforcées.
- `scripts/acceptance/run.sh` — unique chemin de verrou autorisé pour la fixture.
- `docs/design/design-json.md`, `docs/editor/structural-editor.md` — contrat réel et limites.
- Ce rapport et `docs/rapports/fd-editor-008/` — preuves.

Verdict conditionnel : FD-EDITOR-008 satisfait le contrat validé pour les écrivains
participants, sur ext4/tmpfs locaux, dans un seul hôte Linux.
FD-ACCEPTANCE-001 et ACC-003 restent des jalons distincts.
