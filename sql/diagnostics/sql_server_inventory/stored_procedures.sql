-- Inventario técnico: procedimientos almacenados -- SOLO metadatos
-- (nombre, fechas). No se extrae la definición (sys.sql_modules) ni se
-- ejecuta ningún procedimiento.
SELECT
    s.name       AS schema_name,
    p.name       AS procedure_name,
    p.object_id  AS object_id,
    p.create_date,
    p.modify_date
FROM sys.procedures p
JOIN sys.schemas s ON p.schema_id = s.schema_id
ORDER BY schema_name, procedure_name;
