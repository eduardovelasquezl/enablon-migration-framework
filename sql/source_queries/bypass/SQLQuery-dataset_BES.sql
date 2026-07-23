SELECT        ITP_BES.IDBES, ITP_BES.IDFlujo, ITP_BES.IDCentro, ITP_BES.IDEmpresa, ITP_BES.IDCreador, ITP_BES.FechaCreacion, ITP_BES.IDEstado, ITP_BES_TiposEstados.Estado, ITP_BES.FaseActual, 
                         ITP_BES.FechaUltimaModificacion, ITP_BES.IDUsuarioUltimaModificacion, ITP_BES.IDGrupoResponsableFaseActual, ITP_BES.FechaAnulacion, ITP_BES.UnidadOperativa, ITP_BES.IDUnidadOrg, ITP_BES.IDDepartamento, 
                         ITP_BES.Equipo, ITP_BES.TAG, ITP_BES.Descripcion, ITP_BES.IDTipoSCE, ITP_BES_TiposSCE.TipoSCE, ITP_BES.IDTipoBypass, ITP_BES_TiposBypass.TipoBypass, ITP_BES.NivelSIL, ITP_BES.IDMetodoBypass, 
                         ITP_BES_MetodosBypass.MetodoBypass, ITP_BES.IDCausa, ITP_BES_Causas.Causa, ITP_BES.Motivo, ITP_BES.MedidasCompensatorias, ITP_BES.FechaEstimadaPuestaServicioFase1, ITP_BES.IDIniciadorAutorizacion, 
                         ITP_BES.IDGrupoResponsableFase1, ITP_BES.IDUsuarioEnvioFase1, ITP_BES.FechaEnvioFase1, ITP_BES.MotivoAprobacionFase2, ITP_BES.AmpliacionMedidasCompensatoriasFase2, 
                         ITP_BES.FechaEstimadaPuestaServicioFase2, ITP_BES.AutorizaOPoneEnServicioFase2, ITP_BES.IDGrupoResponsableFase2, ITP_BES.IDUsuarioEnvioFase2, ITP_BES.FechaEnvioFase2, ITP_BES.MotivoAprobacionFase3, 
                         ITP_BES.AmpliacionMedidasCompensatoriasFase3, ITP_BES.FechaEstimadaPuestaServicioFase3, ITP_BES.AutorizaOPoneEnServicioFase3, ITP_BES.IDGrupoResponsableFase3, ITP_BES.IDUsuarioEnvioFase3, 
                         ITP_BES.FechaEnvioFase3, ITP_BES.NumCambioTecnico, ITP_BES.AccionesDerivadas, ITP_BES.FechaEstimadaPuestaServicioFase4, ITP_BES.AutorizaOPoneEnServicioFase4, ITP_BES.IDGrupoResponsableFase4, 
                         ITP_BES.IDUsuarioEnvioFase4, ITP_BES.FechaEnvioFase4, ITP_BES.TieneGOS, ITP_BES.MotivoAprobacion, ITP_BES.Autorizar, ITP_BES.IDGrupoResponsableFase5, ITP_BES.IDUsuarioEnvioFase5, 
                         ITP_BES.FechaEnvioFase5, ITP_BES.VueltaOperacionNormal, ITP_BES.ComprobacionImplantacionACs, ITP_BES.PuestoEnServicioOAnulado, ITP_BES.FechaPuestaEnServicio, ITP_BES.NumPermisoTrabajo, 
                         ITP_BES.IDIniciadorEjecutadoPor, ITP_BES.IDIniciadorAutorizadoPor, ITP_BES.IDGrupoResponsableFase6, ITP_BES.IDUsuarioEnvioFase6, ITP_BES.FechaEnvioFase6
FROM            ITP_BES INNER JOIN
                         ITP_BES_MetodosBypass ON ITP_BES.IDMetodoBypass = ITP_BES_MetodosBypass.IDMetodoBypass  JOIN
                         ITP_BES_TiposBypass ON ITP_BES.IDTipoBypass = ITP_BES_TiposBypass.IDTipoBypass  JOIN
                         ITP_BES_TiposEstados ON ITP_BES.IDEstado = ITP_BES_TiposEstados.IDEstado JOIN
                         ITP_BES_TiposSCE ON ITP_BES.IDTipoSCE = ITP_BES_TiposSCE.IDTipoSCE JOIN
                         ITP_BES_Causas ON ITP_BES.IDCausa = ITP_BES_Causas.IDCausa