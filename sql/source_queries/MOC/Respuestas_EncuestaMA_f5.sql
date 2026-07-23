SELECT 
    S.IDSolicitudCambio,
    CONCAT(S.IDSolicitudCambio, '.MA') AS IDEncuestaMA,
    CONCAT(S.IDSolicitudCambio, '.MA.', X.IDMaestro) AS IDPreguntaEncuesta,
    X.IDMaestro AS IDPregunta,
    M.Valor AS TextoPregunta,
    X.Respuesta
FROM GCT.dbo.CT_SOLICITUDES_CT2_FASE5 S

CROSS APPLY (
    SELECT 
        LTRIM(RTRIM(Split.a.value('.', 'VARCHAR(50)'))) AS Valor
    FROM (
        SELECT CAST('<X>' + REPLACE(S.EncuestasTipoMA, ',', '</X><X>') + '</X>' AS XML) AS Data
    ) A
    CROSS APPLY Data.nodes('/X') AS Split(a)
) Raw

CROSS APPLY (
    SELECT 
        LEFT(Raw.Valor, CHARINDEX('_', Raw.Valor) - 1) AS IDMaestro,
        RIGHT(Raw.Valor, LEN(Raw.Valor) - CHARINDEX('_', Raw.Valor)) AS Respuesta
) X

LEFT JOIN GCT.dbo.CT_MAESTROS M 
    ON M.IDMaestro = X.IDMaestro

WHERE 
    S.FechaEnvioFase5 IS NOT NULL
    AND S.EncuestasTipoMA IS NOT NULL