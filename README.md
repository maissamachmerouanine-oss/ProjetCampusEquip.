# CampusEquip v2 : axes 1 (SQL) et 2 (Python)

Projet de binôme, à remettre le 21 novembre 2026.
Ce dépôt charge des lots de locations de matériel (fichiers CSV + JSON) dans PostgreSQL, applique des règles de
qualité, isole les contrats douteux en quarantaine, puis permet 3 analyses SQL et un graphique.

## 1. Ce qu'il faut avoir installé

| Outil | Pourquoi |
|---|---|
| Python 3.10 ou plus | exécuter les programmes |
| Docker Desktop | faire tourner PostgreSQL dans un conteneur (`db-1`, port 5433) |
| DBeaver | créer la base, lancer le SQL, vérifier les résultats |
| VS Code | ouvrir le dossier du projet et lancer les commandes |

Bibliothèques Python à installer une fois, dans le terminal de VS Code :

```
pip install "psycopg[binary]" matplotlib
```

## 2. Préparer une base neuve

La base du projet doit être **distincte de ShopFlow** et ne contenir qu'**une seule campagne**.

1. Dans Docker Desktop, démarrer le conteneur PostgreSQL (`db-1` doit être vert).
2. Dans DBeaver, se connecter au serveur (`localhost`, port `5433`), puis créer une base nommée `campusequip`
   (clic droit sur « Bases de données », puis « Créer une nouvelle base »).
3. Ouvrir `etudiant/schema.sql` dans DBeaver **sur la base campusequip** (vérifier le nom dans la barre du haut) et
   exécuter tout le script (Alt + X). Il crée 9 tables et la vue `line_amounts`.

Pour repartir d'une base vide de test (`campusequip_test`) en une commande, sans toucher à `campusequip` :

```
python preparer_base_test.py
```

## 3. Se connecter sans secret dans les fichiers

Aucun mot de passe n'est écrit dans le code ni dans ce dépôt. La connexion est lue dans la variable d'environnement
`CAMPUS_DSN`. Dans le terminal PowerShell de VS Code (à refaire à chaque nouveau terminal) :

```
$env:CAMPUS_DSN = "postgresql://UTILISATEUR:MOT_DE_PASSE@localhost:5433/campusequip"
```

Remplacer `UTILISATEUR` et `MOT_DE_PASSE` par les identifiants de la base locale. Vérifier ensuite :

```
python test_connexion.py
```

Résultat attendu : `Connecté à la base : campusequip`, `Tables trouvées dans public : 9`, puis `Tout est bon.`

## 4. Démarrer le traitement

Charger les deux petits lots d'exemple (chargement dans la base `campusequip`) :

```
python surveiller.py --entree exemples --une-fois
```

- Premier passage : chaque lot affiche `CHARGE`.
- Relancer la même commande : chaque lot affiche `DEJA_CHARGE` et rien n'est ajouté (le journal `ingestion_batches` empêche
  le double chargement, même après un redémarrage).
- Un rapport JSON et, s'il y a des rejets, un fichier de quarantaine sont écrits dans `rapports/` à chaque tentative.

Contrôler un lot **sans toucher à la base** :

```
python controle_lot.py exemples/lot_000001
```

## 5. Les analyses et le graphique

- `analyses.sql` : 3 analyses + la preuve à la main du contrat 2 (402 + 756 + 4528 = 5686). À ouvrir dans DBeaver sur
  `campusequip`.
- Graphique du cumul par campus :

```
python graphique.py
```

Il écrit `graphique_cumul.png` dans le dossier.

## 6. Les tests de règles et de rejeu

Les petits lots de test se fabriquent avec :

```
python generer_tests.py
python observer_unitaires.py
```

- `essais_preuves/unitaires/` : 9 petits lots (U1 à U9) pour les règles de qualité (`controle_lot.py` ou
  `observer_unitaires.py`).
- `essais_preuves/flux_A`, `flux_B`, `flux_C` : essais avec la base (trois lots, rejeu, contrat déjà chargé, structure
  fausse, alerte à 20 %). À lancer sur la base de test :

```
python preparer_base_test.py
$env:CAMPUS_DSN = "postgresql://UTILISATEUR:MOT_DE_PASSE@localhost:5433/campusequip_test"
python surveiller.py --entree essais_preuves/flux_A --une-fois
```

- `fiche_tests.md` : pour chaque essai, les commandes, l'état initial, l'**attendu** (écrit avant) et l'**observé**.

## 7. Démonstration en continu (trois lots)

Sur une base neuve (`campusequip_test`) et un nouveau dossier `flux`. Deux terminaux dans VS Code.

Terminal 1 (le surveillant, qui attend les lots) :

```
python surveiller.py --entree flux
```

Terminal 2 (le générateur, un lot toutes les 10 secondes, trois lots au total) :

```
python generer.py --sortie flux --contrats 50 --lots 3 --profil mixte --intervalle 10
```

## 8. Arrêter proprement

- Arrêter le surveillant : **Ctrl + C** dans son terminal.
- Le générateur s'arrête seul avec `--lots 3` ; sinon **Ctrl + C**.
- Ne pas supprimer `generator-state.json`. Pour repartir de zéro : nouveau dossier **et** base neuve.
- Arrêter le conteneur PostgreSQL depuis Docker Desktop si besoin. Les données sont conservées.

## 9. Règles de qualité appliquées (dans l'ordre)

1. Structure du fichier fausse (colonnes) : tout le lot est refusé (`REJETE_STRUCTURE`) avant toute écriture.
2. Espaces retirés, `status` et `unit` en minuscules.
3. Ligne répétée à l'identique : gardée une seule fois.
4. Chaque ligne est vérifiée : types, bornes, client, site et équipement connus.
5. Chaque contrat est vérifié comme un tout : en-tête identique, clé (contrat, ligne) unique. Un problème isole
   **tout le contrat** en quarantaine.
6. Quantité supérieure à 20 : signalée comme anomalie, sans rejet.
7. Taux de rejet supérieur à 20 % : alerte, mais les contrats valides sont chargés quand même.

Montant d'une ligne = quantité × durée × tarif. Seuls les contrats `paid` et `closed` comptent, rattachés à `start_date`.

## 10. Contenu du dossier

| Fichier ou dossier | Rôle |
|---|---|
| `etudiant/schema.sql` | tables, vue `line_amounts`, journal `ingestion_batches` |
| `etudiant/regles.py`, `etudiant/controle.py` | règles et contrôles de qualité |
| `etudiant/traitement.py` | signature du lot, chargement en une transaction, rapports, rejeu |
| `analyses.sql`, `graphique.py` | analyses SQL et graphique |
| `controle_lot.py`, `generer_tests.py`, `observer_unitaires.py`, `preparer_base_test.py`, `fiche_tests.md` | tests et preuves |
| `exemples/` | petit échantillon reproductible (2 lots propres de 20 contrats) |
| `generer.py`, `surveiller.py` | fournis par le kit (non modifiés) |
| `journal_IA.md` | aides utilisées |
