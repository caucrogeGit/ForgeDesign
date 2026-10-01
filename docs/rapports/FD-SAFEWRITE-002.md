# Rapport — FD-SAFEWRITE-002

## Ticket et objectif

Traduire le résultat de `detect_template_change` en un ensemble borné de choix
explicites, puis valider le choix de l'utilisateur. Aucune écriture, aucun choix
appliqué, aucun choix par défaut.

## État Git initial

`main` synchronisée avec `origin/main` à `c4add6b` — FD-SAFEWRITE-001.
Seule modification préexistante : `docs/rapports/FD-CONTRACT-001.md`,
préservée hors commit.

## API publique

Ajoutée aux exports de `forge_design.safewrite` : `SafeWriteChoice`,
`SafeWriteDecisionOptions`, `SafeWriteDecision`, `decision_options`,
`select_safe_write_choice` et `has_write_conflict`. Ce dernier est rendu public
pour la lisibilité du futur Web. Les exports de FD-SAFEWRITE-001 sont inchangés.

## SafeWriteChoice

`Literal["proceed", "cancel", "regenerate", "save_as", "mark_manual"]`.
`SafeWriteDecisionOptions(path, status, choices)` et
`SafeWriteDecision(path, status, choice)` sont des dataclasses gelées. Les
statuts réutilisent `TemplateChangeStatus` / `TemplateChangeResult` de
`detection.py`, sans nouveau statut.

## Matrice des choix

| État | Choix |
|---|---|
| `unchanged` | `proceed`, `cancel` |
| `modified` | `cancel`, `regenerate`, `save_as`, `mark_manual` |
| `created` | `cancel`, `regenerate`, `save_as`, `mark_manual` |
| `deleted` | `cancel`, `regenerate`, `save_as`, `mark_manual` |

Les tuples sont constants dans le module ; leur ordre est déterministe et ne sert
qu'à la présentation.

## État unchanged

`proceed` et `cancel` uniquement. `proceed` signifie « aucun conflit au moment
de la détection » ; le docstring de `SafeWriteDecision` et la documentation
précisent que ce n'est pas une autorisation intemporelle.

## États de conflit

`has_write_conflict` vaut `status != "unchanged"`. Pour les trois états de
conflit, `proceed` est absent ; `cancel` est présenté en premier sans être
sélectionné.

## Sélection explicite

`select_safe_write_choice(change, choice)` calcule les options, vérifie
l'appartenance du choix et retourne une décision portant la **valeur canonique
de la matrice**, pas l'objet fourni : une sous-classe de `str` est normalisée
(testé). Pyright avait signalé un `isinstance` inutile ; ce choix le remplace
sans suppression de diagnostic.

## Choix refusés

`ValueError` pour : `proceed` sur `modified` / `created` / `deleted` ; les choix
de conflit sur `unchanged` ; `"overwrite"`, `"yes"`, `"force"`, `"continue"`,
`"ignore_conflict"`, `"replace_anyway"`, `""`, `"PROCEED"`, `" proceed"`, `None`,
`0`, un tuple ou des octets, pour les quatre états. Un statut inconnu
(`conflicted`, `dirty`, `stale`, `""`, `None`) est refusé par les trois fonctions.

## Regenerate

C'est une décision seulement : reprendre le pipeline depuis l'état disque
actuel. Aucun snapshot, aucune génération ni aucun diff n'est déclenché.

## Save as

Aucun champ `destination` : le choix du chemin reste une responsabilité séparée.

## Mark manual

Décision transitoire, sans persistance. Aucun `manual.json` ni marqueur ; le
contrat de stockage est inchangé. La limite est documentée.

## Absence d'overwrite

Aucun `overwrite`, `force`, `ignore_conflict` ou `replace_anyway` : le
vocabulaire complet atteignable est vérifié par test.

## Séparation avec Detection

`decision.py` importe seulement les types de `detection.py` ; il ne connaît ni
`snapshot_template` ni `detect_template_change` (vérifié sur l'espace de noms du
module). `detection.py` n'est pas modifié.

## Séparation avec Diff

Aucun import de `build_template_diff`.

## Séparation avec History

Aucun appel à `append_generation_history` : une décision n'est pas une écriture
réussie.

## Absence d'écriture

Aucun `write_template`, `apply_decision` ou `commit_template`. Le scénario avec
détection réelle vérifie que les octets et le mtime du template sont identiques
et que `.forge-design/` est absent après toutes les sélections.

## Pureté

Pendant les trois fonctions, sur les quatre états et tous les choix autorisés,
les appels suivants sont bloqués : `open`, `os.open`, `os.stat`,
`Path.read_text/write_text/read_bytes/write_bytes`, `socket.socket`,
`subprocess.Popen`, ainsi que `snapshot_template` / `detect_template_change`
dans `detection` et dans le package. Aucun n'est appelé. Les noms `os` et `Path`
sont absents du module.

## Déterminisme

Dix appels sur le même `TemplateChangeResult` donnent les mêmes options, dans le
même ordre, et la même décision.

## Non-mutation

`TemplateChangeResult`, `expected` et `current` sont comparés à une copie
profonde avant et après. `SafeWriteDecision` ne copie pas `expected` / `current`
(champs vérifiés) ; l'orchestrateur conserve le résultat d'origine. Aucun jeton
d'approbation.

## Documentation

- [docs/safewrite/anti-overwrite.md](../safewrite/anti-overwrite.md) : section
  « Choix explicite — FD-SAFEWRITE-002 » (matrice, sens des choix, validation,
  pureté, limites).
- [docs/02-architecture.md](../02-architecture.md) §14 : schéma
  `TemplateSnapshot → … → future controlled writer`.

## Fichiers créés

- `forge_design/safewrite/decision.py`
- `tests/test_safewrite_decision.py`
- `docs/rapports/FD-SAFEWRITE-002.md`

## Fichiers modifiés

- `forge_design/safewrite/__init__.py`
- `docs/safewrite/anti-overwrite.md`
- `docs/02-architecture.md`

Non modifiés, conformément au ticket : `safewrite/detection.py`, `design/`,
`generate/`, `contracts/`, `preview/`, `web/`, `tools/`, `app.py`, `limits.py`,
le contrat de stockage, `pyproject.toml` et le JavaScript.

## Tests ajoutés

`tests/test_safewrite_decision.py` : 97 cas. Matrice exacte (4 états), conflit
(4), vocabulaire, sélections valides (2 + 12), `proceed` refusé (3), choix de
conflit refusés sur `unchanged` (3), 13 choix inconnus × 4 états, 5 statuts
inconnus, champs des dataclasses, gel, déterminisme et non-mutation (4),
pureté, isolation du module, bout en bout avec détection réelle, exports,
valeur canonique. Tous les `TemplateChangeResult` sont construits sans
filesystem, sauf pour le test de bout en bout.

## Validations ciblées

| Commande | Résultat |
|---|---|
| `pytest -q tests/test_safewrite_decision.py` | 97 réussis |
| `pytest -q tests/test_safewrite_detection.py tests/test_safewrite_decision.py` | 162 réussis |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `ruff format --check .` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |

## Tests non exécutés

- Suite globale : non lancée, conformément au ticket.
- Wheel et installation : non nécessaires, le package existe déjà et aucune
  dépendance n'est ajoutée ; exports vérifiés par `test_exports`.
- `pip check`, Node : non concernés. MkDocs : aucune configuration.

## Limites restantes

- Aucun choix n'est appliqué ; aucun writer ni orchestrateur.
- `save_as` sans chemin ; `mark_manual` sans persistance.
- Une décision n'est liée au `TemplateChangeResult` que par `path` et
  `status` : l'orchestrateur doit conserver le résultat d'origine pour la
  révision attendue.
- `proceed` reste daté : la revalidation juste avant publication appartient au
  ticket d'écriture contrôlée.

## État Git final

Un commit sur `main`, rapport inclus, sans push.
Message : `feat: ajouter les choix anti-écrasement (FD-SAFEWRITE-002)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit.
