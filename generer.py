"""Source fictive CampusEquip v2. Python 3.10+, bibliothèque standard seulement."""
import argparse
import csv
import hashlib
import json
import os
import random
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

COLONNES = ['contract_id', 'client_id', 'site_id', 'start_date', 'status',
            'line_no', 'equipment_id', 'quantity', 'unit', 'duration', 'unit_rate']

def json_write(path, data):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(tmp, path)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def references():
    cities = ['Casablanca', 'Rabat', 'Fès', 'Marrakech', 'Tanger', 'Agadir']
    campuses = [dict(campus_id=i, name=f'Campus {city}') for i, city in enumerate(cities, 1)]
    sites = [dict(site_id=(c['campus_id']-1)*2+j, campus_id=c['campus_id'],
                  name=f"{c['name']} / guichet {j}") for c in campuses for j in (1, 2)]
    categories = [dict(category_id=i, name=n, parent_id=None if i <= 2 else (1 if i <= 4 else 2))
                  for i, n in enumerate(['Audiovisuel', 'Événementiel', 'Image', 'Son', 'Mobilier', 'Éclairage'], 1)]
    return dict(schema_version='campusequip-v2', campuses=campuses, sites=sites,
                clients=[dict(client_id=i, name=f'Association {i:04d}') for i in range(1, 2001)],
                categories=categories,
                equipment=[dict(equipment_id=i, name=f'Équipement {i:03d}', category_id=3+(i-1)%4)
                           for i in range(1, 121)])

def rows_for_batch(number, count, seed, profile):
    rng = random.Random(f'{seed}:{number}')
    rows = []
    for i in range(count):
        cid = (number-1)*count + i+1
        row = dict(contract_id=cid, client_id=rng.randint(1, 2000), site_id=rng.randint(1, 12),
                   start_date=(datetime(2026, 11, 1)+timedelta(days=(cid-1)%21)).date().isoformat(),
                   status=rng.choice(['paid', 'paid', 'closed', 'draft', 'cancelled']))
        lines = []
        for j in range(1, rng.randint(1, 3)+1):
            unit = rng.choice(['hour', 'day'])
            lines.append(dict(row, line_no=j, equipment_id=rng.randint(1, 120), quantity=rng.randint(1, 5),
                              unit=unit, duration=rng.randint(1, 8 if unit == 'hour' else 5),
                              unit_rate=f'{rng.randint(10, 80) if unit == "hour" else rng.randint(80, 300)}.00'))
        # Scénarios pédagogiques reproductibles. Aucun résultat du pipeline n'est fourni.
        scenario = i % 50 if profile == 'mixte' else -1
        if scenario == 0:
            lines.append(dict(lines[0]))  # répétition exacte
        elif scenario == 1:
            lines[0]['quantity'] = -1
        elif scenario == 2:
            lines.append(dict(lines[0], duration=lines[0]['duration']+1))
        elif scenario == 3:
            lines.append(dict(lines[0], line_no=len(lines)+1, client_id=2000 if row['client_id'] != 2000 else 1999))
        elif scenario == 4:
            lines[0]['equipment_id'] = 999999
        elif scenario == 5:
            lines[0]['quantity'] = 25
        rows.extend(lines)
    return rows

def make_batch(out, state):
    number = state['next_batch']
    # Réserver le numéro avant d'écrire : une interruption peut créer un trou, jamais une réutilisation.
    state['next_batch'] += 1
    json_write(out/'generator-state.json', state)
    pending = out/f'.lot_{number:06d}.en_cours'
    pending.mkdir()
    rows = rows_for_batch(number, state['contracts'], state['seed'], state['profile'])
    csvpath = pending/'locations.csv'
    with csvpath.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=COLONNES)
        w.writeheader()
        w.writerows(rows)
    json_write(pending/'referentiels.json', references())
    manifest = dict(schema_version='campusequip-v2', campaign_id=state['campaign_id'], batch_number=number,
                    created_at=datetime.now(timezone.utc).isoformat(), contracts_requested=state['contracts'],
                    rows=len(rows), profile=state['profile'],
                    files={p.name: digest(p) for p in [csvpath, pending/'referentiels.json']})
    json_write(pending/'manifest.json', manifest)
    (pending/'READY').write_text('campusequip-v2\n', encoding='utf-8')
    final = out/f'lot_{number:06d}'
    pending.rename(final)  # publication du dossier complet sur le même disque
    return final, len(rows)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sortie', type=Path, default=Path('flux'))
    p.add_argument('--contrats', type=int, default=1000)
    p.add_argument('--intervalle', type=float, default=10)
    p.add_argument('--lots', type=int, default=0, help='0 : jusqu’à Ctrl+C ; sinon nombre de nouveaux lots')
    p.add_argument('--graine', type=int, default=42)
    p.add_argument('--profil', choices=['propre', 'mixte'], default='mixte')
    a = p.parse_args()
    if a.contrats <= 0 or a.intervalle < 0 or a.lots < 0:
        p.error('contrats > 0 ; intervalle >= 0 ; lots >= 0')
    if a.lots == 0 and a.intervalle < 1:
        p.error('Le mode continu exige un intervalle d’au moins 1 seconde.')
    a.sortie.mkdir(parents=True, exist_ok=True)
    lock = a.sortie/'.generator.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        p.error('Générateur déjà actif ou verrou résiduel : lisez le README avant de retirer le verrou.')
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        statepath = a.sortie/'generator-state.json'
        config = dict(contracts=a.contrats, seed=a.graine, profile=a.profil)
        if statepath.exists():
            state = json.loads(statepath.read_text())
            if any(state.get(k) != v for k, v in config.items()):
                p.error('Gardez les paramètres initiaux ou choisissez un autre dossier et une base neuve.')
        else:
            if any(a.sortie.glob('lot_*')) or any(a.sortie.glob('.lot_*')):
                p.error('Lots présents sans état : utilisez un nouveau dossier, ne réinitialisez pas ce flux.')
            state = dict(config, next_batch=1, campaign_id=str(uuid.uuid4()))
            json_write(statepath, state)
        done = 0
        while a.lots == 0 or done < a.lots:
            target, size = make_batch(a.sortie, state)
            done += 1
            print(f'{target}: {size} lignes publiées', flush=True)
            if a.lots == 0 or done < a.lots:
                time.sleep(a.intervalle)
    except KeyboardInterrupt:
        print('\nGénérateur arrêté. Les lots publiés sont conservés.')
    finally:
        lock.unlink(missing_ok=True)

if __name__ == '__main__':
    main()
