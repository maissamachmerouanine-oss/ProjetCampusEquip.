# Journal des aides utilisées

Les dates et les mots sont à vérifier et à adapter par le binôme : ce journal décrit notre démarche.
Aide principale : l'assistant Claude (explications, code proposé, correction d'erreurs à partir de captures d'écran).

| Date | Question ou difficulté | Aide utilisée | Modification réalisée | Test effectué et résultat |
| --- | --- | --- | --- | --- |
| 2026-11-02 | Comprendre le but du projet et le parcours d'une location (du fichier au résultat SQL) | Claude : explications simples avec des exemples | Aucune modification de code. J'ai reformulé le pipeline avec mes mots et relu le sujet | Je sais expliquer : lot, contrôle, quarantaine, base, analyses |
| 2026-11-02 | Créer la base `campusequip` avec Docker et DBeaver | Claude : étapes guidées, captures d'écran | `etudiant/schema.sql` (9 tables, vue `line_amounts`) exécuté dans la base campusequip | `test_connexion.py` : 9 tables, « Tout est bon » |
| 2026-11-03 | Écrire les règles de qualité sans toucher à la base | Claude : `regles.py` et `controle.py` | Fichiers ajoutés dans `etudiant/`, relus fonction par fonction | `controle_lot.py exemples/lot_000001` : rapport affiché, 0 rejet |
| 2026-11-04 | Charger un lot dans PostgreSQL avec signature et journal de rejeu | Claude : `traitement.py` | `traitement.py` complété ; ensuite chargement par paquets de 500 lignes (le premier chargement était trop lent) | 2 lots `CHARGE`, relance = `DEJA_CHARGE`, somme `paid` + `closed` = 48098.00 |
| 2026-11-04 | Erreur « relation line_amounts does not exist » dans DBeaver | Claude : diagnostic à partir de la capture | Aucune modification de code : la mauvaise base était active (shopflow_lab). J'ai choisi campusequip dans la barre du haut | Les 4 requêtes de contrôle donnent 40 contrats, 80 lignes, 2 lots, 48098 |
| 2026-11-05 | Écrire les 3 analyses et le graphique | Claude : `analyses.sql` et `graphique.py` | Fichiers ajoutés à la racine du projet | Preuve à la main du contrat 2 : 402 + 756 + 4528 = 5686 ; graphique : Campus Rabat en tête (10805.00 MAD) |
| 2026-11-05 | Prouver les règles avec de petits lots de test | Claude : `generer_tests.py`, `preparer_base_test.py`, `fiche_tests.md` | Fichiers ajoutés ; `etudiant/schema.sql` remplacé car l'ancien ne créait aucune table (0 table dans `campusequip_test`) | Attendu écrit avant, puis comparé à l'observé |
| 2026-11-10 | Résultats des essais | Aucune aide : comparaison de l'attendu et de l'observé | `fiche_tests.md` complétée | U1 à U9 conformes ; D1 à D4 conformes (base de test finale : 19 contrats, 20 lignes, 4 lots, 1740.00) |