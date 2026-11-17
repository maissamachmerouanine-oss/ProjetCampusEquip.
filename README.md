"""Guide 4 : traiter un lot de bout en bout (contrôles, signature, chargement, rapport).

Le surveillant (surveiller.py) appelle traiter_lot(dossier, manifeste) pour chaque nouveau lot.
La fonction renvoie un dictionnaire avec un statut :
    CHARGE            le lot est nouveau : les contrats acceptés sont écrits dans la base
    DEJA_CHARGE       ce contenu a déjà été chargé : rien n'est ajouté
    REJETE_STRUCTURE  les colonnes sont fausses : le lot est refusé, aucune écriture
Une panne ou un conflit LÈVE une erreur (elle reste visible, ce n'est jamais un succès).

La connexion à la base vient de la variable d'environnement CAMPUS_DSN (aucun secret dans le code).
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg

from etudiant import controle

RULES_VERSION = 'campusequip-v2.0'
DOSSIER_RAPPORTS = Path('rapports')       # rapports et quarantaines : un fichier par tentative
VERROU = (28, 2026)                       # verrou PostgreSQL : un seul chargement à la fois


class ChargementError(RuntimeError):
    """Un chargement n'a pas pu avoir lieu : la transaction est annulée et l'échec reste visible."""


# ---------------------------------------------------------------- signature
def sha256_fichier(chemin):
    """Empreinte SHA-256 d'un fichier (lu par morceaux)."""
    h = hashlib.sha256()
    with open(chemin, 'rb') as f:
        for morceau in iter(lambda: f.read(65536), b''):
            h.update(morceau)
    return h.hexdigest()


def calculer_signature(empreinte_locations, empreinte_referentiels):
    """Signature du lot = empreintes des 2 fichiers + version des règles.
    Le nom du dossier n'y entre pas : un dossier renommé garde la même signature."""
    texte = f'{empreinte_locations}:{empreinte_referentiels}:{RULES_VERSION}'
    return hashlib.sha256(texte.encode('utf-8')).hexdigest()


# ---------------------------------------------------------------- rapports (un fichier par tentative)
def ecrire_rapport(manifeste, rapport, rejetees):
    """Écrit le rapport (JSON) et la quarantaine (une ligne JSON par ligne rejetée)."""
    DOSSIER_RAPPORTS.mkdir(parents=True, exist_ok=True)
    instant = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')    # rend chaque tentative unique
    base = f"lot_{manifeste['batch_number']:06d}_{instant}"
    chemin_rapport = DOSSIER_RAPPORTS / f'{base}_rapport.json'
    chemin_rapport.write_text(json.dumps(rapport, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    if rejetees:
        with (DOSSIER_RAPPORTS / f'{base}_quarantaine.jsonl').open('w', encoding='utf-8') as f:
            for l in rejetees:
                f.write(json.dumps({'source_row': l['source_row'], 'raw': l['raw'], 'reasons': l['reasons']},
                                   ensure_ascii=False) + '\n')
    return chemin_rapport


# ---------------------------------------------------------------- écriture dans la base
def inserer_referentiels(conn, donnees):
    """Les référentiels sont fixes dans une campagne : on les écrit une fois (ON CONFLICT = sans effet ensuite)."""
    cur = conn.cursor()
    cur.executemany('INSERT INTO campus (campus_id, name) VALUES (%s, %s) ON CONFLICT DO NOTHING',
                    [(c['campus_id'], c['name']) for c in donnees['campuses']])
    cur.executemany('INSERT INTO sites (site_id, campus_id, name) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING',
                    [(s['site_id'], s['campus_id'], s['name']) for s in donnees['sites']])
    cur.executemany('INSERT INTO clients (client_id, name) VALUES (%s, %s) ON CONFLICT DO NOTHING',
                    [(c['client_id'], c['name']) for c in donnees['clients']])
    # une catégorie doit être écrite APRÈS son parent
    restantes, ecrites = list(donnees['categories']), set()
    while restantes:
        pretes = [c for c in restantes if c['parent_id'] is None or c['parent_id'] in ecrites]
        if not pretes:
            raise ChargementError('catégories : parent introuvable dans le référentiel')
        cur.executemany('INSERT INTO categories (category_id, name, parent_id) VALUES (%s, %s, %s) '
                        'ON CONFLICT DO NOTHING', [(c['category_id'], c['name'], c['parent_id']) for c in pretes])
        ecrites |= {c['category_id'] for c in pretes}
        restantes = [c for c in restantes if c['category_id'] not in ecrites]
    cur.executemany('INSERT INTO equipments (equipment_id, name, category_id) VALUES (%s, %s, %s) '
                    'ON CONFLICT DO NOTHING',
                    [(e['equipment_id'], e['name'], e['category_id']) for e in donnees['equipment']])


def charger(conn, manifeste, signature, empreintes, ref, resultat, rapport):
    """Tout se passe dans UNE transaction (celle de `with psycopg.connect(...)` dans traiter_lot)."""
    conn.execute('SELECT pg_advisory_xact_lock(%s, %s)', VERROU)

    # 1) une seule campagne par base : la première est mémorisée, une autre est refusée
    ligne = conn.execute("SELECT value FROM lab_config WHERE key = 'campaign_id'").fetchone()
    if ligne is None:
        conn.execute("INSERT INTO lab_config (key, value) VALUES ('campaign_id', %s)", (manifeste['campaign_id'],))
    elif ligne[0] != manifeste['campaign_id']:
        raise ChargementError(f"campagne {manifeste['campaign_id']} refusée : cette base est réservée à la "
                              f"campagne {ligne[0]}")

    # 2) rejeu : cette signature est déjà dans le journal -> on n'ajoute rien
    if conn.execute('SELECT 1 FROM ingestion_batches WHERE batch_signature = %s', (signature,)).fetchone():
        return 'DEJA_CHARGE'

    # 3) un contract_id déjà chargé ne doit jamais être écrasé : la transaction entière échoue
    lignes = [l['values'] for l in resultat['accepted']]
    ids = sorted({v['contract_id'] for v in lignes})
    if ids:
        deja = conn.execute('SELECT contract_id FROM contracts WHERE contract_id = ANY(%s)', (ids,)).fetchall()
        if deja:
            exemples = ', '.join(str(r[0]) for r in deja[:5])
            raise ChargementError(f'{len(deja)} contrat(s) déjà chargé(s) avec un nouveau contenu '
                                  f'(par exemple : {exemples}) : lot annulé, rien n\'est ajouté')

    # 4) écriture : référentiels, contrats, lignes, puis journal du lot (tout ou rien)
    inserer_referentiels(conn, ref['donnees'])
    cur = conn.cursor()
    entetes = {}
    for v in lignes:                                       # l'en-tête est identique sur toutes les lignes
        entetes.setdefault(v['contract_id'], (v['contract_id'], v['client_id'], v['site_id'],
                                              v['start_date'], v['status']))
    cur.executemany('INSERT INTO contracts (contract_id, client_id, site_id, start_date, status) '
                    'VALUES (%s, %s, %s, %s, %s)', list(entetes.values()))
    cur.executemany('INSERT INTO contract_lines (contract_id, line_no, equipment_id, quantity, unit, duration, '
                    'unit_rate) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                    [(v['contract_id'], v['line_no'], v['equipment_id'], v['quantity'], v['unit'],
                      v['duration'], v['unit_rate']) for v in lignes])
    rapport['lignes_ajoutees_en_base'] = len(lignes)
    rapport['contrats_ajoutes_en_base'] = len(entetes)
    rapport['statut'] = 'CHARGE'
    conn.execute('INSERT INTO ingestion_batches (batch_signature, campaign_id, batch_number, rules_version, '
                 'locations_sha256, referentiels_sha256, accepted_contracts, accepted_lines, report) '
                 'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)',
                 (signature, manifeste['campaign_id'], manifeste['batch_number'], RULES_VERSION,
                  empreintes[0], empreintes[1], len(entetes), len(lignes), json.dumps(rapport)))
    return 'CHARGE'


# ---------------------------------------------------------------- la fonction appelée par le surveillant
def traiter_lot(dossier, manifeste):
    dossier = Path(dossier)
    dsn = os.environ.get('CAMPUS_DSN')
    if not dsn:
        raise ChargementError('variable CAMPUS_DSN absente : voir le README (connexion à la base)')

    # 1) structure du fichier : si elle est fausse, le lot est refusé AVANT toute écriture
    try:
        lignes = controle.lire_locations(dossier / 'locations.csv')
    except controle.StructureError as e:
        rapport = {'statut': 'REJETE_STRUCTURE', 'lot': dossier.name, 'motif': str(e),
                   'lignes_ajoutees_en_base': 0}
        chemin = ecrire_rapport(manifeste, rapport, [])
        return {'status': 'REJETE_STRUCTURE', 'motif': str(e), 'lignes_ajoutees_en_base': 0,
                'rapport': str(chemin)}

    # 2) contrôles de qualité (voir controle.py) + signature du lot
    ref = controle.lire_referentiels(dossier / 'referentiels.json')
    resultat = controle.controler(lignes, ref)
    empreintes = (sha256_fichier(dossier / 'locations.csv'), sha256_fichier(dossier / 'referentiels.json'))
    signature = calculer_signature(*empreintes)
    rapport = dict(resultat['report'], lot=dossier.name, batch_number=manifeste['batch_number'],
                   campaign_id=manifeste['campaign_id'], signature=signature, rules_version=RULES_VERSION,
                   lignes_ajoutees_en_base=0, contrats_ajoutes_en_base=0)
    if rapport['alertes']:
        print(f"ALERTE {dossier.name} : taux de rejet {rapport['taux_de_rejet_pct']} % (seuil 20 %)", flush=True)

    # 3) chargement : une transaction. `with` valide (commit) au succès et annule (rollback) sur erreur.
    try:
        with psycopg.connect(dsn) as conn:
            statut = charger(conn, manifeste, signature, empreintes, ref, resultat, rapport)
    except Exception as e:
        rapport.update(statut='ECHEC', erreur=f'{type(e).__name__}: {e}',
                       lignes_ajoutees_en_base=0, contrats_ajoutes_en_base=0)
        ecrire_rapport(manifeste, rapport, resultat['rejected'])
        raise                                              # l'échec reste visible pour le surveillant

    if statut == 'DEJA_CHARGE':                            # rejeu : rien n'a été ajouté
        rapport['lignes_ajoutees_en_base'] = 0
        rapport['contrats_ajoutes_en_base'] = 0
    rapport['statut'] = statut
    chemin = ecrire_rapport(manifeste, rapport, resultat['rejected'])
    return {'status': statut, 'lot': dossier.name,
            'lignes_recues': rapport['lignes_recues'],
            'lignes_ajoutees_en_base': rapport['lignes_ajoutees_en_base'],
            'contrats_ajoutes_en_base': rapport['contrats_ajoutes_en_base'],
            'lignes_rejetees': rapport['lignes_rejetees'],
            'taux_de_rejet_pct': rapport['taux_de_rejet_pct'],
            'alertes': rapport['alertes'], 'rapport': str(chemin)}
