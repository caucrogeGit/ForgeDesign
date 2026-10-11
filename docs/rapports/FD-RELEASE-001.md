# Rapport — FD-RELEASE-001

## Objectif

Permettre à Forge Design de détecter, **avant l'usage**, qu'un module exige une
version du cœur plus récente que celle installée, en séparant clairement trois
notions : version de distribution du cœur, `MODULE_API_VERSION`, versions du
cœur acceptées par un module.

Résultat démontré :

```text
module compatible            → s'installe, s'active, fonctionne (Circuit, 5 scénarios, 2 navigateurs)
module incompatible (pip)    → refusé par pip (ResolutionImpossible)
environnement forcé          → Forge Design démarre, refuse proprement le module,
                               affiche un diagnostic explicite, les autres modules fonctionnent
```

Décisions validées : version **0.2.0** ; source autoritaire
`forge_design.__version__` ; champ `requires_forge_design: str | None = None`,
validé en deux niveaux ; diagnostics `descriptor-invalid`,
`core-version-incompatible`, `core-version-unknown`, `api-incompatible`
(inchangé), `module-import-failed` ; préversions acceptées dans l'intervalle ;
`activate_modules(..., core_version=...)` réservé à l'hôte et aux tests ;
Circuit `>=0.2.0,<1` avec règle 0.x normative ; **`MODULE_API_VERSION` reste 1**.

## État Git initial

| Dépôt | État |
|---|---|
| Forge Design | `3fcb51d` (FD-ARCH-001) sur `44ded4b` (FD-GRAPHICS-EDIT-002) ; `origin/main` = `691e83e` ; 2 commits locaux ; seul `docs/rapports/FD-CONTRACT-001.md` modifié (hors commit, préservé) |

## État Circuit

`6627212` (FDC-EDIT-007) ; `origin/main` = `536adfc` ; 5 commits locaux
(FDC-EDIT-003 à 007) ; arbre propre.

## Problème de compatibilité

Le cœur a gagné des capacités publiques (actions, script d'édition,
`nodeMove`, `addOverlay`, `worldAt`, `onViewChange`) sans changer de version
(`0.1.0.dev0`) ; Circuit, qui les utilise, déclarait
`forge-design>=0.1.0.dev0,<0.2` — contrainte fausse : elle acceptait un cœur
de l'époque de l'extraction, sans ces capacités, et refuserait un cœur `0.2.0`.
Un module mal assorti échouait tard (import, `attach`, « addOverlay is not a
function »).

## Version de distribution actuelle

`0.1.0.dev0` depuis FD-FOUNDATION-002, jamais publiée.

## Historique des versions

Aucun tag Git, aucune publication, une seule version jamais changée
(`0.1.0.dev0`). Circuit (`0.1.0`) avait fixé `<0.2` à l'extraction
(FD-MODULES-003) : « 0.1 » désignait le cœur hôte de modules en consultation
seule. Aucune politique de version écrite avant ce ticket.

## Politique de versionnement

Créée : [docs/release/versioning.md](../release/versioning.md). SemVer en forme
PEP 440 (`MAJEURE.MINEURE.CORRECTIVE`, préversions `aN`, `bN`, `rcN`, `.devN`) ;
MINEURE = capacité publique additive compatible ; CORRECTIVE = correction
compatible ; MAJEURE = rupture volontaire. **Règle 0.x normative** : en 0.x, une
MINEURE reste additive et compatible ; la rupture d'une API publique supportée
n'est jamais une simple MINEURE 0.x mais une MAJEURE et/ou un nouveau
`MODULE_API_VERSION`, selon la frontière rompue — ce qui rend légitime une
contrainte `>=0.Y,<1`. Ce n'est pas une promesse 1.0. Dépréciation (politique
documentaire), ordre de publication, procédure d'ajout d'une capacité.

## Distribution version vs MODULE_API_VERSION

| | Décrit | Valeur |
|---|---|---|
| `forge_design.__version__` | Version publiée du produit | `0.2.0` |
| `MODULE_API_VERSION` | Forme majeure du contrat des modules | `1` (inchangé) |
| `requires_forge_design` | Versions du cœur acceptées par un module | Circuit : `>=0.2.0,<1` |

Diagnostics séparés : `api-incompatible` (contrat majeur non supporté, vérifié
en premier) ≠ `core-version-incompatible` (contrat compris, implémentation du
cœur hors intervalle) ≠ `module-import-failed` (descripteur jamais obtenu).

## Source autoritaire de version

`forge_design.__version__` (déjà unique : `pyproject.toml` la lit par
`version = {attr = "forge_design.__version__"}`), conservée plutôt que
`importlib.metadata` : elle fonctionne depuis le checkout sans installation et
ne demande aucun repli. Chaîne vérifiée :

```text
forge_design.__version__ = 0.2.0
  = version lue par pyproject (attr, aucune version écrite en double ; test)
  = métadonnée installée importlib.metadata.version("forge-design") (test)
  = METADATA de la roue : Version: 0.2.0 (validation)
  = forge-design --version → « Forge Design 0.2.0 » (test, roue installée)
```

`test_version_has_a_single_authoritative_source` a d'ailleurs détecté une copie
de la chaîne dans un commentaire d'exemple, remplacée par une forme générique.
`__version__` n'est pas un ajout : il existait (CLI).

## Contrat requires_forge_design

`ModuleDescriptor.requires_forge_design: str | None = None`, dernier champ
(positions inchangées), facultatif et additif.

```python
ModuleDescriptor(..., api_version=1, requires_forge_design=">=0.2.0,<1")
```

## PEP 440

`packaging.specifiers.SpecifierSet` (dépendance déclarée du cœur), sans
réimplémentation. Testés : `>=0.2.0`, `==0.2.0`, `>=0.2.0,<1`, `>=0.2,<0.4`,
`~=0.2.0`, `~=0.3`, `==0.2.*`. Préversions acceptées si elles sont dans
l'intervalle (`prereleases=True`, comme `pip check` pour une version
installée) :

| Cœur | Exigence | Résultat |
|---|---|---|
| `0.2.0.dev0` | `>=0.2.0` | incompatible (précède 0.2.0) |
| `0.2.0rc1` | `>=0.2.0` | incompatible |
| `0.2.0` | `>=0.2.0` | compatible |
| `0.3.0.dev0` | `>=0.2.0` | compatible |
| `1.0.0.dev0` | `>=0.2.0,<1` | incompatible |
| `1.0.0` | `>=0.2.0,<1` | incompatible (trop récent) |

## Module sans contrainte

`None` : aucune contrainte au-delà de `MODULE_API_VERSION` ; les modules API 1
antérieurs restent activables (témoins `witness` et `flow` sans contrainte :
inchangés). La documentation recommande fortement de déclarer la contrainte.

## Validation descriptor

Deux niveaux : le descripteur n'accepte que `None` ou un texte non vide,
imprimable, d'au plus 200 caractères (sinon `ValueError` à la construction,
comme tout champ) ; l'activation construit le `SpecifierSet`. Un spécificateur
syntaxiquement faux (`">=deux"`) donne `descriptor-invalid` :
« requires_forge_design invalide : '>=deux' (spécificateur PEP 440 attendu). »

## Activation compatible

`activate_modules` compare `forge_design.__version__` (ou `core_version`, paramètre
nommé réservé à l'hôte et aux tests) au spécificateur après la vérification
d'API et avant toute autre étape ; dans l'intervalle, activation normale.

## Activation incompatible

Hors intervalle : `core-version-incompatible`, module non activé, aucun effet
(ni navigation, ni routes, ni assets, ni actions, ni type de ressource, ni
script). Version du cœur illisible et module contraint : `core-version-unknown`
(« fail closed ») ; un module non contraint reste activé.

## Diagnostics

| Code | Message |
|---|---|
| `core-version-incompatible` | `Le module « circuit » nécessite forge-design >=0.3.0,<1 ; version installée : 0.2.0.` |
| `core-version-unknown` | `Le module « bound » nécessite forge-design >=0.2.0 ; version de Forge Design indéterminée.` |
| `descriptor-invalid` | `requires_forge_design invalide : '>=deux' (spécificateur PEP 440 attendu).` |

Messages bornés (spécificateur ≤ 200 caractères), stables (tests exacts),
affichés comme les autres : stderr au démarrage, bloc « Modules non chargés »
de l'accueil. Aucune route dédiée.

## Isolation des modules

Compatible, incompatible, compatible : les deux compatibles actifs, un seul
diagnostic, attribué au bon paquet. Web : le module incompatible renvoie 404
sur sa page, sa ressource, son asset et son action ; le compatible fonctionne.
Démarrage : un module incompatible ne l'empêche jamais (politique existante :
seule une configuration malformée est fatale).

## Import failure avant descriptor

Un module qui importe un symbole absent du cœur échoue **avant** que l'hôte
lise son descripteur : `module-import-failed` (testé avec
`ImportError: cannot import name 'NewFeature'`), jamais présenté comme une
incompatibilité de version. Constat réel (C1 ci-dessous) : le Circuit actuel sur
le cœur `c308c6c` échoue ainsi (`ImportError`, il importe `ModuleAction`, absent
de ce cœur).

## Limite de la vérification runtime

La vérification à l'activation ne protège que les cœurs qui la contiennent
(≥ 0.2.0) et les modules dont l'import réussit. **`Requires-Dist` est la
première barrière** ; le descripteur est une seconde défense (installation
manuelle, `--no-deps`, éditable, environnement cassé, métadonnée inattendue).
Documenté dans la politique de version et le contrat des modules.

## Dépendance packaging

`packaging>=24.0` était déjà une dépendance déclarée du cœur. Le garde de
contrat de `forge_design/modules/` (FD-ARCH-001) autorise désormais
explicitement `packaging.specifiers`, `packaging.version` et `forge_design`
(version), avec commentaire ; aucune autre dépendance.

## Cohérence descriptor / Requires-Dist

Circuit expose `FORGE_DESIGN_REQUIREMENT = ">=0.2.0,<1"`, utilisé par le
descripteur ; `test_core_requirement_matches_the_distribution_dependency`
compare ce spécificateur à `pyproject.toml` **et** à la métadonnée installée
(`Requires-Dist: forge-design<1,>=0.2.0`). Le cœur ne lit jamais le
`pyproject.toml` d'un module.

## Module Circuit

Commit séparé, après celui du cœur : `pyproject.toml`
`forge-design>=0.2.0,<1`, `requires_forge_design=FORGE_DESIGN_REQUIREMENT`, test
de cohérence, README (contrainte, deux barrières, ordre de publication).
658 tests, Pyright, Ruff, `pip check` propres. Version du module inchangée
(`0.1.0`).

## Witness modules

`tests/flow_witness/` reçoit un paramètre `requires` ; tests autonomes, sans
dépendance au dépôt Circuit : matrice de versions, spécificateurs invalides,
version inconnue, modules mélangés, API et version séparées, absence d'effet en
hôte et en Web.

## Metadata wheel

| Roue | `Version` | `Requires-Dist` (forge-design) |
|---|---|---|
| `forge_design-0.2.0-py3-none-any.whl` | `0.2.0` | — (`packaging>=24.0`, `forge-mvc==1.0.0rc9`, `jinja2==3.1.6`, `pydantic<3,>=2`) |
| `forge_design_circuit-0.1.0-py3-none-any.whl` | `0.1.0` | `forge-design<1,>=0.2.0` |
| ancienne roue du cœur (`c308c6c`, export hors dépôt) | `0.1.0.dev0` | — |
| variante temporaire `forge_design_circuit-0.1.0+future` (hors dépôt) | `0.1.0+future` | `forge-design<1,>=0.3.0` |

## Tests pip compatible

Venv neuf A : cœur 0.2.0 + Circuit → installation et `pip check` propres ;
`forge-design --version` → `Forge Design 0.2.0`.

## Tests pip incompatible

Venv neuf B : ancienne roue du cœur (`0.1.0.dev0`) + nouveau Circuit →
`ERROR: Cannot install forge-design 0.1.0.dev0 … and forge-design-circuit==0.1.0
because these package versions have conflicting dependencies` /
`ResolutionImpossible`, code 1, rien installé.

## Tests runtime forcés

| Venv | Contenu | `pip check` | Démarrage | Diagnostic | Autres modules |
|---|---|---|---|---|---|
| C1 | cœur `c308c6c` (0.1.0.dev0) + Circuit `--no-deps` | signale l'incohérence | Forge Design démarre, arrêt propre | `module-import-failed : ImportError` (limite : le cœur ancien ne connaît ni la vérification ni les symboles) | — |
| C2 | cœur 0.2.0 + Circuit exigeant `>=0.3.0,<1` (`--no-deps`) + témoin flowchart installable | signale l'incohérence | Forge Design démarre, arrêt propre | `core-version-incompatible : Le module « circuit » nécessite forge-design >=0.3.0,<1 ; version installée : 0.2.0.` (stderr et accueil) | témoin flowchart : `/modules/flow/` 200 ; Circuit : 404 |

## Chromium

Environnement forcé C2, vraie commande, **5/5** : accueil (navigation du cœur
inchangée, seul le témoin compatible listé, diagnostic d'incompatibilité
visible) ; Circuit sans page, ressource, asset ni action (404) ; témoin
compatible (calque, action, rechargement, fichier modifié) ; Route Explorer ;
aucune exception ni violation CSP. Environnement compatible A, vraie commande
avec Circuit : déplacement 12/12, connexion 10/10, dérivation 12/12, fil → fil
10/10, évitement 5/5.

## Firefox

Mêmes parcours : C2 5/5 ; A 12/12, 10/10, 12/12, 10/10, 5/5.

## Régressions FD-ARCH-001

Tous les tests de frontière passent (`test_module_boundaries.py`,
`test_modules_contract.py`) ; `ToolRegistry` : cinq outils ; navigateurs
`reg.mjs` 7/7 Chromium, 6/6 Firefox, sans JavaScript ; validation
multi-modules (témoins + Circuit) 5/5 dans les deux navigateurs. Aucune logique
Circuit, aucune dépendance cœur → module.

## Mutations

**12/12 tuées** : contrôle de compatibilité ignoré ; comparaison inversée ;
spécificateur invalide accepté ; module incompatible quand même activé (routes,
assets exposés) ; version d'API confondue avec la version du cœur ; version du
cœur inconnue supposée compatible ; diagnostic attribué au mauvais module ;
préversions refusées ; version par défaut non autoritaire ; forme du
spécificateur non contrôlée ; contrôle retiré (ordre) ; API vérifiée après la
version du cœur.

## Performance

Une comparaison à l'activation : activation d'un module 4,5 µs sans contrainte,
16,3 µs avec (`SpecifierSet` construit une fois par module). Négligeable ;
aucune incidence sur les pages ni le Graphic Core.

## Documentation

- `docs/release/versioning.md` (nouveau, normatif) : trois notions, source
  autoritaire, politique et règle 0.x, déclaration d'un module, vérification,
  limite, nouvelle capacité, dépréciation, ordre de publication, hors périmètre.
- `docs/modules/module-architecture.md` : champ du descripteur, compatibilité,
  diagnostics, versioning.
- `docs/modules/module-host.md` : diagnostics au démarrage.
- `docs/architecture/core-module-boundaries.md` : règle 11 (versions séparées)
  et sa garde.
- `docs/03-roadmap.md` : piste A à jour, FD-RELEASE-001 fait.
- `README.md` : renvoi vers la politique de version.

## Version retenue

**0.2.0** : la coupure entre le cœur hôte de modules en consultation
(`0.1.0.dev0`, base de la contrainte `<0.2` d'origine de Circuit) et le cœur
portant les capacités d'édition distribuées. Version finale, supérieure à
toutes les roues `0.1.0.dev0` en circulation. Les installations éditables
doivent être réinstallées pour rafraîchir leur métadonnée (fait, en mode
`compat` pour l'environnement de Circuit : le mode par défaut de setuptools passe
par un import hook que Pyright ne suit pas).

## MODULE_API_VERSION

Reste **1** : `requires_forge_design` est facultatif et additif ; un module API 1
sans ce champ fonctionne à l'identique. Une politique de distribution ne crée
pas une nouvelle génération du contrat.

## Ordre de publication

1. Publier `forge-design 0.2.0`.
2. Publier ensuite `forge-design-circuit` (`Requires-Dist: forge-design<1,>=0.2.0`).

Jamais l'inverse. Aucun tag créé, aucune publication, aucun push.

## Fichiers créés

- `docs/release/versioning.md`
- `docs/rapports/FD-RELEASE-001.md`
- `tests/test_module_version_compatibility.py`
- `tests/test_packaging.py`

## Fichiers modifiés

Cœur : `forge_design/__init__.py` (`0.2.0`), `forge_design/modules/descriptor.py`
(`requires_forge_design`), `forge_design/modules/activation.py` (vérification,
diagnostics, `core_version`), `tests/flow_witness/__init__.py`,
`tests/test_modules_contract.py` (garde d'imports), `tests/test_import.py`,
`README.md`, `docs/03-roadmap.md`, `docs/architecture/core-module-boundaries.md`,
`docs/modules/module-architecture.md`, `docs/modules/module-host.md`.

Circuit : `pyproject.toml`, `forge_design_circuit/__init__.py`,
`tests/test_module.py`, `README.md`.

## Commits

| Ordre | Dépôt | Message |
|---|---|---|
| 1 | Forge Design | `feat: versionner la compatibilité des modules (FD-RELEASE-001)` |
| 2 | ForgeDesign-Circuit | `chore: déclarer la version minimale de Forge Design` |

## Validation finale

| Contrôle | Forge Design | ForgeDesign-Circuit |
|---|---|---|
| `compileall`, Ruff, `ruff format --check`, Pyright strict, `git diff --check` | Réussis | Réussis |
| Pytest | **4 631** réussis (4 593 + 38) | **658** réussis (657 + 1) |
| Node | Graphics 134 réussis | `circuit-editor.test.mjs` 44 (dans pytest) |
| `pip check` | Propre (développement) | Propre (développement) |
| Mutations | 12/12 tuées | — |
| Roues et venvs neufs | A compatible, B refusé par pip, C1 et C2 forcés | idem |
| Navigateurs | C2 5/5 ×2 ; régressions FD-ARCH-001 | A : 5 scénarios ×2 |

## État Git final

- Forge Design : `3fcb51d` + commit FD-RELEASE-001, **non poussé** ;
  `docs/rapports/FD-CONTRACT-001.md` toujours modifié, hors commit, non restauré.
- ForgeDesign-Circuit : `6627212` + commit de déclaration de version,
  **non poussé**.
- Aucun tag ; aucun serveur ni navigateur laissé ouvert ; roues, venvs et
  exports temporaires dans le dossier de travail, hors des dépôts.
