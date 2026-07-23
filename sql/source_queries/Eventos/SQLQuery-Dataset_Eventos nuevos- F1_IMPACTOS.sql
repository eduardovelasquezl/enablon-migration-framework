SELECT
    I.IDInformeInv,
    I.IDEvento,
    I.IDFlujo,
    I.FaseActual,
    FORMAT(I.FechaCreacion, 'dd/MM/yyyy HH:mm:ss') AS FechaCreacion,
    FORMAT(I.FechaUltimaModificacion, 'dd/MM/yyyy HH:mm:ss') AS FechaUltimaModificacion,
    I.IDUsuarioModificacion,
    I.IDEstado,
    I.IDGrupoResponsableFaseActual,

    F1.IDInfFase1,
    F1.IDEstado AS Estado_F1,
    FORMAT(F1.FechaEnvioFase, 'dd/MM/yyyy HH:mm:ss') AS FechaEnvioFase,

    -- 🔹 Consecuencia explotada
    CAST(LTRIM(RTRIM(X.C.value('.', 'varchar(100)'))) AS INT) AS IDConsecuencia,
    M.Descripcion AS NombreConsecuencia,   

    F1.CategoriaAccidenteIndustrial,
    F1.CantidadFugadaDerramada,
    F1.ProductoFugadoDerramado,
    F1.DescripcionEvento,
    F1.Duracion,
    F1.IDEmpresaExterna,
    F1.PermisoTrabajo,
    F1.LugarAccidente,
    F1.TipoTarea,
    F1.AccionesAdoptadas,
    F1.Participante,
    F1.NivelPSEEstimado

FROM ITP_INFORME_INV2 I
FULL JOIN ITP_INFORME_INV2_FASE1 F1
    ON I.IDInformeInv = F1.IDInformeInv

-- 🔹 Explosión de Consecuencias
CROSS APPLY (
    SELECT CAST(
        '<x>' + REPLACE(F1.ConsecuenciasReales, ',', '</x><x>') + '</x>'
        AS XML
    ) AS XmlData
) A
CROSS APPLY A.XmlData.nodes('/x') X(C)

-- 🔹 JOIN a Maestros
LEFT JOIN ITP_MAESTROS M
    ON M.IDMaestro = CAST(LTRIM(RTRIM(X.C.value('.', 'varchar(100)'))) AS INT);
