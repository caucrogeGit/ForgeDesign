# Rapport — FD-GRAPHICS-EDIT-001

Note de support du cœur. Le ticket produit est **FDC-EDIT-001** (déplacer un
composant Circuit), dont le rapport principal vit dans le module :
`ForgeDesign-Circuit/docs/rapports/FDC-EDIT-001.md`. Cette note ne détaille que
les abstractions génériques ajoutées au cœur pour ce besoin.

Normatif : [moteur — Node move](../graphics/graphics-engine.md#node-move-opt-in),
[hôte — Édition](../modules/module-host.md#édition),
[contrat Graphics](../graphics/graphics-core-contract.md#déplacement-de-nœuds--fd-graphics-edit-001).

## État Git initial

```text
$ git log --oneline -6
3ea093a feat: ajouter les actions bornées des modules (FD-EDIT-001)
c308c6c refactor: retirer Circuit du cœur (FD-MODULES-003)
2a0db00 feat: implémenter l'hôte des modules spécialisés (FD-MODULES-002)
558933b feat: définir le contrat des modules spécialisés (FD-MODULES-001)
69f48d8 feat: migrer Debug Center sur le Graphic Core (FD-GRAPHICS-008)
c24dc6c feat: ajouter la minicarte au Graphic Core (FD-GRAPHICS-007)
HEAD 3ea093a · origin/main c308c6c · origin/main...HEAD = 0 1
$ git status --short
 M docs/rapports/FD-CONTRACT-001.md
```

Baseline réelle : `3ea093a` (FD-EDIT-001, local, non poussé).
`FD-CONTRACT-001.md` reste une modification locale de l'utilisateur, hors commit.

## Ce que le besoin Circuit a révélé

| Besoin du premier geste réel | Capacité générique ajoutée |
|---|---|
| Glisser un nœud sans que le moteur connaisse le domaine | Option runtime `nodeMove` du Graphic Core (opt-in) |
| Coordonnées justes sous zoom et pan | Conversion écran → monde par le moteur (son viewport) |
| Fils qui suivent pendant l'aperçu | Translation des extrémités incidentes, points intermédiaires fixes, O(degré) |
| Alignement sur la grille métier | `constrain({ nodeId, delta })` fourni par le client |
| Déplacement accessible | `keyboardStep` obligatoire, Ctrl + Maj + flèches, `aria-keyshortcuts` |
| Code d'éditeur fourni par le module, chargé seulement là où il sert | `ResourceBinding.editor_script` / `editor_config`, contexte inerte calculé par l'hôte, `import()` par `/module-resource.js` |
| Message d'erreur exploitable par un script | `data-action-error` sur la page d'erreur d'action |

## Graphic Core

- `createGraphicEngine(container, scene, { nodeMove })` :
  `canMove(node)`, `keyboardStep`, `constrain` facultatif,
  `onMove({ nodeId, from, to, delta, input })` → `true` / promesse.
- Seuil `DRAG_THRESHOLD` = 4 pixels écran ; capture du pointeur au seuil
  seulement (un clic reste un clic sur le nœud).
- Aperçu runtime `previewNodeMove` (renderer) : `transform` du nœud, premier
  ou dernier point des arêtes incidentes, flèche recalculée ; scène validée,
  minicarte et libellés inchangés.
- Une intention par geste ; aucune pendant `pointermove` ; Échap,
  `pointercancel` et perte de capture annulent sans appel.
- Accepté : aperçu conservé, nouveaux gestes bloqués jusqu'au remplacement de
  la scène. Refusé : rendu autoritaire rétabli.
- Lecture seule : `movableNodes()`, `movePreview()`.
- Route, Entity et Debug ne passent pas `nodeMove` : aucun nœud déplaçable
  (vérifié en Node et dans Chromium et Firefox).
- Vocabulaire : test étendu (`component`, `grid`, `terminal`, `junction`,
  `wire`, `schematic`…) ; le moteur n'en contient aucun.

**Clavier.** Alt + flèches, validé au départ, a été écarté sur un constat
concret : Alt + ←/→ est Précédent / Suivant dans Chromium et Firefox sous Linux.
La suppression par `preventDefault` n'est pas vérifiable ici : en headless, le
raccourci du navigateur est inactif dans les deux navigateurs (témoin mesuré),
et il n'y a ni affichage ni Xvfb. Surtout, entre deux pages (rechargement
après chaque déplacement), aucun gestionnaire ne l'intercepterait. Retenu :
**Ctrl + Maj + flèches**, sans raccourci navigateur ni raccourci de bureau
Linux par défaut (GNOME, KDE ou Xfce ajoutent Alt ou Super ; non éprouvé sur
un bureau réel ici). Ctrl + flèches est exclu
parce qu'il change d'espace de travail sous macOS, et Maj + flèches reste le pan.

## Hôte des modules

- `ResourceBinding(..., editor_script=None, editor_config=None)` : script =
  asset `.js` déclaré (vérifié par le descripteur), exige une projection ;
  configuration exige un script.
- `ModuleResourceView.editor` : contexte `{script, type, path, revision,
  actions, config}` seulement si une action du type est **exposée**, la
  révision lue, la scène projetée et le script déclaré. Configuration isolée
  (message borné, trace journalisée), JSON strict, ≤ 1 Mio
  (`MAX_MODULE_EDITOR_CONFIG_BYTES`), copie détachée.
- `module_resource.html` : bloc `data-module-editor` (échappé comme la scène)
  et zone `data-editor-status` masquée sans JavaScript.
- `/module-resource.js` : `bootModuleResource` vérifie les URLs (chemin absolu
  du même serveur), importe le script, passe un contexte gelé avec
  `announce` ; tout échec du module retombe en consultation seule.
  `mountModuleResource` reste synchrone et compatible.
- **Décision M (API)** : `MODULE_API_VERSION` reste **1**. Ajouts facultatifs ;
  les modules témoins et un module sans script sont inchangés. Limite : la
  version de distribution du cœur (`0.1.0.dev0`) n'a pas bougé, donc la
  contrainte `forge-design>=…` de Circuit ne peut pas exprimer l'exigence ;
  un cœur antérieur refuserait le descripteur (`module-import-failed`).
- Aucun « circuit » dans le code livré (test de frontière inchangé, roue
  vérifiée).

## Tests du cœur

| Suite | Résultat |
|---|---|
| `tests/js/graphics/engine-move.test.mjs` (nouveau) | 17 |
| `tests/js/graphics/module-client.test.mjs` | 7 (4 nouveaux : boot, contexte gelé, échecs, contexte forgé) |
| Suites Node Graphics (15 fichiers) | 123 réussis |
| `tests/test_module_editor.py` (nouveau) | 20 |

## Mutations du cœur

17/17 tuées dans la campagne commune (voir le rapport principal) : nœud non
déplaçable rendu déplaçable, coordonnées écran, pan sur nœud, seuil supprimé,
Échap qui soumet, `pointercancel` qui garde l'aperçu, état partagé entre
instances, refus sans rollback, Alt + flèches au lieu de Ctrl + Maj, clic après
glisser, points intermédiaires translatés, URL de script hors serveur, `attach`
en échec laissé branché, contexte sans action exposée, configuration non
isolée, non bornée, script non déclaré. Un mutant équivalent est signalé dans
le rapport principal.

## Fichiers du cœur

Créés : `tests/js/graphics/engine-move.test.mjs`, `tests/test_module_editor.py`,
`docs/rapports/FD-GRAPHICS-EDIT-001.md`.

Modifiés : `forge_design/web/static/graphics/engine.js`, `svg-renderer.js`,
`forge_design/web/static/module-resource.js`, `shell.css`,
`forge_design/modules/descriptor.py`, `host.py`, `forge_design/web/modules.py`,
`templates/module_resource.html`, `templates/module_action.html`,
`tests/js/graphics/fake-dom.mjs` (`removeAttribute`, `after`),
`model.test.mjs` (vocabulaire), `module-client.test.mjs`,
`tests/module_support.py`, `tests/test_route_graph_script.py` (15 suites),
docs `graphics/graphics-engine.md`, `graphics-core-contract.md`,
`drawciel-reference.md`, `modules/module-host.md`, `module-architecture.md`,
`module-actions.md`, `02-architecture.md`, `03-roadmap.md`.

## Validation du cœur

| Contrôle | Résultat |
|---|---|
| `compileall`, `ruff check`, `ruff format --check .`, `git diff --check` | Réussis |
| `pyright` | 0 erreur |
| Suites Node Graphics | 123 réussies |
| Suite globale `pytest` (hors dépôt, basetemp court) | 4 582 réussis (4 561 + 21) |
| `pip check` | Aucun problème |
| Roue `forge_design-0.1.0.dev0` | Aucun « circuit » ; installée avec la roue du module : vraie commande, Chromium et Firefox 10/10 ; cœur seul : Circuit en 404 |
| Non-régression navigateur (Route, Entity, Debug, témoin, cœur seul, sans JS) | Chromium 7/7, Firefox 6/6 + sans JS |

Aucun push.
