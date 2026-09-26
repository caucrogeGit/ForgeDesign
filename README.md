# Forge Design

**Forge Design** est le cockpit graphique et la plateforme d'outils visuels spécialisés de l'écosystème **Forge**.

```text
Forge peut vivre sans Forge Design.
Forge Design ne peut pas vivre sans Forge.
```

Forge reste le framework applicatif Python.
Forge Design est une application compagnon séparée qui se connecte à un projet Forge existant pour l'inspecter, le diagnostiquer, le représenter, le concevoir et, lorsque cela est explicitement autorisé, modifier certains fichiers de manière contrôlée.

## Conventions de nommage

| Élément | Nom |
|---|---|
| Produit | `Forge Design` |
| Dépôt GitHub | `ForgeDesign` |
| Distribution Python visée | `forge-design` |
| Package Python | `forge_design` |
| CLI visée | `forge-design` |
| Identifiant d'un Tool | slug stable, par ex. `project-inspector` |

Ces conventions évitent de mélanger le nom humain, le dépôt, l'import Python et la commande CLI.

## Installation et version

Avec Python 3.12 ou supérieur, depuis la racine du dépôt :

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
forge-design --version
```

La commande affiche `Forge Design` suivi de la version courante du package.
Pour démarrer l'application Web locale :

```bash
forge-design
```

Le navigateur par défaut ouvre `http://127.0.0.1:8765/` après ouverture du socket.
Forge Design écoute uniquement sur cette adresse locale.
La commande reste active jusqu'à `Ctrl+C`, qui ferme le serveur proprement.
Pour démarrer sans ouvrir le navigateur :

```bash
forge-design --no-browser
```

Si le navigateur est indisponible, le serveur reste actif et l'URL affichée permet
une ouverture manuelle. Si le port est occupé, la commande
signale l'erreur et retourne un code non nul, sans changer de port.
`--version` et `--help` restent disponibles.

## Vision

```text
Forge Design
├── inspection et diagnostic
├── outils de conception Forge
├── prévisualisation
└── outils visuels spécialisés
    ├── Circuit
    ├── Network
    ├── 3D
    └── futurs Tools
```

Le premier cas d'usage réel sera **Project Inspector**.

`Circuit`, `Network` et `3D` sont des perspectives architecturales.
Ils ne font pas partie du premier socle.

## Architecture directrice

Forge Design est une **application locale à interface Web**.

```text
Navigateur Web
    │
    │ http://127.0.0.1:<port>
    ▼
Forge Design UI
    │
    ▼
Backend Python / point de composition
├── Platform
├── Tools
└── Forge Bridge
        │
        ▼
    Projet Forge
```

Le navigateur n'accède jamais directement au système de fichiers du projet Forge.

Seul le backend Python de Forge Design peut lire ou modifier un projet, en passant par les contrôles de sécurité et les services prévus.

Par défaut, le serveur Forge Design écoute uniquement sur l'interface loopback (`127.0.0.1` / `localhost`).

Les Tools ne vont pas chercher des dépendances globales.
L'application leur fournit explicitement les services dont ils ont besoin.

## Priorité initiale

Le premier jalon n'est pas un designer graphique.

Il doit démontrer une tranche verticale minimale :

```text
Forge Design démarre
→ ouvre un vrai projet Forge
→ le Bridge le reconnaît
→ Project Inspector produit un diagnostic en lecture seule
→ les tests vérifient la compatibilité avec Forge
```

L'abstraction générale `Tool` et son registre sont extraits **après** cette première tranche réelle, afin d'éviter de concevoir une API théorique trop tôt.

## Documents fondateurs

- `docs/00-philosophie.md`
- `docs/01-cadrage-fonctionnel.md`
- `docs/02-architecture.md`
- `docs/03-roadmap.md`
- `docs/04-compatibilite-forge.md`
