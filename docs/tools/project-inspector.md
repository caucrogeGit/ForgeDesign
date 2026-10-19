# Project Inspector

Project Inspector est le point d’entrée du cockpit Forge Design. Il reconnaît un
projet Forge, lit sa version déclarée et, une fois le projet sélectionné,
présente une **synthèse de santé** de tout le projet (FD-PROJECT-006). Il ne
modifie jamais les fichiers du projet.

## Ouvrir un projet

Saisir le chemin d’un dossier local, ou ouvrir un projet récent depuis
l’accueil. Le projet n’est sélectionné que s’il est reconnu : `app.py`,
`config.py`, `mvc/` et `mvc/routes/` sont obligatoires.

`bootstrap.py` est **optionnel**, comme pour forge-mvc 1.0.0rc9, qui ne le
charge que s’il existe (`load_bootstrap`, ADR-093). Un projet créé avant ce
câblage est donc reconnu. Absent, `bootstrap.py` n’est signalé que comme
information dans la section Structure. Présent, il doit être un fichier
ordinaire : un lien symbolique ou un autre type rend le projet non reconnu, comme
pour les éléments obligatoires (FD-FORGE-004).

Les autres dossiers MVC sont optionnels. « Actualiser » réinspecte le projet
courant ; un projet devenu invalide ou inaccessible est alors fermé.

## Synthèse de santé

Dès qu’un projet est sélectionné, `/inspector` présente neuf sections, chacune
avec un état, un résumé, des comptages, les premiers diagnostics (cinq au plus,
avec le total) et un lien vers l’outil qui donne le détail.

| Section | Analyse réutilisée | Contenu | Détail |
|---|---|---|---|
| Projet | Contexte courant | Nom, dossier, accessibilité | — |
| Forge | Project Inspector | Projet reconnu, version et source, compatibilité « non évaluée » (aucune règle de version Forge n’existe encore) | Détail de l’inspection |
| Structure | Détection du squelette | Éléments requis trouvés, optionnels trouvés, anomalies | Détail de l’inspection |
| Routes | Route Explorer et ses diagnostics | Nombre de routes, méthodes HTTP, routes avec et sans diagnostic | Route Explorer |
| Entités | Entity Explorer et ses diagnostics | Entités, relations, erreurs, avertissements | Entity Explorer |
| Templates | Template Viewer | Fichiers de `mvc/views`, templates de vue, métadonnées | Template Viewer |
| Migrations | Inventaire des migrations | Fichiers `mvc/migrations/*.sql`, noms conformes, fichiers vides | — |
| Diagnostics | Debug Center | Événements du journal par niveau, anomalies de lecture | Debug Center |
| Contrats de vue | Liaison contrats ↔ templates | Contrats, valides, invalides, templates associés ou sans contrat | Template Viewer |

### États

Chaque état est écrit et marqué ; la couleur ne fait que le souligner.

| État | Signification |
|---|---|
| ✓ OK | Analyse disponible, sans avertissement |
| ! Attention | Avertissement connu, ou analyse secondaire indisponible |
| ✕ Erreur | Diagnostic d’erreur connu |
| – Indisponible | Analyse impossible (projet inaccessible, non reconnu, source illisible) |

Les sévérités sont celles des analyses existantes : routes, entités et
structure gardent leurs erreurs et avertissements. Sans sévérité existante, une
anomalie de template, de contrat ou de migration vaut « attention » ; un contrat
invalide est compté comme invalide sans devenir bloquant. Un élément optionnel
absent (`bootstrap.py`, dossier MVC, `mvc/entities`, `mvc/views`,
`mvc/migrations`) n’est qu’une information ; un `bootstrap.py` présent mais
invalide est une erreur. Les erreurs ERROR ou CRITICAL du journal runtime sont des
erreurs passées de l’application : elles demandent un examen (« attention »)
mais ne mettent jamais le projet « en erreur ». La mise en garde permanente de
Route Explorer (lecture statique, liste possiblement partielle) est une
information ; une vraie limite de lecture reste un avertissement.

### État global

Dans l’ordre : **erreur** si une section est en erreur ; sinon **indisponible**
si le projet lui-même n’est plus analysable (dossier supprimé ou remplacé) ;
sinon **attention** si une section est en attention ou indisponible ; sinon
**OK**. Aucun score : les comptages ne sont pas un verdict sur la qualité du
projet.

### Résultats partiels

Chaque section ne capture que les erreurs déjà traitées par la page de son
outil (racine introuvable, projet non reconnu, source des routes absente ou
illisible) et devient alors « indisponible » avec un message ; les autres
sections restent présentées. Une erreur inattendue est un bug et produit une
erreur serveur, jamais une section silencieusement vide.

### Tableau de bord (FD-UX-002)

La synthèse s'affiche en tuiles, avec le même contenu, les mêmes données et les
mêmes calculs :

- chaque tuile donne son titre et son état écrit, puis son résumé en chiffre clé
  (« 629 routes déclarées. ») ;
- les faits clés restent visibles : une tuile en Attention montre sa raison,
  par exemple « Invalides 3 » ;
- la liste des diagnostics se déplie sous leur nombre (« 8 diagnostics ») ;
- l'action vers l'outil reste en pied de tuile.

Sous la synthèse, deux panneaux :

- **À traiter en priorité** reprend les diagnostics déjà visibles dans les tuiles,
  les erreurs puis les avertissements, six au plus. Chacun renvoie à sa tuile,
  et le reste est compté. Sans erreur ni avertissement, le panneau l'écrit.
- **Commandes Forge** présente `project:audit`, `doctor` et `project:check` avec
  leur niveau de confiance (lecture seule, configuration, exécution du projet).
  Chaque commande renvoie à sa section de Debug Center, où elle se lance par un
  POST explicite. Rien n'est exécuté depuis cette page.

## Lecture seule et coût

La synthèse est recalculée à chaque affichage, sans cache ni persistance
(`Cache-Control: no-store`). Elle n’écrit rien, n’exécute ni le projet ni ses
migrations, et ne lit que par les analyses existantes, avec leurs protections
(descripteurs ancrés, liens non suivis, lectures bornées). Chaque analyse est
lancée une seule fois par affichage ; l’inventaire de `mvc/views` lu pour les
templates est réutilisé pour les contrats de vue, dont l’analyse ne vérifie la
racine Forge qu’une fois au lieu d’une fois par contrat (FD-PERF-001). Après une
ouverture ou une actualisation, l’inspection qui vient d’être faite est reprise
telle quelle.

Les commandes officielles `forge doctor` (qui exécute la configuration),
`forge project:audit` et `forge project:check` (qui importe les routes, donc du
code applicatif) n’entrent pas dans la synthèse : elles se lancent seulement à
la demande depuis
[Debug Center](debug-center.md#diagnostic-forge-à-la-demande-fd-runtime-001)
(FD-RUNTIME-001 à 003).

Les migrations ne sont qu’inventoriées : entrées directes de `mvc/migrations`,
nom (`AAAAMMJJHHMMSS_nom.sql`, convention Forge) et taille pour repérer un
fichier vide ; aucun contenu SQL n’est ouvert.

## Sans projet ni JavaScript

Sans projet sélectionné, aucune analyse n’est faite : la page propose de
saisir un chemin ou d’ouvrir un projet récent. La page est entièrement
utilisable sans JavaScript.
