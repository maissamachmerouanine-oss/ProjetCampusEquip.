"""Guide 5 : dessine le graphique de l'analyse 1 (montant cumulé par campus, 1er au 21 novembre 2026).

Il faut avoir installé matplotlib :  pip install matplotlib
La connexion se donne comme d'habitude par la variable CAMPUS_DSN (aucun mot de passe dans ce fichier).
Résultat : un fichier graphique_cumul.png dans le dossier courant.
"""
import os
import sys
from collections import defaultdict

import matplotlib
matplotlib.use('Agg')                      # dessine dans un fichier, sans ouvrir de fenêtre
import matplotlib.pyplot as plt
import psycopg

REQUETE = """
WITH jours AS (
    SELECT d::date AS jour FROM generate_series('2026-11-01'::date, '2026-11-21'::date, '1 day') AS d
),
montants AS (
    SELECT campus_id, start_date AS jour, SUM(amount) AS montant
    FROM line_amounts WHERE status IN ('paid', 'closed') GROUP BY campus_id, start_date
)
SELECT ca.name, j.jour,
       SUM(COALESCE(m.montant, 0)) OVER (PARTITION BY ca.campus_id ORDER BY j.jour
                                         ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumul
FROM campus ca CROSS JOIN jours j
LEFT JOIN montants m ON m.campus_id = ca.campus_id AND m.jour = j.jour
ORDER BY ca.campus_id, j.jour
"""

dsn = os.environ.get('CAMPUS_DSN')
if not dsn:
    sys.exit('La variable CAMPUS_DSN est vide : voir le Guide 2.')

with psycopg.connect(dsn) as conn:
    lignes = conn.execute(REQUETE).fetchall()

courbes = defaultdict(lambda: ([], []))            # campus -> (jours, cumuls)
for campus, jour, cumul in lignes:
    jours, cumuls = courbes[campus]
    jours.append(int(str(jour)[8:10]))             # numéro du jour dans novembre
    cumuls.append(float(cumul))
if not courbes:
    sys.exit('Aucune donnée : chargez d\'abord les lots (Guide 4).')

champion = max(courbes, key=lambda c: courbes[c][1][-1])
total = courbes[champion][1][-1]

fig, ax = plt.subplots(figsize=(10, 5.5))
for campus, (jours, cumuls) in courbes.items():
    epais = 3 if campus == champion else 1.6      # le campus en tête est mis en avant
    ax.plot(jours, cumuls, linewidth=epais, label=campus)
ax.set_title(f'{champion} réalise le plus fort montant : {total:,.0f} MAD du 1er au 21 novembre 2026'.replace(',', ' '),
             fontsize=12, loc='left')
ax.set_xlabel('Jour de novembre 2026 (date de début du contrat)')
ax.set_ylabel('Montant cumulé (MAD)')
ax.set_xticks(range(1, 22, 2))
ax.set_xlim(1, 21)
ax.grid(axis='y', alpha=0.3)
ax.spines[['top', 'right']].set_visible(False)
ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=3, frameon=False)
fig.tight_layout()
fig.savefig('graphique_cumul.png', dpi=150)
print(f'Graphique écrit : graphique_cumul.png (campus en tête : {champion}, {total:.2f} MAD)')
