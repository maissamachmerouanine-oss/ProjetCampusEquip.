"""Guide 6 : fabrique les petits lots de test (avec des erreurs volontaires).

    python generer_tests.py

Résultat : un dossier essais_preuves/ avec
    unitaires/   9 petits lots pour controle_lot.py (sans base de données)
    flux_A/      3 lots propres        (surveiller.py : trois lots successifs, puis rejeu)
    flux_B/      1 lot qui réutilise un contrat déjà chargé (doit échouer, sans rien ajouter)
    flux_C/      1 lot aux colonnes fausses + 1 lot avec trop de rejets (alerte à 20 %)

Chaque fichier est assez petit pour être expliqué ligne par ligne.
Les référentiels (clients, sites, équipements) sont copiés depuis exemples/lot_000001.
"""
import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path

SORTIE = Path('essais_preuves')
SOURCE_REF = Path('exemples/lot_000001/referentiels.json')
COLONNES = ['contract_id', 'client_id', 'site_id', 'start_date', 'status',
            'line_no', 'equipment_id', 'quantity', 'unit', 'duration', 'unit_rate']
CAMPAGNE = 'aaaaaaaa-0000-4000-8000-000000000001'      # même campagne pour tous les lots de test
CLIENT_INCONNU = 99999                                  # n'existe pas dans le référentiel (1 à 2000)


def ligne(contrat, client, site, jour, statut, no, equipement, quantite, unite, duree, tarif):
    return [contrat, client, site, f'2026-11-{jour:02d}', statut, no, equipement, quantite, unite, duree, tarif]


def ecrire_csv(chemin, lignes, colonnes=COLONNES):
    with chemin.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(colonnes)
        w.writerows(lignes)


def base_dix():
    """10 contrats d'une ligne chacune : quantité 1, 1 jour, tarif 100.00 = 100.00 MAD par ligne.
    Contrats 1 à 6 'paid', 7 et 8 'closed', 9 'draft', 10 'cancelled'  ->  8 x 100 = 800.00 MAD retenus."""
    statuts = ['paid'] * 6 + ['closed'] * 2 + ['draft', 'cancelled']
    return [ligne(c, c, c, c, statuts[c - 1], 1, c, 1, 'day', 1, '100.00') for c in range(1, 11)]


# ------------------------------------------------------------------ les 9 petits lots (sans base)
def unitaires():
    base = base_dix()
    cas = {}
    # U1 : une location à la journée et une à l'heure ; seuls paid et closed comptent
    cas['U1_valide_heure_et_jour'] = [
        ligne(1, 1, 1, 1, 'paid', 1, 5, 2, 'day', 3, '50.00'),       # 2 x 3 x 50 = 300.00
        ligne(2, 2, 2, 2, 'closed', 1, 6, 3, 'hour', 4, '10.00'),    # 3 x 4 x 10 = 120.00
        ligne(3, 3, 3, 3, 'draft', 1, 7, 1, 'day', 1, '100.00'),     # ne compte pas
        ligne(4, 4, 4, 4, 'cancelled', 1, 8, 1, 'hour', 1, '100.00'),  # ne compte pas
    ]
    # U2 : une ligne répétée à l'identique
    cas['U2_doublon_exact'] = base + [list(base[0])]
    # U3 : même clé (contrat 11, ligne 1) mais contenu différent
    cas['U3_conflit_cle_ligne'] = base + [
        ligne(11, 11, 11, 11, 'paid', 1, 11, 1, 'day', 1, '100.00'),
        ligne(11, 11, 11, 11, 'paid', 1, 11, 2, 'day', 1, '100.00')]
    # U4 : une ligne à quantité -3 ; l'autre ligne du contrat est valide mais suit son contrat
    cas['U4_quantite_invalide'] = base + [
        ligne(11, 11, 11, 11, 'paid', 1, 11, -3, 'day', 1, '100.00'),
        ligne(11, 11, 11, 11, 'paid', 2, 12, 1, 'day', 1, '100.00')]
    # U5 : quantité 25 : valide, mais inhabituelle (anomalie, pas de rejet)
    cas['U5_quantite_25'] = base + [ligne(11, 11, 11, 11, 'paid', 1, 11, 25, 'day', 1, '10.00')]
    # U6 : client qui n'existe pas
    cas['U6_client_inconnu'] = base + [ligne(11, CLIENT_INCONNU, 11, 11, 'paid', 1, 11, 1, 'day', 1, '100.00')]
    # U7 : un même contrat avec deux clients différents
    cas['U7_entete_contradictoire'] = base + [
        ligne(11, 11, 11, 11, 'paid', 1, 11, 1, 'day', 1, '100.00'),
        ligne(11, 12, 11, 11, 'paid', 2, 12, 1, 'day', 1, '100.00')]
    # U9 : 4 contrats refusés sur 14 lignes = 28,57 % > 20 %
    cas['U9_alerte_rejet'] = base + [ligne(c, CLIENT_INCONNU, c % 12 + 1, 11, 'paid', 1, c, 1, 'day', 1, '100.00')
                                     for c in range(11, 15)]
    for nom, lignes in cas.items():
        dossier = SORTIE / 'unitaires' / nom
        dossier.mkdir(parents=True)
        ecrire_csv(dossier / 'locations.csv', lignes)
        shutil.copy(SOURCE_REF, dossier / 'referentiels.json')
    # U8 : colonnes fausses (quantity et unit_rate échangées) -> lot refusé
    dossier = SORTIE / 'unitaires' / 'U8_structure_fausse'
    dossier.mkdir(parents=True)
    fausses = list(COLONNES)
    fausses[7], fausses[10] = fausses[10], fausses[7]
    ecrire_csv(dossier / 'locations.csv', base, colonnes=fausses)
    shutil.copy(SOURCE_REF, dossier / 'referentiels.json')


# ------------------------------------------------------------------ lots complets pour surveiller.py
def lot_complet(dossier_flux, numero, lignes, colonnes=COLONNES):
    dossier = SORTIE / dossier_flux / f'lot_{numero:06d}'
    dossier.mkdir(parents=True)
    ecrire_csv(dossier / 'locations.csv', lignes, colonnes)
    shutil.copy(SOURCE_REF, dossier / 'referentiels.json')
    empreintes = {n: hashlib.sha256((dossier / n).read_bytes()).hexdigest()
                  for n in ('locations.csv', 'referentiels.json')}
    manifeste = {'schema_version': 'campusequip-v2', 'campaign_id': CAMPAGNE, 'batch_number': numero,
                 'created_at': '2026-11-05T09:00:00+00:00', 'contracts_requested': len({l[0] for l in lignes}),
                 'rows': len(lignes), 'profile': 'essai', 'files': empreintes}
    (dossier / 'manifest.json').write_text(json.dumps(manifeste, indent=2) + '\n', encoding='utf-8')
    (dossier / 'READY').write_text('', encoding='utf-8')       # le surveillant ne lit que les lots READY


def flux():
    # flux_A : trois lots propres. Total : 9 contrats, 10 lignes, 740.00 MAD (paid + closed)
    lot_complet('flux_A', 1, [
        ligne(1, 1, 1, 1, 'paid', 1, 1, 1, 'day', 1, '100.00'),         # 100.00
        ligne(2, 2, 2, 2, 'closed', 1, 2, 2, 'hour', 3, '10.00'),       # 60.00
        ligne(3, 3, 3, 3, 'draft', 1, 3, 1, 'day', 1, '50.00')])        # ne compte pas
    lot_complet('flux_A', 2, [
        ligne(4, 4, 4, 4, 'paid', 1, 4, 1, 'day', 2, '100.00'),         # 200.00
        ligne(4, 4, 4, 4, 'paid', 2, 5, 1, 'hour', 5, '10.00'),         # 50.00
        ligne(5, 5, 5, 5, 'closed', 1, 6, 1, 'day', 1, '40.00'),        # 40.00
        ligne(6, 6, 6, 6, 'cancelled', 1, 7, 1, 'day', 1, '40.00')])    # ne compte pas
    lot_complet('flux_A', 3, [
        ligne(7, 7, 7, 7, 'paid', 1, 8, 2, 'day', 1, '100.00'),         # 200.00
        ligne(8, 8, 8, 8, 'paid', 1, 9, 1, 'hour', 2, '15.00'),         # 30.00
        ligne(9, 9, 9, 9, 'closed', 1, 10, 3, 'day', 1, '20.00')])      # 60.00
    # flux_B : le contrat 1 est déjà chargé (flux_A) ; ici il revient avec un AUTRE contenu.
    # Le contrat 50 est nouveau et valide, mais le lot entier doit échouer : aucun ajout partiel.
    lot_complet('flux_B', 1, [
        ligne(1, 1, 1, 1, 'paid', 1, 1, 9, 'day', 1, '999.00'),
        ligne(50, 20, 2, 12, 'paid', 1, 20, 1, 'day', 1, '100.00')])
    # flux_C : (1) colonnes fausses -> refusé ; (2) 10 bons contrats (101 à 110) + 4 mauvais (111 à 114) = 28,57 %
    lot_complet('flux_C', 1, base_dix(), colonnes=[COLONNES[0], COLONNES[2], COLONNES[1]] + COLONNES[3:])
    bons = [ligne(c, c - 90, c % 12 + 1, 13, 'paid', 1, c - 90, 1, 'day', 1, '100.00') for c in range(101, 111)]
    mauvais = [ligne(c, CLIENT_INCONNU, c % 12 + 1, 13, 'paid', 1, c - 90, 1, 'day', 1, '100.00')
               for c in range(111, 115)]
    lot_complet('flux_C', 2, bons + mauvais)


def main():
    if not SOURCE_REF.is_file():
        sys.exit(f'Il manque {SOURCE_REF} : lance la commande depuis le dossier CampusEquip_etudiant.')
    if SORTIE.exists():
        shutil.rmtree(SORTIE)                    # on repart toujours d'un état propre
    unitaires()
    flux()
    print(f'Tests prêts dans {SORTIE}/ :')
    for p in sorted(SORTIE.glob('*/*')):
        print('  ', p)


if __name__ == '__main__':
    main()
