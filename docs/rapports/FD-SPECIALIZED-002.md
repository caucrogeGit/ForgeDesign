# Rapport — FD-SPECIALIZED-002

## Ticket et objectif

Transformer le contrat documentaire FD-SPECIALIZED-001 en socle Python
minimal et testable, `forge_design.specialized`, et l'éprouver avec un outil
témoin **limité aux tests**. Aucun Circuit, registre, UI, runtime ni export.

## État Git initial

`main` synchronisée avec `origin/main` à `4108a62` — FD-SPECIALIZED-001.
Seule modification suivie préexistante : `docs/rapports/FD-CONTRACT-001.md`,
préservée hors commit.

## Contrat implémenté

```text
forge_design/specialized/
├── models.py     déclarations gelées et validées
├── resource.py   codec (Protocol) + hôte de lecture/écriture
└── __init__.py   exports publics
```

Le cycle couvert par le critère de fin est démontré par
`test_full_cycle_round_trip` :

```text
create → read → validate → edit in memory → save → read again
```

## API publique

`forge_design.specialized` exporte :

- **Déclarations** : `SpecializedToolDefinition`, `SpecializedResourceType`,
  `SpecializedCapability`, `PlatformCapability`, `PLATFORM_CAPABILITIES`,
  `OptionalDependency`, `UiEntry`.
- **Diagnostics** : `SpecializedIssue`, `SpecializedValidationResult`,
  `ErrorCategory`.
- **Ressource** : `SpecializedResourceRef`, `SpecializedResourceRevision`,
  `SpecializedResourceCodec`, `SpecializedFormatError`,
  `SpecializedReadResult`, `SpecializedWriteResult`.
- **Fonctions** : `read_specialized_resource`, `write_specialized_resource`.
- **Erreurs** : `SpecializedResourceError`,
  `SpecializedResourceRefusedError`, `SpecializedCapabilityError`,
  `UnsupportedSpecializedVersionError`, `SpecializedResourceConflictError`,
  `InvalidSpecializedResourceError`, `SpecializedResourceHistoryError`.

Aucun témoin, fixture ni helper de test n'est exporté. Les tests vérifient
qu'aucun nom exporté et aucune source du paquet ne contient « witness ».

## Tool inchangé

`forge_design/platform/tool.py`, `tool_registry.py` et `app.py` ne sont pas
modifiés (`git diff --stat`). **Le registre contient toujours exactement cinq
Tools** : `project-inspector`, `route-explorer`, `entity-explorer`,
`debug-center` et `template-viewer`. C'est testé, ainsi que l'absence de toute
`SpecializedToolDefinition` dans le registre. Une définition n'a ni `run`, ni
`open`, ni `save`, ni `render`, ni `simulate`, ni `export` (testé).

La règle kebab-case est celle de `ToolRegistry.register`. Elle est reprise
dans `models.py` sans modifier le registre, qui ne doit pas changer, et un
test vérifie que les deux politiques concordent sur onze exemples.

## Outil témoin

L'outil témoin vit dans `tests/specialized_support.py` uniquement :
- `id = witness`, nom « Témoin de test FD-SPECIALIZED-002 » ;
- capacités `create`, `open`, `edit`, `validate`, `save` ;
- `optional_dependencies = ()` et `ui_entry = None` : une définition existe
  sans intégration Web.

**Aucun outil témoin n'est livré.** Le témoin n'est ni dans le paquet, ni dans
la wheel (vérifié en listant son contenu), ni enregistré, ni visible dans la
navigation, ni documenté comme fonctionnalité.

## Type de ressource témoin

| Champ | Valeur |
|---|---|
| `id` | `document` |
| `format_id` | `witness-json` |
| `suffix` | `.witness.json` |
| `source_prefix` | `mvc/resources/witness` (projets temporaires des tests seulement, non réservé, absent du contrat de stockage) |
| `read_versions` / `write_version` | `{"0.1"}` / `0.1` |
| `editable`, `max_size` | `true`, 64 Kio |
| `validation_levels`, bloquants | `structure`, `content` ; seul `structure` bloque |
| `persistent_state` / `runtime_only_state` | `title`, `content` / `selected_tab` |

Document : `{"format_version": "0.1", "title": …, "content": …}`.

## Versionnement

Le type déclare des versions lues (ensemble non vide) et une version écrite,
qui doit en faire partie. Les versions mal formées sont refusées.

**Preuve : une version inconnue est refusée avant decode.** Un document en
`0.2` donne `unsupported-version`, avec la révision mais sans ressource ni
référence, et le compteur `decode_calls` reste à 0. Une version illisible
(JSON invalide, tableau, champ absent ou non textuel) donne
`invalid-resource`, sans `decode` non plus.

## Capabilities

`PlatformCapability` est un `Literal` fermé : `create`, `open`, `edit`,
`validate`, `save`, `export`, `interactive-runtime`. `preview`, `simulate` et
`measure` sont refusés comme capacités plateforme. Une capacité d'outil est en
kebab-case et ne peut pas reprendre un nom plateforme (par exemple `export`),
pour que les deux niveaux ne se confondent pas.

Les capacités sont réellement appliquées par l'hôte :
- lecture sans `open` : `capability-unavailable` ;
- écriture sans `save` (ou type non éditable) : `SpecializedCapabilityError`.
- création sans `create` : `SpecializedCapabilityError`.

## Validation

Le type déclare des niveaux, dont `structure` (obligatoire et toujours
bloquant). Une issue `error` d'un niveau bloquant refuse l'écriture ; une
issue d'un niveau non bloquant ou un `warning` ne la refuse pas.

**Preuves :**
- **un warning ne bloque pas la sauvegarde** : un titre vide produit
  `witness.empty-title` (`warning`, niveau `content`), et la ressource est
  chargée et sauvegardée ;
- **une erreur bloquante empêche la sauvegarde** : `title` non textuel donne
  `InvalidSpecializedResourceError`, sans fichier ni journal ;
- **une validation tronquée bloque aussi l'écriture** (600 issues).

## Issues

`SpecializedIssue(code, severity, message, level, location)`, gelée.
- `code` : une catégorie plateforme connue, ou `<outil>.<code>`, les deux
  segments en kebab-case. Les codes non qualifiés sont refusés.
- `severity` : `error` ou `warning`.
- `location` : tuple d'au plus 64 éléments `str` ou `int` (booléens et
  flottants refusés).

`SpecializedValidationResult` est borné à `MAX_SPECIALIZED_ISSUES = 512`. Le
constructeur `bounded()` s'arrête de consommer au 513e élément et pose
`truncated`. `MAX_DESIGN_ISSUES` n'est pas réutilisé, car sa sémantique
(marqueur inclus) est propre au Design.

## Codec

`SpecializedResourceCodec[Resource]` est un Protocol étroit :
`detect_version`, `decode`, `encode`, `validate`. Le codec ne reçoit que des
octets et une ressource en mémoire : il ne lit pas le système de fichiers,
n'écrit pas et ignore la racine. Les erreurs de format attendues passent par
`SpecializedFormatError(issues)`. Toute autre exception d'un codec reste une
erreur de programmation et se propage, sans être convertie. Un niveau
d'issue non déclaré par le type lève `ValueError`.

## Lecture confinée

Ordre des contrôles :
1. capacité `open` ;
2. chemin lexical : `unsafe_relative_path`, préfixe `source_prefix + "/"`,
   suffixe et nom non vide, **avant tout accès** (testé avec une racine
   inexistante) ;
3. racine : `resolve_project_root`, `detect_forge_project` ;
4. dossiers ouverts par `open_directory` (`O_NOFOLLOW` à chaque segment) ;
5. `lstat` du fichier (ordinaire seulement), puis
   `open(O_NOFOLLOW | O_NONBLOCK)`, `fstat` et `samestat` ;
6. **taille bornée par `max_size` avant lecture** ;
7. lecture bornée, puis contrôle de stabilité (taille, `mtime`, `ctime`, et
   `lstat` comparé par `samestat`).

`read_project_source_bytes` n'est pas réutilisable : il est lié à
`source_parts` (`mvc/views`, `routes`…) et à 1 Mio. La même discipline est
donc reprise, bornée par le type. Le résultat est structuré : chemin,
référence, révision, ressource, issues, `truncated` et catégorie `error`.

## Révision

`SpecializedResourceRevision` comporte la taille, `modified_ns`, l'empreinte
SHA-256, le périphérique, l'inode et `changed_ns`. Elle a la même forme que
`DesignRevision` mais en est indépendante : aucune dépendance de
`specialized` vers `design`.

## Écriture atomique

Pipeline :
1. capacités ;
2. chemin ;
3. `encode` ;
4. borne `max_size` ;
5. `validate` et niveaux bloquants, troncature comprise ;
6. version détectée sur les octets produits, qui doit être `write_version` ;
7. racine ;
8. dossiers sans lien ;
9. révision attendue ;
10. temporaire exclusif `.forge-design-write-*` (`O_EXCL | O_NOFOLLOW`) ;
11. écriture complète, conservation du mode existant, `fsync` ;
12. contrôle du temporaire, puis nouveau contrôle de révision ;
13. publication : `link` pour une création (exclusive), `replace` pour une
    mise à jour ;
14. `fsync` du dossier ;
15. relecture et comparaison de l'empreinte ;
16. journal.

L'implémentation est autonome, inspirée de `write_design`. `write_design`
n'est pas refactoré. L'espace de sources doit exister : aucun dossier n'est
créé (testé, y compris `mvc/resources/` absent).

## Conflits

**Création exclusive et conflit sur révision externe, sans écrasement
silencieux** :
- `expected_revision=None` sur une cible existante : `conflict`, cible
  intacte ;
- course où la cible est créée par un tiers après le dernier contrôle :
  `link` échoue, la cible du tiers est intacte, aucun temporaire ni journal ;
- modification externe après lecture : `conflict` ;
- remplacement par les mêmes octets (nouvel inode) : `conflict` ;
- cible supprimée : `conflict` ;
- lien symbolique posé au moment de l'écriture, en mise à jour comme en
  création : `conflict`, et la cible du lien n'est pas modifiée.

Aucun temporaire ne survit, après succès comme après échec.

## Journalisation

**Situation : adaptée minimalement.** `history.jsonl` est réutilisé. Le
service `append_generation_history` n'acceptait que l'action
`generate_template`. La ligne `{version, timestamp, action, file}` permet
pourtant un autre événement **sans changer de structure** : ni champ ajouté,
ni retiré, ni renommé. `HistoryAction` accepte donc aussi
`write_specialized_resource`, et le format reste en version 1.

Le changement se limite à un `Literal` et au contrôle d'exécution
(`HISTORY_ACTIONS`). Aucun lecteur du journal n'existe (« Lu par : — »).
Contrat de stockage et documentation du journal mis à jour.

Une écriture réussie ajoute une ligne. Si l'écriture a réussi mais que le
journal échoue, `SpecializedResourceHistoryError` porte la référence et la
révision publiées, sans retry ni rollback, comme `TemplateHistoryError` de
SAFEWRITE.

## État persistant / runtime

Le harnais `WitnessSession(document, selected_tab)` sépare l'état runtime de
la ressource. **Preuve : l'état runtime du témoin est absent de la source.**
Changer `selected_tab` de 2 à 7 puis sauvegarder donne des octets et une
empreinte identiques, et `selected_tab` n'apparaît jamais dans le fichier. Le
type déclare `persistent_state` et `runtime_only_state`, et une collision
entre les deux est refusée.

**Preuve : aller-retour sans perte.** `test_full_cycle_round_trip` compare la
ressource lue avec la ressource écrite, avec accents, saut de ligne et
guillemets. Les octets du fichier sont égaux à l'encodage, et la révision lue
est égale à la révision retournée par l'écriture.

## Sécurité filesystem

Sont couverts par les tests :
- chemin hors espace, mauvais suffixe, nom vide, `..`, `.`, `//`, segment
  caché, `env`, absolu, antislash, `:`, NUL : refusés **avant tout accès** ;
- **lien symbolique** de fichier et de dossier parent : refusés ;
- FIFO : refusée sans blocage (moins de 2 s) ;
- dossier à la place du fichier : refusé ;
- **taille bornée** : un fichier de 100 octets avec `max_size = 64` est
  refusé avant lecture (`detect_calls == 0`) ;
- encodage trop grand : refusé avant publication.

La racine doit être un projet Forge (`NotForgeProjectError`).

## Tests models

`tests/test_specialized_models.py` couvre :
- outil valide et gelé, définition descriptive ;
- vocabulaire plateforme fermé, capacités d'outil distinctes ;
- concordance kebab-case avec `ToolRegistry` (11 exemples) ;
- 5 identifiants d'outil invalides ;
- 11 définitions d'outil invalides : nom, description, types vides ou
  dupliqués, capacité dupliquée ou absente, entrée UI, dépendance servant une
  capacité absente ou dupliquée ;
- dépendance et entrée UI ;
- 9 suffixes et 11 préfixes invalides ;
- 24 types invalides : `read_versions` vide ou mal typé, `write_version` hors
  ensemble, `max_size` (0, -1, booléen, flottant, au-delà de la borne),
  `editable`, niveaux, niveau bloquant inconnu, `structure` absent,
  collision persistant/runtime ;
- type en lecture seule ;
- codes d'issues acceptés et refusés, champs d'issue ;
- résultat de validation borné, blocage par niveau ;
- registre à cinq Tools, témoin non livré.

## Tests resource

`tests/test_specialized_resource.py` couvre la lecture (nominale, version
inconnue, version illisible, issues structurelles, warning, taille, 14
chemins refusés, chemin imbriqué, absence, liens, FIFO, dossier, racine,
type étranger, capacité) et l'écriture : création, création sur cible
existante, mise à jour, modification externe, mêmes octets, cible supprimée,
warning, erreur bloquante, troncature, niveau non déclaré, taille, version du
codec, capacités, lien à l'écriture, course de création, espace absent, mode
conservé, échec de `fsync`, échec du journal, catégories. S'y ajoutent
l'aller-retour et l'état runtime. Les deux fichiers totalisent **156
tests**.

## Mutations

Campagne lancée depuis le scratchpad, avec restauration vérifiée par `cmp`
après chaque mutation : **16 mutations sur 16 détectées**.

- Version inconnue acceptée.
- Chemin hors espace accepté.
- Suffixe ignoré.
- Lien de fichier suivi.
- Borne de taille ignorée.
- Validation bloquante ignorée.
- Troncature ignorée.
- Révision attendue ignorée.
- Création qui écrase la cible (contrôle d'existence et `link` retirés).
- Codec écrivant une mauvaise version.
- Écriture non journalisée.
- Niveau d'issue non déclaré accepté.
- `structure` non bloquant.
- Capacité d'outil confondue avec la plateforme.
- État runtime persisté par le codec du témoin.

Une première mutation « lien suivi » (`lstat` et `O_NOFOLLOW` retirés) a
**survécu**. Ce n'est pas une lacune : une troisième barrière, la comparaison
du fichier lu au `lstat` final, refusait encore le lien. La mutation qui
retire les trois barrières ensemble est détectée. Cette défense en profondeur
est voulue.

## Régressions

Testés et réussis (373 avec les nouveaux tests) :
- `tests/test_generate_history.py` (journal) ;
- `tests/test_safewrite_writer.py` (seul appelant du journal) ;
- `tests/test_design_io.py` ;
- `tests/test_source.py`.

Résultats globaux : voir « Validation globale finale ».

## Packaging

`forge_design.specialized` est ajouté à la liste des paquets de
`pyproject.toml`. Wheel `forge_design-0.1.0.dev0-py3-none-any.whl` dans
`tmp/wheels` (ignoré), SHA-256
`4cfae015ea28b8dbb44ca15b00e54d94f167018ffdbcedb8dad63fe08163fd3c`. Elle
contient les trois modules de `forge_design/specialized/`, et aucun fichier
« witness ».

## Installation wheel

Installation `--no-deps --no-index --target` sous `ForgeDesign/tmp/` (disque
principal, `/tmp` étant presque plein), `python -I`, origine
`…/install/forge_design/specialized/__init__.py` vérifiée. Un témoin construit
dans le script, et absent de la wheel, enchaîne :

| Étape | Résultat |
|---|---|
| Création (`expected_revision=None`) | `created=True`, référence `witness/document`, version `0.1` |
| Lecture | ressource relue, sans erreur, révision égale à celle de la création |
| Mise à jour (révision lue) | `created=False`, ressource mise à jour |
| Écriture après modification externe | `SpecializedResourceConflictError` (`conflict`), contenu externe intact |
| Journal | deux lignes `write_specialized_resource` |

## Écarts avec FD-SPECIALIZED-001

Aucune décision du contrat n'a été modifiée ni jugée impraticable. Les
précisions apportées sont consignées dans le contrat (section
« Implémentation minimale ») :
1. une issue porte son niveau de validation ;
2. une validation tronquée bloque l'écriture ;
3. `structure` est obligatoire et toujours bloquant ; un type non éditable
   n'a ni `create`, ni `edit`, ni `save` ; les capacités d'un type sont
   incluses dans celles de l'outil ;
4. une défaillance d'entrée/sortie de l'hôte n'est pas une catégorie de
   ressource (`category = None`) ;
5. l'espace de sources doit exister ;
6. la détection de version peut lire le conteneur, mais pas décoder le
   domaine.

Les catégories réellement utilisées sont `resource-not-found`,
`resource-refused`, `unsupported-version`, `invalid-resource` et `conflict`,
comme prévu par le ticket, plus `capability-unavailable`, qui découle
directement des capacités déclarées. Aucune exception de runtime, d'export ou
de dépendance n'est créée artificiellement.

## Concepts encore descriptifs

Ces concepts sont représentables dans les déclarations, mais ne sont ni
exécutés ni validés :
- `interactive-runtime` et le protocole runtime ↔ hôte ;
- l'autosave réel ;
- `export` ;
- les dépendances optionnelles (déclarées, sans sonde) ;
- l'entrée UI ;
- les capacités propres à un outil ;
- les catégories `dependency-unavailable` et `runtime-error`.

Il n'y a **aucun registre spécialisé, aucune UI et aucun runtime
interactif**.

## Fichiers créés

- `forge_design/specialized/__init__.py`, `models.py`, `resource.py`
- `tests/specialized_support.py` (outil témoin, tests seulement)
- `tests/test_specialized_models.py`, `tests/test_specialized_resource.py`
- `docs/rapports/FD-SPECIALIZED-002.md`

## Fichiers modifiés

- `pyproject.toml` : paquet `forge_design.specialized`.
- `forge_design/limits.py` : `MAX_SPECIALIZED_RESOURCE_BYTES` (64 Mio),
  `MAX_SPECIALIZED_ISSUES` (512), `MAX_SPECIALIZED_LOCATION_DEPTH` (64).
- `forge_design/generate/history.py` : action `write_specialized_resource`,
  format inchangé.
- `docs/specialized-tools/specialized-tool-contract.md` : section
  « Implémentation minimale — FD-SPECIALIZED-002 ».
- `docs/02-architecture.md` : socle exécutable.
- `docs/03-roadmap.md` : Phase 9 annotée.
- `docs/storage/storage-contract.md` : actions du journal (le type témoin
  n'est **pas** ajouté au tableau de la zone C).
- `docs/generate/template-generation.md` : actions acceptées par le journal.

Non modifiés : `platform/tool.py`, `platform/tool_registry.py`, `app.py`,
`design/`, `editor/`, `preview/`, `real_preview/`, `web/`, le JavaScript.
Aucun code de SéquenCiel ou de DrawCiel n'est copié, importé ou
translittéré.

## Validation globale finale

Ordre suivi :
1. code ;
2. tests models et resource ;
3. régressions ;
4. mutations ;
5. documentation ;
6. wheel et installation ;
7. rapport ;
8. statique final ;
9. suite globale.

| Commande | Résultat |
|---|---|
| `pytest -q tests/test_specialized_models.py tests/test_specialized_resource.py` | 156 réussis |
| Régressions (`test_generate_history`, `test_safewrite_writer`, `test_design_io`, `test_source`) avec les nouveaux tests | 373 réussis |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` / `ruff format --check .` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |
| `git diff --stat` sur `platform/`, `app.py`, `design/`, `editor/`, `preview/`, `real_preview/`, `web/` | vide |
| `pytest` (depuis le scratchpad, `--rootdir` vers le dépôt) | **4210 réussis** en 66 s, aucun échec |
| `python -m pip check` | No broken requirements found |
| `node --check` / MkDocs | N/A : aucun JavaScript, aucune configuration MkDocs |

Seul ce tableau a été ajouté au rapport après l'exécution. Les validations
statiques et la suite globale ont ensuite été relancées sur le contenu final,
avec un résultat identique.

## Conclusion

**Le contrat FD-SPECIALIZED-001 survit-il à une première implémentation
réelle ?** **Oui.**

Toutes ses décisions applicables sans runtime ont été implémentées et
éprouvées :
- déclarations ;
- capacités atomiques à deux niveaux ;
- ressource distincte du runtime ;
- version observable et refusée avant décodage ;
- issues structurées et niveaux bloquants ;
- écriture contrôlée avec révision, création exclusive et conflit ;
- journalisation ;
- espace de sources en zone C sans réservation.

Les précisions apportées sont compatibles avec le contrat et y sont
consignées. Les concepts liés au runtime, à l'export, aux dépendances et à
l'UI restent à éprouver avec un outil qui en a réellement besoin.

Le prochain ticket peut décider si un registre est nécessaire avant la
Phase 10 Circuit, ou si Circuit peut être composé explicitement.

## État Git final

Un commit sur `main`, rapport inclus, sans push.
Message : `feat: implémenter le socle des ressources spécialisées (FD-SPECIALIZED-002)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Hash :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-SPECIALIZED-002.md
```
