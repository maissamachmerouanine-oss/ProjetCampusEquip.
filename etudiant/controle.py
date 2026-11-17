"""Guide 3 : lire un lot et appliquer les règles de qualité. Aucune base de données ici.

Ordre imposé par le sujet :
  1. contrôler la structure du fichier        (sinon : tout le lot est refusé)
  2. normaliser                               (espaces, minuscules)
  3. supprimer les répétitions exactes        (on garde une seule fois)
  4. vérifier chaque ligne                    (types, bornes, références connues)
  5. vérifier la cohérence de chaque contrat  (en-tête identique, clé de ligne unique)
"""
import csv
import json
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP
from io import StringIO

from etudiant import regles

COLONNES = ['contract_id', 'client_id', 'site_id', 'start_date', 'status',
            'line_no', 'equipment_id', 'quantity', 'unit', 'duration', 'unit_rate']
STATUTS_COMPTES = {'paid', 'closed'}      # seuls ces contrats comptent dans les indicateurs
SEUIL_ALERTE = Decimal('20')              # alerte si le taux de rejet dépasse 20 %
ENTETE_CONTRAT = ('client_id', 'site_id', 'start_date', 'status')   # doivent être identiques


class StructureError(ValueError):
    """Le fichier n'a pas les bonnes colonnes : le lot est refusé avant toute écriture."""


# ---------------------------------------------------------------- 1. lecture + structure
def lire_locations(chemin):
    """Renvoie la liste des lignes brutes : [{'source_row': 2, 'raw': {colonne: texte}}, ...]."""
    texte = chemin.read_bytes().decode('utf-8-sig')       # utf-8-sig retire un éventuel BOM
    lecteur = csv.reader(StringIO(texte, newline=''))
    try:
        entete = next(lecteur)
    except StopIteration:
        raise StructureError('fichier vide') from None
    if [c.strip() for c in entete] != COLONNES:
        raise StructureError('colonnes absentes, en trop ou dans le mauvais ordre')
    lignes = []
    for champs in lecteur:
        if not champs:                                    # ligne vide : ignorée
            continue
        if len(champs) != len(COLONNES):
            raise StructureError(f'ligne {lecteur.line_num} : {len(champs)} champs au lieu de {len(COLONNES)}')
        lignes.append({'source_row': lecteur.line_num, 'raw': dict(zip(COLONNES, champs))})
    if not lignes:
        raise StructureError('lot vide : aucune ligne de location')
    return lignes


def lire_referentiels(chemin):
    """Charge referentiels.json et prépare des ensembles pour vérifier les identifiants."""
    data = json.loads(chemin.read_text(encoding='utf-8'))
    return {
        'clients': {c['client_id'] for c in data['clients']},
        'sites': {s['site_id']: s['campus_id'] for s in data['sites']},   # site -> campus
        'equipements': {e['equipment_id'] for e in data['equipment']},
        'donnees': data,                                  # gardé tel quel pour le chargement SQL
    }


# ---------------------------------------------------------------- 2. normalisation
def normaliser_ligne(raw):
    """Espaces retirés partout ; status et unit en minuscules."""
    ligne = {k: regles.normaliser(v) for k, v in raw.items()}
    ligne['status'] = ligne['status'].lower()
    ligne['unit'] = ligne['unit'].lower()
    return ligne


# ---------------------------------------------------------------- 4. une ligne
def verifier_ligne(norm, ref):
    """Renvoie (valeurs typées, motifs). Si motifs est vide, la ligne est valide."""
    valeurs, motifs = {}, []

    def essayer(cle, fonction, motif):
        try:
            valeurs[cle] = fonction()
        except ValueError:
            valeurs[cle] = None
            motifs.append(motif)

    essayer('contract_id', lambda: regles.entier_positif(norm['contract_id'], 2**63 - 1), 'INVALID_CONTRACT_ID')
    essayer('line_no', lambda: regles.entier_positif(norm['line_no'], 2**31 - 1), 'INVALID_LINE_NO')
    essayer('start_date', lambda: regles.date_iso(norm['start_date']), 'INVALID_START_DATE')
    essayer('unit_rate', lambda: regles.tarif(norm['unit_rate']), 'INVALID_UNIT_RATE')
    essayer('quantity', lambda: regles.entier_positif(norm['quantity'], regles.QUANTITE_MAX), 'INVALID_QUANTITY')

    valeurs['status'] = norm['status']
    if valeurs['status'] not in regles.STATUTS:
        motifs.append('INVALID_STATUS')

    valeurs['unit'] = norm['unit']
    if valeurs['unit'] not in regles.UNITES:
        motifs.append('INVALID_UNIT')
    # la durée dépend de l'unité : on ne la contrôle que si l'unité est connue
    maximum = regles.DUREE_MAX.get(valeurs['unit'], 0)
    essayer('duration', lambda: regles.entier_positif(norm['duration'], maximum), 'INVALID_DURATION')

    # références : l'identifiant doit exister dans le référentiel
    for cle, ensemble, motif in [('client_id', ref['clients'], 'UNKNOWN_CLIENT'),
                                 ('site_id', ref['sites'], 'UNKNOWN_SITE'),
                                 ('equipment_id', ref['equipements'], 'UNKNOWN_EQUIPMENT')]:
        try:
            valeurs[cle] = regles.entier_positif(norm[cle], 2**31 - 1)
            if valeurs[cle] not in ensemble:
                motifs.append(motif)
        except ValueError:
            valeurs[cle] = None
            motifs.append('INVALID_' + cle.upper())
    return valeurs, motifs


def montant(valeurs):
    """Montant d'une ligne = quantité x durée x tarif par unité (en MAD, Decimal)."""
    return valeurs['quantity'] * valeurs['duration'] * valeurs['unit_rate']


# ---------------------------------------------------------------- tout le lot
def controler(lignes, ref):
    """Applique les étapes 2 à 5. Renvoie accepted, rejected, duplicates, anomalies, report."""
    # 2 + 3 : normaliser puis retirer les répétitions exactes (on garde la première)
    vues, doublons, uniques = set(), [], []
    for ligne in lignes:
        norm = normaliser_ligne(ligne['raw'])
        signature = tuple(norm[c] for c in COLONNES)
        if signature in vues:
            doublons.append({'source_row': ligne['source_row'], 'reason': 'EXACT_DUPLICATE'})
        else:
            vues.add(signature)
            uniques.append({'source_row': ligne['source_row'], 'raw': ligne['raw'], 'norm': norm})

    # 4 : chaque ligne séparément
    for ligne in uniques:
        ligne['values'], ligne['reasons'] = verifier_ligne(ligne['norm'], ref)

    # 5 : chaque contrat comme un tout
    contrats = defaultdict(list)
    for ligne in uniques:
        if ligne['values']['contract_id'] is not None:
            contrats[ligne['values']['contract_id']].append(ligne)
    for groupe in contrats.values():
        entetes = {tuple(l['norm'][c] for c in ENTETE_CONTRAT) for l in groupe}
        if len(entetes) > 1:                                  # client, site, date ou statut qui diffèrent
            for l in groupe:
                l['reasons'].append('CONTRACT_HEADER_CONFLICT')
        cles = Counter(l['values']['line_no'] for l in groupe if l['values']['line_no'] is not None)
        for l in groupe:
            if cles[l['values']['line_no']] > 1:              # même clé (contrat, ligne), contenu différent
                l['reasons'].append('LINE_KEY_CONFLICT')
        if any(l['reasons'] for l in groupe):                 # un problème : tout le contrat est isolé
            for l in groupe:
                if not l['reasons']:
                    l['reasons'].append('CONTRACT_QUARANTINED')

    acceptees = [l for l in uniques if not l['reasons']]
    rejetees = [l for l in uniques if l['reasons']]
    anomalies = [{'source_row': l['source_row'], 'contract_id': l['values']['contract_id'],
                  'reason': 'QUANTITY_ABOVE_20', 'quantity': l['values']['quantity']}
                 for l in acceptees if regles.quantite_signalee(l['values']['quantity'])]

    apres_dedoublonnage = len(uniques)
    taux = (Decimal(len(rejetees)) * 100 / apres_dedoublonnage).quantize(Decimal('0.01'), ROUND_HALF_UP) \
        if apres_dedoublonnage else Decimal('0.00')
    comptes = sum((montant(l['values']) for l in acceptees if l['values']['status'] in STATUTS_COMPTES),
                  Decimal('0.00'))
    rapport = {
        'lignes_recues': len(lignes),
        'doublons_retires': len(doublons),
        'lignes_apres_dedoublonnage': apres_dedoublonnage,
        'lignes_acceptees': len(acceptees),
        'contrats_acceptes': len({l['values']['contract_id'] for l in acceptees}),
        'lignes_rejetees': len(rejetees),
        'contrats_en_quarantaine': len({l['values']['contract_id'] for l in rejetees
                                        if l['values']['contract_id'] is not None}),
        'anomalies': len(anomalies),
        'taux_de_rejet_pct': str(taux),
        'alertes': ['TAUX_DE_REJET_ELEVE'] if taux > SEUIL_ALERTE else [],
        'motifs': dict(Counter(m for l in rejetees for m in l['reasons'])),
        'montant_retenu_mad': str(comptes),        # paid + closed seulement
    }
    # contrôle de bon sens : aucune ligne ne doit disparaître
    assert rapport['lignes_recues'] == rapport['doublons_retires'] + rapport['lignes_acceptees'] + rapport['lignes_rejetees']
    return {'accepted': acceptees, 'rejected': rejetees, 'duplicates': doublons,
            'anomalies': anomalies, 'report': rapport}
