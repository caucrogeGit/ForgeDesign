# Rapport — FD-STORAGE-002

## Ticket et objectif

Mettre `.forge-design/history.jsonl` en conformité avec le contrat de stockage
(FD-STORAGE-001, §5) : chaque ligne porte un entier `version`, placé en premier.

## État Git initial

`main` à `6fca886` — FD-STORAGE-001, deux commits d'avance sur `origin/main`.
Modification hors ticket préservée : `docs/rapports/FD-CONTRACT-001.md`.

## Format

Avant :

```json
{"timestamp":"2026-09-30T09:15:00Z","action":"generate_template","file":"mvc/views/élèves/liste.html"}
```

Après :

```json
{"version":1,"timestamp":"2026-09-30T09:15:00Z","action":"generate_template","file":"mvc/views/élèves/liste.html"}
```

## Choix

- Constante `HISTORY_FORMAT_VERSION = 1` dans `generate/history.py`, exportée par
  `forge_design.generate`.
- La version est une propriété de la sérialisation : `GenerationHistoryEvent` et
  la signature de `append_generation_history` sont inchangées. L'appelant ne
  peut donc pas écrire une version arbitraire.
- La limite `MAX_HISTORY_EVENT_BYTES` (16 384 octets, LF compris) inclut le
  nouveau champ ; le chemin maximal accepté diminue de 14 octets.
- Toutes les autres garanties de FD-GENERATE-005 sont inchangées : append-only,
  un seul `write`, `fsync`, contrôles des liens.

## Migration

Aucune. Le fichier n'existait que dans des projets de test : aucun code produit
n'appelle encore `append_generation_history`. Conformément au contrat
(journaux append-only jamais réécrits), une ligne sans `version` déjà présente
serait laissée telle quelle ; un futur lecteur devra la traiter comme une
version `0` pré-contrat ou la refuser, par décision explicite.

## Fichiers modifiés

- [forge_design/generate/history.py](../../forge_design/generate/history.py)
- [forge_design/generate/__init__.py](../../forge_design/generate/__init__.py)
- [tests/test_generate_history.py](../../tests/test_generate_history.py) : octets
  attendus mis à jour, 1 cas ajouté (version entière en tête de chaque ligne).
- [docs/generate/template-generation.md](../generate/template-generation.md)
- [docs/storage/storage-contract.md](../storage/storage-contract.md) : dette marquée corrigée.

## Fichiers créés

- [docs/rapports/FD-STORAGE-002.md](FD-STORAGE-002.md)

## Commandes exécutées et résultats

| Commande | Résultat |
|---|---|
| `pytest tests/test_generate_history.py` | 50 réussis |
| `pytest` | 2706 réussis |
| `ruff check .` / `ruff format` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |

## État Git final

Un commit, rapport inclus, sans push.
Message : `feat: versionner le journal Forge Design (FD-STORAGE-002)`.
