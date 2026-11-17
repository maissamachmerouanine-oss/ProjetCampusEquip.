"""Guide 6 : crée (ou recrée) une base VIDE nommée campusequip_test, avec les 9 tables.

    python preparer_base_test.py

Ta vraie base campusequip n'est jamais touchée : seule campusequip_test est supprimée puis recréée.
Il faut que la variable CAMPUS_DSN existe déjà (elle sert à se connecter au serveur).
"""
import os
import sys
from pathlib import Path

import psycopg
from psycopg.conninfo import make_conninfo

NOM = 'campusequip_test'
SCHEMA = Path('etudiant/schema.sql')

dsn = os.environ.get('CAMPUS_DSN')
if not dsn:
    sys.exit('La variable CAMPUS_DSN est vide : voir le Guide 2.')
if not SCHEMA.is_file():
    sys.exit('Lance cette commande depuis le dossier CampusEquip_etudiant (etudiant/schema.sql introuvable).')

# 1) on se connecte à la base "postgres" (une base d'administration) pour supprimer / créer campusequip_test
with psycopg.connect(make_conninfo(dsn, dbname='postgres'), autocommit=True) as admin:
    admin.execute(f'DROP DATABASE IF EXISTS {NOM} WITH (FORCE)')
    admin.execute(f'CREATE DATABASE {NOM}')

# 2) on y crée les tables avec le même schema.sql que pour la vraie base
with psycopg.connect(make_conninfo(dsn, dbname=NOM)) as conn:
    conn.execute(SCHEMA.read_text(encoding='utf-8'))
    nb = conn.execute("SELECT count(*) FROM information_schema.tables "
                      "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'").fetchone()[0]

print(f'Base {NOM} prête : {nb} tables (attendu : 9), aucune ligne dedans.')
print('Pour l\'utiliser, remplace campusequip par campusequip_test à la fin de CAMPUS_DSN (voir le guide).')
