# Rapport — FD-UI-003

## Ticket et objectif

Ajouter une navigation explicite entre Accueil et Project Inspector dans un shell Jinja commun, sans état persistant ni navigation issue du registre.

## État Git initial

- Branche `main`, propre et synchronisée avec `origin/main`.
- HEAD `0fef30d` — `feat: lancer Forge Design depuis la CLI (FD-CLI-001)`.
- État Git et cinq derniers commits inspectés avant modification.

## Navigation ajoutée

Deux liens fixes dans un élément `nav` : Accueil vers `/` et Project Inspector vers `/inspector`.
La page active est fournie explicitement au rendu : `home` pour l'accueil, `inspector` pour tous les rendus Inspector, y compris les erreurs et résultats POST.
Aucune introspection des routes ni consultation du registre pour produire les liens.
Les routes existantes sont conservées, aucun Tool ajouté.

## Layout commun

`layout.html` contient le document HTML, le head, la marque, la navigation et le conteneur principal.
Deux blocs Jinja suffisent : `title` et `content`.
Les deux pages héritent directement de ce layout, sans hiérarchie supplémentaire.
Le module `rendering.py` factorise l'appel au renderer public Forge déjà utilisé par Inspector ; ce n'est pas un moteur de templates supplémentaire.
Les noms de templates viennent uniquement du code interne, jamais de l'URL.

## Templates

L'accueil est désormais rendu par Jinja, avec les mêmes titre, description et état sans projet.
Le contenu du formulaire et des diagnostics Inspector est conservé ; seul l'encadrement commun est extrait.
La résolution, les erreurs, la validation HTTP, l'origine du POST et le flux Tool/Bridge sont inchangés.
L'échappement automatique du renderer Forge reste actif.

## Accessibilité

Navigation sémantique avec `aria-label="Navigation principale"`, liens réels et un seul `aria-current="page"` par page.
Le lien actif est souligné et en gras ; l'indication ne repose pas sur la couleur seule.
Le focus visible existant est réutilisé. Chaque page conserve son titre principal et sa structure de contenu.

## CSS

Extension de `/shell.css` pour l'espacement des liens, leur retour à la ligne sur écran étroit et leur état actif.
Aucun framework, script, animation ou étape de build frontend ajouté.

## Fichiers créés

- [forge_design/web/rendering.py](../../forge_design/web/rendering.py)
- [forge_design/web/templates/layout.html](../../forge_design/web/templates/layout.html)
- [docs/rapports/FD-UI-003.md](FD-UI-003.md)

## Fichiers modifiés

- [forge_design/web/server.py](../../forge_design/web/server.py) : rendu Jinja de l'accueil.
- [forge_design/web/inspector.py](../../forge_design/web/inspector.py) : délégation au rendu partagé, contexte de page active.
- [forge_design/web/templates/index.html](../../forge_design/web/templates/index.html) : héritage du layout.
- [forge_design/web/templates/inspector.html](../../forge_design/web/templates/inspector.html) : héritage du layout.
- [forge_design/web/static/shell.css](../../forge_design/web/static/shell.css) : navigation.
- [pyproject.toml](../../pyproject.toml) : inclusion explicite du layout.
- [tests/test_web_server.py](../../tests/test_web_server.py) : navigation et héritage.
- [docs/02-architecture.md](../02-architecture.md) : shell commun disponible.

## Tests ajoutés

Trois nouveaux cas : navigation HTTP sur chacune des deux pages, puis vérification que les deux templates héritent du même layout sans dupliquer le head ou la navigation.
Les tests HTTP vérifient les deux liens, l'état actif unique, les éléments communs et le CSS ; des sentinelles interdisent les appels `get` et `list` du registre lors du rendu de la navigation.
Les tests existants continuent de couvrir les résultats Inspector, le POST, les erreurs, la sécurité, les routes inconnues, les ressources CSS et l'unique Tool intégré.

## Packaging

`layout.html` est déclaré explicitement dans les package-data.
La wheel a été construite puis inspectée comme archive : trois templates et CSS présents.
Installation temporaire avec `pip --no-deps --no-index --target`, puis processus Python isolé (`-I`) depuis un répertoire temporaire, avec vérification de l'origine importée.
Les GET `/` et `/inspector` affichent chacun le bon état actif depuis cette installation.
Le contrôle vérifie aussi le CSS, la CSP, un POST sur le squelette Forge local (version `1.0.0rc9`, source `requirements.txt`), le retour au formulaire vierge, l'arrêt et la libération du port.
Les dépendances runtime proviennent de `.venv` ; aucune nouvelle génération Forge n'est effectuée.

Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `f327bd486c51c37a6c59d37a5700857c10c4f931edb3beef32c3e82072453367`.
Script de vérification ignoré par Git : `tmp/verify_fd_ui_003.py`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| État Git et `git log --oneline --decorate -5` | État initial inspecté |
| `pytest` | 194 tests réussis, dont 3 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| `python -m pip wheel --no-deps --wheel-dir tmp/wheels .` | Succès |
| Inspection ZIP et HTTP depuis la wheel installée | Succès |

Outils de `.venv`, Python 3.13.5. Tests HTTP exécutés avec autorisation de sockets locaux hors sandbox.
Un diagnostic initial Ruff d'ordre des imports a été corrigé avant les validations finales.
La suppression Pyright ciblée pour les stubs manquants du renderer Forge est déplacée avec l'import dans le module partagé, sans nouvelle suppression.
Le diff complet est relu avant commit, rapport compris.

## Tests sautés

Aucun test pytest sauté.
Aucun contrôle visuel automatisé navigateur n'est revendiqué ; sémantique HTML, transport et packaging sont vérifiés.

## Limites restantes

- Navigation fixe limitée aux deux pages existantes.
- Aucun état de projet ou de navigation sauvegardé.
- Les limites du serveur et du Bridge restent inchangées.

## État Git final

Un seul commit local sur `main`, rapport inclus, sans push.
Message : `feat: ajouter la navigation Web minimale (FD-UI-003)`.
Le hash et l'état Git vérifié après commit sont communiqués dans la réponse de livraison.

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-UI-003.md
```
