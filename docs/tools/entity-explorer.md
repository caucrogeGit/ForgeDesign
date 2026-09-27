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
type. Les erreurs restent locales à l’entité et apparaissent dans **Anomalies**.

Chaque GET relit les JSON, sans cache dans le contexte. Fichiers ordinaires UTF-8
avec BOM accepté, au plus 1 Mio chacun ; liens refusés, parcours des parents par
descripteurs et ouverture sans suivi de liens. Les primitives POSIX nécessaires
sont requises. Le contenu peut changer pendant la lecture : aucun instantané
atomique garanti. Le nombre d’entités n’est pas plafonné dans cette version.

Aucun import du projet, lecture Python/SQL, commande Forge, connexion à une base,
édition ou écriture. Les relations sont lues uniquement dans `relations.json`, sans recherche
de fichiers supplémentaires. Aucun champ système implicite n’est inventé. Le chemin source est affiché en
texte ; la politique `/source` reste inchangée.

## Relations déclarées

La section Relations présente many_to_one (la source porte la FK) et many_to_many
(pivot avec ses clés source/cible et champs supplémentaires), dans l’ordre du
document. Inverse_name est affiché seulement s’il existe. Source et index
relations[n] identifient la déclaration, sans lien /source.

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
