# Application HTML – Calendrier concours & dates clés (v0.5)

## Fichiers
- index.html
- styles.css
- app.js
- concours.csv (séparateur ;)
- dates_cles.csv (séparateur ;)

## Lancer en local
Les navigateurs bloquent souvent le chargement de fichiers si on ouvre en file://

Dans le dossier :
- `python -m http.server 8000`
Puis :
- http://localhost:8000


## Mandats (liens)
Dans `concours.csv`, ajoutez une colonne `Mandat` avec une URL. L’app affichera un bouton « Ouvrir le mandat » dans les détails du concours.


## Icônes
Les pictogrammes TAE / 18m / Campagne / Beursault sont chargés depuis le dossier `icons/`.
