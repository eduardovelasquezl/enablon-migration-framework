-- Inventario técnico: filas aproximadas por tabla vía metadatos de
-- partición (sys.partitions, index_id IN (0,1): heap o índice clustered),
-- NUNCA COUNT(*) completo. Deliberadamente NO se usa
-- sys.dm_db_partition_stats (DMV que puede requerir VIEW DATABASE STATE,
-- permiso no confirmado para el login de solo lectura de este proyecto).
SELECT
    s.name          AS schema_name,
    t.name          AS table_name,
    SUM(p.rows)     AS approx_row_count
FROM sys.partitions p
JOIN sys.tables t ON p.object_id = t.object_id
JOIN sys.schemas s ON t.schema_id = s.schema_id
WHERE p.index_id IN (0, 1)
GROUP BY s.name, t.name
ORDER BY schema_name, table_name;
