-- Removes "empty" insegnamento rows: courses whose schede_opis row has
-- both totale_schede = 0 AND totale_schede_nf = 0, plus insegnamenti that
-- have no schede_opis attached at all. They are produced when:
--   * the source API exposes the cluster headers (Frequentanti /
--     Non Frequentanti) without any per-question data — the published-
--     privacy threshold kicks in when the response count is too low.
--   * a getQuestions API call fails and only the parent insegnamento row
--     was inserted by the upstream loop.
--
-- These rows surface in /api/v2/cds/with-id/{cds}/insegnamenti as teachings
-- with no usable Likert data, which the frontend treats inconsistently.
--
-- The transformers.py fix in parse_scheda_opis_data prevents future scrapes
-- from creating new ones; this script cleans up the historical buildup.
--
-- Idempotent: re-running on a clean DB selects zero rows.
--
-- Usage:
--   docker exec -i acore-docker-ac-database-1 mysql -uroot -proot \
--     -h 127.0.0.1 opis_manager < scripts/remove_empty_insegnamenti.sql

START TRANSACTION;

-- Pre-flight visibility: how much will go away, split by year.
SELECT
    i.anno_accademico,
    SUM(CASE WHEN s.id IS NULL THEN 1 ELSE 0 END)                                   AS no_schede,
    SUM(CASE WHEN s.id IS NOT NULL
              AND s.totale_schede = 0
              AND s.totale_schede_nf = 0 THEN 1 ELSE 0 END)                         AS zero_schede,
    SUM(CASE WHEN s.id IS NULL
              OR  (s.totale_schede = 0 AND s.totale_schede_nf = 0) THEN 1 ELSE 0 END) AS total_to_delete
FROM insegnamento i
LEFT JOIN schede_opis s ON s.id_insegnamento = i.id
GROUP BY i.anno_accademico
ORDER BY i.anno_accademico;

-- Delete the all-zero schede_opis rows first (the FK has no ON DELETE
-- CASCADE, so the matching insegnamento delete below would otherwise fail).
DELETE s
FROM schede_opis s
WHERE s.totale_schede = 0
  AND s.totale_schede_nf = 0;

-- Now drop every insegnamento that has no schede_opis attached. This
-- removes both the "always empty" set and the rows whose only attached
-- schede_opis we just deleted above.
DELETE i
FROM insegnamento i
LEFT JOIN schede_opis s ON s.id_insegnamento = i.id
WHERE s.id IS NULL;

SELECT
    'after cleanup' AS phase,
    (SELECT COUNT(*) FROM insegnamento) AS insegnamento_rows,
    (SELECT COUNT(*) FROM schede_opis)  AS schede_opis_rows;

COMMIT;
