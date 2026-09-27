# Projets récents

Après une ouverture valide dans Project Inspector, Forge Design conserve le chemin
canonique du projet. Les dix derniers projets sont proposés sur l’accueil.
**Ouvrir** lance une nouvelle inspection ; **Retirer** enlève uniquement le raccourci.
Un projet retiré reste ouvert et ses fichiers restent intacts.

Au redémarrage, la liste est conservée mais aucun projet n’est ouvert automatiquement.
Si un récent a disparu ou n’est plus reconnu, le diagnostic s’affiche, l’entrée reste
présente et le projet courant précédent est conservé. Une réouverture valide remonte
l’entrée en tête, sans doublon. Fermer ou actualiser ne change pas cette liste.

Le stockage local se trouve dans :

```text
$XDG_CONFIG_HOME/forge-design/recent-projects.json
```

Si XDG_CONFIG_HOME est absent, vide ou relatif, le chemin utilisé est
`~/.config/forge-design/recent-projects.json`. Il n’est pas basé sur le dossier courant.
Le stockage doit rester hors des projets. Aucun dossier `.forge-design` n’y est créé.

Le JSON contient seulement la version du format (`1`) et une liste de chemins.
Il ne contient ni diagnostic, ni version Forge, ni projet actif. Aucun chemin n’est
envoyé à un service extérieur. Les programmes locaux disposant des mêmes droits
utilisateur peuvent naturellement accéder à cette liste.

Un fichier invalide, trop grand (64 Kio), lié ou de version inconnue n’est pas réparé
ni écrasé automatiquement. Un avertissement est affiché ; l’ouverture d’un projet
valide reste possible. Pour rétablir l’historique, corriger ou déplacer ce fichier
manuellement après l’avoir sauvegardé. Les parents liés sont également refusés.
Les plateformes ne fournissant pas les primitives sécurisées nécessaires signalent
l’indisponibilité du stockage, sans repli moins strict.

L’écriture atomique évite un JSON partiellement remplacé. Plusieurs instances peuvent
lire le même fichier ; leurs modifications concurrentes ne sont pas fusionnées.
Ce composant ne constitue ni un workspace multi-projets ni une sauvegarde des projets.
