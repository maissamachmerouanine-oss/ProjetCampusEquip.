"""Guide 2 : vérifie que Python arrive à parler à la base campusequip.

La connexion se donne par une variable d'environnement CAMPUS_DSN :
aucun mot de passe n'est écrit dans ce fichier (le sujet l'interdit).
"""
import os
import sys

if sys.version_info < (3, 10):
    sys.exit(f'Python 3.10 ou plus est demandé, vous avez {sys.version.split()[0]}.')

try:
    import psycopg
except ImportError:
    sys.exit('psycopg n\'est pas installé. Lancez : pip install "psycopg[binary]"')

dsn = os.environ.get('CAMPUS_DSN')
if not dsn:
    sys.exit('La variable CAMPUS_DSN est vide. Voir le Guide 2, étape sur la connexion.')

with psycopg.connect(dsn) as conn:
    base = conn.execute('SELECT current_database()').fetchone()[0]
    nb_tables = conn.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
    ).fetchone()[0]

print(f'Connecté à la base : {base}')
print(f'Tables trouvées dans public : {nb_tables} (attendu : 9)')
if base != 'campusequip' or nb_tables != 9:
    sys.exit('Quelque chose ne va pas : vérifiez la base et le schéma.')
print('Tout est bon.')
