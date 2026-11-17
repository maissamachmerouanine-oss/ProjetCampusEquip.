"""Guide 3 : contrôle un lot SANS toucher à la base. Sert à voir le rapport et la quarantaine.

Exemples :
    python controle_lot.py exemples/lot_000001
    python controle_lot.py essai/lot_000001 --quarantaine quarantaine_lot1.jsonl
"""
import argparse
import json
import sys
from pathlib import Path

from etudiant import controle


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('dossier', type=Path, help='dossier du lot, par exemple exemples/lot_000001')
    p.add_argument('--quarantaine', type=Path, help='fichier où écrire les lignes rejetées (JSON, une par ligne)')
    a = p.parse_args()

    try:
        lignes = controle.lire_locations(a.dossier / 'locations.csv')
    except controle.StructureError as e:
        print(f'REJETE_STRUCTURE : {e}')
        return 1
    ref = controle.lire_referentiels(a.dossier / 'referentiels.json')
    resultat = controle.controler(lignes, ref)

    print('--- Rapport ---')
    print(json.dumps(resultat['report'], indent=2, ensure_ascii=False))
    print('\n--- Anomalies (acceptées mais signalées) ---')
    for an in resultat['anomalies']:
        print(f"  ligne {an['source_row']} : contrat {an['contract_id']}, quantité {an['quantity']}")
    print('\n--- Quarantaine (10 premières lignes) ---')
    for l in resultat['rejected'][:10]:
        print(f"  ligne {l['source_row']} : contrat {l['values']['contract_id']} -> {', '.join(l['reasons'])}")

    if a.quarantaine:
        with a.quarantaine.open('w', encoding='utf-8') as f:
            for l in resultat['rejected']:
                f.write(json.dumps({'source_row': l['source_row'], 'raw': l['raw'], 'reasons': l['reasons']},
                                   ensure_ascii=False) + '\n')
        print(f"\nQuarantaine écrite dans {a.quarantaine}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
