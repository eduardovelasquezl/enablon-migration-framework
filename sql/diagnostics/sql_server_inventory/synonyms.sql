-- Inventario técnico: sinónimos. base_object_name se guarda tal cual (texto
-- crudo, puede referenciar otro servidor/base) -- no se resuelve ni se
-- sigue la referencia.
SELECT
    s.name              AS schema_name,
    syn.name            AS synonym_name,
    syn.object_id       AS object_id,
    syn.base_object_name
FROM sys.synonyms syn
JOIN sys.schemas s ON syn.schema_id = s.schema_id
ORDER BY schema_name, synonym_name;
