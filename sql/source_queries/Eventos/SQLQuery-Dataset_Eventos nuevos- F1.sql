SELECT        ITP_INFORME_INV2.IDInformeInv, ITP_INFORME_INV2.IDEvento, ITP_INFORME_INV2.IDFlujo, ITP_INFORME_INV2.FaseActual,
format( ITP_INFORME_INV2.FechaCreacion,   'dd/MM/yyyy HH:mm:ss') as FechaCreacion,
format( ITP_INFORME_INV2.FechaUltimaModificacion,   'dd/MM/yyyy HH:mm:ss') as FechaUltimaModificacion,
                         ITP_INFORME_INV2.IDUsuarioModificacion, ITP_INFORME_INV2.IDEstado,
                         ITP_INFORME_INV2.IDGrupoResponsableFaseActual,
                         ITP_INFORME_INV2_FASE1.IDInfFase1,
                         ITP_INFORME_INV2_FASE1.IDEstado AS Estado_F1,
                         
                         format( ITP_INFORME_INV2_FASE1.FechaEnvioFase,   'dd/MM/yyyy HH:mm:ss') as FechaEnvioFase
                         , ITP_INFORME_INV2_FASE1.ConsecuenciasReales,
                         ITP_INFORME_INV2_FASE1.CategoriaAccidenteIndustrial,
                         ITP_INFORME_INV2_FASE1.CantidadFugadaDerramada, 
                         ITP_INFORME_INV2_FASE1.ProductoFugadoDerramado,
                         ITP_INFORME_INV2_FASE1.DescripcionEvento,
                         ITP_INFORME_INV2_FASE1.Duracion,
                         ITP_INFORME_INV2_FASE1.IDEmpresaExterna, 
                         ITP_INFORME_INV2_FASE1.PermisoTrabajo,
                         ITP_INFORME_INV2_FASE1.LugarAccidente,
                         ITP_INFORME_INV2_FASE1.TipoTarea,
                         ITP_INFORME_INV2_FASE1.AccionesAdoptadas,
                         ITP_INFORME_INV2_FASE1.Participante, 
                         ITP_INFORME_INV2_FASE1.NivelPSEEstimado
FROM            ITP_INFORME_INV2 full JOIN
                         ITP_INFORME_INV2_FASE1 ON ITP_INFORME_INV2.IDInformeInv = ITP_INFORME_INV2_FASE1.IDInformeInv