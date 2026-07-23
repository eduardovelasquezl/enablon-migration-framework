SELECT        
    ic.IDInformeCheckList,
    FORMAT(ic.Fecha, 'dd/MM/yyyy HH:mm:ss') AS Fecha,
    ic.IDCentro,
    ic.IDEmpresa,
    ic.IDDepartamento,
    ic.IDUnidadOrganizativa,
    ic.IDContratista,
    ic.NumPermisoTrabajo,
    ic.NumCertificadoAislamiento,
    ic.OtroContratista,
    ic.ComentarioGeneral,
    ic.IDEstado,
    ic.IDUsuario,
    FORMAT(ic.fechaCreacion, 'dd/MM/yyyy HH:mm:ss') AS fechaCreacion,
    ic.Aceptable,
    ic.NumRojosPlanificacionDef,
    ic.NumRojosEvaluacionRiesgos,
    ic.NumRojosEjecucionTrabajo,
    ic.NumRojosPreparacion,
    ic.NumRojosCierre,
    ic.NumNaranjasNoAceptables,
    ic.NearMisses,
    ic.NumNegrasTotal,

    ic.IDTipoPermisoTrabajo,
    mtp.Descripcion AS NombreTipoPermiso,

    ic.IDSeguridad,
    ic.IdUsuarioCreador,
    ic.Zona,

    ic.IdTipoTrabajo,
    mtt.Descripcion AS NombreTipoTrabajo

FROM ITP_INFORMECHECKLISTPT ic

LEFT JOIN ITP_MAESTROS mtp 
    ON mtp.IDMaestro = ic.IDTipoPermisoTrabajo
    -- AND mtp.IDTipoMaestro = <ID_DEL_TIPO_PERMISO>

LEFT JOIN ITP_MAESTROS mtt 
    ON mtt.IDMaestro = ic.IdTipoTrabajo
    -- AND mtt.IDTipoMaestro = <ID_DEL_TIPO_TRABAJO>
