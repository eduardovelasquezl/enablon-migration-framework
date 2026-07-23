-- Inventario técnico: claves foráneas a nivel de columna, con
-- foreign_key_object_id como identificador estable de la restricción
-- (necesario para deduplicar FKs compuestas en table_relationships sin
-- volver a consultar SQL Server -- ver src/analysis/sql_inventory.py).
SELECT
    fk.object_id                            AS foreign_key_object_id,
    fk.name                                 AS foreign_key_name,
    ss.name                                 AS source_schema,
    st.name                                 AS source_table,
    sc.name                                 AS source_column,
    ts.name                                 AS target_schema,
    tt.name                                 AS target_table,
    tc.name                                 AS target_column,
    fkc.constraint_column_id                AS column_ordinal,
    fk.update_referential_action_desc       AS update_action,
    fk.delete_referential_action_desc       AS delete_action
FROM sys.foreign_keys fk
JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
JOIN sys.tables st ON fk.parent_object_id = st.object_id
JOIN sys.schemas ss ON st.schema_id = ss.schema_id
JOIN sys.columns sc ON sc.object_id = fkc.parent_object_id AND sc.column_id = fkc.parent_column_id
JOIN sys.tables tt ON fk.referenced_object_id = tt.object_id
JOIN sys.schemas ts ON tt.schema_id = ts.schema_id
JOIN sys.columns tc ON tc.object_id = fkc.referenced_object_id AND tc.column_id = fkc.referenced_column_id
ORDER BY source_schema, source_table, foreign_key_name, column_ordinal;
