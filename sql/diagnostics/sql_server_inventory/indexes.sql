-- Inventario técnico: índices, distinguiendo columnas clave de incluidas,
-- orden ASC/DESC, unicidad, si respaldan una PK o UNIQUE constraint, e
-- índices filtrados (con su definición de filtro).
-- type > 0 excluye heaps (type = 0), que no tienen filas en sys.index_columns.
SELECT
    s.name                  AS schema_name,
    t.name                   AS table_name,
    i.index_id,
    i.name                   AS index_name,
    i.type_desc              AS index_type,
    i.is_unique,
    i.is_primary_key,
    i.is_unique_constraint,
    i.has_filter,
    i.filter_definition,
    ic.index_column_id,
    ic.key_ordinal,
    ic.is_included_column,
    CASE ic.is_descending_key WHEN 1 THEN 'DESC' ELSE 'ASC' END AS sort_direction,
    c.name                   AS column_name
FROM sys.indexes i
JOIN sys.tables t ON i.object_id = t.object_id
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
WHERE i.type > 0
ORDER BY schema_name, table_name, index_name, ic.key_ordinal, ic.index_column_id;
