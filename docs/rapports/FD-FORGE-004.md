# Rapport — FD-FORGE-004

Reconnaître les projets Forge sans `bootstrap.py`. Date : 2026-10-16.

## Objectif

Corriger le défaut MAJEUR D1 relevé par [FD-AUDIT-002](FD-AUDIT-002.md) : Forge
Design 0.2.0 refusait SéquenCiel parce qu'il exigeait `bootstrap.py`, alors que
forge-mvc 1.0.0rc9 le traite comme optionnel.

Responsabilité unique : rendre `bootstrap.py` optionnel dans la reconnaissance d'un
projet Forge, sans modifier SéquenCiel.

| Décision | Résultat |
|---|---|
| A. `bootstrap.py` optionnel ? | Oui |
| B–E. `app.py`, `config.py`, `mvc/`, `mvc/routes/` obligatoires ? | Oui, tous les quatre |
| F. Détection toujours statique ? | Oui : mêmes `lstat`, aucune lecture |
| G. SéquenCiel modifié ? | Non (statut Git et mtimes identiques) |
| H. ACC-002 corrigé ici ? | Non |
| I. FD-EDITOR-008 intégré ici ? | Non |
| J. Changement de version ? | Non : reste 0.2.0 |
| K. Sonde statique SéquenCiel ? | Oui, une seule : `valid True` |
| L. Premier essai complet SéquenCiel ? | Non |

## État Git initial

| Élément | Valeur |
|---|---|
| Branche | `main` |
| HEAD | `909ceca` (FD-AUDIT-002) |
| `origin/main` | `e411d0c` ; 0 commit en retard, 14 en avance |
| Index | Vide |
| `git status --short` | 11 modifiés et 16 entrées non suivies (593 fichiers avec `--untracked-files=all`), comme à la fin de FD-AUDIT-002 |
| Collision FD-FORGE-004 | Aucune : aucun fichier `FD-FORGE-004*` ; l'identifiant n'apparaissait que comme recommandation de FD-AUDIT-002 |
| Worktrees | Dépôt principal, plus `tmp/fd-audit-002/wt`, resté de FD-AUDIT-002 (non touché) |
| Espace disque | `/` à 100 % (≈ 0,8 Gio libres), `/tmp` à 93 % |

## Baseline

**`909ceca`.** C'est `7805152` (release 0.2.0) plus le seul commit approuvé depuis :
FD-AUDIT-002, qui ne contient que de la documentation. `forge_design/`, `tests/` et
`pyproject.toml` y sont identiques à la release.

Ce choix permet aussi de partir de la roadmap déjà corrigée par l'audit.

Tout le travail a été fait dans un worktree détaché et propre :
`git worktree add --detach tmp/fd-forge-004/wt 909ceca`, avec 0 ligne de statut au
départ. Il a été piloté uniquement par chemins absolus.

## Travail concurrent exclu

Les éléments suivants sont restés dans le dépôt principal, sans y être lus pour la
qualification ni intégrés :

- **FD-EDITOR-008** : `io.py`, `editor.py`, `locking.py`, tests, `run.sh`, deux documents ;
- **FD-ACC-002** : `routes.py`, `optin_routes.py`, `route-explorer.md`, tests ;
- **FD-STABILISATION-001**, les rapports et les 571 preuves non suivis ;
- `docs/rapports/FD-CONTRACT-001.md`, modifié par l'utilisateur.

Les sept fichiers de ce ticket n'en recoupent aucun. Le worktree ne contient que la
baseline et ces fichiers.

## Défaut détecté

Sur la baseline, un projet Forge valide sans `bootstrap.py` est refusé :

```text
detect_forge_project(projet sans bootstrap.py)
→ valid=False, errors=('bootstrap.py : absent.',)
```

Conséquence : Project Inspector refuse d'ouvrir le projet, et toutes les analyses
qui exigent un projet reconnu deviennent indisponibles. SéquenCiel, créé avec Forge
1.0.0-rc.3 et sans `bootstrap.py`, était dans ce cas.

## Référence Forge rc9

La référence normative est forge-mvc 1.0.0rc9 lui-même, et non une fixture de Forge
Design. `core/app/app_factory.py::load_bootstrap` (SKELETON-BOOTSTRAP-WIRING-001,
ADR-093) dit :

> Un projet sans `bootstrap.py` n'en a pas besoin : `None`, et le comportement
> d'avant s'applique. Forge n'écrit jamais dans un projet existant (principe 9), et
> il n'y a rien à migrer.

Concrètement, `importlib.util.find_spec("bootstrap") is None` donne `None` ; sinon le
module est importé.

Le squelette rc9 installé (`skeleton/data/`) contient `bootstrap.py`. Un test copie
ce vrai squelette, le reconnaît, puis retire `bootstrap.py` et le reconnaît encore.

## Reproduction avant correction

Les tests ont été écrits **avant** toute modification du code, puis lancés sur le
code de la baseline. Résultat : **25 échecs et 157 réussites** sur
`test_project_detection.py`, `test_project_health.py` et `test_web_inspector.py`.

| Témoin | Observé sur la baseline |
|---|---|
| 1. Projet sans `bootstrap.py` | `valid=False`, `errors=('bootstrap.py : absent.',)` |
| 1 bis. Vrai squelette rc9 sans `bootstrap.py` | `valid=False`, `errors=('bootstrap.py : absent.',)` |
| 2. Projet avec `bootstrap.py` | Valide (déjà conforme) |
| 3–5. Sans `app.py`, `config.py`, `mvc/` ou `mvc/routes/` | Refusé, mais avec **deux** erreurs quand `bootstrap.py` manque aussi (`assert 2 == 1`) |
| Santé, projet sain sans `bootstrap.py` | Erreur au lieu de OK |
| HTTP, ouverture sans `bootstrap.py` | « Projet Forge non reconnu » |

Ces 25 échecs comprennent aussi les assertions déjà adaptées au nouveau contrat
(`StructureEntry("bootstrap.py", False, …, strict=True)`, « 4 / 4 »), qui échouent
logiquement sur l'ancien code.

## Cause racine

`forge_design/forge/project_detection.py`, baseline, l. 87–88 :

```python
for name in ("app.py", "bootstrap.py", "config.py"):
    check(name, directory=False, required=True)
```

Cette règle date de FD-FORGE-002, qui avait relevé les fichiers du squelette actuel
comme « Nécessaire », sans confronter ce relevé au chargement réel par Forge.

## Contrat avant

| Élément | Absent | Présent, valide | Lien, mauvais type ou invérifiable |
|---|---|---|---|
| `app.py`, `config.py`, `mvc/`, `mvc/routes/` | Erreur, projet refusé | OK | Erreur, projet refusé |
| `bootstrap.py` | **Erreur, projet refusé** | OK | Erreur, projet refusé |
| Dossiers MVC optionnels | Avertissement | OK | Avertissement |

## Contrat après

| Élément | Absent | Présent, valide | Lien, mauvais type ou invérifiable |
|---|---|---|---|
| `app.py`, `config.py`, `mvc/`, `mvc/routes/` | Erreur, projet refusé | OK | Erreur, projet refusé |
| `bootstrap.py` | **Accepté, sans message** ; information dans la santé | OK, affiché comme optionnel présent | **Erreur, projet refusé** (inchangé) |
| Dossiers MVC optionnels | Avertissement | OK | Avertissement |

Seule la case « `bootstrap.py` absent » change. Les messages existants sont inchangés,
et l'ordre des contrôles aussi : `app.py`, `bootstrap.py`, `config.py`, `mvc`,
`mvc/routes`, puis les dossiers optionnels.

## bootstrap.py optionnel

Le modèle comptait deux catégories, obligatoire et optionnel. `bootstrap.py` demande
une troisième : **optionnel strict**. Il peut manquer, mais s'il est présent, il ne
doit jamais être pris pour un fichier ordinaire alors qu'il est un lien, un dossier
ou une FIFO. Le traiter comme les dossiers MVC optionnels aurait affaibli la règle de
sécurité : un lien serait devenu un simple avertissement.

Changement minimal :

- `StructureEntry` gagne un champ `strict: bool = False`. Il est additif, avec une
  valeur par défaut, donc rétrocompatible, et ne fait pas partie des API publiques
  de modules.
- `bootstrap.py` est contrôlé avec `required=False, strict=True` :
  - absent → aucune erreur, aucun avertissement ;
  - invalide → erreur, comme avant.
- Les primitives sont inchangées : `lstat`, refus des liens, `S_ISREG`.

Il n'y a ni nouvelle lecture, ni parcours, ni import.

## Marqueurs obligatoires

`app.py`, `config.py`, `mvc/` et `mvc/routes/` restent obligatoires. `test_required`
couvre chacun, absent puis de mauvais type, **avec et sans `bootstrap.py`**
(16 cas). Il exige exactement une erreur, qui nomme le marqueur. L'absence de
`bootstrap.py` ne masque donc ni n'ajoute aucune erreur.

La liste des entrées `required` est vérifiée explicitement :
`["app.py", "config.py", "mvc", "mvc/routes"]`.

## Project Inspector

- **Ouverture** : un projet sans `bootstrap.py` est reconnu (« Projet Forge reconnu »),
  et le texte « bootstrap.py : absent. » n'apparaît nulle part dans la page.
- **Structure** (page de santé, test HTTP réel) :
  - section `data-status="ok"` ;
  - « Information : Élément optionnel absent. `bootstrap.py` » ;
  - « Éléments requis trouvés : 4 / 4 ».
- **Présent** : `bootstrap.py` figure dans « Éléments optionnels trouvés ».
- **Inchangés** : projets récents, Actualiser, Fermer.

La documentation est à jour ([Project Inspector](../tools/project-inspector.md)) :
`bootstrap.py` y est décrit comme optionnel, un `bootstrap.py` invalide reste
bloquant, avec la référence ADR-093.

`docs/02-architecture.md` n'affirme nulle part que `bootstrap.py` serait requis : il
n'est pas modifié. `docs/04-compatibilite-forge.md` liste le contenu du squelette, ce
qui reste exact : il n'est pas modifié non plus.

## Project Health

`_structure` distingue le nouveau cas, sans analyser de message :

| Cas | Diagnostic | Section |
|---|---|---|
| `bootstrap.py` absent | `info` « Élément optionnel absent. » | OK |
| `bootstrap.py` présent | Aucun ; listé parmi les optionnels trouvés | OK |
| `bootstrap.py` lien ou dossier | `error` « Élément optionnel invalide (lien ou type) : projet non reconnu. » | Erreur ; projet non reconnu, sections d'analyse indisponibles |

Tests :

- un projet sain sans `bootstrap.py` reste **OK dans les neuf sections** ;
- un projet minimal avec ou sans `bootstrap.py` donne exactement les mêmes états ;
- « Éléments requis trouvés » vaut « 4 / 4 » au lieu de « 5 / 5 ».

## SéquenCiel — sonde statique

Une seule sonde a été lancée, à la fin, une fois le code final, avec la copie du
worktree (`forge_design.__file__` dans `tmp/fd-forge-004/wt`) :

```text
detect_forge_project('/home/roger/Projets/SequenCiel')
valid True
errors ()
warnings ()
bootstrap [StructureEntry(label='bootstrap.py', required=False, state='absent', strict=True)]
required [('app.py', 'present'), ('config.py', 'present'), ('mvc', 'present'), ('mvc/routes', 'present')]
```

Rien d'autre n'a été lancé sur SéquenCiel : ni serveur, ni ouverture dans Forge
Design, ni `doctor`, `project:audit` ou `project:check`, ni preview, ni éditeur, ni
base.

Les diagnostics suivants ne relèvent pas de la détection et ne sont pas évalués ici.
Les routes devraient rester en « Attention », à cause du registre d'opt-ins actif :
c'est une limite connue, que FD-ACC-002 ne couvre pas.

## Non-écriture SéquenCiel

Relevés pris avant et après la sonde, puis comparés par `diff`, **identiques** :

- empreinte SHA-256 de `git status --short --untracked-files=all` et nombre de lignes de statut (4) ;
- mtimes et tailles de la racine, de `app.py`, `config.py`, `mvc/`, `mvc/routes/` et `mvc/routes/__init__.py` ;
- absence de `bootstrap.py`.

La mtime de la racine (2026-10-16 07:29) est antérieure à la sonde : c'est l'activité
d'une autre partie sur SéquenCiel, que la sonde n'a pas modifiée. Les 4 lignes de
statut non suivies appartiennent à ce projet ; elles ne sont pas touchées.

## Tests Python

| Fichier | Ajouts et adaptations |
|---|---|
| `test_project_detection.py` | `REQUIRED_FILES` sans `bootstrap.py` ; `test_required` paramétré avec et sans `bootstrap.py` ; entrée structurée `StructureEntry("bootstrap.py", False, "present", strict=True)` ; nouveaux tests : absent reconnu, présent affiché, invalide refusé (dossier, FIFO, lien extérieur, cassé, cyclique, intérieur), invérifiable refusé, même nombre de `lstat` sans accès au contenu, vrai squelette rc9 avec et sans `bootstrap.py` |
| `test_project_health.py` | « 4 / 4 » ; `bootstrap.py` listé parmi les optionnels ; projet sain sans `bootstrap.py` OK partout ; états identiques avec ou sans ; `bootstrap.py` lien ou dossier en erreur |

Les deux hypothèses obsolètes (« 5 / 5 » et « aucun » optionnel trouvé pour un projet
qui contient `bootstrap.py`) sont **remplacées par des valeurs exactes**, et non
supprimées : aucune assertion n'est affaiblie.

Les autres fixtures du dépôt créent `bootstrap.py` et restent valides. Elles
continuent donc de couvrir le cas « présent ».

## Tests Web

`test_web_inspector.py::test_project_without_bootstrap_is_opened` sert le projet en
HTTP réel :

- POST `/inspector` : projet reconnu, sans le texte d'absence ;
- GET `/inspector` : section Structure OK, l'information `bootstrap.py`, « 4 / 4 » ;
- accueil : le projet est courant.

Project Inspector est rendu côté serveur, sans JavaScript : cette vérification HTTP
couvre aussi le parcours sans JavaScript. Aucun navigateur ni acceptance n'a été
relancé (§49–50) ; le kit n'est pas modifié, et ses fixtures gardent `bootstrap.py`.

## Mutations

Chaque mutant est appliqué sur une **copie** de `forge_design/`, chargée par
`PYTHONPATH` ; le worktree n'est jamais modifié. Les mutants sont évalués par
`test_project_detection.py`, `test_project_health.py` et `test_web_inspector.py`.

Un témoin non muté passe d'abord : **182 réussites**.

Une première campagne avait annoncé 11 mutants tués à tort : pytest ne pouvait pas
créer son `--basetemp`, dont le dossier parent n'existait pas, et le code de sortie
était 1. L'erreur a été repérée en lisant la sortie. Le script exige désormais un
témoin vert et rejette une `FileNotFoundError` du harnais. La campagne rejouée est
celle-ci :

| Mutant | Résultat | Premier échec |
|---|---|---|
| `bootstrap.py` redevient obligatoire | Tué | `assert 2 == 1` |
| `app.py` devient optionnel | Tué | `assert not True` |
| `config.py` devient optionnel | Tué | `assert not True` |
| `mvc` devient optionnel | Tué | `assert not True` |
| `mvc/routes` devient optionnel | Tué | `assert not True` |
| `bootstrap.py` absent → avertissement de détection | Tué | Avertissements différents |
| `bootstrap.py` absent → erreur de détection | Tué | `assert 2 == 1` |
| `bootstrap.py` absent → Attention (santé) | Tué | `'attention' == 'ok'` |
| `bootstrap.py` absent → Erreur (santé) | Tué | `'erreur' == 'ok'` |
| `bootstrap.py` dossier ou lien accepté comme fichier | Tué | `assert not True` |
| `bootstrap.py` invalide → seulement Attention (santé) | Tué | `'attention' == 'erreur'` |

**11 mutants sur 11 tués.**

## Performance

Aucun parcours et aucune lecture ne sont ajoutés. `test_same_stat_calls_without_content_access`
compte les `Path.lstat` sous la racine, avec et sans `bootstrap.py` : **12 dans les
deux cas**, un par entrée, sous interdiction de `open`, `iterdir` et `rglob`.

L'ancien test `test_no_content_read_or_mutation` reste vert.

## ToolRegistry

Toujours **5 Tools**, vérifiés avec la copie du worktree :
`project-inspector`, `route-explorer`, `entity-explorer`, `debug-center`,
`template-viewer`.

## Graphic Core

Non modifié : 134/134 tests Node.

## Modules

Circuit et Flowchart ne sont pas modifiés. Le cœur ne change que la détection et la
section Structure : `forge_design/modules` et `forge_design/specialized` sont
intacts.

Real Preview, Debug Center, l'éditeur, Route Explorer et les projets récents ne sont
pas modifiés (diff limité aux sept fichiers listés plus bas).

## Dette restante

- **Correctif non publié.** Il est committé sur `main` après la release 0.2.0 et
  n'est dans aucune roue qualifiée. La version reste 0.2.0 ; le bump vers 0.2.1
  revient à FD-RELEASE-003.
- **Acceptance sans fixture sans `bootstrap.py`.** Les projets du kit ont tous
  `bootstrap.py`. Le cas n'est qualifié que par la suite Python et par HTTP.
  FD-RELEASE-003 devrait l'ajouter à la requalification.
- **Autres outils sur un projet antérieur au câblage.** Preview réelle, `doctor`,
  `audit` et `check` sur un `app.py` de type rc.3 comme celui de SéquenCiel ne sont
  pas qualifiés. Ils relèvent de l'essai réel.
- **Paquet `bootstrap/`.** Forge accepterait un paquet `bootstrap/` (`find_spec`) ;
  Forge Design le refuse, comme avant, par conservatisme. Aucun cas réel observé.
- **Combinaison avec 008 et ACC-002.** Non qualifiée dans ce ticket ; elle relève du
  jalon 0.2.1.

## Impact sur FD-AUDIT-002

- **D1, détection trop stricte : corrigée sur `main`.** SéquenCiel est reconnu par
  la détection statique. En revanche, la release 0.2.0 qualifiée reste celle de
  l'audit : sans le correctif, elle refuse toujours SéquenCiel.
- **Préparation SéquenCiel** : la cause de refus identifiée est levée dans les
  sources. L'essai réel n'a toujours pas eu lieu.
- **Verdict de l'audit** (`FORGEDESIGN_NEEDS_CONSOLIDATION`) : non réévalué ici.
  D2 (traçabilité locale, travaux non committés) reste entière.

## Recommandation ticket suivant

**FD-RELEASE-003 — jalon correctif 0.2.1**, et non FD-SEQUENCIEL-001 directement.

- Sélection Git approuvée de FD-EDITOR-008 et FD-ACC-002, au-dessus de ce commit.
- Version 0.2.1 (CORRECTIVE, `docs/release/versioning.md`).
- Une seule requalification de l'ensemble : acceptance, roue, smoke, avec un projet
  fixture sans `bootstrap.py`.

Ensuite, FD-SEQUENCIEL-001 sur la 0.2.1.

## Fichiers créés

- `docs/rapports/FD-FORGE-004.md`

## Fichiers modifiés

- `forge_design/forge/project_detection.py` : `StructureEntry.strict`, `bootstrap.py` optionnel strict, docstring.
- `forge_design/tools/project_health.py` : diagnostic d'erreur pour un optionnel strict invalide.
- `tests/test_project_detection.py`, `tests/test_project_health.py`, `tests/test_web_inspector.py`.
- `docs/tools/project-inspector.md`.
- `docs/03-roadmap.md` : piste B, état (FD-FORGE-004) et suite recommandée (jalon 0.2.1, puis essai).

Non modifiés : SéquenCiel, Circuit, Flowchart, `docs/rapports/FD-CONTRACT-001.md`,
tout le travail concurrent, `pyproject.toml`, la version.

Temporaires hors suivi Git :

- **supprimés après le commit** : le worktree `tmp/fd-forge-004/` (`git worktree
  remove`), les `--basetemp` `tmp/f4a/` à `tmp/f4d/` et `tmp/f4m/`, et le cache Ruff
  `tmp/f4-ruffcache/` ;
- **conservés** : les scripts et relevés de la sonde et des mutations, dans le
  scratchpad de la session.

Le worktree `tmp/fd-audit-002/` de FD-AUDIT-002 reste en place : il n'appartient
pas à ce ticket.

Après le commit, la suite complète a aussi été lancée sur l'arbre principal combiné,
c'est-à-dire ce ticket plus le travail non committé de 008 et ACC-002, depuis un
cwd hors dépôt. Résultat : **5 196 réussis**. C'est une information, pas une
qualification de la combinaison.

## Validation finale

Dans le worktree `909ceca` + ce ticket, contenu exact du commit :

| Commande | Résultat |
|---|---|
| `python -m compileall -q forge_design tests` | OK |
| `ruff check forge_design tests scripts` | All checks passed |
| `ruff format --check .` | 449 fichiers déjà formatés (ce rapport compris) |
| `pyright` (strict) | 0 erreur, 0 avertissement |
| `git diff --check` | OK |
| Tests ciblés : détection, Inspector, Inspector Web, santé, routes, diagnostics de routes | 356 réussis |
| `pytest` (suite complète) | **5 120 réussis** |
| `node --test tests/js/graphics/*.test.mjs` | 134/134 |
| Mutations | 11/11 tuées, témoin vert |

La suite complète est relancée après l'écriture de la documentation et de ce
rapport, parce que des tests lisent `docs/`.

## État Git final

Un commit sur `main`, au-dessus de `909ceca` :
`fix: accepter les projets Forge sans bootstrap.py (FD-FORGE-004)`.

Il est créé dans le worktree, puis intégré à `main` en avance rapide
(`merge --ff-only`). Aucun push : `origin/main` reste `e411d0c`, à 15 commits.

Le travail concurrent (11 modifiés, 582 non suivis) reste hors commit et inchangé.
La version reste 0.2.0.
