# Rapport — FD-UI-001

## Ticket et objectif

Servir une première page HTML Forge Design sur `GET /`, sans connecter de projet ou afficher de Tool.
Le shell reste une ressource statique sans infrastructure Web supplémentaire.

## État Git initial

- Branche : `main`, synchronisée avec `origin/main`.
- HEAD : `4a2c7d0` — `feat: ajouter le serveur Web local minimal (FD-WEB-001)`.
- Répertoire de travail propre.
- `git status` et `git log --oneline --decorate -5` exécutés avant modification.

## Structure du shell

Le document français comporte un en-tête de marque, un contenu principal avec titre `Forge Design`, une courte description et une section d'état « Aucun projet ouvert. ».
Le titre de document, l'encodage UTF-8 et la métadonnée viewport sont explicites.
Un CSS intégré utilise les polices système, une mise en page adaptative, un fond clair et des contrastes sobres.
Aucun bouton inactif, formulaire, navigation, dashboard ou contenu métier n'est ajouté.

## Technologie retenue

HTML statique avec CSS intégré dans un seul fichier.
Le gestionnaire existant sert les octets de cette ressource sur l'unique route `/` avec `Content-Type: text/html; charset=utf-8` et `Content-Length` calculé sur les octets.
Aucune dépendance, moteur de templates, substitution de chaînes, routeur, contrôleur ou middleware n'est nécessaire.
Aucun JavaScript, framework frontend ou chargement externe n'est ajouté.

## Gestion des templates/ressources

Le fichier est situé dans `forge_design/web/templates/index.html`.
Malgré le nom du dossier, il s'agit d'une ressource HTML statique, sans syntaxe de template dynamique.
Le serveur utilise :

```python
files("forge_design.web").joinpath("templates/index.html").read_bytes()
```

Le chemin est constant, indépendant de l'URL et du répertoire courant.
`importlib.resources` permet aussi le chargement depuis la wheel utilisée comme archive Python.
La page n'est pas écrite dans une chaîne Python.

## Sécurité

Le comportement réseau reste inchangé : `127.0.0.1` uniquement, port par défaut `8765`, autres hôtes refusés.
Seule la ressource explicitement nommée du paquet est lue ; aucune donnée du projet ou du répertoire courant n'est exposée.
Les chemins inconnus, paramètres de projet, traversals bruts, encodés et doublement encodés sont refusés avec 404.
Même `/templates/index.html` n'est pas une route publique : seule `/` sert le shell.
Aucune URL n'est convertie en chemin filesystem.
Le serveur n'appelle ni le Bridge ni Project Inspector et ne lance aucune commande.

## Packaging

Déclaration ajoutée à `pyproject.toml` :

```toml
[tool.setuptools.package-data]
"forge_design.web" = ["templates/index.html"]
```

Commande exécutée réellement :

```bash
python -m pip wheel --no-deps --wheel-dir tmp/wheels .
```

L'interpréteur utilisé est celui de `.venv`.
Le build isolé a installé ses outils nécessaires sans ajouter de dépendance runtime.

Wheel produite : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `c126e7da48977b4d7357ef4245f0938ee32b560220417b14682e6783e22689f1`.

Contrôles effectués :

- ouverture de la wheel avec `zipfile.ZipFile` ;
- présence de `forge_design/web/templates/index.html` (1747 octets) ;
- égalité exacte avec les octets de la ressource source ;
- sous-processus Python isolé (`-I`) lancé depuis un répertoire temporaire ;
- import du serveur directement depuis la wheel et vérification de son origine ;
- lecture de la ressource depuis cette archive et assertions sur le titre et l'état sans projet.

Ces contrôles réussissent sans s'appuyer sur le checkout ou l'installation éditable pour les imports.
La wheel et les artefacts de build restent ignorés par Git.

## Fichiers créés

- [forge_design/web/templates/index.html](../../forge_design/web/templates/index.html)
- [docs/rapports/FD-UI-001.md](FD-UI-001.md)

## Fichiers modifiés

- [forge_design/web/server.py](../../forge_design/web/server.py) : réponse HTML via ressource fixe.
- [tests/test_web_server.py](../../tests/test_web_server.py) : assertions HTML, sécurité des chemins et indépendance du cwd.
- [pyproject.toml](../../pyproject.toml) : déclaration de la ressource distribuée.
- [docs/02-architecture.md](../02-architecture.md) : shell HTML effectivement disponible.

## Tests ajoutés

Six nouveaux cas s'ajoutent aux tests Web existants : quatre chemins supplémentaires refusés (traversals encodés et URL de ressource), un cwd temporaire avec faux `index.html`, un fichier arbitraire local inaccessible par URL.
Les tests existants de réponse sont adaptés au HTML : code 200, Content-Type, longueur, doctype, langue, titre et état sans projet.
Le contrôle d'accès aux fichiers autorise exclusivement la lecture binaire de la ressource connue du paquet et continue d'interdire les appels métier.
Les tests réseau précédents restent actifs, dont host, port, arrêt, libération du socket et port occupé.
La wheel est vérifiée séparément du pytest standard.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat |
|---|---|
| `git status` | État initial propre |
| `git log --oneline --decorate -5` | Historique initial inspecté |
| `pytest` | 162 tests réussis, dont 25 cas Web |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |
| `python -m pip wheel --no-deps --wheel-dir tmp/wheels .` | Wheel construite |
| Inspection ZIP et chargement isolé depuis la wheel | Succès |

Les outils sont ceux de `.venv` ; les tests HTTP utilisent l'autorisation de sockets locaux hors sandbox, comme pour FD-WEB-001.
Le diff complet est relu avant le commit, rapport compris.

## Tests sautés

Aucun test pytest sauté.
Aucun contrôle visuel automatisé dans un navigateur n'est revendiqué ; le document et son transport sont vérifiés par les tests HTTP.
Aucun projet Forge réel n'est nécessaire à ce shell statique.

## Limites restantes

- Page statique sans sélection de projet, Tool ou navigation métier.
- Aucune ouverture automatique de navigateur ni intégration CLI nouvelle.
- Les limites du serveur local synchrone de FD-WEB-001 restent inchangées.
- Toute évolution nécessitant un véritable backend Web devra faire l'objet d'une décision architecturale dédiée.

## État Git final

Livraison sur `main` dans un seul commit local, rapport inclus, sans push.
Message : `feat: ajouter le shell Web minimal (FD-UI-001)`.
Le hash et l'état Git vérifié après commit sont communiqués dans la réponse de livraison.

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-UI-001.md
```
