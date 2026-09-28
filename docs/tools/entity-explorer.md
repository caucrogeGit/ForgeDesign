# Entity Explorer

Ouvrir un projet Forge, puis choisir **Entity Explorer** dans la navigation.
La page `/entities` liste les entités et propose leurs champs dans des blocs
natifs dépliables. Sans projet courant, aucun Tool n’est exécuté.

Les sources sont `mvc/entities/<snake>/<snake>.json` et le fichier fixe
`mvc/entities/relations.json`. Les dossiers directs
sont visités dans l’ordre lexical ; les champs gardent l’ordre JSON. Un dossier
canonique sans son JSON attendu produit une anomalie. Aucun autre JSON n’est cherché.
Les noms de dossiers acceptés sont des identifiants minuscules avec chiffres et
underscores séparateurs ; noms cachés, `env`, préfixes de clés SSH et fichiers
isolés sont ignorés. Aucun parcours récursif.

La baseline est Forge main `73a956e587e5f169c028415e0e540c149cbaff56`, contrat
`schema_version: "1.0"`. Le nom métier et la table viennent du JSON, même s’ils ne
correspondent pas au dossier. Les versions inconnues et le format legacy sont
signalés sans migration ni modèle inventé.

Sont affichés : nom, table, nombre de champs, timestamps et soft_delete ; pour
chaque champ : nom, type, requis, nullable, unique, max_length, precision, scale,
default et references si déclarés. Les booléens absents suivent Forge : required
et unique faux, nullable vrai ; required vrai rend nullable faux. Les options
absentes valent faux. La valeur default est affichée comme JSON ; null reste
distinct d’une valeur non déclarée. Une référence étrangère reste du texte.

Il s’agit d’une interprétation minimale, pas d’une validation complète du schéma
Forge : types inconnus affichés sans liste prédéfinie, propriétés hors périmètre
ignorées, contraintes métier et cohérence SQL non vérifiées. Les champs doivent
former une liste non vide ; les attributs affichés sont contrôlés quant à leur
type. Les erreurs restent locales à l’entité et apparaissent dans **Diagnostics**.

Chaque GET relit les JSON, sans cache dans le contexte. Fichiers ordinaires UTF-8
avec BOM accepté, au plus 1 Mio chacun ; liens refusés, parcours des parents par
descripteurs et ouverture sans suivi de liens. Les primitives POSIX nécessaires
sont requises. Le contenu peut changer pendant la lecture : aucun instantané
atomique garanti. Les plafonds centralisés sont décrits dans « Limites connues ».

Aucun import du projet, lecture Python/SQL, commande Forge, connexion à une base,
édition ou écriture. Les relations sont lues uniquement dans `relations.json`, sans recherche
de fichiers supplémentaires. Aucun champ système implicite n’est inventé. Le chemin source est affiché en lien lorsque la politique `/source` l’autorise
(voir Navigation source).

## Relations déclarées

La section Relations présente many_to_one (la source porte la FK) et many_to_many
(pivot avec ses clés source/cible et champs supplémentaires), dans l’ordre du
document. Inverse_name est affiché seulement s’il existe. Source et index
relations[n] identifient la déclaration ; le lien source ouvre le fichier entier.

Le document exige schema_version "1.0" et une liste relations. Fichier absent ou
liste vide : aucune relation déclarée. Legacy et versions inconnues sont refusés.
Une erreur globale laisse les entités disponibles ; une relation mal formée
n’empêche pas les autres d’être affichées.

Pour many_to_one, foreign_key et on_delete sont obligatoires selon le validateur
Forge ; nullable et index valent vrai par défaut. Les valeurs déclaratives
restrict, cascade, set_null et no_action ne sont pas traduites en SQL.
Pour many_to_many, pivot.table/from_key/to_key sont requis, id et unique_pair
doivent être true. On_delete vaut cascade et fields est vide par défaut.
Les champs pivot réutilisent le modèle immuable des champs d’entité et ses défauts.

Les entités source/cible sont vérifiées contre les noms des entités interprétées.
Une référence indisponible produit relation.entity_missing, mais la déclaration
lisible reste présentée ; une entité illisible ne compte pas comme disponible.
Les auto-relations sont conservées. Aucun diagnostic d’absence de champ FK ni
comparaison FK/references n’est ajouté. Aucun on_update interne n’est inventé.

Cette lecture ne remplace pas la validation métier officielle Forge : pas de
validation exhaustive des identifiants, unicités, couples de clés, types pivot ou
compatibilité des politiques. Aucun SQL, DB, comparaison modèle/base,
génération ou édition. La lecture est fondée uniquement sur les contrats JSON.

## Graphe des entités

Le SVG rendu par le serveur complète les tableaux et reste lisible sans JavaScript. Chaque entité,
même isolée, affiche son nom, sa table et son nombre de champs. Chaque déclaration
many_to_many dispose d’un pivot distinct, identifié par le texte « Pivot », des
coins arrondis et une bordure discontinue.

Les flèches suivent `from_entity → to_entity` pour many_to_one : la source porte
la clé étrangère. Une many_to_many suit `source → pivot → cible`, avec le nom
métier sur le premier segment. Les auto-relations, cycles et relations parallèles
sont conservés. Une extrémité manquante empêche de dessiner la relation ; son
anomalie et sa déclaration restent dans les sections textuelles.

Entités à gauche et pivots à droite, dans leur ordre d’entrée ; un couloir par
arête distingue les relations parallèles. Les longs labels sont tronqués dans
le dessin, avec texte complet dans les titres SVG et tableaux. Le conteneur
permet le défilement, y compris au clavier. Aucun zoom ni édition.

Les modèles `EntityGraph` et `EntityGraphLayout` sont immuables et indépendants du
Bridge. Leur construction est linéaire dans les nœuds et arêtes et ne lit aucun
fichier. Les IDs utilisent les positions dans le résultat : reproductibles pour
une même entrée, ils ne sont pas des identifiants persistants après réordonnancement.
En cas de noms d’entités identiques, chaque occurrence reste visible et les relations
désignent la première. Aucune fusion de pivots ou correction métier n’est tentée.

Le placement vise de petits graphes : sa hauteur augmente avec les relations et
les rangées ; certains segments se croisent ou se partagent. Il n’y a ni moteur
de réduction des croisements, ni plafond graphique supplémentaire, ni diagnostic
de cycle de données. Une syntaxe interprétable n’est pas une validation de base.

## Sélection et détails

Cliquer une entité ou un pivot, ou utiliser Entrée/Espace sur son nœud, sélectionne
cet élément. Une deuxième activation le désélectionne. Les bordures renforcées
signalent le choix et ses voisins directs ; les arêtes incidentes sont soulignées.
Pour `Article → article_tag → Tag`, sélectionner Article ne sélectionne pas Tag.
Sélectionner le pivot met en évidence les deux entités voisines.

Le panneau affiche le nom complet, la table, le nombre de champs (supplémentaires
pour un pivot), le nombre d’arêtes incidentes et leur liste orientée avec les noms
métier disponibles. Les parallèles restent distinctes ; une boucle compte une fois.
Échap dans le graphe ou le bouton Désélectionner réinitialise le panneau et rend
le focus au nœud choisi. Les autres éléments restent entièrement visibles.

Le script local `entity-graph.js` ne consulte que les attributs du DOM déjà rendu.
Aucune requête de données, persistance, modification du layout ou des tableaux.
Un rechargement efface la sélection. Sans JavaScript, le SVG et les tableaux
conservent toutes leurs informations ; seul le panneau interactif reste inactif.

## Diagnostics structurés

La section **Diagnostics** présente les compteurs d’erreurs, d’avertissements et
d’informations, puis une liste avec sévérité explicite, code, message et source.
Sans anomalie, les trois compteurs valent zéro et la page indique :
« Aucun diagnostic dans les informations disponibles. » Aucun score ou verdict
global n’est déduit ; cette présentation ne remplace pas une validation Forge exhaustive.

La projection pure `build_entity_diagnostics(EntitiesResult)` conserve les codes,
messages, sources et occurrences du Bridge, erreurs puis avertissements dans
leur ordre initial. La sévérité vient exclusivement de `errors` ou `warnings` ;
aucune information artificielle n’est créée. Les codes stables sont :

- `entity.source_missing`, `entity.unreadable`, `entity.json_invalid`,
  `entity.schema_version_unsupported`, `entity.structure_invalid` ;
- `relation.unreadable`, `relation.json_invalid`,
  `relation.schema_version_unsupported`, `relation.structure_invalid`,
  `relation.type_unsupported`, `relation.entity_missing`.

La source autorisée devient un lien `/source` ; sinon elle reste textuelle.
Le sujet est le chemin source ou
`relations[n]` si un index est disponible. Une relation interprétée à référence
manquante reste dans le tableau. Aucun diagnostic ne modifie le graphe.
`severity` et `code` sont structurés et exposés par les attributs DOM
`data-diagnostic-severity` et `data-diagnostic-code` ; l’index éventuel est exposé
par `data-diagnostic-relation-index`. Le filtrage GET décrit ci-dessous utilise
les diagnostics structurés côté serveur.

## Filtres GET

Le formulaire de `/entities` utilise uniquement GET. L’URL contient tout l’état :
`q`, `type=all|entity|relation`, `relation=all|many_to_one|many_to_many`,
`severity=all|error|warning|info` et `diagnostics=only` (ou `all`).
Réinitialiser revient à `/entities`. Aucun cookie, stockage navigateur, session,
contexte projet ou historique ne conserve les filtres.

`q` est limité à 256 caractères avant et après normalisation strip/casefold.
Une expansion Unicode excessive est refusée avant affichage. La recherche est une sous-chaîne Unicode, sans regex : nom/table et
nom/type/references des champs d’entités ; extrémités, nom/inverse, clé étrangère,
table/clés du pivot et nom/type/references des champs pivot pour les relations.
Les valeurs normalisées restent visibles dans le formulaire.

Les critères se combinent. `type=entity` masque les relations ; `type=relation`
masque les tableaux et détails d’entités. Le type de relation ne restreint que
les relations, pas les entités directement retenues. Le graphe ajoute les premières
occurrences des extrémités nécessaires aux relations retenues, sans les ajouter
aux tableaux d’entités ni aux compteurs. Les relations à extrémité absente restent
dans le tableau ; aucun nœud absent n’est inventé. Les IDs sont locaux à chaque vue.

Les diagnostics sont filtrés uniquement par sévérité, jamais par recherche ou type.
Ils peuvent donc concerner un élément masqué. Les diagnostics globaux restent
visibles. `severity` seul ne limite pas les éléments ; `diagnostics=only` retient
ceux associés à un diagnostic de la sévérité demandée : égalité exacte de chemin
source pour les entités, égalité de relation_index/source_index pour les relations.
Aucune association par message ou nom métier. Les extrémités graphiques de support
peuvent être sans diagnostic. Exemple :
`/entities?q=article&relation=many_to_many&severity=error&diagnostics=only`.

Les compteurs d’éléments comparent les tableaux filtrés à l’inventaire complet ;
les compteurs de diagnostics concernent leur projection par sévérité. Ordres et
occurrences sont conservés. Aucun résultat : message explicite ; aucun nœud :
ni SVG ni script interactif. Chaque GET valide appelle le Tool une seule fois,
sans lui transmettre les filtres, et conserve `Cache-Control: no-store`.

Valeur invalide, paramètre inconnu, recherche trop longue ou répétition détectable :
HTTP 400 avant appel Tool. Le parseur public Forge élimine les valeurs vides :
`q=` équivaut à l’absence, `q=&q=Article` est une recherche unique, et deux valeurs
non vides sont refusées. Cette convention s’applique à tous les paramètres.
POST reste refusé. Aucun fichier projet ou de configuration n’est écrit par ces GET.


## Navigation source

Les sources d’entités, de relations et de diagnostics sont cliquables uniquement
si la politique lexicale les autorise. Pour les contrats d’entités, seuls
`mvc/entities/<snake>/<snake>.json` et `mvc/entities/relations.json` sont acceptés.
Le nom de dossier suit `[a-z][a-z0-9]*(?:_[a-z0-9]+)*` et correspond exactement au
nom du JSON. Traversal, chemins absolus, segments cachés/sensibles, fichiers Python,
SQL et JSON non canoniques sont refusés. Les liens proviennent des SourceLocation
existantes, sans reconstruire le chemin depuis le nom métier.

La page `/source` affiche le texte brut UTF-8/BOM, au plus 1 Mio, avec numéros de
ligne et échappement HTML. Un JSON invalide reste consultable depuis son diagnostic.
Les sources non renseignées, dossiers ou refusées lexicalement ne deviennent pas des
liens trompeurs ; une source autorisée mais disparue retourne 404 à l’ouverture.
L’autorisation lexicale d’un lien ne garantit pas que le fichier existe ou soit
lisible : la lecture vérifie alors tous les segments, refuse les symlinks et les
fichiers non réguliers. Aucun parsing JSON, exécution ou écriture.

Les liens Entity Explorer ouvrent le fichier entier sans paramètre line ni
pseudo-ancre ; relations[n] reste une information textuelle à côté du lien.
Le retour est déduit du chemin validé : Retour à Entity Explorer vers `/entities`,
sans préserver les filtres. Aucun return_to fourni par le client n’est utilisé.
Aucun formulaire de chemin, catalogue de fichiers ou navigation dossier n’est ajouté.
Les nœuds du graphe conservent leur interaction locale.


## API stable actuelle

| API | Entrée → sortie | Responsabilité |
|---|---|---|
| `read_entities(root)` | racine str/PathLike → `EntitiesResult` | Lecture JSON statique, bornée et confinée |
| `EntitiesResult` | tuples entities/errors/warnings/relations | Faits disponibles, sans projection Web |
| `EntityInfo`, `EntityFieldInfo` | valeurs déclaratives et source | Contrat minimal immuable des entités/champs |
| `RelationInfo`, `ManyToOneInfo`, `ManyToManyInfo` | extrémités, index source et options | Déclarations, sans SQL ni résolution DB |
| `EntityExplorerTool.run(root)` | Path → `EntitiesResult` | Adaptateur du Bridge, sans filtres |
| `build_entity_diagnostics(result)` | résultat → `EntityDiagnostics` | Conservation des issues, erreurs puis warnings |
| `filter_entities(result, diagnostics, filters)` | faits complets + `EntityFilter` → `EntityFilteredView` | Sélection pure et supports graphiques |
| `build_entity_graph(result)` | résultat → `EntityGraph` | Nœuds/arêtes déterministes |
| `build_entity_graph_from_items(entities, relations)` | tuples → `EntityGraph` | Même projection pour une vue filtrée |
| `layout_entity_graph(graph)` | graphe aux IDs uniques/extrémités présentes → `EntityGraphLayout` | Placement pur à deux colonnes |

Les dataclasses exposent des tuples et sont gelées. Aucun de ces contrats n’exécute
Forge, n’importe le projet ou n’interroge une base. Les transformations après lecture
n’effectuent aucun accès filesystem. Les IDs graphiques sont locaux à la projection.
Les limites d’analyse relèvent du Bridge ; les fonctions pures acceptent les faits fournis.

## Limites connues

| Constante centralisée | Valeur | Comportement au dépassement |
|---|---:|---|
| MAX_SOURCE_BYTES | 1 Mio/fichier | Refus local de lecture |
| MAX_ENTITY_DIRECTORY_ENTRIES | 4096 | Préfixe de découverte conservé, warning entity.analysis_truncated |
| MAX_ENTITY_FILES | 256 | Candidats canoniques inspectés, puis arrêt et même warning |
| MAX_ENTITY_RELATIONS | 512 | Premières déclarations (invalides incluses), warning relation.analysis_truncated |
| MAX_ENTITY_FIELDS | 256 | Premiers champs interprétés, warning entity.fields_truncated |
| MAX_ENTITY_PIVOT_FIELDS | 64 | Premiers champs pivot, warning relation.fields_truncated |
| MAX_FILTER_QUERY_LENGTH | 256 | HTTP 400 avant/après normalisation si dépassement |

La découverte lit au plus 4097 noms (un témoin de dépassement), trie seulement les
4096 premiers dans l’ordre lexical, puis inspecte au plus 256 candidats. Les entrées
ignorées comptent dans la borne de découverte ; un candidat inaccessible ou invalide
compte dans la borne d’inspection. Sous ces bornes, l’ordre lexical historique est
inchangé. Au-delà de 4096 entrées, le sous-ensemble dépend de l’ordre fourni par le
filesystem, et un warning le signale ; aucun ordre global n’est promis.
Les champs et relations conservent leur ordre JSON. Le document JSON entier est
encore décodé, sous la borne 1 Mio, avant limitation des objets interprétés.
Les compteurs représentent les données disponibles, pas le volume total non analysé.
Les filtres n’élargissent jamais l’analyse ; les warnings globaux ne sélectionnent
aucun élément arbitraire avec diagnostics=only.

`entity.name_duplicate` et `entity.table_duplicate` sont des warnings par occurrence
sur les EntityInfo déjà lus (égalité exacte, sans casefold). Les données sont gardées,
le graphe désigne la première occurrence du nom, y compris en vue filtrée. Ces
constats ne prétendent pas valider les règles SQL ou remplacer check:model.
Les champs tronqués au-delà du plafond ne sont pas validés ; /source permet de
consulter le contrat entier. Des références vers des entités non disponibles,
y compris non analysées, peuvent produire relation.entity_missing.

L’analyse reste statique JSON et minimale : aucune validation Forge exhaustive,
DB, SQL, édition ou génération. L’état filesystem n’est pas atomique globalement.
Les parents sont ancrés par descripteurs sans symlink ; le dossier d’entité est
comparé à sa découverte et chaque fichier à son stat avant ouverture. Un dossier
ouvert peut être renommé et son contenu modifié : aucun instantané global n’est promis.
La taille cumulée peut atteindre 256 Mio de contrats d’entités plus 1 Mio de relations,
même si la lecture est séquentielle ; les objets Python ajoutent leur propre coût mémoire.
Le layout reste simple : grandes hauteurs, segments partagés/croisements possibles,
labels tronqués visuellement, pas d’optimisation des croisements. Interaction locale
seulement, validation navigateur/lecteur d’écran réelle non effectuée.

Pour /source, le contrat historique de paramètres est conservé et testé : première
valeur non vide de path/line, autres valeurs et clés inconnues ignorées. Cette
convention diffère de /entities qui refuse les doublons détectables et clés inconnues ;
la politique lexicale s’applique toujours à la valeur effectivement retenue.
