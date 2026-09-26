# Rapport — FD-FORGE-002

Ce rapport décrit l’état constaté à la clôture de l’implémentation, avant l’ajout du présent fichier.

| Élément | Résultat |
|---|---|
| Ticket | FD-FORGE-002 — Détecter un projet Forge réel |
| Objectif | Reconnaître structurellement un projet Forge sans exécuter son code, lire ses secrets ni déterminer sa version |
| Branche | `main` |
| Commit | `8c5a2a736c156d90d599d6151fbb48a265db8fd7` |
| Message | `feat: détecter un projet Forge (FD-FORGE-002)` |
| État Git initial | Propre ; 1 commit d’avance sur `origin/main` |
| État Git final de l’implémentation | Propre ; 2 commits d’avance sur `origin/main` ; aucun push |

## Signatures Forge retenues

| Chemin | Type attendu | Rôle |
|---|---|---|
| `app.py` | Fichier ordinaire | Nécessaire |
| `bootstrap.py` | Fichier ordinaire | Nécessaire |
| `config.py` | Fichier ordinaire | Nécessaire |
| `mvc/` | Dossier | Nécessaire |
| `mvc/routes/` | Dossier | Nécessaire |
| `mvc/controllers/`, `mvc/entities/`, `mvc/forms/`, `mvc/helpers/`, `mvc/models/`, `mvc/validators/`, `mvc/views/` | Dossiers | Optionnels |

Une signature nécessaire absente ou incorrecte invalide le diagnostic. Un élément optionnel absent ou incorrect produit un avertissement. Les dossiers supplémentaires sont acceptés.

Ces choix reposent sur l’inspection de `forge.py`, de `skeleton/__init__.py` et du [squelette officiel de Forge](https://github.com/caucrogeGit/Forge/tree/73a956e587e5f169c028415e0e540c149cbaff56/skeleton/data), au commit `73a956e587e5f169c028415e0e540c149cbaff56`. La commande `git ls-remote` a confirmé que ce commit correspondait à la tête distante de `main`.

## Fichiers et API

Deux fichiers créés pour l’implémentation :

- [forge_design/forge/project_detection.py](../../forge_design/forge/project_detection.py)
- [tests/test_project_detection.py](../../tests/test_project_detection.py)

Aucun fichier existant modifié. Le document `docs/04-compatibilite-forge.md` reste inchangé.

API ajoutée :

```python
detect_forge_project(root: str | PathLike[str]) -> ForgeProjectDiagnostic
```

Le résultat est une dataclass gelée contenant :

```python
valid: bool
errors: tuple[str, ...]
warnings: tuple[str, ...]
```

La racine passe systématiquement par `resolve_project_root`. Les exceptions de cette API restent propagées.

Le détecteur vérifie uniquement les métadonnées des chemins sélectionnés. Il refuse les liens symboliques des signatures, y compris internes, et ne descend pas dans un `mvc` invalide. Il ne lit aucun contenu, n’importe pas l’application et n’écrit rien dans le projet.

## Tests unitaires

28 nouveaux cas couvrent :

- structure minimale valide et diagnostic déterministe ;
- absence et mauvais type de chaque signature nécessaire ;
- éléments optionnels absents ou de mauvais type ;
- dossiers supplémentaires ;
- liens symboliques internes, externes, cassés et cycliques ;
- résolution de racine ;
- erreur d’accès à une signature ;
- absence de lecture de contenu, de parcours récursif et de modification.

## Test d’intégration Forge réel

**Version utilisée :** Forge `1.0.0rc9`, depuis le dépôt local correspondant au commit distant vérifié.

Commande exécutée :

```bash
forge new projet-test
```

Répertoire de travail temporaire :

```text
/tmp/fd-forge-002-lvidanxw
```

L’appel utilisait un environnement explicite, sans configuration utilisateur de pip ou Git, avec téléchargements et cache pip désactivés. Le nom simple était nécessaire : cette version de Forge refuse un chemin absolu comme nom de projet.

**Résultat : échec, code de retour 1.**

La commande a matérialisé le squelette puis échoué pendant l’installation des dépendances :

```text
ERROR: No matching distribution found for forge-mvc==1.0.0rc9
```

Cet échec en mode hors ligne ne démontre pas une indisponibilité du paquet en ligne. Aucun test d’intégration complet réussi n’est revendiqué. Le répertoire temporaire a été nettoyé.

Une vérification distincte du détecteur sur le squelette officiel local a réussi :

```python
ForgeProjectDiagnostic(valid=True, errors=(), warnings=())
```

Cette vérification ne remplace pas une création complète par `forge new`.

## Commandes et validations

Les contrôles Git initiaux, l’inspection du code Forge, la vérification distante de `main` et la relecture du diff complet ont été effectués.

| Commande | Résultat final |
|---|---|
| `pytest` | 44 tests réussis |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |
| `git diff --cached --check` | Succès |

Une erreur initiale Ruff de longueur de ligne a été corrigée avant les validations finales.

**Tests sautés :** aucun dans la suite pytest. Aucun test automatisé d’intégration Forge ajouté.

## Limites restantes

- La création complète d’un projet Forge reste à valider avec les dépendances disponibles.
- La reconnaissance porte sur la structure ; elle ne garantit ni l’authenticité ni l’exécutabilité du projet.
- Aucune version du projet cible n’est déterminée.
- L’inspection suppose un système de fichiers stable pendant l’appel ; elle ne protège pas contre les modifications concurrentes.

Le détecteur répond désormais de manière déterministe au critère de reconnaissance structurelle demandé. L’unique commit d’implémentation du ticket est créé et reste local.
