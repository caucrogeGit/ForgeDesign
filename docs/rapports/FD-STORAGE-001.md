# Rapport — FD-STORAGE-001

## Ticket et objectif

Phase 7 de la roadmap : fixer le contrat de stockage avant toute nouvelle
ressource persistante. Structure de `.forge-design/`, versionnement des formats,
partage Git, stockage utilisateur local, migrations. Documentation seulement,
aucun code modifié.

## État Git initial

`main` à `1ec1d29` — FD-WEB-003, un commit d'avance sur `origin/main`.
Modification hors ticket préservée : `docs/rapports/FD-CONTRACT-001.md`.

## Contexte

L'audit du 1er octobre 2026 a relevé que FD-GENERATE-005 crée déjà
`.forge-design/history.jsonl`, alors que la roadmap place ce contrat
« avant toute ressource persistante » et que l'architecture déclarait
« aucun format sous `.forge-design/` stable avant un ticket dédié ».

## Inventaire de l'existant

| Ressource | Zone | Version |
|---|---|---|
| `$XDG_CONFIG_HOME/forge-design/recent-projects.json` | utilisateur | `"version": 1`, inconnue refusée |
| `.forge-design/history.jsonl` | projet | aucune |
| `mvc/views/**/*.design.json` | sources | `"version": "0.1"` |
| `mvc/views/**/*.view.json` | sources | aucune (choix FD-CONTRACT-001) |
| `.forge-design-write-*` | temporaire | — |

## Décisions

1. **Trois zones** : état utilisateur local (XDG), métadonnées projet
   (`.forge-design/`), sources du projet (`mvc/…`).
2. **Tout ce qui est écrit dans le projet est destiné à Git** ; le local va
   en XDG. Forge Design ne crée ni `.gitignore` ni `.gitattributes`.
   Conséquence : `history.jsonl` est partagé.
3. **Structure fermée** de `.forge-design/` : liste explicite, tout autre nom
   réservé, extension par ticket. Pas de manifeste global.
4. **Version par fichier**, entier `version` ; pour JSONL, dans chaque ligne.
5. **Écrivains** : version courante seulement, jamais de réécriture d'un
   format inconnu. **Lecteurs** : refus explicite d'une version inconnue.
6. **Migrations** : jamais automatiques et silencieuses ; journaux
   append-only jamais réécrits.
7. **Dette listée** : `history.jsonl` (FD-STORAGE-002), `*.view.json` sans
   version, `*.design.json` pré-stable.

La décision 2 est la plus structurante. Alternative écartée : journal local
ignoré par Git, qui aurait placé dans le projet un fichier non partagé et
contredit le cadrage §8.2 (« métadonnées explicitement partagées et versionnées »).

## Fichiers créés

- [docs/storage/storage-contract.md](../storage/storage-contract.md)
- [docs/rapports/FD-STORAGE-001.md](FD-STORAGE-001.md)

## Fichiers modifiés

- [docs/02-architecture.md](../02-architecture.md) : §10 résumé et renvoi au contrat.
- [docs/01-cadrage-fonctionnel.md](../01-cadrage-fonctionnel.md) : §8.2 renvoi au contrat.

## Commandes exécutées et résultats

| Commande | Résultat |
|---|---|
| `git diff --check` | Succès |

Aucun code modifié : suite de tests non concernée.

## Limites restantes

- `$XDG_CACHE_HOME` et `$XDG_STATE_HOME` sont définis par le contrat mais
  aucun code ne les utilise encore.
- Le contrat ne fixe pas de rotation ni de taille maximale pour `history.jsonl`.

## État Git final

Un commit, rapport inclus, sans push.
Message : `docs: définir le contrat de stockage (FD-STORAGE-001)`.
