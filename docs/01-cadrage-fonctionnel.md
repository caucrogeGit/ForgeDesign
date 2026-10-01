# Forge Design — Cadrage fonctionnel V2

## 1. Définition

Forge Design est une application graphique séparée connectée à un projet Forge existant.

Elle fournit un **socle commun d'inspection, de diagnostic, de conception et d'outils visuels spécialisés**.

Forge Design ne remplace pas Forge et ne devient pas une application métier.

## 2. Premier jalon fonctionnel

Le premier jalon doit permettre :

- d'installer le package minimal ;
- de lancer la CLI Forge Design ;
- de désigner un dossier projet Forge ;
- de vérifier qu'il est reconnu sans exécuter l'application cible ;
- de lire une version Forge lorsque la source est fiable ;
- de produire un diagnostic Project Inspector en lecture seule ;
- de tester ce comportement contre un vrai projet Forge.

Le premier jalon ne doit pas :

- modifier le projet cible ;
- lancer un serveur Forge ;
- générer un CRUD ;
- modifier des entités ;
- modifier des migrations ;
- construire Circuit ;
- construire 3D ;
- introduire un canvas complexe ;
- construire un système de plugins dynamique général.

## 3. Project Inspector avant l'abstraction Tool

Project Inspector est le premier cas d'usage réel.

La première tranche peut exister avec des services simples et explicites.

Ensuite seulement, ce que Project Inspector révèle comme besoins réellement communs est extrait dans un contrat minimal de Tool.

Ordre :

```text
Forge Bridge minimal
→ Project Inspector minimal
→ contrat Tool minimal
→ registre minimal
→ UI
```

Cette séquence évite de concevoir un framework de plugins théorique avant d'avoir un premier utilisateur réel du contrat.

## 4. Notion de Tool

Un **Tool** est une capacité visuelle identifiable de Forge Design.

Exemples :

```text
Project Inspector
Debug Center
Route Explorer
Template Designer
Circuit
3D
```

Un Tool possède au minimum :

- un identifiant stable ;
- un nom d'affichage ;
- une responsabilité ;
- les capacités dont il a réellement besoin.

Le contrat précis est dérivé des cas réels.

## 5. Platform

La Platform fournit uniquement les services transversaux prouvés nécessaires.

Responsabilités potentielles :

- configuration Forge Design ;
- contexte d'exécution ;
- registre des Tools ;
- sélection du projet Forge ;
- erreurs communes ;
- intégration avec l'interface ;
- cycle de vie minimal.

Elle ne contient ni logique électrique, ni géométrie 3D, ni logique métier d'une application consommatrice.

## 6. Forge Bridge

Le Forge Bridge adapte un projet Forge réel aux besoins de Forge Design.

Responsabilités progressives :

- canoniser la racine du projet ;
- détecter un projet Forge ;
- lire une version Forge ;
- inspecter une structure utile ;
- exposer des résultats structurés ;
- exécuter plus tard uniquement des commandes autorisées.

Règles :

- lecture seule par défaut ;
- pas de shell libre ;
- pas d'exécution arbitraire ;
- pas d'import dangereux de l'application cible ;
- pas de lecture générique de secrets ;
- pas de suivi de symlink hors racine ;
- pas d'écriture implicite.

## 7. Sécurité des chemins

Toute opération fichier commence par une racine projet canonique.

Principe :

```text
racine autorisée
→ résolution canonique de la cible
→ vérification que la cible reste dans la racine
→ opération
```

Au début :

- les symlinks qui sortent du projet sont ignorés ou refusés ;
- les contenus sensibles tels que `env/`, `.env*`, clés et certificats ne sont pas lus par un scanner générique ;
- un lecteur spécialisé doit déclarer précisément ce qu'il lit.

## 8. Stockage

Forge Design distingue trois catégories.

### 8.1 État local de l'application Forge Design

Exemples :

- préférences ;
- projets récents ;
- cache ;
- état d'interface ;
- diagnostics temporaires.

Cet état vit hors du projet Forge dans un emplacement utilisateur adapté au système.

### 8.2 Métadonnées partagées du projet

Forge Design réserve le namespace :

```text
.forge-design/
```

Il **n'est pas créé** pendant les phases de lecture seule.

Il contient des métadonnées partagées par Git et versionnées. Sa structure,
le versionnement des formats et les migrations sont fixés par le
[contrat de stockage](storage/storage-contract.md) (FD-STORAGE-001).

### 8.3 Fichiers Forge

Les fichiers existants de l'application restent sous contrôle du développeur.

Aucune écriture n'est autorisée tant qu'un contrat d'écriture contrôlée n'est pas implémenté.

## 9. Conception de vues

La conception de vues reste une capacité importante mais ne définit plus Forge Design.

Elle pourra comprendre :

- contrats de vue ;
- `.design.json` ;
- blocs structurels ;
- bindings ;
- Jinja ;
- HTML ;
- Tailwind ;
- HTMX ;
- Alpine.js ;
- prévisualisation ;
- diff ;
- écriture contrôlée.

Elle vient après stabilisation du socle.

## 10. Circuit — perspective

Périmètre potentiel :

- schéma ;
- composants ;
- connexions ;
- propriétés électriques ;
- simulation ;
- mesures ;
- instrumentation.

Ne sont pas décidés ici :

- moteur de simulation ;
- format définitif ;
- bibliothèque de composants ;
- niveau de fidélité physique ;
- interface finale.

## 11. 3D — perspective

Périmètre potentiel :

- primitives ;
- objets ;
- composants ;
- assemblages ;
- transformations ;
- visualisation ;
- export.

Ne sont pas décidés ici :

- moteur 3D ;
- format natif ;
- formats d'export ;
- modeleur complet ou composition ;
- contraintes mécaniques.

## 12. Intégration avec une application Forge

Une application Forge peut référencer ou présenter une ressource produite par un Tool Forge Design.

Le contrat d'intégration doit être explicite et versionné.

L'application consommatrice ne doit pas dépendre de détails internes de l'UI Forge Design.

## 13. Écriture contrôlée

Toute écriture future suit :

1. charger ;
2. valider ;
3. produire en mémoire ;
4. afficher le diff ;
5. obtenir une décision explicite ;
6. écrire ;
7. journaliser.

Aucun fichier utilisateur n'est écrasé silencieusement.

## 14. Interface Web locale

Forge Design utilise une interface Web servie par son backend Python local.

Principes :

- lancement local ;
- ouverture dans un navigateur ;
- écoute sur `127.0.0.1` / `localhost` par défaut ;
- aucun accès direct du navigateur au système de fichiers ;
- accès projet uniquement via les services backend ;
- aucune exposition réseau implicite ;
- technologies frontend progressives selon les besoins réels des Tools.

Le socle peut démarrer avec HTML, Jinja, Tailwind, HTMX et Alpine.js.

Des technologies plus spécialisées peuvent être introduites localement lorsqu'un Tool les justifie, par exemple SVG, Canvas, WebGL, Three.js ou un framework frontend ciblé.

Le choix d'une technologie graphique pour un Tool ne doit pas imposer cette technologie à toute la plateforme.

## 15. Contraintes non fonctionnelles

Forge Design doit être :

- local-first ;
- explicite ;
- modulaire ;
- testable ;
- documenté ;
- réversible ;
- sobre en dépendances ;
- compatible avec les conventions Forge réellement testées.

Forge Design évite :

- abstraction prématurée ;
- service locator global ;
- framework de plugins surdimensionné ;
- build frontend complexe sans nécessité ;
- stockage opaque ;
- logique métier cachée ;
- couplage d'un Tool à l'implémentation concrète d'un moteur externe.

## 16. Qualité

Dès que le paquet Python existe, les validations de base visées sont :

```bash
pytest
python -m compileall -q forge_design
ruff check forge_design tests
pyright
git diff --check
```

Les commandes sont introduites avec leur configuration effective.

Aucune validation n'est déclarée réussie si elle n'a pas réellement été exécutée.
