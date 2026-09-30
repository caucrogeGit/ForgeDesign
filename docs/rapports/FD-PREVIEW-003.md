# Rapport — FD-PREVIEW-003

## Ticket et objectif

Ajouter desktop, tablet et mobile comme enveloppes de largeur indicative autour
du fragment de render_preview. Clôturer la phase Preview statique, sans navigateur,
route Web, CSS projet, backend ou écriture de fichier.

## État Git initial

main et origin/main à 357fc97 — FD-PREVIEW-002. État Git et dix derniers commits
inspectés. Seule modification préexistante : docs/rapports/FD-CONTRACT-001.md,
titre « État Git initiala », conservée hors ticket et hors commit.
Aucun AGENTS.md dans le dépôt.

## Sources fonctionnelles

Ticket FD-PREVIEW-003, architecture et documentation Preview, API renderer/data,
modèles Design et fixtures contacts-list/conditional examinés. La roadmap distingue
preview statique et preview réelle. Les largeurs sont les conventions explicites
du ticket, sans référence à une norme ou un modèle d'appareil.

## Presets responsive

PreviewViewportMode est le Literal desktop/tablet/mobile.
PreviewViewport est une dataclass gelée : mode et width_px.
PREVIEW_VIEWPORTS est un MappingProxyType contenant exactement trois presets gelés :
desktop 1440 px, tablet 768 px, mobile 390 px. Aucune hauteur fixe.

## API publique

Exports depuis forge_design.preview :
PreviewViewportMode, PreviewViewport, PREVIEW_VIEWPORTS, ResponsivePreviewResult,
preview_viewport, wrap_preview_html et render_responsive_preview.
ResponsivePreviewResult est gelé et contient mode, width_px, html, issues et complete.
preview_viewport retourne le preset canonique. Mode invalide : ValueError stable
« Mode de preview inconnu : desktop, tablet ou mobile attendu. » avant tout rendu.

## Wrapper HTML

Div avec data-forge-design-responsive et data-forge-design-width.
Composition exacte ouverture + rendered.html + fermeture, sans parsing,
reconstruction, interprétation ou double échappement.
wrap_preview_html peut réutiliser un seul fragment pour trois modes.
La primitive attend un fragment contrôlé du renderer ; elle n'assainit pas un
HTML arbitraire fourni par l'appelant.

## Style indicatif

Style exclusivement interne : width:<preset>px;max-width:100%;margin:0 auto;.
Aucune valeur utilisateur interpolée. Pas de hauteur, padding, bordure, ombre,
police, fond ou CSS supplémentaire. L'exception au principe sans style du renderer
appartient uniquement à l'enveloppe de simulation, jamais au code généré du projet.
max-width peut réduire la largeur effective dans un parent plus étroit.

## Composition avec renderer

render_responsive_preview valide le mode, appelle render_preview exactement une
fois puis enveloppe sa sortie. Les blocs, tables et conditions restent gérés par
render.py inchangé. Aucun appel implicite au générateur de données.
MAX_PREVIEW_HTML_CHARS inchangé : l'enveloppe ajoute un surcoût fixe par preset,
sans nouveau budget ni troncature. La primitive sur fragment ne borne pas sa taille.

## Diagnostics

Tuple issues propagé par identité, sans copie des diagnostics, traduction, perte
de location ou nouveau diagnostic métier. Complete repris strictement.
Test missing_value et test réel output_too_large : même fragment d'erreur conservé
à l'intérieur des trois enveloppes.

## Déterminisme

Même Design, mapping et mode : même HTML, largeur, diagnostics et complétude.
Un fragment unique est vérifié identique à l'intérieur des trois modes.
Aucun temps, hasard, calcul d'écran ou état persistant.

## Pureté

Tests bloquant open, os.open, Path.open/read_text/read_bytes, socket et subprocess.
Aucun import Forge, Web, navigateur, registre ou contexte dans responsive.py.
Scénario installé construit tout en mémoire et bloque les accès fichiers pendant
le pipeline. Aucune nouvelle dépendance.

## Non-mutation

Comparaison profonde Design/data avant/après et conservation des identités de
children et de la liste de données. MappingProxyType accepté en entrée.
Dataclasses gelées et collection de presets non modifiable vérifiées.
Le résultat renderer est seulement lu ; son tuple de diagnostics est réutilisé.

## Limites responsive

Un div de largeur cible ne reproduit pas un viewport navigateur et ne déclenche
pas les media queries comme une fenêtre dédiée. Aucune feuille Tailwind chargée :
md:grid-cols-2 reste une classe textuelle sans calcul de son comportement.
Pas de DPR, orientation, touch mode, user-agent, capture ou test d'appareil réel.
Les modes sont indicatifs et ne remplacent pas les tests responsive réels.

## Compatibilité Preview 001/002

data.py, render.py et limits.py inchangés. Même contexte fictif, trois lignes
contacts et mêmes emails dans chaque mode. Conditions True/False conservées,
texte hostile échappé sans double échappement, classe Tailwind conservée.
Design, Contracts, Bridge, Tools, Web, app.py, pyproject.toml et JavaScript inchangés.

## Documentation

docs/preview/static-preview.md étendu avec presets, API, wrapper, style contrôlé,
conservation du fragment, caractère indicatif et limites navigateur/Tailwind.
docs/02-architecture.md décrit le pipeline jusqu'aux trois enveloppes.
La clôture de phase et la suite FD-GENERATE-001 sont documentées.

## Fichiers créés

- forge_design/preview/responsive.py
- tests/test_preview_responsive.py
- docs/rapports/FD-PREVIEW-003.md

## Fichiers modifiés

- forge_design/preview/__init__.py : exports publics.
- docs/preview/static-preview.md : contrats responsive.
- docs/02-architecture.md : composition du pipeline.

La modification utilisateur FD-CONTRACT-001.md reste hors commit.

## Tests ajoutés

17 cas : trois presets/minimal/attributs parsés, immutabilité, six modes invalides
dont injection et valeurs non chaînes, contacts/conditions dans trois modes,
texte hostile et conservation exacte, propagation diagnostics/fragment de limite,
appel unique au renderer, pureté/déterminisme/non-mutation.
Aucun duplicata de la batterie interne des blocs ou de leurs budgets.

## Validations ciblées

| Contrôle | Résultat |
|---|---|
| pytest render + responsive | 91 réussis |
| pytest data + render + responsive | 125 réussis |
| pytest responsive après ajustements de typage | 17 réussis |
| python -m compileall -q forge_design | Succès |
| ruff check forge_design tests | Succès |
| pyright | 0 erreur, 0 avertissement |
| git diff --check | Succès |

Le contrôle runtime initial isinstance a été remplacé par l'appartenance au
vocabulaire fermé pour respecter le typage Literal tout en refusant les modes
invalides. La liste de comptage du test a été typée explicitement. Formatage
et imports corrigés avant la validation de clôture.

## Validation complète de fin de phase

Suite globale exécutée une fois après succès des tests ciblés, conformément au
ticket de clôture : 2424 tests réussis en 26,94 s, aucun test sauté.
Pip check : No broken requirements found.
Suite avec autorisation hors sandbox pour ses sockets HTTP historiques ;
build isolé hors sandbox pour les dépendances de construction.
Journaux ignorés : tmp/pytest_fd_preview_003.log et tmp/wheel_fd_preview_003.log.
Les tickets suivants reviennent aux validations ciblées par défaut.

## Packaging

Wheel : tmp/wheels/forge_design-0.1.0.dev0-py3-none-any.whl.
SHA-256 : 2a15c3d987c8a0ca85072c48b388103239cc44f1d56c929e93f046396f542cf8.
Archive inspectée : preview/__init__.py, data.py, render.py et responsive.py
identiques aux sources. Aucun tests/ ou tmp/ distribué.
Métadonnées vérifiées : aucune dépendance runtime nouvelle, pyproject.toml inchangé.

## Installation réelle

Installation --no-deps --no-index --target dans un répertoire temporaire.
Processus Python -I : origine installée de forge_design.preview et responsive
vérifiée. Contrat contacts et Design construits en mémoire, génération de données,
render_preview puis les trois enveloppes. Vérification largeurs, fragment interne
identique, statut, diagnostics, trois lignes, email, section et bouton.
Accès fichiers bloqués pendant le pipeline ; aucun serveur ni projet consulté.
Script/journal ignorés : tmp/verify_fd_preview_003.py et .log.
Installation et scénario réussis sans élévation.

## Tests sautés

Aucun test pytest sauté. MkDocs strict non applicable : aucune configuration dans le dépôt.
Node --check non relancé conformément au ticket, aucun JavaScript modifié.
Aucun navigateur, iframe, test visuel ou capture revendiqué.

## Limites restantes

Presets conventionnels, largeur effective dépendante du parent, croissance
verticale libre. Aucune simulation du CSS final, des breakpoints ou d'appareils.
wrap_preview_html compose du HTML de confiance sans le nettoyer ni le borner.
La preview avancée pourra traiter le rendu navigateur et CSS réel.
Aucune intégration Web dans ce ticket.

## État Git final

Un seul commit local sur main, rapport inclus, sans push.
Message : feat: ajouter la preview responsive (FD-PREVIEW-003).
Diff utilisateur FD-CONTRACT-001.md conservé hors commit ; Forge Core inchangé.
Hash et état Git final communiqués dans la réponse de livraison.
