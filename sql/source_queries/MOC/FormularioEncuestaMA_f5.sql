SELECT 
    IDSolicitudCambio,
    CONCAT(IDSolicitudCambio, '.MA') AS IDEncuestaMA,
    IDGrupoResponsableFase5
FROM GCT.dbo.CT_SOLICITUDES_CT2_FASE5
WHERE FechaEnvioFase5 IS NOT NULL