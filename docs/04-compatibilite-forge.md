# Forge Design — Compatibilité avec Forge

## 1. Objectif

Forge Design dépend des conventions réelles de Forge.

La compatibilité ne doit donc jamais reposer uniquement sur :

- une ancienne version de Forge ;
- une documentation obsolète ;
- une arborescence mémorisée ;
- une hypothèse codée en dur sans test.

## 2. Deux références différentes

### Forge `main`

`main` sert de référence de développement pour détecter les évolutions à venir.

Forge Design peut l'inspecter pendant son développement.

### Versions Forge supportées

Une release Forge Design supporte des versions Forge explicitement testées.

La compatibilité publiée est fondée sur ces versions, pas sur la simple affirmation « compatible avec main ».

## 3. Baseline initiale observée

Au démarrage du nouveau projet, la branche `main` de Forge expose notamment :

```text
Forge 1.0.0rc9
Python >= 3.12
```

Le squelette Forge actuel contient notamment :

```text
app.py
bootstrap.py
config.py
mvc/
    controllers/
    entities/
    forms/
    helpers/
    models/
    routes/
    validators/
    views/
```

Point notable :

```text
mvc/routes/
```

est une structure actuelle.

Forge Design ne doit donc pas figer l'ancienne hypothèse `mvc/routes.py`.

Cette baseline est un **constat de départ**, pas encore un contrat de support tant que les tests Forge Design correspondants n'existent pas.

## 4. Stratégie de tests

La compatibilité combine deux niveaux.

### 4.1 Fixtures unitaires

Des fixtures minimales permettent de tester rapidement :

- projet valide ;
- projet incomplet ;
- version absente ;
- structure inattendue ;
- symlink hors racine ;
- fichier sensible.

Ces fixtures testent les contrats internes.

### 4.2 Test d'intégration Forge réel

Un test dédié :

1. installe ou utilise une version Forge déterminée ;
2. exécute la création officielle d'un projet dans un répertoire temporaire ;
3. fait analyser ce projet par Forge Design ;
4. vérifie le résultat attendu.

Exemple conceptuel :

```text
forge new <tmp>/projet-test
        ↓
Forge Design detector
        ↓
Project Inspector
        ↓
assertions
```

Le test d'intégration ne doit pas modifier le dépôt Forge Design.

## 5. Matrice de compatibilité

Quand le premier test existe, Forge Design maintient une matrice explicite.

Exemple futur :

```text
Forge Design 0.x
├── Forge 1.0.0rc9 : testé
├── Forge 1.0.0     : à tester
└── Forge main      : surveillance développement
```

Ne pas annoncer une version comme supportée sans test correspondant.

## 6. Détection de version

La lecture de version doit :

- indiquer la valeur ;
- indiquer la source ;
- distinguer absence et erreur ;
- éviter d'importer arbitrairement l'application cible.

Si plusieurs sources existent, l'ordre de priorité est documenté et testé.

### Contrat de lecture établi par FD-FORGE-003

Source observée sur Forge `main`, commit
[`73a956e587e5f169c028415e0e540c149cbaff56`](https://github.com/caucrogeGit/Forge/tree/73a956e587e5f169c028415e0e540c149cbaff56/skeleton/data) :
le squelette déclare `forge-mvc==1.0.0rc9` dans `requirements.txt`.
Son `pyproject.toml` configure uniquement les outils, sans table `[project]`.
`forge new` peut remplacer le pin par une référence Git selon la provenance du CLI
(`cli/project/install_source.py`).
Cette référence ne déclare pas à elle seule une version de distribution.

`read_forge_version(root)` reconnaît d'abord le projet avec le détecteur du Bridge,
puis lit uniquement `requirements.txt` à la racine canonique.
C'est la seule source retenue : aucun ordre de priorité entre fichiers ni fallback.
La version de l'application, les commentaires d'`app.py`, les métadonnées de
l'environnement installé et `forge --version` ne constituent pas cette déclaration.

Le résultat immuable `ForgeVersionInfo` contient `status`, `version`, `source` et
`details`. `source` vaut `requirements.txt` lorsque ce chemin est présent ou
inaccessible, et `None` lorsque le fichier est absent.

| Statut | Signification |
|---|---|
| `found` | Déclarations `forge-mvc` exactes (`==` sans joker), inconditionnelles et cohérentes ; version normalisée PEP 440 |
| `absent` | Fichier ou déclaration absent, ou aucune version exacte déterminable (URL Git, plage, joker, condition) |
| `unreadable` | Erreur d'accès, format Forge invalide, UTF-8 invalide, source non régulière, taille excessive ou directive non prise en charge |
| `conflict` | Plusieurs pins exacts désignent des versions différentes dans le même fichier |

Seul `found` fournit une version. Les noms de distribution sont normalisés et les
préversions sont acceptées. Des pins équivalents selon PEP 440 sont cohérents ;
la première déclaration fournit la représentation normalisée retournée.
Les spécificateurs d'une même déclaration sont triés pour stabiliser ce choix.
Une erreur de lecture ou de format prime sur un conflit ; un conflit entre pins
exacts prime sur une déclaration non résolue. Une déclaration non résolue empêche
un résultat `found`, même si un autre pin exact est présent.

Le lecteur n'évalue pas les conditions, ne suit ni inclusions `-r`/`-c`, ni
installations éditables, ni continuations de ligne. Ces directives donnent
`unreadable`. Les autres dépendances et les commentaires sont ignorés.
Les diagnostics ne recopient pas les lignes du fichier.

La lecture est limitée à 1 Mio et refuse les liens symboliques et fichiers
spéciaux. Le type et l'identité sont contrôlés avant lecture sur le descripteur
ouvert ; `O_NOFOLLOW` et `O_NONBLOCK` sont utilisés lorsqu'ils sont disponibles.
La racine et ses parents doivent rester stables pendant l'appel.
Une racine invalide conserve les exceptions de `resolve_project_root` ; un
projet non reconnu déclenche `NotForgeProjectError`.

Ce contrat décrit la version **déclarée**, pas nécessairement la version installée
(notamment en mode `FORGE_DEV_SRC`). Il ne compare pas cette version à Forge Design
et ne statue pas sur son support.

## 7. Détection de projet

La détection doit utiliser un petit ensemble de signatures stables.

Elle ne doit pas exiger que tout projet Forge possède exactement tous les dossiers optionnels.

Principe :

```text
signatures nécessaires
+
indices optionnels
=
diagnostic
```

Un dossier optionnel absent produit au besoin un avertissement, pas nécessairement un refus.

### Lancement d'un projet — constats FD-REALPREVIEW-001

Vérifiés statiquement dans `forge-mvc==1.0.0rc9` pour la future preview réelle
(voir le [contrat](preview/real-preview-contract.md)), sans lancer de projet :

- `forge run` démarre un reloader par défaut ; `--no-reload` exécute
  `scripts/dev-server.sh` s'il existe, sinon `python app.py` ; aucune option
  d'hôte ni de port ;
- `python app.py --env dev` sert l'application avec `ThreadingHTTPServer`
  (threads, aucun processus enfant) ; aucun handler `SIGTERM` ;
- hôte, port et TLS viennent de `APP_HOST` (défaut `127.0.0.1`), `APP_PORT`
  (défaut `8000`) et `APP_SSL_ENABLED` (défaut vrai hors prod) ; `config.py`
  charge `env/example` puis `env/<APP_ENV>` avec écrasement des variables
  reçues ;
- port occupé : message puis sortie `1`, sans autre essai ;
- `GET /health` → `200 {"status": "ok"}`, garanti par le contrat de
  stabilité Forge sur les deux serveurs ;
- en-têtes par défaut `X-Frame-Options: DENY` et `frame-ancestors 'none'` ;
  aucun contrôle de l'en-tête `Host`.

Complément FD-REALPREVIEW-001A (même version, dépôt Forge au commit
`73a956e587e5f169c028415e0e540c149cbaff56`) :

- `config.py` lit `APP_HOST`, `APP_PORT` et `APP_SSL_ENABLED` après
  `load_dotenv(env/<APP_ENV>, override=True)` : une valeur fournie par le
  processus parent ne peut pas être garantie pour `python app.py` ;
- ces trois valeurs ne sont consommées que par le bloc `__main__` de `app.py` ;
- `import app` construit `application` sans serveur (nom public et absence
  d'effet de bord testés par Forge) ;
- chemin WSGI documenté : `create_wsgi_app(application)` (`core.app.wsgi`),
  servi par un serveur externe qui choisit son bind ; `/static/` non servi.

Mécanisme retenu pour la preview réelle : bootstrap enfant de Forge Design,
`import app` puis `create_wsgi_app(app.application)`, bind par le bootstrap sur
`127.0.0.1:<port>`. `create_wsgi_app` est documenté et testé par Forge mais
absent des imports publics du contrat de stabilité : le bootstrap vérifie la
version `forge-mvc` du projet (`1.0.0rc9`) et la présence du symbole avant
tout bind.

Confirmé à l'exécution par FD-REALPREVIEW-002, sur des projets synthétiques
copiés du squelette `forge-mvc` 1.0.0rc9 installé, jamais sur un projet
utilisateur :

- `import app` construit `application` sans serveur, et
  `create_wsgi_app(app.application)` sert `GET /health` →
  `200 application/json {"status": "ok"}` ;
- `env/dev` est bien chargé dans l'enfant (`APP_HOST=0.0.0.0`,
  `APP_SSL_ENABLED=true` y sont visibles), sans effet sur l'endpoint ;
- l'import du squelette exige aussi le dossier `optins/` (`register_optins`),
  en plus des signatures reconnues par Forge Design. Un projet sans `optins/`
  échoue à l'import (code 5), avec la trace dans les logs.

## 8. Évolution

Lorsqu'une évolution Forge casse une hypothèse Forge Design :

1. reproduire avec un projet Forge réel ;
2. ajouter ou corriger le test ;
3. adapter le Bridge ;
4. documenter la nouvelle compatibilité ;
5. ne pas modifier Forge Core uniquement pour préserver une hypothèse Forge Design.

## 9. Principe final

```text
Forge Design comprend Forge
par des contrats vérifiés,
pas par des suppositions.
```
