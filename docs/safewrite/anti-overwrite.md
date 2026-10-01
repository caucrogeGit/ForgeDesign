# Anti-écrasement — détection des modifications externes

FD-SAFEWRITE-001. Première brique de la phase SAFEWRITE : savoir si un template
a changé sur disque depuis sa lecture. **Aucune écriture, aucune décision.**

```text
lecture initiale ─► TemplateSnapshot(expected)
                         │   … génération, diff, temps, éditeur externe …
                         ▼
relecture ─────────► TemplateSnapshot(current)
                         │
                         ▼
          unchanged | modified | created | deleted
```

## API — `forge_design.safewrite`

```python
expected = snapshot_template(root, "mvc/views/contacts/list.html")
# … édition externe éventuelle …
result = detect_template_change(root, expected)
result.status  # "unchanged" | "modified" | "created" | "deleted"
```

| Symbole | Rôle |
|---|---|
| `snapshot_template(project_root, template_path)` | Lit l'état disque d'un template |
| `detect_template_change(project_root, expected)` | Relit `expected.path` et compare |
| `compare_template_snapshots(expected, current)` | Comparaison pure, sans filesystem |
| `TemplateRevision` | `size`, `modified_ns`, `digest`, `device`, `inode`, `changed_ns` |
| `TemplateSnapshot` | `path`, `exists`, `revision` |
| `TemplateChangeResult` | `path`, `status`, `expected`, `current` |
| `TemplateChangeStatus` | `Literal["unchanged", "modified", "created", "deleted"]` |
| `TemplateSnapshotError` | Cible présente mais impossible à capturer sûrement |

Toutes les dataclasses sont gelées. `detect_template_change` ne prend pas de
chemin séparé : `expected.path` est la seule source, sans divergence possible.

## Révision

`TemplateRevision` reprend volontairement la forme de `DesignRevision` :

| Champ | Source | Détecte |
|---|---|---|
| `digest` | SHA-256 des octets lus | tout changement de contenu, mtime restauré compris |
| `size` | octets lus | — (redondant avec le digest, utile au diagnostic) |
| `modified_ns` | `st_mtime_ns` | touch sans changement de contenu |
| `device`, `inode` | `st_dev`, `st_ino` | remplacement par un nouveau fichier |
| `changed_ns` | `st_ctime_ns` | changement de métadonnées, remplacement |

La comparaison porte sur **la révision complète**. Un fichier remplacé par un
nouveau fichier aux octets identiques (éditeur qui écrit un temporaire puis
renomme) est `modified` : l'anti-écrasement doit voir le remplacement, pas
seulement une différence de contenu. Aucun type commun avec `DesignRevision`
n'est extrait tant qu'un seul writer de template n'existe pas.

Le digest porte sur les octets : aucun décodage UTF-8, aucun parsing HTML ou
Jinja. Un template binaire ou syntaxiquement invalide reste comparable.

## Snapshot : présent, absent, erreur

| Situation | Résultat |
|---|---|
| Fichier régulier lisible ≤ 1 Mio | `exists=True`, révision complète |
| Fichier absent, ou dossier parent absent | `exists=False`, `revision=None` |
| Fichier disparu entre `stat` et `open` | `exists=False` |
| Lien (fichier ou parent), même cassé | `TemplateSnapshotError` |
| Dossier, FIFO, socket, device | `TemplateSnapshotError`, sans blocage |
| Parent qui est un fichier | `TemplateSnapshotError` |
| Permission refusée, EIO… | `TemplateSnapshotError` (cause chaînée) |
| > `MAX_SOURCE_BYTES` | `TemplateSnapshotError` |
| Remplacé pendant ouverture ou lecture | `TemplateSnapshotError` |
| Chemin refusé | `SourceReadError`, avant toute I/O |
| Racine non Forge | `NotForgeProjectError` |

L'absence est un état normal ; une cible non sûre n'est **jamais** prise pour
une absence. `TemplateSnapshot` refuse à la construction `exists=True` sans
révision et `exists=False` avec révision.

## Chemins

Seuls `mvc/views/**/*.html` avec un nom non vide. Le reste de la politique est
celle de la vue source (`template_source` / `source_parts`) : pas de chemin
absolu, d'antislash, de deux-points, de `..`, `.`, segment vide ou caché, ni de
nom sensible (`env`, clés). L'inventaire Template Viewer accepte d'autres
suffixes : la détection est volontairement plus stricte.

## Lecture sécurisée et courses

Séquence, comme `design/io.py` :

```text
open_directory racine puis chaque parent (O_DIRECTORY | O_NOFOLLOW)
stat nom (sans suivre)        → régulier ?
open O_RDONLY|O_NOFOLLOW|O_NONBLOCK
fstat fd                      → régulier ? samestat(stat, fstat) ? ≤ 1 Mio ?
read_source_bytes             → taille, mtime, ctime stables sur le fd
stat nom                      → samestat(fd, nom) ? ctime inchangé ?
```

`O_NONBLOCK` évite de bloquer sur une FIFO substituée après le `stat`. La
dernière relecture du nom détecte un renommage concurrent : le descripteur
lirait encore l'ancien fichier, qui n'est plus le template. Un snapshot
incohérent n'est jamais produit.

## Matrice

| attendu \ courant | absent | présent |
|---|---|---|
| **absent** | `unchanged` | `created` |
| **présent** | `deleted` | `unchanged` si révision identique, sinon `modified` |

Chemins différents : `ValueError`. Même entrée, même statut.

## Ce que le statut ne dit pas

`modified`, `created` ou `deleted` signifient seulement : l'état actuel ne
correspond plus au snapshot attendu. Ils n'interdisent rien. Le choix proposé à
l'utilisateur (annuler, régénérer, enregistrer ailleurs, marquer manuel) relève
de FD-SAFEWRITE-002.

## Séparations

- **Diff** (FD-GENERATE-004) compare des contenus ; la détection compare une
  révision disque attendue à l'état courant. Aucun appel à `build_template_diff`.
- **Journal** (FD-GENERATE-005) décrit les écritures réussies ; il n'est pas la
  source de vérité de l'état d'un fichier. `.forge-design/history.jsonl` n'est
  ni lu ni écrit, et son format (STORAGE-002) est inchangé.
- **Stockage** : aucune ressource persistante créée ; le contrat de stockage
  est inchangé. Le template appartient à la zone C.
- Aucun import du projet cible, aucun Jinja, aucune route Web, aucun Tool.

## Limites

- POSIX requis (`dir_fd`, `O_NOFOLLOW`, `O_NONBLOCK`) ; sinon erreur explicite.
- Le snapshot est un instant : rien n'empêche un changement juste après la
  détection. L'écriture future devra recontrôler juste avant de publier.
- Un remplacement qui réutiliserait le même inode avec mêmes octets, mtime et
  ctime n'est pas détectable ; le ctime, non réglable par l'utilisateur, rend ce
  cas improbable hors manipulation du filesystem.
- Sur des systèmes de fichiers à faible résolution temporelle ou réseau,
  `st_ino`/`st_ctime_ns` peuvent être moins fiables ; le digest reste décisif
  pour le contenu.

## Choix explicite — FD-SAFEWRITE-002

Module `forge_design/safewrite/decision.py`. Il répond seulement à : *étant
donné l'état détecté, quelles décisions l'utilisateur peut-il prendre ?*

```text
TemplateChangeResult ─► decision_options() ─► choix autorisés
                                                   │ l'utilisateur choisit
                                                   ▼
                     select_safe_write_choice() ─► SafeWriteDecision
```

| Symbole | Rôle |
|---|---|
| `SafeWriteChoice` | `Literal["proceed", "cancel", "regenerate", "save_as", "mark_manual"]` |
| `has_write_conflict(change)` | `status != "unchanged"` |
| `decision_options(change)` | `SafeWriteDecisionOptions(path, status, choices)` |
| `select_safe_write_choice(change, choice)` | `SafeWriteDecision(path, status, choice)` ou `ValueError` |

### Matrice

| État | Choix, dans l'ordre de présentation |
|---|---|
| `unchanged` | `proceed`, `cancel` |
| `modified` | `cancel`, `regenerate`, `save_as`, `mark_manual` |
| `created` | `cancel`, `regenerate`, `save_as`, `mark_manual` |
| `deleted` | `cancel`, `regenerate`, `save_as`, `mark_manual` |

L'ordre est déterministe et ne sert qu'à la présentation : **aucun choix n'est
sélectionné par défaut**. `cancel` vient en tête en cas de conflit parce que
c'est l'option non destructive à proposer en premier. Aucun statut nouveau
(`conflicted`, `stale`…) : le conflit se déduit de `status`.

### Sens des choix

| Choix | Signifie | Ne signifie pas |
|---|---|---|
| `proceed` | aucun conflit **au moment de la détection** | une autorisation intemporelle d'écrire |
| `cancel` | abandonner, sans effet | — |
| `regenerate` | reprendre le pipeline depuis l'état disque actuel (nouveau snapshot → génération → diff → nouvelle décision) | écraser, ni régénérer immédiatement |
| `save_as` | ne pas remplacer la cible actuelle | un chemin : la destination est une responsabilité séparée |
| `mark_manual` | l'utilisateur déclare la vue gérée manuellement | un marqueur persistant : rien n'est stocké |

Il n'existe ni `overwrite`, ni `force`, ni `ignore_conflict`. Un remplacement
volontaire aura son propre contrat dans la couche d'écriture.

### Validation

`select_safe_write_choice` refuse par `ValueError` tout choix absent de
`decision_options(change).choices` : `proceed` sur un conflit, un choix de
conflit sur `unchanged`, et au runtime toute valeur inconnue (`"overwrite"`,
`"yes"`, `"force"`, `None`, octets, casse différente…) même si le typage est
contourné. Un statut inconnu est aussi refusé. La décision porte la valeur
canonique de la matrice, jamais l'objet fourni.

### Pureté

Les trois fonctions n'utilisent que `change.path` et `change.status` : aucune
I/O, aucun appel à `snapshot_template` ou `detect_template_change`, aucun diff,
aucun journal. `SafeWriteDecision` ne copie pas `expected`/`current` :
l'orchestrateur conserve le `TemplateChangeResult` d'origine. Aucun jeton
d'approbation : ce n'est pas une couche de sécurité Web.

### Limites

- Aucun choix appliqué, aucun writer : rien n'est écrit, relu ni journalisé.
- `save_as` : aucun chemin alternatif.
- `mark_manual` : décision transitoire destinée à un futur orchestrateur ou à
  l'UI ; aucun marqueur persistant, contrat de stockage inchangé.
- `proceed` : le writer devra **recontrôler la révision juste avant publication**.
