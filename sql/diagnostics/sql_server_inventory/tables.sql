-- Inventario técnico: tablas de usuario (sys.tables ya excluye objetos de
-- sistema por diseño de SQL Server -- no hace falta filtrar más).
-- Solo lectura de catálogo, no toca datos.
SELECT
    s.name       AS schema_name,
    t.name       AS table_name,
    t.object_id  AS object_id,
    t.create_date,
    t.modify_date
FROM sys.tables t
JOIN sys.schemas s ON t.schema_id = s.schema_id
ORDER BY schema_name, table_name;
