# Rapport — FD-DESIGN-004

## Ticket et objectif

Lire un design confiné à mvc/views, valider JSON/Pydantic/imbrication et sauvegarder
explicitement le seul .design.json avec révision et publication atomique.
Aucun template généré ou modifié, aucun inventaire, Web ou nouveau Tool.

## État Git initial

main synchronisée avec origin/main à `f37f809` — FD-DESIGN-003.
Git status et dix derniers commits inspectés. La modification utilisateur de
FD-CONTRACT-001.md (« État Git initiala ») est conservée exactement hors commit.
Aucun AGENTS.md trouvé. Baseline : 2039 tests.

## Baseline Forge

Vérification distante en lecture seule : git -C ../Forge ls-remote origin
refs/heads/main retourne `73a956e587e5f169c028415e0e540c149cbaff56`, baseline attendue.
Aucun fetch, checkout ou changement Forge Core. Dépôt Forge resté propre.
Les écritures du scénario installé concernent une copie temporaire du squelette.

## Convention de chemin

Chemin relatif à mvc/views, suffixe exact .design.json et stem non vide.
design.json, .design.json, variantes de casse, suffixes .bak et préfixe mvc/views
refusés. design_source réutilise template_source/source_parts ; pas de copie des
listes de noms sensibles. Refus avant ouverture des traversées, absolus, segments
cachés, antislash, deux-points, NUL et noms sensibles. Espaces/Unicode admis selon
la politique commune. Les parents doivent déjà exister.

## API de lecture

read_design(root, design_path) → DesignReadResult gelé : path, size, modified_ns,
revision, design et tuple issues. Racine résolue et reconnue avec les fonctions
projet existantes. Absence : FileNotFoundError ; refus lexical : SourceReadError ;
projet invalide : exceptions projet historiques. Échec de lecture sûre : issue
design.unreadable avec métadonnées None. Aucun import ou exécution du projet.

## Révision

DesignRevision gelée : size, modified_ns, digest SHA-256, device, inode et changed_ns.
Les champs d'identité/ctime complètent le minimum demandé pour détecter un
remplacement à contenu et mtime identiques. Le digest provient des octets réellement
lus, BOM compris, sans deuxième ouverture dédiée. Métadonnées conservées après
lecture sûre même si UTF-8, syntaxe JSON ou validation échouent.

## JSON strict

Extraction neutre de loads_strict_json dans forge_design/json_strict.py. Les hooks
existants des contrats sont conservés : refus doublons et NaN/Infinity/-Infinity.
UTF-8 avec BOM initial accepté, commentaires et virgules finales refusés.
ValueError/RecursionError deviennent design.json_invalid ; UTF-8 invalide devient
design.unreadable. Le JSON reste décodé intégralement dans la borne de 1 Mio.

## Validation Pydantic

DesignFile.model_validate après parsing strict. Échec : design=None et diagnostics
design.validation_error avec locations Pydantic. Diagnostics plafonnés à
MAX_DESIGN_ISSUES, dernier slot réservé au marqueur en cas de surplus.
Aucun input brut ou message détaillé Pydantic exposé dans les diagnostics.

## Validation d’imbrication

Exécutée après validation structurelle. DesignFile conservé si nesting invalide.
Conversion en design.nesting_error avec path fichier, location du nœud, parent_type
et child_type. Troncature propagée comme design.analysis_truncated. Aucun arbre
tronqué présenté comme valide. Matrice historique inchangée, dont page → table.

## API d’écriture

write_design(root, design_path, design, *, expected_revision) → DesignWriteResult
gelé : path, created, size, modified_ns et revision. Paramètre de révision explicite
obligatoire. Exceptions publiques : DesignWriteError, DesignWriteConflictError,
InvalidDesignForWriteError (avec issues). Refus lexical via SourceReadError.
Aucune option force/overwrite et aucun helper de scan.

## Revalidation avant sauvegarde

model_dump(exclude_unset=True), puis DesignFile.model_validate sur les données
sérialisées, puis nesting. Mutations internes invalides, clé props vide, NaN,
cycle, nesting invalide/tronqué et taille excessive refusés avant I/O d'écriture.
Aucun model_construct, déplacement, suppression ou réparation automatique.

## Sérialisation

JSON lisible déterministe : ensure_ascii=False, indent=2, allow_nan=False,
pas de sort_keys, UTF-8 sans BOM, un newline final. Ordre conceptuel des modèles.
Octets encodés calculés avant ouverture de la cible, plafond MAX_SOURCE_BYTES=1 Mio.
Aucune métadonnée runtime, date ou empreinte ajoutée au document.

## Contrôle de concurrence

Précontrôle avant temporaire, puis nouveau contrôle après préparation/fsync,
juste avant publication. Égalité de tous les champs de DesignRevision exigée.
Tests : création existante, modification externe, mtime seul, mêmes taille/mtime
mais octets différents, disparition, symlink et remplacement d'inode. Les octets
externes sont conservés dans ces conflits. Modification après préparation du
temporaire détectée par le dernier contrôle.

## Création

expected_revision=None signifie cible absente uniquement. Publication via
os.link(temp, cible) avec dirfds et follow_symlinks=False, puis unlink(temp).
Ce choix POSIX fournit une création atomique sans écrasement, même si une cible
apparaît entre contrôle et publication ; os.replace seul ne le garantirait pas.
Course simulée avec un créateur concurrent : conflit, son fichier reste intact.

## Mise à jour

La révision courante est obtenue par stat/open sans liens/fstat/samestat et lecture
bornée, puis comparaison. Le nom est recontrôlé après lecture. Disparition, cible
non régulière, lien ou révision différente donnent un conflit. Le remplacement
par os.replace est suivi de fsync(directory) et d'une relecture sûre de la cible.
La révision retournée correspond aux octets finaux observés, pas au temporaire.

## Écriture atomique

Temporaire .forge-design-write-<128 bits aléatoires> dans le même dossier, créé par
O_CREAT|O_EXCL|O_NOFOLLOW|O_NONBLOCK. Écriture via os.write avec gestion des écritures
partielles et refus d'un retour zéro. Fermeture garantie, fsync avant publication,
contrôle d'identité du temporaire. Nettoyage dans finally après succès/erreur.
Collision avec un symlink préexistant : refus, sans le suivre ni le supprimer.

Échecs write/fsync(temp)/replace testés : ancienne cible intacte, aucun temporaire
créé par l'appel résiduel. Échec fsync(directory) après publication : erreur
contrôlée, nouvelle cible possiblement déjà présente. Pas de rollback prétendu ;
relecture requise avant toute nouvelle tentative.

## Permissions

Création 0o666 soumis à l'umask. Mise à jour : bits existing_mode & 0o777 appliqués
au temporaire avant fsync ; test de conservation 0o640. Pas de promesse concernant
ACL, xattrs, propriétaire particulier ou liens physiques. Test hard link : les
autres noms conservent l'ancien inode et ses octets après remplacement de la cible.

## Races résiduelles

Pas de verrou interprocessus ni de compare-and-swap filesystem. Une course résiduelle
subsiste entre le dernier contrôle et replace ; un acteur concurrent peut modifier
ou remplacer la cible dans cet intervalle. Même limite autour du nom temporaire
si un acteur a les droits d'écriture sur le dossier. Les contrôles réduisent la
fenêtre sans fournir une transaction globale. Un dossier ouvert peut être renommé.
Après publication, une erreur de fsync/relecture/nettoyage ne garantit pas l'absence
d'effet. Crash ou refus de nettoyage peuvent laisser un temporaire.

## Sécurité filesystem

Politique source commune ; racine canonique puis parents ouverts segment par segment
avec O_NOFOLLOW. Pas de dossier créé. Cibles symlink/FIFO/socket/dossier et fichiers
supérieurs à la borne refusés. Lecture contrôlée size/mtime/ctime/longueur après
lecture ; mutation simulée détectée. POSIX sécurisé requis, refus contrôlé si les
primitives d'écriture sont absentes, aucun fallback Path.write_text.

read_project_source_bytes et read_source_bytes extraient la lecture brute commune.
SourceContent, inspect_project_source et read_project_source_details conservent
leurs signatures/résultats historiques. Descripteurs fermés ; /proc/self/fd stable
sur lecture, création, update, conflit et erreur.

## Non-impact template/contrat

Sentinelles HTML et .view.json comparées en octets et mtime après création/update/
conflit. Le contenu du contrat sentinelle n'a pas besoin d'être un contrat valide :
aucune résolution de source_contract ni liaison contractuelle n'est effectuée.

## Non-exécution

Projet hostile de test : app.py, config.py et contrôleur lèvent à l'import.
Le cycle read/write réussit sans importer ces fichiers. Aucun subprocess Forge,
Jinja, DB, SQL, binding évalué ou template généré dans le produit.

## Non-écriture hors design

Pas de préférence XDG, historique, backup ou création de parent. Traversées refusées
sans fichier extérieur créé. Scénario installé : tous les fichiers projet
préexistants sont comparés en octets et mtime, seules les deux nouvelles cibles
design sont permises. Configuration XDG sentinelle inchangée.

## Round-trip

Fixtures minimal et contacts-list : modèle → création → lecture → payload identique.
Nouvelle sauvegarde du même modèle : mêmes octets. Modification du champ view puis
update avec révision et relecture : nouveau modèle et nouvelle révision cohérents.
Les fichiers officiels du dépôt ne sont jamais réécrits.

## Compatibilité Design 001–003

Schéma, models.py, nesting.py et fixtures inchangés. Tous les tests précédents
actifs. Cinq Tools inchangés ; aucune modification Web, JavaScript, app.py ou limits.py.

## Compatibilité Contracts

Seule extraction des hooks JSON et remplacement de json.loads par loads_strict_json.
Mêmes règles et diagnostics, aucun changement d'inventaire, modèle ou liaison.
Suite complète et tests ciblés Source Viewer/Contracts réussis.

## Fichiers créés

- forge_design/design/io.py
- forge_design/json_strict.py
- tests/test_design_io.py
- tests/test_json_strict.py
- docs/rapports/FD-DESIGN-004.md

## Fichiers modifiés

- forge_design/design/__init__.py : exports publics et description du package.
- forge_design/forge/source.py : extraction de lecture brute commune.
- forge_design/contracts/reader.py : parseur strict partagé uniquement.
- docs/design/design-json.md : API, sauvegarde et limites.
- docs/02-architecture.md : pipeline I/O explicite.

FD-CONTRACT-001.md reste un diff utilisateur hors ticket.

## Tests ajoutés

78 nouveaux cas : 70 I/O et 8 JSON strict. Fixtures, Unicode/BOM, syntaxe/encoding,
metadata/hash, Pydantic et nesting avec locations/troncature, chemins refusés,
projet/absence, symlinks/parents/spéciaux, taille, mutations internes, conflits,
modes/hard links, collision temp, mutation pendant lecture, contrôle tardif,
publication exclusive concurrente, écritures partielles/zéro, pannes et descripteurs.
Comparaisons explicites templates/contrats/XDG et refus avant I/O d'un modèle invalide.

## Test réel

Copie temporaire de ../Forge/skeleton/data. Wheel installée --no-deps --no-index
--target, processus Python -I vérifiant la provenance de design et design.io.
Schéma installé comparé via importlib.resources. Fixtures lues depuis le dépôt de
test, non distribuées. Pour chaque fixture : création, lecture, modification en
mémoire, update, relecture, modification externe puis conflit avec ancienne révision.
Tous les fichiers préexistants et XDG restent identiques en octets/mtime. Aucun
temporaire résiduel. Seuls minimal.design.json et contacts/list.design.json ajoutés.
Script/journal ignorés : tmp/verify_fd_design_004.py et .log.

## Packaging

Wheel : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : `e89e35b42e5ff8b53a5e9f8fa9238367e85bdf2fa3a8e5c90d459f544cebc8f9`.
Archive inspectée : design/__init__, models, nesting, io, schéma, json_strict,
source et lecteur contracts identiques aux sources. Aucun tests/ ou tmp/ distribué.
Requires-Dist inchangés, aucune dépendance nouvelle ni modification pyproject.toml.
Installation et scénario réel réussis.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat |
|---|---|
| git status ; git log --oneline --decorate -10 | Baseline et diff utilisateur vérifiés |
| git -C ../Forge ls-remote origin refs/heads/main | Baseline Forge identique |
| pytest ciblé Design 001–004 + JSON strict | 458 réussis |
| pytest -q --tb=short | 2117 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| python -m pip --no-cache-dir check | No broken requirements found |
| git diff --check | Succès |
| node --check entity-graph.js et route-graph.js | Succès |
| python -m pip wheel --no-deps --wheel-dir tmp/wheels . | Succès |
| Installation temporaire et scénario Python -I | Succès |

Outils .venv, Python 3.13.5. Premier test socket en sandbox refusé ; exécution
ciblée et complète hors sandbox réussie. Build isolé hors sandbox pour les dépendances.
Un lambda de test a été remplacé par une fonction typée après pyright. Journal
complet : tmp/pytest_fd_design_004.log. Diff et nouveaux fichiers relus avant commit.

## Tests sautés

Aucun test pytest sauté ; /proc/self/fd disponible. mkdocs build --strict non
applicable : aucune configuration MkDocs dans ForgeDesign. Aucun test navigateur
requis pour ce module sans interface HTTP.

## Limites restantes

POSIX avec dirfd, liens physiques et fsync requis. Pas de transaction interprocessus,
verrou, protection totale contre un adversaire concurrent ou garantie de rollback
après publication. Le remplacement change l'inode, sans préservation ACL/xattrs/
propriétaire/hard links. Parsing complet sous 1 Mio et sérialisation complète en
mémoire avant contrôle de taille. Pas d'inventaire, génération, binding, historique,
UI ou nouvelle route. Limites Pydantic/nesting historiques conservées.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : `feat: lire et sauvegarder les designs (FD-DESIGN-004)`.
Modification utilisateur FD-CONTRACT-001 préservée hors commit ; dépôt Forge Core
inchangé. Hash et état final communiqués dans la réponse de livraison.
