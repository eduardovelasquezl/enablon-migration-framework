SELECT  [IDSimulacro]
      ,[IDFlujo]
      ,[IDCentro]
      ,[IDEmpresa]
      ,format([FechaCreacion], 'dd/MM/yyyy HH:mm:ss' ) as FechaCreacion
      ,format([FechaUltimaModificacion], 'dd/MM/yyyy HH:mm:ss' ) as FechaUltimaModificacion
      ,[IDUsuarioUltimaModificacion]
      ,[IDTipo]
      ,format([Fecha], 'dd/MM/yyyy HH:mm:ss') as Fecha
      ,[Hora]
      ,'' as FechaHoraCombinado
      ,[IDGrupoIniciador]
      ,[Estado]
      ,[IDGrupoResponsableFaseActual]
      ,[FaseActual]
      ,[IDGrupoResponsableFase1]
      ,[IDUsuarioEnvioFase1]
      ,format([FechaEnvioFase1], 'dd/MM/yyyy HH:mm:ss') as FechaEnvioFase1
      ,[IDDepartamento]
      ,[IDUnidadOrg]
      ,[IDLetra]
      ,[Norma]
      
      ,[Duracion]
      ,[BreveDescripcion]
      ,[HipotesisAccidental]
      ,[Asistentes]
      ,[NumAsistentes]
      ,[Comentarios]
      ,[IDResponsable]
      ,[Auditado]
      ,[Ejercicio]
      ,[IDGrupoResponsableFase2]
      ,[IDUsuarioEnvioFase2]
      ,format([FechaEnvioFase2], 'dd/MM/yyyy HH:mm:ss') as [FechaEnvioFase2]
      ,[Observaciones]
      ,[Aprobacion]
      ,format([FechaFinalizacion], 'dd/MM/yyyy HH:mm:ss') as [FechaFinalizacion]
  FROM [Prevencion].[dbo].[ITP_SIMULACRO]

 
                         order by FechaCreacion asc
