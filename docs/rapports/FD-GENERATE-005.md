# Rapport — FD-GENERATE-005

## Ticket et objectif

Créer l'infrastructure append-only .forge-design/history.jsonl pour tracer des
écritures déjà autorisées et réussies. Aucun template écrit par l'API, aucune
décision d'autorisation, anti-écrasement, sauvegarde ou restauration.
Clôture de la phase Generate après validations ciblées, globale et installation.

## État Git initial

main synchronisée avec origin/main à bac55a0 — FD-GENERATE-004.
État Git et cinq derniers commits inspectés. Seule modification préexistante :
docs/rapports/FD-CONTRACT-001.md, « État Git initiala », préservée hors commit.
Aucun AGENTS.md dans le dépôt.

## Sources fonctionnelles

Ticket, writer design/io.py et helper forge/filesystem.py examinés.
Réutilisation de open_directory : ouverture segment par segment de la racine,
puis dir_fd. La synchronisation des dossiers créés suit la politique de durabilité
du writer existant, sans modifier ce writer.

## Format du journal

Emplacement fixe <project>/.forge-design/history.jsonl, aucun XDG.
Objet minimal avec ordre timestamp, action, file ; aucun champ supplémentaire.
Un objet JSON compact puis un LF par événement.

## API publique

HistoryAction = Literal["generate_template"].
GenerationHistoryEvent(timestamp, action, file) est une dataclass gelée.
append_generation_history(project_root, *, action, file, timestamp=None)
retourne l'événement seulement après write et synchronisations réussis.
Les trois symboles sont exportés depuis forge_design.generate.
La sérialisation pure reste interne.

## Timestamp

Horloge réelle datetime.now(UTC) si absent. Datetime fourni obligatoire aware,
conversion UTC et isoformat terminé par Z. Microsecondes conservées si présentes.
Datetime naïf : ValueError avant I/O. Tests à heure fixe avec conversion +02:00,
microsecondes et horloge par défaut remplacée par un double déterministe.

## Chemins relatifs

File string non vide, séparateur /, segments non vides distincts de . et ...
Antislash, deux-points, contrôles ASCII et DEL refusés. Absolute POSIX, chemins
Windows, traversal et segments vides rejetés sans normalisation.
Cette validation concerne la métadonnée ; le fichier tracé n'est ni ouvert ni
consulté. Action inconnue et chemin invalide refusés avant I/O.

## Sérialisation JSONL

json.dumps ensure_ascii=False, separators=(",", ":"), allow_nan=False, puis UTF-8
sans BOM et un LF. Unicode lisible, guillemets JSON échappés. Ordre stable.
Entrée préparée intégralement avant ouverture de la racine.

## Append-only

Aucun O_TRUNC, seek(end), rename ou remplacement du journal.
Création O_EXCL si absent ; fichier existant ouvert sans O_CREAT après contrôle.
O_APPEND laisse le système choisir l'offset à chaque write. Deux événements
conservent exactement le préfixe déjà écrit. Test de vingt appends concurrents
avec quatre threads : vingt objets JSON complets et distincts.

## Sécurité filesystem

open_directory existant réutilisé pour la racine et .forge-design.
Stat sans suivi puis fstat, comparaison samestat pour dossier/journal.
Fichier régulier obligatoire à l'ouverture ; contrôle d'identité du nom avant write.
O_NONBLOCK évite le blocage sur FIFO si la cible change entre stat et open.
Pas de seconde implémentation du parcours des parents, pas de résolution préalable
qui accepterait silencieusement les liens.
Descripteurs fermés après succès et erreur ; le catch BaseException local ne fait
que fermer le descripteur puis relancer, sans convertir l'erreur en succès.

## Symlinks

Racine liée, parent de racine lié, .forge-design lié et history.jsonl lié refusés.
O_NOFOLLOW sur les segments et le journal. Sentinelle extérieure inchangée.
Remplacement contrôlé d'un dossier réel ou fichier entre stat/open détecté
par samestat, sans append dans le remplacement.

## Hardlinks

st_nlink doit valoir exactement 1. Vérification avant ouverture existante, sur
le descripteur puis sur le nom courant. Hardlink de sentinelle refusé sans écriture.
Aucune garantie contre la création hostile d'un nouveau lien après ces contrôles.

## Permissions

Création .forge-design en 0700 et history.jsonl en 0600, sous réserve d'un umask
plus restrictif. Modes existants inchangés, journal 0640 conservé dans le test.
Pas de chmod arbitraire. O_CLOEXEC utilisé si disponible ; le helper de dossier
emploie os.open, dont les descripteurs Python sont non héritables par défaut.

## Atomicité d'une entrée

Un seul os.write reçoit les octets déjà préparés de l'événement normal.
Le test instrumenté compte ce write et ses synchronisations.
Écriture courte : OSError EIO, sans retry ni append du reste. Des octets partiels
peuvent subsister ; aucun rollback ne risque de tronquer une écriture concurrente.
O_APPEND évite les offsets calculés séparément ; cela ne promet pas une atomicité
universelle sur tous les filesystems réseau.

## fsync

Fsync du fichier après write complet. Si création du journal, fsync du dossier ;
si création de .forge-design, fsync de la racine projet. Retour seulement ensuite.
Échec fsync propagé : une ligne peut exister sans succès de durabilité annoncé.
Tests d'erreur write ENOSPC, short write et fsync échoué. Aucun faux retour succès.

## Limite d'un événement

MAX_HISTORY_EVENT_BYTES=16_384 dans limits.py, octets UTF-8 et LF compris.
Limite exacte acceptée ; surplus ValueError avant I/O. Journal existant inchangé
en cas de surplus, aucun dossier créé pour une entrée initiale trop grande.
Cas Unicode confirme que le budget porte sur des octets.

## Absence de secrets

Seulement timestamp/action/file. Aucun contenu, token, cookie, mot de passe,
environnement ou digest collecté. Le nom fourni par l'appelant reste une métadonnée :
aucune analyse sémantique ou détection de secret dans son libellé.

## Relation avec Diff

diff.py inchangé. Aucun appel du journal depuis le générateur ou le diff.
Un diff consulté ou refusé n'est pas journalisé. Le scénario installé vérifie
l'absence de .forge-design avant la simulation explicite d'écriture.

## Relation avec SAFEWRITE

L'appelant futur devra d'abord obtenir l'autorisation et réussir l'écriture cible.
Le journal trace seulement ce succès déclaré, sans le vérifier ni l'autoriser.
Pas de hash before/after, mtime, inode, conflit ou révision dans l'événement.
La phase SAFEWRITE réalisera le contrôle réel d'écriture et de concurrence.

## Déterminisme structurel

Même événement et même timestamp injecté : mêmes octets JSONL.
Seule l'horloge réelle par défaut varie volontairement. Aucun ID aléatoire.

## Non-mutation

Arguments string/datetime/Path non modifiés, événement gelé.
Sentinelle template comparée octet par octet et par mtime avant/après journalisation.
Seuls .forge-design et history.jsonl sont créés par le service nominal.
Forge Core demeure propre et inchangé.

## Fichiers créés

- forge_design/generate/history.py
- tests/test_generate_history.py
- docs/rapports/FD-GENERATE-005.md

## Fichiers modifiés

- forge_design/generate/__init__.py : exports et description du package.
- forge_design/limits.py : taille maximale d'événement.
- docs/generate/template-generation.md : contrat du journal.
- docs/02-architecture.md : position après la future écriture contrôlée.

Aucune modification des générateurs, diff, Design, Contracts, Preview, Web, Tools,
app.py, pyproject.toml ou JavaScript. FD-CONTRACT-001.md hors ticket.

## Tests ajoutés

49 cas : format exact et Unicode, permissions, append successif, validation avant
I/O des chemins/actions/timestamps, horloge injectée, microsecondes, symlinks
racine/parent/dossier/fichier, FIFO/dossier/hardlink, racines invalides,
taille exacte/surplus, erreurs write/short write/fsync, un seul write et fermeture,
vingt appends concurrents, races de remplacement fichier/dossier.
Types socket/device simulés au niveau fstat pour vérifier leur rejet sans
ouvrir de device ni lancer de serveur.

## Validations ciblées

| Contrôle | Résultat |
|---|---|
| pytest history initial | 46 réussis |
| pytest simple + control_flow + tables + diff + history | 232 réussis |
| pytest history après trois contrôles de sécurité supplémentaires | 49 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| git diff --check | Succès |

Les trois derniers cas sont également inclus dans la suite globale finale.

## Validation globale de fin de phase

Suite complète exécutée une seule fois après les validations ciblées :
2659 tests réussis en 27,72 s, aucun sauté.
Python -m pip --no-cache-dir check : No broken requirements found.
Suite autorisée hors sandbox pour les sockets HTTP historiques.
Journal ignoré : tmp/pytest_fd_generate_005.log.

## Packaging

Wheel construite en fin de phase avec build isolé autorisé hors sandbox.
Artefact : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : 760f39d96d24e11303862768512ac567a5ac9de9c510c7031d4b9260474a33e2.
Archive inspectée : __init__, simple, control_flow, tables, diff, history et limits
identiques aux sources. Aucun tests/ ou tmp/ distribué.
Métadonnées runtime inchangées, aucune dépendance nouvelle.
Journal ignoré : tmp/wheel_fd_generate_005.log.

## Installation réelle

Installation temporaire --no-deps --no-index --target. Python -I vérifie l'origine
installée de forge_design.generate et importe les trois API génération/diff/history.
Contrat/Design construits en mémoire, template nominal parsé sans exécution,
diff créé depuis current vide. Aucun journal à ce stade.

Le script de scénario simule ensuite explicitement l'écriture autorisée dans
son projet temporaire, hors API produit, puis appelle append_generation_history.
Vérification des trois champs JSON, timestamp Z fixe, unique LF, unique fichier
dans .forge-design et template byte-for-byte/mtime inchangé par l'append.
Aucun writer de template livré par ce ticket.
Script/journal ignorés : tmp/verify_fd_generate_005.py et .log.

## Tests sautés

Aucun test pytest sauté. Node non relancé, aucun JavaScript concerné.
MkDocs strict non applicable faute de configuration.
Aucun navigateur, système de fichiers réseau ou crash matériel simulé.

## Limites restantes

POSIX requis pour l'ouverture sécurisée ; aucune solution de repli non sûre.
Les contrôles ne constituent pas un instantané filesystem global : répertoire
ou fichier ouvert peut être renommé/supprimé, hardlink ajouté après contrôle.
Journal existant supposé JSONL valide et terminé par LF ; aucune lecture,
réparation, rotation ou borne de taille totale.
Échec possible après création, append partiel ou append complet : aucun rollback
ni retry automatique. Un appelant ne doit pas déduire « rien écrit » de l'exception
ou rejouer aveuglément au risque de doublons. Aucun mécanisme de transaction
atomique entre une future écriture de template et son événement.
L'API ne vérifie pas que le succès déclaré par l'appelant a réellement eu lieu.

## État Git final

Un commit local, rapport inclus, sans push.
Message : feat: journaliser les écritures Forge Design (FD-GENERATE-005).
Diff utilisateur FD-CONTRACT-001.md préservé ; hash et état Git final communiqués
dans la réponse de livraison. Phase Generate clôturée après validation globale.
