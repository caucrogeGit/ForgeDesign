# Forge Design — Compatibilité avec Forge

## 1. Objectif

Forge Design dépend des conventions réelles de Forge.

La compatibilité ne doit donc jamais reposer uniquement sur :

- une ancienne version de Forge ;
- une documentation obsolète ;
- une arborescence mémorisée ;
- une hypothèse codée en dur sans test.

## 2. Deux références différentes

### Forge `main`

`main` sert de référence de développement pour détecter les évolutions à venir.

Forge Design peut l'inspecter pendant son développement.

### Versions Forge supportées

Une release Forge Design supporte des versions Forge explicitement testées.

La compatibilité publiée est fondée sur ces versions, pas sur la simple affirmation « compatible avec main ».

## 3. Baseline initiale observée

Au démarrage du nouveau projet, la branche `main` de Forge expose notamment :

```text
Forge 1.0.0rc9
Python >= 3.12
```

Le squelette Forge actuel contient notamment :

```text
app.py
bootstrap.py
config.py
mvc/
    controllers/
    entities/
    forms/
    helpers/
    models/
    routes/
    validators/
    views/
```

Point notable :

```text
mvc/routes/
```

est une structure actuelle.

Forge Design ne doit donc pas figer l'ancienne hypothèse `mvc/routes.py`.

Cette baseline est un **constat de départ**, pas encore un contrat de support tant que les tests Forge Design correspondants n'existent pas.

## 4. Stratégie de tests

La compatibilité combine deux niveaux.

### 4.1 Fixtures unitaires

Des fixtures minimales permettent de tester rapidement :

- projet valide ;
- projet incomplet ;
- version absente ;
- structure inattendue ;
- symlink hors racine ;
- fichier sensible.

Ces fixtures testent les contrats internes.

### 4.2 Test d'intégration Forge réel

Un test dédié :

1. installe ou utilise une version Forge déterminée ;
2. exécute la création officielle d'un projet dans un répertoire temporaire ;
3. fait analyser ce projet par Forge Design ;
4. vérifie le résultat attendu.

Exemple conceptuel :

```text
forge new <tmp>/projet-test
        ↓
Forge Design detector
        ↓
Project Inspector
        ↓
assertions
```

Le test d'intégration ne doit pas modifier le dépôt Forge Design.

## 5. Matrice de compatibilité

Quand le premier test existe, Forge Design maintient une matrice explicite.

Exemple futur :

```text
Forge Design 0.x
├── Forge 1.0.0rc9 : testé
├── Forge 1.0.0     : à tester
└── Forge main      : surveillance développement
```

Ne pas annoncer une version comme supportée sans test correspondant.

## 6. Détection de version

La lecture de version doit :

- indiquer la valeur ;
- indiquer la source ;
- distinguer absence et erreur ;
- éviter d'importer arbitrairement l'application cible.

Si plusieurs sources existent, l'ordre de priorité est documenté et testé.

## 7. Détection de projet

La détection doit utiliser un petit ensemble de signatures stables.

Elle ne doit pas exiger que tout projet Forge possède exactement tous les dossiers optionnels.

Principe :

```text
signatures nécessaires
+
indices optionnels
=
diagnostic
```

Un dossier optionnel absent produit au besoin un avertissement, pas nécessairement un refus.

## 8. Évolution

Lorsqu'une évolution Forge casse une hypothèse Forge Design :

1. reproduire avec un projet Forge réel ;
2. ajouter ou corriger le test ;
3. adapter le Bridge ;
4. documenter la nouvelle compatibilité ;
5. ne pas modifier Forge Core uniquement pour préserver une hypothèse Forge Design.

## 9. Principe final

```text
Forge Design comprend Forge
par des contrats vérifiés,
pas par des suppositions.
```
