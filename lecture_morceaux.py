"""Bonus 3 : lire un gros lot PAR MORCEAUX, sans couper un contrat, et prouver les mêmes décisions.

Principe (2 passes) :
  1) on lit le fichier ligne par ligne (jamais en entier) et on range chaque ligne dans un morceau
     choisi d'après le numéro de contrat : toutes les lignes d'un même contrat vont dans le MÊME morceau ;
  2) on contrôle les morceaux un par un avec les règles de controle.py, puis on additionne les résultats.
Preuve : on refait le contrôle en lecture complète et on compare ligne par ligne.

Usage :  python lecture_morceaux.py gros_lot --morceaux 8
"""
import argparse
import csv
import json
import tempfile
import zlib
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from io import StringIO
from pathlib import Path

from etudiant import controle, regles


def cle_contrat(brut):
    """Clé qui décide du morceau : le numéro de contrat (' 12', '12' et '012' donnent la même clé)."""
    texte = regles.normaliser(brut)
    try:
        return str(regles.entier_positif(texte, 2**63 - 1))
    except ValueError:
        return 'x:' + texte                                  # numéro invalide : clé = le texte lui-même


def numero_morceau(cle, nb):
    return zlib.crc32(cle.encode('utf-8')) % nb


def lire_en_flux(chemin):
    """Comme controle.lire_locations, mais ligne par ligne (même contrôle de structure)."""
    with open(chemin, encoding='utf-8-sig', newline='') as f:
        lecteur = csv.reader(f)
        try:
            entete = next(lecteur)
        except StopIteration:
            raise controle.StructureError('fichier vide') from None
        if [c.strip() for c in entete] != controle.COLONNES:
            raise controle.StructureError('colonnes absentes, en trop ou dans le mauvais ordre')
        for champs in lecteur:
            if not champs:
                continue
            if len(champs) != len(controle.COLONNES):
                raise controle.StructureError(
                    f'ligne {lecteur.line_num} : {len(champs)} champs au lieu de {len(controle.COLONNES)}')
            yield {'source_row': lecteur.line_num, 'raw': dict(zip(controle.COLONNES, champs))}


def repartir(chemin, dossier, nb):
    """Passe 1 : range les lignes dans nb fichiers temporaires. Renvoie le nombre de lignes par morceau."""
    fichiers = [open(dossier / f'morceau_{i}.jsonl', 'w', encoding='utf-8') for i in range(nb)]
    tailles = [0] * nb
    try:
        for ligne in lire_en_flux(chemin):
            i = numero_morceau(cle_contrat(ligne['raw']['contract_id']), nb)
            fichiers[i].write(json.dumps(ligne, ensure_ascii=False) + '\n')
            tailles[i] += 1
    finally:
        for f in fichiers:
            f.close()
    return tailles


def controler_par_morceaux(chemin, ref, nb):
    """Passe 2 : contrôle chaque morceau avec controle.controler, puis fusionne les résultats."""
    with tempfile.TemporaryDirectory() as tmp:
        dossier = Path(tmp)
        tailles = repartir(chemin, dossier, nb)
        fusion = {'accepted': [], 'rejected': [], 'duplicates': [], 'anomalies': []}
        total = Counter()
        motifs = Counter()
        montant = Decimal('0.00')
        for i in range(nb):
            with open(dossier / f'morceau_{i}.jsonl', encoding='utf-8') as f:
                lignes = [json.loads(l) for l in f]
            if not lignes:
                continue
            res = controle.controler(lignes, ref)          # exactement les mêmes règles que la lecture complète
            for cle in fusion:
                fusion[cle].extend(res[cle])
            r = res['report']
            for cle in ('lignes_recues', 'doublons_retires', 'lignes_apres_dedoublonnage', 'lignes_acceptees',
                        'contrats_acceptes', 'lignes_rejetees', 'contrats_en_quarantaine', 'anomalies'):
                total[cle] += r[cle]
            motifs.update(r['motifs'])
            montant += Decimal(r['montant_retenu_mad'])
    taux = (Decimal(total['lignes_rejetees']) * 100 / total['lignes_apres_dedoublonnage']).quantize(
        Decimal('0.01'), ROUND_HALF_UP) if total['lignes_apres_dedoublonnage'] else Decimal('0.00')
    fusion['report'] = dict(total, taux_de_rejet_pct=str(taux), motifs=dict(motifs),
                            montant_retenu_mad=str(montant))
    return fusion, tailles


def controler_en_tranches_aveugles(chemin, ref, nb):
    """CONTRE-EXEMPLE : on coupe le fichier tous les N lignes, sans regarder les contrats.
    Les lignes d'un même contrat se retrouvent dans des tranches différentes : les décisions changent."""
    lignes = list(lire_en_flux(chemin))
    taille = -(-len(lignes) // nb)
    fusion = {'accepted': [], 'rejected': [], 'duplicates': [], 'anomalies': []}
    for i in range(0, len(lignes), taille):
        res = controle.controler(lignes[i:i + taille], ref)
        for cle in fusion:
            fusion[cle].extend(res[cle])
    return fusion


def decisions(res):
    """Ce qui a été décidé pour CHAQUE ligne du fichier d'origine (repérée par son numéro de ligne)."""
    return {
        'acceptees': sorted(l['source_row'] for l in res['accepted']),
        'rejetees': sorted((l['source_row'], tuple(sorted(l['reasons']))) for l in res['rejected']),
        'doublons': sorted(d['source_row'] for d in res['duplicates']),
        'anomalies': sorted(a['source_row'] for a in res['anomalies']),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument('lot', help='dossier du lot (locations.csv + referentiels.json)')
    p.add_argument('--morceaux', type=int, default=8)
    p.add_argument('--contre-exemple', action='store_true',
                   help='montre ce qui se passe si on coupe le fichier sans respecter les contrats')
    a = p.parse_args()
    lot = Path(a.lot)
    ref = controle.lire_referentiels(lot / 'referentiels.json')

    par_morceaux, tailles = controler_par_morceaux(lot / 'locations.csv', ref, a.morceaux)
    complet = controle.controler(controle.lire_locations(lot / 'locations.csv'), ref)

    print(f'Lecture par morceaux : {a.morceaux} morceaux, le plus gros contient {max(tailles)} lignes '
          f'sur {sum(tailles)} (jamais le fichier entier en mémoire)')
    d1, d2 = decisions(par_morceaux), decisions(complet)
    print(f'{"":28}{"par morceaux":>14}{"lecture complète":>18}')
    for cle in ('lignes_recues', 'doublons_retires', 'lignes_acceptees', 'lignes_rejetees',
                'contrats_acceptes', 'contrats_en_quarantaine', 'anomalies', 'taux_de_rejet_pct',
                'montant_retenu_mad'):
        print(f'{cle:28}{str(par_morceaux["report"][cle]):>14}{str(complet["report"][cle]):>18}')
    print('motifs identiques :', par_morceaux['report']['motifs'] == complet['report']['motifs'])
    identiques = d1 == d2
    print(f'décision identique pour chacune des {sum(tailles)} lignes :', 'OUI' if identiques else 'NON')
    if a.contre_exemple:
        aveugle = decisions(controler_en_tranches_aveugles(lot / 'locations.csv', ref, a.morceaux))
        diff = (len(set(aveugle['acceptees']) ^ set(d2['acceptees'])) + len(set(aveugle['rejetees']) ^ set(d2['rejetees'])))
        print(f'Contre-exemple (coupure tous les N lignes, contrats coupés) : {diff} décisions différentes de la '
              f'lecture complète -> identique : {"OUI" if aveugle == d2 else "NON"}')
    raise SystemExit(0 if identiques else 1)


if __name__ == '__main__':
    main()
