# Rapport — FD-EDITOR-006

## Ticket et objectif

Afficher dans l'éditeur Web une prévisualisation statique du Design, produite
exclusivement par `generate_preview_data(contract)` et
`render_preview(design, data)`, dans une `<iframe sandbox>` avec trois modes
de largeur, sans JavaScript, sans backend cible, sans exécution Jinja et sans
écriture.

## État Git initial

`main` synchronisée avec `origin/main` à `3ea2fb2` — FD-EDITOR-005. Seule
modification suivie préexistante : `docs/rapports/FD-CONTRACT-001.md`,
préservée hors commit. Le `storage/` de 09:03 est toujours ignoré, non ouvert
et inchangé.

## Architecture

```text
Design + Contract ─┬→ arbre / propriétés (/editor)
                   └→ generate_preview_data → render_preview → /editor/preview → <iframe sandbox>
```

Nouveau module `web/editor_preview.py`. Pour éviter d'importer des noms privés,
`web/editor.py` expose ses helpers de chargement sous des noms publics
(`load_design`, `load_contract`, `EditorHttpError`) ; c'est un renommage pur,
sans changement de comportement. `forge_design/preview/` n'est pas modifié.

## Endpoint preview

`GET /editor/preview?design=…&mode=…`, `no_store`. Paramètres exacts
(`design` obligatoire, `mode` facultatif, valant `desktop` par défaut) ;
paramètre inconnu, dupliqué, mode inconnu ou `design` trop long : 400. Sans
projet : 409. Document HTML complet (`preview_frame.html`), pas un fragment
brut.

## Chargement Design

`load_design`, donc `read_design`, sans lecture directe. Design introuvable :
404 ; chemin refusé : 400 ; Design invalide : « Prévisualisation
indisponible : Design invalide. », sans rendu partiel inventé.

## Chargement Contract

`load_contract(design)`, donc `read_view_contract(design.source_contract)`.
Contrat absent, JSON invalide ou non conforme : « Prévisualisation
indisponible : contrat absent ou invalide. » La page de l'éditeur reste
utilisable pour la structure (testé).

## Données fictives

`generate_preview_data(contract)` sans altération : un binding string affiche
« Exemple » et une liste donne trois lignes (testés).

## Renderer existant

`render_preview(design, data.data)`. Sa sortie est la **seule** chaîne marquée
`Markup`, côté Python, en un point unique et commenté. Aucun `|safe` dans les
templates. Les valeurs hostiles (classe et vue contenant `<script>` et
`<img onerror>`) restent inertes.

## Iframe

`<iframe class="preview-frame preview-frame--<mode>" src="/editor/preview?…"
title="Prévisualisation du Design" sandbox></iframe>`, vérifiée à l'octet.

## Sandbox

`sandbox` sans aucune permission : aucun `allow-*` (testé), donc ni script,
ni formulaire, ni même origine.

## CSP

**Constat bloquant traité.** Forge envoie sur toute réponse
`X-Frame-Options: DENY` et `frame-ancestors 'none'`. Implémentée telle que le
ticket la décrit, l'iframe aurait été **refusée par tout navigateur**, alors
que les tests HTTP l'auraient vue passer.

Forge pose ses en-têtes par `setdefault`, une route peut donc les définir.
**Seule** la réponse `/editor/preview` définit :

```text
Content-Security-Policy: default-src 'none'; style-src 'self' http://127.0.0.1:<port>;
  img-src 'self' data:; frame-ancestors 'self'; base-uri 'none'; form-action 'none'
X-Frame-Options: SAMEORIGIN
```

Cette politique est plus stricte que celle de Forge (aucun script, aucune
soumission), avec une seule ouverture : l'encadrement en même origine, sans
risque de clickjacking puisque le document n'a ni formulaire ni action.
`/editor`, `/` et `/editor-preview.css` gardent `DENY` et
`frame-ancestors 'none'` (testé). L'origine exacte est ajoutée à `style-src`,
parce que l'origine d'un document sandboxé sans `allow-same-origin` est opaque
et que l'interprétation de `'self'` varie selon les navigateurs. Elle n'est
ajoutée que pour un `Host` de forme exacte `127.0.0.1:<port>` (un `Host`
hostile est testé). **C'est une décision de sécurité à valider.**

Aucun style inline dans `/editor` ni dans le document encadré (testé).
`render_responsive_preview` et `wrap_preview_html`, qui produisent
`style="width:…"`, ne sont ni importés ni appelés (instrumenté).

## Modes responsive

`desktop` 1440, `tablet` 768 et `mobile` 390, issus de `PREVIEW_VIEWPORTS`,
exprimés en classes CSS dans `shell.css` avec `max-width: 100%` ; un test
vérifie l'alignement. Les liens GET « Desktop », « Tablette » et « Mobile »
marquent le mode actif par `aria-current`. Le paramètre `preview` de
`/editor` est omis pour `desktop`, si bien que les URL historiques sont
inchangées (testé). Le mode est conservé par les liens de l'arbre, les
formulaires et les redirections. Le champ `preview` est **facultatif** dans
les POST : c'est la seule exception à l'ensemble exact de champs, il est
validé (400 si inconnu), et les requêtes sans ce champ restent valides.

## CSS indicatif

`/editor-preview.css`, servi par une route explicite comme `/shell.css` :
lisibilité, tableaux, contour des blocs `data-forge-design-type`. Aucune
émulation Tailwind. L'interface dit « Aperçu structurel » et
« Prévisualisation indicative », jamais « rendu final » ou « exact » (testé).

## Diagnostics

« Données fictives : complètes/partielles » et « Rendu : complet/partiel »,
avec les listes `PreviewDataIssue` et `PreviewRenderIssue` et leurs codes
(`preview.unsupported_field_type`, `preview.unsupported_prop`, testés). Une
preview partielle est affichée avec « Prévisualisation partielle ».

## Mise à jour après mutation

PRG inchangé : un ajout avec `preview=tablet` redirige avec `preview=tablet`,
et l'iframe relit le bloc ajouté ; `tailwind_add` avec `preview=mobile`
redirige et la preview relit la classe. Un no-op n'écrit rien et conserve le
mode.

## Absence de backend réel

Aucun import du projet cible, aucun appel HTTP applicatif ; les données sont
fictives.

## Absence de Jinja runtime

La preview consomme le Design et les données fictives ; aucun template généré
n'est produit ni exécuté.

## Absence d'écriture

GET `/editor/preview` avec `write_design`, `set_design_props` et
`append_design_block` rendus interdits, dans les trois modes : 200 ;
`.design.json` et template `.html` inchangés, aucun `.forge-design/`.

## Fichiers créés

- `forge_design/web/editor_preview.py`
- `forge_design/web/templates/preview_frame.html`
- `forge_design/web/static/editor-preview.css`
- `tests/test_web_editor_preview.py`
- `docs/rapports/FD-EDITOR-006.md`

## Fichiers modifiés

- `forge_design/web/editor.py` : helpers publics, mode d'aperçu (URL,
  rendus, redirections, champ facultatif).
- `forge_design/web/server.py` : `/editor/preview` et `/editor-preview.css`.
- `forge_design/web/templates/editor.html` : section de prévisualisation,
  champ `preview` caché, liens d'arbre.
- `forge_design/web/static/shell.css` : modes et iframe.
- `pyproject.toml` : `preview_frame.html` et `editor-preview.css` en
  package-data.
- `tests/test_web_editor.py` : fixtures extraites en `make_root` et `serving`
  pour être partagées, sans changement de comportement.
- `docs/editor/structural-editor.md`, `docs/02-architecture.md`

Non modifiés : `preview/`, `editor/`, `design/`, `generate/`, `safewrite/`,
`contracts/`, `tools/`, `app.py`, le JavaScript, le contrat de stockage.

## Tests ajoutés

`tests/test_web_editor_preview.py` : 41 cas. Sans projet, rendu nominal (page,
« Exemple », trois lignes), en-têtes de la réponse encadrée, en-têtes intacts
des autres pages, 4 cas de politique selon `Host`, 3 modes, mode par défaut,
9 paramètres invalides, Design absent ou invalide, 3 contrats indisponibles,
preview partielle, valeurs hostiles, absence de style inline, helpers
responsive non utilisés, lecture seule, CSS servi ; iframe exacte et sans
permission, mode dans l'éditeur, mode invalide, URL historiques, mutation avec
mode puis preview relue, redirection historique, no-op, `preview` invalide en
POST, largeurs CSS alignées.

**Défauts de mes tests corrigés en cours de route :**
- le test de diagnostics utilisait le type `date`, qui est supporté par
  `preview/data.py` ; il utilise maintenant `uuid` ;
- importer les fixtures depuis `test_web_editor.py` déclenchait F811 ; elles
  sont maintenant extraites en helpers.

Vérification par mutation, lancée depuis le scratchpad avec restauration
vérifiée : CSP par défaut (1 échec), XFO par défaut (1), HTML non marqué sûr
(4), `Host` non contrôlé (2), paramètre en trop (1), contrat non exigé (3),
`preview=desktop` explicite (3), mode invalide accepté (4), `preview` non
facultatif (2), iframe sans `sandbox` (1), `allow-scripts` (1), mode perdu
dans l'arbre (1). Toutes les mutations sont détectées, et aucun nouveau
`storage/` n'a été créé.

## Validations ciblées

Toutes les exécutions pytest sont lancées depuis le scratchpad.

| Commande | Résultat |
|---|---|
| `pytest -q tests/test_web_editor_preview.py tests/test_web_editor.py` | 145 réussis |
| `pytest -q tests/test_preview_data.py tests/test_preview_render.py tests/test_preview_responsive.py tests/test_web_editor_preview.py tests/test_web_editor.py tests/test_tailwind_classes.py tests/test_web_server.py` | 391 réussis |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` / `ruff format --check .` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |

## Validation globale

`pytest` : **3352 réussis** en 37 s. `python -m pip check` : No broken
requirements found.

## Packaging

Wheel `forge_design-0.1.0.dev0-py3-none-any.whl` dans `tmp/wheels`, SHA-256
`c576b9f5d1ef7dddb22630b913cda9fff528665752cc821ecfdd5497c9c0eb7e`. Elle
contient `editor_preview.py`, `preview_frame.html` et `editor-preview.css`.

## Installation réelle

Installation `--no-deps --no-index --target` temporaire, `python -I`, origine
installée vérifiée, serveur réel :
1. `/editor` : iframe `sandbox` sans permission ;
2. `/editor/preview` en desktop, tablet et mobile : 200, largeur annoncée,
   trois lignes fictives, « Exemple », `SAMEORIGIN` et
   `frame-ancestors 'self'` ;
3. `/editor?…&preview=mobile`, puis `tailwind_add` avec `preview=mobile` :
   303 vers `preview=mobile`, et la preview relit `class="py-8 max-w-5xl"` ;
4. `/editor-preview.css` servie depuis la wheel.

## Validation navigateur

**Non effectuée.** Le HTML, le CSS, les en-têtes et le comportement HTTP sont
testés ; l'affichage réel de l'iframe, le chargement de la feuille de style
dans le document sandboxé et l'apparence n'ont pas été vérifiés dans un
navigateur. Les en-têtes ont été conçus pour que l'encadrement fonctionne
(`frame-ancestors 'self'`, `SAMEORIGIN`, origine explicite dans `style-src`) ;
une vérification manuelle est recommandée.

## Limites restantes

- Données fictives : booléens à `true`, listes de trois éléments ; les
  `empty_state` ne sont pas visibles et il n'y a pas de bascule.
- Classes Tailwind non compilées : l'aperçu est structurel, pas visuel.
- Rendu navigateur non vérifié (voir ci-dessus).
- L'iframe a une hauteur fixe (40rem), défilable ; pas d'ajustement
  automatique sans JavaScript.

## État Git final

Un commit sur `main`, rapport inclus, sans push.
Message : `feat: intégrer la preview dans l'éditeur (FD-EDITOR-006)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Hash :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-EDITOR-006.md
```
