# Rapport — FD-RUNTIME-004

Conserver les sorties runtime avant un délai dépassé, avec Python non tamponné. Date : 2026-10-14.

## Objectif

Ajouter `-u` aux trois commandes Forge de Debug Center (`doctor`, `project:audit`, `project:check`). Ce que le processus Python principal a déjà écrit sur stdout ou stderr doit rester disponible si la commande est ensuite interrompue au délai, sans changer le sens métier des commandes.

| Décision | Résultat |
|---|---|
| A. Nouvelle commande ? | Non |
| B. `-u` ajouté aux trois commandes ? | Oui : `-s -B -P -u -m forge <commande>` |
| C. Streaming navigateur ? | Non |
| D. Timeout modifié ? | Non : 10 s |
| E. Bornes modifiées ? | Non : 256 Kio par flux |
| F. Runner généralisé davantage ? | Non : inchangé |
| G. Résultat fonctionnel normal changé ? | Non : sorties identiques à l'octet près |
| H. Sortie pré-timeout mieux conservée ? | Oui |
| I. Nouveau Tool ? | Non |
| J. Graphic Core modifié ? | Non : 134/134 |

## État Git initial

| Élément | Valeur |
|---|---|
| HEAD | `942775f` (FD-RUNTIME-003), qui contient FD-RUNTIME-001, FD-DEBUG-006 et FD-RUNTIME-002 |
| `origin/main` | `e411d0c` ; 0 commit en retard, 6 en avance |
| Arbre | Seul `docs/rapports/FD-CONTRACT-001.md` est modifié par l'utilisateur ; il est préservé et hors commit |
| Collision | Aucune : FD-RUNTIME-004 n'apparaissait nulle part |
| Version | 0.2.0, inchangée |

## Périmètre

Le ticket ne modifie, dans le code, que les trois constantes d'argv de `forge/runtime_diagnostics.py`, plus la docstring du module. Il n'ajoute ni route, ni bouton, ni modèle, ni persistance, ni streaming, ni tâche de fond.

Côté tests :

- le faux interpréteur devient réaliste ;
- trois tests de contrat et le test « thread non démon » de FD-RUNTIME-003 sont mis à jour ;
- deux fichiers de tests sont ajoutés.

## Défaut observé

Démontré par FD-RUNTIME-003 : du code importé par `project:check` lance un thread non démon. Le processus ne se termine pas et le délai est dépassé. Le rapport et tout ce qui a été imprimé restent dans le tampon de stdout, jamais vidé, et sont donc **perdus**. Stderr est vidé à chaque ligne, mais perd sa dernière ligne incomplète.

## Reproduction avant ticket

Vrai `project:check` sur le squelette Forge (`bufproj`). Ses routes impriment des lignes, un secret, un fragment sans saut de ligne sur stdout et sur stderr, puis lancent un thread non démon. Délai de 3 s, avec le runner réel. La colonne « avec `-u` » utilise un lanceur qui insère `-u` avant `-m`.

| | stdout | stderr |
|---|---|---|
| Avant (`-s -B -P -m`) | **vide** | `ERREUR AVANT TIMEOUT\n` (`ERR-SANS-LF` perdu) |
| Avec `-u` | `AVANT TIMEOUT`, `DB_PASSWORD=[masqué] avant blocage`, `SANS-LF`, puis le rapport complet | `ERREUR AVANT TIMEOUT\nERR-SANS-LF` |

## Pourquoi -u

`-u` force les flux stdout et stderr du Python principal à ne pas être tamponnés : chaque écriture part immédiatement dans le tube, même sans saut de ligne. Le runner, qui draine les deux tubes en continu, possède donc déjà les données au moment du délai. Le line buffering seul ne suffirait pas : le fragment sans saut de ligne de stderr était perdu.

`-u` ne garantit **pas** le vidage d'un processus enfant lancé par le projet (un `python enfant.py` garde sa propre politique), d'une bibliothèque native, ni d'un fichier écrit par le projet.

## Commandes avant

```text
<python> -s -B -P -m forge doctor
<python> -s -B -P -m forge project:audit
<python> -s -B -P -m forge project:check
```

## Commandes après

```text
<python> -s -B -P -u -m forge doctor
<python> -s -B -P -u -m forge project:audit
<python> -s -B -P -u -m forge project:check
```

## Position de -u

`-u` est placé **avant** `-m`. Après `-m forge`, il deviendrait un argument de Forge et non de Python. Un test exige l'argv exact et l'ordre `-u` avant `-m`. La mutation « `-u` après `-m` » est tuée par ce test, et aussi par le seul test comportemental, puisque la sortie est alors perdue.

## Runner

Inchangé (§17-19) : `Popen`, sélecteur, tubes, drainage continu, délai, `killpg`, `wait`, `clean_output`, `redact_debug_text`. Les tests n'ont montré aucun défaut du runner : ce qu'il a lu avant le délai était déjà conservé. Seule la mise en tampon côté enfant posait problème. Aucun « drainage final » n'a été ajouté.

## stdout

Lignes et fragment final sans saut de ligne conservés, dans l'ordre reçu. Test : `stdout == "AVANT TIMEOUT\nDB_PASSWORD=[masqué] avant blocage\nSANS-LF"`, pour les trois commandes.

## stderr

Conservé indépendamment, fragment sans saut de ligne compris : `stderr == "ERREUR AVANT TIMEOUT\nERR-SANS-LF"`. L'ordre entre stdout et stderr n'est pas garanti, puisque ce sont deux tubes indépendants ; l'ordre au sein d'un flux l'est.

## Sortie sans newline

`print("SANS-LF", end="")` sur stdout et `print("ERR-SANS-LF", end="", file=sys.stderr)` sont récupérés avec `-u`. Sans `-u`, la même mécanique les perd ; c'est la preuve contraire.

## Timeout

10 s, inchangé. Messages inchangés : « Diagnostic interrompu », « Audit interrompu », « Vérification interrompue : délai dépassé. ». `timed_out=True`, `exit_code=None`, et la sortie acquise est présente.

## Groupe de processus

Inchangé : `SIGKILL` au groupe. Test : un enfant `sh` du groupe écrit « ENFANT AVANT TIMEOUT » puis reste actif. Sa sortie est conservée avec celle du parent, puis l'enfant est tué au délai. Après les scénarios navigateurs, aucun processus n'a pour dossier courant le projet.

## Enfant détaché

Limite de FD-RUNTIME-003 inchangée : un processus que le projet détache dans une nouvelle session sort du groupe et peut survivre. `-u` n'y change rien.

## Bornes

256 Kio par flux, inchangé. Test : 1 Mio écrit avant le blocage donne 256 Kio gardés et 786 432 octets comptés, puis le délai et l'arrêt du groupe, sans interblocage.

## Troncature

Même comportement : surplus lu, jeté et compté (`stdout_truncated`).

## ANSI

Même `clean_output`.

## Masquage

Le pipeline est inchangé : octets → UTF-8 → `clean_output` → `redact_debug_text` → Jinja. Une valeur sensible écrite avant le délai est masquée (`DB_PASSWORD=[masqué] avant blocage`) et n'apparaît ni dans le résultat, ni dans le HTML (tests, navigateurs). La mutation « sortie partielle non masquée » est tuée.

## Environnement

Inchangé : `child_environment` n'est pas modifié. `PYTHONUNBUFFERED` n'est ni utilisé ni transmis. Test : un parent qui le définit ne le transmet pas, et `-u` suffit. La mutation « `-u` remplacé par `PYTHONUNBUFFERED` » est tuée par le test d'argv exact et, comportementalement, par la preuve contraire : la sortie n'y est plus perdue sans `-u`.

## Doctor

Vrai `doctor` : sorties identiques avec et sans `-u` sur trois projets, avec les mêmes codes (0, 1, 0) et le même temps (médianes 99/98, 117/117, 117/118 ms).

## project:audit

Identique avec et sans `-u` sur les mêmes trois projets : codes 0, médianes 86 à 88 ms.

## project:check

Identique avec et sans `-u` en exécution normale (codes 0, 1, 1 ; médianes 91 à 104 ms). Bloqué, il conserve désormais sa sortie. Le test « thread non démon » de FD-RUNTIME-003 est mis à jour : le rapport, les secrets masqués et stderr sont présents.

## Résultats fonctionnels avant/après

En exécution normale, codes retour, messages, stdout, stderr et effets de bord sont identiques **à l'octet près**. Les sorties de Forge ne contiennent ni horodatage ni durée, ce qui permet une comparaison exacte. Deux vérifications :

- en ligne de commande, 9 combinaisons (3 projets × 3 commandes) ;
- dans les tests, avec le vrai Forge et le runner (avec `-u`, et sans `-u` via un lanceur) pour les trois commandes.

## Tests Python

**Faux interpréteur réaliste.** `.venv/bin/python` applique au vrai Python les options placées avant `-m` (`-s -B -P -u`) et transmet l'argv complet au faux CLI. Retirer `-u` change donc réellement la mise en tampon. Trois nouveaux modes : `partial`, `partial-big` et `partial-child`.

`tests/test_runtime_unbuffered.py` (13 tests) :

- argv exact des trois commandes, `-u` avant `-m` ;
- `test_unbuffered_output_is_preserved_before_timeout`, pour les trois commandes : lignes, secret masqué, fragments sans saut de ligne sur les deux flux ;
- `test_same_output_is_lost_without_u`, même mécanique sans `-u` : stdout vide, fragment de stderr perdu ;
- plus de 256 Kio avant le délai : bornes et surplus ;
- enfant du groupe : sortie conservée, enfant tué ;
- `PYTHONUNBUFFERED` ni nécessaire ni transmis ;
- vrai Forge : sorties identiques avec et sans `-u`, pour les trois commandes.

Tests de contrat mis à jour : `test_runtime_diagnostics`, `test_runtime_audit` et `test_runtime_project_check` (argv), plus le test du thread non démon.

## Tests Web

`tests/test_web_runtime_unbuffered.py` (3 tests, un par section) : délai dépassé, puis la page affiche le message de délai, la sortie déjà émise (stdout et stderr, fragments compris) et le secret masqué ; les deux autres sections restent « non exécutées ». Aucun changement de gabarit n'a été nécessaire.

## Mutations

Script hors dépôt, lancé depuis le scratchpad, avec restauration à l'octet et empreinte vérifiée. Résultat : **10/10 tuées**.

| Mutation | Tuée par |
|---|---|
| `-u` retiré de `doctor` | `test_exact_argv_puts_u_before_m` ; seul : `test_unbuffered_output_is_preserved_before_timeout[doctor]` |
| `-u` retiré de l'audit | idem ; seul : `…[project:audit]` |
| `-u` retiré de la vérification | idem ; seul : `…[project:check]` |
| `-u` après `-m` (argument de Forge) | idem ; seul : `…[project:check]` |
| `-u` remplacé par `PYTHONUNBUFFERED` | idem ; seul : `test_same_output_is_lost_without_u` |
| Runner qui ignore la sortie acquise au délai | `test_unbuffered_output_is_preserved_before_timeout` |
| stdout perdu au délai | idem |
| stderr perdu au délai | idem |
| Sortie partielle non masquée | idem |
| Borne ignorée (sortie volumineuse avant délai) | `test_large_output_before_timeout_is_bounded` |

Les cinq mutations sur `-u` ont été rejouées **sans** les tests d'argv littéral : les seuls tests comportementaux les tuent toutes. La garde ne tient donc pas uniquement à une comparaison de chaîne.

## Chromium

Conditions :

- roue 0.2.0 dans un venv neuf, vraie commande `forge-design` ;
- projet `bufproj` (vrai squelette Forge et son `.venv`), dont les routes impriment puis bloquent sur un thread non démon.

Scénario, 5/5 :

1. ouverture : trois commandes présentes, non exécutées ;
2. vrais audit et `doctor` : résultats normaux inchangés. Ils n'importent pas les routes, donc ni « AVANT TIMEOUT » ni blocage ;
3. vrai `project:check` : **vraie attente du délai de 10 s** (10,12 s mesurés), groupe arrêté, état « Vérification interrompue : délai dépassé. », code « — ». Stdout commence par `AVANT TIMEOUT`, `DB_PASSWORD=[masqué] avant blocage`, `SANS-LF`, et contient le rapport complet jusqu'à « Tout est conforme. » ; stderr vaut `ERREUR AVANT TIMEOUT\nERR-SANS-LF`. Aucune valeur sensible dans le HTML ;
4. aucune erreur JavaScript ;
5. projet inchangé.

Ce scénario n'est joué qu'une fois par navigateur et variante critique.

## Firefox

Même scénario, 5/5 (10,15 s d'attente).

## Sans JavaScript

Firefox avec `javascript.enabled=false` : vrai POST natif de la vérification, vraie attente de 10 s, état « interrompue ». La sortie déjà produite est lisible (XPath : « AVANT TIMEOUT », « DB_PASSWORD=[masqué] avant blocage », « SANS-LF », « ERR-SANS-LF ») et aucune valeur sensible n'apparaît.

## Performance

| Mesure | Sans `-u` | Avec `-u` |
|---|---:|---:|
| `doctor` (3 projets, médianes) | 99 / 117 / 117 ms | 98 / 117 / 118 ms |
| `project:audit` | 86 / 87 / 88 ms | 86 / 87 / 88 ms |
| `project:check` | 104 / 92 / 91 ms | 104 / 91 / 91 ms |
| 1 Mio par flux (faux interpréteur, 10 exécutions) | médiane 36 ms, pire 38, écart 3 | médiane 36 ms, pire 37, écart 2 |

Le surcoût est négligeable. La mémoire est inchangée : même plafond de 256 Kio par flux.

## ToolRegistry

Cinq Tools, inchangés.

## Graphic Core

Aucune modification ; 134/134 tests Node.

## Modules externes

Circuit et Flowchart non modifiés. Le scénario Chromium complet, avec les deux modules activés, donne 5/5.

## Dette / limites

- **Python principal seulement.** `-u` ne contrôle que le Python principal ; un sous-processus Python ou natif lancé par le projet garde sa mise en tampon.
- **Pas de streaming.** La réponse reste celle d'un POST synchrone, affichée à la fin.
- **Enfant détaché.** Un processus détaché par le projet reste hors de la garantie d'arrêt.
- **Échéance exacte.** Un octet écrit dans les toutes dernières microsecondes avant l'échéance peut ne pas avoir été lu. Aucun cas observé.

## Recommandation ticket suivant

La piste Runtime de Debug Center est stabilisée : trois commandes, une frontière de confiance démontrée, des sorties conservées. Recommandation : **Phase 12 (intégration applicative)**, ou une revue de cohérence du manuel utilisateur sur les trois niveaux de confiance.

## Fichiers créés

- `tests/test_runtime_unbuffered.py`
- `tests/test_web_runtime_unbuffered.py`
- `docs/rapports/FD-RUNTIME-004.md`

## Fichiers modifiés

- `forge_design/forge/runtime_diagnostics.py` (trois constantes d'argv et docstring)
- `tests/runtime_diagnostics_support.py` (faux interpréteur réaliste, trois modes)
- `tests/test_runtime_diagnostics.py`, `tests/test_runtime_audit.py`, `tests/test_runtime_project_check.py` (argv, thread non démon)
- `docs/tools/debug-center.md`
- `docs/03-roadmap.md`

`docs/02-architecture.md` n'est pas modifié : il ne décrit pas le runner runtime, seulement le partage de `project_python.py` avec la preview réelle, qui ne change pas.

## Validation finale

| Commande | Résultat |
|---|---|
| `python -m compileall -q forge_design tests` | OK |
| `ruff check forge_design tests` | All checks passed |
| `ruff format --check .` | OK |
| `pyright` (strict) | 0 erreur, 0 avertissement |
| `git diff --check` | OK |
| `pytest` (suite complète) | 5 024 passed |
| `node --test tests/js/graphics/*.test.mjs` | 134/134 |
| Roue 0.2.0, venv neuf | `pip check` OK |
| Chromium, Firefox, Chromium + modules | 5/5 chacun, vraie attente de 10 s |
| Firefox sans JavaScript | OK |
| Mutations | 10/10 tuées, dont 5/5 par les seuls tests comportementaux |

## État Git final

Un seul commit : `fix: préserver les sorties runtime avant timeout (FD-RUNTIME-004)`, au-dessus de `942775f`. Il n'a pas été poussé. `docs/rapports/FD-CONTRACT-001.md` reste modifié localement, hors commit. La version reste 0.2.0.
