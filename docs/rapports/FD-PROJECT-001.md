# Rapport — FD-PROJECT-001

## Ticket et objectif

Conserver un projet courant en mémoire par instance Forge Design, afficher sa racine dans le shell et permettre sa fermeture sans écriture ni persistance.

## État Git initial

- Branche `main`, propre et synchronisée avec `origin/main`.
- HEAD `1641ada` — `feat: ouvrir le navigateur au lancement (FD-CLI-002)`.
- État Git et cinq derniers commits inspectés avant modification.

## Modèle du contexte projet

`CurrentProjectContext` conserve une seule référence privée vers un `ProjectInspection` immuable, ou `None`.
Les propriétés en lecture seule `inspection` et `root` exposent ce diagnostic et sa racine.
La racine est dérivée du diagnostic : il n'existe pas deux champs susceptibles de diverger.
`set_project(inspection)` refuse un diagnostic invalide avec `ValueError` avant mutation ; `clear()` rétablit l'état vide.
Le contrat accepte le résultat canonique du Tool ; il ne refait aucune résolution ou lecture du projet.

## Cycle de vie

`create_application()` construit explicitement un contexte neuf, une seule fois, puis le fournit aux routes via leurs fermetures Python.
Un résultat Inspector valide devient courant ; une nouvelle inspection valide le remplace, y compris si sa version est indéterminable.
La fermeture vide le contexte. Une nouvelle instance d'application démarre toujours vide.
Le diagnostic reste un instantané ; aucune surveillance ni actualisation automatique ajoutée.

## Intégration Project Inspector

Après récupération du Tool dans le registre et vérification du type `ProjectInspection`, le handler appelle `set_project` uniquement si `valid` est vrai.
Le chemin conservé est celui du résultat, jamais la saisie brute.
Le traitement métier, le Bridge et le registre sont inchangés.
Le formulaire GET reste vierge ; le shell montre désormais le projet conservé sans relancer l'inspection.

## Intégration Web

Le layout affiche « Aucun projet ouvert. » ou la racine du projet et sa version lorsqu'elle est connue.
Le diagnostic courant est fourni explicitement au rendu des deux pages.
L'ancien bloc d'état de l'accueil est retiré pour éviter un affichage contradictoire ou dupliqué.
Les pages portant l'état sont servies avec `Cache-Control: no-store`.
Aucun état n'est placé dans le ToolRegistry, aucun singleton ni variable globale de projet.

## Fermeture du projet

Un formulaire du shell appelle `POST /project/close` ; après contrôle d'origine, `clear()` vide le contexte et l'accueil est rendu avec statut 200.
Le serveur reste actif. Une fermeture répétée est sans effet supplémentaire.
Un GET ne ferme pas le projet.

La sécurité est réévaluée pour les deux actions, activation et fermeture, puisqu'elles modifient maintenant l'état runtime.
L'inspection du code installé `core/security/middleware.py` et `core/app/application.py` confirme que le CSRF Forge rc9 repose sur une session.
Le choix retenu sans session est un contrôle strict d'origine partagé dans `web/security.py`, avec `csrf=False` explicite sur ces deux POST seulement.
`Origin` doit correspondre exactement à `http://` suivi du Host local `127.0.0.1[:port]` ; `Sec-Fetch-Site`, s'il existe, doit valoir `same-origin`.
Origine absente, nulle ou étrangère : 403 avant mutation. Aucun middleware global n'est retiré.
Cette protection vise les soumissions de pages étrangères dans un navigateur ; elle n'authentifie pas les programmes locaux capables de fabriquer des en-têtes.
La fermeture ne reçoit aucune donnée projet et ne nécessite pas de parser un champ de chemin.

## Gestion des erreurs

Une inspection structurellement invalide affiche son diagnostic tout en conservant le précédent projet courant.
Les trois erreurs attendues de racine, les champs invalides et les refus HTTP ne modifient pas le contexte.
Une version inconnue ne retire pas la validité structurelle et n'empêche pas l'activation.
Les exceptions inattendues restent propagées comme auparavant.

## État et isolation

Le contexte appartient à l'instance serveur et est partagé entre ses onglets et clients locaux, sans session utilisateur.
Deux applications ont deux contextes indépendants. Un redémarrage simulé par une nouvelle application retrouve un état vide.
Les mutations sont encapsulées ; aucune infrastructure de verrouillage ajoutée au serveur synchrone actuel.
Aucun fichier de configuration, cookie, base de données, localStorage ou répertoire de projet ajouté.

## Fichiers créés

- [forge_design/current_project.py](../../forge_design/current_project.py)
- [forge_design/web/security.py](../../forge_design/web/security.py)
- [tests/test_current_project.py](../../tests/test_current_project.py)
- [docs/rapports/FD-PROJECT-001.md](FD-PROJECT-001.md)

## Fichiers modifiés

- [forge_design/web/server.py](../../forge_design/web/server.py) : composition et fermeture.
- [forge_design/web/inspector.py](../../forge_design/web/inspector.py) : activation et contexte de rendu.
- [forge_design/web/templates/layout.html](../../forge_design/web/templates/layout.html) : projet courant et fermeture.
- [forge_design/web/templates/index.html](../../forge_design/web/templates/index.html) : suppression du bloc d'état dupliqué.
- [forge_design/web/static/shell.css](../../forge_design/web/static/shell.css) : zone de projet sobre.
- [tests/test_web_inspector.py](../../tests/test_web_inspector.py) : cycle runtime et isolation.
- [docs/02-architecture.md](../02-architecture.md) : contrat runtime et sécurité actualisés.

## Tests ajoutés

14 nouveaux cas couvrent l'invariant du contexte, l'état initial, l'activation canonique, le stockage du même diagnostic, une version connue puis inconnue, la conservation après inspection invalide ou erreur de racine, la fermeture, les origines refusées et l'isolation entre applications.
Le contrôle de fermeture vérifie le refus de GET et de `Sec-Fetch-Site: cross-site`, ainsi que l'absence de modifications, créations ou suppressions dans le projet.
Les tests existants de non-écriture, d'échappement et du Bridge restent actifs.
Le test antérieur de GET vierge est adapté : le champ reste vide mais le projet apparaît désormais dans le shell.

## Test réel

Une wheel est construite puis inspectée : layout, deux pages et CSS présents.
Installation temporaire avec `pip --no-deps --no-index --target`, processus Python isolé (`-I`) depuis un répertoire temporaire, origine des imports vérifiée.
Un POST HTTP inspecte le squelette Forge local de référence : `1.0.0rc9`, source `requirements.txt`.
Les GET suivants affichent sa racine sur Inspector et Accueil ; un POST de fermeture retourne à l'état vide, confirmé par un nouveau GET.
Le contrôle vérifie aussi CSS, CSP, arrêt du thread, fermeture et réutilisation du port.
Aucune nouvelle génération Forge effectuée ; les dépendances runtime proviennent de `.venv`.

Artefact : `tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl`.
SHA-256 : `3b748db408b186c008a97ccc61a6727a869a7b6cd3bab2ddd3162aa390c8c3bc`.
Script ignoré par Git : `tmp/verify_fd_project_001.py`.

## Commandes exécutées et résultats

| Commande ou contrôle | Résultat final |
|---|---|
| État Git et `git log --oneline --decorate -5` | État initial inspecté |
| Inspection CSRF Forge installé | Dépendance à la session confirmée |
| `pytest` | 212 tests réussis, dont 14 nouveaux cas |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Succès |
| `python -m pip wheel --no-deps --wheel-dir tmp/wheels .` | Succès |
| Wheel installée, cycle HTTP réel | Succès |

Outils de `.venv`, Python 3.13.5 ; échanges HTTP avec autorisation de sockets locaux hors sandbox.
Les diagnostics initiaux Ruff de longueur de ligne et d'import sont corrigés avant validation finale.
Le diff complet, rapport compris, est relu avant commit.

## Tests sautés

Aucun test pytest sauté.
Aucun test visuel navigateur ou nouvelle génération Forge revendiqué.

## Limites restantes

- Contexte partagé par les clients de la même instance, sans isolation utilisateur.
- Diagnostic instantané pouvant devenir obsolète après une modification externe du projet.
- Garantie de racine canonique héritée du Tool ; aucune nouvelle validation filesystem dans le contexte.
- Protection d'origine navigateur, pas authentification locale.
- Serveur synchrone et limites du Bridge inchangés.

## État Git final

Un seul commit local sur `main`, rapport inclus, sans push.
Message : `feat: ajouter le contexte projet courant (FD-PROJECT-001)`.
Le hash et l'état Git vérifié après commit sont communiqués dans la réponse de livraison.

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-PROJECT-001.md
```
