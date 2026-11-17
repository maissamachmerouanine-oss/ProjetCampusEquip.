"""Petites règles de lecture : chaque fonction valide UNE valeur et lève ValueError si elle est fausse.

On ne "répare" jamais une valeur : si elle est invalide, on la signale (le sujet l'interdit).
"""
import re
from datetime import date
from decimal import Decimal

STATUTS = {'paid', 'closed', 'draft', 'cancelled'}
UNITES = {'hour', 'day'}
DUREE_MAX = {'hour': 720, 'day': 365}     # 1 à 720 heures ou 1 à 365 jours
QUANTITE_MIN, QUANTITE_MAX = 1, 100
QUANTITE_SIGNALEE = 20                    # au-delà de 20 : anomalie, mais pas un rejet
TARIF_MAX = Decimal('99999999.99')        # limite de NUMERIC(10,2)


def normaliser(valeur):
    """Retire les espaces autour d'une valeur. Les valeurs None deviennent ''."""
    return (valeur or '').strip()


def entier_positif(texte, maximum):
    """'12' -> 12. Refuse '-3', '3.0', '1e3', '', '0', ' ' ou un nombre trop grand."""
    texte = normaliser(texte)
    if not re.fullmatch(r'[0-9]+', texte):          # chiffres uniquement
        raise ValueError('entier attendu')
    valeur = int(texte)
    if not 1 <= valeur <= maximum:
        raise ValueError('hors limites')
    return valeur


def tarif(texte):
    """'25' ou '25.50' -> Decimal. Refuse la virgule, l'exposant, le négatif, NaN, inf."""
    texte = normaliser(texte)
    if not re.fullmatch(r'[0-9]+(\.[0-9]{1,2})?', texte):   # point + 2 décimales maximum
        raise ValueError('tarif invalide')
    valeur = Decimal(texte)
    if valeur > TARIF_MAX:
        raise ValueError('tarif trop grand')
    return valeur


def date_iso(texte):
    """'2026-11-02' -> date. Refuse '02/11/2026' et les dates qui n'existent pas ('2026-02-30')."""
    texte = normaliser(texte)
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', texte):
        raise ValueError('format YYYY-MM-DD attendu')
    return date.fromisoformat(texte)       # lève ValueError si la date n'existe pas


def quantite_signalee(quantite):
    """Vrai si la quantité est valide mais inhabituelle (plus de 20)."""
    return quantite > QUANTITE_SIGNALEE
