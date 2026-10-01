# Rapport — FD-SAFEWRITE-003

## Ticket et objectif

Première écriture réelle d'un template Forge par Forge Design : publier un
contenu généré seulement après `proceed`, avec revalidation du disque avant la
préparation et juste avant la publication, puis vérification, fsync et journal.
Ce ticket clôt la phase anti-écrasement minimale (détecter, décider, écrire).

## État Git initial

`main` synchronisée avec `origin/main` à `3eb9c35` — FD-SAFEWRITE-002, poussé
par l'utilisateur. Seule modification préexistante :
`docs/rapports/FD-CONTRACT-001.md`, préservée hors commit.

## Contrat de stockage

Aucune nouvelle ressource : templates en zone C, temporaires
`.forge-design-write-*` déjà réservés, `history.jsonl` inchangé. Une
incohérence réelle a été corrigée dans
[storage-contract.md](../storage/storage-contract.md) : la ligne `*.html`
indiquait « aucune écriture à ce jour » ; elle référence désormais
`write_generated_template`. Aucune autre modification du contrat.

## API publique

Ajouts à `forge_design.safewrite` : `TemplatePublication`,
`TemplateWriteResult`, `TemplateWriteError`, `TemplateWriteConflictError`,
`TemplatePublishedError`, `TemplateHistoryError` et `write_generated_template(
project_root, *, generated, change, decision, timestamp=None)`.

`TemplatePublishedError` est l'exception supplémentaire prévue aux §105-107,
car plusieurs étapes post-publication peuvent échouer. Dans
`detection.py`, une primitive est exposée (§134) : `read_template_revision_at
(directory_fd, name)`, enveloppe de trois lignes autour de `_read_revision`,
sans changement de comportement et non exportée par le package. Elle permet la
revalidation finale dans le **même descripteur de dossier** que la
publication, sans troisième implémentation de lecture sûre.

## Validation de la décision

Avant toute I/O (prouvé par des tests où toute I/O lève une erreur), `ValueError`
si : types inattendus ; chemins de `decision`, `change`, `expected`, `current`
différents ; statuts différents ; choix autre que `proceed` ; statut autre que
`unchanged` ; `compare_template_snapshots(expected, current)` différent de
`unchanged` (statut falsifié).

## Payload UTF-8

`generated` doit être un `str`. L'encodage passe par `str.encode(generated,
"utf-8")`, qu'une sous-classe ne peut pas détourner (testé avec un `encode`
redéfini). Les surrogates donnent `ValueError`. Aucun BOM ajouté, aucun strip,
aucune normalisation : CRLF, absence de LF final, espaces, NUL, BOM fourni,
chaîne vide, é / 日本語 / emoji sont conservés à l'octet près. Limite
`MAX_SOURCE_BYTES` en octets : limite exacte acceptée (multi-octets), dépassement
refusé avant tout temporaire.

## Révalidation initiale

`detect_template_change(project_root, change.current)` doit donner
`unchanged`. Sinon, ou si la cible est devenue non sûre (`TemplateSnapshotError`),
`TemplateWriteConflictError`. Le statut d'origine n'est jamais cru seul.

## Temporaire

Le dossier cible est ouvert par `open_directory` segment par segment, avec
`O_NOFOLLOW`. Nom `.forge-design-write-` + `secrets.token_hex(16)`, créé avec
`O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC`. L'écriture boucle
jusqu'à complétion ; `count <= 0` donne une erreur. Le temporaire reçoit
`fchmod` (mode existant), `fsync`, `fstat`, puis est fermé. Avant publication,
le nom temporaire doit encore désigner un fichier régulier `samestat` au
fichier préparé, sinon `TemplateWriteError`.

La création du temporaire est séparée de son remplissage. Une collision
`O_EXCL` n'est jamais nettoyée (ce n'est pas notre fichier). Un échec après
création supprime toujours le temporaire. La première version ne le faisait
pas pour un échec pendant le remplissage ; le défaut a été corrigé avant les
tests.

## Révalidation finale

Juste avant publication, dans le même dossier ouvert :
`read_template_revision_at(directory, name) == change.current.revision`, et le
mode doit être identique au mode lu avant la préparation. Sinon,
`TemplateWriteConflictError` et le temporaire est supprimé.

**Défaut trouvé par les tests.** Un `chmod` concurrent n'était pas toujours
détecté : le ctime Linux a la granularité du tick d'horloge, si bien qu'un
`chmod` fait dans le même tick ne le modifie pas. Le test correspondant
passait ou échouait selon le moment. Sans contrôle de mode, le writer aurait
réappliqué l'ancien mode sur un `chmod` tiers. `TemplateRevision` ne porte pas
le mode et ne devait pas être modifiée : le writer compare donc lui-même le mode.
Mutation : sans ce contrôle, le test échoue 3 fois sur 5 ; avec, il passe 5
fois sur 5. Un second défaut du même type a été corrigé : la lecture du mode
après suppression concurrente sortait en `TemplateWriteError` générique au
lieu d'un conflit.

## Création exclusive

Si `change.current` est absent : `os.link(temp, cible, follow_symlinks=False)`,
puis `unlink(temp)`. Une cible apparue après le second contrôle fait échouer
`link` (`FileExistsError`), ce qui donne `TemplateWriteConflictError`, cible
externe intacte, aucun journal (testé en injectant la création après le second
contrôle).

## Mise à jour atomique

Si `change.current` est présent : `os.replace(temp, cible)` dans le même
dossier, après la seconde revalidation.

## Permissions

Création : `0666` sous l'umask. Mise à jour : `fchmod(previous_mode & 0o777)`,
avec un `0640` conservé dans le test.

## Vérification post-publication

`snapshot_template(racine canonique, chemin)`, par le chemin : digest SHA-256
attendu, taille attendue, et `(device, inode)` égal à celui du fichier préparé.
Une modification ou un remplacement juste après publication donne
`TemplatePublishedError(publication=None)`, aucun journal. Trois cas sont
testés : contenu différent, même octets sur un autre inode, et même inode et
même taille avec un octet différent (seul le digest le révèle).

## Limite de concurrence POSIX

> Forge Design revalide la révision immédiatement avant la publication et
> vérifie le résultat immédiatement après. Cette stratégie réduit fortement les
> races mais ne constitue pas un CAS filesystem contre un processus externe non
> coopératif entre le dernier contrôle et `os.replace`.

Une écriture externe dans cette fenêtre est écrasée par `os.replace`, et la
vérification post-publication ne la voit pas puisqu'elle relit notre fichier.
Une suppression dans cette fenêtre est recréée. Pour une création, `os.link`
ferme la fenêtre. Ce rapport ne revendique aucune absence de course.

## Journalisation

`append_generation_history(racine canonique, action="generate_template",
file=change.path, timestamp=timestamp)`, appelé une seule fois après la
publication vérifiée et le fsync du dossier. Le format STORAGE-002 est vérifié
à l'octet ; un journal existant conserve ses lignes ; le timestamp injecté est
exact, et un timestamp à fuseau +02:00 est converti en Z.

Deux pièges découverts en lisant le code ont été traités en amont, car ils
auraient fait échouer le journal **après** publication :
- le journal refuse une racine contenant un lien symbolique, alors que
  `resolve_project_root` l'accepte : le writer passe donc la racine canonique
  (testé avec une racine liée ; la mutation fait échouer ce test) ;
- un timestamp naïf, un chemin avec caractère de contrôle (accepté par
  `source_parts`, refusé par le journal) ou un chemin trop long pour
  `MAX_HISTORY_EVENT_BYTES` sont refusés par `ValueError` avant toute I/O.

## Échec du journal après publication

`TemplateHistoryError(publication)` : *écriture réussie, traçage incomplet*.
Testé sur trois causes : `.forge-design` lié, dossier sans permission
d'écriture, fsync en échec. Dans chaque cas, le template est réellement publié,
la `publication` est accessible avec son digest, et le journal n'a été appelé
qu'une seule fois. Aucun rollback, aucun retry.

## Exceptions

| Exception | Publié | Journal |
|---|---|---|
| `ValueError` | non (aucune I/O) | non |
| `TemplateWriteConflictError` | non | non |
| `TemplateWriteError` (base) | non | non |
| `TemplatePublishedError` | oui (`publication` ou `None`) | non |
| `TemplateHistoryError` | oui, vérifié | non |

Le §53 demandait `TemplateWriteConflictError` pour une vérification
post-publication en échec. Ce cas lève plutôt `TemplatePublishedError`, qui
n'hérite **pas** de la classe de conflit, pour respecter le §104 (« ne jamais
présenter comme aucune écriture »). Un `except TemplateWriteConflictError` ne
peut ainsi jamais confondre « rien écrit » et « écrit ». La hiérarchie est
vérifiée par test.

## Symlinks et fichiers spéciaux

Cible liée, FIFO (sans blocage), dossier, parent lié, tous substitués après la
décision : `TemplateWriteConflictError`, rien n'est écrit hors de la racine.
Permission refusée sur le dossier : `TemplateWriteError` hors publication, rien
publié.

## Hardlinks

La politique de SAFEWRITE-001 est inchangée. `os.replace` publie un nouvel
inode : un autre lien dur garde l'ancien contenu (testé et documenté). Forge
Design ne met pas à jour les autres liens.

## Nettoyage

Aucun temporaire après un succès ni après un échec pré-publication (testé pour
le contenu changé, la suppression, le chmod, le temporaire remplacé, le write à
zéro, le fsync du temporaire, `replace`, `link`). Après publication, la cible
n'est jamais supprimée.

## Non-mutation

`change`, `decision` et `generated` sont comparés à une copie profonde. Le writer
ne connaît ni `build_template_diff` ni `generate_simple_template` (vérifié sur
l'espace de noms). ToolRegistry : 5 Tools. Aucune modification de `web/`.

## Fichiers créés

- `forge_design/safewrite/writer.py`
- `tests/test_safewrite_writer.py`
- `docs/rapports/FD-SAFEWRITE-003.md`

## Fichiers modifiés

- `forge_design/safewrite/__init__.py` : exports.
- `forge_design/safewrite/detection.py` : primitive `read_template_revision_at`
  (§134), aucun changement de comportement.
- `docs/safewrite/anti-overwrite.md` : section « Écriture contrôlée ».
- `docs/02-architecture.md` §14 : pipeline implémenté.
- `docs/storage/storage-contract.md` : ligne `*.html` (incohérence réelle).

Non modifiés : `decision.py`, `design/io.py`, `generate/diff.py`,
`generate/history.py`, `contracts/`, `preview/`, `web/`, `tools/`, `app.py`,
JavaScript.

## Tests ajoutés

`tests/test_safewrite_writer.py` : 71 cas.
- Nominal : création, mise à jour avec mode, append, timestamps, 7 contenus à
  l'octet, racine liée.
- Validation sans I/O : 4 choix non-`proceed`, 3 conflits avec `proceed`
  falsifié, 9 incohérences (chemins, statut, snapshots), types et surrogates,
  timestamps, chemins non journalisables, sous-classe de `str`, limite exacte et
  dépassement, non-mutation.
- Conflits : modification et création avant revalidation, remplacement aux
  mêmes octets, contenu / suppression / chmod entre les contrôles, création
  après le second contrôle (`link`), 4 cibles non sûres, permission.
- Publication : collision du temporaire, temporaire remplacé, short writes,
  write à zéro, fsync du temporaire, `replace` et `link` en erreur.
- Post-publication : fsync du dossier, 3 mutations immédiates, 3 échecs du
  journal sans retry.
- Hardlink, hiérarchie des exceptions, absence de diff et de génération,
  registre.

Vérification par mutation (chaque garde retiré dans une copie restaurée
ensuite) : second contrôle (4 échecs), première revalidation (1), création via
`replace` (3), `samestat` du temporaire (2), inode post-publication (2), digest
post-publication (2, après ajout du test même-taille : il survivait
auparavant), statut recalculé (4), nettoyage du temporaire (9), `fchmod` (2),
timestamp (3), chemin journalisable (3), racine canonique (1), mode
(intermittent par nature, voir plus haut).

## Validations ciblées

| Commande | Résultat |
|---|---|
| `pytest -q tests/test_safewrite_writer.py` | 71 réussis, stable sur 5 exécutions |
| `pytest -q tests/test_safewrite_detection.py tests/test_safewrite_decision.py tests/test_safewrite_writer.py` | 233 réussis |
| idem + `test_design_io.py test_source.py test_generate_history.py test_templates.py` | 423 réussis |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` / `ruff format --check .` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |

## Validation globale de phase

`pytest` : **2939 réussis** en 29 s. `python -m pip check` : No broken
requirements found.

## Packaging

`python -m pip wheel --no-deps --wheel-dir tmp/wheels .` produit
`forge_design-0.1.0.dev0-py3-none-any.whl`, SHA-256
`f1b94d505e36c1cccf240968ea2aae44f0288a30adfbcce3b929aa80f6ab2ccb`.
Elle contient `safewrite/{__init__,decision,detection,writer}.py` et aucun
fichier de `tests/` ni de `tmp/`. Aucune dépendance nouvelle.

## Installation réelle

Installation `--no-deps --no-index --target` temporaire ; `python -I` depuis un
cwd temporaire, avec vérification de l'origine installée ; imports
`snapshot_template`, `detect_template_change`, `decision_options`,
`select_safe_write_choice` et `write_generated_template`. Le design et le
contrat `contacts-list` sont lus comme données.

1. **Création** : snapshot absent, génération réelle (`complete`), diff réel,
   `unchanged`, `proceed`, écriture : 464 octets exacts, `created=True`, une
   ligne de journal `version: 1`.
2. **Modification externe** : `modified`, `proceed` absent des options et refusé
   par la sélection ; arborescence du projet inchangée à l'octet.
3. **Course** : `proceed`, puis modification externe, puis writer :
   `TemplateWriteConflictError` ; arborescence inchangée et aucun
   `.forge-design/`.

## Limites restantes

- Pas de compare-and-swap : fenêtre documentée entre le dernier contrôle et
  `os.replace`.
- Les autres liens durs gardent l'ancien contenu.
- Après `link`, un `unlink` du temporaire en échec laisse un temporaire résiduel
  et lève `TemplatePublishedError(None)`.
- POSIX requis (`dir_fd`, `O_NOFOLLOW`, `link` sans suivi) ; erreur explicite
  sinon.
- Aucun orchestrateur ni UI ; `save_as`, `mark_manual` et `regenerate` ne sont
  pas appliqués.
- Aucun rollback ni backup : après `TemplatePublishedError`, relire la cible.

## État Git final

Un commit sur `main`, rapport inclus, sans push.
Message : `feat: écrire les templates de façon contrôlée (FD-SAFEWRITE-003)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Le hash ne peut pas
figurer dans le commit qui le produit : il est communiqué dans la réponse de
livraison et retrouvable par :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-SAFEWRITE-003.md
```
