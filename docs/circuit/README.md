# Circuit : module externe

Depuis FD-MODULES-003, Circuit ne fait plus partie du cœur Forge Design. Le
code, les tests et les documents normatifs vivent dans le dépôt
**ForgeDesign-Circuit** :

| Élément | Valeur |
|---|---|
| Dépôt | `ForgeDesign-Circuit` (dépôt voisin `../ForgeDesign-Circuit`) |
| Distribution | `forge-design-circuit` |
| Paquet | `forge_design_circuit` |
| Identifiant de module | `circuit` |
| Activation | `forge-design --module forge_design_circuit` |

Les anciens documents de ce dossier ont été déplacés, sans réécriture :

| Ancien chemin (cœur) | Nouveau chemin (module) |
|---|---|
| `docs/circuit/circuit-scope.md` | `docs/circuit-scope.md` |
| `docs/circuit/circuit-resource.md` | `docs/circuit-resource.md` |
| `docs/circuit/circuit-domain.md` | `docs/circuit-domain.md` |

La provenance (commit source `2a0db00`, chemins copiés, commits historiques)
est décrite dans le fichier `PROVENANCE.md` du module. L'histoire avant
extraction reste lisible ici : rapports FD-CIRCUIT-001 à FD-CIRCUIT-003 et
[FD-MODULES-003](../rapports/FD-MODULES-003.md).

Le cœur n'importe jamais `forge_design_circuit` et ne livre aucun code Circuit.
Il héberge le module comme n'importe quel autre, via le contrat décrit dans
[Architecture des modules spécialisés](../modules/module-architecture.md) et
[Hôte des modules](../modules/module-host.md).
