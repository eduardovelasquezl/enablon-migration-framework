SELECT
    -- Columnas principales
    CT_SOLICITUDES_CT2.IDSolicitudCambio,
    CT_SOLICITUDES_CT2.IDFlujo,
    CT_SOLICITUDES_CT2.IDCentro,
    CT_SOLICITUDES_CT2.FechaHora,
    CT_SOLICITUDES_CT2.IDEstado,
    CT_SOLICITUDES_CT2.IDGrupoResponsableFaseActual,
    CT_SOLICITUDES_CT2.FaseActual,
    CT_SOLICITUDES_CT2.FechaCreacion,
    CT_SOLICITUDES_CT2.FechaAprobacion,
    CT_SOLICITUDES_CT2.FechaTerminacion,
    CT_SOLICITUDES_CT2.FechaUltimaModificacion,
    CT_SOLICITUDES_CT2.IDUsuarioUltimaModificacion,
    CT_SOLICITUDES_CT2.Observaciones,
    CT_SOLICITUDES_CT2.NumeroDocumentos,
    CT_SOLICITUDES_CT2.AnyoPresupuesto,
    CT_SOLICITUDES_CT2.MotivoAnulacion,
    CT_SOLICITUDES_CT2.IDPrioridadGeneral,
    CT_SOLICITUDES_CT2.IDEstadoInversion,
    CT_SOLICITUDES_CT2.IndNuevaSolicitudSinCentro,
    CT_SOLICITUDES_CT2.INDNuevaSolicitud,
    CT_SOLICITUDES_CT2.OnHold,
    CT_SOLICITUDES_CT2.IdNotificado,

    -- Fase1
    CT_SOLICITUDES_CT2_FASE1.IDGrupoResponsableFase1,
    CT_SOLICITUDES_CT2_FASE1.IDUsuarioEnvioFase1,
    CT_SOLICITUDES_CT2_FASE1.FechaEnvioFase1,
    CT_SOLICITUDES_CT2_FASE1.Titulo,
    CT_SOLICITUDES_CT2_FASE1.IDFabrica,
    CT_SOLICITUDES_CT2_FASE1.IDPlanta,
    CT_SOLICITUDES_CT2_FASE1.IDUnidad,
    CT_SOLICITUDES_CT2_FASE1.IDTipoSC,
    CT_SOLICITUDES_CT2_FASE1.ReferenciaProyectoST,
    CT_SOLICITUDES_CT2_FASE1.FechaRetorno,
    CT_SOLICITUDES_CT2_FASE1.IDMotivo,
    CT_SOLICITUDES_CT2_FASE1.CambioPropuesto,
    CT_SOLICITUDES_CT2_FASE1.CausasCambio,
    CT_SOLICITUDES_CT2_FASE1.IDImplicaCambio,
    CT_SOLICITUDES_CT2_FASE1.IDPrioridad,
    CT_SOLICITUDES_CT2_FASE1.ImplicacionesMedioAmbientales,
    CT_SOLICITUDES_CT2_FASE1.AfectaA,
    CT_SOLICITUDES_CT2_FASE1.Parada,
    CT_SOLICITUDES_CT2_FASE1.ObservacionesParada,
    CT_SOLICITUDES_CT2_FASE1.FechaTerminacionSolicitada,
    CT_SOLICITUDES_CT2_FASE1.IndCargarPPM,
    CT_SOLICITUDES_CT2_FASE1.CargarPPM,
    CT_SOLICITUDES_CT2_FASE1.IDDivision,
    CT_SOLICITUDES_CT2_FASE1.IDAreaNegocio,
    CT_SOLICITUDES_CT2_FASE1.IDUnidadNegocio,
    CT_SOLICITUDES_CT2_FASE1.IDSubclasificacion,
    CT_SOLICITUDES_CT2_FASE1.BeneficioAnualEsperado,
    CT_SOLICITUDES_CT2_FASE1.UbicacionTecnica,
    CT_SOLICITUDES_CT2_FASE1.VidaUtilCT,
    CT_SOLICITUDES_CT2_FASE1.PorcentajeMedioambiental,
    CT_SOLICITUDES_CT2_FASE1.EquiposSustituir,
    CT_SOLICITUDES_CT2_FASE1.DepartamentoEjecutante,
    CT_SOLICITUDES_CT2_FASE1.CondicionesFechas,
    CT_SOLICITUDES_CT2_FASE1.OtrosProyectos,
    CT_SOLICITUDES_CT2_FASE1.ObservacionesGestorFase1,
    CT_SOLICITUDES_CT2_FASE1.FechaPrevInstalacionCambio,

    -- Fase2
    CT_SOLICITUDES_CT2_FASE2.IDGrupoResponsableFase2,
    CT_SOLICITUDES_CT2_FASE2.IDUsuarioEnvioFase2,
    CT_SOLICITUDES_CT2_FASE2.FechaEnvioFase2,
    CT_SOLICITUDES_CT2_FASE2.Observaciones AS [Observaciones-f2],
    CT_SOLICITUDES_CT2_FASE2.IDResuelve,
    CT_SOLICITUDES_CT2_FASE2.IDPlanificacion,
    CT_SOLICITUDES_CT2_FASE2.Optimizacion,
    CT_SOLICITUDES_CT2_FASE2.IndCargarPPM AS [IndCargarPPM-f2],
    CT_SOLICITUDES_CT2_FASE2.CargarPPM AS [CargarPPM-f2],
    CT_SOLICITUDES_CT2_FASE2.IDDuenioFase2,
    CT_SOLICITUDES_CT2_FASE2.ObservacionesGestorFase2,

    -- Fase3
    CT_SOLICITUDES_CT2_FASE3.IDGrupoResponsableFase3,
    CT_SOLICITUDES_CT2_FASE3.IDUsuarioEnvioFase3,
    CT_SOLICITUDES_CT2_FASE3.FechaEnvioFase3,
    CT_SOLICITUDES_CT2_FASE3.Observaciones AS [Observaciones-f3],
    CT_SOLICITUDES_CT2_FASE3.ObservacionesGestorFase3,

    -- Fase4
    CT_SOLICITUDES_CT2_FASE4.IDGrupoResponsableFase4,
    CT_SOLICITUDES_CT2_FASE4.IDUsuarioEnvioFase4,
    CT_SOLICITUDES_CT2_FASE4.FechaEnvioFase4,
    CT_SOLICITUDES_CT2_FASE4.Observaciones AS [Observaciones-f4],
    CT_SOLICITUDES_CT2_FASE4.RequiereGOS,
    CT_SOLICITUDES_CT2_FASE4.RequiereProcesos,
    CT_SOLICITUDES_CT2_FASE4.ObservacionesGestorFase4,

    -- Fase5
    CT_SOLICITUDES_CT2_FASE5.IDGrupoResponsableFase5,
    CT_SOLICITUDES_CT2_FASE5.IDUsuarioEnvioFase5,
    CT_SOLICITUDES_CT2_FASE5.FechaEnvioFase5,
    CT_SOLICITUDES_CT2_FASE5.EncuestasH,
    CT_SOLICITUDES_CT2_FASE5.IDGradoRiesgo,
    CT_SOLICITUDES_CT2_FASE5.EncuestasS,
    CT_SOLICITUDES_CT2_FASE5.IDCriterioMagnitud,
    CT_SOLICITUDES_CT2_FASE5.EncuestasTipoMA,
    CT_SOLICITUDES_CT2_FASE5.IDCriterioMagnitudMA,
    CT_SOLICITUDES_CT2_FASE5.IDNivelRiesgo,
    CT_SOLICITUDES_CT2_FASE5.IDMetodologiaAnalisisRiesgo,
    CT_SOLICITUDES_CT2_FASE5.IDEvalConsecuenciasMedioAmbiente,
    CT_SOLICITUDES_CT2_FASE5.IDMetodologia,
    CT_SOLICITUDES_CT2_FASE5.ObservacionesGestorFase5,

    -- Fase6
    CT_SOLICITUDES_CT2_FASE6.IDGrupoResponsableFase6,
    CT_SOLICITUDES_CT2_FASE6.IDUsuarioEnvioFase6,
    CT_SOLICITUDES_CT2_FASE6.FechaEnvioFase6,
    CT_SOLICITUDES_CT2_FASE6.Observaciones AS [Observaciones-f6],
    CT_SOLICITUDES_CT2_FASE6.EstudioSeguridad,
    CT_SOLICITUDES_CT2_FASE6.EstudioPrevencionMedioAmbiental,
    CT_SOLICITUDES_CT2_FASE6.RevisionEvaluacionRiesgos,
    CT_SOLICITUDES_CT2_FASE6.LicenciaObras,
    CT_SOLICITUDES_CT2_FASE6.ProyectoOficial,
    CT_SOLICITUDES_CT2_FASE6.ComunicacionIndustria,
    CT_SOLICITUDES_CT2_FASE6.DocumentoContraExplosiones,
    CT_SOLICITUDES_CT2_FASE6.RequiereReunionGOS,
    CT_SOLICITUDES_CT2_FASE6.RequiereGuiaSMAR,
    CT_SOLICITUDES_CT2_FASE6.Valoracion,
    CT_SOLICITUDES_CT2_FASE6.ObservacionesGestorFase6,

    -- Fase7
    CT_SOLICITUDES_CT2_FASE7.IDGrupoResponsableFase7,
    CT_SOLICITUDES_CT2_FASE7.IDUsuarioEnvioFase7,
    CT_SOLICITUDES_CT2_FASE7.FechaEnvioFase7,
    CT_SOLICITUDES_CT2_FASE7.EncuestasH AS [EncuestasH-f7],
    CT_SOLICITUDES_CT2_FASE7.IDGradoRiesgo AS [IDGradoRiesgo-f7],
    CT_SOLICITUDES_CT2_FASE7.EncuestasS AS [EncuestasS-f7],
    CT_SOLICITUDES_CT2_FASE7.IDCriterioMagnitud AS [IDCriterioMagnitud-f7],
    CT_SOLICITUDES_CT2_FASE7.EncuestasTipoMA AS [EncuestasTipoMA-f7],
    CT_SOLICITUDES_CT2_FASE7.IDCriterioMagnitudMA AS [IDCriterioMagnitudMA-f7],
    CT_SOLICITUDES_CT2_FASE7.IDNivelRiesgo AS [IDNivelRiesgo-f7],
    CT_SOLICITUDES_CT2_FASE7.IDMetodologiaAnalisisRiesgo AS [IDMetodologiaAnalisisRiesgo-f7],
    CT_SOLICITUDES_CT2_FASE7.IDEvalConsecuenciasMedioAmbiente AS [IDEvalConsecuenciasMedioAmbiente-f7],
    CT_SOLICITUDES_CT2_FASE7.IDMetodologia AS [IDMetodologia-f7],
    CT_SOLICITUDES_CT2_FASE7.ObservacionesGestorFase7,

    -- Fase8
    CT_SOLICITUDES_CT2_FASE8.IDGrupoResponsableFase8,
    CT_SOLICITUDES_CT2_FASE8.IDUsuarioEnvioFase8,
    CT_SOLICITUDES_CT2_FASE8.FechaEnvioFase8,
    CT_SOLICITUDES_CT2_FASE8.Observaciones AS [Observaciones-f8],
    CT_SOLICITUDES_CT2_FASE8.IDResuelve AS [IDResuelve-f8],
    CT_SOLICITUDES_CT2_FASE8.ObservacionesGestorFase8,

    -- Fase9
    CT_SOLICITUDES_CT2_FASE9.IDGrupoResponsableFase9,
    CT_SOLICITUDES_CT2_FASE9.IDUsuarioEnvioFase9,
    CT_SOLICITUDES_CT2_FASE9.FechaEnvioFase9,
    CT_SOLICITUDES_CT2_FASE9.Observaciones AS [Observaciones-f9],
    CT_SOLICITUDES_CT2_FASE9.EstudioMedioAmbiental,
    CT_SOLICITUDES_CT2_FASE9.EstudioSeguridad AS [EstudioSeguridad-f9],
    CT_SOLICITUDES_CT2_FASE9.EstudioSeguridadAdicional,
    CT_SOLICITUDES_CT2_FASE9.ObservacionesGestorFase9,

    -- Fase10
    CT_SOLICITUDES_CT2_FASE10.IDGrupoResponsableFase10,
    CT_SOLICITUDES_CT2_FASE10.IDUsuarioEnvioFase10,
    CT_SOLICITUDES_CT2_FASE10.FechaEnvioFase10,
    CT_SOLICITUDES_CT2_FASE10.Observaciones AS [Observaciones-f10],
    CT_SOLICITUDES_CT2_FASE10.Anexo3,
    CT_SOLICITUDES_CT2_FASE10.PresupuestoAprobado,
    CT_SOLICITUDES_CT2_FASE10.FechaTerminacionEstimada,
    CT_SOLICITUDES_CT2_FASE10.EstudioMedioAmbiental AS [EstudioMedioAmbiental-f10],
    CT_SOLICITUDES_CT2_FASE10.EstudioSeguridad AS [EstudioSeguridad-f10],
    CT_SOLICITUDES_CT2_FASE10.EstudioSeguridadAdicional AS [EstudioSeguridadAdicional-f10],
    CT_SOLICITUDES_CT2_FASE10.ObservacionesGestorFase10,

    -- Fase11
    CT_SOLICITUDES_CT2_FASE11.IDGrupoResponsableFase11,
    CT_SOLICITUDES_CT2_FASE11.IDUsuarioEnvioFase11,
    CT_SOLICITUDES_CT2_FASE11.FechaEnvioFase11,
    CT_SOLICITUDES_CT2_FASE11.Observaciones AS [Observaciones-f11],
    CT_SOLICITUDES_CT2_FASE11.GradoAvance,
    CT_SOLICITUDES_CT2_FASE11.ObservacionesGestorFase11,
    CT_SOLICITUDES_CT2_FASE11.FechaRealInstalacionCambio,
    CT_SOLICITUDES_CT2_FASE11.FechaRealRetiradaCambio,
    CT_SOLICITUDES_CT2_FASE11.FechaLimiteCambio,

    -- Fase12
    CT_SOLICITUDES_CT2_FASE12.IDGrupoResponsableFase12,
    CT_SOLICITUDES_CT2_FASE12.IDUsuarioEnvioFase12,
    CT_SOLICITUDES_CT2_FASE12.FechaEnvioFase12,
    CT_SOLICITUDES_CT2_FASE12.Observaciones AS [Observaciones-f12],
    CT_SOLICITUDES_CT2_FASE12.RealizadaInspeccionYListaFaltas,
    CT_SOLICITUDES_CT2_FASE12.RealizadoProgramaInspeccion,
    CT_SOLICITUDES_CT2_FASE12.ObservacionesGestorFase12,
    CT_SOLICITUDES_CT2_FASE12.FaseRealizada,

    -- Fase13
    CT_SOLICITUDES_CT2_FASE13.IDGrupoResponsableFase13,
    CT_SOLICITUDES_CT2_FASE13.IDUsuarioEnvioFase13,
    CT_SOLICITUDES_CT2_FASE13.FechaEnvioFase13,
    CT_SOLICITUDES_CT2_FASE13.Observaciones AS [Observaciones-f13],
    CT_SOLICITUDES_CT2_FASE13.ProteccionIndividual,
    CT_SOLICITUDES_CT2_FASE13.PlanEmergencia,
    CT_SOLICITUDES_CT2_FASE13.RealizadoHAZOP_SIL,
    CT_SOLICITUDES_CT2_FASE13.RealizadoGOS,
    CT_SOLICITUDES_CT2_FASE13.FinalizadoEvaluacionRiesgo,
    CT_SOLICITUDES_CT2_FASE13.FinalizadoEstudioSeguridad,
    CT_SOLICITUDES_CT2_FASE13.ObservacionesGestorFase13,
    CT_SOLICITUDES_CT2_FASE13.ActualizadoDocumentosAtex,
    CT_SOLICITUDES_CT2_FASE13.FaseRealizada AS [FaseRealizada-f13],

    -- Fase14
    CT_SOLICITUDES_CT2_FASE14.IDGrupoResponsableFase14,
    CT_SOLICITUDES_CT2_FASE14.IDUsuarioEnvioFase14,
    CT_SOLICITUDES_CT2_FASE14.FechaEnvioFase14,
    CT_SOLICITUDES_CT2_FASE14.Observaciones AS [Observaciones-f14],
    CT_SOLICITUDES_CT2_FASE14.RealizadaActualizacionResponsable,
    CT_SOLICITUDES_CT2_FASE14.ObservacionesGestorFase14,
    CT_SOLICITUDES_CT2_FASE14.FaseRealizada AS [FaseRealizada-f14],

    -- Fase15
    CT_SOLICITUDES_CT2_FASE15.IDGrupoResponsableFase15,
    CT_SOLICITUDES_CT2_FASE15.IDUsuarioEnvioFase15,
    CT_SOLICITUDES_CT2_FASE15.FechaEnvioFase15,
    CT_SOLICITUDES_CT2_FASE15.Observaciones AS [Observaciones-f15],
    CT_SOLICITUDES_CT2_FASE15.ManualOperacion,
    CT_SOLICITUDES_CT2_FASE15.PersonalOperacion,
    CT_SOLICITUDES_CT2_FASE15.AceptadoOperacion,
    CT_SOLICITUDES_CT2_FASE15.RevisadosAspectosAnexo3,
    CT_SOLICITUDES_CT2_FASE15.RevisadosAccionesPendientes,
    CT_SOLICITUDES_CT2_FASE15.ListaFaltasCompletada,
    CT_SOLICITUDES_CT2_FASE15.DocumentacionCTCompleta,
    CT_SOLICITUDES_CT2_FASE15.ObservacionesGestorFase15,
    CT_SOLICITUDES_CT2_FASE15.FechaRealRetiradaCambio AS [FechaRealRetiradaCambio-f15],

    -- Fase16
    CT_SOLICITUDES_CT2_FASE16.FechaEnvioFase16,
    
    CT_SOLICITUDES_CT2_FASE16.IDUsuarioEnvioFase16,
    CT_SOLICITUDES_CT2_FASE16.IDGrupoResponsableFase16,
    CT_SOLICITUDES_CT2_FASE16.Observaciones AS [Observaciones-f16],
    CT_SOLICITUDES_CT2_FASE16.DocumentacionActualizada,
    CT_SOLICITUDES_CT2_FASE16.EstudioSeguridad AS [EstudioSeguridad-f16],
    CT_SOLICITUDES_CT2_FASE16.EstudioPrevencionAmbiental,
    CT_SOLICITUDES_CT2_FASE16.RevisionEvaluacionRiesgos AS [RevisionEvaluacionRiesgos-f16],
    CT_SOLICITUDES_CT2_FASE16.ImplicacionesMedioAmbientales AS [ImplicacionesMedioAmbientales-f16],
    CT_SOLICITUDES_CT2_FASE16.LicenciaObras AS [LicenciaObras-f16],
    CT_SOLICITUDES_CT2_FASE16.ProyectoOficial AS [ProyectoOficial-f16],
    CT_SOLICITUDES_CT2_FASE16.ComunicacionIndustria AS [ComunicacionIndustria-f16],
    CT_SOLICITUDES_CT2_FASE16.LibroContraExplosiones,
    CT_SOLICITUDES_CT2_FASE16.ObservacionesGestorFase16

FROM CT_SOLICITUDES_CT2

LEFT JOIN CT_SOLICITUDES_CT2_FASE1 
    ON CT_SOLICITUDES_CT2.IDSolicitudCambio = CT_SOLICITUDES_CT2_FASE1.IDSolicitudCambio
LEFT JOIN CT_SOLICITUDES_CT2_FASE2 
    ON CT_SOLICITUDES_CT2.IDSolicitudCambio = CT_SOLICITUDES_CT2_FASE2.IDSolicitudCambio
LEFT JOIN CT_SOLICITUDES_CT2_FASE3 
    ON CT_SOLICITUDES_CT2.IDSolicitudCambio = CT_SOLICITUDES_CT2_FASE3.IDSolicitudCambio
LEFT JOIN CT_SOLICITUDES_CT2_FASE4 
    ON CT_SOLICITUDES_CT2.IDSolicitudCambio = CT_SOLICITUDES_CT2_FASE4.IDSolicitudCambio
LEFT JOIN CT_SOLICITUDES_CT2_FASE5 
    ON CT_SOLICITUDES_CT2.IDSolicitudCambio = CT_SOLICITUDES_CT2_FASE5.IDSolicitudCambio
LEFT JOIN CT_SOLICITUDES_CT2_FASE6 
    ON CT_SOLICITUDES_CT2.IDSolicitudCambio = CT_SOLICITUDES_CT2_FASE6.IDSolicitudCambio
LEFT JOIN CT_SOLICITUDES_CT2_FASE7 
    ON CT_SOLICITUDES_CT2.IDSolicitudCambio = CT_SOLICITUDES_CT2_FASE7.IDSolicitudCambio
LEFT JOIN CT_SOLICITUDES_CT2_FASE8 
    ON CT_SOLICITUDES_CT2.IDSolicitudCambio = CT_SOLICITUDES_CT2_FASE8.IDSolicitudCambio
LEFT JOIN CT_SOLICITUDES_CT2_FASE9 
    ON CT_SOLICITUDES_CT2.IDSolicitudCambio = CT_SOLICITUDES_CT2_FASE9.IDSolicitudCambio
LEFT JOIN CT_SOLICITUDES_CT2_FASE10 
    ON CT_SOLICITUDES_CT2.IDSolicitudCambio = CT_SOLICITUDES_CT2_FASE10.IDSolicitudCambio
LEFT JOIN CT_SOLICITUDES_CT2_FASE11 
    ON CT_SOLICITUDES_CT2.IDSolicitudCambio = CT_SOLICITUDES_CT2_FASE11.IDSolicitudCambio
LEFT JOIN CT_SOLICITUDES_CT2_FASE12 
    ON CT_SOLICITUDES_CT2.IDSolicitudCambio = CT_SOLICITUDES_CT2_FASE12.IDSolicitudCambio
LEFT JOIN CT_SOLICITUDES_CT2_FASE13 
    ON CT_SOLICITUDES_CT2.IDSolicitudCambio = CT_SOLICITUDES_CT2_FASE13.IDSolicitudCambio
LEFT JOIN CT_SOLICITUDES_CT2_FASE14 
    ON CT_SOLICITUDES_CT2.IDSolicitudCambio = CT_SOLICITUDES_CT2_FASE14.IDSolicitudCambio
LEFT JOIN CT_SOLICITUDES_CT2_FASE14_1 
    ON CT_SOLICITUDES_CT2.IDSolicitudCambio = CT_SOLICITUDES_CT2_FASE14_1.IDSolicitudCambio
LEFT JOIN CT_SOLICITUDES_CT2_FASE15 
    ON CT_SOLICITUDES_CT2.IDSolicitudCambio = CT_SOLICITUDES_CT2_FASE15.IDSolicitudCambio
LEFT JOIN CT_SOLICITUDES_CT2_FASE16 
    ON CT_SOLICITUDES_CT2.IDSolicitudCambio = CT_SOLICITUDES_CT2_FASE16.IDSolicitudCambio;