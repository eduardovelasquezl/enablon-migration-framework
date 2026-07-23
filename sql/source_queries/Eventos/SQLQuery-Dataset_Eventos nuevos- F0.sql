SELECT        ITP_ANALISIS_EVENTO.IDEvento,
ITP_ANALISIS_EVENTO.IDCentro,
ITP_ANALISIS_EVENTO.IDEmpresa,
ITP_ANALISIS_EVENTO.DescripcionEvento,
format(ITP_ANALISIS_EVENTO.FechaEvento,  'dd/MM/yyyy HH:mm:ss') as FechaEvento,
format(ITP_ANALISIS_EVENTO.FechaCreacion,  'dd/MM/yyyy HH:mm:ss') as FechaCreacion, 
format(ITP_ANALISIS_EVENTO.FechaUltimaModificacion,  'dd/MM/yyyy HH:mm:ss') as FechaUltimaModificacion,
ITP_ANALISIS_EVENTO.IDUsuarioUltMod,
ITP_ANALISIS_EVENTO.SinInfInvestigacion,
ITP_ANALISIS_EVENTO.IDUnidadOrg,
ITP_ANALISIS_EVENTO.IDDepartamento, 
ITP_ANALISIS_EVENTO.NearMisses,
ITP_INFORME_INV2.IDInformeInv,
ITP_INFORME_INV2.IDFlujo,
ITP_INFORME_INV2.FaseActual,
format(ITP_INFORME_INV2.FechaCreacion,  'dd/MM/yyyy HH:mm:ss') as  FechaCreacion_f1,
format(ITP_INFORME_INV2.FechaUltimaModificacion,  'dd/MM/yyyy HH:mm:ss') as  FechaUltimaModificacion_f1,
ITP_INFORME_INV2.IDUsuarioModificacion,
ITP_INFORME_INV2.IDEstado,
ITP_MAESTROS.Descripcion as Desc_Estado,
ITP_INFORME_INV2.IDGrupoResponsableFaseActual
FROM            ITP_ANALISIS_EVENTO full JOIN
                         ITP_INFORME_INV2 ON ITP_ANALISIS_EVENTO.IDEvento = ITP_INFORME_INV2.IDEvento
                         left join ITP_MAESTROS on ITP_MAESTROS.IDMaestro = ITP_INFORME_INV2.IDEstado

