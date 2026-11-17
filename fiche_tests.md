# Fiche de tests (Guide 6)

Règle du sujet : on écrit l'**attendu AVANT** de lancer la commande, puis on note l'**observé** et on compare.
Ne cochez « OK » que pour un test que vous avez vraiment exécuté.

Tous les lots de test viennent de `python generer_tests.py` (dossier `essais_preuves/`).
Base commune des tests U2 à U9 : 10 contrats d'une ligne (quantité 1, 1 jour, 100.00 MAD).
Contrats 1 à 6 `paid`, 7 et 8 `closed`, 9 `draft`, 10 `cancelled` : seuls 8 comptent, donc **800.00 MAD**.

## Partie 1 : règles de qualité, sans base de données

Commande type : `python controle_lot.py essais_preuves/unitaires/<NOM>`
État initial : aucune base utilisée, rien n'est écrit.

| # | Dossier de test | Ce que contient le lot | Attendu | Observé | OK ? |
|---|---|---|---|---|---|
| U1 | `U1_valide_heure_et_jour` | 4 contrats : `paid` au jour (2×3×50), `closed` à l'heure (3×4×10), `draft`, `cancelled` | 4 lignes acceptées, 0 rejet, montant retenu **420.00** (300 + 120) | | |
| U2 | `U2_doublon_exact` | base + la ligne du contrat 1 copiée à l'identique | 11 reçues, **1 doublon retiré**, 10 acceptées, 0 rejet, 800.00 | | |
| U3 | `U3_conflit_cle_ligne` | base + contrat 11 ligne 1 écrite 2 fois avec un contenu différent (quantité 1 puis 2) | 12 reçues, 10 acceptées, **2 rejetées** (`LINE_KEY_CONFLICT`), 1 contrat en quarantaine, taux 16.67 %, 800.00 | | |
| U4 | `U4_quantite_invalide` | base + contrat 11 : ligne 1 quantité **-3**, ligne 2 valide | 12 reçues, 10 acceptées, 2 rejetées (`INVALID_QUANTITY` + `CONTRACT_QUARANTINED`), 1 contrat isolé en entier, taux 16.67 %, 800.00 | | |
| U5 | `U5_quantite_25` | base + contrat 11 avec quantité **25** (tarif 10.00) | 11 acceptées, **0 rejet**, **1 anomalie** (ligne 12), montant 800 + 250 = **1050.00** | | |
| U6 | `U6_client_inconnu` | base + contrat 11 avec client 99999 | 10 acceptées, 1 rejetée (`UNKNOWN_CLIENT`), 1 contrat en quarantaine, taux 9.09 %, 800.00 | | |
| U7 | `U7_entete_contradictoire` | base + contrat 11 dont la ligne 1 a le client 11 et la ligne 2 le client 12 | 10 acceptées, **2 rejetées** (`CONTRACT_HEADER_CONFLICT`), taux 16.67 %, 800.00 | | |
| U8 | `U8_structure_fausse` | colonnes `quantity` et `unit_rate` échangées | `REJETE_STRUCTURE : colonnes absentes, en trop ou dans le mauvais ordre`, rien n'est lu ni écrit | | |
| U9 | `U9_alerte_rejet` | base + 4 contrats (11 à 14) avec un client inconnu | 14 reçues, 10 acceptées, 4 rejetées, taux **28.57 %**, `alertes: ["TAUX_DE_REJET_ELEVE"]`, 800.00 | | |

## Partie 2 : chargement dans la base de test `campusequip_test`

Préparation : `python preparer_base_test.py` (base vide, 9 tables), puis `CAMPUS_DSN` pointe vers `campusequip_test`.
Commande type : `python surveiller.py --entree essais_preuves/<flux> --une-fois`

| # | Essai | État initial de la base | Attendu | Observé | OK ? |
|---|---|---|---|---|---|
| D1 | `flux_A` : **trois lots successifs** | vide (0 / 0 / 0) | 3 lots `CHARGE`, **3 rapports distincts** dans `rapports/` ; base : **9 contrats, 10 lignes, 3 lots, somme 740.00** | | |
| D2 | `flux_A` relancé (**arrêt puis redémarrage**) | 9 / 10 / 3 / 740.00 | 3 × `DEJA_CHARGE`, 0 ligne ajoutée ; base **identique** : 9 / 10 / 3 / 740.00 | | |
| D3 | `flux_B` : un lot **réutilise le contrat 1** avec un autre contenu (+ un contrat 50 neuf) | 9 / 10 / 3 / 740.00 | `ECHEC … 1 contrat(s) déjà chargé(s)`, **aucun ajout** (même le contrat 50 est refusé) ; base **identique** : 9 / 10 / 3 / 740.00 | | |
| D4a | `flux_C`, lot 1 : **colonnes fausses** | 9 / 10 / 3 / 740.00 | `REJETE_STRUCTURE`, 0 ligne écrite, journal toujours à 3 lots | | |
| D4b | `flux_C`, lot 2 : **28.57 % de rejets** | 9 / 10 / 3 / 740.00 | message `ALERTE … 28.57 %`, statut `CHARGE` : les **10 bons contrats** sont chargés quand même ; base : **19 contrats, 20 lignes, 4 lots, somme 1740.00** | | |

Requête de contrôle à lancer dans DBeaver (base `campusequip_test`) avant et après chaque essai :

```sql
SELECT (SELECT count(*) FROM contracts)          AS contrats,
       (SELECT count(*) FROM contract_lines)     AS lignes,
       (SELECT count(*) FROM ingestion_batches)  AS lots,
       (SELECT sum(amount) FROM line_amounts WHERE status IN ('paid','closed')) AS somme;
```
## Résultats observés
U1_valide_heure_et_jour : 4 reçues, 0 doublon(s) retiré(s), 4 acceptées, 0 rejetées (0 contrat(s) en quarantaine), 0 anomalie(s), taux 0.00 %, alerte : aucune, motifs : aucun, montant retenu 420.00 MAD
U2_doublon_exact : 11 reçues, 1 doublon(s) retiré(s), 10 acceptées, 0 rejetées (0 contrat(s) en quarantaine), 0 anomalie(s), taux 0.00 %, alerte : aucune, motifs : aucun, montant retenu 800.00 MAD
U3_conflit_cle_ligne : 12 reçues, 0 doublon(s) retiré(s), 10 acceptées, 2 rejetées (1 contrat(s) en quarantaine), 0 anomalie(s), taux 16.67 %, alerte : aucune, motifs : LINE_KEY_CONFLICT x2, montant retenu 800.00 MAD
U4_quantite_invalide : 12 reçues, 0 doublon(s) retiré(s), 10 acceptées, 2 rejetées (1 contrat(s) en quarantaine), 0 anomalie(s), taux 16.67 %, alerte : aucune, motifs : INVALID_QUANTITY x1, CONTRACT_QUARANTINED x1, montant retenu 800.00 MAD
U5_quantite_25 : 11 reçues, 0 doublon(s) retiré(s), 11 acceptées, 0 rejetées (0 contrat(s) en quarantaine), 1 anomalie(s), taux 0.00 %, alerte : aucune, motifs : aucun, montant retenu 1050.00 MAD
U6_client_inconnu : 11 reçues, 0 doublon(s) retiré(s), 10 acceptées, 1 rejetées (1 contrat(s) en quarantaine), 0 anomalie(s), taux 9.09 %, alerte : aucune, motifs : UNKNOWN_CLIENT x1, montant retenu 800.00 MAD
U7_entete_contradictoire : 12 reçues, 0 doublon(s) retiré(s), 10 acceptées, 2 rejetées (1 contrat(s) en quarantaine), 0 anomalie(s), taux 16.67 %, alerte : aucune, motifs : CONTRACT_HEADER_CONFLICT x2, montant retenu 800.00 MAD
U8_structure_fausse : REJETE_STRUCTURE (colonnes absentes, en trop ou dans le mauvais ordre) ; rien n'est lu ni écrit
U9_alerte_rejet : 14 reçues, 0 doublon(s) retiré(s), 10 acceptées, 4 rejetées (4 contrat(s) en quarantaine), 0 anomalie(s), taux 28.57 %, alerte : TAUX_DE_REJET_ELEVE, motifs : UNKNOWN_CLIENT x4, montant retenu 800.00 MAD


D1 : flux_A, 3 lots CHARGE, base à 9 contrats / 10 lignes / 3 lots / somme 740.00
D2 : flux_A relancé, 3 DEJA_CHARGE, 0 ligne ajoutée, base inchangée (9 / 10 / 3 / 740.00)
D3 : flux_B, ECHEC « 1 contrat(s) déjà chargé(s) avec un nouveau contenu … lot annulé, rien n'est ajouté », base inchangée
D4 : flux_C, REJETE_STRUCTURE puis ALERTE 28.57 % et CHARGE (10 lignes ajoutées), base à 19 contrats / 20 lignes / 4 lots / somme 1740.00