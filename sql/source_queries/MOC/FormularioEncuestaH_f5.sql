SELECT 
    IDSolicitudCambio,
    CONCAT(IDSolicitudCambio, '.EH') AS IDEncuestaH,
    IDGrupoResponsableFase5
FROM GCT.dbo.CT_SOLICITUDES_CT2_FASE5
WHERE FechaEnvioFase5 IS NOT NULL
