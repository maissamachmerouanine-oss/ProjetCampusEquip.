"""Bonus 3 : fabrique un GROS lot de test (locations.csv) avec des cas de qualité mélangés.

Les lignes sont mélangées : les lignes d'un même contrat sont éparpillées dans le fichier.
Usage :  python generer_gros_lot.py --contrats 20000
Résultat : gros_lot/locations.csv et gros_lot/referentiels.json
"""
import argparse
import csv
import json
import random
import shutil
from pathlib import Path

REFERENTIELS = Path('exemples/lot_000001/referentiels.json')
SORTIE = Path('gros_lot')
COLONNES = ['contract_id', 'client_id', 'site_id', 'start_date', 'status',
            'line_no', 'equipment_id', 'quantity', 'unit', 'duration', 'unit_rate']


def fabriquer(nb_contrats, graine=2026):
    hasard = random.Random(graine)
    ref = json.loads(REFERENTIELS.read_text(encoding='utf-8'))
    clients = [c['client_id'] for c in ref['clients']]
    sites = [s['site_id'] for s in ref['sites']]
    equipements = [e['equipment_id'] for e in ref['equipment']]
    lignes = []
    for n in range(1, nb_contrats + 1):
        client, site = hasard.choice(clients), hasard.choice(sites)
        date = f'2026-11-{hasard.randint(1, 21):02d}'
        statut = hasard.choice(['paid', 'closed', 'draft', 'cancelled'])
        contrat = []
        for no in range(1, hasard.randint(2, 4) + 1):
            unite = hasard.choice(['hour', 'day'])
            contrat.append([n, client, site, date, statut, no, hasard.choice(equipements),
                            hasard.randint(1, 10), unite, hasard.randint(1, 12),
                            f'{hasard.randint(20, 300)}.00'])
        # cas de qualité injectés régulièrement (de quoi tester toutes les décisions)
        if n % 97 == 0:
            contrat.append(list(contrat[0]))                       # doublon exact
        if n % 53 == 0:
            autre = list(contrat[0]); autre[7] = 9                 # même clé de ligne, autre contenu
            contrat.append(autre)
        if n % 71 == 0:
            contrat[0][7] = -3                                     # quantité invalide
        if n % 89 == 0:
            contrat[-1][1] = 999999                                # client inconnu
        if n % 61 == 0 and len(contrat) > 1:
            contrat[-1][4] = 'paid' if statut != 'paid' else 'draft'   # en-tête contradictoire
        if n % 41 == 0:
            contrat[0][7] = 25                                     # quantité > 20 : anomalie seulement
        lignes.extend(contrat)
    hasard.shuffle(lignes)                                         # lignes d'un contrat éparpillées
    return ref, lignes


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--contrats', type=int, default=20000)
    a = p.parse_args()
    ref, lignes = fabriquer(a.contrats)
    SORTIE.mkdir(exist_ok=True)
    with (SORTIE / 'locations.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(COLONNES)
        w.writerows(lignes)
    shutil.copy(REFERENTIELS, SORTIE / 'referentiels.json')
    print(f'{len(lignes)} lignes écrites dans {SORTIE / "locations.csv"} ({a.contrats} contrats)')


if __name__ == '__main__':
    main()
