"""Guide 6 : relance les 9 petits tests U1 à U9 et écrit UNE ligne de résultat par test.

    python observer_unitaires.py

Ce programme ne donne pas l'attendu : il affiche seulement ce que ton code (controle.py) a trouvé.
Tu copies ces lignes dans fiche_tests.md (colonne « Observé ») et tu les compares à l'attendu.
Il faut d'abord avoir lancé : python generer_tests.py
"""
import sys
from pathlib import Path

from etudiant import controle

DOSSIER = Path('essais_preuves/unitaires')

if not DOSSIER.is_dir():
    sys.exit('Dossier essais_preuves introuvable : lance d\'abord  python generer_tests.py')

for lot in sorted(DOSSIER.iterdir()):
    nom = lot.name
    try:
        lignes = controle.lire_locations(lot / 'locations.csv')
    except controle.StructureError as e:
        print(f'{nom} : REJETE_STRUCTURE ({e}) ; rien n\'est lu ni écrit')
        continue
    r = controle.controler(lignes, controle.lire_referentiels(lot / 'referentiels.json'))['report']
    motifs = ', '.join(f'{m} x{n}' for m, n in r['motifs'].items()) or 'aucun'
    alerte = ', '.join(r['alertes']) or 'aucune'
    print(f"{nom} : {r['lignes_recues']} reçues, {r['doublons_retires']} doublon(s) retiré(s), "
          f"{r['lignes_acceptees']} acceptées, {r['lignes_rejetees']} rejetées "
          f"({r['contrats_en_quarantaine']} contrat(s) en quarantaine), {r['anomalies']} anomalie(s), "
          f"taux {r['taux_de_rejet_pct']} %, alerte : {alerte}, motifs : {motifs}, "
          f"montant retenu {r['montant_retenu_mad']} MAD")
