# Versions et compatibilité de Forge Design

Statut : **normatif** (FD-RELEASE-001). Ce document fixe la politique de
version de la distribution `forge-design` et la façon dont un module externe
déclare les versions du cœur qu'il accepte. Contrat des modules :
[Architecture des modules](../modules/module-architecture.md) ; frontières :
[cœur et modules](../architecture/core-module-boundaries.md).

## Trois notions à ne jamais confondre

| Notion | Où | Ce qu'elle décrit | Change quand |
|---|---|---|---|
| **Version de distribution** | `forge_design.__version__` (ex. `0.2.0`) | Une version publiée du produit Forge Design | À chaque publication (règles ci-dessous) |
| **`MODULE_API_VERSION`** | `forge_design.modules` (aujourd'hui `1`) | La forme **majeure** du contrat des modules | Seulement si le contrat des modules est rompu |
| **`requires_forge_design`** | `ModuleDescriptor` d'un module (ex. `">=0.2.0,<1"`) | Les versions de distribution du cœur qu'un module accepte, parce qu'il utilise des capacités apparues dans une version donnée | Quand le module commence à utiliser une capacité plus récente |

Exemple : `forge-design 0.4.0` et `MODULE_API_VERSION 1` ; le module A exige
`>=0.3`, le module B `>=0.4`. Les deux comprennent l'API 1 ; seul B a besoin
d'une capacité apparue en 0.4. `MODULE_API_VERSION` ne sert jamais à exprimer
une version minimale du cœur, et une contrainte de distribution ne crée jamais
une nouvelle génération du contrat.

## Source autoritaire de la version

Une seule source : `forge_design.__version__` dans `forge_design/__init__.py`.
`pyproject.toml` la lit (`version = {attr = "forge_design.__version__"}`) ; la
roue, la métadonnée installée (`importlib.metadata.version("forge-design")`)
et `forge-design --version` en découlent. Elle fonctionne aussi depuis le
checkout, sans installation. Aucune autre copie n'est permise (test
`test_packaging.py`). Après une montée de version, une installation éditable
doit être réinstallée pour rafraîchir sa métadonnée.

## Politique de version (SemVer, forme PEP 440)

`MAJEURE.MINEURE.CORRECTIVE`, préversions PEP 440 (`aN`, `bN`, `rcN`,
`.devN`) :

| Montée | Signification |
|---|---|
| **MINEURE** | Capacité publique **additive et compatible** (nouvelle méthode du Graphic Core, nouveau champ facultatif du descripteur, nouvelle action d'hôte…) |
| **CORRECTIVE** | Correction compatible, sans capacité publique nouvelle |
| **MAJEURE** | Rupture volontaire d'une API publique supportée |

**Règle de compatibilité 0.x (choix délibéré).** Forge Design ne suit pas
l'interprétation habituelle des versions `0.x` où chaque MINEURE peut tout
casser : en `0.x`, une MINEURE reste **additive et compatible**, une
CORRECTIVE reste compatible, et la rupture d'une API publique supportée
(`forge_design.modules`, `forge_design.specialized`, contrat `GraphicScene`,
API publique du Graphic Core, client générique des ressources de module) n'est
**jamais** une simple montée `0.x` MINEURE : elle exige une MAJEURE et/ou un
nouveau `MODULE_API_VERSION`, selon la frontière rompue. C'est ce qui rend
légitime une contrainte de module `>=0.Y,<1`. Ce n'est pas une promesse de
stabilité 1.0 : les API internes restent libres.

Préversions : `0.3.0.dev0` précède `0.3.0` et suit `0.2.0`.

## Déclarer la compatibilité dans un module

Deux barrières, de même valeur :

1. **`Requires-Dist`** de la distribution du module (`pyproject.toml`) :
   `forge-design>=0.2.0,<1`. Première barrière : `pip` refuse normalement
   d'installer le module avec un cœur hors intervalle.
2. **`requires_forge_design`** du descripteur : `">=0.2.0,<1"`, spécificateur
   PEP 440. Seconde barrière : l'hôte la vérifie à l'activation et protège
   l'installation manuelle, `--no-deps`, l'installation éditable ou un
   environnement cassé.

Un test du module garantit que les deux sont identiques (le cœur ne lit
jamais le `pyproject.toml` d'un module). `requires_forge_design = None` :
aucune contrainte au-delà de `MODULE_API_VERSION` (compatibilité des modules
API 1 antérieurs) ; tout nouveau module **devrait** la déclarer.

## Vérification à l'activation

`activate_modules` compare `forge_design.__version__` au spécificateur avant
toute exposition (navigation, routes, assets, actions, types de ressource,
script d'édition) :

| Situation | Diagnostic | Effet |
|---|---|---|
| Spécificateur absent | — | Activation normale |
| Version du cœur dans l'intervalle (préversion comprise si elle y est) | — | Activation normale |
| Version du cœur hors intervalle | `core-version-incompatible` : « Le module « id » nécessite forge-design SPEC ; version installée : X. » | Module non activé ; les autres continuent ; Forge Design démarre |
| Version du cœur illisible et module contraint | `core-version-unknown` | Module non activé (jamais supposé compatible) |
| Spécificateur invalide | `descriptor-invalid` | Module non activé |
| `api_version` non supportée | `api-incompatible` (vérifié avant) | Module non activé |

Préversions : `0.2.0.dev0` ne satisfait pas `>=0.2.0` ; `0.2.0` et
`0.3.0.dev0` le satisfont (comme `pip check` pour une version installée).

**Limite.** Si un module importe un symbole absent du cœur (par exemple
`from forge_design.modules import NouveauSymbole` avec un cœur ancien),
l'import échoue avant que l'hôte puisse lire son descripteur : le diagnostic
reste `module-import-failed`. C'est pourquoi `Requires-Dist` est la première
barrière et la vérification à l'activation une défense supplémentaire.

## Nouvelle capacité publique du cœur

1. Ticket du cœur qui l'introduit.
2. Nouvelle version MINEURE (ou CORRECTIVE si c'est une correction).
3. Le module qui l'utilise relève sa borne basse (`Requires-Dist` et
   `requires_forge_design`, ensemble).
4. Tests d'installation (pip) et d'activation.

Une capacité purement interne ne demande pas de relever la contrainte d'un
module.

## Dépréciation

Avant de retirer une API publique : la documenter comme dépréciée, la garder
au moins une version MINEURE publiée, puis la retirer avec une MAJEURE et/ou un
nouveau `MODULE_API_VERSION`. Aucun mécanisme automatique de dépréciation.

## Ordre de publication

Pour un module qui exige une nouvelle capacité : **publier d'abord le cœur,
ensuite le module**, jamais l'inverse (un module publié avant son cœur serait
installable nulle part, ou trompeusement). Pas de tag ni de publication
automatique : la décision de publier reste manuelle.

## Hors périmètre

Pas de version séparée du Graphic Core (`GRAPHICS_API_VERSION`) : la version de
distribution suffit. Pas de mise à jour ni de téléchargement automatiques de
modules. Les versions de **format** des documents d'un module (par exemple
`format_version` d'un schéma Circuit) sont un autre sujet.
