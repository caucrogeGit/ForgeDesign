# Rapport — FD-SPECIALIZED-001

## Ticket et objectif

Ouvrir la Phase 9 en définissant le contrat minimal d'un outil spécialisé :
ce dont Forge Design a besoin pour héberger Circuit, Network ou 3D sans
connaître leur domaine. Le contrat est confronté au cas réel de DrawCiel
intégré à SéquenCiel. Ticket documentaire : aucun code, registre ni outil.

## État Git initial

`main` synchronisée avec `origin/main` à `9339b2f` — FD-REALPREVIEW-005
(Phase 8 terminée). Seule modification suivie préexistante :
`docs/rapports/FD-CONTRACT-001.md`, préservée hors commit.

## Référence DrawCiel étudiée

Sources lues dans `/home/roger/Projets/SequenCiel`, en lecture seule :
- aucun fichier SéquenCiel modifié ;
- aucun code DrawCiel copié, importé ou exécuté ;
- SéquenCiel non lancé.

| Source | Contenu utilisé |
|---|---|
| `docs/tickets/DC-016-00-audit-architecture-drawciel.md` | Audit architectural de DrawCiel 0.15 intégré, au commit SéquenCiel `5a02277d` : localisation, architecture, flux, persistance, isolation, TP, modèle de document, moteur graphique, domaine, simulation, couplage, tests, risques, découplages candidats, inconnues. |
| `docs/tickets/DC-016-01-contrat-persistance-drawciel.md` | Caractérisation de la persistance : corpus synthétique, matrice de compatibilité, champs filtrés et limites du contrat serveur. |
| `docs/rapports/DC-016-01-architecture-microcontroleurs-iot.md`, `DC-016-02-banc-compilation-avr.md`, `DC-016-03-qualification-avr8js-simavr.md` | Extraits sur les moteurs externes, illustrant les dépendances optionnelles : pas de téléchargement automatique, échec explicite, capacités limitées. |

État constaté : l'audit est commité dans SéquenCiel (`663131e0`), et le dépôt
compte 47 commits après le commit audité (HEAD `c229b2ed`). Ce ticket **ne
réaudite pas** le code courant. Les affirmations sur DrawCiel proviennent des
documents ci-dessus. Seule l'existence actuelle des fichiers cités a été
vérifiée :
- `static/vendor/drawciel/js/app.js`, `model.js`, `simulation.js`, `tp.js` ;
- `static/drawciel-cadre.js`, `static/drawciel-hote.js` ;
- `mvc/controllers/drawciel_controller.py`, `mvc/services/drawciel.py`,
  `mvc/models/drawciel_model.py` ;
- ADR 255 et 256.

Éléments DrawCiel examinés à travers l'audit :
- `app.js` : état global, scène SVG, historique, fichiers, API hôte ;
- `model.js` : propriétés, bornes, réseaux ;
- `simulation.js` : solveur MNA et mutations de `component.state` ;
- `tp.js` : définition, tentative, formats ;
- `drawciel-cadre.js` et `drawciel-hote.js` : `postMessage`, file de
  sauvegarde, révisions, WebP ;
- le contrôleur, le service `drawciel.py` et le modèle SQL : autorisations,
  filtrage JSON, transactions et `Revision` ;
- les formats `.drawciel`, `.drawcielt`, `.drawcielr` et les formats
  historiques `.drawcielx` et `.edrawx`.

## Architecture DrawCiel observée

```text
application JavaScript autonome (app.js, model.js, simulation.js, tp.js)
→ iframe sandbox (allow-scripts allow-downloads allow-modals, sans allow-same-origin)
→ adaptateur interne drawciel-cadre.js (API et DOM du moteur)
→ adaptateur hôte drawciel-hote.js (routes, CSRF, révisions, WebP)
→ backend SéquenCiel (13 routes, contrôleur, service, modèle SQL, MariaDB)
```

Quatre frontières sont observables mais incomplètes :
1. **la ressource** : état natif du circuit, définition TP et tentative ;
2. **le runtime** : `app.js` et les modules globaux, avec simulation ;
3. **l'intégration hôte** : les deux adaptateurs et les routes ;
4. **le domaine** : catalogue, bornes, réseaux, simulation, mesures, TP.

Le TP traverse ces quatre frontières. Aucun registre de profils n'existe.

## Leçons retenues

1. **Pas de moteur graphique comme définition.** Un outil spécialisé est une
   description, des types de ressources, des capacités, un runtime éventuel
   et une intégration hôte. Ce n'est pas « un moteur graphique ».
2. **L'état runtime pollue la ressource s'il n'est pas séparé** :
   `component.state` du solveur est sérialisé, confirmé par DC-016-01.
3. **Une version absente rend toute évolution dangereuse.** La version
   native est filtrée à la persistance, sans dispatch de migration.
4. **La validation se superpose** (structure, électrique, pédagogique). Elle
   est dupliquée entre JS et Python et ne doit pas être réduite à un booléen.
5. **Les modes d'interface ne sont pas des autorisations** : le serveur
   reste l'autorité.
6. **L'autosave est nécessaire à un outil de dessin**, mais reste contrôlé
   par la révision et le conflit (409).
7. **Source et rendu doivent rester distincts** : le WebP n'est pas la
   source, et le lien entre les deux est fragile.
8. **La pédagogie doit rester hors du moteur** pour garder l'outil
   réutilisable.

## Relation avec Tool

**Décision** : le Protocol `Tool` (synchrone, lecture seule,
`run(project_root)`) et le registre des cinq Tools sont **inchangés**. Un
outil spécialisé éditable n'est pas une extension de `Tool`, et il n'y a pas
de `class SpecializedTool(Tool)`.

Terminologie retenue :
- `SpecializedToolDefinition` ;
- `SpecializedResourceType` ;
- `SpecializedResource` ;
- `SpecializedCapability` ;
- runtime spécialisé ;
- hôte ;
- domaine.

## Ressource

Une ressource est la source éditable persistante, distincte du runtime, des
exports, du cache et de l'état d'interface. Son identité est `(type, chemin
relatif, format_version observée)`, sans UUID universel. Le contrat documente
les avantages (lisible, compatible Git) et les limites (un renommage change
l'identité). Le format n'est pas imposé (JSON non obligatoire), mais la
version doit être observable :
- versions lues : un ensemble ;
- version écrite : une seule ;
- version inconnue : refus explicite, sans migration silencieuse.

## Runtime

Le runtime est distinct de la ressource et n'a aucun accès au système de
fichiers. Il ne fait que demander une sauvegarde ou un export, et l'hôte
décide. Aucune technologie n'est imposée (iframe, DOM, SVG, Canvas, WebGL).
Le type déclare son état persistant et son état runtime-only. Par défaut,
rien de runtime n'est sauvegardé ; l'état éditorial est un choix explicite
du format.

## Capabilities

Les capacités sont atomiques et déclaratives, et non des profils. Il y a deux
niveaux :
- **plateforme**, avec un vocabulaire fermé, dont Forge Design connaît la
  sémantique : `create`, `open`, `edit`, `validate`, `save`, `export`,
  `interactive-runtime` ;
- **outil**, avec un vocabulaire propre (par exemple `simulate`, `measure`),
  que la plateforme ne connaît que par son identifiant et sa disponibilité.

`preview` est reporté, car ambigu avec les previews de la Phase 8. Une
capacité n'est jamais un domaine.

## Validation

Un résultat de validation est une liste d'issues (code, `error` ou
`warning`, message, localisation éventuelle) avec indicateur de troncature,
et non un booléen. Le type déclare ses niveaux de validation :
- le niveau structurel bloque toujours l'écriture ;
- les niveaux de domaine ne la bloquent que si le type le déclare ;
- un circuit incomplet reste donc sauvegardable.

Validité, simulabilité et pédagogie restent distinctes. La validation n'est
jamais une autorisation.

## Erreurs

Huit catégories plateforme :
- `resource-not-found` ;
- `resource-refused` ;
- `unsupported-version` ;
- `invalid-resource` ;
- `conflict` ;
- `capability-unavailable` ;
- `dependency-unavailable` ;
- `runtime-error`.

`resource-refused` a été ajoutée à la liste du ticket. Elle sépare les
chemins, liens, types et tailles refusés de l'absence de la ressource, comme
le font déjà les lecteurs confinés de Forge Design. Les erreurs de domaine
(circuit flottant, valeur absente, conflit d'alimentation) restent des issues
de l'outil.

## Sauvegarde

Le pipeline reprend la discipline de `DesignRevision` et SAFEWRITE :
1. lecture bornée ;
2. révision : taille, `mtime_ns`, empreinte, et périphérique et inode si
   disponibles ;
3. édition ;
4. validation ;
5. diff, ou résumé pour un format non textuel ;
6. décision explicite ;
7. revalidation ;
8. écriture atomique avec révision attendue ;
9. journalisation.

Garanties associées :
- un conflit n'écrase jamais rien ;
- aucune écriture n'est déclenchée par un GET, une preview ou une
  inspection ;
- la source de vérité est le fichier du projet ;
- la base SQL de SéquenCiel n'est pas confondue avec cette source.

## Autosave

L'autosave est autorisé **dans une session d'édition ouverte
explicitement**, sans confirmation à chaque modification. Chaque écriture
respecte la révision, la validation bloquante, les bornes, l'écriture
contrôlée et la journalisation, sans chevauchement. Un conflit suspend
l'autosave jusqu'à une décision explicite. La fermeture de la session arrête
les écritures. Ce cadre rend possible un futur outil de type DrawCiel
(`dirty` puis 450 ms), sans affaiblir l'anti-écrasement.

## Exports

Source ≠ export. Un export ne remplace jamais la source et n'est pas
réimporté sans action explicite. Le type déclare des formats d'export
(identifiant et type MIME), et Forge Design décide de la destination, de la
publication et des protections. Aucune API `export() -> bytes` définitive
n'est fixée.

## Dépendances optionnelles

Une dépendance se déclare par `id`, `purpose`, `required_for` (capacités) et
`availability`, déterminée par une sonde sans effet de bord. Une dépendance
absente ne rend indisponibles que les capacités concernées, avec un
diagnostic explicite. Il n'y a aucune installation automatique, et aucun
moteur n'est choisi pour Circuit.

La simulation DrawCiel 0.15 est un solveur intégré, pas une dépendance
externe. Les travaux AVR de SéquenCiel (DC-016-02 et DC-016-03) illustrent en
revanche l'échec explicite sans téléchargement et les « capacités limitées ».

## Intégration hôte

Le contrat fixe des responsabilités logiques — `ready`, `load`, `dirty`,
`save-request`, `export-request`, `error` — et non un protocole filaire. Ni
`postMessage` ni un autre transport ne sont standardisés. L'hôte ne déduit
aucun droit des messages et refuse toute `save-request` hors session
d'édition. Les messages sont bornés.

## UI

Une entrée UI se décrit par :
- le nom ;
- une icône facultative (référence opaque) ;
- une entrée ;
- les types de ressources ;
- les capacités avec leur disponibilité.

La navigation de Forge Design n'est pas modifiée. Un outil a sa propre
surface. Circuit n'est pas un bloc du Template Designer.

## Pédagogie

La pédagogie est hors du contrat générique : professeur, élève, sujet,
tentative, corrigé, notation, progression. Une application l'associe à une
ressource sans modifier le moteur, et la référence côté SéquenCiel relève de
la Phase 12.

## Stockage

Une ressource spécialisée est une source du projet : elle vit en **zone C**,
jamais en zone B, et l'état d'interface personnel va en zone A. Chaque type
déclare son espace de sources, et le ticket qui l'introduit l'ajoute au
contrat de stockage. Aucun chemin n'est réservé : ni `mvc/circuit/`, ni
`resources/circuit/`, ni `.forge-design/circuit/`. Une sous-section « Ressources
d'outils spécialisés » est ajoutée au §4 du contrat de stockage, car la
zone C ne visait jusqu'ici que `mvc/views/`.

## Décisions retenues

Réponses aux questions à fermer du ticket :

| Question | Décision |
|---|---|
| Tool existant étendu ? | Non : `Tool` en lecture seule inchangé, contrat spécialisé séparé. |
| Ressource distincte du runtime ? | Oui : état persistant et runtime-only déclarés par type. |
| Capabilities ou profils ? | Capacités atomiques, en deux niveaux (plateforme fermé, outil propre) ; pas de profils. |
| Source et export ? | Distincts ; l'export ne remplace jamais la source, et l'hôte publie. |
| Validation générique minimale ? | Issues structurées (code, sévérité `error`/`warning`, message, localisation) ; niveaux bloquants déclarés. |
| Politique de sauvegarde ? | Écriture contrôlée avec révision attendue, conflit sans écrasement, journalisation. |
| Autosave autorisable ? | Oui, dans une session d'édition ouverte explicitement, avec les mêmes contrôles. |
| Dépendances optionnelles ? | Par capacité, avec disponibilité sondée, diagnostic explicite et sans installation automatique. |
| Pédagogie ? | Hors contrat, associée par l'application (Phase 12). |

Les autres décisions attendues sont également retenues : runtime sans accès
au système de fichiers, ressource en zone C, pas de registre ni de plugin à
ce stade, `DesignFile` et `ViewContract` inchangés.

## Questions reportées

Questions laissées ouvertes :
- chemin et format Circuit ;
- moteur de simulation ;
- API graphique ;
- protocole filaire runtime ↔ hôte ;
- formats et publication d'export ;
- capacité `preview` ;
- identifiant stable interne de ressource ;
- registre d'outils spécialisés ;
- Network et 3D ;
- isolation technique d'un runtime.

Elles sont détaillées dans le contrat, avec le ticket attendu pour chacune.

## Fichiers créés

- `docs/specialized-tools/specialized-tool-contract.md` (contrat normatif)
- `docs/rapports/FD-SPECIALIZED-001.md`

## Fichiers modifiés

- `docs/02-architecture.md` : la §13 « Outils spécialisés » remplace
  l'ancienne « Outils spécialisés futurs ». Celle-ci parlait de « Tool
  Circuit », ce qui contredit la décision. Elle renvoie désormais au contrat.
- `docs/03-roadmap.md` : Phase 9 annotée (DrawCiel → contrat → outil simple
  → registre).
- `docs/storage/storage-contract.md` : §4, règle générale des ressources
  d'outils spécialisés en zone C.

Aucun fichier Python, test, template, dépendance ni fichier SéquenCiel n'est
modifié. Aucun code DrawCiel n'est copié.

## Validations finales

Exécutées après la dernière modification documentaire, ce rapport compris.

| Commande | Résultat |
|---|---|
| `git diff --check` | Succès |
| Tests qui lisent `docs/` (`tests/test_design_schema.py`, `tests/test_view_contract_schema.py`, depuis le scratchpad) | 45 réussis |
| compileall / ruff / pyright | Non requis : aucun Python modifié |
| Suite globale | Non requise : aucun code ni fichier consommé par le runtime modifié ; aucun test ne lit l'architecture, la roadmap ou le contrat de stockage |
| MkDocs | N/A : aucune configuration MkDocs dans Forge Design |

Seul ce tableau a été ajouté au rapport après l'exécution. Les validations ont
été relancées sur le contenu final, avec un résultat identique.

## Conclusion

**Le contrat est-il suffisamment précis pour implémenter un outil spécialisé
minimal sans prendre de nouvelle décision d'architecture fondamentale ?**

**Oui.** FD-SPECIALIZED-002 peut implémenter un outil volontairement simple
sans trancher de nouvelle question d'architecture. Le contrat fixe :
- l'identité ;
- un type de ressource versionné en zone C, avec son espace de sources ;
- le vocabulaire des capacités ;
- les issues de validation et les catégories d'erreurs ;
- l'écriture contrôlée et l'autosave en session ;
- la règle des exports et des dépendances optionnelles ;
- la frontière runtime ↔ hôte.

Les choix restants sont **locaux à l'outil**, prévus par le contrat :
- le chemin et le format de sa ressource ;
- la forme Python de ses déclarations (dataclasses), à introduire au besoin
  par ce ticket ;
- la technologie de son éventuel runtime.

## État Git final

Un commit sur `main`, rapport inclus, sans push.
Message : `docs: définir le contrat des outils spécialisés (FD-SPECIALIZED-001)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Hash :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-SPECIALIZED-001.md
```
