# Format .design.json — v0.1

Le `.design.json` est la source graphique structurée et éditable de Forge Design.
Il décrit une composition lisible manuellement, sans devenir la source unique de
vérité d'un projet Forge. **Sa suppression ne doit jamais empêcher Forge d'utiliser
le template `.html` existant.** Le runtime Forge ne doit pas en dépendre.

| Fichier | Responsabilité |
|---|---|
| .view.json | Ce que la page peut utiliser : données disponibles |
| .design.json | Comment la page est composée : source éditable Forge Design |
| .html | Template final utilisable par Forge |

## Source normative et emplacement

Le [schéma produit](../../forge_design/design/design.schema.json) est l'unique
source normative, JSON Schema Draft 2020-12. Il est distribué dans
`forge_design.design/design.schema.json`, sans `$id` public fictif.
Convention physique : `mvc/views/<vue>.design.json`, par exemple
`mvc/views/contacts/list.design.json`, dans l'espace des vues du projet.
Aucune liaison réelle au template voisin n'est déduite ni effectuée ici.

## Racine stricte

| Propriété obligatoire | Contrat |
|---|---|
| version | Chaîne constante `"0.1"`, jamais nombre 0.1 |
| view | Identité logique, chaîne de 1 à 256 caractères, sans regex métier |
| source_contract | Référence relative à mvc/views, suffixe .view.json |
| root | Unique PageRoot, type page et children obligatoire |

Toutes les autres propriétés racine sont interdites, notamment template, roots,
metadata, editor, hash et generated_at. Les limites de chaînes comptent les
caractères, pas les octets. Aucun trim ou normalisation Unicode implicite.

`source_contract` est une chaîne non vide de 4096 caractères au plus, telle que
`contacts/list.view.json`, pas `mvc/views/contacts/list.view.json`.
Le motif de segments interdit slash initial, backslash, deux-points, segments vides
et CR/LF ; les exclusions légères refusent les segments `.`/`..`, le préfixe
mvc/views/ et un nom `.view.json` sans stem. Les espaces et Unicode sont permis.
Les motifs ne constituent pas une autorisation d'ouverture : noms sensibles,
liens, existence et confinement seront contrôlés par le lecteur FD-DESIGN-004.
Aucune copie de toute la politique source_parts dans le schéma.

## Nœuds

`DesignNode` est un objet strict. Seul `type` est obligatoire pour un descendant.
Vocabulaire exact : page, section, container, grid, card, title, text, button,
table, form, field, alert, empty_state.

`PageRoot` réutilise DesignNode via allOf et impose type=page ainsi que children.
Sa strictesse est héritée de DesignNode : aucune duplication de propriétés.
Dans cette première définition structurelle, un descendant page reste admis ;
FD-DESIGN-003 décidera les règles d'imbrication. Aucune règle Form→Field ou
Button→aucun enfant n'est anticipée.

| Champ facultatif du nœud | Déclaration |
|---|---|
| binding | Chaîne non vide, référence déclarative |
| props | Objet à clés non vides, valeurs scalaires simples |
| columns | Tableau de TableColumn |
| children | Tableau récursif de DesignNode |

`children` et `columns` peuvent être vides. Une feuille n'a pas à déclarer children.
Aucune profondeur métier ni taille fichier n'est définie par ce schéma ; les futurs
modèles/lecteurs devront borner leur traitement. Aucun ID de bloc, action ou content
inventé dans cette version.

## Props, bindings et colonnes

PropValue autorise seulement string, boolean, integer et number (integer est un
sous-ensemble de number en JSON Schema). Absence représentée par omission : aucun
null, objet ou tableau imbriqué dans props. Les chaînes vides sont permises.
`class` et `tag` sont des chaînes explicites, pas un objet Tailwind ou style parallèle.
Aucun contrôle des propriétés propre à chaque type de bloc dans ce ticket.

Un binding comme `page_title` ou `contacts` nomme une donnée déclarative ; il ne
contient pas de Jinja à exécuter et ne déclenche aucune évaluation. Le schéma exige
seulement une chaîne non vide, sans parser son contenu ni vérifier son existence.
Ne pas écrire `{{ page_title }}` ou une expression métier. Les propriétés
visible_if/if/unless/condition sont hors du format ; validation des bindings en
phase FD-BINDING-001.

TableColumn est strict : label et binding sont des chaînes non vides obligatoires.
Columns reste facultatif sur DesignNode, sans condition exigeant type=table.
Les futurs modèles/règles pourront affiner les propriétés, sans les anticiper ici.

## Exemples officiels

Les fixtures appartiennent uniquement au dépôt Forge Design ; aucun fichier n'est
créé dans un projet cible. Ordre conceptuel recommandé : version, view,
source_contract, root ; puis type, binding, props, columns, children. L'ordre des
clés JSON n'a pas de signification fonctionnelle.

[Minimal](../../tests/fixtures/design/minimal.design.json) :

```json
{
  "version": "0.1",
  "view": "home/index",
  "source_contract": "home/index.view.json",
  "root": {
    "type": "page",
    "children": []
  }
}
```

[Contacts](../../tests/fixtures/design/contacts-list.design.json) :

```json
{
  "version": "0.1",
  "view": "contacts/list",
  "source_contract": "contacts/list.view.json",
  "root": {
    "type": "page",
    "children": [
      {
        "type": "section",
        "props": {
          "tag": "header",
          "class": "max-w-5xl mx-auto py-8"
        },
        "children": [
          {
            "type": "text",
            "binding": "page_title",
            "props": {
              "tag": "h1",
              "class": "text-3xl font-bold"
            }
          }
        ]
      },
      {
        "type": "table",
        "binding": "contacts",
        "props": {
          "class": "w-full border border-slate-200"
        },
        "columns": [
          {
            "label": "Nom",
            "binding": "nom"
          },
          {
            "label": "Email",
            "binding": "email"
          },
          {
            "label": "Téléphone",
            "binding": "telephone"
          }
        ]
      }
    ]
  }
}
```

## Données interdites et limites

Le document ne doit contenir ni secret/password/token/credential/session/API key,
ni données backend réelles, résultats SQL ou utilisateur courant. Aucun état runtime
(modal_open, selected_tab, csrf_token, flash_message), ni état opaque d'éditeur
(zoom, viewport, selection, drag_state, undo_stack, editor_cache).
Ces interdictions sont architecturales : aucune détection de secret ou de code dans
les chaînes libres n'est prétendue. Les clés non prévues sont refusées aux niveaux
racine/nœud/colonne, mais props ne filtre pas sémantiquement tous les noms possibles.
Aucune logique métier, condition exécutable, génération ou dépendance runtime Forge.

## Responsabilités futures

```text
ViewContract + DesignFile
            ↓
validation des bindings
            ↓
génération du template
            ↓
diff → écriture contrôlée
```

FD-DESIGN-002 : modèles Pydantic de blocs ; FD-DESIGN-003 : imbrication ;
FD-DESIGN-004 : lecture/écriture sécurisée ; FD-BINDING-001 : bindings.
FD-DESIGN-001 apporte seulement le schéma packagé, les exemples et les tests de
ses déclarations. Aucun validateur Python ni moteur jsonschema. Les assertions
structurelles et tests ciblés de motifs ne prouvent pas une validation complète
d'instances. Aucun scan projet, UI, drag-and-drop, Tool ou helper runtime.
Les contrats et Template Viewer restent inchangés : ce dernier peut afficher les
.design.json comme fichiers génériques ; la liaison contractuelle les exclut localement.
