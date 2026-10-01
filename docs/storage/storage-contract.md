# Contrat de stockage — FD-STORAGE-001

Ce document est normatif. Il fixe **où** Forge Design persiste quelque chose,
**qui** le partage, **comment** chaque format est versionné et **comment** il
évolue. Toute nouvelle ressource persistante doit s'y conformer ou le modifier
explicitement par ticket.

## 1. Trois zones, une règle

```text
Zone                         Emplacement                        Partage Git
─────────────────────────    ───────────────────────────────    ──────────────
A. État utilisateur local    $XDG_*_HOME/forge-design/          jamais
B. Métadonnées projet        <projet>/.forge-design/            oui
C. Sources du projet         <projet>/mvc/…                     oui (sources)
```

**Règle directrice : tout ce que Forge Design écrit dans un projet est destiné à
être partagé par Git. Ce qui est propre à une personne ou à une machine vit hors
du projet, dans la zone A.**

Conséquences :

- aucun fichier ignoré par construction sous `.forge-design/` ; Forge Design ne
  crée ni ne modifie de `.gitignore` ou `.gitattributes` dans le projet ;
- aucun chemin absolu, nom d'utilisateur, nom de machine, secret ou contenu
  sensible dans les zones B et C : seulement des chemins relatifs à la racine ;
- un cache ou un état d'interface lié à un projet va en zone A, indexé par le
  projet, jamais en zone B.

## 2. Zone A — état utilisateur local

| Usage | Base | Fichier actuel |
|---|---|---|
| Configuration et listes | `$XDG_CONFIG_HOME/forge-design/` | `recent-projects.json` |
| Cache reconstructible | `$XDG_CACHE_HOME/forge-design/` | aucun |
| État d'exécution (UI, sessions) | `$XDG_STATE_HOME/forge-design/` | aucun |

Valeurs par défaut quand la variable est absente ou relative :
`~/.config`, `~/.cache`, `~/.local/state`. Une valeur relative n'est jamais
résolue depuis le répertoire courant.

Un cache peut être supprimé à tout moment sans perte : son absence n'est jamais
une erreur. La configuration et l'état ne le sont pas et suivent la section 5.

## 3. Zone B — `.forge-design/`

### Création

Le dossier n'est créé que par un service d'écriture, à la suite d'une action
explicite de l'utilisateur. Aucune lecture, inspection, preview ou génération
en mémoire ne le crée. Création en `0700`, fichiers en `0600` (sous réserve de
l'umask), modes existants jamais modifiés.

### Structure réservée

```text
.forge-design/
└── history.jsonl      journal append-only des écritures réussies
```

Tout autre nom est réservé. Un nouveau fichier ou sous-dossier exige un ticket
qui met à jour ce tableau :

| Chemin | Format | Version courante | Écrit par | Lu par |
|---|---|---|---|---|
| `history.jsonl` | JSONL, un objet par ligne | `1` | `append_generation_history` | — |

Pas de manifeste global : chaque fichier porte sa propre version (section 4),
ce qui évite toute transaction entre deux fichiers.

### Fusion Git

`history.jsonl` est append-only ; deux branches qui l'alimentent produisent un
conflit trivial en fin de fichier. La résolution correcte est de conserver les
deux blocs de lignes. Un projet peut déclarer lui-même `merge=union` pour ce
chemin ; Forge Design ne le fait pas à sa place.

## 4. Zone C — ressources de conception dans les sources

Les ressources de conception sont des sources du projet, à côté des templates
qu'elles décrivent, sous `mvc/views/`, et suivent la politique de chemins de la
vue source (pas de segment caché, pas de nom sensible, pas de lien) :

| Suffixe | Rôle | Version | Écriture |
|---|---|---|---|
| `*.view.json` | contrat de vue | aucune (voir dette) | lecture seule |
| `*.design.json` | design de vue | `"version": "0.1"` | `write_design`, révision attendue |
| `*.html` | template Forge | — | `write_generated_template` (FD-SAFEWRITE-003), révision attendue |

Les temporaires d'écriture `.forge-design-write-<aléatoire>` sont créés dans le
dossier cible et supprimés en sortie ; le préfixe est réservé.

Écrire dans la zone C suit le pipeline de l'architecture §14 :
lecture → validation → diff → décision utilisateur → écriture atomique avec
révision attendue → journalisation dans `history.jsonl`.

## 5. Versionnement des formats

1. Tout format persistant des zones A et B porte un champ entier `version`,
   à `1` pour sa première forme stable.
   - Fichier JSON : champ de premier niveau `"version"`.
   - Fichier JSONL : champ `"version"` dans **chaque** ligne, placé en premier.
     Chaque événement reste ainsi autodescriptif et des versions différentes
     peuvent coexister sans réécriture.
2. Les formats de la zone C conservent leur propre schéma produit. `0.x`
   (chaîne) signale un format pré-stable : il peut changer sans migration.
3. Un **écrivain** n'écrit que la version courante. Il ne réécrit jamais un
   fichier dont la version est inconnue ou supérieure.
4. Un **lecteur** refuse explicitement une version inconnue ou supérieure,
   sans réparation ni repli silencieux (modèle : `recent-projects.json`).
5. Zones A et B : un champ inconnu dans une version connue est une erreur de
   format, sauf si
   le format déclare explicitement une extension libre.
6. Augmenter la version est obligatoire pour tout changement qu'un lecteur de la
   version précédente interpréterait mal : champ retiré, renommé, sémantique
   modifiée, champ obligatoire ajouté.

## 6. Migrations

- Aucune migration automatique silencieuse. Une migration est une écriture comme
  une autre : diff présenté, décision utilisateur, écriture atomique.
- Zone A : un format obsolète peut être migré à la demande ; un format inconnu
  est laissé intact et signalé.
- Zone B, journaux append-only : jamais réécrits. Les nouvelles lignes sont
  écrites dans la version courante ; les lecteurs acceptent toutes les versions
  qu'ils déclarent supporter.
- Zone C : migration `0.x → 1` d'un format de conception par ticket dédié,
  appliquée fichier par fichier avec diff.
- Chaque ticket qui augmente une version documente : ancienne et nouvelle forme,
  versions lues, versions écrites, procédure de migration.

## 7. Dette connue au moment du contrat

| Élément | Écart | Traitement |
|---|---|---|
| `history.jsonl` | lignes sans `version` | corrigé par FD-STORAGE-002 |
| `*.view.json` | aucun champ de version | à décider avant stabilisation publique (cf. `docs/contracts/view-contract.md`) |
| `*.design.json` | version `"0.1"` pré-stable | passage à `1` lors de la stabilisation du format |
