# FD-INSPECT-001 — Mode analyse : note de conception de la preuve de concept

Date : 29 octobre 2026. Statut : **proposition**, à valider par le porteur.

## 1. L'idée

On ouvre une application Forge dans Forge Design et on y navigue comme un
utilisateur. Un Alt+clic sur un élément de la page ouvre le **mode analyse** :
d'où vient cet élément ? Quelle route a servi la page, quel handler l'a
construite, quels templates l'ont produite, quelles requêtes SQL ont été
lancées ?

L'outil doit permettre à quelqu'un qui ne connaît pas le code d'un projet
(ni celui de Forge) de le comprendre en partant de ce qu'il voit à l'écran.

## 2. Changement d'approche

Jusqu'ici, Forge Design **déduisait** la structure du projet par analyse
statique. Sur SéquenCiel, cette déduction bute sur ses limites : 36 routes
dont le template est indéterminable, des routes d'opt-ins ou générées par
boucle absentes de l'inventaire, des templates rendus par des helpers qu'on
ne suit pas.

Le mode analyse **observe l'exécution réelle** : l'application elle-même
raconte ce qu'elle fait pendant qu'elle sert la page. Rien n'est deviné.
Les inventaires statiques existants servent ensuite à enrichir ce qu'on a
observé (où la route est déclarée, à quelle entité correspond une table).

## 3. Ce que voit l'utilisateur

1. Il démarre le mode analyse sur un projet. La page d'accueil de
   l'application s'affiche dans Forge Design.
2. Il navigue normalement : liens, menus, formulaires.
3. Alt+clic sur un élément, par exemple une ligne de tableau. L'élément est
   entouré et un panneau s'ouvre à côté de la page.
4. Le panneau montre, pour la page courante :

| Rubrique | Contenu |
|---|---|
| Route | Méthode, motif (`/clients/{id}`), nom, publique ou protégée, paramètres reçus |
| Handler | `ClientController.show`, fichier et ligne, lien vers le source |
| Templates | Arbre réellement rendu (layout, page, inclusions), avec **le template qui a produit l'élément cliqué** mis en évidence |
| Requêtes SQL | Texte, paramètres masqués, durée, nombre de lignes, table, entité correspondante si connue |
| Réponse | Statut, durée totale |

La preuve de concept affiche ces rubriques en texte. Les vues graphiques
(chaîne route → handler → templates → entités) viennent à l'étape 4, en
réutilisant les scènes existantes.

## 4. Fonctionnement

```text
 Forge Design (127.0.0.1:8765)
 ┌─────────────────────────────────────────────┐
 │  page « Mode analyse »                      │
 │  ┌───────────────────────┐  ┌────────────┐  │
 │  │ iframe : l'application│  │  panneau   │  │
 │  │  + inspect.js         │─▶│  d'analyse │  │
 │  └──────────┬────────────┘  └─────▲──────┘  │
 └─────────────┼─────────────────────┼─────────┘
    postMessage│(trace, template)    │ trace lue côté serveur
               ▼                     │
        proxy Real Preview ──────────┤
               │                     │
               ▼                     │
        processus enfant : app Forge + sondes ──┘
```

### 4.1 Sondes dans le processus enfant

La Real Preview lance déjà l'application dans un processus enfant
(`forge_design/real_preview/child_bootstrap.py`), qui importe `app` puis sert
`create_wsgi_app(application)`. Les sondes sont posées **dans ce processus,
juste après l'import de l'application et avant le premier service**. Aucun
fichier de Forge ni du projet n'est modifié.

| Sonde | Point de Forge 1.0.0rc9 enveloppé | Information recueillie |
|---|---|---|
| Route | `Router.match` (`core/http/router.py:218`) | Route trouvée, paramètres |
| Handler | `route.handler`, localisé par `inspect` | Contrôleur, méthode, fichier, ligne |
| Templates | Chargeur Jinja du `Jinja2Renderer` (`integrations/jinja2/renderer.py`) | Chaque template chargé, y compris `extends` et `include` |
| SQL | `core.database.db._run_query` | Requête, durée, nombre de lignes |

Chaque requête HTTP reçoit un identifiant de trace, porté par une
`contextvars.ContextVar` (le serveur sert un thread par requête). L'enfant
garde les 200 dernières traces en mémoire et répond un en-tête
`X-Forge-Design-Trace: <id>`.

### 4.2 Retrouver le template d'un élément

Le chargeur enveloppé insère des marqueurs invisibles dans le source de
chaque template, au début et à la fin du template et de chacun de ses
`{% block %}` :

```html
<!--fd:t:12-->  …contenu du template n° 12…  <!--/fd:t:12-->
```

Au clic, le script cherche le couple de marqueurs le plus proche qui
entoure l'élément. Son numéro désigne le template dans la trace de la page.

Précision visée pour la preuve de concept : **le template et le bloc**, pas
la ligne exacte. La ligne viendra plus tard, en allant plus loin dans le
moteur Jinja.

### 4.3 Script d'inspection et panneau

En mode analyse, le proxy ajoute une balise
`<script src="/__forge_design/inspect.js" defer>` avant `</body>` dans les
réponses HTML, et sert ce script lui-même. La CSP de Forge
(`script-src 'self'`) l'accepte, parce que le proxy et la page ont la même
origine. Le proxy refuse tout autre chemin `/__forge_design/`.

Le script gère l'Alt+clic et l'entourage de l'élément, puis transmet
l'identifiant de trace et le numéro de template à la page Forge Design par
`postMessage`, avec l'origine de Forge Design comme seule destinataire.
Le serveur Forge Design lit ensuite la trace directement auprès de l'enfant,
sur la boucle locale. La page de l'application n'a jamais accès aux traces.

## 5. Réutilisé, modifié, laissé de côté

**Réutilisé tel quel**

- runner de la Real Preview : lancement `-I -B -u`, nouvelle session, arrêt
  du groupe, garde loopback et garde `Host` ;
- inventaire des routes : lien vers la déclaration ;
- inventaire des entités : correspondance table → entité ;
- visualiseur de source ;
- scènes graphiques (routes, entités, flux), à l'étape 4.

**Modifié**

- `child_bootstrap.py` : pose des sondes, endpoint de trace ;
- proxy : injection du script, en mode analyse seulement. Cela lève la règle
  actuelle « les corps ne sont jamais réécrits ». C'est un choix assumé ;
- point d'entrée : le mode analyse part de `/` et laisse naviguer partout.
  Le filtre d'éligibilité de Route Explorer (1 route sur 629 éligible sur
  SéquenCiel) ne s'applique pas.

**Laissé de côté, en pause**

Éditeur, Designs, génération, écriture contrôlée, modules Circuit et Flowchart.
Rien n'est supprimé.

## 6. Obstacles connus sur SéquenCiel

Ils sont tirés des rapports FD-SEQUENCIEL-005R2 et 006.

1. **Connexion.** `GET /` redirige vers `/login`, qui répond 503 si la base
   est arrêtée. Le proxy n'accepte que GET et HEAD, donc on ne peut pas se
   connecter. Pour aller au-delà de la page de connexion, il faut **la base de
   développement démarrée et le POST autorisé** dans le proxy. Cela implique
   des écritures dans la base (au minimum la session). Décision au porteur
   (§10).
2. **Enveloppes WSGI du projet.** La preview sert `app.application` sans les
   enveloppes de `wsgi.py`, ce qui bloque certains styles en ligne.
   L'affichage est dégradé, pas faux. À traiter plus tard si cela gêne.
3. **Marqueurs hors du HTML.** Un template inclus dans un attribut, un
   `<script>`, un `<title>` ou un `<textarea>` afficherait ou casserait le
   marqueur. La preuve de concept le mesure : chaque page est rendue avec et
   sans marqueurs, puis on compare le texte visible. Les templates en cause
   sont alors exclus du marquage.
4. **Dépendance aux détails internes de Forge.** `_run_query` est privée.
   Les sondes sont liées à forge-mvc 1.0.0rc9, version que le bootstrap
   vérifie déjà. À terme, on proposera dans Forge de vrais points
   d'accroche, quand le code de Forge sera mieux connu, justement grâce à cet
   outil.

## 7. Hors périmètre de la preuve de concept

- navigation automatique (robot qui parcourt les pages) ;
- ligne exacte dans le template ;
- requêtes AJAX et réponses JSON (seules les pages HTML sont analysées) ;
- autres frameworks que Forge ;
- toute écriture dans le projet.

## 8. Critère de réussite

Sur 5 pages de SéquenCiel choisies par le porteur, 10 Alt+clics par page :

- route et handler justes à chaque fois ;
- bon template indiqué dans au moins 8 cas sur 10 ;
- aucune différence de texte visible entre la page avec et sans marqueurs ;
- et surtout : **le porteur apprend sur SéquenCiel quelque chose qu'il ne
  savait pas**.

## 9. Étapes

| Étape | Livré | Vérifié par |
|---|---|---|
| 1. Sondes et trace | L'enfant sert l'app et produit une trace JSON par requête (route, handler, templates, SQL) | Tests unitaires sur un projet Forge minimal |
| 2. Marqueurs et Alt+clic | Script d'inspection, panneau texte dans Forge Design | Test navigateur sur le projet minimal |
| 3. SéquenCiel | Connexion (selon §10), essai sur 5 pages | Critère du §8 |
| 4. Graphique | Chaîne route → handler → templates → entités en scène graphique | Essai réel |

Méthode allégée tant que l'idée n'a pas fait ses preuves : tests ciblés,
essai réel, un compte rendu de quelques lignes par étape. Pas de rapport de
qualification, pas de version publiée avant la fin de l'étape 3.

## 10. Décisions du porteur (29 octobre 2026)

1. **Base de données pour l'étape 3** : une **copie jetable** de la base de
   développement. La base réelle n'est jamais touchée.
2. **Formulaires** : les POST sont **autorisés** en mode analyse, vers cette
   copie seulement.
3. **Panneau** : **à côté** de la page.

## 11. Avancement

**Étape 1 faite** (sondes et trace) :

- `forge_design/real_preview/child_inspect.py` : sondes de route, handler,
  templates (avec marqueurs) et SQL, une trace par requête, servie par
  `GET /__forge_design/trace/<id>` ; bibliothèque standard seulement ;
- `child_bootstrap.py` accepte `--inspect` et charge ce module par son
  chemin ; sans l'option, rien ne change ;
- `tests/test_real_preview_inspect.py` : fonctions de marquage, sondes sur de
  faux objets Forge, bout en bout réel sur le squelette rc9 (route `/`,
  `HomeController.index`, templates et marqueurs justes, `<title>` intact) ;
- essai à blanc sur SéquenCiel, sans exécuter l'application : les 563
  templates HTML compilent avec les marqueurs, sans un seul repli, une fois
  déclarés ses filtres `enrichi` et `nu`.

**Étape 2 faite** (marqueurs et Alt+clic) :

- page **Analyse** (`/inspect`, groupe Explorer de la barre latérale) :
  « Lancer l'analyse » démarre le runtime de la preview avec `--inspect`
  (un runner ordinaire du même projet est arrêté puis relancé), l'application
  s'affiche à gauche à partir de `/`, le panneau à droite ;
- proxy : en mode analyse, balise `<script src="/__forge_design/inspect.js">`
  avant `</body>` des réponses HTML (avec l'identifiant de trace et l'origine
  de Forge Design), script servi par le proxy, tout autre chemin
  `/__forge_design/` refusé en 404 et jamais relayé ;
- `inspect.js` (dans la page de l'application) : Alt+clic, ou bouton
  « Choisir un élément » qui arme un seul clic, cadre autour de l'élément,
  chaîne des marqueurs envoyée à Forge Design par `postMessage` ;
- `inspect-panel.js` (dans Forge Design) : n'accepte que les messages de
  l'iframe du proxy, lit la trace par `GET /inspect/trace?id=…` (le serveur
  la demande à l'enfant), affiche en texte l'élément choisi et son gabarit,
  la page, la route, le handler (lien vers le source) et les gabarits rendus
  (liens vers le visualiseur), avec les requêtes SQL ;
- vérifié dans Chromium sur le squelette : panneau rempli au chargement,
  Alt+clic sur le titre attribué à `home/index.html`, bloc `content`, clic
  armé sur le pied de page attribué à `layouts/base.html`, navigation suivie,
  aucune violation de CSP venant du mode analyse.

Constat : une balise ouverte dans un gabarit et fermée par un bloc enfant
appartient au gabarit qui l'ouvre (le `<footer>` du layout reste au layout,
même quand son contenu vient d'un bloc). C'est le comportement attendu.
