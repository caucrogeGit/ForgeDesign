# Référence DrawCiel

Statut : **procédure normative légère** (FD-GRAPHICS-001). DrawCiel, intégré
à SéquenCiel, est la référence fonctionnelle et technique des outils graphiques
de Forge Design (Graphic Core, Circuit, simulation). Ce document dit **comment**
Forge Design suit ses évolutions. Il est mis à jour **par chaque ticket Forge
Design qui utilise DrawCiel**, jamais par synchronisation continue.

## Dépôt source

| Élément | Valeur |
|---|---|
| Dépôt | `caucrogeGit/SequenCiel` |
| Copie locale de travail | `/home/roger/Projets/SequenCiel` (lecture seule pour Forge Design) |
| Branche de référence | `origin/main` |
| Code DrawCiel | `static/vendor/drawciel/` (moteur), `static/drawciel-cadre.js`, `static/drawciel-hote.js` (adaptateurs) |
| Tests | `tests/drawciel-*.cjs` (Node hors DOM), `tests/browser/drawciel*.cjs` (Playwright), `tests/test_drawciel*.py`, `tests/fixtures/drawciel*` |
| Décisions | `docs/adr/` (255 à 286 pour DrawCiel au commit de référence) |
| Rapports | `docs/rapports/DC-*`, `docs/tickets/DC-*` |

Forge Design **ne dépend pas** de DrawCiel à l'exécution : aucun import, aucune
copie automatique, aucun suivi du HEAD en runtime.

## Dernière référence analysée

| Champ | Valeur |
|---|---|
| Commit | `aac36b27` — feat(drawciel): intégrer et qualifier le profil expérimental UNO R4 |
| Date du commit | 3 octobre 2026 |
| Date d'analyse | 3 octobre 2026 |
| Ticket | FD-CIRCUIT-003 |

## Journal des références

| Ticket | Référence précédente | Référence du ticket | Delta | Impacts retenus |
|---|---|---|---|---|
| FD-SPECIALIZED-001 | — | `5a02277d` (audit DC-016-00) | — | Contrat des outils spécialisés |
| FD-CIRCUIT-001 | `5a02277d` | `c229b2ed` | DC-015-23 à 32, DC-016-01 à 12 | Graphe unique, contrats de bornes, session isolée, IR ; périmètre Circuit |
| FD-GRAPHICS-001 | `c229b2ed` | `c229b2ed` | Vide sur `origin/main` ; commit local non publié `aac36b27` (profil UNO R4) examiné, non retenu | Aucun impact sur le noyau graphique ; à reprendre au prochain ticket une fois publié |
| FD-CIRCUIT-002 | `c229b2ed` | `aac36b27` (publié) | UNO R4 / RA4M1 : ADR-287 à 306, contrats de périphériques (GPIO, ADC, UART, PWM, I²C, SPI, DAC), QEMU/Renode, cosimulation, `drawciel_r4/document.py` | Graphics : aucun. Circuit V0.1 : aucun champ ; principes confirmés (liste fermée de champs de composant, définition versionnée immuable, état d'exécution refusé, aucune sémantique par nom). Simulation future : à conserver. Microcontrôleurs : hors Phase 10 |
| FD-CIRCUIT-003 | `aac36b27` | `aac36b27` | Vide (`git fetch` : `origin/main` inchangé) | Contrats des 8 types V1 (`electrical-contracts.js`), identité canonique des réseaux (ADR-262), masse = référence sans source ; correspondances documentées dans le domaine Circuit |

## Procédure de delta

À appliquer au démarrage de chaque ticket FD-GRAPHICS-\* important, FD-CIRCUIT-\*
architectural ou de simulation :

1. `git fetch` dans la copie SéquenCiel (aucune autre modification de ce dépôt).
2. Relever `origin/main` ⇒ `DRAWCIEL_REFERENCE_CURRENT`. La dernière ligne du
   journal donne `DRAWCIEL_REFERENCE_PREVIOUS`.
3. Si les deux diffèrent : `git log --oneline PREVIOUS..CURRENT` et
   `git diff --stat PREVIOUS..CURRENT` restreints aux zones surveillées ;
   lire les ADR et rapports DC ajoutés.
4. Signaler, sans l'adopter, tout commit local non publié de la copie de
   travail : il peut être réécrit ; il n'est retenu qu'une fois publié.
5. Classer chaque constat : **historique**, **encore vrai**, **corrigé depuis**,
   **nouveau**. Un constat récent prévaut sur un ancien audit.
6. Évaluer l'impact selon les règles ci-dessous.
7. **Figer** `DRAWCIEL_REFERENCE_CURRENT` pour la durée du ticket.
8. Consigner dans le rapport du ticket : commit de référence, date, delta,
   éléments examinés, impacts retenus ; ajouter une ligne au journal.

## Zones à surveiller

| Zone | Chemins indicatifs | Concerne |
|---|---|---|
| Géométrie, sélection, routage, historique, export | `static/vendor/drawciel/js/app.js`, `tests/browser/drawciel-routage.cjs`, `-interface.cjs`, `-plan-travail.cjs`, `-rendus.cjs` | Graphic Core |
| Modèle, graphe électrique | `js/model.js`, `tests/drawciel-graph.cjs`, fixtures A–J | Circuit |
| Catalogue et contrats | `js/components-data.js`, `js/electrical-contracts.js`, `tools/drawciel-catalogue.cjs`, `tests/drawciel-contracts.cjs` | Circuit |
| Annotations, texte | `app.js`, `tests/browser/drawciel-annotations.cjs`, `-texte.cjs`, `-rappel.cjs`, `-trait-libre.cjs` | Graphic Core |
| Simulation | `js/simulation.js`, `tests/drawciel-session.cjs`, `-numerique.cjs` | Simulation Circuit |
| IR et SPICE | `js/simulation-ir.js`, `js/simulation-translation-policy.js`, `js/spice-netlist.js`, `tests/drawciel-simulation-ir.cjs`, `-spice*.cjs`, `tools/drawciel-spice/` | Simulation Circuit |
| Instruments | `app.js` (multimètre, oscilloscope), `js/readouts.js`, `tests/browser/drawciel-ohmmetre.cjs` | Simulation Circuit |
| Microcontrôleurs, cosimulation | `js/cosim-core.js`, `js/avr-adapter.js`, `js/mcu-ui.js`, `js/board-*.js`, `js/r4-*.js`, bus I²C/SPI, terminal série | À étudier (hors Phase 10) |
| Adaptateurs hôte | `static/drawciel-cadre.js`, `static/drawciel-hote.js` | Référence pour l'intégration hôte ; code SéquenCiel |
| ADR | `docs/adr/` | Toutes |

## Règles d'impact

| Constat dans le delta | Action |
|---|---|
| Correction d'un algorithme repris ou à reprendre (routage, géométrie) | Mettre à jour la matrice de réutilisation ; ajouter le scénario correspondant aux témoins |
| Nouveau contrat de catalogue ou de bornes | Réévaluer la conversion de catalogue ; vérifier les identifiants de bornes et propriétés Circuit |
| Changement de l'IR ou de la politique de traduction | Réévaluer la compatibilité de la future IR Circuit |
| Nouvelle dette (heuristique par nom, état runtime persisté) | Consigner comme *nouveau* ; ne pas reproduire |
| Fonctionnalité pédagogique ou SéquenCiel | Consigner ; aucun impact sur Forge Design |
| Correction critique invalidant le ticket en cours | Seule exception au gel : l'intégrer et le justifier dans le rapport |

## Automatisation

Aucune automatisation n'est créée. Un script produisant le rapport de delta
(commits, fichiers des zones surveillées, ADR ajoutées) pourra être ajouté plus
tard si la procédure manuelle devient coûteuse.
