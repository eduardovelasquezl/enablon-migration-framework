-- Inventario técnico: vistas de usuario. Solo metadatos -- no se extrae la
-- definición de la vista (ver restricción: no extraer código).
SELECT
    s.name       AS schema_name,
    v.name       AS view_name,
    v.object_id  AS object_id,
    v.create_date,
    v.modify_date
FROM sys.views v
JOIN sys.schemas s ON v.schema_id = s.schema_id
ORDER BY schema_name, view_name;
