-- Inventario técnico: columnas de tablas y vistas, con tipo, nulabilidad y
-- valor por defecto -- las cuatro son atributos de la misma fila de
-- sys.columns, por eso viven en un único artefacto (columns.csv) en vez de
-- fragmentarse en cuatro consultas casi idénticas.
--
-- sys.types se resuelve por user_type_id, que cubre tanto tipos base del
-- motor como tipos definidos por el usuario en un único join.
SELECT
    s.name              AS schema_name,
    o.name              AS table_name,
    o.type              AS object_type,        -- 'U' tabla, 'V' vista
    c.column_id,
    c.name              AS column_name,
    ty.name             AS data_type,
    c.max_length,
    c.precision,
    c.scale,
    c.is_nullable,
    c.is_identity,
    c.is_computed,
    dc.definition       AS default_definition
FROM sys.columns c
JOIN sys.objects o ON c.object_id = o.object_id AND o.type IN ('U', 'V')
JOIN sys.schemas s ON o.schema_id = s.schema_id
JOIN sys.types ty ON c.user_type_id = ty.user_type_id
LEFT JOIN sys.default_constraints dc
    ON dc.parent_object_id = c.object_id AND dc.parent_column_id = c.column_id
ORDER BY schema_name, table_name, c.column_id;
