# Rapport — FD-SEQUENCIEL-006

Première édition contrôlée réelle, par Forge Design 0.3.0, du Design versionné
de SéquenCiel `mvc/views/home/index.design.json`.
Date : 2026-10-19.

## Objectif

Démontrer que Forge Design 0.3.0 sait modifier volontairement et proprement le
vrai Design de SéquenCiel :

- ouverture ;
- geste structurel unique ;
- sauvegarde par `write_design` avec révision attendue et verrou ;
- diff minimal, nouvelle révision, réouverture à l'identique ;
- sans toucher `home/index.html`, `home/index.view.json`, le code applicatif ni
  les fichiers utilisateur.

**Verdict : SEQUENCIEL_EDIT_PASS_WITH_ISSUES.** L'édition est conforme sur tous
les points exigés. Les écarts ne portent que sur la documentation, la
performance et le harnais, et aucun ne bloque.

## Baseline Forge Design

Dépôt à `f15a90d` (FD-SEQUENCIEL-005R2), sur `main`, avec 9 commits d'avance
sur `origin/main`. `forge_design/` et `tests/` ne sont pas modifiés.
`FD-CONTRACT-001.md` (modification utilisateur) et les fichiers non suivis
historiques sont préservés.

Le code exécuté est la roue `tmp/fd-release-004-dist/forge_design-0.3.0-py3-none-any.whl`,
de SHA-256 `d7e9f2ec…c2b1`, installée dans un venv neuf hors du dépôt. Il n'y a
ni installation éditable ni `PYTHONPATH`.

## Baseline SéquenCiel

| Élément | Valeur |
|---|---|
| Branche | `main` |
| HEAD | `d7c09c5714b82830d7d5cca8de123e3bab9ba5b4` (SC-FORGE-002), précédé de `07a4aeed` (SC-FORGE-001) |
| `app.application` | Présent (SC-FORGE-001) |
| `home/index.view.json`, `home/index.design.json` | Présents (SC-FORGE-002) |
| `.forge-design/` | Absent |

## SC-FORGE-002

Le ticket SéquenCiel `d7c09c57` a créé la paire :

- `home/index.view.json`, avec un `context` vide ;
- `home/index.design.json`, réduit à `page › section.text-center py-6`.

Ses octets sont canoniques : ce sont ceux que produit le sérialiseur de
`write_design`. Le ticket a aussi établi trois points :

- la Real Preview de l'éditeur est refusée, à cause de 36 routes GET au template
  non déterminable ;
- la Real Preview depuis Route Explorer reste disponible ;
- `tests/meta/test_suite_sans_base.py` sature `/tmp`, et
  `tests/test_aide_contextuelle.py` réécrit des artefacts ignorés de `guide/`.

Aucun de ces deux tests n'a été lancé ici.

## État Git initial

| Contrôle | Valeur |
|---|---|
| Statut (`GIT_OPTIONAL_LOCKS=0`) | 20 fichiers non suivis, préexistants ; empreinte `cdfb4f1f…`, identique à SC-FORGE-001 et SC-FORGE-002 |
| Modifications suivies ou indexées | Aucune |
| Processus avec SéquenCiel pour cwd | Aucun (hors l'outil de relevé) |
| Écouteurs 8090, 8092, 33389, 8765, 9341 | Aucun |

Empreintes SHA-256 avant édition :

| Fichier | SHA-256 (préfixe) |
|---|---|
| `mvc/views/home/index.design.json` | `c74a9d398fe9eb29` |
| `mvc/views/home/index.view.json` | `d0999dfe9501e354` |
| `mvc/views/home/index.html` | `1a64019788b5c11d` |
| `mvc/controllers/home_controller.py` | `9722c0b73e52eb13` |
| `mvc/routes/__init__.py` | `db14a3268d88f1a5` |
| `app.py` / `wsgi.py` | `bdfac7068adb2e11` / `5ed007afde6a6d4f` |

## T0 / T1

La méthode est celle des tickets précédents : SHA-256 complet hors dossiers
lourds, métadonnées seules pour `.git`, `.venv`, `node_modules`, `tmp` et
`sauvegardes`.

| Instantané | Heure | Entrées | Comparaison |
|---|---|---:|---|
| T0 | 16:57:05 | 519 603 (7 832 complet / 511 770 lourd) | — |
| T1 | 17:02:16 (5 min 11 s après) | 519 603 | **= T0**, même HEAD, même statut |

La gate de stabilité est franchie.

## HOME / XDG isolés

| Élément | Valeur |
|---|---|
| Lancement | `env -i`, avec `HOME` et les quatre `XDG_*` dans le scratchpad |
| Environnement | `PATH=/usr/bin:/bin`, `LANG=C.UTF-8` |
| cwd / options | `/tmp`, `--no-browser`, sans module |
| Écoute | `127.0.0.1:8765` |
| HOME isolé à la fin | `.config/forge-design/recent-projects.json` seul (77 octets) |

Chromium tournait en headless, avec un profil neuf détruit à la fin de chaque
phase, et pilotait la page par vrais clics souris (CDP).

## Design initial

```json
{
  "version": "0.1",
  "view": "home/index",
  "source_contract": "home/index.view.json",
  "root": {
    "type": "page",
    "children": [
      {
        "props": {
          "class": "text-center py-6"
        },
        "type": "section"
      }
    ]
  }
}
```

Dans l'éditeur, avant le geste :

- un seul `h1` ;
- l'arbre `page › section` ;
- « Contrat : home/index.view.json » ;
- aucune alerte ni violation CSP ;
- aucun contrôle de génération (aucun bouton « Générer » ni « Écrire la vue »).

## ViewContract

`home/index.view.json` (`name` `home/index`, `template`
`mvc/views/home/index.html`, `context` vide) n'a été ni lu en écriture ni
modifié. Son empreinte est identique avant et après.

## Template source

`mvc/views/home/index.html` (406 octets) : `extends "layouts/base.html"`, bloc
`title`, puis `include "partials/accueil_bienvenue.html"`. Il n'est jamais
écrit. Le Design ne le génère pas, et l'aperçu indicatif ne prétend pas le
reproduire (§42).

## Geste retenu

**Ajouter un `container` vide sous la `section`**, avec l'action `append`,
`parent=0` et `block_type=container`.

- L'imbrication `section → container` est autorisée par la matrice v0.1 :
  l'éditeur propose `alert`, `card`, `container`, `form`, `grid`, `table` et
  `text`.
- Le geste est réversible par l'action `remove`, et déterministe.
- Il n'ajoute ni texte, ni binding, ni action, ni classe, ni donnée métier.
- Il ne demande aucun contexte nouveau.

## Révision avant

L'éditeur ne montre pas la révision en clair. Il porte, dans chaque formulaire
d'action, un jeton opaque de 64 caractères lié au chemin du Design et à la
révision complète lue (taille, mtime, SHA-256, device, inode, ctime). Il n'est
jamais interprété comme un hash métier. Le rapport n'en cite qu'une empreinte
de comparaison.

| Vue | Jeton (SHA-256 du jeton, 12 car.) |
|---|---|
| A, à l'ouverture | `8ea799466173` |
| B, à l'ouverture | `8ea799466173`, même révision |

Chaque page ne contient qu'une seule valeur de révision distincte.

## Édition

Le geste unique a été fait dans la **vue B**, second onglet du même navigateur :

1. sélection de la section par l'URL `node=0` ;
2. choix de `container` dans « Ajouter un enfant » ;
3. vrai clic sur « Ajouter » à 17:10:39,441.

| Étape (trace serveur) | Instant |
|---|---|
| `POST /editor/action` reçu | 17:10:39,479 |
| Verrou ouvert | 17:10:39,495 |
| Temporaire créé | 17:10:39,524 |
| `renameat` vers `index.design.json` | 17:10:39,538 |
| Réponse **303** vers `…&node=0.0&notice=saved` | 17:10:39,545 |
| Page rechargée | 17:10:40,770 |

La sauvegarde a duré 66 ms côté serveur. Le rechargement de l'éditeur en a pris
1,14 s (voir Observations Forge Design). Après le geste, B affiche l'arbre
`page › section › container`, le bloc sélectionné `container` et aucune alerte.

Le serveur n'a reçu au total que **deux** POST d'action. Le premier est ce
geste ; le second est la soumission périmée de A, refusée (voir Stale / 409).

## Écriture Design

Le pipeline `write_design` observé est celui de FD-DESIGN-004 et FD-EDITOR-008 :

1. ouverture du verrou ;
2. temporaire `.forge-design-write-<aléatoire>` créé avec `O_CREAT|O_EXCL|O_NOFOLLOW`
   dans `mvc/views/home/` ;
3. `renameat` atomique vers `index.design.json`, qui prend un nouvel inode ;
4. nettoyage du temporaire, `unlinkat` → `ENOENT`, car il a été consommé par le
   `rename`.

Aucun temporaire ne subsiste. Le fichier fait 263 octets avant et 342 octets
après.

## Lock

| Chemin créé (17:10:39,49) | Type | Mode | Taille |
|---|---|---|---:|
| `.forge-design/` | dossier | 0700 | — |
| `.forge-design/locks/` | dossier | 0700 | — |
| `.forge-design/locks/design-97eccec994daf0964a53d89190757cb9ffeb89b32d5daeb5ca1fa756636cdf52.lock` | fichier | 0600 | 0 |

Le nom du verrou est le SHA-256 de `home/index.design.json`, chemin relatif à
`mvc/views/`, et non le chemin depuis la racine. Le fichier est ouvert avec
`O_RDWR|O_CREAT|O_NONBLOCK|O_NOFOLLOW|O_CLOEXEC`. La soumission de A a réutilisé
le même verrou (`mkdirat` → `EEXIST`, puis réouverture). Les fichiers restent
après libération, comme le prévoit FD-EDITOR-008. Ils n'ont pas été supprimés
(§57).

## Diff Design

```diff
@@ -9,7 +9,12 @@
         "props": {
           "class": "text-center py-6"
         },
-        "type": "section"
+        "type": "section",
+        "children": [
+          {
+            "type": "container"
+          }
+        ]
       }
     ]
   }
```

C'est le geste et rien d'autre : 6 lignes ajoutées et 1 modifiée par la
virgule. Il n'y a aucun réordonnancement ni aucun bruit de sérialisation, ce
qui confirme les octets canoniques de SC-FORGE-002. Le nouveau SHA-256 du Design
commence par `248ce0d1e0384fff` (blob Git `b024b26c`).

## Snapshot S-WRITE

Pris après la séance d'édition (17:10:50) et comparé à T1 :

| Différence | Classement |
|---|---|
| `mvc/views/home/index.design.json` : taille, mtime, ctime, inode, contenu | EXPECTED |
| `.forge-design/`, `locks/` et le fichier de verrou : ajoutés | EXPECTED (§26) |
| Dossiers `.` et `mvc/views/home` : mtime et ctime | EXPECTED (création de `.forge-design/`, `rename`) |
| Statut Git | 22 lignes : les 20 d'origine, le Design modifié et le verrou non suivi |

Il n'y a **aucune autre différence**.

## Révision après

| Vue | Jeton |
|---|---|
| B, après sauvegarde | `9b831ad0c58a` (**changé**) |
| A, après son 409 | `9b831ad0c58a` (révision courante réaffichée) |
| B, rechargée | `9b831ad0c58a` |
| Réouverture | `9b831ad0c58a` |

## Relecture

Après rechargement de B (`/editor?design=home%2Findex.design.json`), l'arbre est
`page › section › container`, avec le contrat résolu, aucune alerte et la même
révision.

## Fermeture / réouverture

L'onglet B a été fermé, puis A a navigué vers `/templates` avant de rouvrir
l'éditeur. Résultat : arbre identique (`""` › `0` › `0.0`), révision stable
(`9b831ad0c58a`) et aucune alerte.

## Validation Design

Relecture par les API de la roue (`python -I -B`, cwd `/tmp`) : **10/10**.

| Contrôle | Résultat |
|---|---|
| `read_design` | 0 issue |
| Arbre | `page › section › container`, le container valant exactement `{"type": "container"}` |
| `validate_design_nesting` | Valide |
| `validate_design_bindings`, `validate_table_bindings` | Valides |
| `validate_conditional_bindings` | Valide |
| `validate_form_fields`, `validate_submit_buttons` | Valides |

## Validation ViewContract

| Contrôle | Résultat |
|---|---|
| `read_view_contract(source_contract)` | Contrat valide, 0 issue |
| `analyze_view_contract_links` | Lien `home/index.html` inchangé, 0 issue, inventaire complet |
| SHA-256 | Identique |

## Non-régression template

`mvc/views/home/index.html` est **identique octet pour octet** (SHA-256
`1a64019788b5c11d…`). Sur les 7 empreintes du §13, seul le Design diffère : le
contrat, le template, le contrôleur, `mvc/routes/__init__.py`, `app.py` et
`wsgi.py` sont identiques. Aucun `.html` n'a été ouvert en écriture.

## Preview indicative

`GET /editor/preview?design=home%2Findex.design.json&mode=desktop` donne 200,
« Données fictives : complètes — Rendu : complet », sans alerte ni violation
CSP. Le canevas rendu est :

```html
<div data-forge-design-type="page" data-forge-design-preview="page">
  <section data-forge-design-type="section" class="text-center py-6">
    <div data-forge-design-type="container"></div>
  </section>
</div>
```

C'est le Design modifié, conformément au §42, et non le template complet.

## Real Preview via Route Explorer

Le bouton de Real Preview de l'éditeur n'a pas été utilisé (§5). La chaîne
`GET / → HomeController.index → home/index.html → home/index.view.json` est
« disponible ». Vrai clic sur « Prévisualiser réellement », sous `strace -f` :

| Point | Résultat |
|---|---|
| Enfant | `.venv/bin/python -I -B -u child_bootstrap.py --port 41579`, cwd SéquenCiel, nouvelle session, `stdin` `/dev/null`, 4 variables (`APP_ENV`, `HOME`, `LANG`, `PATH`) |
| État | `running` ; iframe sur le proxy `127.0.0.1:41901` |
| `/health` | 200 |
| `GET /` | 302 |
| `/login` | 503 |
| `/static` | 16 requêtes, toutes 200, servies par le proxy |
| Maintien 30 s | 1 thread, RSS 78 532 Kio constante, 0 descendant |
| Stop | Groupe vide, ports `41579` et `41901` fermés |
| S-START, S-LIVE, S-STOP | **= S-WRITE** |
| Écritures | Seulement `/dev/null` et les temporaires `/tmp` de la rafale weasyprint connue ; 0 dans SéquenCiel |

Le comportement qualifié en FD-SEQUENCIEL-005R2 est reproduit à l'identique.
L'édition du Design n'a pas cassé le projet. La page affiche toujours le
template existant (§47), avec la violation CSP de style déjà connue.

## DB arrêtée

`127.0.0.1:33389` n'avait aucun écouteur au début, pendant la séance et à la
fin. Une seule tentative `connect` refusée a eu lieu, celle de `/login`, comme
en 005R2. `tmp/base-locale/demarrer.sh` n'a pas été lancé.

## Stale / 409

Le test a été fait sur le vrai Design, **sans seconde mutation** (§50-51).

1. A et B sont ouverts à la même révision (`8ea79946…`).
2. Le geste unique est fait dans B : 303, puis la nouvelle révision.
3. Depuis A, sa page périmée resoumet le même `append container`, avec l'ancien
   jeton.

Résultat de la soumission de A :

| Point | Constat |
|---|---|
| Réponse | **409** |
| Message | « Le design a été modifié depuis l'affichage de cette page. Rechargez l'éditeur avant de recommencer. » |
| Lien | « Recharger l'éditeur » |
| Affichage | La page réaffiche le Design courant et la révision courante |
| Trace | Ouverture du verrou seulement : ni temporaire, ni `rename`, ni écriture |
| Contrôle | Le Design n'a toujours qu'**un** container (relecture API et S-WRITE) |

Dans l'éditeur, le refus intervient avant toute interprétation de l'action.
Aucune seconde écriture n'a donc eu lieu.

Entre le clic dans A (17:10:40,779) et la réception du POST par le serveur
(17:10:45,836), il s'est écoulé environ 5 s. Le serveur était inactif pendant
ce temps et a répondu en 70 ms. Ce délai vient du navigateur, dont A était
l'onglet d'arrière-plan. C'est un artefact du harnais, pas un comportement de
Forge Design.

## .forge-design

| Question | Réponse |
|---|---|
| Créé ? | Oui, à 17:10:39,491, par la première sauvegarde, comme prévu par le contrat |
| Contenu | `locks/` et un fichier de verrou vide (tableau Lock) |
| Locks ? | Oui, un fichier par Design muté |
| History ? | **Non**. `history.jsonl` n'est écrit que par les actions `generate_template` et `write_specialized_resource` |
| Autres fichiers ? | Aucun |
| Versionné ? | Non (§58) |

`.forge-design/` n'est pas versionné, parce que le contrat de stockage ne cite
pas `locks/` parmi les éléments de la zone B. Le verrou apparaît donc comme
fichier non suivi de SéquenCiel. Forge Design ne crée pas de `.gitignore`, et
la décision revient au porteur (voir Observations Forge Design).

## Historique

Aucun historique de Design n'est créé : pas de `history.jsonl` ni d'autre
journal. L'éditeur ne journalise pas les sauvegardes de Design, ce qui est
conforme au contrat de stockage actuel.

## Filesystem

Écritures du serveur Forge Design pendant toute la séance d'édition, d'après la
trace complète :

| Zone | Écritures |
|---|---|
| HOME isolé | `recent-projects.json`, par temporaire puis `rename` (ouverture du projet) |
| SéquenCiel | `mkdir .forge-design` et `locks`, verrou, temporaire, `rename` du Design |
| Ailleurs | Aucune |

Écritures du runner pendant la Real Preview : `/dev/null` et `/tmp`
(weasyprint), toutes nettoyées.

FINAL est **identique** à S-WRITE. Il n'y a aucune écriture inconnue.

## Réseau

| Phase | Constat |
|---|---|
| Édition | Un seul thread serveur, aucun `connect` ni `bind` ; trafic limité à Chromium ↔ `127.0.0.1:8765` |
| Real Preview | Proxy ↔ enfant sur loopback ; un `connect` refusé vers 33389 |
| Les deux | Aucune connexion externe |

## Secrets

Le contrôle a porté sur 49 secrets candidats et 3 identifiants, extraits en
mémoire. Surfaces vérifiées :

- le Design et le contrat ;
- les données du scénario et les pages HTML enregistrées : éditeur, 409, aperçu,
  états de la preview ;
- le journal du serveur ;
- toutes les traces `strace` de l'édition et de la preview.

Résultat : **0** correspondance et **0** identifiant. Le Design et le contrat ne
contiennent que de la structure.

## Processus

| Phase | Constat |
|---|---|
| Édition | 0 `clone` ou `execve` du serveur, 0 enfant |
| Real Preview | Un seul enfant, la rafale weasyprint connue, aucun survivant |
| Fin | Aucun Chromium, serveur ni enfant restant ; aucun profil restant |

Le surveillant `/proc` (10 605 relevés pendant l'édition) a vu, avec SéquenCiel
pour cwd :

- `git config`, `git status -z -uall` et `git check-ignore`, lancés à
  17:10:40,7 par l'hôte d'extensions **VS Code** de la fenêtre du porteur, où
  le rapport SC-FORGE-002 est ouvert. Ce sont des commandes de lecture :
  `.git/index` reste daté du commit SC-FORGE-002 (16:47:41). Classement :
  EXPECTED, environnement du porteur.
- le `git --no-optional-locks status` de l'outil d'instantané.

## Snapshot final

FINAL est pris après l'arrêt de Forge Design.

- **FINAL = S-WRITE.**
- FINAL comparé à T1 : 3 ajouts (`.forge-design/`, `locks/` et le fichier de
  verrou), le Design modifié, et les mtime et ctime de `.` et de
  `mvc/views/home`.
- Rien d'autre : aucun fichier suivi, aucun fichier non suivi préexistant, rien
  dans `.venv` ni `tmp`.

## État Git final SéquenCiel

| Élément | Valeur |
|---|---|
| HEAD | `cd7cc5b41765f65b0fe2aeac211a03d7883dcb21` |
| Statut | Les 20 fichiers non suivis d'origine, inchangés, plus `?? .forge-design/locks/design-97ecce….lock` |
| Push | Aucun |

## Commit SéquenCiel

`cd7cc5b4 feat(forge-design): première édition contrôlée du design accueil`.
Il ne contient qu'un fichier, `mvc/views/home/index.design.json` (+6/−1). Le
message indique que le geste est voulu par le porteur et fait dans le cadre de
FD-SEQUENCIEL-006, et que l'état local `.forge-design/` n'est pas versionné.
Aucun commit ne mélange les deux dépôts.

## État Git final Forge Design

Un commit, `test: qualifier la première édition réelle sur SéquenCiel
(FD-SEQUENCIEL-006)`, contient ce rapport et la roadmap. Il n'est pas poussé :
10 commits d'avance sur `origin/main`. `forge_design/` et `tests/` sont sans
modification, et `FD-CONTRACT-001.md` est préservé.

## Observations SéquenCiel

| # | Observation | Classement |
|---|---|---|
| 1 | Paire SC-FORGE-002 éditable telle quelle, octets canoniques, diff minimal | EXPECTED |
| 2 | La Real Preview de `GET /` reproduit 005R2 : rafale weasyprint, 503 de `/login` avec la base arrêtée | EXPECTED_APPLICATION_SIDE_EFFECT |
| 3 | Le verrou non suivi apparaît dans `git status` : une règle d'ignorance ou un commit est à trancher par le porteur | SEQUENCIEL-ISSUE mineure (décision de dépôt) |
| 4 | L'extension Git de VS Code suit SéquenCiel dès qu'un de ses fichiers est ouvert, et relance `git status` à chaque écriture | EXPECTED (environnement) |

## Observations Forge Design

| # | Observation | Gravité | Classement |
|---|---|---|---|
| 1 | Cycle d'édition complet conforme sur un vrai projet : ouverture, geste unique, verrou, écriture atomique, nouvelle révision, 409 sur vue périmée sans écriture, réouverture identique | — | EXPECTED |
| 2 | Le **contrat de stockage** (`docs/storage/storage-contract.md`, §3) ne recense pas `.forge-design/locks/`, introduit par FD-EDITOR-008, alors qu'il exige un ticket pour tout nouveau nom. Sa règle « tout ce que Forge Design écrit dans un projet est destiné à être partagé par Git » laisse sans réponse le statut Git des verrous, qui sont un état de coordination local et vide | Mineure | FORGEDESIGN-ISSUE (documentation) |
| 3 | Chaque affichage de l'éditeur recalcule la sélection Real Preview sur tout l'inventaire des routes, soit environ 1,1 s par page sur 629 routes. La RSS du serveur passe de 45,7 à 120 Mio pendant la séance | Mineure | FORGEDESIGN-ISSUE (performance) |
| 4 | La Real Preview de l'éditeur est refusée (36 routes au template indéterminable, SC-FORGE-002). Hors périmètre ici (§6) | Mineure | FORGEDESIGN-ISSUE (ouvert) |
| 5 | L'éditeur ne montre pas la révision en clair : seul le jeton caché des formulaires la porte | Information | EXPECTED (jeton opaque) |
| 6 | `favicon.ico` en 404 | Cosmétique | FORGEDESIGN-ISSUE (préexistant) |
| 7 | Harnais : une première séance a avorté **avant tout geste**, sur une expression régulière mal échappée du scénario (1 POST d'ouverture, des GET, 0 mutation, S-ECHEC1 = T1). Le serveur a été arrêté et la séance rejouée avec un serveur et un HOME neufs, donc avec un seul POST d'ouverture | — | EXPECTED (harnais, sans effet) |
| 8 | Harnais : l'onglet A en arrière-plan retarde de 5 s l'envoi de son POST | — | EXPECTED (navigateur) |

## Classification

| Catégorie | Constats |
|---|---|
| EXPECTED | Ouverture, geste unique, 303, diff minimal, révision changée puis stable, 409 sans écriture, relecture et réouverture identiques, création de `.forge-design/locks/`, aperçu indicatif, Real Preview conforme à 005R2, 0 écriture inattendue, 0 fuite |
| EXPECTED_APPLICATION_SIDE_EFFECT | Rafale weasyprint et temporaires `/tmp` nettoyés ; 503 de `/login` avec la base arrêtée |
| SEQUENCIEL-ISSUE | Statut Git du verrou à trancher |
| FORGEDESIGN-ISSUE | `locks/` absent du contrat de stockage ; recalcul des routes à chaque page de l'éditeur ; Real Preview de l'éditeur refusée ; `favicon.ico` |
| FORGE-LIMITATION | Aucune nouvelle (la CSP du cœur reste celle de 005R2) |
| UNKNOWN | Aucun |
| BLOCKING | **Aucun** |

## Verdict

**SEQUENCIEL_EDIT_PASS_WITH_ISSUES**

| Condition du §74 | Constat |
|---|---|
| Design ouvert | Oui |
| Geste unique effectué | Oui : `append container`, un seul POST accepté |
| `write_design` réussi | Oui : 303, temporaire puis `rename`, 66 ms |
| Diff minimal | Oui : le container seul |
| Révision changée | Oui : `8ea79946…` → `9b831ad0…` |
| Relecture identique | Oui : rechargement et réouverture |
| ViewContract intact | Oui |
| Template intact | Oui, octet pour octet |
| Aucune écriture métier inattendue | Oui : FINAL = S-WRITE = T1 + Design + `.forge-design/` |
| Real Preview Route Explorer fonctionnelle | Oui : 200 / 302 / 503 / 16 × 200, Stop propre |

« With issues » (§75) tient à des dettes non bloquantes : le statut de `locks/`
absent du contrat de stockage, le recalcul des routes à chaque page de
l'éditeur, et le verrou non suivi à trancher dans SéquenCiel.

## Fichiers créés

- `docs/rapports/FD-SEQUENCIEL-006.md`

Dans SéquenCiel, par l'éditeur : `.forge-design/`, `.forge-design/locks/` et le
fichier de verrou, non versionnés.

Les outils (`edit006.sh`, `cycle006.sh`, phase `edit` du scénario,
`sc006_validate.py`) et les traces restent dans le scratchpad. Les instantanés,
empreintes et états Git sont dans `tmp/fd-sequenciel-006/`, ignoré par Git.

## Fichiers modifiés

- `docs/03-roadmap.md` : entrées SC-FORGE-002 et FD-SEQUENCIEL-006, clôture du
  parcours, suite.
- Dans SéquenCiel (commit séparé) : `mvc/views/home/index.design.json`.

Non modifiés : `forge_design/`, les tests, le kit d'acceptance,
`FD-CONTRACT-001.md`, `home/index.html`, `home/index.view.json` et le code de
SéquenCiel.

## Validation finale

| Commande (dépôt Forge Design) | Résultat |
|---|---|
| `python -m compileall -q forge_design tests` | OK |
| `ruff check .` | OK |
| `ruff format --check .` | 480 fichiers formatés |
| `pyright` | 0 erreur, 0 avertissement |
| `pytest` ciblé, 19 fichiers : design (I/O, verrou, modèles, imbrication, schéma, bindings), éditeur (structure, propriétés, Web, révision, aperçu), jetons de révision, contrats | **1 357 réussis** (1 354 au premier passage, plus les 3 tests de sockets rejoués) |
| `git diff --check` | OK |
| Tests qui lisent `docs/` (`test_design_schema.py`, `test_view_contract_schema.py`) | Réussis, après la rédaction |

Trois tests de sockets (`test_unreadable_targets[socket]`, `test_special_files`)
n'ont réussi qu'avec un `--basetemp` court. Le chemin du scratchpad dépasse la
limite AF_UNIX : c'est une contrainte d'environnement connue, sans lien avec le
ticket.

Côté SéquenCiel, les contrôles sont :

- JSON strict, Design et contrat valides (API) ;
- `home/index.html` inchangé ;
- `git diff --check` réussi ;
- `test_suite_sans_base` et `test_aide_contextuelle` non lancés (§65).

Stockage : environ 11 Mio de traces dans le scratchpad (édition, Real Preview
et séance avortée), et 8 instantanés de 7,9 Mio chacun sur `/`. `/tmp` a gardé
plus de 510 Mio libres, sans incident.

## Conclusion du parcours

**Parcours d'intégration réel Forge Design ↔ SéquenCiel : TERMINÉ.**

Sur une vraie application Forge (629 routes, 86 entités, 497 templates, 251
migrations), le parcours a qualifié la chaîne complète :

- détection du projet et lecture (FD-SEQUENCIEL-001) ;
- Inspector, Routes, Entités, Templates, Migrations, Debug ;
- `project:audit` (002), `doctor` (003), `project:check` (004) ;
- Real Preview depuis Route Explorer (005, 005R, 005R2, après SC-FORGE-001) ;
- adoption d'une première paire contrat + Design (SC-FORGE-002) ;
- édition réelle, révision, verrouillage, sauvegarde atomique, refus stale et
  réouverture (006).

Cela ne signifie pas que :

- toutes les dettes de Forge Design sont corrigées ;
- toutes les routes sont parfaitement analysées ;
- les vues de SéquenCiel sont migrées en Design (une seule l'est) ;
- une production publique est prête.

Dettes hors chemin critique, qui restent ouvertes :

- FD-ROUTES-023 : borne de templates pour les grands projets ;
- FD-REALPREVIEW-009 : contrôle statique du point d'entrée ;
- la sélection Real Preview de l'éditeur : routes au template indéterminable, et
  conflit de déclarations GET ;
- la CSP de la Real Preview face aux enveloppes WSGI du projet ;
- la RSS de `/routes` et le recalcul des routes à chaque page de l'éditeur ;
- `locks/` absent du contrat de stockage, et le statut Git des verrous ;
- côté SéquenCiel : weasyprint importé au niveau module, et session en base dès
  `/login` ;
- `favicon.ico` ;
- la licence publique.
