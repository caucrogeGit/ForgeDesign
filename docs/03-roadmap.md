# Forge Design — Roadmap V2

## 0. Principe

Le nouveau dépôt repart d'une feuille blanche **architecturale**, sans effacer l'expérience acquise dans `Forge-Design-old`.

L'ancien dépôt est une référence historique.
Son architecture et son code ne sont pas repris automatiquement.

Ordre directeur :

```text
documenter
→ paquet minimal
→ Bridge réel
→ Project Inspector réel
→ extraire le contrat Tool
→ UI
→ élargir
```

Cette roadmap privilégie une tranche verticale réelle avant les abstractions générales.

## Phase 0 — Fondation documentaire

### FD-FOUNDATION-001 — Documents fondateurs

Responsabilité : poser philosophie, cadrage, architecture, roadmap et politique de compatibilité.

Aucun code fonctionnel.

Validation :

```bash
git diff --check
```

### Décision de gouvernance à garder ouverte

La licence de Forge Design doit être décidée explicitement avant la première diffusion versionnée.

Aucun `LICENSE` n'est copié automatiquement depuis Forge.

## Phase 1 — Paquet minimal

### FD-FOUNDATION-002 — Paquet Python minimal

Créer :

- `pyproject.toml` ;
- package `forge_design` ;
- version Forge Design indépendante ;
- test d'import ;
- `.gitignore`.

Forge Design ne reprend pas le numéro de version de Forge.

Validation visée :

```bash
pytest
python -m compileall -q forge_design
ruff check forge_design tests
pyright
git diff --check
```

### FD-FOUNDATION-003 — CLI minimale

Fournir :

```text
forge-design --version
```

Pas encore de commande métier.

## Phase 2 — Première tranche verticale en lecture seule

### FD-FORGE-001 — Racine projet sûre

Responsabilité :

- accepter un chemin ;
- le canoniser ;
- vérifier qu'il est un dossier ;
- établir la racine de sécurité ;
- gérer les symlinks conformément à l'architecture.

Pas encore de détection Forge complète.

### FD-FORGE-002 — Détecter un projet Forge réel

Détecter un projet selon les conventions réellement produites par Forge supporté.

Ne pas exécuter l'application cible.

Le ticket comprend un test d'intégration contre un projet généré par Forge.

### FD-FORGE-003 — Lire la version Forge

Utiliser une ou plusieurs sources fiables et indiquer la source retenue.

Ne pas inventer une version si elle n'est pas déterminable.

### FD-INSPECTOR-001 — Project Inspector minimal

Project Inspector produit un résultat structuré :

```text
racine
validité
version détectée
source de version
erreurs
avertissements
```

Pas encore de registre générique.

### FD-INSPECTOR-002 — Résumé structurel

Ajouter uniquement les informations de structure réellement utiles.

Toujours en lecture seule.

## Phase 3 — Extraire Platform et contrat Tool

À ce stade seulement, observer les besoins réels de Project Inspector.

### FD-PLATFORM-001 — Contrat Tool minimal

Extraire :

- identifiant ;
- nom ;
- responsabilité ;
- entrée nécessaire ;
- résultat ou état minimal si nécessaire.

Pas d'API de plugins externes.

### FD-PLATFORM-002 — Registre explicite

Enregistrer et retrouver les Tools intégrés.

Pas de chargement dynamique arbitraire.

### FD-PLATFORM-003 — Point de composition

Centraliser l'assemblage explicite :

```text
configuration
+ services
+ Tool
```

Interdire service locator et singleton global comme mécanisme principal.

## Phase 4 — Interface Web locale

L'interface Web est une décision architecturale, pas une option à réévaluer.

### FD-WEB-001 — Serveur Web local minimal

Créer le serveur local Forge Design.

Contraintes :

```text
127.0.0.1 par défaut
pas de 0.0.0.0 par défaut
pas d'accès direct navigateur → filesystem
pas d'exposition distante implicite
```

Le ticket ne construit pas encore une interface graphique riche.

### FD-UI-001 — Shell Web minimal

Créer l'interface nécessaire pour :

- choisir un projet ;
- afficher son état ;
- accéder à Project Inspector.

Stack initiale sobre :

```text
HTML
Jinja
Tailwind
HTMX
Alpine.js seulement si nécessaire
```

### FD-UI-002 — Project Inspector graphique

Présenter les données du Tool sans dupliquer sa logique dans l'UI.

### FD-UI-003 — Ouverture navigateur

Étudier et implémenter séparément le confort de lancement :

```text
forge-design
→ serveur local
→ URL affichée
→ navigateur ouvert si configuré
```

Le comportement exact et une éventuelle option `--no-browser` sont testés dans ce ticket.

## Phase 5 — Diagnostics Forge

Après vérification des commandes réellement présentes dans les versions Forge supportées :

- runner sécurisé ;
- commandes de diagnostic autorisées ;
- routes si exposées de façon fiable ;
- migrations si exposées de façon fiable ;
- erreurs structurées.

Chaque capacité reste un ticket séparé.

## Phase 6 — Exploration

Introduire progressivement :

- Route Explorer ;
- Template Viewer ;
- Entity Viewer ;
- Debug Center.

Lecture seule en priorité.

## Phase 7 — Contrat de stockage projet

Avant toute ressource persistante Forge Design :

- décider la structure de `.forge-design/` ;
- versionner le format ;
- définir ce qui est partageable par Git ;
- définir ce qui reste dans le stockage utilisateur local ;
- documenter les migrations de format.

Ce ticket ne construit ni Circuit ni 3D.

## Phase 8 — Conception de vues

Après stabilisation du socle :

- contrats de vue ;
- `.design.json` ;
- bindings ;
- preview statique ;
- génération Jinja/Tailwind ;
- diff ;
- anti-écrasement ;
- éditeur structurel ;
- HTMX/Alpine contrôlés ;
- preview réelle : contrat de sécurité (FD-REALPREVIEW-001) → runner → intégration Web.

`Forge-Design-old` peut servir de référence technique, jamais de source à recopier massivement.

## Phase 9 — Contrat d'outil spécialisé

Avant Circuit, Network ou 3D, définir le minimum réellement nécessaire :

- identité ;
- capacités ;
- ressource ;
- validation ;
- erreurs ;
- sauvegarde contrôlée ;
- dépendances optionnelles ;
- intégration UI.

Valider le modèle avec un Tool simple si nécessaire.

Démarche retenue : cas réel DrawCiel → contrat minimal (FD-SPECIALIZED-001,
[contrat](specialized-tools/specialized-tool-contract.md)) → validation par un outil
spécialisé volontairement simple (FD-SPECIALIZED-002 : socle exécutable
`forge_design.specialized`, éprouvé par un outil témoin limité aux tests) →
registre et intégration seulement ensuite, si un besoin réel les justifie.

## Phase 10 — Circuit

Périmètre normatif : [Circuit — besoins et périmètre](circuit/circuit-scope.md)
(FD-CIRCUIT-001). Circuit V1 est un éditeur de schémas électriques exacts ;
la simulation est une capacité optionnelle future, hors du premier jalon.

Sous-phase Graphics (FD-GRAPHICS-001) : avant de figer le format Circuit, le
[noyau graphique commun](graphics/graphics-core-contract.md) répartit les
responsabilités entre Graphics (géométrie, nœuds, ports, arêtes, routes,
routage, sélection, commandes, historique) et Circuit (sémantique électrique).
Il capitalise sur DrawCiel, suivi par une [procédure de référence](graphics/drawciel-reference.md)
appliquée à chaque ticket concerné. Les phases globales ne sont pas renumérotées.

Ordre retenu (numéros indicatifs, révisé par FD-GRAPHICS-001) :

```text
FD-CIRCUIT-001   besoins et périmètre
→ FD-GRAPHICS-001  contrat du noyau graphique commun, capitalisation DrawCiel
→ FD-CIRCUIT-002   contrat de ressource Circuit (adopte les conventions de champs Graphics)
→ FD-GRAPHICS-002  primitives géométriques pures, transformations exactes, ports
→ FD-GRAPHICS-003  routage orthogonal extrait de DrawCiel, témoins portés
→ FD-CIRCUIT-003   domaine, catalogue V1 (conversion contrôlée), codec, validation, topologie
→ FD-GRAPHICS-004  étude du renderer et de l'interaction (choix)
→ FD-GRAPHICS-005  scène, projection, sélection, commandes, historique (domaine témoin non électrique)
→ FD-CIRCUIT-004   projection Circuit → scène, commandes Circuit
→ FD-CIRCUIT-005   intégration hôte, session, éditeur Web minimal
→ FD-CIRCUIT-006   export SVG depuis le modèle
→ FD-CIRCUIT-007   qualification du premier jalon en navigateur
→ FD-CIRCUIT-008   étude des moteurs et de l'IR Circuit (compatibilité SimulationIR DrawCiel)
→ FD-CIRCUIT-009   adaptateur et simulation DC minimale
→ FD-CIRCUIT-010   mesures
→ ultérieur        instruments, transitoires, extension du catalogue, import DrawCiel
```

Par rapport à l'ordre indicatif initial, la validation structurelle est
avancée avec le modèle, géométrie et routage deviennent des tickets Graphics
communs, le choix du rendu est une étude explicite et la généricité du noyau
est prouvée par un domaine témoin avant Circuit. Le moteur de simulation n'est
pas choisi avant une étude dédiée.

Premier jalon de la phase : créer, éditer, valider, enregistrer avec
révision, rouvrir à l'identique et exporter en SVG un schéma exact, sans
simulation.

## Phase 11 — 3D

Ordre indicatif :

```text
besoins exacts
→ étude des moteurs
→ modèle de ressource
→ visualisation
→ transformations
→ assemblage
→ sauvegarde
→ export
```

Ne pas supposer qu'un modeleur 3D complet est nécessaire.

## Phase 12 — Intégration applicative

Définir comment une application Forge telle que SéquenCiel référence une ressource Forge Design sans dépendre des détails internes de l'outil graphique.

## Règles de tickets

Chaque ticket respecte :

- une responsabilité ;
- périmètre court ;
- tests adaptés ;
- documentation minimale ;
- pas de refactoring opportuniste ;
- pas d'écrasement utilisateur ;
- rapport final.

## Premier jalon mesurable

Le premier jalon est atteint lorsque :

```text
forge-design démarre
→ lance son serveur Web local sur loopback
→ reçoit un chemin projet
→ sécurise la racine
→ reconnaît un projet réellement généré par Forge supporté
→ lit sa version de manière traçable
→ Project Inspector produit un diagnostic en lecture seule
→ ce diagnostic est affichable dans le navigateur
→ les tests de compatibilité passent
```

Aucun Template Designer, Circuit, Network ou 3D n'est nécessaire pour atteindre ce jalon.
