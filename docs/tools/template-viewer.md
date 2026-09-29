# Template Viewer

Template Viewer v1 liste uniquement les fichiers physiques de `mvc/views/` du
projet Forge ouvert. Il expose leur chemin relatif, taille en octets et date de
modification, puis leur contenu brut en lecture seule. Aucun import du projet,
parsing HTML/Jinja, rendu, prévisualisation, édition ou génération n'est effectué.
La coloration est reportée ; aucun JavaScript ni dépendance n'est ajouté.

## Utilisation

Ouvrir un projet puis choisir **Template Viewer**. `/templates` rescane à chaque
GET ; **Voir** ouvre `/templates/view?path=layouts%2Fbase.html`. Le détail relit le
fichier à chaque consultation, même s'il ne figurait pas dans un inventaire tronqué.
Les deux pages gardent la navigation active et `Cache-Control: no-store`.
POST est refusé (405). Sans projet, la liste affiche « Aucun projet ouvert. » et
ne lance aucun Tool ; le détail retourne 409.

Le tableau est trié lexicalement selon les chemins Unicode. Tous les suffixes
sont admis, y compris `.html`, `.xml`, `.jinja` et les noms sans extension. Un fichier
non UTF-8 ou trop gros peut figurer dans l'inventaire mais sa lecture est refusée.
Un `mvc/views/` absent est un inventaire normal vide avec `source_present=False` ;
un dossier vide donne `True`. Un dossier inaccessible produit un diagnostic.

Les dates sont affichées en UTC, à la seconde, sans servir d'identifiant. Les
attributs `data-size` et `data-modified-ns` conservent les valeurs brutes. Le détail
utilise taille et mtime du descripteur de sa lecture courante, jamais d'un ancien
inventaire. Une modification détectée pendant la lecture fait refuser celle-ci.

## API et responsabilités

- `read_templates(root: Path) -> TemplatesResult` valide le projet et inventorie.
- `TemplateViewerTool.run(project_root)` délègue directement à ce Bridge ; la
  liste Web appelle le Tool une fois. Aucun scan au démarrage du registre.
- `TemplateInfo(path, size, modified_ns)` utilise `st_size` et `st_mtime_ns`.
- `TemplateIssue(code, message, path=None)` décrit un refus local ou une troncature.
- `TemplatesResult(templates, issues, source_present, truncated)` utilise des tuples.
- `read_template_source(root, template_path) -> TemplateSource` retourne chemin,
  taille, mtime et texte. Les modèles sont des dataclasses gelées.

La lecture brute réutilise `source_parts` et `read_project_source_details`.
`read_project_source` conserve son API historique retournant une chaîne. Le Web
convertit seulement la date, encode les liens avec `urlencode` et échappe le texte
par Jinja dans `<pre><code>`. Même un `{% if` incomplet reste du texte lisible.

## Confinement et erreurs

Le scan ouvre les dossiers segment par segment avec `open_directory` et
`O_NOFOLLOW`. Fichiers cachés, dossiers cachés, symlinks, FIFO, sockets, devices et
noms sensibles de la politique source sont exclus. Aucun suffixe supplémentaire
n'est utilisé comme barrière de sécurité. Les fichiers ordinaires sont ouverts
sans lecture de contenu pour vérifier leur identité et obtenir leurs métadonnées
(`stat/open/fstat/samestat`). Les dossiers découverts sont aussi vérifiés à l'ouverture.

La source exige UTF-8, accepte le BOM initial et conserve les caractères/newlines.
Traversal, chemin absolu, segments vides/cachés, backslash, deux-points, NUL et noms
sensibles sont refusés. La longueur maximale du chemin **complet relatif**
`mvc/views/<path>` est 4096 caractères. `path` doit avoir une seule valeur non vide ;
les autres paramètres non vides sont refusés. Comme les autres parsers Web Forge,
`Request.params` élimine les valeurs vides : `path=&path=page` fournit une valeur,
`path=&path=` aucune, `path=page&path=page` est refusé. Pas de double décodage URL.

| Situation | Statut du détail |
|---|---:|
| Refus lexical / paramètre absent ou répété | 400 |
| Template absent | 404 |
| Projet disparu, invalide, non dossier ou non résoluble | 409 |
| Source liée, remplacée, inaccessible, trop grosse ou non UTF-8 | 409 |

L'inventaire garde les autres fichiers après un échec local
(`template.unreadable`). Aucune politique de `/source` n'est élargie et ses statuts
historiques ne changent pas. L'état du projet ouvert et la configuration XDG ne
sont pas modifiés par les GET ; aucun cache, fichier `.forge-design` ou stockage.

## Bornes et limites

| Constante | Valeur | Portée |
|---|---:|---|
| `MAX_TEMPLATE_FILES` | 512 | Fichiers retenus |
| `MAX_TEMPLATE_DIRECTORY_ENTRIES` | 4096 | Noms découverts au total, même exclus |
| `MAX_TEMPLATE_SCAN_DEPTH` | 32 | Sous-dossiers sous views (racine à zéro) |
| `MAX_SOURCE_BYTES` | 1 Mio | Octets ouverts en lecture brute |

Un surplus détecté donne `truncated=True` et une seule issue
`template.analysis_truncated`. Une limite exactement remplie sans surplus ne
tronque pas. Un dossier au-delà de la profondeur autorisée suffit à signaler une
troncature, même vide, car il n'est pas parcouru. La découverte consomme au plus
4097 noms, le dernier uniquement pour détecter le dépassement. Au-delà de 4096,
le sous-ensemble dépend de l'ordre du filesystem ; le résultat retenu reste trié.
Le plafond de fichiers porte sur les fichiers vérifiés conservés ; les essais
infructueux restent bornés par le budget de découverte.

Ce n'est pas un instantané atomique : un dossier déjà ouvert peut être renommé ou
son contenu changé. Le contrôle avant/après lecture détecte les changements de
size/mtime/ctime ordinaires, sans constituer un verrou filesystem. Les dates
sortant de la plage Web sont affichées « Date hors plage ». Le support POSIX des
descripteurs et `O_NOFOLLOW` est requis. L'accessibilité est vérifiée structurellement,
sans revendiquer un essai navigateur ou lecteur d'écran.

## Opt-ins

Les templates fournis exclusivement par les loaders d'opt-in ne sont pas inclus.
Aucun loader d'opt-in n'est instancié ou exécuté. Un template local surchargeant un
opt-in apparaît normalement parce qu'il existe dans `mvc/views/`, sans analyse de
cette relation. `mvc/templates/` n'est pas une source canonique Forge actuelle.
