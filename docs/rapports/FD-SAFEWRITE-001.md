# Rapport — FD-SAFEWRITE-001

## Ticket et objectif

Première brique de l'anti-écrasement : capturer la révision disque d'un template,
la relire plus tard et dire explicitement s'il est `unchanged`, `modified`,
`created` ou `deleted`, ou s'il est devenu impossible à capturer de façon sûre.
Aucun template écrit.

## État Git initial

`main` synchronisée avec `origin/main` à `e573f65` — FD-STORAGE-002.
`git status` et `git log --oneline --decorate -10` inspectés : FD-WEB-003,
FD-STORAGE-001 et FD-STORAGE-002 présents dans la baseline. Seule modification
préexistante : `docs/rapports/FD-CONTRACT-001.md`, préservée hors commit.

## Contrat de stockage

Le template est en zone C (`<projet>/mvc/views/**/*.html`). Aucune ressource
persistante créée : `docs/storage/storage-contract.md` inchangé.
`.forge-design/` n'est ni créé, ni lu, ni écrit.

## API publique

Exportée par `forge_design.safewrite` : `TemplateRevision`, `TemplateSnapshot`,
`TemplateChangeStatus`, `TemplateChangeResult`, `TemplateSnapshotError`,
`snapshot_template`, `detect_template_change`, ainsi que le helper pur
`compare_template_snapshots`, exporté parce qu'il permet de tester la matrice
sans filesystem et qu'il servira à SAFEWRITE-002.

## TemplateRevision

Dataclass gelée `size, modified_ns, digest, device, inode, changed_ns`, de même
forme et même sémantique que `DesignRevision`. `DesignRevision` n'est pas
refactorée et aucun type commun n'est extrait.

## TemplateSnapshot

`path, exists, revision`, gelée. `__post_init__` refuse `exists=True` sans
révision et `exists=False` avec révision : `exists` porte seul l'absence.

## États de changement

`TemplateChangeStatus = Literal["unchanged", "modified", "created", "deleted"]`.
`TemplateChangeResult(path, status, expected, current)`. Le chemin vient
uniquement de `expected.path`.

## Matrice de comparaison

absent→absent `unchanged`, absent→présent `created`, présent→absent `deleted`,
présent→présent `unchanged` si la révision complète est égale, sinon `modified`.
Chemins différents : `ValueError`. La fonction est pure et déterministe.

## Lecture sécurisée

Séquence de `design/io.py::_current`, construite avec les primitives existantes :
`open_directory` (racine puis chaque parent, `O_NOFOLLOW`), `stat` du nom sans
suivre, `open O_RDONLY|O_NOFOLLOW|O_NONBLOCK`, `fstat` + `samestat`, limite
`MAX_SOURCE_BYTES`, `read_source_bytes` (taille, mtime et ctime stables sur le
fd), puis nouveau `stat` du nom + `samestat` + ctime.

`read_project_source_bytes` n'est pas utilisé tel quel : il ne relit pas le nom
après la lecture (point 38) et ne distingue pas l'absence d'un parent.
La validation des chemins réutilise `template_source` / `source_parts`, à
laquelle s'ajoutent le préfixe `mvc/views/` et le suffixe `.html` avec un nom
non vide. Aucun parseur parallèle. La racine est validée comme dans les autres
lecteurs : `resolve_project_root` puis `detect_forge_project`.

## Digest

`sha256(data).hexdigest()` sur les octets réellement lus, sans décodage.

## Identité filesystem

`st_dev`, `st_ino`, `st_ctime_ns` du descripteur lu. Un remplacement aux octets
identiques est `modified` (testé en gardant l'ancien inode vivant pour éviter
sa réutilisation).

## Templates absents

Absence du fichier ou d'un dossier parent avant ouverture, et disparition entre
`stat` et `open` : `exists=False`. La disparition **après** ouverture, pendant
la lecture, est une course : `TemplateSnapshotError`.

## Symlinks et fichiers spéciaux

Lien de template, lien de parent (valides ou cassés), parent fichier, dossier,
FIFO, socket : `TemplateSnapshotError`. Permission refusée sur le fichier ou le
parent : `TemplateSnapshotError` avec cause chaînée, jamais absence.

## Races filesystem

Simulées : remplacement, lien et FIFO substitués entre `stat` et `open` ;
remplacement, suppression et modification pendant la lecture. Toutes refusées.
Les tests forcent `_secure_read_available` car instrumenter `os.open` le retire
de `os.supports_dir_fd`. Sans cela, ils passaient pour une mauvaise raison,
défaut détecté puis corrigé pendant le ticket. Chaque test vérifie le message
attendu ; le cas du lien vérifie `ELOOP`.

Vérification par mutation : supprimer le contrôle d'identité à l'ouverture fait
échouer 3 tests, et supprimer la relecture du nom après lecture en fait échouer 1.

## Séparation avec Diff

Aucun appel à `build_template_diff` ; `forge_design/generate/` est inchangé.

## Séparation avec History

`history.jsonl` n'est ni lu ni écrit ; son format STORAGE-002 est inchangé.

## Pureté de la comparaison

`compare_template_snapshots` ne fait aucune I/O. Matrice testée sur des
révisions construites, chaque champ de révision variant isolément.

## Non-mutation

Dataclasses gelées. `expected` et `project_root` sont inchangés. Octets et mtime
du template, absence de `.forge-design/` et contenu du dossier sont vérifiés
après détection. Descripteurs fermés (`/proc/self/fd` stable sur 60 appels,
succès et erreurs). ToolRegistry : toujours 5 Tools.

## Documentation

- [docs/safewrite/anti-overwrite.md](../safewrite/anti-overwrite.md)
- [docs/02-architecture.md](../02-architecture.md) §14 : pipeline et schéma.

## Fichiers créés

- `forge_design/safewrite/__init__.py`
- `forge_design/safewrite/detection.py`
- `tests/test_safewrite_detection.py`
- `docs/safewrite/anti-overwrite.md`
- `docs/rapports/FD-SAFEWRITE-001.md`

## Fichiers modifiés

- `pyproject.toml` : package `forge_design.safewrite` (liste explicite).
- `docs/02-architecture.md`

Fichiers non modifiés, conformément au ticket : `design/io.py`, `generate/`,
`contracts/`, `preview/`, `web/`, `tools/`, `app.py`, le contrat de stockage
et le JavaScript.

## Tests ajoutés

`tests/test_safewrite_detection.py` : 65 cas. Matrice pure (9), cohérence des
snapshots, gel, snapshot nominal avec les six champs, absence (fichier, parent),
unchanged / modified / created / deleted, remplacement aux octets identiques,
mtime restauré, Unicode `élèves/liste.html`, binaire, limite exacte et
dépassement, 19 chemins invalides refusés avant I/O, racine non Forge, code
projet non importé, liens, parent fichier, FIFO, dossier, socket, permissions,
6 courses, descripteurs, non-mutation, registre.

## Validations ciblées

| Commande | Résultat |
|---|---|
| `pytest -q tests/test_safewrite_detection.py` | 65 réussis |
| `pytest -q tests/test_safewrite_detection.py tests/test_design_io.py tests/test_source.py tests/test_templates.py tests/test_template_viewer.py tests/test_entity_source.py tests/test_tool_registry.py tests/test_import.py` | 279 réussis |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` / `ruff format --check .` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |

## Packaging

Wheel `forge_design-0.1.0.dev0-py3-none-any.whl`, construite une fois après les
validations ciblées. SHA-256 :
`a54c2853f140b475e79c491166bba05e887fcc188f7806231dead1f112b92acf`.
Contient `forge_design/safewrite/{__init__,detection}.py` ; aucun fichier de
`tests/` ni de `tmp/`. Aucune dépendance nouvelle.

Installation `--no-deps --no-index --target` dans un dossier temporaire, puis
`python -I` lancé depuis un cwd temporaire, avec vérification de l'origine
installée du module. Scénario : projet Forge temporaire, snapshot de
`mvc/views/contacts/list.html` → `unchanged`, arborescence du projet identique
octet par octet et mtime ; modification externe → `modified` ; aucun
`.forge-design/`.

## Tests non exécutés

- Suite globale : non lancée, conformément au ticket, en l'absence de régression
  transversale.
- `pip check` : non nécessaire, aucune dépendance nouvelle.
- Node : aucun JavaScript modifié.
- MkDocs : aucune configuration, non applicable.
- `test_permission_denied_*` : sautés si exécutés en root (non le cas ici).

## Limites restantes

- POSIX requis ; erreur explicite sinon.
- Un snapshot est instantané : l'écriture future devra recontrôler juste avant
  de publier.
- Un remplacement qui réutiliserait inode, octets, mtime et ctime identiques
  n'est pas détectable.
- Fiabilité de `st_ino` / `st_ctime_ns` moindre sur certains filesystems réseau ;
  le digest reste décisif pour le contenu.
- Aucun contrôle de hardlinks, comme dans `design/io.py` : un template à liens
  multiples est lu normalement.

## État Git final

Un commit sur `main`, rapport inclus, sans push.
Message : `feat: détecter les modifications externes (FD-SAFEWRITE-001)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit.
