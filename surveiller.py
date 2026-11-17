"""Boucle fournie. Complétez etudiant/traitement.py pour charger les locations."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from etudiant.traitement import traiter_lot

def preflight(folder):
    manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema_version') != 'campusequip-v2':
        raise ValueError('Version de source incompatible')
    if set(manifest.get('files', {})) != {'locations.csv', 'referentiels.json'}:
        raise ValueError('Le manifeste doit décrire exactement les deux fichiers attendus')
    for name, expected in manifest['files'].items():
        actual = hashlib.sha256((folder/name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f'Empreinte incorrecte : {name}')
    return manifest

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--entree', type=Path, default=Path('flux'))
    p.add_argument('--intervalle', type=float, default=2)
    p.add_argument('--une-fois', action='store_true')
    a = p.parse_args()
    if a.intervalle < 1:
        p.error('intervalle >= 1')
    visited = set()
    failed = False
    try:
        while True:
            failed = False
            for folder in sorted(a.entree.glob('lot_*')):
                if not folder.is_dir() or not (folder/'READY').is_file() or folder.name in visited:
                    continue
                try:
                    manifest = preflight(folder)
                    result = traiter_lot(folder, manifest)
                    if not isinstance(result, dict) or result.get('status') not in {'CHARGE', 'DEJA_CHARGE', 'REJETE_STRUCTURE'}:
                        raise ValueError('traiter_lot doit renvoyer un statut documenté')
                    visited.add(folder.name)
                    print(folder.name, result, flush=True)
                except NotImplementedError as e:
                    p.exit(2, f'{e}\n')
                except Exception as e:
                    failed = True
                    print(f'{folder.name}: ECHEC {type(e).__name__}: {e}', flush=True)
                    # Garder l'ordre : ne pas dépasser un lot en échec temporaire.
                    break
            if a.une_fois:
                return 1 if failed else 0
            time.sleep(a.intervalle)
    except KeyboardInterrupt:
        print('\nSurveillance arrêtée. Le journal SQL permet la reprise.')
        return 0

if __name__ == '__main__':
    raise SystemExit(main())
