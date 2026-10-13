# Rapport — FD-DEBUG-006

Renforcer le masquage commun des secrets de Debug Center. Date : 2026-10-13.

## Objectif

Élargir le masquage textuel défensif de `redact_debug_text` pour qu'il couvre deux familles de secrets :

- les clés suffixées (`DB_PASSWORD`, `SERVICE_TOKEN`, `OPENAI_API_KEY`…) ;
- le mot de passe des URL de connexion.

Le masquage s'applique au journal runtime comme à la sortie de `forge doctor`. Le ticket ne change ni la signature, ni le marqueur, ni les données sources, et n'ajoute aucun stockage. Le masqueur reste non exhaustif.

| Décision | Résultat |
|---|---|
| A. Nouvelle fonctionnalité métier ? | Non |
| B. Nouveau Tool ? | Non : cinq Tools |
| C. Nouveau scanner de secrets ? | Non : formes textuelles seulement |
| D. Masquage plus défensif ? | Oui |
| E. Journal source modifié ? | Non (vérifié octet par octet) |
| F. `forge doctor` modifié ? | Non : runner et `clean_output` inchangés |
| G. Graphic Core modifié ? | Non : 134/134 |

## État Git initial

| Élément | Valeur |
|---|---|
| HEAD | `4bf67ab` (FD-RUNTIME-001), qui contient FD-ROUTES-021 et FD-PERF-001 |
| `origin/main` | `e411d0c` ; 0 commit en retard, 3 en avance |
| Arbre | Seul `docs/rapports/FD-CONTRACT-001.md` modifié par l'utilisateur, préservé et hors commit |
| Version | 0.2.0, inchangée |

L'identifiant FD-DEBUG-006 était libre : il n'apparaissait que comme recommandation dans le rapport FD-RUNTIME-001, et les rapports existants s'arrêtent à FD-DEBUG-005.

## Périmètre

Le ticket ne modifie que `forge_design/forge/debug_redaction.py`. Aucun appelant n'a changé : il n'y a aucune adaptation d'API. S'ajoutent des tests, de la documentation et ce rapport.

## Masqueur avant ticket

Deux expressions régulières, toutes deux précédées de `(?<![\w-])` :

1. **En-têtes** : `authorization`, `cookie` et `set-cookie` masqués jusqu'à la fin de ligne.
2. **Affectations** : 12 clés exactes, `=` ou `:`, valeur nue, citée ou citée sans fin.

Ce lookbehind excluait `_` et `-`, ce qui produisait trois défauts :

- `DB_PASSWORD=`, `--password=`, `X-Api-Key:` et `mysql-password=` n'étaient pas masqués (`app.secret=` l'était, par hasard) ;
- aucune forme d'URL n'était reconnue ;
- le masqueur n'était pas idempotent : au second passage, `(password="a b")` devenait `(password=[masqué]`, car la valeur nue absorbait la `)` qui suivait le marqueur. Ce défaut a été trouvé par les nouveaux tests et corrigé.

## Appelants

| Texte | Masqué | Appel |
|---|---|---|
| id, timestamp, environment, exception_type, message, schema_version, level, category | Oui | `debug_errors._event` |
| hint, route, controller, template, sql, correlation_id | Oui | `_optional` |
| request.method, path, query | Oui | `_optional` |
| Noms de post_keys et headers | Oui | `_event` |
| Frames et `location` (fichier, fonction) | **Non**, contrat FD-DEBUG-001, conservé | — |
| Issues | Sans JSON brut | — |
| stdout et stderr de `forge doctor` | Oui | `runtime_diagnostics._displayed` |

Les consommateurs en aval lisent tous le modèle déjà masqué : recherche (`filter_debug_events`), détail et `debug_event_url`, scène du flux, section Diagnostics de Project Inspector. Ils sont protégés sans aucun changement de code.

## Familles sensibles ajoutées

1. Clés dont le dernier composant est sensible.
2. Composés : `secret_key`, `private_key`, et `api_key` avec `_`, `-` ou `.`.
3. `authorization` précédé d'un préfixe.
4. Mot de passe des URL `schéma://utilisateur:mot-de-passe@hôte`.

## Clés suffixées

Mots-clés : `password|passwd|pwd|secret|token|api[_.-]?key|secret[_.-]?key|private[_.-]?key|authorization`, en ASCII (`(?a:…)`) et sans distinction de casse.

Règle : le mot-clé doit être précédé du début du texte ou d'un caractère non alphanumérique (`(?<![^\W_])`, largeur fixe 1 : `_`, `-` et `.` sont admis), puis suivi de `["']?\s*[:=]`. Il est donc le **dernier composant** de la clé :

- `ACCESS_TOKEN` et `REFRESH_TOKEN` sont des cas de `*_TOKEN` ;
- `fooDB_PASSWORD` est masqué (dernier composant `PASSWORD`, décision B) ;
- `DB_PASSWORD_EXTRA` ne l'est pas (décision A).

## Faux positifs

Conservés à l'identique (tests) :

- `password_policy`, `token_count`, `tokenizer`, `mytoken` ;
- `secretary`, `monkey`, `api_keys_count`, `API_KEY_STATUS` ;
- `DB_PASSWORD_EXTRA`, `PRIVATE_KEY_PATH`, `PRIVATE_KEY_FILE` ;
- `Authorization_Mode`, `AuthorizationCount` ;
- `key=value`, `password policy`, `session_cookie=abc`.

## URLs avec credentials

`(?i)((?<![a-z0-9+.-])[a-z][a-z0-9+.-]*://[^\s/?#@:]*:)[^\s/?#]+(?=@)` : le schéma, l'utilisateur et `:` sont conservés, le mot de passe est remplacé.

| Cas | Résultat |
|---|---|
| `mysql://`, `postgresql://`, `redis://`, `https://` | Masqué |
| `redis://:secret@h` (utilisateur vide) | Masqué |
| IPv6 (`@[::1]:5432`), port, chemin, query | Conservés |
| Plusieurs URL sur une ligne | Toutes masquées |
| `p%40ss%3Aword`, `pa%2Fss` | Masqués, sans décodage |
| `u:p@ss@h` (`@` non encodé) | Masqué jusqu'au dernier `@` de l'autorité |
| `user@host`, `user:@host`, `host:8443` | Inchangés |
| `u:pa/ss@h` | **Hors contrat**, inchangé : `/` termine syntaxiquement l'autorité |

Le traitement est syntaxique : aucun décodage ni réparation d'URL (décision I).

## Query strings

Aucune logique dédiée : l'expression des affectations s'arrête à `&`. Les cas `?token=`, `?api_key=` (historiques), `?db_password=` et `&service_token=` sont masqués ; `&page=2` et le fragment sont conservés, et le fragment n'est pas analysé.

## Headers

- `authorization`, avec ou sans préfixe (`Authorization`, `Proxy-Authorization`, `HTTP_AUTHORIZATION`, `X.Authorization`), est masqué jusqu'à la fin de ligne (décision C). Le prototype faisait fuir `Proxy-Authorization: [masqué] secret` ; ce cas est corrigé et testé.
- `Cookie` et `Set-Cookie` gardent leur politique historique (`(?<![\w-])`).
- Ni Base64 décodé, ni JWT analysé.

## Valeurs citées

Le comportement historique est conservé :

- `"…"` et `'…'` sont remplacés en entier, guillemets compris ;
- une citation inachevée est masquée jusqu'à la fin de ligne ;
- le marqueur `[masqué]` est inchangé.

## Idempotence

Le marqueur est désormais une valeur atomique reconnue en premier. Les trois passes (en-têtes, affectations, URL) ne font que remplacer ; aucune ne peut réexposer ce qu'une autre a masqué.

Couverture par tests :

- chaque cas du corpus est soumis à `redact(redact(x)) == redact(x)` ;
- plus de 10 000 combinaisons déterministes (préfixes, séparateurs, clés, casse, affectations, valeurs, ponctuation), sans Hypothesis.

Un texte qui contient littéralement `password=[masqué]suite` conserve `suite` ; un tel texte n'apparaît pas spontanément, ce cas est accepté.

## Unicode et lignes

- LF, CRLF et CR sont conservés, et aucune ligne n'est fusionnée.
- Les valeurs Unicode sont masquées et le texte n'est pas normalisé.
- Les clés sont ASCII. Sans `(?a:…)`, `re` en mode insensible à la casse ferait correspondre `ı`, `İ`, `ſ` ou le signe kelvin à des lettres ASCII ; cette restriction rend aussi le préfiltre exact.
- La politique des caractères de contrôle est inchangée : un NUL ne termine pas une valeur nue.
- La sortie grandit d'au plus `len("[masqué]") - 1` caractères par valeur remplacée, donc proportionnellement au nombre de secrets (décision E).

## Complexité / ReDoS

- Lookbehinds de largeur fixe, aucun motif imbriqué non borné, aucune expression construite depuis l'entrée.
- Le schéma d'URL ne démarre qu'en début de mot. Sans ce lookbehind, une longue suite de lettres suivie de `://` devient **quadratique** : la mutation correspondante est tuée par un garde dédié.
- Chaque passe n'est tentée que si son indice figure dans le texte : `authorization` ou `cookie` ; un fragment de mot-clé dans `value.lower()` ; `://`.
- Un test compare le résultat avec et sans préfiltre sur un corpus qui inclut des homoglyphes.

## Journal runtime

Le Bridge `read_debug_errors` n'a pas changé ; il appelle le même masqueur. Le fichier JSONL n'est jamais réécrit : un test vérifie l'égalité des octets avant et après lecture. Aucune persistance du texte masqué.

## Recherche Debug Center

La recherche porte toujours sur les textes masqués. `VerySecret123`, issu de `DB_PASSWORD=VerySecret123`, n'est plus retrouvable ; les autres valeurs ne le sont pas non plus. La recherche d'un texte ordinaire (`connection`) trouve toujours l'événement.

## Détail événement

Le couple ligne + id public masqué fonctionne comme avant. Un id contenant une forme nouvellement reconnue (`evt SERVICE_TOKEN=x`) devient `evt SERVICE_TOKEN=[masqué]`, et l'URL de détail ne contient aucune valeur. Un ancien lien vers cet événement peut répondre 404, ce qui est conforme au contrat : le couple désigne une occurrence de la lecture courante (décision G). La politique des collisions d'id après masquage est inchangée.

## forge doctor

Le pipeline est inchangé : octets → UTF-8 avec remplacement → `clean_output` (ANSI et contrôles) → `redact_debug_text` → Jinja. Avec un faux doctor puis le vrai `forge doctor`, la sortie `DB_PASSWORD=… vers mysql://roger:…@db.local/app API_TOKEN=…` devient `DB_PASSWORD=[masqué] vers mysql://roger:[masqué]@db.local/app API_TOKEN=[masqué]`, et `HTTP_AUTHORIZATION=Bearer …` devient `HTTP_AUTHORIZATION=[masqué]`.

## Modèle public

Test : un événement porte des secrets dans l'id, le message, le hint (URL), le SQL, la route, la query et un header. Ni `repr(read_debug_errors(...))` ni l'URL de détail ne contiennent aucune des valeurs.

## HTML

Tests HTTP et navigateurs : aucune valeur dans le HTML de Project Inspector, de la liste, du détail, de la recherche (hors du champ, qui réaffiche la saisie de l'utilisateur), de l'URL de détail, ni dans la sortie du diagnostic.

## Limites conservées

- Secret isolé, sans nom de clé.
- Clé métier inconnue (`MY_PASSPHRASE`, `DSN`…).
- Encodage arbitraire, base64 ou valeur chiffrée sans contexte.
- Valeur répartie sur plusieurs lignes.
- Caractère réservé non encodé dans un mot de passe d'URL (`u:pa/ss@h`).
- Frames et `location`.
- Masquage défensif, ni DLP ni détecteur de secrets.

## Tests Python

- `tests/test_debug_redaction.py` (208 tests) :
  - 35 clés sensibles × 4 séparateurs ;
  - 22 textes ordinaires ;
  - valeurs citées et inachevées ;
  - idempotence entre parenthèses ;
  - Authorization préfixé, Cookie historique ;
  - query strings ;
  - 15 cas d'URL, plus le cas hors contrat ;
  - plusieurs familles sur une ligne ;
  - Unicode et lignes ;
  - croissance bornée par le marqueur ;
  - plus de 10 000 combinaisons ;
  - pureté (seul import : `re`) ;
  - garde de complexité (×4 sur l'entrée doit coûter moins de ×16, médiane de 3, 16 entrées) ;
  - garde quadratique sur une suite unique (×8 doit coûter moins de ×32) ;
  - équivalence avec et sans préfiltre ;
  - casse ASCII ;
  - modèle public, recherche et liens.
- `tests/test_runtime_diagnostics.py` : le faux doctor imprime les nouvelles formes.

Les tests historiques de Debug Center (`test_debug_errors`, `test_debug_center_stabilization`, `test_web_debug*`, `test_debug_filters`) restent verts sans modification.

## Tests Web

`tests/test_web_debug_redaction.py` (2 tests, vrai serveur HTTP) :

- **Journal** : aucune valeur dans Project Inspector, la liste, le détail, l'URL de détail et cinq recherches ; texte masqué visible ; recherche ordinaire fonctionnelle ; journal inchangé.
- **POST du diagnostic Forge** : aucune valeur ; marqueurs et texte ordinaire présents.

## Mutations

Script hors dépôt, lancé depuis le scratchpad. Pour chaque mutation : édition, `pytest -x` sur dix fichiers de tests Debug Center et runtime, restauration à l'octet, empreinte vérifiée. Résultat : **22/22 tuées**.

| Mutation | Tuée par |
|---|---|
| Suffixes sensibles ignorés (lookbehind historique) | `test_last_component_is_sensitive[db_password]` |
| `DB_PASSWORD` non masqué | idem |
| `SERVICE_TOKEN` (`*_TOKEN`) non masqué | `test_last_component_is_sensitive[api_token]` |
| Identifiants d'URL non masqués | `test_url_credentials` |
| Première URL seulement | `test_url_credentials[plusieurs URL]` |
| Query suffixée non masquée | `test_query_strings` |
| Authorization relâché (premier mot) | `test_authorization_with_prefix_masks_to_end_of_line` |
| Authorization préfixé ignoré | idem |
| Cookie élargi aux préfixes | `test_ordinary_text_is_preserved[session_cookie]` |
| Valeur citée relâchée | `test_quoted_and_unfinished_values` |
| Valeur inachevée relâchée | idem |
| Idempotence cassée (marqueur non atomique) | idem |
| Secret encore cherchable (Bridge sans masquage) | `test_public_model_search_and_links_never_expose_values` |
| `forge doctor` sans masquage | `test_forge_diagnostic_output_hides_new_forms` |
| Indice `key` oublié (préfiltre trop strict) | `test_deterministic_combinations` |
| Indice `pwd` oublié | `test_growth_is_bounded_by_the_marker_per_replacement` |
| Indice d'en-tête `authorization` oublié | `test_authorization_with_prefix_masks_to_end_of_line` |
| Casse Unicode admise (`ſ`, `ı`, signe kelvin) | `test_prefilter_never_changes_the_result` |
| `PRIVATE_KEY` retiré | `test_last_component_is_sensitive[PRIVATE_KEY]` |
| `SECRET_KEY` retiré | `test_last_component_is_sensitive[secret_key]` |
| URL : premier `@` seulement | `test_url_credentials[u:p@ss@h]` |
| URL : schéma admis au milieu d'un mot (quadratique) | `test_no_quadratic_scheme_scan_on_a_single_long_run` |

## Performance

Médianes sur 7 exécutions, pire cas entre parenthèses ; masqueur de HEAD comparé au masqueur final :

| Entrée | HEAD 64 Kio | Final 64 Kio | HEAD 256 Kio | Final 256 Kio | Croissance (×4 sur l'entrée) |
|---|---:|---:|---:|---:|---:|
| Aucun secret | 3,8 ms | 0,2 ms (0,3) | 15,4 ms | 1,0 ms (1,1) | ×4,0 |
| Clés nombreuses | 3,6 ms | 3,7 ms (4,0) | 14,5 ms | 16,3 ms (17,9) | ×4,4 |
| URL nombreuses | 6,1 ms | 2,4 ms (2,9) | 24,4 ms | 10,9 ms (15,5) | ×4,5 |
| Hostile `A_` | 3,8 ms | 0,3 ms (0,3) | 9,4 ms | 1,1 ms (1,1) | ×4,0 |
| Hostile `:` | 10,3 ms | 0,4 ms (0,4) | 42,0 ms | 1,2 ms (1,2) | ×3,0 |
| Hostile `@` | 10,5 ms | 0,2 ms (0,3) | 42,6 ms | 0,8 ms (0,9) | ×3,7 |
| Hostile `a://` | 8,6 ms | 2,5 ms (2,6) | 34,5 ms | 10,3 ms (10,9) | ×4,1 |
| Hostile `x://u:a:a:…` | 6,4 ms | 3,2 ms (3,3) | 24,7 ms | 12,6 ms (12,9) | ×4,0 |
| Hostile `password` + blancs | 10,2 ms | 7,6 ms (8,0) | 41,0 ms | 29,9 ms (30,3) | ×4,0 |
| Hostile `Proxy-Authorization` | 2,0 ms | 6,0 ms (6,3) | 8,2 ms | 24,4 ms (24,7) | ×4,1 |

La croissance est linéaire partout. Le pire cas observé est de 30 ms pour 256 Kio saturés de mots-clés.

Lecture complète d'un journal de 2 000 événements (`read_debug_errors`) :

| Journal | HEAD | Final |
|---|---:|---:|
| 7,8 Mio de messages ordinaires | 513 ms | 75 ms |
| 7,7 Mio de messages saturés de secrets | 629 ms | 870 ms |

Le second cas ne se produit pas pour un journal réel.

Sans les préfiltres, une première version coûtait 2 à 4 fois HEAD sur du texte ordinaire ; les préfiltres ont été ajoutés pour cette raison.

## Chromium

Conditions : roue 0.2.0 dans un venv neuf, vraie commande `forge-design`. Fixture réelle `redactproj` (copie de gx8 avec son `.venv` réel), qui contient :

- un journal de deux événements : clés suffixées dans l'id, le message, le SQL et la query ; URL PostgreSQL dans le hint ;
- un `config.py` qui imprime `DB_PASSWORD`, une URL MySQL, `API_TOKEN` et `HTTP_AUTHORIZATION`.

Scénario, 7/7 :

1. sélection du projet ; Project Inspector sans valeur ;
2. liste : valeurs masquées, texte ordinaire conservé (`token_count=3 password_policy=strict tokenizer ready`) ;
3. détail par clic réel : aucune valeur, ni dans la page ni dans le lien ;
4. recherche de trois valeurs : « Aucun événement ne correspond aux filtres. » ;
5. vrai `forge doctor` par clic : variable, URL et en-tête masqués, texte ordinaire conservé ;
6. aucune erreur JavaScript ;
7. journal et projet inchangés.

## Firefox

Même scénario, 7/7.

## Sans JavaScript

Firefox avec `javascript.enabled=false`, vérification par XPath sur les textes et les attributs (Firefox ne gère pas encore le localisateur `innerText` de BiDi) :

- liste, détail et diagnostic Forge (POST natif par clic réel) : aucune valeur, marqueurs attendus présents ;
- recherche d'une valeur : aucun événement.

## ToolRegistry

Cinq Tools, inchangés.

## Graphic Core

Aucune modification ; 134/134 tests Node.

## Modules externes

Circuit et Flowchart non modifiés. Le scénario Chromium complet, avec `--module forge_design_circuit --module forge_design_flowchart`, donne 7/7.

## Recommandation ticket suivant

Deux pistes :

- Masquer de façon optionnelle les chemins des frames : un chemin peut contenir un nom d'utilisateur, mais aucune valeur de secret n'a été observée dans une frame Forge. Cela demande une décision contractuelle explicite, puisque le contrat FD-DEBUG-001 laisse les frames hors masquage.
- Poursuivre la Phase 5 (FD-RUNTIME-002) avec une autre commande Forge offrant une sortie fiable, en réutilisant le runner et ce masqueur.

## Fichiers créés

- `tests/test_debug_redaction.py`
- `tests/test_web_debug_redaction.py`
- `docs/rapports/FD-DEBUG-006.md`

## Fichiers modifiés

- `forge_design/forge/debug_redaction.py`
- `tests/runtime_diagnostics_support.py`
- `tests/test_runtime_diagnostics.py`
- `docs/tools/debug-center.md`
- `docs/02-architecture.md`
- `docs/03-roadmap.md`

## Validation finale

| Commande | Résultat |
|---|---|
| `python -m compileall -q forge_design tests` | OK |
| `ruff check forge_design tests` | All checks passed |
| `ruff format --check .` | OK |
| `pyright` (strict) | 0 erreur, 0 avertissement |
| `git diff --check` | OK |
| `pytest` (suite complète) | 4 964 passed |
| `node --test tests/js/graphics/*.test.mjs` | 134/134 |
| Roue 0.2.0, venv neuf | `pip check` OK |
| Chromium, Firefox, Chromium + modules | 7/7 chacun, vrai `forge doctor` |
| Firefox sans JavaScript | OK |
| Mutations | 22/22 tuées |

## État Git final

Un seul commit : `fix: renforcer le masquage des secrets Debug Center (FD-DEBUG-006)`, au-dessus de `4bf67ab`. Il n'a pas été poussé. `docs/rapports/FD-CONTRACT-001.md` reste modifié localement, hors commit. La version reste 0.2.0.
