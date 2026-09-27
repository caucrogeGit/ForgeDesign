# Entity Explorer

Ouvrir un projet Forge, puis choisir **Entity Explorer** dans la navigation.
La page `/entities` liste les entités et propose leurs champs dans des blocs
natifs dépliables. Sans projet courant, aucun Tool n’est exécuté.

La source exclusive est `mvc/entities/<snake>/<snake>.json`. Les dossiers directs
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
édition ou écriture. `relations.json` et les dépendances entre entités ne sont pas
lus. Aucun champ système implicite n’est inventé. Le chemin source est affiché en
texte ; la politique `/source` reste inchangée.
