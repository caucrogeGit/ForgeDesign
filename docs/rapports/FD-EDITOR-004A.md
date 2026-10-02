# Rapport — FD-EDITOR-004A

## Ticket et objectif

Correctif de cohérence de FD-EDITOR-004, sans nouvelle fonctionnalité :
1. supprimer la sauvegarde explicite redondante `POST /editor/save` ;
2. ignorer le dossier de journaux runtime Forge `/storage/` à la racine.

## État Git initial

`main` à `7173cfc` — FD-EDITOR-004, déjà poussé (`origin/main` identique).
`git status` : `docs/rapports/FD-CONTRACT-001.md` modifié (préservé hors
commit) et `storage/` non suivi, produit par les passes de mutation de
FD-EDITOR-004.

## Décision sur la sauvegarde

Chaque mutation réussie étant déjà écrite immédiatement, `/editor/save` ne
faisait que réécrire le même Design dans sa forme canonique. La route est
supprimée, sans remplacement (`/editor/normalize` ou autre). Une normalisation
explicite pourra faire l'objet d'un ticket dédié si le besoin apparaît.

## Route supprimée

- `server.py` : route `POST /editor/save` et son adaptateur retirés.
- `web/editor.py` : handler `editor_save` retiré. Le helper `_save` est
  conservé, car il sert aux mutations réelles ; il n'est pas renommé.
- Comportement réel du routeur Forge : `POST /editor/save` répond **404**, et
  le fichier reste inchangé (testé).

## Politique de persistance

Seule une mutation effective (`append`, `remove`, `move`, `binding`,
`visibility`, `props`, `columns`) écrit :

```text
read_design → editor/* → changed=True → write_design(expected_revision=read.revision) → 303 → GET
```

Testé : un ajout et une modification de props appellent `write_design`
exactement une fois, avec une révision non nulle.

## No-op

`changed=False` sans diagnostic : aucun appel à `write_design`, 303 avec
« Aucune modification. » (test existant conservé). Refus de l'éditeur
(`issues`) : aucun appel à `write_design`, 422 (nouveau test, ajout interdit
et binding invalide).

## Interface utilisateur

Le formulaire « Réenregistrer le Design (forme canonique) » est supprimé. Le
texte devient : « Les modifications validées sont enregistrées immédiatement
dans le fichier Design. Aucun template HTML n'est généré ni écrit. » Le mot
« autosave » n'est pas employé. Aucun `/editor/save` dans le HTML rendu
(racine, section, table), ni dans le template packagé de la wheel.

## Dossier storage

Les journaux `storage/logs/errors.dev.*` existants **n'ont pas été ouverts**.
Seuls leurs noms et dates ont été consultés, pendant FD-EDITOR-004. Ils ne sont
pas versionnés et ne sont pas supprimés par ce ticket : leur suppression
locale (`rm -rf storage/`) reste à la main de l'utilisateur et ne fait pas
partie du commit.

Les tests de ce ticket, la suite globale comprise, ont été lancés depuis un
répertoire du scratchpad (`--rootdir` vers le dépôt) : aucun `storage/` n'y a
été créé.

## Politique gitignore

`.gitignore` : `/storage/`, à la racine seulement.

| Chemin | Résultat |
|---|---|
| `storage/test.log` | ignoré par `.gitignore:16:/storage/` |
| `foo/storage/example.txt` | non ignoré |
| `forge_design/storage/x.py` | non ignoré |

`storage/` n'apparaît plus dans `git status`.

## Sécurité

Inchangée : `is_local_action` (403), Content-Type urlencodé (415), champs
exacts par action (400), contrat exigé côté serveur (409), révision attendue
et conflit (409). Les tests correspondants restent verts ; le test 403 ne vise
plus que `/editor/action`.

## Fichiers modifiés

- `.gitignore`
- `forge_design/web/server.py`
- `forge_design/web/editor.py`
- `forge_design/web/templates/editor.html`
- `tests/test_web_editor.py`
- `docs/editor/structural-editor.md`
- `docs/02-architecture.md`

Fichier créé : `docs/rapports/FD-EDITOR-004A.md`. Non modifiés : `editor/`,
`design/`, `generate/`, `safewrite/`, `contracts/`, `tools/`, `app.py`, le
JavaScript, le contrat de stockage.

## Tests adaptés

`tests/test_web_editor.py` : 77 cas (74 auparavant).
- Retirés : `test_save_rewrites_canonical` et l'assertion 403 sur
  `/editor/save`.
- Ajoutés : `test_save_route_removed` (404, fichier inchangé, aucun formulaire
  dans trois rendus), `test_editor_refusal_never_writes` et
  `test_effective_mutation_writes_once` (ajout et props).

## Validations ciblées

Toutes les exécutions pytest sont lancées depuis le scratchpad.

| Commande | Résultat |
|---|---|
| `pytest -q tests/test_web_editor.py` | 77 réussis |
| `pytest -q tests/test_editor_structure.py tests/test_editor_properties.py tests/test_web_editor.py` | 301 réussis |
| `pytest -q tests/test_web_editor.py tests/test_web_server.py tests/test_web_inspector.py tests/test_web_recent_projects.py tests/test_web_templates.py` | 289 réussis |
| `pytest` (suite globale, peu coûteuse) | 3240 réussis |
| `git check-ignore -v storage/test.log` | `.gitignore:16:/storage/` |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` / `ruff format --check .` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |

## Packaging

Wheel `forge_design-0.1.0.dev0-py3-none-any.whl` dans `tmp/wheels`, SHA-256
`7dc5c7005149defcd303da860ffa5954aab275a0e6a8c066185948b887c242a6`. Le
template `editor.html` packagé ne contient aucun `/editor/save`.

Installation `--no-deps --no-index --target` temporaire, `python -I`, serveur
réel : `GET /editor` (200, arbre), `POST append` (303 et fichier écrit),
relecture, `POST props` (303, prop affichée), `POST /editor/save` (404), aucun
formulaire de sauvegarde, template `.html` intact, aucun `.forge-design/`.

La 404 fait journaliser par Forge « Rendu de errors/404.html impossible ;
repli sur une réponse minimale ». C'est le comportement documenté depuis
FD-WEB-002 pour toute 404 en l'absence de renderer d'erreur ; il n'est pas
propre à ce ticket.

## Tests non exécutés

- `pip check` : aucune dépendance modifiée.
- Node : aucun JavaScript modifié. MkDocs : aucune configuration.

## Limites restantes

- Le dossier `storage/` existant reste sur le disque, ignoré, jusqu'à sa
  suppression manuelle.
- Les 404 de Forge journalisent l'absence de renderer d'erreur (préexistant).
- Pas de normalisation explicite d'un `.design.json` écrit à la main.

## État Git final

Un commit sur `main`, distinct de `7173cfc` (pas de squash), rapport inclus,
sans push.
Message : `fix: simplifier la persistance Web de l'éditeur (FD-EDITOR-004A)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Hash :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-EDITOR-004A.md
```
