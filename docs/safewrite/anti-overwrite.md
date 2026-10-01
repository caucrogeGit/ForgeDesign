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

## Écriture contrôlée — FD-SAFEWRITE-003

Module `forge_design/safewrite/writer.py`. Première écriture réelle d'un
template par Forge Design.

```python
expected = snapshot_template(root, path)
# … génération + diff montrés à l'utilisateur …
change = detect_template_change(root, expected)
decision = select_safe_write_choice(change, "proceed")
result = write_generated_template(
    root, generated=generated, change=change, decision=decision
)
```

### Séquence

```text
validation pure (avant toute I/O)
→ revalidation 1 : detect_template_change(root, change.current) == unchanged
→ ouverture ancrée des dossiers (open_directory, O_NOFOLLOW)
→ mode existant, puis contrôle de révision dans le dossier ouvert
→ temporaire .forge-design-write-<hex> (O_CREAT|O_EXCL|O_NOFOLLOW|O_NONBLOCK)
→ écriture complète en boucle, fchmod du mode existant, fsync, fermeture
→ le nom temporaire désigne encore le fichier préparé (samestat)
→ revalidation 2 dans le même dossier : révision ET mode inchangés
→ publication : os.link exclusif (création) ou os.replace (mise à jour)
→ relecture par le chemin : digest, taille, inode du fichier préparé
→ fsync du dossier
→ append_generation_history(racine canonique, …)
```

### Validation avant I/O

Le writer ne fait confiance à aucune dataclass reçue. Il lève `ValueError` si :
- les chemins de `decision`, `change`, `change.expected` et `change.current`
  diffèrent ;
- les statuts de la décision et du changement diffèrent ;
- le choix n'est pas `proceed` (`cancel`, `regenerate`, `save_as` et
  `mark_manual` ne sont jamais appliqués) ;
- le statut n'est pas `unchanged`, ou `compare_template_snapshots(expected,
  current)` ne donne pas `unchanged` (statut falsifié) ;
- `generated` n'est pas un `str`, ne s'encode pas en UTF-8 (surrogates), ou
  dépasse `MAX_SOURCE_BYTES` en octets ;
- le timestamp est naïf, ou le chemin contient un caractère de contrôle ou est
  trop long pour le journal : ces cas feraient échouer le journal *après*
  publication, ils sont donc refusés avant.

La cible vient uniquement de `change.path`. Les octets écrits sont exactement
`str.encode(generated, "utf-8")` : sans BOM ajouté, sans strip, sans
normalisation des fins de ligne, NUL compris. Une sous-classe de `str` ne peut
pas détourner l'encodage.

### Création et mise à jour

| `change.current` | Publication | `created` | Mode |
|---|---|---|---|
| absent | `os.link(temp, cible)` puis `unlink(temp)` : refuse une cible apparue entre-temps | `True` | `0666 & ~umask` |
| présent | `os.replace(temp, cible)` | `False` | mode existant conservé |

`created` vient de `change.current.exists`, pas d'une relecture.

### Limite de concurrence POSIX

> Forge Design revalide la révision immédiatement avant la publication et
> vérifie le résultat immédiatement après. Cette stratégie réduit fortement les
> races mais ne constitue pas un CAS filesystem contre un processus externe non
> coopératif entre le dernier contrôle et `os.replace`.

Concrètement : une modification externe dans cette fenêtre est écrasée par
`os.replace`. Elle n'est **pas** détectée par la vérification post-publication,
qui relit notre propre fichier. Une suppression dans cette fenêtre fait recréer
la cible par `os.replace`. Pour une création, `os.link` ferme cette fenêtre.

Le ctime a une granularité grossière (tick d'horloge du noyau) : un `chmod` fait
dans le même tick ne le modifie pas. Le writer compare donc aussi le mode juste
avant publication, pour ne pas réappliquer un ancien mode sur un `chmod` tiers.

### Erreurs et ce qu'elles garantissent

| Exception | Publication ? | Journal ? |
|---|---|---|
| `ValueError` | non, aucune I/O | non |
| `TemplateWriteConflictError` | non : cible changée, supprimée, remplacée, apparue ou illisible | non |
| `TemplateWriteError` (base) | non : échec technique avant publication (temporaire, fsync, replace, link…) | non |
| `TemplatePublishedError` | **oui** ; `publication` vaut `None` si le résultat n'a pas pu être certifié (modifié juste après publication) ; renseignée si seul le fsync du dossier a échoué | non |
| `TemplateHistoryError` | **oui**, vérifiée et synchronisée ; `publication` renseignée | non : *écriture réussie, traçage incomplet* |

`TemplatePublishedError` n'hérite **pas** de `TemplateWriteConflictError` : un
`except TemplateWriteConflictError` ne peut jamais confondre « rien écrit » et
« écrit ». Il n'y a aucun rollback automatique, car restaurer l'ancien contenu
pourrait écraser un tiers. Il n'y a pas non plus de retry du journal. Après
toute erreur publiée, relire la cible avant une nouvelle tentative.

### Nettoyage

Le temporaire est supprimé à toute erreur antérieure à la publication. Après
la publication, le nettoyage ne touche plus à la cible. En cas de collision du
nom temporaire (`O_EXCL`), le fichier existant n'appartient pas à Forge Design
et n'est jamais supprimé. Aucun temporaire ne reste après un succès.

### Hardlinks

La politique de SAFEWRITE-001 est inchangée : un template à liens multiples est
accepté. `os.replace` publie un **nouvel inode** : les autres liens durs
continuent de pointer vers l'ancien contenu. Forge Design ne met pas à jour
les autres liens.

### Journal

`append_generation_history` est appelé une seule fois, après la publication, la
vérification et le fsync du dossier, avec la racine canonique. Une racine
fournie via un lien symbolique est acceptée par le writer, alors que le journal
refuserait un chemin contenant un lien. Le format STORAGE-002 est inchangé.
Aucune entrée n'est écrite pour une tentative, un refus ou un échec.

### Hors périmètre

Pas de génération, de diff, d'UI, de route Web, de `save_as`, de
`mark_manual`, de `regenerate`, de backup ni de rollback.
