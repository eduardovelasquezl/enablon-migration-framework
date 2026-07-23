-- Inventario técnico: funciones (escalares, inline table-valued,
-- table-valued, y sus variantes CLR). Solo metadatos -- no se extrae código.
SELECT
    s.name       AS schema_name,
    o.name       AS function_name,
    o.object_id  AS object_id,
    o.type_desc  AS function_type,
    o.create_date,
    o.modify_date
FROM sys.objects o
JOIN sys.schemas s ON o.schema_id = s.schema_id
WHERE o.type IN ('FN', 'IF', 'TF', 'FS', 'FT')
ORDER BY schema_name, function_name;
