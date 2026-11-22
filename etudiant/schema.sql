-- CampusEquip v2 : modèle de l'axe 1.
-- À lancer dans une base NEUVE nommée campusequip (jamais dans la base ShopFlow).
-- Rappel des grains :
--   campus, sites, clients, categories, equipments = les référentiels (1 ligne = 1 objet)
--   contracts      = 1 ligne par contrat
--   contract_lines = 1 ligne par équipement loué dans un contrat, clé (contract_id, line_no)
--   ingestion_batches = 1 ligne par lot déjà chargé (sert au rejeu)

CREATE TABLE campus (
    campus_id integer PRIMARY KEY,
    name      text NOT NULL
);

CREATE TABLE sites (
    site_id   integer PRIMARY KEY,
    campus_id integer NOT NULL REFERENCES campus (campus_id),   -- un site = un seul campus
    name      text NOT NULL
);

CREATE TABLE clients (
    client_id integer PRIMARY KEY,
    name      text NOT NULL
);

CREATE TABLE categories (
    category_id integer PRIMARY KEY,
    name        text NOT NULL,
    parent_id   integer REFERENCES categories (category_id)     -- parent facultatif (bonus récursif)
);

CREATE TABLE equipments (
    equipment_id integer PRIMARY KEY,
    name         text NOT NULL,
    category_id  integer NOT NULL REFERENCES categories (category_id)
);

CREATE TABLE contracts (
    contract_id bigint  PRIMARY KEY,                             -- unique dans une campagne
    client_id   integer NOT NULL REFERENCES clients (client_id),
    site_id     integer NOT NULL REFERENCES sites (site_id),     -- le site donne le campus
    start_date  date    NOT NULL,                                -- date à laquelle on rattache le montant
    status      text    NOT NULL CHECK (status IN ('paid', 'closed', 'draft', 'cancelled'))
);

CREATE TABLE contract_lines (
    contract_id  bigint  NOT NULL REFERENCES contracts (contract_id),
    line_no      integer NOT NULL CHECK (line_no > 0),
    equipment_id integer NOT NULL REFERENCES equipments (equipment_id),
    quantity     integer NOT NULL CHECK (quantity BETWEEN 1 AND 100),
    unit         text    NOT NULL CHECK (unit IN ('hour', 'day')),
    duration     integer NOT NULL CHECK (duration >= 1),
    unit_rate    numeric(10, 2) NOT NULL CHECK (unit_rate >= 0), -- tarif en MAD, jamais de float
    PRIMARY KEY (contract_id, line_no),
    -- durée maximale selon l'unité : 720 heures ou 365 jours
    CONSTRAINT duration_max CHECK (
        (unit = 'hour' AND duration <= 720) OR (unit = 'day' AND duration <= 365)
    )
);

-- Journal des lots : la signature est la référence du rejeu (pas le nom du dossier).
CREATE TABLE ingestion_batches (
    batch_signature     text PRIMARY KEY,        -- SHA-256 des 2 empreintes + version des règles
    campaign_id         text        NOT NULL,
    batch_number        integer     NOT NULL,
    rules_version       text        NOT NULL,
    locations_sha256    text        NOT NULL,
    referentiels_sha256 text        NOT NULL,
    accepted_contracts  integer     NOT NULL,
    accepted_lines      integer     NOT NULL,
    report              jsonb       NOT NULL,    -- le rapport de la tentative
    loaded_at           timestamptz NOT NULL DEFAULT now()
);

-- Configuration du laboratoire : on y mémorise la campagne autorisée.
CREATE TABLE lab_config (
    key   text PRIMARY KEY,
    value text NOT NULL
);

-- Montant d'une ligne = quantity * duration * unit_rate. Vue pratique pour l'axe 1.
CREATE VIEW line_amounts AS
SELECT s.campus_id,
       c.contract_id,
       c.start_date,
       c.status,
       l.line_no,
       l.equipment_id,
       l.unit,
       l.quantity * l.duration * l.unit_rate AS amount
FROM contracts c
JOIN sites s           ON s.site_id = c.site_id
JOIN contract_lines l  ON l.contract_id = c.contract_id;

CREATE INDEX IF NOT EXISTS idx_contracts_start_date ON contracts (start_date);
