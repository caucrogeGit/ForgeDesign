# Rapport — FD-GRAPHICS-EDIT-002

Note de support du cœur. Le ticket produit est **FDC-EDIT-004** (créer une
connexion Circuit entre deux bornes), dont le rapport principal vit dans le
module : `ForgeDesign-Circuit/docs/rapports/FDC-EDIT-004.md`. Cette note ne
détaille que l'abstraction générique ajoutée au Graphic Core pour ce besoin.

Normatif : [moteur — calques monde](../graphics/graphics-engine.md#world-overlays-and-view-changes),
[contrat Graphics](../graphics/graphics-core-contract.md#calques-monde-et-vue--fd-graphics-edit-002),
[hôte — édition](../modules/module-host.md#édition).

## État Git initial

```text
$ git log --oneline -5
691e83e feat: ajouter le déplacement générique des nœuds (FD-GRAPHICS-EDIT-001)
3ea093a feat: ajouter les actions bornées des modules (FD-EDIT-001)
c308c6c refactor: retirer Circuit du cœur (FD-MODULES-003)
2a0db00 feat: implémenter l'hôte des modules spécialisés (FD-MODULES-002)
558933b feat: définir le contrat des modules spécialisés (FD-MODULES-001)
$ git rev-parse --short HEAD → 691e83e ; origin/main → 691e83e
$ git status --short
 M docs/rapports/FD-CONTRACT-001.md
```

`FD-CONTRACT-001.md` reste une modification locale de l'utilisateur, hors
commit.

## Besoin révélé

Le geste « tirer une connexion d'une borne à une autre » exige des éléments
interactifs **dans le dessin** (poignées de bornes, aperçu du fil), suivant le
zoom et le pan. L'API publique du moteur (à `691e83e`) n'offrait :

- aucun point d'insertion public dans le SVG de scène ;
- aucune notification de changement de vue ou de niveau de détail ;
- aucune conversion écran → monde publique.

Sans ces points, le script du module aurait dû insérer ses éléments dans le
groupe SVG privé du renderer, ou superposer un SVG séparé et deviner le
viewport en écoutant zoom et pan : précisément la frontière que le cœur doit
préserver. Décision validée par l'utilisateur avant implémentation : extension
générique minimale, sans vocabulaire de domaine.

## API ajoutée

```js
createGraphicEngine(container, scene, { onViewChange(state) {} });
const overlay = engine.addOverlay({ label });  // { root, remove() }, gelé
engine.worldAt({ clientX, clientY });           // { x, y } monde, gelé
```

| Élément | Contrat |
|---|---|
| `addOverlay` | Racine `<g class="gx-overlay" role="group">` dédiée, vide, créée par le renderer (`createOverlayRoot`), placée après les nœuds dans le SVG de scène : coordonnées monde, viewBox du viewport. Nom accessible facultatif, une ligne, borné à 200 caractères. Aucun calque interne exposé |
| Rendu | `render()` rattache les mêmes racines, dans l'ordre de création (`attachOverlays`) : le contenu du client survit |
| `remove()` | Idempotent ; `destroy()` retire toutes les racines de l'instance |
| Pointeur | Un appui dans un calque n'est jamais un pan (même règle qu'un nœud) |
| Clavier | Une touche déjà traitée par le client (`defaultPrevented`) n'est reprise ni par la désélection (Échap) ni par le pan (Maj + flèches) |
| `onViewChange` | État gelé `{ scale, x, y, width, height, detailLevel }`, émis seulement quand il change (zoom, pan, fit, home, recentrage, redimensionnement, niveau de détail) ; exception du client isolée |
| `worldAt` | Conversion écran → monde par le viewport de l'instance ; entrée non finie refusée (`TypeError`) ; erreur après `destroy()` |
| Client générique | `/module-resource.js` transmet `onViewChange` fourni par `createResourceEditor` (comme `nodeMove`) |
| Thème | `shell.css` : `gx-overlay-item`, `gx-overlay-handle`, `gx-overlay-hit`, `gx-overlay-active`, `gx-overlay-candidate`, `gx-overlay-path` ; couleurs et traits seulement (traits `non-scaling-stroke`), aucune taille imposée ; nécessaire car la CSP (`style-src 'self'`) interdit les styles en ligne d'un module |

Le moteur ne dessine rien dans un calque et ne connaît ni port, ni borne, ni
fil, ni Circuit. Route, Entity et Debug n'appellent ni `addOverlay` ni
`onViewChange` : rendu inchangé (vérifié en Node et dans les navigateurs).

## Tests du cœur

| Suite | Résultat |
|---|---|
| `tests/js/graphics/engine-overlay.test.mjs` (nouveau) | 10 : absence par défaut, racine dédiée et nom borné, survie au rendu et ordre, `remove` / `destroy`, deux instances indépendantes, appui sans pan (fond toujours pan), `onViewChange` (initial, zoom, pan, fit, resize, niveau, aucune émission sans changement, plancher de zoom), erreur client isolée, `worldAt` sous zoom et pan, touches déjà traitées |
| `tests/js/graphics/module-client.test.mjs` | 8 (1 nouveau : `onViewChange` transmis, calque créé dans `attach`) |
| Suites Node Graphics (16 fichiers) | 134 réussis (123 + 11) |
| `tests/test_route_graph_script.py` | Décompte des suites porté à 16 |

## Mutations du cœur

**12/12 tuées** (fichiers restaurés à l'octet près) : calques non rattachés au
rendu, calques laissés au `destroy`, appui sur un calque traité comme pan,
`onViewChange` sans changement, Échap déjà traité repris, Maj + flèches déjà
traité repris, `worldAt` sans validation, calques partagés entre instances,
erreur du client non isolée, nom de calque non borné, calque placé avant les
nœuds, `onViewChange` non transmis par le client générique.

## Fichiers du cœur

Créés : `tests/js/graphics/engine-overlay.test.mjs`,
`docs/rapports/FD-GRAPHICS-EDIT-002.md`.

Modifiés : `forge_design/web/static/graphics/engine.js`, `svg-renderer.js`, `docs/graphics/drawciel-reference.md` (journal : FDC-EDIT-002, FDC-EDIT-003, FDC-EDIT-004),
`forge_design/web/static/module-resource.js`, `shell.css`,
`tests/js/graphics/module-client.test.mjs`, `tests/test_route_graph_script.py`,
docs `graphics/graphics-engine.md`, `graphics/graphics-core-contract.md`,
`modules/module-host.md`, `02-architecture.md`, `03-roadmap.md`.

Aucun code Python du cœur n'est modifié ; l'API de modules reste 1.

## Validation du cœur

| Contrôle | Résultat |
|---|---|
| Suites Node Graphics | 134 réussies (16 fichiers) |
| Mutations | 12/12 |
| Suite globale `pytest` (hors dépôt, basetemp court) | 4 583 réussis (4 582 + 1 contrôle `node --check` de la nouvelle suite) ; un premier passage a échoué sur `/tmp` plein (595 `OSError: [Errno 28]`), relancé après avoir libéré l'espace |
| `ruff check`, `ruff format --check .`, `git diff --check` | Réussis |
| Non-régression navigateur (Route, Entity, Debug, module témoin, cœur seul, sans JavaScript) | Chromium 7/7, Firefox 6/6 + sans JavaScript |

L'usage réel du calque (poignées, aperçu, clavier, Chromium et Firefox, roues
installées, vraie commande) est rapporté dans FDC-EDIT-004.

Aucun push.
