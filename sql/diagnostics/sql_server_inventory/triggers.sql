-- Inventario técnico: triggers DML de tabla (parent_class = 1) y triggers
-- de base de datos / DDL (parent_class = 0, resolubles con esta misma
-- consulta de catálogo simple). Los triggers de servidor quedan
-- deliberadamente fuera de alcance. Solo metadatos -- no se extrae código.
SELECT
    'TABLE'      AS trigger_scope,
    s.name       AS schema_name,
    t.name       AS table_name,
    tr.name      AS trigger_name,
    tr.object_id AS object_id,
    tr.is_disabled,
    tr.is_instead_of_trigger
FROM sys.triggers tr
JOIN sys.tables t ON tr.parent_id = t.object_id
JOIN sys.schemas s ON t.schema_id = s.schema_id
WHERE tr.parent_class = 1

UNION ALL

SELECT
    'DATABASE'   AS trigger_scope,
    NULL         AS schema_name,
    NULL         AS table_name,
    tr.name      AS trigger_name,
    tr.object_id AS object_id,
    tr.is_disabled,
    tr.is_instead_of_trigger
FROM sys.triggers tr
WHERE tr.parent_class = 0

ORDER BY trigger_scope, schema_name, table_name, trigger_name;
