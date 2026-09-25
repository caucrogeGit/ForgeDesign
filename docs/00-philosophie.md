# Philosophie de Forge Design

## 1. Intention générale

Forge Design est le **cockpit graphique et la plateforme d'outils visuels spécialisés de l'écosystème Forge**.

Forge Design n'est ni le moteur de Forge, ni un framework concurrent, ni un éditeur HTML générique, ni une application métier.

```text
Forge peut vivre sans Forge Design.
Forge Design ne peut pas vivre sans Forge.
```

Relation fondamentale :

```text
Forge Design ─────► Projet Forge
Forge Core   ─────► aucune dépendance vers Forge Design
```

Cette dépendance asymétrique protège Forge contre l'alourdissement tout en permettant à Forge Design de devenir riche, graphique et extensible.

## 2. Appartenance à la famille Forge

Forge Design est un dépôt et une application séparés, mais appartient à la famille Forge.

Il reprend lorsque pertinent :

- documentation structurée ;
- tests séparés ;
- configuration explicite ;
- validations reproductibles ;
- sobriété des dépendances ;
- lisibilité des sources ;
- préservation des fichiers utilisateur ;
- sécurité par défaut ;
- refus de la magie cachée ;
- une responsabilité par ticket.

```text
Même famille, mêmes principes.
Chaque projet garde une architecture adaptée à son rôle.
```

Forge Design ne copie pas mécaniquement l'arborescence interne de Forge Core.

## 3. Une plateforme, pas un outil unique

Forge Design ne doit pas être conçu autour du seul Template Designer.

```text
Forge Design
├── Project Inspector
├── Debug Center
├── Route Explorer
├── Template Designer
├── CRUD Designer
├── Entity Designer
└── outils spécialisés
    ├── Circuit
    ├── Network
    ├── 3D
    └── futurs Tools
```

Chaque Tool possède une responsabilité identifiable.

Le cœur de Forge Design orchestre les capacités communes.
Il n'absorbe pas la logique spécialisée de chaque Tool.

## 4. Refuser l'abstraction prématurée

Forge Design doit être extensible, mais ne doit pas commencer par construire un framework de plugins général.

La règle est :

```text
cas réel
→ contrat minimal
→ deuxième cas réel
→ généralisation seulement si elle est justifiée
```

Project Inspector sert de premier cas réel.

Le contrat générique d'un Tool doit être extrait à partir des besoins observés, puis stabilisé avant l'arrivée des Tools lourds comme Circuit, Network ou 3D.

## 5. Outils spécialisés

### Circuit

Perspective :

- schémas électriques ;
- composants ;
- connexions ;
- simulation ;
- mesures ;
- instrumentation pédagogique.

Le moteur de simulation reste spécialisé et n'entre jamais dans Forge Core.

### 3D

Perspective :

- conception ou composition d'objets ;
- assemblage ;
- visualisation ;
- manipulation ;
- export lorsque pertinent.

Le moteur 3D reste spécialisé et ne devient pas le cœur métier de Forge Design.

Règle générale :

```text
Forge Design fournit le cadre.
Le Tool fournit le domaine.
Un adaptateur isole le moteur spécialisé.
Forge Core reste indépendant.
```

## 6. Isolation des dépendances

L'installation minimale de Forge Design ne doit pas imposer les dépendances lourdes de tous les Tools.

À terme :

```text
Forge Design minimal
≠
Forge Design + moteur électrique + moteur 3D + toutes les dépendances spécialisées
```

Un Tool spécialisé porte ses dépendances propres ou un extra explicitement choisi.

La stratégie de packaging exacte sera décidée lorsqu'un premier Tool spécialisé existera.

## 7. Applications consommatrices

Une application Forge peut utiliser une ressource ou une capacité issue de Forge Design.

```text
SéquenCiel
    ↓
Forge
    ↓
ressource Forge Design
    ├── circuit
    └── modèle 3D
```

La logique générique d'un simulateur ou d'un outil 3D ne doit pas être enfermée dans une seule application métier lorsqu'elle peut être réutilisée.

Forge Design ne devient toutefois pas la logique métier de SéquenCiel.

## 8. Sources et réversibilité

Forge Design ne confisque pas les sources Forge.

Python, JSON, SQL, Jinja/HTML/Tailwind, Markdown et les autres formats définis par Forge restent les sources applicatives réelles.

Les ressources Forge Design doivent être :

- explicites ;
- versionnées ;
- validables ;
- sans secrets ;
- réversibles ;
- compatibles avec Git lorsque cela est raisonnable.

Toute écriture importante suit :

```text
lecture
→ validation
→ génération en mémoire
→ diff
→ validation explicite
→ écriture
→ journalisation
```

Le travail humain n'est jamais écrasé silencieusement.

## 9. Interface Web locale

Forge Design est une **application locale à interface Web**.

L'interface utilisateur s'exécute dans un navigateur et communique avec un backend Python local.

Architecture de principe :

```text
Navigateur
    ↓
UI Forge Design
    ↓
Backend Python
    ↓
Platform / Tools / Forge Bridge
    ↓
Projet Forge
```

Le navigateur ne doit jamais disposer d'un accès direct au système de fichiers du projet.

L'accès aux fichiers, commandes et ressources Forge passe toujours par le backend Python et ses contrôles.

Par défaut, Forge Design écoute uniquement sur l'interface loopback.

Une exposition sur le réseau local ou au-delà est hors comportement par défaut et nécessitera une décision explicite de sécurité.

## 10. Graphique sans boîte noire

Le graphique rend la mécanique visible ; il ne la cache pas.

Pour les interfaces Forge, l'édition reste structurelle plutôt que pixel-perfect.

Un utilisateur doit pouvoir revenir, lorsque pertinent, de la représentation graphique au contrat, à la ressource ou au fichier réel.

## 11. Sécurité

Forge Design est local-first.

Il doit notamment :

- masquer les secrets ;
- limiter les commandes exécutables ;
- éviter le shell libre ;
- contrôler les chemins ;
- empêcher les sorties hors de la racine autorisée ;
- contrôler les écritures ;
- distinguer développement, test et production.

La sécurité des chemins et des fichiers fait partie du design initial, pas d'une phase ajoutée après coup.

## 12. Compatibilité explicite avec Forge

Forge Design ne déduit pas Forge à partir de souvenirs ou d'une ancienne arborescence.

Les conventions Forge sont vérifiées contre Forge réel.

Les versions supportées sont testées et documentées.

`main` de Forge sert de référence de développement, mais les versions supportées par une release Forge Design doivent être explicitement testées et enregistrées.

## 13. Gouvernance des décisions

Les documents ont des responsabilités différentes :

```text
00-philosophie.md
→ principes non négociables

01-cadrage-fonctionnel.md
→ ce que Forge Design fait et ne fait pas

02-architecture.md
→ frontières, dépendances, stockage, sécurité structurelle

03-roadmap.md
→ ordre de construction

04-compatibilite-forge.md
→ contrat de compatibilité avec Forge
```

Une décision structurante durable pourra ensuite être figée dans un ADR dédié.

## 14. Licence

La licence de Forge Design doit faire l'objet d'une décision explicite avant sa première diffusion versionnée.

Aucun fichier `LICENSE` ne doit être inventé ou copié mécaniquement depuis Forge sans cette décision.

## 15. Synthèse

```text
Forge est le moteur.
Forge CLI est l'interface de commande.
Forge Design est le cockpit et la plateforme visuelle.
Les Tools apportent des capacités spécialisées.
Le code et les ressources restent lisibles.
Le graphique aide à comprendre, concevoir, diagnostiquer et simuler.
Il ne doit jamais enfermer le développeur.
```
