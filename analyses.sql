-- CampusEquip : les 3 analyses de l'axe 1.
-- Règle commune : seuls les contrats 'paid' et 'closed' comptent. Tout le montant est rattaché à start_date.
-- La vue line_amounts (créée par schema.sql) donne déjà : campus, contrat, date, statut, équipement, unité
-- et le montant d'une ligne = quantity * duration * unit_rate.

-- ============================================================================
-- Analyse 1 : montant par date et par campus, du 1er au 21 novembre 2026,
--             avec les jours à zéro et le cumul par campus.
-- ============================================================================
WITH jours AS (                                   -- les 21 jours, même ceux sans location
    SELECT d::date AS jour
    FROM generate_series('2026-11-01'::date, '2026-11-21'::date, '1 day') AS d
),
montants AS (                                     -- le montant réel par campus et par jour
    SELECT campus_id, start_date AS jour, SUM(amount) AS montant
    FROM line_amounts
    WHERE status IN ('paid', 'closed')
    GROUP BY campus_id, start_date
)
SELECT ca.campus_id,
       ca.name AS campus,
       j.jour,
       COALESCE(m.montant, 0) AS montant,         -- jour sans location : 0 (et pas une ligne manquante)
       SUM(COALESCE(m.montant, 0)) OVER (
           PARTITION BY ca.campus_id ORDER BY j.jour
           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumul
FROM campus ca
CROSS JOIN jours j                                -- chaque campus x chaque jour
LEFT JOIN montants m ON m.campus_id = ca.campus_id AND m.jour = j.jour
ORDER BY ca.campus_id, j.jour;

-- ============================================================================
-- Analyse 2 : équipements les plus contributeurs dans chaque campus
--             (rang par montant décroissant ; les égalités ont le même rang).
-- ============================================================================
WITH par_equipement AS (
    SELECT l.campus_id, l.equipment_id, SUM(l.amount) AS montant
    FROM line_amounts l
    WHERE l.status IN ('paid', 'closed')
    GROUP BY l.campus_id, l.equipment_id
),
classement AS (
    SELECT campus_id, equipment_id, montant,
           RANK() OVER (PARTITION BY campus_id ORDER BY montant DESC) AS rang   -- RANK : égalités = même rang
    FROM par_equipement
)
SELECT ca.name AS campus, c.rang, e.name AS equipement, c.montant
FROM classement c
JOIN campus ca     ON ca.campus_id = c.campus_id
JOIN equipments e  ON e.equipment_id = c.equipment_id
WHERE c.rang <= 3                                 -- les 3 premiers rangs de chaque campus pour le tableau
ORDER BY ca.campus_id, c.rang, e.equipment_id;

-- ============================================================================
-- Analyse 3 : location à l'heure ou à la journée : par campus et par unité,
--             nombre de lignes retenues et montant.
-- ============================================================================
SELECT ca.name AS campus,
       l.unit AS unite,
       COUNT(*) AS lignes_retenues,
       SUM(l.amount) AS montant
FROM line_amounts l
JOIN campus ca ON ca.campus_id = l.campus_id
WHERE l.status IN ('paid', 'closed')
GROUP BY ca.campus_id, ca.name, l.unit
ORDER BY ca.campus_id, l.unit;

-- ============================================================================
-- Preuve à la main : le contrat 2 (statut paid) ligne par ligne.
-- On refait le calcul sur papier : 3x1x134 + 2x3x126 + 4x4x283 = 402 + 756 + 4528 = 5686.
-- ============================================================================
SELECT l.contract_id, l.line_no, l.quantity, l.unit, l.duration, l.unit_rate,
       l.quantity * l.duration * l.unit_rate AS montant_ligne,
       SUM(l.quantity * l.duration * l.unit_rate) OVER () AS total_contrat
FROM contract_lines l
WHERE l.contract_id = 2
ORDER BY l.line_no;
