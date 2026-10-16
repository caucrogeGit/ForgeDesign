# FD-ACC-002 — Qualification du branchement `register_optins(router)`

Date : 15 octobre 2026. Projet : **ForgeDesign**.

**Verdict : correction ciblée qualifiée sur les sources, sous réserve des défauts
historiques de lint documentaire indiqués ci-dessous.** Le projet A nominal
passe de « Routes — Attention » à « Routes — OK ». B et C conservent leurs erreurs.
Un branchement absent ou incorrect reste signalé. Les registres actifs ou
personnalisés restent explicitement non résolus.

Ce résultat ne constitue ni une nouvelle acceptation globale, ni une validation
d'exécution des opt-ins. Le verdict et les autres réserves de
[FD-ACCEPTANCE-001](FD-ACCEPTANCE-001-REQUALIFICATION-RAPPORT.md) restent inchangés.
Aucun commit, push, installation, déploiement ou publication.

## Références, état initial et contrat réel

Ticket fourni : FD-ACC-002 du 15 octobre 2026. Références vérifiées :
[rapport historique](FD-ACCEPTANCE-001.md), anomalie ACC-002, rapport final ci-dessus,
[kit](../../scripts/acceptance/README.md), `build_projects.py` et ses projets A/B/C,
[contrat de lecture des routes](../tools/route-explorer.md).

Dépôt `/home/roger/Projets/ForgeDesign`, branche `main`, HEAD
`b38a2c2982ea0e6cba2db684b8a7e78a4e6db608`. Les travaux non committés 007/008,
la requalification précédente et la modification utilisateur de
`FD-CONTRACT-001.md` ont été inventoriés avant intervention :
[état Git](fd-acc-002/status-before.txt), [empreintes initiales](fd-acc-002/initial.json).
Aucun de ces travaux n'est réinitialisé ou réécrit.

Inspection en lecture seule de Forge MVC **1.0.0rc9 réellement installé** :

- `skeleton/data/mvc/routes/__init__.py` importe `register_optins` depuis
  `optins.registry`, crée le routeur, déclare les routes puis appelle
  `register_optins(router)` (ligne 23).
- `skeleton/data/optins/registry.py` déclare `BACKEND: str | None = None`,
  `ENABLED_OPTINS: dict[str, str] = {}` et une fonction retournant `None`.
  Le registre A est identique à cette forme vide ; aucun opt-in n'est activé.
- `cli/project/doctor.py::check_optin_registry` contrôle les inscriptions et
  disponibilités des paquets. Pour A, résultat réel : **ok, aucun opt-in inscrit**.
  Il ne vérifie pas l'appel racine ; il reste « ok » si cet appel est supprimé.
- `cli/optins/list.py` distingue un branchement absent comme partiel ;
  `cli/optins/enable.py` fournit l'import et l'appel à copier. Les ADR Forge
  061 et 085 ainsi que `architecture/optins-project-structure.md` confirment
  le registre visible, l'appel explicite et l'absence d'autodécouverte.

Les versions, chemins des sources importées/consultées et SHA-256 sont consignés
[dans la provenance](fd-acc-002/provenance.json). Aucun fichier du dépôt Forge,
de son installation, de SéquenCiel, Circuit ou Flowchart n'est modifié.

## Cause racine et correction retenue

Chaîne exacte avant correction :

1. `forge_design/forge/routes.py::read_routes` lit l'AST de la racine.
2. `_parse` ne reconnaît pas l'appel opt-ins ; sa branche de repli ajoute
   **« Ligne 23 : déclaration non interprétée. »**, en plus de la réserve générale.
3. `forge_design/tools/route_diagnostics.py::build_route_diagnostics` émet
   `route.partial`, sévérité `warning`.
4. `forge_design/tools/project_health.py::_routes` ne traite comme information
   que la réserve statique isolée (`len(warnings) <= 1`). Avec ce second message,
   la section devient **Attention**.

Le problème vient donc de la détection statique ForgeDesign, pas de `forge doctor`.
La limite reste légitime pour un registre actif ; elle est évitable pour le
registre vide vérifiable du squelette. Aucun contrat externe ni seuil de sécurité
n'a besoin d'être changé : aucun nouvel arbitrage n'est requis.

Correction dans **une seule couche, la détection** :

- `forge_design/forge/optin_routes.py` reconnaît la structure AST du registre vide
  conventionnel, indépendamment des commentaires, docstrings, espaces, chemins
  et noms de projets. Il n'existe aucune liste blanche des fixtures A/B/C.
- Les imports directs, la création du routeur et l'appel unique inconditionnel
  doivent être dans l'ordre. Alias, réaffectations, suppressions, imports étoilés,
  argument incorrect et appels conditionnels ou multiples ne sont pas reconnus.
- Le registre est lu comme fichier régulier, au plus `MAX_SOURCE_BYTES`, par
  des descripteurs de répertoire et `O_NOFOLLOW`, avec lecture non bloquante.
  Les liens de fichier ou de parent, FIFO, fichiers trop grands, erreurs de lecture
  ou syntaxe invalide ne produisent jamais de succès nominal.
- `read_routes` omet uniquement l'instruction prouvée vide de son analyse générique.
  Une configuration opt-ins non résolue conserve un diagnostic explicite. Une
  référence ou un registre déclaré sans appel valide ne peut plus passer au vert.
- Les projets historiques sans registre ni référence opt-ins gardent leur résultat.
  La réserve générale de lecture statique reste affichée dans tous les cas.

Ni `project_health`, ni `route_diagnostics`, ni le squelette, ni les fixtures,
ni les assertions existantes ne sont modifiés. L'écriture des designs, leurs
verrous, modèles, révisions, preview, Host/Origin/CSP et chemins check/audit
restent inchangés. La documentation de Route Explorer précise seulement la
nouvelle limite du lecteur ; elle ne redéfinit aucun contrat Forge.

## Reproduction avant/après et contre-exemples

Copies jetables des projets de la première passe du kit précédent, sans `.venv` :
`/tmp/fd-acc-002-20261015/before-*`. Leurs sources ne sont jamais exécutées.
Cette comparaison est **ciblée sur la lecture et la synthèse des routes** ;
elle n'est pas une relance du kit global ni un nouveau parcours navigateur.

| Projet | Avant | Après | Observation conservée |
|---|---|---|---|
| A nominal | Attention | **OK** | 3 routes, réserve générale uniquement |
| B volontairement erroné | Erreur | **Erreur** | 6 routes, handler dynamique, cycle Jinja et branchements non résolus |
| C volontairement erroné | Erreur | **Erreur** | 7 routes, syntaxe Jinja invalide conservée |
| A sans appel opt-ins | OK | **Attention** | Lacune antérieure révélée puis corrigée |
| A avec `other_router` | Attention | **Attention** | Mauvais argument toujours signalé |

Preuves : [avant](fd-acc-002/before.json), [après](fd-acc-002/after.json),
[lanceur reproductible](fd-acc-002/qualify.py), sources racines et registres
`*-routes.py.txt` / `*-registry.py.txt`. Les empreintes de toutes les sources des
cinq copies restent identiques après inspection. Les routes actives d'un opt-in
ne sont jamais inventées ou importées.

## Tests exécutés et boucle de correction

`tests/test_optin_routes.py` apporte **37 tests** : nominal, câblage manquant ou
ambigu, registre actif/personnalisé/invalide, frontière de lecture, code hostile,
absence d'écriture, diagnostic dynamique indépendant et projet historique.

- Avant correction : **3 échecs attendus, 32 réussites** sur les 35 premiers tests.
  Les échecs reproduisent le nominal et le défaut d'appel absent ; les cas
  invalides restaient déjà signalés. [Journal](fd-acc-002/tests-before.log).
- Une première tranche élargie a révélé **56 échecs** : l'ouverture inutile du
  répertoire projet, même sans opt-ins, violait les gardes de lecture des tests
  existants. Un filtre de métadonnées préalable élimine ces ouvertures ; la lecture
  effective reste protégée par des descripteurs et `O_NOFOLLOW`. Aucune assertion
  n'a été affaiblie. [Trace complète compressée](fd-acc-002/targeted-initial.log.gz).
- Tranche routes/diagnostics/santé/stabilité : **238 réussites**.
  [Journal](fd-acc-002/targeted-final.log).
- Première suite complète : **5 172 réussites, 1 échec** du test de frontière
  `test_single_forge_mvc_composition`. Sa recherche textuelle voyait l'exemple
  `Router()` du détecteur comme une instanciation. La description attendue est
  désormais construite en nœuds AST explicites, sans instanciation ni modification
  du test. Rejeu ciblé : **40 réussites**.
- Suite Python complète finale : **5 173 réussites en 153,38 s**.
  [Journal](fd-acc-002/pytest-full.log), [code retour](fd-acc-002/pytest-full.exit).
  Elle comprend les non-régressions de sécurité, check/audit et frontières.

Les essais hostiles utilisent des sentinelles dans le registre, les contrôleurs
et les initialiseurs de paquets : aucune n'est créée. Un succès statique ne
prétend pas qualifier l'exécution de ces initialiseurs.

## Qualité, intégrité et limites

- `ruff check forge_design tests scripts docs/rapports/fd-acc-002/qualify.py` :
  **réussi**, [journal](fd-acc-002/ruff-code.log).
- `ruff format --check .` : **réussi**, [journal](fd-acc-002/format.log).
- `pyright` sur le périmètre configuré complet : **0 erreur, 0 avertissement**,
  [journal](fd-acc-002/pyright.log).
- `git diff --check` et liens documentaires locaux : voir
  [contrôles finaux](fd-acc-002/final-checks.json).
- `ruff check .` : **28 erreurs préexistantes** dans les scripts de preuve 007/008
  (imports groupés, ordre/imports après adaptation de chemins, import inutilisé).
  [Journal complet](fd-acc-002/ruff.log). Leurs empreintes sont celles de l'état
  initial ; ils ne sont pas corrigés hors périmètre. Le lint global n'est donc
  pas déclaré réussi.

[Comparaison finale des empreintes](fd-acc-002/preservation.json) : les seuls
fichiers préexistants modifiés par ce ticket sont `forge_design/forge/routes.py`
et `docs/tools/route-explorer.md`. Ajouts : détecteur, tests, présent rapport et
ses preuves. HEAD inchangé, aucun commit concomitant pendant ce ticket.

Limites assumées : seuls les opt-ins vides dans la forme conventionnelle sans
backend sont reconnus. Un registre personnalisé pourtant valide, un backend
configuré ou des opt-ins actifs restent des limites d'analyse signalées, sans
jugement automatique sur leur bon fonctionnement. L'analyse n'exécute rien et
ne prouve pas l'identité runtime des imports, l'installation des paquets ou la
complétude de toutes les routes. Aucun paquet construit/installé ni navigateur
ne fait l'objet d'une nouvelle qualification dans ce ticket.

**Décision proposée : clore FD-ACC-002 pour le faux positif du squelette nominal,
avec cette portée statique explicite.** Les autres réserves historiques et les
défauts de lint des anciennes preuves restent indépendants.

## Rejouer

Depuis ForgeDesign, avec son environnement de test existant et un cache jetable :

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_optin_routes.py tests/test_routes.py tests/test_route_explorer_stability.py tests/test_project_health.py tests/test_route_diagnostics.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
RUFF_CACHE_DIR=/tmp/fd-acc-002-ruff .venv/bin/ruff check forge_design tests scripts docs/rapports/fd-acc-002/qualify.py
RUFF_CACHE_DIR=/tmp/fd-acc-002-ruff .venv/bin/ruff format --check .
.venv/bin/pyright
git diff --check
```

Pour les copies A/B/C et les deux cas altérés conservés dans `/tmp` :

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/rapports/fd-acc-002/qualify.py --projects /tmp/fd-acc-002-20261015 --output /tmp/fd-acc-002-replay.json
```

Les copies `/tmp` restent jetables. Les tests unitaires construisent leurs propres
projets minimaux et ne dépendent pas de leur conservation. Les fichiers de preuve
`.py.txt` sont des sources archivées, non des composants applicatifs actifs.
