# Rapport — FD-EDITOR-007

Refuser les actions de l'éditeur structurel depuis une vue périmée (correction d'ACC-004). Date : 2026-10-15.

## Objectif

Empêcher toute mutation d'un `.design.json` depuis une vue d'éditeur périmée. Le défaut ACC-004 (MAJOR), relevé par FD-ACCEPTANCE-001, avait fermé le gate SéquenCiel : une action envoyée depuis une page ancienne s'appliquait au bloc qui occupe **aujourd'hui** le chemin soumis.

| Décision | Résultat |
|---|---|
| A. Corrige ACC-004 ? | Oui |
| B. Révision affichée transportée ? | Oui : champ caché `revision`, jeton opaque |
| C. Comparaison avant mutation ? | Oui : avant validation, contrat, action et no-op |
| D. Conflit = 409 ? | Oui |
| E. Rebase automatique ? | Non |
| F. Identifiant persistant de nœud ajouté ? | Non |
| G. `write_design` garde sa révision ? | Oui, inchangé |
| H. Nouveau Tool ? | Non : cinq Tools |
| I. Graphic Core modifié ? | Non : 134/134 |
| J. Gate SéquenCiel ouvert après ce ticket ? | Non : ACC-003 reste à corriger, puis FD-ACCEPTANCE-002 |

## État Git initial

| Élément | Valeur |
|---|---|
| HEAD | `97a214a` (FD-ACCEPTANCE-001), qui contient FD-RUNTIME-004 |
| `origin/main` | `e411d0c` ; 0 commit en retard, 8 en avance |
| Arbre | Seul `docs/rapports/FD-CONTRACT-001.md` est modifié par l'utilisateur ; il est préservé et hors commit |
| Collision | Aucune : FD-EDITOR-007 n'apparaissait que comme recommandation dans le rapport d'acceptation |
| Version | 0.2.0, inchangée |

## Défaut ACC-004

L'éditeur adresse les blocs par `NodePath`, c'est-à-dire par des indices. Ce chemin n'est pas une identité stable : une suppression ou une insertion en amont décale les indices. Les formulaires ne portaient pas la révision affichée. Une action soumise depuis une page ancienne s'appliquait donc au bloc qui occupe désormais le chemin, puis était enregistrée avec un 303 « Modification enregistrée. ». L'éditeur n'a pas d'historique pour annuler.

## Reproduction avant correction

`test_acc_004_two_tabs_never_touch_the_wrong_block` a été écrit et lancé **avant** toute modification. Il simule un navigateur : les champs soumis sont ceux du formulaire réellement affiché, relus dans la page.

1. Ajout d'une section : `[section, table, section]`.
2. L'onglet A affiche la `table` (chemin 1) et son formulaire de suppression.
3. L'onglet B supprime le bloc 0 avec son propre formulaire : `[table, section]`.
4. L'onglet A soumet son formulaire.

Résultat avant correction : **303**, et c'est la section (bloc 1 courant) qui est supprimée, conformément à ACC-004. L'assertion `assert 303 == 409` échoue. Après correction, le test passe.

## Cause racine

`editor_action` relisait le design **au moment du POST**. La « révision attendue » transmise à `write_design` était celle du POST, pas celle de la page affichée. La garde de `write_design` ne couvre que l'intervalle entre la lecture et l'écriture d'une même requête ; rien ne liait l'action à la vue de l'utilisateur.

## Modèle de révision existant

`read_design` renvoie une `DesignRevision` **complète** : taille, `modified_ns`, `digest` (SHA-256 du contenu), `device`, `inode`, `changed_ns`. `write_design(expected_revision=…)` la compare deux fois, avant et après la préparation du fichier temporaire. Ce modèle n'est pas modifié et reste l'autorité ; aucun autre système de révision n'est introduit.

## Token Web

Le calcul du jeton opaque des actions de modules (FD-EDIT-001, `modules/actions.revision_token`) est réutilisé, après extraction dans un module neutre, `forge_design/revision_tokens.py`. Ce module se limite à « périmètre + révision complète → jeton opaque », sans sémantique métier :

- `revision_token(scope, revision)` : SHA-256 du JSON `[*scope, size, modified_ns, digest, device, inode, changed_ns]` ;
- `is_revision_token(value)` : forme seulement (64 hexadécimaux minuscules).

| Usage | Périmètre |
|---|---|
| Modules (inchangé) | `(module_id, type_id, chemin)` |
| Éditeur | `("design", chemin du design)` |

**Extraction sans changement de comportement.** Trois vecteurs ont été relevés avec le code **d'avant** l'extraction, dont un chemin Unicode et une taille de 2⁴⁰ octets. Ils sont figés dans `test_revision_tokens.py` : le jeton des modules reste identique octet pour octet, et les tests des modules passent sans modification.

Opacité : le navigateur ne voit ni mtime, ni inode, ni périphérique, et ne reconstruit jamais une révision. Le jeton diffère du simple SHA-256 du contenu (test). Le contrat des modules (`test_modules_contract`) autorise explicitement ce nouveau module, qui ne dépend que de la bibliothèque standard.

## Formulaires concernés

Les 10 actions POST réelles de l'éditeur (`_ACTION_FIELDS`), toutes adressées par `NodePath` :

| Famille | Actions |
|---|---|
| Structure | `append`, `remove`, `move` |
| Propriétés | `props`, `tailwind_set`, `tailwind_add`, `tailwind_remove` |
| Contrat | `binding`, `visibility`, `columns` |

**11 formulaires dans le gabarit pour 10 actions** : `tailwind_add` en a deux (saisie libre, et suggestions par catégorie). À l'affichage, deux d'entre eux sont répétés par des boucles : un `tailwind_remove` par classe présente, un formulaire de suggestions par catégorie.

Chaque formulaire **rendu** porte `<input type="hidden" name="revision">` avec le jeton courant (test sur la page réelle). Le formulaire GET d'ouverture et les POST de la preview réelle, qui ne modifient pas le design, n'en portent pas (test).

## Pipeline avant

```text
POST /editor/action → forme des champs → read_design (révision Rp) → contrat → action
  → no-op : 303 (aucune écriture)
  → sinon : write_design(expected_revision=Rp) → 303
```

## Pipeline après

```text
GET /editor            read_design → D1 ; jeton T1 dans chaque formulaire d'action
POST /editor/action    forme du jeton (400 si absent, vide ou mal formé)
                       → read_design → jeton courant T2
                       → T1 ≠ T2 (comparaison à temps constant) : 409, rien d'autre
                       → T1 = T2 : forme de l'action → contrat → action
                         → no-op : 303 ; sinon write_design(expected_revision) inchangé → 303
```

## Garde avant mutation

La comparaison a lieu juste après la lecture, **avant** :

- la validation de forme de l'action ;
- la validité du design et le contrat ;
- l'interprétation de l'action ;
- le no-op.

Une vue périmée « gagne » sur tout le reste, comme fixé à la validation. Pendant le ticket, l'ordre a été réarrangé sur disque pour placer la garde devant la validation de forme ; ce réarrangement est conservé, il correspond exactement à ce contrat. La comparaison utilise `hmac.compare_digest`, comme l'hôte des modules.

## 409 Conflict

La page de l'éditeur est rendue **sur le design courant**, avec ces caractéristiques :

- statut 409, sans 303 ni redirection, `Cache-Control: no-store` ;
- sélection à la **racine**, jamais le chemin soumis, qui peut viser un autre bloc ;
- formulaires portant le jeton **courant** : ils correspondent à ce que l'utilisateur voit désormais ;
- jeton attendu jamais divulgué : un jeton altéré n'apparaît pas dans la réponse.

Un jeton bien formé mais inconnu (un caractère changé) reçoit aussi 409. Politique stable : forme invalide → 400, révision différente → 409.

## Message utilisateur

« Le design a été modifié depuis l'affichage de cette page. Rechargez l'éditeur avant de recommencer. », avec un lien « Recharger l'éditeur » vers `/editor?design=…`, à la racine. Le texte est figé dans les tests : une régression du message échoue.

## Aucun write sur conflit

Sur 409 : aucune mutation, aucun appel à `write_design`, aucune réécriture canonique, aucun historique (l'éditeur n'en a pas, et aucun n'est ajouté). C'est vérifié par l'empreinte du fichier, identique octet pour octet, pour chacune des 10 actions.

## Double garde Web / write_design

| Garde | Protège | Message |
|---|---|---|
| Web (nouvelle) | L'intention de l'utilisateur : la vue qu'il a affichée | « Le design a été modifié depuis l'affichage… » |
| `write_design` (inchangée) | La publication pendant la requête | « Le Design a été modifié depuis sa lecture… » |

Les deux tests historiques de la garde interne (`test_conflict_409`, `test_tailwind_conflict_409`) restent verts. Ils lisent la révision affichée **avant** d'injecter la modification externe pendant la requête : la garde Web est satisfaite, et c'est bien `write_design` qui répond 409.

## Deux onglets

Le test HTTP réel du « Reproduction avant correction » donne 409 : le design reste exactement dans l'état laissé par l'onglet B, et aucun bloc n'est touché. La même démonstration a été faite dans Chromium, Firefox et Firefox sans JavaScript (voir plus bas).

## Modification externe

`GET` (T1), puis un bloc valide inséré en tête par un autre outil, puis `POST` avec T1 : **409** pour chacune des 10 actions (tableau paramétré), fichier identique à l'état externe.

## Remplacement octets identiques

Copie, puis `os.replace` (mêmes octets, nouvel inode), puis `POST` avec T1 : **409**. La sémantique de la révision complète est conservée.

D'autres tests ferment les mutations « jeton fondé sur le seul mtime » ou « sur la seule taille » :

- seul le mtime change : 409 ;
- même taille et même mtime, contenu différent : 409.

## No-op stale

Vue périmée, puis action qui serait sans effet sur le document courant (classe déjà présente) : **409**, jamais le 303 `notice=noop`.

## Concurrence

Vérifiée, pas supposée.

**Serveur réel.** `ForgeDesignServer` dérive de `WSGIServer`, sans `ThreadingMixIn` (test qui fige cette hypothèse) : il traite une requête à la fois. Deux POST portant la même révision passent l'un après l'autre ; le premier publie, le second reçoit **409** (test).

**Même processus, vrais threads.** L'application WSGI est appelée par deux threads, synchronisés par une barrière après la lecture : les deux franchissent ensemble la garde Web. Distribution mesurée :

| Issue | Fréquence | Signification |
|---|---|---|
| 303 + 409 | 37/40 | `write_design` détecte le conflit |
| 303 + 303 | 3/40 | Les deux publient (mêmes octets) |
| 303 + 500 | 1/30 (boucle antérieure) | « Sauvegarde incertaine » |

L'invariant tient dans **tous** les cas : un design valide portant une seule mutation, jamais un état mélangé (test).

Cause : `write_design` contrôle, puis publie par `replace`, sans verrou entre ce contrôle et la publication. Seule une création est exclusive (`link`). Cette fenêtre existait avant ce ticket. Elle est inatteignable par HTTP avec le serveur actuel. Elle n'est pas corrigée ici (§34) et fait l'objet d'une recommandation.

## Sécurité HTTP

Les gardes existantes sont inchangées :

- `is_local_action`, sinon 403 ;
- formulaire encodé, sinon 415 ;
- 64 Kio par champ ;
- `no-store`.

Le jeton est borné par sa forme : exactement 64 caractères, et 400 pour tout autre format (absent, vide, majuscules, 63 ou 65 caractères, espace, non hexadécimal). Aucune analyse de système de fichiers n'est faite depuis HTTP.

## Sans JavaScript

Aucune dépendance au JavaScript : les formulaires sont natifs. Dans Firefox avec `javascript.enabled=false`, deux étapes passent :

- **Deux onglets** : l'onglet B poste avec son propre formulaire relu dans la page ; l'onglet A clique sur le bouton natif. Le message et le lien de rechargement s'affichent, et le design reste identique à S1.
- **Modification externe** : sélection racine, rechargement, puis action valide enregistrée. Cette étape a été ajoutée sur disque pendant le ticket ; elle est conservée.

## Tests Python

`tests/test_revision_tokens.py` (19 tests) :

- trois vecteurs connus d'avant l'extraction ;
- séparation des périmètres ;
- chacun des six champs de la révision change le jeton ;
- forme du jeton.

## Tests Web

`tests/test_web_editor_revision.py` (49 tests, vrai serveur HTTP) :

- reproduction d'ACC-004 ;
- message contractuel figé ;
- chaque formulaire rendu porte le jeton courant, aucun autre n'en porte, opacité ;
- **10 actions × vue périmée** (409, octets identiques) et **10 actions × révision courante** (303 ou 422 : la garde laisse passer) ;
- action valide ;
- page 409 sur le design courant, sélection racine, lien, rechargement puis action valide ;
- remplacement par octets identiques ; mtime seul ; même taille et même mtime ;
- 8 révisions absentes ou mal formées (400) ; jeton altéré (409) ;
- no-op périmé ;
- modification externe ;
- concurrence en processus ;
- sérialisation du serveur ;
- deux POST successifs.

Tests existants adaptés :

- le helper `action()` relit la révision dans la page, comme un navigateur ;
- les requêtes mal formées reçoivent une révision valide, pour que leur 400 tienne à la cause visée ;
- les deux tests de la garde interne lisent la révision avant l'injection ;
- le contrat des modules autorise `forge_design.revision_tokens`.

## Mutations

Script hors dépôt, lancé depuis le scratchpad, avec restauration à l'octet et empreinte vérifiée. Résultat : **16/16 tuées**.

| Mutation | Tuée par |
|---|---|
| Révision non envoyée par un formulaire (suppression) | `test_acc_004_two_tabs_never_touch_the_wrong_block` |
| Révision ignorée côté Web | idem |
| Mismatch accepté (condition inversée) | idem |
| Comparaison après mutation (avant écriture) | `test_every_action_refuses_a_stale_view_without_writing` |
| Comparaison après écriture | `test_acc_004_…` |
| 409 transformé en 303 | idem |
| Écriture malgré le conflit | idem |
| Mauvais message | `test_message_matches_the_contract` (première passe : survivante, le test importait la constante ; texte figé depuis) |
| Une action de structure sans garde (`remove`) | `test_acc_004_…` |
| Une action de propriété sans garde (`tailwind_add`) | `test_every_action_refuses_a_stale_view_without_writing[tailwind_add]` |
| Jeton fondé sur le seul mtime | `test_identical_bytes_replacement_is_a_new_revision` |
| Jeton fondé sur la seule taille | idem |
| Jeton non lié à la révision complète (sans inode ni ctime) | idem |
| Sélection = chemin soumis au lieu de la racine | `test_conflict_page_shows_current_design_root_selection_and_reload` |
| Lien « Recharger » absent | idem |
| Révision mal formée acceptée | `test_missing_empty_or_malformed_revision_is_400` |

## Chromium

Acceptance ciblée par `scripts/acceptance/run.sh` : roue 0.2.0 reconstruite (166 fichiers, `revision_tokens.py` compris, 34 ressources vérifiées), venv neuf hors ligne, projets reconstruits, étapes `ONLY="éditeur"`.

| Étape | Résultat |
|---|---|
| Lecture, action enregistrée, sans-modification, preview statique | OK |
| **Vue périmée** : la `table` est affichée ; l'onglet B supprime le bloc 0 avec son propre formulaire et sa révision ; état S1 | OK |
| L'onglet A soumet sa vue | Message 409 visible ; design **identique octet pour octet à S1** (SHA-256) ; `[table, section]` intact |
| Rechargement par le lien du message, puis action valide | « Modification enregistrée. » |

Instantanés des 10 projets : conformes. Aucun processus restant.

## Firefox

Mêmes étapes, OK ; instantanés conformes ; aucun processus restant.

## Performance

| Mesure | Valeur |
|---|---|
| Garde seule (jeton et comparaison), moyenne sur 20 000 | **4,2 µs** |
| Action `tailwind_add`/`remove` par HTTP, garde active | Médiane 2,50 ms, pire 2,80 ms |
| Même action, garde neutralisée | Médiane 2,50 ms, pire 2,83 ms |

Le surcoût est négligeable : aucune lecture supplémentaire (la révision vient de la lecture que l'action faisait déjà), aucun cache.

## ToolRegistry

Cinq Tools, inchangés.

## Graphic Core

Aucune modification ; 134/134 tests Node.

## Modules

Circuit et Flowchart ne sont pas modifiés. Leur jeton est inchangé (vecteurs). L'étape « modules » de l'acceptance (renommage d'un nœud et d'une arête Flowchart, déplacement d'un composant Circuit au clavier) passe dans Chromium et Firefox.

## Dette / limites

- **Contrôle optimiste.** Pas de verrou, pas de session d'édition, pas de fusion : après un conflit, l'utilisateur recharge et refait son action.
- **Fenêtre de `write_design`.** Entre threads d'un même processus, deux publications simultanées restent possibles (voir Concurrence). Cette fenêtre est inatteignable avec le serveur actuel, et le design n'est jamais mélangé.
- **Identité des blocs.** `NodePath` reste fondé sur des indices : toute modification du design périme la page, même une modification sans rapport avec le bloc visé. Une identité stable des blocs relèverait d'un autre ticket.
- **Preview réelle.** Hors périmètre (ACC-003 reste ouvert).

## Impact sur ACC-004

**ACC-004 est corrigé.** Une vue d'éditeur périmée ne peut plus modifier silencieusement le mauvais bloc : 409, aucune mutation, aucune écriture, design inchangé, invitation à recharger. C'est démontré par HTTP sur les 10 actions et dans Chromium, Firefox et Firefox sans JavaScript.

Le rapport FD-ACCEPTANCE-001 n'est pas modifié : il reste l'historique du rejet. Le gate SéquenCiel reste **fermé** jusqu'à la correction d'ACC-003 et à FD-ACCEPTANCE-002.

## Recommandation ticket suivant

1. **FD-REALPREVIEW-007** : ajouter `-B` à la commande de la preview réelle, ce qui ferme ACC-003.
2. **FD-ACCEPTANCE-002** : rejouer `scripts/acceptance/run.sh` en entier pour viser ACCEPTED_WITH_MINOR_ISSUES et ouvrir le gate.
3. *(Facultatif, hors du chemin critique)* **FD-SAFEWRITE-004** : rendre exclusif « contrôler, puis publier » dans `write_design` (verrou par fichier ou compare-and-swap), pour fermer la fenêtre observée entre threads.

## Fichiers créés

- `forge_design/revision_tokens.py`
- `tests/test_revision_tokens.py`
- `tests/test_web_editor_revision.py`
- `docs/rapports/FD-EDITOR-007.md`

## Fichiers modifiés

- `forge_design/web/editor.py` : jeton, garde, rendu du 409
- `forge_design/web/templates/editor.html` : champ `revision` dans les 11 formulaires, lien « Recharger »
- `forge_design/modules/actions.py` : délégation au calcul commun, octets inchangés
- `tests/test_web_editor.py` : helper `action()`, requêtes mal formées, tests de la garde interne
- `tests/test_modules_contract.py` : dépendance autorisée
- `scripts/acceptance/scenario.mjs` : étape « vue périmée »
- `scripts/acceptance/nojs.mjs` : étapes sans JavaScript, filtre `ONLY`
- `docs/editor/structural-editor.md`, `docs/modules/module-actions.md`, `docs/03-roadmap.md`

Non modifiés : `DesignFile`, `NodePath`, le format `.design.json`, `write_design`, `FD-ACCEPTANCE-001.md`.

## Validation finale

| Commande | Résultat |
|---|---|
| `python -m compileall -q forge_design tests` | OK |
| `ruff check forge_design tests` | All checks passed |
| `ruff format --check .` | 441 fichiers formatés |
| `pyright` (strict) | 0 erreur, 0 avertissement |
| `git diff --check` | OK |
| `pytest` (suite complète) | 5 092 passed |
| `node --test tests/js/graphics/*.test.mjs` | 134/134 |
| `mkdocs build --strict` | Sans objet (MkDocs non configuré) |
| Roue 0.2.0, venv neuf, hors ligne | `pip check` OK, inspection OK |
| Acceptance ciblée (éditeur, modules) | Chromium et Firefox OK, sans JavaScript OK, instantanés conformes |
| Mutations | 16/16 tuées |

## État Git final

Un seul commit : `fix: refuser les actions sur un design périmé (FD-EDITOR-007)`, au-dessus de `97a214a`. Il n'a pas été poussé. `docs/rapports/FD-CONTRACT-001.md` reste modifié localement, hors commit. La version reste 0.2.0.
