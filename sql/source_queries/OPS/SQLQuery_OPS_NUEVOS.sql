SELECT [IdOps]
      ,format([FechaRealizacion], 'dd/MM/yyyy HH:mm:ss' ) as FechaRealizacion
      ,[IdCentro]
      ,[IdEmpresa]
      ,[Observador]
      ,[OtroObservador]
      ,[IdDepartamento]
      ,[IdUnidadOrganizativa]
      ,[EmpresaObservada]
      ,[TareaObservada]
      ,[DescTareaObservada]
      ,[TipoPermiso]
      ,[NPermisoTrabajo]
      ,[NearMiss]
      ,[TipologiaDesviacion]
      ,[ReglasSalvavidas]
      ,[AccionesInmediatas]
      ,[BuenasPracticas]
      ,[Gravedad]
      ,format([FechaCreacion], 'dd/MM/yyyy HH:mm:ss' ) as FechaCreacion
      ,format([FechaUltimaModificacion], 'dd/MM/yyyy HH:mm:ss' ) as FechaUltimaModificacion
      ,[IdUsuarioUltimaModificacion]
      ,[Estado]
      ,[TieneDesviaciones]
      ,[EquipoProteccionIndividual]
  FROM [Prevencion].[dbo].[ITP_OPS2]-- where FechaUltimaModificacion < '2025-01-01 00:00:00.000' 
  order by idOps asc
