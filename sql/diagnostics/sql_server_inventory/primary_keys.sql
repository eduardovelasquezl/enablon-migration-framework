-- Inventario técnico: claves primarias, una fila por columna de la PK
-- (key_ordinal indica el orden dentro de la clave compuesta si aplica).
SELECT
    s.name          AS schema_name,
    t.name          AS table_name,
    kc.name         AS constraint_name,
    c.name          AS column_name,
    ic.key_ordinal
FROM sys.key_constraints kc
JOIN sys.tables t ON kc.parent_object_id = t.object_id
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.index_columns ic
    ON ic.object_id = t.object_id AND ic.index_id = kc.unique_index_id
JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
WHERE kc.type = 'PK'
ORDER BY schema_name, table_name, ic.key_ordinal;
