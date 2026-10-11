# Frontières du cœur, du moteur générique et des modules

Statut : **normatif** (FD-ARCH-001). Ce document fixe ce qui appartient à Forge
Design en tant qu'outil des projets Forge, ce qui appartient à son moteur
générique, et ce qui appartient aux modules spécialisés. Le contrat détaillé des
modules reste dans [Architecture des modules](../modules/module-architecture.md) ;
l'API JavaScript du moteur dans [Moteur graphique](../graphics/graphics-engine.md) ;
l'architecture d'ensemble dans [Architecture V2](../02-architecture.md).

## Deux responsabilités, un produit

```text
Forge Design
│
├── A. outils propres aux projets Forge
│   └── Project Inspector, Route Explorer, Entity Explorer, Debug Center,
│       Template Viewer, Template Designer
│
├── B. moteur générique d'outils spécialisés
│   ├── hôte de ressources (système de fichiers sûr, révision, conflit, historique)
│   ├── hôte de modules (activation, routes exactes, assets, actions bornées)
│   ├── Graphic Core (scène, viewport, sélection, gestes, calques monde)
│   └── contrat spécialisé (types, codecs, validation, capacités)
│
└── contrat des modules
        ├── Circuit (ForgeDesign-Circuit, validation réelle)
        └── autres domaines (Flowchart, Network…)
```

## Matrice des frontières

| Élément | Propre à Forge | Moteur générique | Module |
|---|:---:|:---:|:---:|
| Project Inspector, détection et version Forge | ✓ | | |
| Route Explorer, Entity Explorer, Debug Center | ✓ | | |
| Template Viewer, Template Designer, preview | ✓ | | |
| `ToolRegistry` (exactement les cinq Tools Forge) | ✓ | | |
| `ProjectSelector`, `CurrentProjectContext` (runtime), projets récents (XDG) | ✓ | | |
| Hôte de ressources (`read/write_specialized_resource`, `list_specialized_resources`) | | ✓ | |
| Système de fichiers sûr (`openat`/`dir_fd`, `O_NOFOLLOW`, `O_NONBLOCK`, `fstat`, `samestat`, lectures bornées, écriture atomique) | | ✓ | |
| Révision, conflit, historique | | ✓ | |
| Hôte des modules (`ModuleHost`), activation explicite (`activate_modules`) | | ✓ | |
| Contrat spécialisé (`forge_design.specialized`) et contrat des modules (`forge_design.modules`) | | ✓ | l'utilise |
| `ModuleAction` : route POST, garde d'origine, payload borné, jeton, validation, écriture, PRG, statut HTTP | | ✓ | |
| Graphic Core : `GraphicScene`, rendu, viewport, minicarte, niveaux de détail, sélection de nœuds, `nodeMove`, `addOverlay`, `worldAt`, `onViewChange` | | ✓ | |
| Client générique des ressources de module (`/module-resource.js`) | | ✓ | |
| Format, codec, schéma et validation métier d'un domaine | | | ✓ |
| Projection document → `GraphicScene` | | | ✓ |
| Transformation métier d'une action (`handler(document, payload)`) | | | ✓ |
| Script d'édition (`createResourceEditor`), configuration d'édition | | | ✓ |
| Routage, géométrie et vocabulaire métier (bornes, fils, jonctions de Circuit ; étapes d'un organigramme…) | | | ✓ |

## Règles

1. **Vocabulaire.** Le moteur générique connaît `node`, `edge`, `scene`,
   `viewport`, `selection`, `overlay`, gestes, `action`, `resource`, `revision`,
   `history`, `module`, `capability`. Il ne connaît ni résistance, ni borne, ni
   fil, ni jonction, ni routeur électrique, ni commutateur réseau, ni décision
   d'organigramme, ni classe UML. Le code livré du cœur ne contient aucun
   vocabulaire Circuit (test).
2. **Direction des dépendances.** `Forge MVC ← Forge Design ← modules`, jamais
   l'inverse : le paquet `forge_design` n'importe que la bibliothèque standard et
   ses dépendances déclarées (Forge MVC — paquets `core` et `integrations` —,
   Jinja2/markupsafe, pydantic, packaging), jamais un paquet `forge_design_*`
   ni une autre pile Web (test statique).
3. **Une seule pile Web.** Le cœur est une application Forge MVC (`Application`,
   `Router`, `Request`, `Response`, Jinja, `create_wsgi_app`) ; aucun
   mini-framework, Flask, FastAPI ou serveur Node parallèle.
4. **Modules ≠ Tools.** Un module spécialisé n'ajoute jamais de Tool au
   `ToolRegistry` : il apparaît dans la zone « Modules » du shell, sous
   `/modules/<id>/` (test comportemental sur le registre composé par le serveur).
5. **Le module ne voit que son document.** Codec : octets ; projection,
   configuration d'édition et handler : le document décodé (et le payload borné
   pour le handler). Jamais racine de projet, chemin système, `Request`,
   `Router`, `Application` (test des arguments effectivement passés).
6. **`GraphicScene` est une projection runtime**, jamais un document persistant :
   lire et projeter n'écrivent rien, et une action ne peut faire enregistrer
   qu'une ressource encodée par le codec du module (test).
7. **Activation explicite**, depuis la ligne de commande, dans l'ordre donné,
   sans découverte (`entry_points`, `pkgutil`, balayage de `sys.path` interdits ;
   test). Un échec de module est un diagnostic, jamais une panne de l'hôte.
8. **Code de confiance, pas de bac à sable.** Un module Python installé et
   activé est du code local de confiance : le contrat empêche les accès
   *accidentels*, il ne protège pas d'un module malveillant.
9. **Primitive générique révélée par un module : oui ; comportement d'un
   domaine : non.** Le cœur peut exposer une primitive qu'un module a rendue
   nécessaire (`nodeMove`, `addOverlay`, `worldAt`, `onViewChange`) si elle est
   générique ; il ne contient jamais de comportement propre à un domaine.
10. **Le cœur est complet sans module.** Sans activation : aucune route
    `/modules`, aucune zone Modules, les cinq Tools inchangés.

## Preuves

| Règle | Garde automatisée |
|---|---|
| 1 | `test_modules_contract.py::test_core_distribution_ships_no_circuit`, `test_graphics_and_tool_registry_know_no_module` |
| 2, 3 | `test_module_boundaries.py::test_core_depends_only_on_stdlib_and_declared_packages`, `test_web_layer_dogfoods_forge_mvc`, `test_modules_contract.py::test_core_never_imports_circuit` |
| 4 | `test_module_boundaries.py::test_modules_never_become_tools`, `test_three_modules_with_editors_stay_isolated` |
| 5 | `test_module_boundaries.py::test_module_code_receives_only_the_document_and_the_payload`, `test_module_actions.py::test_handler_receives_only_document_and_payload` |
| 6 | `test_module_boundaries.py::test_graphic_scene_is_never_persisted` |
| 7 | `test_modules_contract.py::test_module_contract_depends_only_on_the_specialized_contract`, `test_failures_are_isolated_with_diagnostics` |
| 9 | Module témoin « flowchart-like » (`tests/flow_witness/`) : un second domaine qui déclare, projette, pose un calque, agit et recharge sans aucun code Circuit |
| 10 | `test_web_modules.py::test_without_modules_nothing_is_exposed` |

Le module témoin n'est pas livré : il vit dans les tests du cœur. Circuit
(`ForgeDesign-Circuit`) est une **validation réelle**, jamais la définition du
contrat ; les tests du cœur ne dépendent pas de son dépôt.
