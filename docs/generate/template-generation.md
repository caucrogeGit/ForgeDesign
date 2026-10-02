# Génération de templates simples — FD-GENERATE-001

## Objectif et API

`generate_simple_template(design: DesignFile, contract: ViewContract)` produit
du HTML/Jinja en mémoire. Les exports de `forge_design.generate` comprennent
TemplateGenerationResult(template, issues, complete) et
TemplateGenerationIssue(code, message, location), dataclasses gelées ; issues et
locations sont des tuples. Toute issue implique complete=False.

Aucun chemin projet reçu, fichier lu ou écrit, moteur Jinja exécuté, donnée
fictive injectée ou backend consulté. Le résultat est du code lisible, modifiable
à la main. Diff et écriture contrôlée sont des étapes futures distinctes.

## Mapping et limites fonctionnelles

| Bloc | Sortie |
|---|---|
| page | Enfants uniquement, aucun wrapper |
| section | section |
| container, grid | div |
| card | article |
| title | h2 |
| text | p |

Button, form, field et alert sont omis avec unsupported_block,
ainsi que leur sous-arbre. Les autres branches supportées restent générables. Depuis FD-GENERATE-003, table
et son empty_state sont pris en charge selon la section dédiée ci-dessous.
Depuis FD-GENERATE-002, visible_if sur un bloc supporté produit une directive
if validée contre le contrat ; voir la section Conditions et boucles ci-dessous.
Le comportement historique unsupported_condition de FD-GENERATE-001 est remplacé.

Aucun layout, extends, block, include, formulaire fonctionnel, route,
attribut data-forge-design-* ou style inline n'est inventé.
Les règles d'imbrication Design restent applicables : title se place sous card,
text ne peut pas être enfant direct de page, grid reste une feuille.

## Props et bindings

Props acceptées sur les éléments HTML : tag et class string. Tag est restreint à
div, section, article, header, footer, main, aside, p, span, h1 à h6.
Tag inconnu : fallback par défaut avec invalid_tag. Toute autre prop ou valeur
non string est ignorée avec unsupported_prop. Page n'ayant aucune balise, ses
props sont ignorées avec unsupported_prop.

Les classes restent explicites, sans transformation Tailwind ou CSS synthétique.
Les caractères HTML sont échappés. Les accolades sont encodées en entités HTML
pour empêcher l'ouverture d'expressions, directives ou commentaires Jinja ;
CR/LF sont également encodés pour conserver une ligne par élément textuel.
La valeur HTML décodée conserve exactement la chaîne de classe d'origine.

Title/text avec binding produisent `{{ page_title }}`, sans valeur de preview.
Le validateur existant exige une variable string présente dans le contrat.
Sans binding : contenu vide sans diagnostic. Les noms générables satisfont
`[A-Za-z_][A-Za-z0-9_]*` sur la chaîne entière ; constantes et mots d'expression
Jinja (true/false/none, variantes initiales majuscules, and/or/not/in/is/if/else/for)
sont exclus pour ne pas changer le sens de la référence. Les clés pointées,
tirets, espaces, Unicode ou fragments Jinja donnent unsupported_binding_syntax
et un contenu vide. Aucun accès de chemin ou expression libre.

## Validation et diagnostics

Avant sérialisation, un parcours itératif borne les occurrences et la profondeur,
cycles synthétiques compris. Les modèles sont ensuite copiés par
model_dump(exclude_unset=True) puis model_validate. Les mutations invalides
produisent invalid_design ou invalid_contract, sans template.
Les erreurs attendues de validation/sérialisation sont capturées, sans catch global.

validate_design_nesting est appelé avant toute génération : invalid_nesting avec
les chemins originaux, sortie vide. validate_design_bindings est ensuite appelé ;
les erreurs title/text deviennent invalid_binding, conservent leurs locations et
bloquent toute sortie. Les bindings des blocs reportés ne bloquent pas à eux seuls
les autres branches. Une troncature de validation reste bloquante.

Les codes portent tous le préfixe generate :

- invalid_design, invalid_contract, invalid_nesting, invalid_binding ;
- unsupported_binding_syntax, unsupported_block ;
- invalid_condition, unsupported_condition_syntax ;
- invalid_tag, unsupported_prop ;
- analysis_truncated, output_too_large.

Les issues de validation précèdent le rendu ; les issues de rendu suivent l'ordre
source. Pas de déduplication. Les erreurs de revalidation ont une location vide ;
les autres ciblent le nœud, la propriété ou le binding concerné.

## Lisibilité

Deux espaces par niveau HTML, sans niveau supplémentaire pour page.
Text/title et conteneurs vides sont sur une ligne ; conteneurs avec enfants ont
une ouverture et une fermeture sur leurs lignes propres. Tout résultat non vide
finit par un unique LF. Une page vide donne template="", issues=(), complete=True.

```jinja
<section class="max-w-5xl mx-auto py-8">
  <h1 class="text-3xl font-bold">{{ page_title }}</h1>
</section>
```

## Bornes, pureté et limites

MAX_DESIGN_NODES=4096 (racine comprise), MAX_DESIGN_DEPTH=128 (racine à zéro),
MAX_DESIGN_ISSUES=512 (marqueur terminal compris). Le précontrôle parcourt aussi
les branches qui seront omises. Les références partagées comptent par occurrence.
En cas de surplus, analysis_truncated et aucune sortie ; le dernier diagnostic
est remplacé par le marqueur si nécessaire.

MAX_GENERATED_TEMPLATE_CHARS=1_000_000 compte indentation, échappement et LF.
Un dépassement retourne template="" avec output_too_large, sans tronquer une
balise ou expression. Ce n'est pas une limite de mémoire totale : objets d'entrée,
copies Pydantic et chaînes temporaires existent indépendamment du budget de sortie.

Aucune mutation des entrées, hasard, accès fichier, réseau, subprocess, Forge
runtime ou Web. Aucune nouvelle dépendance ni Tool. Preview et formats
Design/Contract inchangés. Jinja est parsé seulement dans les tests, jamais rendu.
Le consommateur futur devra fournir son environnement Jinja et sa politique
d'auto-échappement ; ce ticket génère uniquement le texte du template.
Des choix de tags incompatibles peuvent rester sémantiquement invalides en HTML :
la whitelist protège la syntaxe, elle ne remplace pas une validation navigateur.

FD-GENERATE-002 ajoute les conditions et la primitive de boucle ci-dessous.
FD-GENERATE-003 ajoute les tables et états vides ci-dessous.

## Conditions et boucles — FD-GENERATE-002

### Conditions contractuelles

La source unique est visible_if. Après les validations historiques, le générateur
appelle validate_conditional_bindings : la clé exacte doit exister dans context
avec type=boolean. Variable inconnue ou mauvais type : generate.invalid_condition,
location du validateur conservée, template vide et complete=False. Aucun doublon
design.condition.* n'est exposé. Une troncature devient analysis_truncated.
Cette validation porte sur l'arbre entier, y compris les conditions des blocs
reportés ; une condition valide ne rend pas ces blocs supportés.

Même une clé contractuelle doit respecter l'identifiant ASCII simple générable.
Une syntaxe refusée (can-create, permission.create, not flag, etc.) produit
generate.unsupported_condition_syntax et omet le sous-arbre concerné.
La regex et les exclusions Jinja sont mutualisées avec les bindings texte.
Ni expression libre, conversion de permission, négation ni truthiness calculée
par Forge Design. Le backend devra fournir les booléens déclarés.

```jinja
{% if can_view %}
  <section>
    {% if can_create %}
      <p class="text-xl">{{ page_title }}</p>
    {% endif %}
  </section>
{% endif %}
```

Un if entoure tout le bloc et ajoute deux espaces à son contenu. Page ne produit
toujours aucune balise : sa condition entoure tous ses enfants. Les sept types
supportés peuvent porter une condition ; les conditions imbriquées se composent.
La sortie sans visible_if reste identique, y compris classes, indentation et LF.
Le budget HTML/Jinja existant compte également les directives et leur indentation.

### Primitive de boucle interne

Le module interne `forge_design.generate.control_flow` fournit :

```python
render_jinja_loop(
    *,
    collection: str,
    item: str,
    body: tuple[str, ...],
    indent: int = 0,
) -> tuple[str, ...]
```

Ces fonctions ne sont pas réexportées par l'API publique du package. Collection
et item sont deux identifiants simples explicitement fournis. Aucun accès au
contrat, singularisation, conversion d'Entity ou heuristique de nommage.

```jinja
{% for contact in contacts %}
  <p>{{ contact.nom }}</p>
{% endfor %}
```

Body contient des lignes de code générées de confiance, sans LF/CR, avec leur
indentation relative. La primitive ajoute un niveau au corps et conserve son
texte sans ré-échappement. Indent est un nombre entier de niveaux, positif ou nul,
hors bool. Corps vide accepté. Les violations sont des ValueError de programmation.
Dotted collections, filtres, appels et slices sont refusés. Le nom local loop
est également refusé car réservé par Jinja pour le contexte de boucle.

Le futur appelant reste responsable du code du corps, du choix du nom local,
des collisions de portée et du budget de sortie ; cette primitive interne n'est
ni un parseur ni un assainisseur. Aucun moteur Jinja exécuté.

### Périmètre conservé

Aucun bloc Loop/For/Condition ajouté au Design. FD-GENERATE-002 ne branchait pas
encore cette primitive sur table ; FD-GENERATE-003 l'utilise désormais comme décrit
ci-dessous. Les modèles, revalidation, nesting, bindings simples, limites,
Preview, exports publics et packaging sont inchangés.

## Tables et états vides — FD-GENERATE-003

L'API publique reste generate_simple_template. Le module interne generate/tables.py
consomme la projection de validate_table_bindings, appelé une fois après les
validations existantes. Statut de collection, champs validés, ordre des colonnes et
has_empty_state viennent de cette projection ; aucun accès Forge ou nouvelle
résolution du contrat.

### Collection et colonnes

Table nécessite un binding de variable list. Sans binding : table_missing_binding.
Variable inconnue, non list ou fields absents alors que des colonnes sont présentes :
invalid_table_binding. Colonne non déclarée : invalid_table_column.
Les chemins de colonnes restent root/.../columns/index/binding. Une table
incorrecte est entièrement omise, ses autres branches sœurs restent générables.
Une troncature du validateur annule toute sortie avec analysis_truncated.

Collection et champs doivent être des identifiants Jinja simples selon la règle
commune. Une collection non générable produit unsupported_binding_syntax ; un champ
non générable produit unsupported_field_syntax. Pas de bracket access, expression
ou filtre automatique. Une colonne inconnue n'ajoute pas aussi une erreur de syntaxe.

```jinja
<table class="w-full">
  <thead>
    <tr>
      <th>Nom</th>
      <th>Email</th>
    </tr>
  </thead>
  <tbody>
    {% for item in contacts %}
      <tr>
        <td>{{ item.nom }}</td>
        <td>{{ item.email }}</td>
      </tr>
    {% endfor %}
  </tbody>
</table>
```

La variable locale est toujours item, sans singularisation ni dérivation d'entity.
La primitive render_jinja_loop existante produit for/endfor et leur indentation.
Les colonnes conservent leur ordre ; zéro colonne est permis, avec thead/tr vide
et tr vide dans la boucle. Une liste sans fields est donc générable sans colonnes.
Aucun filtre, safe ou formatage de champ n'est ajouté. Le runtime Jinja et ses
règles d'accès aux attributs restent ceux du consommateur du template.

### État vide et visibilité

Sans enfant empty_state : table et boucle seules. Avec un unique état vide :

```jinja
{% if contacts %}
  <table>
    ...
  </table>
{% else %}
  <div class="py-8 text-center">Aucune donnée</div>
{% endif %}
```

has_empty_state de la projection active cette branche. Le texte « Aucune donnée »
est une convention temporaire v0.1, faute de propriété de contenu éditable.
Plusieurs états vides : multiple_empty_states, table omise. Visible_if sur cet
enfant, même inconnu au contrat : unsupported_empty_state_condition et table omise.
Le validateur conditionnel reste appelé ; ses erreurs sur empty_state sont traitées
par cette règle dédiée, sans diagnostic conditionnel dupliqué.

Visible_if sur table utilise l'enveloppe conditionnelle existante, à l'extérieur
du if de collection. Le premier if vise un booléen contractuel ; le second teste
la présence d'éléments dans la collection. Les niveaux logiques ajoutent deux espaces.
Un état vide hors table est interdit par nesting et provoque invalid_nesting avant
rendu ; le moteur interne ne le rend jamais comme un bloc autonome supporté.

### Props, sécurité et budgets

Table conserve la balise table, empty_state la balise div. Seule class string est
acceptée ; tag et autres props sont ignorées avec unsupported_prop.
Labels et classes partagent l'échappement existant : HTML, accolades Jinja, CR/LF.
Le texte HTML décodé est conservé, sans création de script, include ou expression.

MAX_TABLE_COLUMNS est appliqué par le validateur existant. Les budgets Design et
MAX_GENERATED_TEMPLATE_CHARS restent inchangés et couvrent toutes les nouvelles
lignes, directives et indentations. Le corps temporaire de boucle est contrôlé
avant accumulation ; un dépassement annule tout le template avec output_too_large.
La limite de sortie ne constitue pas une limite mémoire globale des entrées/copies.

Les revalidations Pydantic, nesting et bindings simples sont conservés. Aucune
mutation, I/O, exécution Jinja, API publique supplémentaire ou dépendance.
Button, form, field et alert restent reportés. Aucune action CRUD de ligne n'est
inventée : le modèle ne possède ni row_actions ni table_actions, et table n'accepte
que des enfants empty_state. Pas de pagination, tri, filtres, layout ou écriture.
Le ticket suivant est FD-GENERATE-004, diff avant écriture.

## Diff avant écriture — FD-GENERATE-004

`build_template_diff(*, target, current, generated, origin)` compare deux chaînes
déjà disponibles en mémoire. Aucun appel au générateur, lecteur projet ou service
d'écriture ; aucun couplage à DesignFile, ViewContract ou TemplateGenerationResult.

L'API est exportée depuis forge_design.generate avec les dataclasses gelées
TemplateDiffIssue(code, message) et TemplateDiffResult :

- target et origin : métadonnées conservées exactement ;
- current et generated : chaînes originales, sans normalisation ;
- unified_diff et changed ;
- added_lines, removed_lines, modified_lines ;
- issues (tuple) et complete.

Target et origin doivent être des chaînes non vides, sinon ValueError.
Aucun strip ni origine par défaut. Target est seulement descriptif :
../../etc/passwd n'est ni ouvert ni résolu, et n'est pas déclaré sûr pour une
future écriture. La future couche d'écriture devra appliquer sa propre politique.

### Unified diff et fins de ligne

difflib.unified_diff utilise les lignes avec séparateurs conservés, un contexte
de trois lignes, les en-têtes `--- target` et `+++ target.generated`, sans dates.
Origin reste dans le résultat, sans être injectée dans le diff.
Les en-têtes ont un LF ; les lignes de contenu gardent leurs séparateurs, CRLF
compris. Une ligne produite sans LF reçoit un LF de présentation puis le marqueur
textuel `\ No newline at end of file`, pour éviter de coller deux lignes du diff.
Les contenus originaux restent disponibles exactement, quelle que soit la
présentation des fins de ligne.

Une égalité exacte donne changed=False, diff vide, compteurs zéro et complete=True.
Une entrée current vide représente un ajout ; generated vide une suppression.
Un changement uniquement de LF final ou CRLF/LF donne changed=True et un diff,
même si les compteurs de contenu restent à zéro.

### Métriques sémantiques

Les métriques sont indépendantes du texte du diff. SequenceMatcher compare
`splitlines()` sans séparateurs, avec son comportement standard (autojunk activé).

| Opcode | Comptage |
|---|---|
| insert | Toutes les nouvelles lignes sont ajoutées |
| delete | Toutes les anciennes lignes sont supprimées |
| replace | min(anciennes, nouvelles) modifiées ; excédent ajouté ou supprimé |
| equal | Aucun compteur |

Un remplacement 1→1 donne 1 modifiée, 0 ajoutée, 0 supprimée ; 1→3 donne 1 modifiée
et 2 ajoutées. Des insertions et suppressions indépendantes ne deviennent pas
artificiellement des modifications. Les lignes de contenu commençant par --- ou
+++ n'interfèrent pas avec ces métriques.

### Taille et présentation

MAX_TEMPLATE_DIFF_CHARS=1_000_000 limite les caractères du unified diff, en-têtes,
séparateurs et marqueurs compris. La limite exacte est acceptée. En cas de surplus :
unified_diff="", complete=False et une issue diff.output_too_large. Les compteurs,
changed, métadonnées et contenus sont conservés. Pas de diff partiel silencieux.

Le budget ne limite ni les entrées, ni les listes de lignes, ni le temps/mémoire
de SequenceMatcher. Des contenus répétitifs peuvent rendre la comparaison coûteuse ;
les métriques suivent son alignement déterministe et ne constituent pas une mesure
sémantique du code. Les séparateurs reconnus sont ceux de str.splitlines ; la sortie
sert à la revue textuelle, pas à appliquer un patch universel à tous les encodages.

Aucun HTML échappé, template exécuté, ANSI ajouté ou horodatage généré.
HTML/Jinja/ANSI présents dans les entrées restent du texte littéral. Les métadonnées
sont également conservées sans assainissement de présentation ; un futur affichage
Web ou terminal devra traiter ces chaînes selon son contexte.
Aucune UI, confirmation, sauvegarde, détection de conflit ou écriture dans ce service.

## Journal des écritures — FD-GENERATE-005

`append_generation_history(project_root: Path, *, action: HistoryAction,
file: str, timestamp: datetime | None = None)` ajoute un événement dans
`<project_root>/.forge-design/history.jsonl` et retourne une
GenerationHistoryEvent gelée : timestamp, action, file. Ces types et la fonction
sont exportés depuis forge_design.generate. HistoryAction accepte seulement
generate_template, y compris au runtime.

**L'appelant doit appeler ce service après une écriture autorisée et réussie.**
Le journal ne prouve pas lui-même cette écriture, n'autorise rien et ne crée aucun
template. Génération et diff n'appellent pas automatiquement le journal. Un diff
refusé ou seulement consulté n'est pas un événement d'écriture.

### Format minimal

```json
{"version":1,"timestamp":"2026-09-30T09:15:00Z","action":"generate_template","file":"mvc/views/élèves/liste.html"}
```

Un objet compact dans cet ordre, UTF-8 sans BOM, ensure_ascii=False, un LF final.
`version` (entier, `HISTORY_FORMAT_VERSION = 1`, FD-STORAGE-002) ouvre chaque ligne
conformément au [contrat de stockage](../storage/storage-contract.md) ; il n'est
pas fourni par l'appelant ni porté par GenerationHistoryEvent.
Aucun contenu de fichier, token, cookie, mot de passe ou environnement ajouté.
Le champ file est une métadonnée fournie par l'appelant ; aucune extraction
automatique de contenu ou analyse de secrets dans les noms n'est réalisée.

Timestamp par défaut : heure réelle courante UTC. L'appelant peut injecter un
datetime aware, converti en UTC avec suffixe Z ; microsecondes conservées si
présentes. Datetime naïf refusé par ValueError. Pas d'horloge dans la sérialisation
interne pure ; celle-ci reçoit l'événement préparé.

File doit être une chaîne relative non vide à séparateurs /. Segments vides,
. et .. interdits. Antislash, deux-points, contrôles ASCII et DEL refusés :
chemins absolus POSIX, Windows, UNC et traversals ne sont pas normalisés puis acceptés.
Le fichier tracé n'est ni ouvert ni vérifié : cette politique valide la métadonnée,
pas l'autorisation d'écrire un futur template.

### Append sécurisé

La racine doit être un dossier réel. Le helper existant open_directory ouvre
chaque segment sans suivre les symlinks ; les opérations suivantes utilisent
dir_fd. Aucun resolve qui accepterait silencieusement une racine liée.

.forge-design est créé si absent avec mode 0700 ; history.jsonl avec mode 0600
(sous réserve d'un umask plus restrictif). Les modes existants ne sont pas modifiés.
Le dossier et le fichier sont contrôlés par comparaison d'identité stat/fstat.
Journal régulier obligatoire avec st_nlink==1. Symlinks, hardlinks, dossiers,
FIFO, sockets et devices sont refusés.

Création exclusive si absent ; sinon ouverture du fichier existant sans
troncature. Flags O_WRONLY/O_APPEND/O_NOFOLLOW/O_NONBLOCK et O_CLOEXEC lorsque
disponible. O_NONBLOCK évite l'attente sur une FIFO remplacée entre les contrôles.
Les descripteurs sont fermés aussi en cas d'échec.

L'événement est entièrement validé, sérialisé et borné avant toute I/O.
Un seul os.write pour la ligne normale ; aucun seek(end), aucune boucle de
réécriture partielle. O_APPEND place chaque write à la fin du fichier.
Après succès : fsync du fichier ; fsync du dossier si le journal vient d'être
créé, puis fsync du parent projet si .forge-design vient d'être créé.
Retour de l'événement seulement après toutes ces opérations.

### Limites et erreurs

MAX_HISTORY_EVENT_BYTES=16_384 borne les octets UTF-8, LF compris.
Limite exacte acceptée ; surplus ValueError avant I/O, journal inchangé.
Les erreurs de permission, ouverture, écriture ou synchronisation se propagent.
Une écriture courte lève OSError sans tentative supplémentaire qui pourrait
entrelacer la fin de ligne avec une autre entrée concurrente.

Un échec peut avoir laissé un dossier/fichier vide, un fragment de ligne ou une
ligne déjà ajoutée mais dont la durabilité n'est pas confirmée. Aucun rollback,
troncature ou retry automatique : l'appelant ne doit pas assimiler l'exception
à « rien écrit », ni rejouer aveuglément l'événement.

Cette stratégie suppose un filesystem POSIX avec les primitives nécessaires.
O_APPEND ne promet pas les mêmes garanties sur tous les systèmes de fichiers
réseau. Les contrôles d'identité réduisent les races à l'ouverture, sans garantir
un instantané global face à un processus hostile : un dossier ouvert peut être
renommé, un hardlink créé après le dernier contrôle, le journal supprimé ensuite.
Le journal préexistant est supposé JSONL valide et terminé par LF ; il n'est pas
relu, réparé ou compacté. Aucune rotation ni borne de taille totale ici.

FD-GENERATE-005 fournit seulement History append. La future couche SAFEWRITE
traitera écriture contrôlée, conflits et modifications externes. Ce journal
minimal ne contient ni hash, révision, inode ou mtime.

## Boutons HTMX — FD-INTERACT-001

Module interne `forge_design/generate/buttons.py` (`prepare_button`,
`render_button`), orchestré par `simple.py` comme les tables : le bouton est
**entièrement préparé avant émission**, condition comprise.

```text
Button Design (binding + props) + ViewAction du contrat
   → interaction contrôlée
   → <button type="button" … hx-get|hx-post="…">Action</button>
```

### Représentation

Aucun changement de schéma ni de modèle : le bouton est un `DesignNode`
`button` dont `binding` désigne `contract.actions[binding]` (`ViewAction`
existant : `method`, `path`, `csrf`). Les attributs HTMX sont des props
explicites (`"hx-target": "#main"`). La résolution et la vérification de
l'action restent celles de `validate_design_bindings` : une action inconnue,
ou un binding vers une variable de contexte, donne `generate.invalid_binding`.
C'est **bloquant** pour tout le template, comme pour `title` et `text`.

### Méthodes et URL

| `ViewAction.method` | Attribut |
|---|---|
| `GET` | `hx-get` |
| `POST` | `hx-post` |
| autre (`PUT`, `PATCH`, `DELETE`, `HEAD`…) | `generate.unsupported_action_method`, bouton omis |

L'URL vient **exclusivement** de `ViewAction.path`. Elle n'est jamais déduite
du nom de l'action, de l'entité ou du bouton, et elle n'est pas vérifiée
contre le routeur Forge : aucun import ni exécution du projet cible.

### Sortie

Une ligne, avec des attributs dans un **ordre fixe**, indépendant de l'ordre
des props : `type="button"` (toujours, pour éviter une soumission implicite),
`class`, `hx-get` ou `hx-post`, `hx-target`, `hx-swap`, `hx-confirm`. Le
libellé est `Action`, convention de la preview, tant que le Design n'a pas de
représentation explicite du libellé.

```html
<button type="button" class="px-4 py-2" hx-get="/contacts/create" hx-target="#content" hx-swap="outerHTML">Action</button>
```

### Props

Liste blanche fermée : `class`, `hx-target`, `hx-swap`, `hx-confirm`. Les
valeurs `hx-*` sont **opaques** (`closest tr`, `beforeend swap:1s`…), sans
analyse de la syntaxe HTMX. Elles doivent être des chaînes non vides, sinon
`generate.invalid_htmx_prop` et le bouton est omis. Toute autre clé (`tag`,
`onclick`, `style`, `hx-trigger`, `hx-get`, `data-*`…) donne
`generate.unsupported_prop` et **n'est pas émise** : les props ne deviennent
jamais des attributs arbitraires. Une `class` non textuelle suit la politique
existante (`unsupported_prop`, ignorée).

### Échappement

`class`, le chemin et les valeurs `hx-*` passent par l'échappement commun du
générateur : `html.escape(quote=True)`, neutralisation de `{` et `}`, CR et LF
encodés. Une valeur `"><script>…` reste dans l'attribut, et `{{ … }}`,
`{% … %}` ou `{# … #}` ne deviennent jamais du Jinja. Tous les caractères
participent au budget `MAX_GENERATED_TEMPLATE_CHARS` : un dépassement donne
`generate.output_too_large`, sans template partiel.

### Conditions

`visible_if` réutilise l'enveloppe `{% if … %}` existante. Un bouton omis ne
laisse pas de condition vide. Une condition invalide garde le diagnostic
historique (`generate.invalid_condition`).

### CSRF

Aucune stratégie CSRF n'est inventée : aucun jeton, champ ni en-tête n'est
généré.
- `GET` : généré quel que soit `csrf`.
- `POST` sans `csrf`, ou avec `csrf: false` : généré (`hx-post`), **sans
  protection CSRF fournie par Forge Design** ; l'application cible en reste
  responsable.
- `POST` avec `csrf: true` : `generate.unsupported_csrf`, bouton omis. Émettre
  seulement `hx-post` ferait perdre une exigence explicite du contrat, alors
  que Forge Design ne connaît ni jeton, ni session, ni nom de champ.

### Preview et runtime

La preview reste **inerte** : `render_preview` n'émet ni `hx-get`/`hx-post`
ni chemin, et les props `hx-*` y produisent `preview.unsupported_prop`. La
preview ne simule aucune interaction. Forge Design ne génère ni `<script>` ni
CDN, et ne vérifie pas qu'HTMX est installé : le chargement d'HTMX appartient
à l'application Forge cible. Pas de dépendance npm.

## Formulaires HTML/HTMX — FD-INTERACT-003

Module interne `forge_design/generate/forms.py` (`prepare_form`,
`render_form_open`/`render_form_close`, `prepare_field`, `render_field`),
orchestré par `simple.py`. La politique d'interaction commune aux boutons et
aux formulaires (verbes, CSRF, props HTMX) est factorisée dans
`generate/actions.py` (`prepare_interaction`) : `buttons.py` l'utilise aussi,
sans changement de sortie.

```text
Form Design ──────────────► ViewAction
    │
    ├─ FieldDefinition
    └─ children
            ↓
     generate/forms.py
            ↓
       HTML + HTMX
```

### Validation avant émission

`validate_form_fields(design)` est **réutilisé** tel quel, avant toute
émission, et bloque la génération entière (aucun template) :

| Diagnostic design | Génération |
|---|---|
| `design.field.missing_definition`, `design.field.unsupported_definition` | `generate.invalid_field` |
| `design.field.duplicate_name` | `generate.duplicate_field_name` |
| `design.field.analysis_truncated` | `generate.analysis_truncated` |

`form` rejoint les bindings bloquants : une action inconnue donne
`generate.invalid_binding` et aucun template. Chaque formulaire est
**entièrement préparé** avant l'émission de sa balise ouvrante.

### Formulaire

`form.binding` désigne une `ViewAction`. La balise porte à la fois le HTML
natif (`action`, `method`, pour une dégradation sans HTMX) et l'attribut
HTMX, avec la **même URL**, issue de `ViewAction.path` :

```html
<form action="/contacts" method="post" class="space-y-4" hx-post="/contacts" hx-target="#content">
  <label>Adresse e-mail<input type="email" name="email" required></label>
</form>
```

- `GET` donne `method="get" hx-get` ; `POST` donne `method="post" hx-post`.
  Les autres verbes donnent `generate.unsupported_action_method`.
- Ordre fixe : `action`, `method`, `class`, `hx-get`/`hx-post`, `hx-target`,
  `hx-swap`, `hx-confirm`.
- Props : `class` et `hx-target`, `hx-swap`, `hx-confirm` (chaînes non vides,
  sinon `generate.invalid_htmx_prop`). Toute autre prop (`style`, `onclick`,
  `hx-trigger`, `hx-vals`, `hx-headers`, `tag`, `id`…) donne
  `generate.unsupported_prop` et n'est pas émise.
- `form` sans binding : `generate.form_missing_action`. Le formulaire **et
  son sous-arbre** sont omis, et ses champs ne sont jamais rendus hors d'un
  `<form>`. Il en va de même pour une méthode non supportée, `csrf: true` en
  `POST` ou une prop HTMX invalide.
- Un formulaire sans enfant donne `<form …></form>`.

### Champs

Chaque champ vient exclusivement de `FieldDefinition` :

- `<input type="…" name="…">` : `type` parmi les six `FieldInputType`
  (liste fermée revalidée), `name` opaque et échappé (`contact.email`,
  `items[0].name`) ;
- `label` présent : `<label>Libellé<input …></label>`. Le libellé englobant
  évite d'inventer un `id`/`for`. Libellé absent : `<input …>` seul, sans
  `<label>` vide ;
- `required: true` donne l'attribut booléen `required` ; `false` ou absent :
  rien (la distinction reste dans le Design) ;
- props : seule `class` (chaîne) est émise. Les autres (`placeholder`, `min`,
  `autocomplete`…) ou une `class` non textuelle donnent
  `generate.unsupported_prop`, ignorée sans bloquer le champ ;
- aucun `id`, `for`, `value`, `placeholder`, `min`/`max`/`step` ni
  `autocomplete` n'est inventé ; une checkbox n'a ni `value` ni champ caché
  compagnon.

### Enfants, boutons et soumission

`field` et `button` sont générés sous un `form`, et `alert` reste
`generate.unsupported_block`. Un `button` enfant reste `type="button"` avec
**sa propre** action (FD-INTERACT-001). **Aucun bouton de soumission n'est
ajouté ni déduit** : un formulaire généré peut donc ne pas avoir de bouton
d'envoi. La représentation d'un vrai `submit` sera décidée séparément.

### Conditions, échappement et budget

`visible_if` sur un `form` ou un `field` réutilise l'enveloppe `{% if %}` de
`simple.py`, et un bloc omis ne laisse pas de condition vide. Le chemin, les
classes, les valeurs HTMX, les noms et les libellés passent par l'échappement
commun (HTML, `{`/`}`, CR/LF) et par le budget unique
`MAX_GENERATED_TEMPLATE_CHARS`.

### CSRF et runtime

`GET` est généré quel que soit `csrf` ; `POST` sans `csrf` ou avec
`csrf: false` est généré **sans protection fournie par Forge Design** ;
`POST` avec `csrf: true` donne `generate.unsupported_csrf` et le formulaire
est omis. Il n'y a ni jeton, ni script, ni CDN, ni runtime HTMX. La preview
est inchangée et inerte (pas d'`<input>`, d'`action` ni de `hx-*`).

## Boutons submit — FD-INTERACT-005

Le générateur distingue désormais deux sortes de boutons :

```text
Button
├─ binding → action HTMX autonome          (FD-INTERACT-001, inchangé)
└─ submit  → soumission HTML du form parent (FD-INTERACT-005)
```

| Bouton | Sortie |
|---|---|
| `binding` | `<button type="button" [class] hx-get\|hx-post="…" [hx-*]>Action</button>`, sans changement |
| `submit` | `<button type="submit" [class="…"]>Libellé</button>` |
| ni l'un ni l'autre | omis, `generate.button_missing_action` (inchangé) |

```html
<form action="/contacts" method="post" hx-post="/contacts">
  <input type="email" name="email">
  <button type="submit" class="px-4 py-2">Enregistrer</button>
</form>
```

### Validation

`validate_submit_buttons(design)` est **réutilisé** dans le pipeline, après
`validate_form_fields` et avant les tables : nesting, bindings, conditions,
champs, submits, tables, puis génération. Toute erreur (`submit` hors
`button`, `binding` et `submit` ensemble, submit qui n'est pas enfant direct
d'un `form`) donne `generate.invalid_submit` et **bloque** tout le template,
car la sémantique du bouton serait ambiguë. Une troncature donne
`generate.analysis_truncated`. Les diagnostics gardent l'ordre préfixe du
validateur. Un submit n'ayant pas de binding, `validate_design_bindings` ne
signale rien pour lui ; une action autonome inconnue reste
`generate.invalid_binding`.

### Submit

- `type="submit"` explicite. Le libellé vient **exclusivement** de
  `submit.label`, échappé (HTML, `{`/`}`, CR/LF), jamais remplacé par
  `Action` ni par un libellé inventé.
- Ordre des attributs : `type`, puis `class` (chaîne).
- **Aucune action propre** : ni `hx-get`/`hx-post`, ni `action`,
  `formaction`, `formmethod`, `name` ou `value`. Le `<form>` parent porte
  l'interaction ; le submit le soumet nativement. Le générateur ne relit pas
  le plan du formulaire : la position est garantie par le validateur.
- `hx-target`, `hx-swap`, `hx-confirm`, `tag`, `onclick` ou toute autre prop
  donnent `generate.unsupported_prop` et ne sont **pas émis** : un `hx-*` sur
  le submit créerait une seconde action implicite. Le bouton reste généré,
  et une `class` non textuelle est signalée puis ignorée.
- `visible_if` réutilise l'enveloppe de `simple.py`. Plusieurs submits sont
  générés dans l'ordre du Design. Un formulaire omis n'est pas parcouru :
  son submit n'apparaît jamais seul.
- Le libellé et la classe consomment le budget
  `MAX_GENERATED_TEMPLATE_CHARS`.

### Preview

La preview reste **structurelle** et inchangée : un submit y apparaît comme
un bouton générique (`type="button"`, sans libellé), alors que le template
généré porte `type="submit"` et le libellé.
