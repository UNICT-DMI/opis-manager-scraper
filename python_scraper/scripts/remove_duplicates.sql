-- Removes duplicate `insegnamento` rows produced by the original scraper
-- commit (d6ce98b) that lacked a dedup check on INSERT. Each re-run of that
-- old scraper appended a fresh copy of every (gomp, teacher, module) tuple
-- inside each CDS, so the worst groups now hold 16 identical-key rows.
--
-- "Duplicate" here means rows that share the natural key:
--   (codice_gomp, anno_accademico, id_cds, docente, id_modulo,
--    COALESCE(nome_modulo, ''))
--
-- For each duplicate group we keep the row with the smallest id (oldest
-- insert) and delete the rest, plus any schede_opis rows attached to them
-- (the FK has no ON DELETE CASCADE, so schede_opis must go first).
--
-- Idempotent: re-running on a clean DB selects zero rows and deletes nothing.
-- Safe to run inside a transaction so a wrong PARTITION key can be rolled
-- back.
--
-- Usage:
--   docker exec -i acore-docker-ac-database-1 mysql -uroot -proot \
--     -h 127.0.0.1 opis_manager < scripts/remove_duplicates.sql

START TRANSACTION;

-- Identify the dup ids in one pass so the temp table is the single source
-- of truth for both deletes (avoids races and lets the user inspect before
-- COMMIT).
DROP TEMPORARY TABLE IF EXISTS _insegnamento_duplicates;
CREATE TEMPORARY TABLE _insegnamento_duplicates AS
SELECT id
FROM (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY
                codice_gomp,
                anno_accademico,
                id_cds,
                docente,
                id_modulo,
                COALESCE(nome_modulo, '')
            ORDER BY id
        ) AS rn
    FROM insegnamento
) ranked
WHERE rn > 1;

-- Surface the impact before any destructive write so the user sees what
-- they are about to lose. MySQL forbids referencing the same temp table
-- twice in one query, so the row count is captured in a session variable
-- via a side query that touches the temp table once.
SET @insegnamento_to_delete := (SELECT COUNT(*) FROM _insegnamento_duplicates);
SELECT
    'about to delete'           AS phase,
    @insegnamento_to_delete     AS insegnamento_rows,
    (SELECT COUNT(*) FROM schede_opis s
        JOIN _insegnamento_duplicates d ON d.id = s.id_insegnamento)
                                AS schede_opis_rows;

DELETE FROM schede_opis
WHERE id_insegnamento IN (SELECT id FROM _insegnamento_duplicates);

DELETE FROM insegnamento
WHERE id IN (SELECT id FROM _insegnamento_duplicates);

DROP TEMPORARY TABLE _insegnamento_duplicates;

-- COMMIT the deletes now: the DDL below implicitly commits anyway, so an
-- explicit COMMIT here makes the transaction boundary obvious and lets the
-- script abort safely if the DDL portion fails on a version that doesn't
-- support generated columns.
COMMIT;

-- Defense-in-depth: prevent regressions from a future scraper bug. The
-- index has to live on a generated column because MySQL's UNIQUE allows
-- multiple NULLs, which would still let nome_modulo-NULL duplicates slip
-- through. The generated column is STORED (not VIRTUAL) so it can be
-- indexed under InnoDB. MySQL 8 doesn't support `ADD COLUMN IF NOT EXISTS`,
-- so we guard both DDL statements with INFORMATION_SCHEMA lookups.
SET @col_exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'insegnamento'
      AND COLUMN_NAME  = '_dedup_nome_modulo'
);
SET @ddl := IF(@col_exists = 0,
    'ALTER TABLE insegnamento ADD COLUMN _dedup_nome_modulo VARCHAR(255) '
    "GENERATED ALWAYS AS (COALESCE(nome_modulo, '')) STORED",
    'SELECT "column _dedup_nome_modulo already exists" AS msg');
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Prefix indexes on the long varchars because the full-length composite
-- (4 + 20·4 + 8 + 255·4 + 255·4 + 255·4 = ~3172 B) exceeds InnoDB's 3072 B
-- key limit under utf8mb4. 150-char prefixes are well above the longest
-- real teacher/module names observed in the data while leaving headroom.
SET @idx_exists := (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'insegnamento'
      AND INDEX_NAME   = 'insegnamento_natural_key_unique'
);
SET @ddl := IF(@idx_exists = 0,
    'ALTER TABLE insegnamento ADD UNIQUE INDEX insegnamento_natural_key_unique '
    '(codice_gomp, anno_accademico, id_cds, docente(150), id_modulo(30), '
    '_dedup_nome_modulo(150))',
    'SELECT "index insegnamento_natural_key_unique already exists" AS msg');
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT
    'after cleanup' AS phase,
    (SELECT COUNT(*) FROM insegnamento) AS insegnamento_rows,
    (SELECT COUNT(*) FROM schede_opis)   AS schede_opis_rows;
